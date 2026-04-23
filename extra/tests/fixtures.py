"""
Test fixtures and sample data for testing
"""
import pytest
import pandas as pd
import io


@pytest.fixture
def sample_sales_csv():
    """Sample sales CSV content"""
    return """product,sales,region,date
Laptop,1200,North,2024-01-01
Mouse,25,South,2024-01-02
Keyboard,75,East,2024-01-03
Monitor,300,West,2024-01-04
Laptop,1500,North,2024-01-05
Mouse,30,South,2024-01-06"""


@pytest.fixture
def sample_sales_dataframe():
    """Sample sales DataFrame"""
    data = {
        'product': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Laptop', 'Mouse'],
        'sales': [1200, 25, 75, 300, 1500, 30],
        'region': ['North', 'South', 'East', 'West', 'North', 'South'],
        'date': pd.date_range('2024-01-01', periods=6)
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_employee_dataframe():
    """Sample employee DataFrame"""
    data = {
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'age': [28, 35, 42, 25, 31],
        'department': ['IT', 'Sales', 'IT', 'HR', 'Sales'],
        'salary': [70000, 65000, 85000, 55000, 72000]
    }
    return pd.DataFrame(data)


@pytest.fixture
def conversation_history():
    """Sample conversation history"""
    return [
        {"role": "user", "content": "What is the total sales?"},
        {"role": "assistant", "content": "The total sales are $3,130"},
        {"role": "user", "content": "Which product sold the most?"},
        {"role": "assistant", "content": "Laptop sold the most with total sales of $2,700"}
    ]


@pytest.fixture
def csv_file_bytes(sample_sales_csv):
    """CSV file as bytes for upload testing"""
    return io.BytesIO(sample_sales_csv.encode())


@pytest.fixture
def invalid_csv_file():
    """Invalid CSV file (missing data)"""
    return io.BytesIO(b"header1,header2\nvalue1")


@pytest.fixture
def large_dataframe():
    """Large DataFrame for performance testing"""
    import numpy as np
    
    n_rows = 10000
    data = {
        'id': range(n_rows),
        'value': np.random.randn(n_rows),
        'category': np.random.choice(['A', 'B', 'C', 'D'], n_rows),
        'date': pd.date_range('2020-01-01', periods=n_rows, freq='H')
    }
    return pd.DataFrame(data)
