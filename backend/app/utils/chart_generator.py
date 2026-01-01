import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, Optional
import json


def generate_chart(df: pd.DataFrame, query: str, code: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate chart configuration based on query and data
    
    Args:
        df: DataFrame to visualize
        query: Natural language query
        code: Optional generated code
        
    Returns:
        Chart configuration in Plotly format
    """
    
    query_lower = query.lower()
    
    # Determine chart type based on query
    if any(word in query_lower for word in ['trend', 'over time', 'timeline', 'time series']):
        return create_line_chart(df, query)
    elif any(word in query_lower for word in ['distribution', 'histogram']):
        return create_histogram(df, query)
    elif any(word in query_lower for word in ['compare', 'comparison', 'vs', 'versus']):
        return create_bar_chart(df, query)
    elif any(word in query_lower for word in ['correlation', 'relationship']):
        return create_scatter_plot(df, query)
    elif any(word in query_lower for word in ['pie', 'proportion', 'percentage']):
        return create_pie_chart(df, query)
    else:
        # Default to bar chart
        return create_bar_chart(df, query)


def create_line_chart(df: pd.DataFrame, query: str) -> Dict[str, Any]:
    """Create a line chart"""
    
    # Try to identify time column and value column
    date_columns = df.select_dtypes(include=['datetime64']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if not date_columns:
        # Try to convert first column to datetime
        date_columns = [df.columns[0]]
    
    if not numeric_columns:
        numeric_columns = [df.columns[1]] if len(df.columns) > 1 else [df.columns[0]]
    
    x_col = date_columns[0]
    y_col = numeric_columns[0]
    
    fig = px.line(
        df.head(100),  # Limit to 100 points for performance
        x=x_col,
        y=y_col,
        title=f"{y_col} over {x_col}"
    )
    
    return {
        'type': 'line',
        'data': json.loads(fig.to_json())
    }


def create_bar_chart(df: pd.DataFrame, query: str) -> Dict[str, Any]:
    """Create a bar chart"""
    
    # Identify categorical and numeric columns
    categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if not categorical_columns:
        categorical_columns = [df.columns[0]]
    if not numeric_columns:
        numeric_columns = [df.columns[1]] if len(df.columns) > 1 else [df.columns[0]]
    
    x_col = categorical_columns[0]
    y_col = numeric_columns[0]
    
    # Aggregate data if needed
    grouped = df.groupby(x_col)[y_col].sum().reset_index()
    grouped = grouped.nlargest(10, y_col)  # Top 10
    
    fig = px.bar(
        grouped,
        x=x_col,
        y=y_col,
        title=f"{y_col} by {x_col}"
    )
    
    return {
        'type': 'bar',
        'data': json.loads(fig.to_json())
    }


def create_histogram(df: pd.DataFrame, query: str) -> Dict[str, Any]:
    """Create a histogram"""
    
    numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if not numeric_columns:
        numeric_columns = [df.columns[0]]
    
    col = numeric_columns[0]
    
    fig = px.histogram(
        df,
        x=col,
        title=f"Distribution of {col}",
        nbins=30
    )
    
    return {
        'type': 'histogram',
        'data': json.loads(fig.to_json())
    }


def create_scatter_plot(df: pd.DataFrame, query: str) -> Dict[str, Any]:
    """Create a scatter plot"""
    
    numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if len(numeric_columns) < 2:
        return create_bar_chart(df, query)
    
    x_col = numeric_columns[0]
    y_col = numeric_columns[1]
    
    fig = px.scatter(
        df.head(100),
        x=x_col,
        y=y_col,
        title=f"{y_col} vs {x_col}"
    )
    
    return {
        'type': 'scatter',
        'data': json.loads(fig.to_json())
    }


def create_pie_chart(df: pd.DataFrame, query: str) -> Dict[str, Any]:
    """Create a pie chart"""
    
    categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if not categorical_columns:
        categorical_columns = [df.columns[0]]
    if not numeric_columns:
        numeric_columns = [df.columns[1]] if len(df.columns) > 1 else [df.columns[0]]
    
    names_col = categorical_columns[0]
    values_col = numeric_columns[0]
    
    # Aggregate and get top categories
    grouped = df.groupby(names_col)[values_col].sum().reset_index()
    grouped = grouped.nlargest(10, values_col)
    
    fig = px.pie(
        grouped,
        names=names_col,
        values=values_col,
        title=f"{values_col} by {names_col}"
    )
    
    return {
        'type': 'pie',
        'data': json.loads(fig.to_json())
    }
