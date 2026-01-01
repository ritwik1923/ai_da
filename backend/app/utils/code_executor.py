import pandas as pd
from typing import Dict, Any
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safe_builtins
import json


def safe_execute_pandas_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Safely execute Pandas code with restricted permissions
    
    Args:
        code: Python/Pandas code to execute
        df: DataFrame to analyze
        
    Returns:
        Dictionary with execution results
    """
    
    # Create a safe execution environment
    safe_locals = {
        'df': df,
        'pd': pd,
        '__builtins__': safe_builtins,
        '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        '_getiter_': lambda x: iter(x),
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
        elif isinstance(result, (int, float, str, bool)):
            return {
                'type': 'scalar',
                'value': result
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
