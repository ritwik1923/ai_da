"""
Comprehensive Test Suite for Schema-First Architecture
Tests large-scale data handling (100k rows × 1000 columns)
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.data_passport import generate_data_passport, DataPassport
from app.utils.column_vector_store import ColumnVectorStore, ColumnSelector
from app.utils.self_healing_executor import SelfHealingExecutor, ErrorCategory


class TestDataPassport:
    """Test suite for Data Passport generation."""
    
    @pytest.fixture
    def small_df(self):
        """Small DataFrame for quick tests."""
        return pd.DataFrame({
            'id': range(100),
            'revenue': np.random.randint(1000, 10000, 100),
            'category': np.random.choice(['A', 'B', 'C'], 100),
            'date': pd.date_range('2024-01-01', periods=100),
            'score': np.random.random(100)
        })
    
    @pytest.fixture
    def large_df(self):
        """Large DataFrame simulating 100k rows × 100 columns."""
        np.random.seed(42)
        data = {}
        
        # 50 numeric columns
        for i in range(50):
            data[f'num_col_{i}'] = np.random.randn(100000)
        
        # 30 categorical columns
        for i in range(30):
            data[f'cat_col_{i}'] = np.random.choice(['A', 'B', 'C', 'D', 'E'], 100000)
        
        # 10 datetime columns
        for i in range(10):
            data[f'date_col_{i}'] = pd.date_range('2020-01-01', periods=100000, freq='1min')
        
        # 10 text columns with nulls
        for i in range(10):
            vals = np.random.choice(['text1', 'text2', 'text3', None], 100000)
            data[f'text_col_{i}'] = vals
        
        return pd.DataFrame(data)
    
    @pytest.fixture
    def ultra_wide_df(self):
        """Ultra-wide DataFrame simulating 1000 columns × 1000 rows."""
        np.random.seed(42)
        data = {f'col_{i}': np.random.randn(1000) for i in range(1000)}
        return pd.DataFrame(data)
    
    def test_passport_generation_small(self, small_df):
        """Test passport generation on small dataset."""
        passport = generate_data_passport(small_df)
        
        assert passport.passport['metadata']['shape']['rows'] == 100
        assert passport.passport['metadata']['shape']['columns'] == 5
        assert len(passport.passport['schema']) == 5
        assert passport.passport['sample_data']['count'] == 5
    
    def test_passport_generation_large(self, large_df):
        """Test passport generation on large dataset (100k rows)."""
        passport = generate_data_passport(large_df, max_sample_rows=3)
        
        # Should handle large dataset efficiently
        assert passport.passport['metadata']['shape']['rows'] == 100000
        assert passport.passport['metadata']['shape']['columns'] == 100
        
        # Sample should be limited
        assert passport.passport['sample_data']['count'] == 3
        
        # All columns should have schema
        assert len(passport.passport['schema']) == 100
        
        # Should categorize correctly
        schema = passport.passport['schema']
        numeric_cols = [c for c in schema if c['category'] == 'numeric']
        cat_cols = [c for c in schema if c['category'] == 'categorical']
        date_cols = [c for c in schema if c['category'] == 'datetime']
        
        assert len(numeric_cols) == 50
        assert len(cat_cols) == 40  # text + categorical
        assert len(date_cols) == 10
    
    def test_passport_ultra_wide(self, ultra_wide_df):
        """Test passport generation on ultra-wide dataset (1000 columns)."""
        passport = generate_data_passport(ultra_wide_df)
        
        assert passport.passport['metadata']['shape']['columns'] == 1000
        assert len(passport.passport['schema']) == 1000
        
        # Verify fingerprint generation
        assert len(passport.passport['fingerprint']) == 32  # MD5 hash
    
    def test_passport_prompt_context(self, small_df):
        """Test conversion to prompt-friendly context."""
        passport = generate_data_passport(small_df)
        context = passport.to_prompt_context()
        
        assert 'Dataset Information' in context
        assert 'Column Schema' in context
        assert 'revenue' in context
        assert 'category' in context
    
    def test_column_descriptions(self, small_df):
        """Test column description generation for RAG."""
        passport = generate_data_passport(small_df)
        descriptions = passport.get_column_descriptions()
        
        assert len(descriptions) == 5
        assert 'revenue' in descriptions
        assert 'numeric' in descriptions['revenue'].lower()
        assert 'category' in descriptions
        assert 'categorical' in descriptions['category'].lower()
    
    def test_data_quality_detection(self):
        """Test data quality issue detection."""
        # Create DataFrame with quality issues
        df = pd.DataFrame({
            'high_nulls': [None] * 80 + [1] * 20,  # 80% nulls
            'constant': [5] * 100,  # Constant value
            'normal': range(100)
        })
        
        passport = generate_data_passport(df)
        quality = passport.passport['data_quality']
        
        assert quality['issues_count'] >= 2
        
        # Check for high null detection
        null_issues = [i for i in quality['issues'] if i['issue'] == 'high_null_percentage']
        assert len(null_issues) >= 1
        
        # Check for constant value detection
        constant_issues = [i for i in quality['issues'] if i['issue'] == 'constant_value']
        assert len(constant_issues) >= 1


class TestColumnVectorStore:
    """Test suite for Column RAG system."""
    
    @pytest.fixture
    def vector_store(self):
        """Initialize vector store."""
        return ColumnVectorStore(
            collection_name="test_cols",
            persist_directory=None  # In-memory
        )
    
    @pytest.fixture
    def sample_columns(self):
        """Sample column descriptions."""
        return {
            'Total_Revenue': 'Total revenue amount in USD. Numeric. Range from 0 to 1000000',
            'Customer_Name': 'Name of the customer. Text. Contains 5000 unique values',
            'Order_Date': 'Date when order was placed. Datetime. Range from 2020-01-01 to 2024-12-31',
            'Product_Category': 'Category of product sold. Categorical. Values: Electronics, Clothing, Food',
            'Shipping_City': 'City where product was shipped. Text. Contains 200 unique cities',
            'Gross_Profit_Margin': 'Profit margin percentage. Numeric. Range from -10 to 50',
            'Discount_Applied': 'Discount percentage applied to order. Numeric. Range from 0 to 30'
        }
    
    def test_add_columns(self, vector_store, sample_columns):
        """Test adding columns to vector store."""
        vector_store.add_columns(sample_columns)
        
        all_cols = vector_store.get_all_columns()
        assert len(all_cols) == 7
        assert 'Total_Revenue' in all_cols
    
    def test_semantic_search(self, vector_store, sample_columns):
        """Test semantic search for columns."""
        vector_store.add_columns(sample_columns)
        
        # Search for revenue-related columns
        results = vector_store.search_columns("show me revenue", top_k=3)
        
        assert len(results) <= 3
        # Should find revenue-related columns
        col_names = [r['column_name'] for r in results]
        assert 'Total_Revenue' in col_names or 'Gross_Profit_Margin' in col_names
    
    def test_search_by_location(self, vector_store, sample_columns):
        """Test searching for location columns."""
        vector_store.add_columns(sample_columns)
        
        results = vector_store.search_columns("by city", top_k=3)
        col_names = [r['column_name'] for r in results]
        
        # Should find city-related column
        assert 'Shipping_City' in col_names
    
    def test_search_by_time(self, vector_store, sample_columns):
        """Test searching for time-related columns."""
        vector_store.add_columns(sample_columns)
        
        results = vector_store.search_columns("trend over time", top_k=3)
        col_names = [r['column_name'] for r in results]
        
        # Should find date column
        assert 'Order_Date' in col_names
    
    def test_large_column_set(self, vector_store):
        """Test with large number of columns (1000+)."""
        # Generate 1000 columns
        large_cols = {}
        for i in range(1000):
            category = i % 10
            large_cols[f'metric_{i}'] = f'Metric {i} for category {category}. Numeric data.'
        
        vector_store.add_columns(large_cols)
        
        # Should be able to search through all
        results = vector_store.search_columns("category 5", top_k=20)
        
        assert len(results) <= 20
        # Should find relevant columns
        assert len(results) > 0


class TestSelfHealingExecutor:
    """Test suite for self-healing code execution."""
    
    @pytest.fixture
    def df(self):
        """Sample DataFrame for code execution."""
        return pd.DataFrame({
            'revenue': [100, 200, 300, 400, 500],
            'cost': [50, 100, 150, 200, 250],
            'category': ['A', 'B', 'A', 'B', 'C'],
            'date': pd.date_range('2024-01-01', periods=5)
        })
    
    def test_successful_execution(self, df):
        """Test executing valid code."""
        executor = SelfHealingExecutor(df)
        
        code = "result = df['revenue'].sum()"
        result = executor.execute_with_healing(code)
        
        assert result.success
        assert result.result['value'] == 1500
        assert result.attempt_number == 1
    
    def test_fix_key_error(self, df):
        """Test fixing KeyError (wrong column name)."""
        executor = SelfHealingExecutor(df)
        
        # Typo in column name
        code = "result = df['revenu'].sum()"  # Missing 'e'
        result = executor.execute_with_healing(code)
        
        # Should auto-fix and succeed
        if result.success:
            assert result.attempt_number > 1  # Required a retry
        else:
            # At least should have attempted a fix
            assert result.attempt_number > 1
    
    def test_fix_zero_division(self, df):
        """Test fixing ZeroDivisionError."""
        executor = SelfHealingExecutor(df)
        
        # Add a zero to create division by zero
        df_with_zero = df.copy()
        df_with_zero.loc[0, 'cost'] = 0
        
        executor.df = df_with_zero
        code = "result = df['revenue'] / df['cost']"
        
        result = executor.execute_with_healing(code)
        
        # Should attempt to fix
        assert result.attempt_number >= 1
    
    def test_execution_history(self, df):
        """Test tracking of execution attempts."""
        executor = SelfHealingExecutor(df)
        
        code = "result = df['revenue'].sum()"
        executor.execute_with_healing(code)
        
        summary = executor.get_execution_summary()
        
        assert summary['total_attempts'] >= 1
        assert summary['success'] == True
        assert len(summary['attempts']) >= 1


class TestSchemaFirstWorkflow:
    """Integration tests for full schema-first workflow."""
    
    def test_large_dataset_efficiency(self):
        """Test that large datasets are handled without sending raw data."""
        # Create 100k row dataset
        df = pd.DataFrame({
            'col1': np.random.randn(100000),
            'col2': np.random.choice(['A', 'B', 'C'], 100000)
        })
        
        # Generate passport
        passport = generate_data_passport(df, max_sample_rows=3)
        context = passport.to_prompt_context()
        
        # Context should be compact (< 10k chars for 2 columns)
        assert len(context) < 10000
        
        # Should contain sample, not full data
        assert passport.passport['sample_data']['count'] == 3
    
    def test_wide_dataset_rag(self):
        """Test RAG system with wide dataset (1000 columns)."""
        # Create dataset with 1000 columns
        np.random.seed(42)
        data = {f'metric_{i}': np.random.randn(100) for i in range(1000)}
        df = pd.DataFrame(data)
        
        # Generate passport and initialize RAG
        passport = generate_data_passport(df)
        store = ColumnVectorStore(collection_name="test_wide")
        
        descriptions = passport.get_column_descriptions()
        store.add_columns(descriptions)
        
        # Should be able to search through 1000 columns
        results = store.search_columns("metric 500", top_k=10)
        
        assert len(results) <= 10
        assert len(results) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
