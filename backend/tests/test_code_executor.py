"""
Unit tests for code executor
Run with: pytest
"""

import pytest
import pandas as pd
from app.utils.code_executor import safe_execute_pandas_code, validate_pandas_code


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing"""
    return pd.DataFrame({
        'A': [1, 2, 3, 4, 5],
        'B': [10, 20, 30, 40, 50],
        'C': ['a', 'b', 'c', 'd', 'e']
    })


def test_simple_calculation(sample_df):
    """Test simple Pandas calculation"""
    code = "result = df['A'].sum()"
    result = safe_execute_pandas_code(code, sample_df)
    
    assert result['type'] == 'scalar'
    assert result['value'] == 15


def test_dataframe_operation(sample_df):
    """Test operation that returns a DataFrame"""
    code = "result = df[df['A'] > 2]"
    result = safe_execute_pandas_code(code, sample_df)
    
    assert result['type'] == 'dataframe'
    assert len(result['data']) == 3


def test_series_operation(sample_df):
    """Test operation that returns a Series"""
    code = "result = df['A'] * 2"
    result = safe_execute_pandas_code(code, sample_df)
    
    assert result['type'] == 'series'


def test_dangerous_code_blocked():
    """Test that dangerous code is blocked"""
    dangerous_codes = [
        "import os",
        "import sys",
        "open('file.txt')",
        "__import__('os')",
        "eval('print(1)')"
    ]
    
    for code in dangerous_codes:
        with pytest.raises(Exception):
            validate_pandas_code(code)


def test_safe_code_allowed(sample_df):
    """Test that safe code executes successfully"""
    safe_codes = [
        "result = df.mean()",
        "result = df.groupby('C')['A'].sum()",
        "result = df['A'].max()"
    ]
    
    for code in safe_codes:
        result = safe_execute_pandas_code(code, sample_df)
        assert result is not None


def test_code_with_error(sample_df):
    """Test that code errors are caught"""
    code = "result = df['NonexistentColumn'].sum()"
    
    with pytest.raises(Exception):
        safe_execute_pandas_code(code, sample_df)


def test_complex_operation(sample_df):
    """Test a complex multi-line operation"""
    code = """
df_filtered = df[df['A'] > 2]
result = df_filtered['B'].mean()
"""
    result = safe_execute_pandas_code(code, sample_df)
    
    assert result['type'] == 'scalar'
    assert result['value'] == 40.0


def test_dictionary_result(sample_df):
    """Test operation that returns a dictionary"""
    code = """
result = {
    'sum_A': df['A'].sum(),
    'mean_B': df['B'].mean()
}
"""
    result = safe_execute_pandas_code(code, sample_df)
    
    assert result['type'] == 'dict'
    assert 'sum_A' in result['data']
    assert 'mean_B' in result['data']
