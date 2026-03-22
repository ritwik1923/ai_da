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
        'eval', 'exec', 'compile', 'open(', 'file(', 'input(',
        'matplotlib', 'pyplot', 'plt.', '.show(', '.plot('
    ]
    
    code_lower = code.lower()
    for keyword in dangerous_keywords:
        if keyword in code_lower:
            # We allow exec only for the internal RestrictedPython call
            if keyword == 'exec' and 'compile_restricted' in code:
                continue
            raise Exception(f"Dangerous operation detected: {keyword}")
    
    return True