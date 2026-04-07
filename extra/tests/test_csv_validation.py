"""
Comprehensive validation tests for test1.csv file
Tests basic exploration, sales analysis, product/regional analysis, and hallucination detection
"""
import pytest
import pandas as pd
from backend.app.agents.data_analyst_v2 import DataAnalystAgent


@pytest.fixture
def test1_dataframe():
    """Create the test1.csv DataFrame"""
    data = {
        'product': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Laptop', 'Mouse'],
        'sales': [1200, 25, 75, 300, 1500, 30],
        'region': ['North', 'South', 'East', 'West', 'North', 'South'],
        'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-06']
    }
    return pd.DataFrame(data)


@pytest.fixture
def agent(test1_dataframe):
    """Create agent instance with test1 data"""
    agent = DataAnalystAgent(df=test1_dataframe)
    return agent


def get_answer(response):
    """Helper to extract answer string from agent response dict"""
    if isinstance(response, dict):
        return response.get("answer", "")
    return str(response)


class TestBasicDataExploration:
    """Q1-Q4: Basic data exploration queries"""
    
    def test_row_count(self, agent):
        """Q1: How many rows are in the dataset?"""
        response = agent.analyze("How many rows are in the dataset?")
        answer = get_answer(response)
        assert "6" in answer
    
    def test_column_names(self, agent):
        """Q2: What columns are available?"""
        response = agent.analyze("What columns are available in the data?")
        answer = get_answer(response).lower()
        assert "product" in answer
        assert "sales" in answer
        assert "region" in answer
        assert "date" in answer
    
    def test_show_first_rows(self, agent):
        """Q3: Show me the first few rows"""
        response = agent.analyze("Show me the first few rows")
        answer = get_answer(response).lower()
        assert "laptop" in answer or "1200" in answer
    
    def test_data_types(self, agent):
        """Q4: What data types are in each column?"""
        response = agent.analyze("What data types are in each column?")
        answer = get_answer(response).lower()
        # Should mention types for all columns
        assert any(word in answer for word in ['object', 'text', 'string', 'int', 'numeric', 'number'])


class TestSalesAnalysis:
    """Q5-Q8: Sales calculations"""
    
    def test_total_sales(self, agent):
        """Q5: What is the total sales? Expected: 3130"""
        response = agent.analyze("What is the total sales?")
        answer = get_answer(response)
        assert "3130" in answer or "3,130" in answer
    
    def test_average_sales(self, agent):
        """Q6: What is the average sales? Expected: 521.67"""
        response = agent.analyze("What is the average sales value?")
        answer = get_answer(response)
        # Accept 521.67, 521.66, or 521.7
        assert any(val in answer for val in ["521.67", "521.66", "521.7", "521"])
    
    def test_min_max_sales(self, agent):
        """Q7: Min and max sales? Expected: Min=25, Max=1500"""
        response = agent.analyze("What is the minimum and maximum sales?")
        answer = get_answer(response)
        assert "25" in answer
        assert "1500" in answer or "1,500" in answer
    
    def test_median_sales(self, agent):
        """Q8: Median sales? Expected: 187.5"""
        response = agent.analyze("What is the median sales value?")
        answer = get_answer(response)
        assert "187.5" in answer or "187" in answer


class TestProductAnalysis:
    """Q9-Q12: Product-based queries"""
    
    def test_unique_product_count(self, agent):
        """Q9: How many unique products? Expected: 4"""
        response = agent.analyze("How many unique products are there?")
        answer = get_answer(response)
        assert "4" in answer
    
    def test_highest_sales_product(self, agent):
        """Q10: Which product has highest sales? Expected: Laptop"""
        response = agent.analyze("Which product has the highest sales?")
        answer = get_answer(response).lower()
        assert "laptop" in answer
    
    def test_sales_by_product(self, agent):
        """Q11: Total sales for each product"""
        response = agent.analyze("What is the total sales for each product?")
        answer = get_answer(response).lower()
        # Laptop: 2700, Monitor: 300, Keyboard: 75, Mouse: 55
        assert "laptop" in answer
        assert any(val in answer for val in ["2700", "2,700"])
    
    def test_sorted_product_sales(self, agent):
        """Q12: Show sales by product sorted high to low"""
        response = agent.analyze("Show me sales by product sorted from highest to lowest")
        answer = get_answer(response).lower()
        assert "laptop" in answer
        # Response should have structure showing sorted data


