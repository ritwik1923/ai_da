import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, Optional, Set, List
import json
import re


_CHART_INTENT_WORDS: Set[str] = {
    "chart", "plot", "graph", "visualize", "visualisation", "show", "create", "make", "draw",
    "trend", "trends", "timeline", "time", "timeseries", "series", "over", "between", "across",
    "compare", "comparison", "vs", "versus", "by", "per", "group", "grouped",
    "distribution", "histogram", "correlation", "relationship", "scatter", "pie", "proportion", "percentage",
    "and", "or", "of", "the", "a", "an", "to", "for", "in", "on", "with", "non",
}


def _tokenize_subject_terms(query_lower: str) -> List[str]:
    # Keep only alphabetic tokens; remove generic chart intent + filler words.
    tokens = re.findall(r"[a-zA-Z]{3,}", query_lower)
    terms = [t for t in tokens if t not in _CHART_INTENT_WORDS]
    # Deduplicate while preserving order
    seen = set()
    unique_terms: List[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique_terms.append(t)
    return unique_terms


def _subject_terms_match_columns(df: pd.DataFrame, query_lower: str) -> bool:
    """Return True if query seems to reference any existing columns.

    This prevents misleading fallback charts when user asks for non-existent fields
    (e.g., "region/subscription/holiday" but dataset doesn't have those columns).
    """
    subject_terms = _tokenize_subject_terms(query_lower)
    if not subject_terms:
        # Query is generic like "show a chart"; allow fallback.
        return True

    columns_lower = [str(c).lower() for c in df.columns]
    return any(any(term in col for col in columns_lower) for term in subject_terms)


def _create_chart_from_code(df: pd.DataFrame, code: str, query: str) -> Optional[Dict[str, Any]]:
    """
    Execute the code and create a chart from the result.
    
    Args:
        df: Original DataFrame
        code: Python code that was executed (e.g., "result = df.groupby('Region')['Sales'].count().to_dict()")
        query: User query for chart title
        
    Returns:
        Chart configuration or None
    """
    try:
        # Execute the code to get the result
        local_vars = {"df": df, "pd": pd}
        exec(code, {"pd": pd, "df": df}, local_vars)
        
        if "result" not in local_vars:
            return None
            
        result = local_vars["result"]
        
        # Convert result to DataFrame if it's a dict or Series
        if isinstance(result, dict):
            result_df = pd.DataFrame(list(result.items()), columns=['Category', 'Value'])
        elif isinstance(result, pd.Series):
            result_df = result.reset_index()
            result_df.columns = ['Category', 'Value']
        elif isinstance(result, pd.DataFrame):
            result_df = result
            # If it has 2 columns, use them as Category and Value
            if len(result_df.columns) == 2:
                result_df.columns = ['Category', 'Value']
        else:
            return None
        
        # Limit to top 20 for readability
        if len(result_df) > 20:
            result_df = result_df.nlargest(20, 'Value') if 'Value' in result_df.columns else result_df.head(20)
        
        # Determine chart type from query
        query_lower = query.lower()
        if any(word in query_lower for word in ['pie', 'proportion', 'percentage']):
            fig = px.pie(result_df, names='Category', values='Value', title=query.capitalize())
        elif any(word in query_lower for word in ['line', 'trend', 'over time']):
            fig = px.line(result_df, x='Category', y='Value', title=query.capitalize())
        else:
            # Default: bar chart
            fig = px.bar(result_df, x='Category', y='Value', title=query.capitalize())
        
        return {
            'type': 'bar' if 'bar' in query_lower else 'pie' if 'pie' in query_lower else 'line' if 'line' in query_lower else 'bar',
            'data': json.loads(fig.to_json())
        }
        
    except Exception as e:
        print(f"[chart_generator] Error creating chart from code: {e}")
        return None


def generate_chart(df: pd.DataFrame, query: str, code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Generate chart configuration based on query and data
    
    Args:
        df: DataFrame to visualize
        query: Natural language query
        code: Optional generated code that was executed
        
    Returns:
        Chart configuration in Plotly format, or None if unsuitable
    """
    
    if df is None or getattr(df, "empty", False):
        print("[chart_generator] DataFrame is None or empty")
        return None

    query_lower = query.lower()

    # If the query clearly references concepts that don't exist in the dataset,
    # don't fabricate a chart from unrelated columns.
    if not _subject_terms_match_columns(df, query_lower):
        print(f"[chart_generator] Query terms don't match dataset columns. Skipping chart.")
        return None
    
    # If code was executed, try to extract the aggregation result
    chart_from_code = None
    if code:
        chart_from_code = _create_chart_from_code(df, code, query)
        if chart_from_code:
            return chart_from_code
    
    # Fallback: Determine chart type based on query keywords
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


def create_line_chart(df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    """Create a line chart"""
    
    # Try to identify time column and value column
    date_columns = df.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()

    # Heuristic: look for likely date columns by name and parseability
    if not date_columns:
        name_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ["date", "time", "day", "month", "year"])]
        for c in name_candidates:
            try:
                parsed = pd.to_datetime(df[c].head(50), errors='coerce')
                if parsed.notna().any():
                    date_columns.append(c)
                    break
            except Exception:
                continue

    if not date_columns or not numeric_columns:
        return None

    x_col = date_columns[0]
    y_col = numeric_columns[0]
    
    fig = px.line(
        df.head(200),  # Limit points for performance
        x=x_col,
        y=y_col,
        title=f"{y_col} over {x_col}"
    )
    
    return {
        'type': 'line',
        'data': json.loads(fig.to_json())
    }


def create_bar_chart(df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    """Create a bar chart"""
    
    # Identify categorical and numeric columns
    categorical_columns = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()

    if not categorical_columns or not numeric_columns:
        return None
    
    x_col = categorical_columns[0]
    y_col = numeric_columns[0]
    
    # Aggregate data
    grouped = df.groupby(x_col, dropna=False)[y_col].sum().reset_index()
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
    
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    
    if not numeric_columns:
        return None
    
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
    
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    
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
    
    categorical_columns = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()

    if not categorical_columns or not numeric_columns:
        return None
    
    names_col = categorical_columns[0]
    values_col = numeric_columns[0]
    
    # Aggregate and get top categories
    grouped = df.groupby(names_col, dropna=False)[values_col].sum().reset_index()
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
