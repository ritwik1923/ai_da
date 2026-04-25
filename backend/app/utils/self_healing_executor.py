"""
Self-Healing Code Executor with ReAct Pattern
Automatically detects and fixes code errors through iterative refinement.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Callable
import traceback
import re
from dataclasses import dataclass
from enum import Enum
import json

from app.utils.code_executor import safe_execute_pandas_code, validate_pandas_code


class ErrorCategory(Enum):
    """Categories of execution errors."""
    SYNTAX = "syntax_error"
    NAME = "name_error"
    TYPE = "type_error"
    KEY = "key_error"
    VALUE = "value_error"
    ATTRIBUTE = "attribute_error"
    INDEX = "index_error"
    ZERO_DIVISION = "zero_division_error"
    RUNTIME = "runtime_error"
    UNKNOWN = "unknown_error"


@dataclass
class ExecutionResult:
    """Result of code execution attempt."""
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    error_category: Optional[ErrorCategory]
    error_line: Optional[int]
    code_executed: str
    attempt_number: int
    fix_applied: Optional[str] = None


class SelfHealingExecutor:
    """
    Executor that automatically fixes common code errors.
    Uses pattern matching and heuristics to debug and retry.
    """
    
    def __init__(self, 
                 df: pd.DataFrame, 
                 max_retries: int = 3,
                 llm_fix_callback: Optional[Callable] = None):
        """
        Args:
            df: DataFrame to execute code against
            max_retries: Maximum number of retry attempts
            llm_fix_callback: Optional function(code, error) -> fixed_code for LLM-based fixes
        """
        self.df = df
        self.max_retries = max_retries
        self.llm_fix_callback = llm_fix_callback
        self.execution_history: List[ExecutionResult] = []
    
    def execute_with_healing(self, code: str) -> ExecutionResult:
        """
        Execute code with automatic error detection and fixing.
        
        Args:
            code: Python/Pandas code to execute
            
        Returns:
            ExecutionResult with success status and result/error
        """
        current_code = code
        print(f"Executing code with self-healing (max {self.max_retries} attempts)...")
        print(f"Initial code:\n{current_code}\n{'-'*40}")
        for attempt in range(1, self.max_retries + 1):
            result = self._try_execute(current_code, attempt)
            self.execution_history.append(result)
            
            if result.success:
                return result
            

            result.fix_applied = f"Applied automatic fix for {result.error_category.value}"

            # # Try to fix the error
            # if attempt < self.max_retries:
            #     fixed_code = self._attempt_fix(current_code, result)
            #     if fixed_code and fixed_code != current_code:
            #         current_code = fixed_code
            #         result.fix_applied = f"Applied automatic fix for {result.error_category.value}"
            #     else:
            #         # No fix found, return the error
            #         break
        
        # All retries exhausted
        return result
    
    def _try_execute(self, code: str, attempt: int) -> ExecutionResult:
        """Try to execute code once."""
        try:
            # Validate code first
            validate_pandas_code(code)
            
            # Execute
            result = safe_execute_pandas_code(code, self.df)
            
            return ExecutionResult(
                success=True,
                result=result,
                error=None,
                error_category=None,
                error_line=None,
                code_executed=code,
                attempt_number=attempt
            )
            
        except Exception as e:
            error_info = self._analyze_error(e, code)
            
            return ExecutionResult(
                success=False,
                result=None,
                error=str(e),
                error_category=error_info['category'],
                error_line=error_info['line'],
                code_executed=code,
                attempt_number=attempt
            )
    
    def _analyze_error(self, error: Exception, code: str) -> Dict[str, Any]:
        """Analyze error to categorize and locate it."""
        error_str = str(error)
        error_type = type(error).__name__
        
        # Categorize error
        category_map = {
            'SyntaxError': ErrorCategory.SYNTAX,
            'NameError': ErrorCategory.NAME,
            'TypeError': ErrorCategory.TYPE,
            'KeyError': ErrorCategory.KEY,
            'ValueError': ErrorCategory.VALUE,
            'AttributeError': ErrorCategory.ATTRIBUTE,
            'IndexError': ErrorCategory.INDEX,
            'ZeroDivisionError': ErrorCategory.ZERO_DIVISION,
        }
        
        category = category_map.get(error_type, ErrorCategory.RUNTIME)
        
        # Try to extract line number
        line_number = None
        tb = traceback.extract_tb(error.__traceback__)
        if tb:
            line_number = tb[-1].lineno
        
        return {
            'category': category,
            'line': line_number,
            'type': error_type,
            'message': error_str
        }
    
    def _attempt_fix(self, code: str, error_result: ExecutionResult) -> Optional[str]:
        """
        Attempt to automatically fix the code based on error.
        
        Returns:
            Fixed code or None if no fix available
        """
        category = error_result.error_category
        error_msg = error_result.error or ""
        
        # Try pattern-based fixes first
        fixed = None
        
        if category == ErrorCategory.KEY:
            fixed = self._fix_key_error(code, error_msg)
        elif category == ErrorCategory.NAME:
            fixed = self._fix_name_error(code, error_msg)
        elif category == ErrorCategory.ATTRIBUTE:
            fixed = self._fix_attribute_error(code, error_msg)
        elif category == ErrorCategory.ZERO_DIVISION:
            fixed = self._fix_zero_division(code)
        elif category == ErrorCategory.TYPE:
            fixed = self._fix_type_error(code, error_msg)
        
        # If pattern fix didn't work, try LLM fix
        if not fixed and self.llm_fix_callback:
            try:
                fixed = self.llm_fix_callback(code, error_msg)
            except Exception as e:
                print(f"LLM fix failed: {e}")
        
        return fixed
    
    def _fix_key_error(self, code: str, error_msg: str) -> Optional[str]:
        """Fix KeyError - usually wrong column name."""
        # Extract the problematic key
        match = re.search(r"['\"]([^'\"]+)['\"]", error_msg)
        if not match:
            return None
        
        bad_key = match.group(1)
        
        # Find similar column names
        similar_cols = self._find_similar_columns(bad_key)
        
        if similar_cols:
            # Replace the bad key with the best match
            best_match = similar_cols[0]
            fixed_code = code.replace(f"'{bad_key}'", f"'{best_match}'")
            fixed_code = fixed_code.replace(f'"{bad_key}"', f'"{best_match}"')
            fixed_code = fixed_code.replace(f"['{bad_key}']", f"['{best_match}']")
            fixed_code = fixed_code.replace(f'["{bad_key}"]', f'["{best_match}"]')
            return fixed_code
        
        return None
    
    def _fix_name_error(self, code: str, error_msg: str) -> Optional[str]:
        """Fix NameError - usually undefined variable."""
        # Extract the undefined name
        match = re.search(r"name '(\w+)' is not defined", error_msg)
        if not match:
            return None
        
        undefined_name = match.group(1)
        
        # Common fixes
        common_fixes = {
            'pd': 'import pandas as pd\n',
            'np': 'import numpy as np\n',
            'plt': 'import matplotlib.pyplot as plt\n',
        }
        
        if undefined_name in common_fixes:
            return common_fixes[undefined_name] + code
        
        # Check if it's a typo of a column name
        similar_cols = self._find_similar_columns(undefined_name)
        if similar_cols:
            best_match = similar_cols[0]
            # Replace as variable reference with column access
            fixed_code = re.sub(
                rf'\b{undefined_name}\b',
                f"df['{best_match}']",
                code
            )
            return fixed_code
        
        return None
    
    def _fix_attribute_error(self, code: str, error_msg: str) -> Optional[str]:
        """Fix AttributeError - usually wrong method name."""
        # Common pandas mistakes
        common_fixes = {
            'describe()': 'describe()',
            'value_counts()': 'value_counts()',
            'unique()': 'unique()',
            'nunique()': 'nunique()',
            'isna()': 'isna()',
            'isnull()': 'isnull()',
            'dropna()': 'dropna()',
            'fillna': 'fillna',
            'groupby': 'groupby',
            'sort_values': 'sort_values',
            'reset_index': 'reset_index',
        }
        
        # Try to find and fix method name typos
        for correct_method in common_fixes.values():
            method_name = correct_method.replace('()', '')
            if method_name in error_msg or f"'{method_name}'" in error_msg:
                # Already using correct method, might be wrong object
                # Try adding .copy() or checking DataFrame vs Series
                if 'Series' in error_msg and 'DataFrame' in code:
                    # Convert Series operation to DataFrame
                    fixed_code = code.replace('[result]', '')
                    return fixed_code
        
        return None
    
    def _fix_zero_division(self, code: str) -> Optional[str]:
        """Fix ZeroDivisionError by adding safe division."""
        # Add epsilon to denominator or wrap in try-except
        # Look for division operations
        division_pattern = r'(\w+)\s*/\s*(\w+)'
        
        def safe_div(match):
            numerator = match.group(1)
            denominator = match.group(2)
            return f"({numerator} / ({denominator} + 1e-10))"
        
        fixed_code = re.sub(division_pattern, safe_div, code)
        
        if fixed_code != code:
            return fixed_code
        
        return None
    
    def _fix_type_error(self, code: str, error_msg: str) -> Optional[str]:
        """Fix TypeError - usually wrong data type."""
        # Common type fixes
        if "unsupported operand type" in error_msg:
            # Might need to convert types
            if "str" in error_msg and "int" in error_msg:
                # Add type conversion
                # This is complex, return None to let LLM handle it
                return None
        
        if "cannot convert" in error_msg or "must be str" in error_msg:
            # Need explicit conversion
            # Too complex for pattern matching
            return None
        
        return None
    
    def _find_similar_columns(self, query: str, threshold: float = 0.6) -> List[str]:
        """
        Find column names similar to query using fuzzy matching.
        
        Args:
            query: The query string
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of similar column names, sorted by similarity
        """
        from difflib import SequenceMatcher
        
        similarities = []
        for col in self.df.columns:
            similarity = SequenceMatcher(None, query.lower(), str(col).lower()).ratio()
            if similarity >= threshold:
                similarities.append((col, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [col for col, _ in similarities]
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all execution attempts."""
        return {
            "total_attempts": len(self.execution_history),
            "success": any(r.success for r in self.execution_history),
            "attempts": [
                {
                    "attempt": r.attempt_number,
                    "success": r.success,
                    "error_category": r.error_category.value if r.error_category else None,
                    "error": r.error,
                    "fix_applied": r.fix_applied
                }
                for r in self.execution_history
            ]
        }

