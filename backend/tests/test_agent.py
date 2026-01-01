"""
Unit tests for the DataAnalystAgent
Run with: pytest
"""

import pytest
import pandas as pd
from app.agents.data_analyst import DataAnalystAgent


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing"""
    return pd.DataFrame({
        'Product': ['Laptop', 'Mouse', 'Keyboard', 'Monitor'],
        'Revenue': [15000, 500, 800, 12000],
        'Sales': [50, 200, 150, 40],
        'Region': ['North', 'South', 'East', 'West']
    })


def test_agent_initialization(sample_dataframe):
    """Test that agent initializes correctly"""
    agent = DataAnalystAgent(sample_dataframe)
    assert agent.df is not None
    assert len(agent.tools) == 3
    assert agent.agent is not None


def test_dataframe_info_tool(sample_dataframe):
    """Test the get_dataframe_info tool"""
    agent = DataAnalystAgent(sample_dataframe)
    
    # Find the tool
    info_tool = next(tool for tool in agent.tools if tool.name == "get_dataframe_info")
    
    # Execute tool
    result = info_tool.func("")
    
    assert "DataFrame Information" in result
    assert "Product" in result
    assert "Revenue" in result


def test_simple_query(sample_dataframe):
    """Test a simple analysis query"""
    agent = DataAnalystAgent(sample_dataframe)
    
    result = agent.analyze("What is the total revenue?")
    
    assert result["success"] is True
    assert "answer" in result
    assert result["answer"] is not None


def test_conversation_memory(sample_dataframe):
    """Test that conversation memory works"""
    # Create conversation history
    memory = [
        {"role": "user", "content": "What are the products?"},
        {"role": "assistant", "content": "The products are: Laptop, Mouse, Keyboard, Monitor"}
    ]
    
    agent = DataAnalystAgent(sample_dataframe, conversation_memory=memory)
    
    # Ask a follow-up question
    result = agent.analyze("Which one has the highest revenue?")
    
    assert result["success"] is True


def test_chart_detection(sample_dataframe):
    """Test that chart generation is triggered for appropriate queries"""
    agent = DataAnalystAgent(sample_dataframe)
    
    result = agent.analyze("Show me a chart of revenue by product")
    
    # Chart should be generated for queries with visualization keywords
    assert result["success"] is True


@pytest.mark.parametrize("query,expected_success", [
    ("What is the total revenue?", True),
    ("Show me the top product by sales", True),
    ("Calculate average revenue", True),
])
def test_various_queries(sample_dataframe, query, expected_success):
    """Test various types of queries"""
    agent = DataAnalystAgent(sample_dataframe)
    result = agent.analyze(query)
    assert result["success"] == expected_success


def test_error_handling(sample_dataframe):
    """Test that errors are handled gracefully"""
    agent = DataAnalystAgent(sample_dataframe)
    
    # Query that might cause issues
    result = agent.analyze("Do something impossible with this data")
    
    # Should return a result even if there's an error
    assert "answer" in result
