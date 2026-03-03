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


# def _clean_code(code: str) -> str:
#     """
#     Enhanced cleaning to remove natural language and repair Mistral syntax errors.
#     """
#     # 1. FIX MISTRAL NESTING: Remove tool name if LLM wrote Action Input: execute_pandas_code("...")
#     code = re.sub(r"execute_pandas_code\s*\(\s*['\"]+(.*?)['\"]+\s*\)", r"\1", code, flags=re.DOTALL)
    
#     # 2. FIX MISTRAL BRACKET SYNTAX: Change df'Col1', 'Col2' to df[['Col1', 'Col2']]
#     # This specifically targets the comma-separated strings outside of actual list brackets.
#     code = re.sub(r"df\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", r"df[['\1', '\2']]", code)

#     # 3. FIX MISSING BRACKETS: Change dfnumeric_columns to df[numeric_columns]
#     code = re.sub(r"df([a-zA-Z_][a-zA-Z0-9_]*)", r"df[\1]", code)

#     # Cut off at any ReAct format keyword that appears
#     react_keywords = ['Thought:', 'Action:', 'Observation:', 'Action Input:', 'Final Answer:']
#     for keyword in react_keywords:
#         if keyword in code:
#             code = code.split(keyword)[0]
    
#     lines = code.split('\n')
#     cleaned = []
    
#     for line in lines:
#         stripped = line.strip()
#         if not stripped:
#             cleaned.append(line)
#             continue
        
#         # Skip markdown code blocks
#         if stripped.startswith('```'):
#             continue
        
#         # Skip natural language phrases Mistral loves to include
#         lower_line = stripped.lower()
#         if any(phrase in lower_line for phrase in [
#             'please wait', 'i\'ll', 'i will', 'here\'s', 'here is', 'now i', 'let me',
#             'as you can see', 'the code', 'this code', 'executing', 'analyzing',
#             'calculating', 'note:', 'example:', 'explanation:', 'in this corrected',
#             'in python', 'should resolve', 'this should', 'will help'
#         ]):
#             continue
        
#         cleaned.append(line)
    
#     result = '\n'.join(cleaned).strip()
#     return result if len(result) >= 3 else code

# def _clean_code(code: str) -> str:
#     # 1. REMOVE NESTED TOOL CALLS (Mistral's biggest loop issue)
#     # Fixes: result = execute_pandas_code("result = df.corr()") -> result = df.corr()
#     code = re.sub(r"execute_pandas_code\s*\(\s*['\"]+(.*?)['\"]+\s*\)", r"\1", code, flags=re.DOTALL)
    
#     # 2. FIX SELECT_DTYPES SYNTAX (Mistral's current crash)
#     # Fixes: include='int64', 'float64' -> include=['int64', 'float64']
#     code = re.sub(r"include\s*=\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", r"include=['\1', '\2']", code)

#     # 3. FIX BRACKET HALLUCINATIONS
#     # Fixes: df'Phone 1', 'Phone 2' -> df[['Phone 1', 'Phone 2']]
#     code = re.sub(r"df\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", r"df[['\1', '\2']]", code)
    
#     # 4. FIX CONCATENATED VARIABLE NAMES
#     # Fixes: dfnumeric_columns -> df[numeric_columns]
#     # We only apply this if it's not already bracketed
#     code = re.sub(r"df(?![\[])([a-zA-Z_][a-zA-Z0-9_]*)", r"df[\1]", code)

#     # Standard cleaning (same as your current script)
#     react_keywords = ['Thought:', 'Action:', 'Observation:', 'Action Input:', 'Final Answer:']
#     for keyword in react_keywords:
#         if keyword in code:
#             code = code.split(keyword)[0]
            
#     lines = code.split('\n')
#     cleaned = [line for line in lines if not any(phrase in line.lower() for phrase in ['i will', 'here is', 'corrected code', '```'])]
    
#     return '\n'.join(cleaned).strip()

def _clean_code(code: str) -> str:
    lines = code.split('\n')
    cleaned = []
    
    for line in lines:
        s = line.strip()
        # Strip imports - RestrictedPython will fail on these anyway
        if s.startswith('import ') or s.startswith('from '):
            continue
        # Strip dummy data creation if it looks like data = {...} or df = pd.DataFrame(...)
        if s.startswith('data =') or s.startswith('df = pd.DataFrame'):
            continue
        cleaned.append(line)
        
    return '\n'.join(cleaned).strip()

def safe_execute_pandas_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Safely execute Pandas code with restricted permissions and auto-repair.
    """
    # First, validate against hard-coded dangerous keywords
    validate_pandas_code(code)
    
    # Clean and repair the code syntax
    code = _clean_code(code)
    
    # Create a safe execution environment
    safe_locals = {
        'df': df,
        'pd': pd,
        'np': np,
        're': re,  
        '__builtins__': safe_builtins,
        '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        '_getiter_': lambda x: iter(x),
        '_getitem_': _getitem_,
        '_getattr_': safer_getattr,
        '_write_': full_write_guard,
        'json': json,
    }
    safe_locals.update(safe_globals)
    
    try:
        # Pre-execution check: If correlation is called without numeric filter, auto-inject it
        # This fixes the common "could not convert string to float" error
        if '.corr()' in code and 'select_dtypes' not in code:
            code = code.replace('.corr()', ".select_dtypes(include='number').corr()")

        byte_code = compile_restricted(code, filename='<inline code>', mode='exec')
        exec(byte_code, safe_locals)
        
        result = safe_locals.get('result', None)
        
        # Formatting the output
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
                'name': str(result.name)
            }
        elif isinstance(result, (int, float, str, bool, np.integer, np.floating)):
            return {
                'type': 'scalar',
                'value': result if isinstance(result, (int, float, str, bool)) else result.item()
            }
        elif isinstance(result, (dict, list)):
            return {'type': 'collection', 'data': result}
        else:
            return {'type': 'unknown', 'value': str(result)}
            
    except Exception as e:
        # Pass the error back to the SelfHealingExecutor
        raise Exception(f"Code execution failed: {str(e)}")


def validate_pandas_code(code: str) -> bool:
    """Validate that code is safe to execute"""
    dangerous_keywords = [
        'import os', 'import sys', 'import subprocess', '__import__',
        'eval', 'exec', 'compile', 'open(', 'file(', 'input('
    ]
    
    code_lower = code.lower()
    for keyword in dangerous_keywords:
        if keyword in code_lower:
            # We allow exec only for the internal RestrictedPython call
            if keyword == 'exec' and 'compile_restricted' in code:
                continue
            raise Exception(f"Dangerous operation detected: {keyword}")
    
    return True