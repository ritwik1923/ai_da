import pandas as pd
import numpy as np
from typing import Dict, Any
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence, 
    safe_builtins,
    safer_getattr,
    full_write_guard
)
import json
import re


def _getitem_(obj, index):
    """Safe getitem implementation for RestrictedPython"""
    return obj[index]


def _clean_code(code: str) -> str:
    """
    Remove non-code text from the code string.
    This is critical because the LLM may mix ReAct format lines into the code.
    """
    # FIRST: Cut off at any ReAct format keyword that appears
    # This prevents "Thought:", "Action:", etc. from being treated as code
    react_keywords = ['Thought:', 'Action:', 'Observation:', 'Action Input:', 'Final Answer:']
    for keyword in react_keywords:
        if keyword in code:
            code = code.split(keyword)[0]
    
    # Now clean up individual lines
    lines = code.split('\n')
    cleaned = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            cleaned.append(line)
            continue
        
        # Skip markdown code blocks
        if stripped == '```' or stripped.startswith('```'):
            continue
        
        # Skip lines that are clearly natural language explanations
        lower_line = stripped.lower()
        if any(phrase in lower_line for phrase in [
            'please wait',
            'i\'ll',
            "i will",
            'here\'s',
            'here is',
            'now i',
            'let me',
            'as you can see',
            'the code',
            'this code',
            'executing',
            'analyzing',
            'calculating',
            'note:',
            'example:',
            'explanation:',
            'in this corrected',
            'in the corrected',
            'in python',
            'should resolve',
            'this should',
            'will help',
            'to perform',
            'to identify',
            'to analyze',
        ]):
            continue
        
        # Skip obvious comment lines that are explanations
        if stripped.startswith('#') and any(word in stripped.lower() for word in ['wait', 'please', 'example', 'explanation']):
            continue
        
        cleaned.append(line)
    
    result = '\n'.join(cleaned).strip()
    
    # If result is empty or too short, return original
    if not result or len(result) < 3:
        return code
    
    return result

    # If result is empty or too short, return original
    if not result or len(result) < 5:
        return code
    
    return result


def safe_execute_pandas_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Safely execute Pandas code with restricted permissions
    
    Args:
        code: Python/Pandas code to execute
        df: DataFrame to analyze
        
    Returns:
        Dictionary with execution results
    """
    
    # Clean the code to remove non-code text that LLMs might include
    code = _clean_code(code)
    
    # Create a safe execution environment
    safe_locals = {
        'df': df,
        'pd': pd,
        '__builtins__': safe_builtins,
        '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        '_getiter_': lambda x: iter(x),
        '_getitem_': _getitem_,
        '_getattr_': safer_getattr,
        '_write_': full_write_guard,
        'json': json,
    }
    
    # Add safe globals
    safe_locals.update(safe_globals)
    
    try:
        # Compile with RestrictedPython
        byte_code = compile_restricted(
            code,
            filename='<inline code>',
            mode='exec'
        )
        
        # Execute the code
        exec(byte_code, safe_locals)
        
        # Extract result (assume it's stored in 'result' variable)
        result = safe_locals.get('result', None)
        
        # Convert result to serializable format
        if isinstance(result, pd.DataFrame):
            return {
                'type': 'dataframe',
                'data': result.to_dict(orient='records'),
                'columns': list(result.columns),
                'shape': result.shape
            }
        elif isinstance(result, pd.Series):
            return {
                'type': 'series',
                'data': result.to_dict(),
                'name': result.name
            }
        elif isinstance(result, (int, float, str, bool, np.integer, np.floating)):
            return {
                'type': 'scalar',
                'value': result if isinstance(result, (int, float, str, bool)) else result.item()
            }
        elif isinstance(result, dict):
            return {
                'type': 'dict',
                'data': result
            }
        elif isinstance(result, list):
            return {
                'type': 'list',
                'data': result
            }
        else:
            return {
                'type': 'unknown',
                'value': str(result)
            }
            
    except Exception as e:
        raise Exception(f"Code execution failed: {str(e)}")


def validate_pandas_code(code: str) -> bool:
    """
    Validate that code is safe to execute
    
    Args:
        code: Python code to validate
        
    Returns:
        True if safe, raises Exception otherwise
    """
    
    # Blacklist dangerous operations
    dangerous_keywords = [
        'import os',
        'import sys',
        'import subprocess',
        '__import__',
        'eval',
        'exec',
        'compile',
        'open(',
        'file(',
        'input(',
        'raw_input(',
    ]
    
    code_lower = code.lower()
    for keyword in dangerous_keywords:
        if keyword in code_lower:
            raise Exception(f"Dangerous operation detected: {keyword}")
    
    return True