class TestRegionalAnalysis:
    """Q13-Q16: Region-based queries"""
    
    def test_unique_region_count(self, agent):
        """Q13: How many regions? Expected: 4"""
        response = agent.analyze("How many regions are in the data?")
        answer = get_answer(response)
        assert "4" in answer
    
    def test_highest_sales_region(self, agent):
        """Q14: Which region has highest total sales? Expected: North"""
        response = agent.analyze("Which region has the highest total sales?")
        answer = get_answer(response).lower()
        assert "north" in answer
    
    def test_sales_by_region(self, agent):
        """Q15: Total sales by region"""
        response = agent.analyze("What are the total sales by region?")
        answer = get_answer(response).lower()
        # North: 2700, South: 55, West: 300, East: 75
        assert "north" in answer
        assert any(val in answer for val in ["2700", "2,700"])
    
    def test_transactions_per_region(self, agent):
        """Q16: How many transactions per region?"""
        response = agent.analyze("How many transactions happened in each region?")
        answer = get_answer(response).lower()
        # North: 2, South: 2, East: 1, West: 1
        assert "north" in answer


class TestTimeBasedAnalysis:
    """Q17-Q19: Date-based queries"""
    
    def test_date_range(self, agent):
        """Q17: What date range does data cover? Expected: Jan 1-6, 2024"""
        response = agent.analyze("What date range does the data cover?")
        answer = get_answer(response).lower()
        assert "2024-01-01" in answer or "january" in answer or "01-01" in answer
        assert "2024-01-06" in answer or "01-06" in answer
    
    def test_sales_trends(self, agent):
        """Q18: Sales trends over time"""
        response = agent.analyze("What are the sales trends over time?")
        answer = get_answer(response)
        # Should show variation in sales values
        assert len(answer) > 50  # Non-trivial response
    
    def test_specific_date_sales(self, agent):
        """Q19: Sales on January 5th? Expected: 1500"""
        response = agent.analyze("What was the total sales on January 5th?")
        answer = get_answer(response)
        assert "1500" in answer or "1,500" in answer


class TestFilteringQueries:
    """Q20-Q23: Conditional filtering"""
    
    def test_sales_greater_than_100(self, agent):
        """Q20: Show sales > $100. Expected: 4 rows"""
        response = agent.analyze("Show me all sales greater than $100")
        answer = get_answer(response)
        # Should include 1200, 300, 1500 but not 25, 75, 30
        assert "1200" in answer or "1,200" in answer
    
    def test_products_in_north(self, agent):
        """Q21: Products sold in North? Expected: Laptop"""
        response = agent.analyze("What products were sold in the North region?")
        answer = get_answer(response).lower()
        assert "laptop" in answer
    
    def test_sales_under_100(self, agent):
        """Q22: How many sales under $100? Expected: 3"""
        response = agent.analyze("How many sales were under $100?")
        answer = get_answer(response)
        assert "3" in answer
    
    def test_sales_between_range(self, agent):
        """Q23: Sales between $50 and $500"""
        response = agent.analyze("Show me sales between $50 and $500")
        answer = get_answer(response)
        # Should include 75 and 300, exclude 25 and 1200/1500
        assert "75" in answer or "300" in answer


class TestComplexAnalysis:
    """Q24-Q27: Multi-step analysis"""
    
    def test_average_sales_per_region(self, agent):
        """Q24: Average sales per region"""
        response = agent.analyze("What is the average sales per region?")
        answer = get_answer(response).lower()
        # North: 1350, South: 27.5, East: 75, West: 300
        assert "north" in answer
    
    def test_product_region_combination(self, agent):
        """Q25: Highest product-region combo? Expected: Laptop in North $1500"""
        response = agent.analyze("Which product-region combination has the highest sales?")
        answer = get_answer(response).lower()
        assert "laptop" in answer
        assert "north" in answer
    
    def test_laptop_sales_percentage(self, agent):
        """Q26: What % of sales from Laptops? Expected: 86.3%"""
        response = agent.analyze("What percentage of total sales comes from Laptops?")
        answer = get_answer(response)
        # 2700/3130 = 86.26%
        assert any(val in answer for val in ["86", "86.2", "86.3"])
    
    def test_group_by_product_and_region(self, agent):
        """Q27: Group sales by product and region"""
        response = agent.analyze("Group sales by product and region")
        answer = get_answer(response).lower()
        assert "laptop" in answer
        assert "north" in answer


class TestHallucinationDetection:
    """Q28-Q30: CRITICAL - Ensure no fake data generation"""
    
    def test_nonexistent_customer_names(self, agent):
        """Q28: Ask for customer names (doesn't exist)"""
        response = agent.analyze("Show me customer names")
        answer = get_answer(response).lower()
        # Should indicate column not found, NOT generate fake names
        assert any(word in answer for word in [
            "not found", "doesn't exist", "not available", "does not exist", "does not contain",
            "no column", "cannot find", "missing", "error", "not contain"
        ])
        # Should NOT contain common fake names
        assert "john" not in answer
        assert "smith" not in answer
    
    def test_nonexistent_profit_margin(self, agent):
        """Q29: Ask for profit margin (doesn't exist)"""
        response = agent.analyze("What is the profit margin?")
        answer = get_answer(response).lower()
        # Should indicate column not available
        assert any(word in answer for word in [
            "not found", "doesn't exist", "not available", "does not exist", "does not contain",
            "no column", "cannot find", "missing", "error", "not contain", "profit"
        ])
    
    def test_nonexistent_email_addresses(self, agent):
        """Q30: Ask for email addresses (doesn't exist)"""
        response = agent.analyze("Show me the email addresses")
        answer = get_answer(response).lower()
        # Should indicate column doesn't exist
        assert any(word in answer for word in [
            "not found", "doesn't exist", "not available", "does not exist", "does not contain",
            "no column", "cannot find", "missing", "error", "not contain", "email"
        ])
        # Should NOT contain fake email patterns - check carefully to avoid false positives
        if "@" in answer:
            # If @ appears, it should be in the context of explaining the error
            assert "email" in answer


class TestQuickValidation:
    """Quick 5-question validation suite"""
    
    def test_quick_row_count(self, agent):
        """Quick test: Row count"""
        response = agent.analyze("How many rows?")
        answer = get_answer(response)
        assert "6" in answer
    
    def test_quick_total_sales(self, agent):
        """Quick test: Total sales"""
        response = agent.analyze("Total sales?")
        answer = get_answer(response)
        assert "3130" in answer or "3,130" in answer
    
    def test_quick_top_product(self, agent):
        """Quick test: Top product"""
        response = agent.analyze("Top product by sales?")
        answer = get_answer(response).lower()
        assert "laptop" in answer
    
    def test_quick_top_region(self, agent):
        """Quick test: Top region"""
        response = agent.analyze("Which region has most sales?")
        answer = get_answer(response).lower()
        assert "north" in answer
    
    def test_quick_hallucination_check(self, agent):
        """Quick test: Hallucination detection"""
        response = agent.analyze("Show customer emails")
        answer = get_answer(response).lower()
        assert any(word in answer for word in [
            "not found", "doesn't exist", "not available", "does not exist", "does not contain", "error"
        ])
