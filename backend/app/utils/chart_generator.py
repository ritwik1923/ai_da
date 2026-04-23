import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, Optional, Set, List
import json
import re
from abc import ABC, abstractmethod
import traceback
from functools import wraps
from pandas.api.types import is_numeric_dtype

# ==========================================
# NUMBER FORMATTING UTILITY (for generated code)
# ==========================================
def format_number_indian(value: int | float, decimals: int = 2) -> str:
    """
    Format numbers using Indian numbering system (Crores, Lakhs, Thousands).
    
    Examples:
        1000000 -> "10.00L" (10 Lakhs)
        10000000 -> "1.00Cr" (1 Crore)
        100000000 -> "10.00Cr" (10 Crores)
    """
    if value is None or pd.isna(value):
        return "0"
    
    abs_val = abs(value)
    if abs_val >= 10000000:  # Crores (1 Crore = 10 Million)
        return f"{value / 10000000:.{decimals}f}Cr"
    elif abs_val >= 100000:  # Lakhs (1 Lakh = 100K)
        return f"{value / 100000:.{decimals}f}L"
    elif abs_val >= 1000:  # Thousands
        return f"{value / 1000:.{decimals}f}K"
    else:
        return f"{value:,.{decimals}f}"


# ==========================================
# 1. UTILITIES & ANALYZERS (SRP)
# ==========================================
class ChartGenerationError(Exception):
    """Exception raised when LLM-generated chart code fails to execute."""


class SafePlotlyExpress:
    """Proxy for plotly.express with go-based fallbacks for pandas/plotly grouping issues."""

    _WRAPPED_METHODS = {"bar", "scatter", "scatter_3d", "line", "histogram", "pie"}

    def __init__(self, plotly_express_module):
        self._px = plotly_express_module

    def __getattr__(self, name: str):
        attr = getattr(self._px, name)
        if name in self._WRAPPED_METHODS and callable(attr):
            return self._wrap_chart(name, attr)
        return attr

    def _wrap_chart(self, chart_type: str, chart_func):
        @wraps(chart_func)
        def safe_chart(*args, **kwargs):
            try:
                return chart_func(*args, **kwargs)
            except KeyError:
                return self._build_fallback(chart_type, *args, **kwargs)

        return safe_chart

    def _build_fallback(self, chart_type: str, *args, **kwargs):
        data_frame = args[0] if args else kwargs.get('data_frame')
        fallback_kwargs = dict(kwargs)
        title = fallback_kwargs.pop('title', None)

        if data_frame is None:
            raise ValueError(f"{chart_type} fallback requires a data_frame argument.")

        if chart_type == 'pie':
            return self._build_pie_fallback(data_frame, title=title, **fallback_kwargs)

        if chart_type == 'histogram':
            return self._build_histogram_fallback(data_frame, title=title, **fallback_kwargs)

        if chart_type == 'bar':
            return self._build_bar_fallback(data_frame, title=title, **fallback_kwargs)

        if chart_type == 'scatter_3d':
            return self._build_xyz_fallback(data_frame, title=title, **fallback_kwargs)

        data_frame = self._with_index_column(data_frame)
        x_col = fallback_kwargs.get('x')
        y_col = fallback_kwargs.get('y')

        if x_col is None and y_col is None:
            raise ValueError(f"{chart_type} fallback requires x and y arguments.")
        if x_col is None:
            x_col = '__fallback_index__'
        if y_col is None:
            y_col = '__fallback_index__'

        return self._build_xy_fallback(
            chart_type,
            data_frame,
            x_col,
            y_col,
            color_col=fallback_kwargs.get('color'),
            title=title,
        )

    def _build_xyz_fallback(
        self,
        data_frame: pd.DataFrame,
        x: Optional[str] = None,
        y: Optional[str] = None,
        z: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[Any] = None,
        title: Optional[str] = None,
        **_: Any,
    ) -> go.Figure:
        if x is None or y is None or z is None:
            raise ValueError("scatter_3d fallback requires x, y, and z arguments.")
        if x not in data_frame.columns or y not in data_frame.columns or z not in data_frame.columns:
            raise ValueError("scatter_3d fallback columns must exist in the DataFrame.")
        if color is not None and color not in data_frame.columns:
            color = None

        marker_size = None
        if isinstance(size, str) and size in data_frame.columns and is_numeric_dtype(data_frame[size]):
            marker_size = data_frame[size]

        fig = go.Figure()
        if color:
            grouped = data_frame.groupby(color, dropna=False, sort=False)
            for group_name, subset in grouped:
                trace_size = marker_size.loc[subset.index] if marker_size is not None else None
                fig.add_trace(
                    go.Scatter3d(
                        x=subset[x],
                        y=subset[y],
                        z=subset[z],
                        mode='markers',
                        name=str(group_name),
                        marker=dict(size=trace_size if trace_size is not None else 5, opacity=0.85),
                    )
                )
        else:
            fig.add_trace(
                go.Scatter3d(
                    x=data_frame[x],
                    y=data_frame[y],
                    z=data_frame[z],
                    mode='markers',
                    name='data',
                    marker=dict(size=marker_size if marker_size is not None else 5, opacity=0.85),
                )
            )

        if title:
            fig.update_layout(title=title)
        fig.update_layout(scene=dict(xaxis_title=x, yaxis_title=y, zaxis_title=z))
        return fig

    def _build_bar_fallback(
        self,
        data_frame: pd.DataFrame,
        x: Optional[str] = None,
        y: Optional[str] = None,
        color: Optional[str] = None,
        title: Optional[str] = None,
        **_: Any,
    ) -> go.Figure:
        if x is not None and x not in data_frame.columns:
            x = None
        if y is not None and y not in data_frame.columns:
            y = None
        if color is not None and color not in data_frame.columns:
            color = None

        if x is None and color is not None:
            x = color

        if x and y and is_numeric_dtype(data_frame[y]):
            if color and color != x:
                grouped = data_frame.groupby([x, color], dropna=False)[y].sum().reset_index()
                figure = go.Figure()
                for group_name, subset in grouped.groupby(color, dropna=False, sort=False):
                    figure.add_trace(go.Bar(x=subset[x], y=subset[y], name=str(group_name)))
                figure.update_layout(barmode='group')
            else:
                grouped = data_frame.groupby(x, dropna=False)[y].sum().reset_index()
                figure = go.Figure(data=[go.Bar(x=grouped[x], y=grouped[y], name=str(y))])

            if title:
                figure.update_layout(title=title)
            figure.update_xaxes(title=x)
            figure.update_yaxes(title=y)
            return figure

        count_source = x or color or y
        if count_source is None:
            fallback_frame = self._with_index_column(data_frame)
            return self._build_xy_fallback('bar', fallback_frame, '__fallback_index__', '__fallback_index__', title=title)

        grouped = data_frame.groupby(count_source, dropna=False).size().reset_index(name='Count')
        figure = go.Figure(data=[go.Bar(x=grouped[count_source], y=grouped['Count'], name='Count')])
        if title:
            figure.update_layout(title=title)
        figure.update_xaxes(title=count_source)
        figure.update_yaxes(title='Count')
        return figure

    def _with_index_column(self, data_frame: pd.DataFrame) -> pd.DataFrame:
        if '__fallback_index__' in data_frame.columns:
            return data_frame
        frame = data_frame.copy()
        frame['__fallback_index__'] = frame.index
        return frame

    def _build_xy_fallback(
        self,
        chart_type: str,
        data_frame: pd.DataFrame,
        x_col: str,
        y_col: str,
        color_col: Optional[str] = None,
        title: Optional[str] = None,
    ) -> go.Figure:
        if x_col not in data_frame.columns or y_col not in data_frame.columns:
            raise ValueError(f"{chart_type} fallback columns must exist in the DataFrame.")

        fig = go.Figure()

        if color_col and color_col in data_frame.columns:
            grouped = data_frame.groupby(color_col, dropna=False, sort=False)
            for group_name, subset in grouped:
                fig.add_trace(self._build_xy_trace(chart_type, subset, x_col, y_col, str(group_name)))
        else:
            fig.add_trace(self._build_xy_trace(chart_type, data_frame, x_col, y_col, 'data'))

        if title:
            fig.update_layout(title=title)
        if chart_type == 'bar' and color_col and color_col in data_frame.columns:
            fig.update_layout(barmode='group')
        fig.update_xaxes(title=x_col)
        fig.update_yaxes(title=y_col)
        return fig

    def _build_xy_trace(
        self,
        chart_type: str,
        data_frame: pd.DataFrame,
        x_col: str,
        y_col: str,
        name: str,
    ) -> Any:
        if chart_type == 'bar':
            return go.Bar(x=data_frame[x_col], y=data_frame[y_col], name=name)
        if chart_type == 'line':
            return go.Scatter(x=data_frame[x_col], y=data_frame[y_col], mode='lines', name=name)
        return go.Scatter(x=data_frame[x_col], y=data_frame[y_col], mode='markers', name=name)

    def _build_histogram_fallback(
        self,
        data_frame: pd.DataFrame,
        x: Optional[str] = None,
        color: Optional[str] = None,
        title: Optional[str] = None,
        **_: Any,
    ) -> go.Figure:
        if x is None or x not in data_frame.columns:
            raise ValueError("Histogram fallback requires a valid x column.")

        fig = go.Figure()
        if color and color in data_frame.columns:
            grouped = data_frame.groupby(color, dropna=False, sort=False)
            for group_name, subset in grouped:
                fig.add_trace(go.Histogram(x=subset[x], name=str(group_name), opacity=0.75))
            fig.update_layout(barmode='overlay')
        else:
            fig.add_trace(go.Histogram(x=data_frame[x], name=x))

        if title:
            fig.update_layout(title=title)
        fig.update_xaxes(title=x)
        fig.update_yaxes(title='Count')
        return fig

    def _build_pie_fallback(
        self,
        data_frame: pd.DataFrame,
        names: Optional[str] = None,
        values: Optional[str] = None,
        title: Optional[str] = None,
        **_: Any,
    ) -> go.Figure:
        if names is None or values is None:
            raise ValueError("Pie fallback requires names and values arguments.")
        if names not in data_frame.columns or values not in data_frame.columns:
            raise ValueError("Pie fallback columns must exist in the DataFrame.")

        fig = go.Figure(data=[go.Pie(labels=data_frame[names], values=data_frame[values])])
        if title:
            fig.update_layout(title=title)
        return fig


def _to_numeric_for_corr(series: pd.Series) -> pd.Series:
    """Prefer native numeric conversion; fallback to stable category codes."""
    numeric = pd.to_numeric(series, errors='coerce')
    if numeric.notna().sum() >= 2:
        return numeric

    out = pd.Series(float('nan'), index=series.index, dtype='float64')
    non_null = series.notna()
    if non_null.any():
        codes = pd.factorize(series[non_null], sort=False)[0]
        out.loc[non_null] = pd.Series(codes, index=series[non_null].index, dtype='float64')
    return out


def _safe_corr(df: pd.DataFrame, left_col: str, right_col: str) -> float:
    """Compute correlation safely even when columns are categorical strings."""
    if left_col not in df.columns or right_col not in df.columns:
        raise KeyError(f"Columns not found for correlation: {left_col}, {right_col}")

    left = _to_numeric_for_corr(df[left_col])
    right = _to_numeric_for_corr(df[right_col])
    valid = left.notna() & right.notna()
    if valid.sum() < 2:
        return float('nan')
    return float(left[valid].corr(right[valid]))


SAFE_PX = SafePlotlyExpress(px)


def _humanize_label(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).replace("_", " ").strip().title()


def _style_figure(
    fig: go.Figure,
    chart_type: str,
    title: Optional[str] = None,
    x_title: Optional[str] = None,
    y_title: Optional[str] = None,
) -> go.Figure:
    if title:
        fig.update_layout(title=title)

    fig.update_layout(
        template='plotly_white',
        hovermode='closest',
        legend_title_text='',
        margin=dict(l=40, r=40, t=70, b=40),
    )

    if x_title:
        fig.update_xaxes(title=_humanize_label(x_title))
    if y_title:
        fig.update_yaxes(title=_humanize_label(y_title))

    if chart_type == 'bar':
        fig.update_xaxes(tickangle=-30)

    if chart_type == 'scatter':
        fig.update_traces(marker=dict(opacity=0.85, line=dict(width=0.5, color='white')))

    return fig

class QueryAnalyzer:
    """Handles NLP heuristics, intent parsing, and column matching."""
    
    CHART_INTENT_WORDS: Set[str] = {
        "chart", "plot", "graph", "visualize", "visualisation", "show", "create", "make", "draw",
        "trend", "trends", "timeline", "time", "timeseries", "series", "over", "between", "across",
        "compare", "comparison", "vs", "versus", "by", "per", "group", "grouped",
        "distribution", "histogram", "correlation", "relationship", "scatter", "pie", "proportion", "percentage",
        "and", "or", "of", "the", "a", "an", "to", "for", "in", "on", "with", "non",
    }

    @staticmethod
    def select_column(query_lower: str, columns: List[str], preferred_terms: List[str]) -> Optional[str]:
        if not columns:
            return None
        columns_lower = {str(c).lower(): c for c in columns}
        for term in preferred_terms:
            for col_lower, original in columns_lower.items():
                if term in col_lower:
                    return original
        for token in re.findall(r"[a-zA-Z]{3,}", query_lower):
            for col_lower, original in columns_lower.items():
                if token in col_lower:
                    return original
        return columns[0]

    @classmethod
    def get_subject_terms(cls, query_lower: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z]{3,}", query_lower)
        terms = [t for t in tokens if t not in cls.CHART_INTENT_WORDS]
        return list(dict.fromkeys(terms)) # Deduplicate preserving order

    @classmethod
    def subject_terms_match_columns(cls, df: pd.DataFrame, query_lower: str) -> bool:
        subject_terms = cls.get_subject_terms(query_lower)
        if not subject_terms:
            return True
        columns_lower = [str(c).lower() for c in df.columns]
        return any(any(term in col for col in columns_lower) for term in subject_terms)


# ==========================================
# 2. STRATEGY INTERFACES (OCP, DIP, ISP)
# ==========================================

class ChartStrategy(ABC):
    """Abstract base class for all chart generation strategies."""
    
    @abstractmethod
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        pass
    
    def _format_response(self, figure: go.Figure, chart_type: str) -> Dict[str, Any]:
        return {
            'type': chart_type,
            'data': json.loads(figure.to_json())
        }


# ==========================================
# 3. CONCRETE STRATEGIES (LSP)
# ==========================================

class LineChartStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        date_columns = df.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns.tolist()
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()

        if not date_columns:
            name_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ["date", "time", "day", "month", "year"])]
            for c in name_candidates:
                try:
                    if pd.to_datetime(df[c].head(50), errors='coerce').notna().any():
                        date_columns.append(c)
                        break
                except (TypeError, ValueError):
                    continue

        if not date_columns or not numeric_columns:
            return None

        x_col, y_col = date_columns[0], numeric_columns[0]
        figure = SAFE_PX.line(df.head(200), x=x_col, y=y_col, title=f"{y_col} over {x_col}")
        _style_figure(figure, 'line', x_title=x_col, y_title=y_col)
        return self._format_response(figure, 'line')


class BarChartStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        categorical = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        numeric = df.select_dtypes(include=['number']).columns.tolist()

        if not categorical or not numeric:
            return None
        
        query_lower = (query or "").lower()
        x_col = QueryAnalyzer.select_column(query_lower, categorical, ["category", "brand", "availability", "status", "color", "name", "type"])
        y_col = QueryAnalyzer.select_column(query_lower, numeric, ["stock", "price", "count", "total", "sum", "quantity", "amount", "value"])
        
        if any(word in query_lower for word in ['count', 'how many', 'frequency']):
            grouped = df.groupby(x_col, dropna=False).size().reset_index(name='Value')
            y_plot_col = 'Value'
        elif any(word in query_lower for word in ['average', 'mean']):
            grouped = df.groupby(x_col, dropna=False)[y_col].mean().reset_index()
            y_plot_col = y_col
        else:
            grouped = df.groupby(x_col, dropna=False)[y_col].sum().reset_index()
            y_plot_col = y_col

        if not any(k in query_lower for k in ['for each', 'each', 'all', 'every']) and len(grouped) > 10:
            grouped = grouped.nlargest(10, y_plot_col)
        
        figure = SAFE_PX.bar(grouped, x=x_col, y=y_plot_col, title=f"{_humanize_label(y_plot_col)} by {_humanize_label(x_col)}")
        _style_figure(figure, 'bar', x_title=x_col, y_title=y_plot_col)
        return self._format_response(figure, 'bar')


class HistogramStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        numeric = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric:
            return None
        col = numeric[0]
        figure = SAFE_PX.histogram(df, x=col, title=f"Distribution of {_humanize_label(col)}", nbins=30)
        _style_figure(figure, 'histogram', x_title=col, y_title='Count')
        return self._format_response(figure, 'histogram')


class CategoryDistributionStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        categorical = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        numeric = df.select_dtypes(include=['number']).columns.tolist()
        if not categorical or not numeric:
            return BarChartStrategy().generate(df, query)

        query_lower = (query or "").lower()
        category_col = QueryAnalyzer.select_column(query_lower, categorical, ["category", "brand", "type", "segment", "region", "status"])
        metric_col = QueryAnalyzer.select_column(query_lower, numeric, ["price", "revenue", "sales", "amount", "value", "stock", "quantity"])

        top_n = 10
        if 'top 5' in query_lower:
            top_n = 5
        elif 'top 10' in query_lower:
            top_n = 10

        aggregated = (
            df.groupby(category_col, dropna=False)[metric_col]
            .sum()
            .reset_index()
            .sort_values(metric_col, ascending=False)
            .head(top_n)
        )
        title = f"Top {top_n} {_humanize_label(category_col)} by Total {_humanize_label(metric_col)}"
        figure = SAFE_PX.bar(
            aggregated,
            x=metric_col,
            y=category_col,
            orientation='h',
            color=metric_col,
            color_continuous_scale='Blues',
            title=title,
        )
        figure.update_layout(coloraxis_showscale=False, yaxis={'categoryorder': 'total ascending'})
        _style_figure(figure, 'bar', x_title=metric_col, y_title=category_col)
        return self._format_response(figure, 'bar')


class ScatterPlotStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        numeric = df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric) < 2:
            return BarChartStrategy().generate(df, query) # Fallback
        
        query_lower = (query or "").lower()
        x_col = QueryAnalyzer.select_column(query_lower, numeric, ["price", "x", "amount", "value", "stock", "quantity"])
        remaining_numeric = [c for c in numeric if c != x_col] or numeric
        y_col = QueryAnalyzer.select_column(query_lower, remaining_numeric, ["stock", "y", "quantity", "count", "price", "value"])

        categorical = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        category_col = QueryAnalyzer.select_column(
            query_lower,
            categorical,
            ["category", "brand", "type", "segment", "region", "status", "group"],
        ) if categorical else None

        if category_col and df[category_col].nunique(dropna=False) > 1:
            summary = (
                df.groupby(category_col, dropna=False)
                .agg(
                    x_value=(x_col, 'mean'),
                    y_value=(y_col, 'mean'),
                    record_count=(category_col, 'size'),
                )
                .reset_index()
                .sort_values('record_count', ascending=False)
            )
            if len(summary) > 12:
                summary = summary.head(12)
            summary['label'] = summary[category_col].astype(str)

            title = f"Average {_humanize_label(y_col)} vs Average {_humanize_label(x_col)} by {_humanize_label(category_col)}"
            figure = SAFE_PX.scatter(
                summary,
                x='x_value',
                y='y_value',
                color=category_col,
                size='record_count',
                title=title,
                hover_data={'record_count': True},
            )
            for trace in figure.data:
                trace.text = [trace.name] * len(trace.x)
                trace.mode = 'markers+text'
                trace.textposition = 'top center'
            _style_figure(figure, 'scatter', x_title=f"Average {x_col}", y_title=f"Average {y_col}")
            return self._format_response(figure, 'scatter')

        figure = SAFE_PX.scatter(df.head(100), x=x_col, y=y_col, title=f"{_humanize_label(y_col)} vs {_humanize_label(x_col)}")
        _style_figure(figure, 'scatter', x_title=x_col, y_title=y_col)
        return self._format_response(figure, 'scatter')


class PieChartStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        categorical = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        numeric = df.select_dtypes(include=['number']).columns.tolist()

        if not categorical or not numeric:
            return None
        
        names_col, values_col = categorical[0], numeric[0]
        grouped = df.groupby(names_col, dropna=False)[values_col].sum().reset_index().nlargest(10, values_col)
        figure = SAFE_PX.pie(grouped, names=names_col, values=values_col, title=f"{_humanize_label(values_col)} by {_humanize_label(names_col)}")
        _style_figure(figure, 'pie')
        return self._format_response(figure, 'pie')

# ==========================================
# 4. FACTORY & SERVICE (OCP, SRP)
# ==========================================

class ChartStrategyFactory:
    """Decides which strategy to use based on the query and context."""
    
    @staticmethod
    def get_strategy(query: Optional[str] = None, code: Optional[str] = None) -> ChartStrategy:
        query_lower = (query or "").lower()
        
        # Determine if we should use CodeStrategy
        if code:
            prefers_full = any(k in query_lower for k in ["for each", "each", "all", "every"])
            has_top_n = any(k in code.lower() for k in ["head(", "nlargest(", "nsmallest("])
            if not (prefers_full and has_top_n):
                return CodeStrategy(code)
                
        # Fallbacks mapping
        if any(w in query_lower for w in ['trend', 'over time', 'timeline', 'time series']):
            return LineChartStrategy()
        if 'distribution' in query_lower and any(token in query_lower for token in [' by ', 'category', 'brand', 'segment', 'region']):
            return CategoryDistributionStrategy()
        if any(w in query_lower for w in ['distribution', 'histogram']):
            return HistogramStrategy()
        if any(w in query_lower for w in ['compare', 'comparison', 'vs', 'versus']):
            return BarChartStrategy()
        if any(w in query_lower for w in ['correlation', 'relationship']):
            return ScatterPlotStrategy()
        if any(w in query_lower for w in ['pie', 'proportion', 'percentage']):
            return PieChartStrategy()
            
        return BarChartStrategy()


class ChartGeneratorService:
    """Main Orchestrator Service."""
    
    @staticmethod
    def generate_chart_from_query(df: pd.DataFrame, query: str, code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if df is None or getattr(df, "empty", False):
            print("[chart_generator] DataFrame is None or empty")
            return None

        query_lower = query.lower()

        # 1. Get the strategy (Will be ExecutedCodeStrategy if DeepSeek wrote code)
        strategy = ChartStrategyFactory.get_strategy(query, code)
        
        # 2. If we do NOT have code, apply the strict NLP heuristic guardrail
        if not isinstance(strategy, CodeStrategy):
            if not QueryAnalyzer.subject_terms_match_columns(df, query_lower):
                print("[chart_generator] Query terms don't match dataset columns. Skipping heuristic chart.")
                return None

        # 3. Generate the chart (This will run the exec() block if code is provided)
        result = strategy.generate(df, query)
        
        # 4. If Code Strategy failed gracefully (e.g. blocked Matplotlib) and returned None, try fallback
        if result is None and isinstance(strategy, CodeStrategy):
            if not query:
                return None
            if not QueryAnalyzer.subject_terms_match_columns(df, query_lower):
                print("[chart_generator] Query terms don't match dataset columns. Skipping fallback chart.")
                return None
            
            fallback_strategy = ChartStrategyFactory.get_strategy(query, code=None)
            result = fallback_strategy.generate(df, query)

        return result

    @staticmethod
    def generate_chart(df: pd.DataFrame, code: str) -> Optional[Dict[str, Any]]:
        if df is None or getattr(df, "empty", False):
            print("[chart_generator] DataFrame is None or empty")
            return None

        return CodeStrategy(code).generate(df)


class CodeStrategy(ChartStrategy):
    """Generates charts by executing arbitrary python code generated by LLMs."""
    
    def __init__(self, code: str):
        self.code = code

    @staticmethod
    def _repair_generated_code(code: str) -> tuple[str, bool]:
        """Patch common LLM chart mistakes before execution."""
        repaired = code or ""

        # Correlation on categorical strings often crashes; route to safe helper.
        repaired = re.sub(
            r"df\[\s*['\"]([^'\"]+)['\"]\s*\]\.corr\(\s*df\[\s*['\"]([^'\"]+)['\"]\s*\]\s*\)",
            lambda m: f"_safe_corr(df, {repr(m.group(1))}, {repr(m.group(2))})",
            repaired,
        )

        # Plotly expects a column for size; direct Python lists can break grouping.
        size_pattern = r"size\s*=\s*\[\s*1\s*\]\s*\*\s*len\(\s*df\s*\)"
        uses_constant_size = re.search(size_pattern, repaired) is not None
        repaired = re.sub(size_pattern, "size='__constant_size__'", repaired)

        # Plotly Express does not support `sort=` on chart calls.
        repaired = re.sub(r",\s*sort\s*=\s*(True|False)", "", repaired)

        return repaired, uses_constant_size

    def generate(self, df: pd.DataFrame, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            # 1. Block malicious or blocking GUI calls
            if any(token in self.code.lower() for token in ['matplotlib', 'pyplot', 'plt.', '.show(', '.plot(']):
                print("[chart_generator] Blocked matplotlib code to prevent server hang.")
                return None

            # 2. Execute the code with utility functions available
            # We inject px, pd, go, and format_number_indian so DeepSeek-generated code can use them
            executable_code, uses_constant_size = self._repair_generated_code(self.code)
            df_for_exec = df.copy() if uses_constant_size else df
            if uses_constant_size and '__constant_size__' not in df_for_exec.columns:
                df_for_exec['__constant_size__'] = 1

            global_scope = {
                "pd": pd,
                "df": df_for_exec,
                "px": SAFE_PX,
                "go": go,
                "format_number_indian": format_number_indian,
                "_safe_corr": _safe_corr,
            }
            local_vars = {
                "df": df_for_exec,
                "pd": pd,
                "px": SAFE_PX,
                "go": go,
                "format_number_indian": format_number_indian,
                "_safe_corr": _safe_corr,
            }
            exec(executable_code, global_scope, local_vars)
            
            result = local_vars.get("result")
            
            # 3. FAST PATH
            if isinstance(result, go.Figure):
                chart_type = result.data[0].type if result.data else 'custom'
                _style_figure(result, chart_type)
                return {
                    'type': chart_type,
                    'data': json.loads(result.to_json())
                }

            # 4. FALLBACK PATH
            normalized = self._normalize_result_to_dataframe(result)
            if normalized is None:
                raise ValueError(f"Executed code did not return a valid DataFrame or Plotly Figure in 'result'. Type was: {type(result)}")
            result_df, x_axis, y_axis = normalized
            
            query_lower = (query or "").lower()
            if len(result_df) > 20 and not any(k in query_lower for k in ['for each', 'each', 'all', 'every']):
                result_df = result_df.nlargest(20, y_axis) if y_axis in result_df.columns and is_numeric_dtype(result_df[y_axis]) else result_df.head(20)
            
            title = query.capitalize() if query else "Generated chart"
            if any(w in query_lower for w in ['pie', 'proportion', 'percentage']):
                figure = SAFE_PX.pie(result_df, names=x_axis, values=y_axis, title=title)
                _style_figure(figure, 'pie')
                return self._format_response(figure, 'pie')
            elif any(w in query_lower for w in ['line', 'trend', 'over time']):
                figure = SAFE_PX.line(result_df, x=x_axis, y=y_axis, title=title)
                _style_figure(figure, 'line', x_title=x_axis, y_title=y_axis)
                return self._format_response(figure, 'line')
            else:
                figure = SAFE_PX.bar(result_df, x=x_axis, y=y_axis, title=title)
                _style_figure(figure, 'bar', x_title=x_axis, y_title=y_axis)
                return self._format_response(figure, 'bar')
                
        except Exception as e:
            # Raise our custom exception so the orchestrator knows to retry!
            error_traceback = traceback.format_exc()
            print(f"\n[chart_generator] ❌ CODE CRASHED:\n{error_traceback}\n")
            raise ChartGenerationError(f"Chart code execution failed:\n{error_traceback}") from e

    def _normalize_result_to_dataframe(self, result: Any) -> Optional[tuple[pd.DataFrame, str, str]]:
        if isinstance(result, dict):
            out = pd.DataFrame(list(result.items()), columns=['Category', 'Value'])
            return out, 'Category', 'Value'
        elif isinstance(result, pd.Series):
            y_label = str(result.name) if result.name else 'Value'
            x_label = str(result.index.name) if result.index.name else 'Category'
            out = result.reset_index(name=y_label)
            out.columns = [x_label, y_label]
            return out, x_label, y_label
        elif isinstance(result, pd.DataFrame):
            df = result.copy()

            if df.empty:
                return None

            # Fast-path: already in expected shape.
            if len(df.columns) == 2:
                x_label = str(df.columns[0])
                y_label = str(df.columns[1])
                return df, x_label, y_label

            # Prefer explicit semantic columns when present.
            column_lookup = {str(col).strip().lower(): col for col in df.columns}
            if 'category' in column_lookup and 'value' in column_lookup:
                cat_col = column_lookup['category']
                val_col = column_lookup['value']
                out = df[[cat_col, val_col]].copy()
                return out, str(cat_col), str(val_col)

            numeric_cols = [col for col in df.columns if is_numeric_dtype(df[col])]
            non_numeric_cols = [col for col in df.columns if col not in numeric_cols]

            # Common case from generated code: [dimension, metric, ...extra].
            if non_numeric_cols and numeric_cols:
                out = df[[non_numeric_cols[0], numeric_cols[0]]].copy()
                return out, str(non_numeric_cols[0]), str(numeric_cols[0])

            # If everything is numeric, use first column as pseudo-category and second as value.
            if len(numeric_cols) >= 2:
                out = df[[numeric_cols[0], numeric_cols[1]]].copy()
                return out, str(numeric_cols[0]), str(numeric_cols[1])

            # Single numeric column: use index as category.
            if len(numeric_cols) == 1:
                out = df[[numeric_cols[0]]].copy()
                x_label = 'Index'
                y_label = str(numeric_cols[0])
                out.insert(0, x_label, out.index.astype(str))
                out.columns = [x_label, y_label]
                return out, x_label, y_label

            # No numeric columns: chart record counts by first column.
            first_col = df.columns[0]
            y_label = 'Count'
            out = df.groupby(first_col, dropna=False).size().reset_index(name=y_label)
            return out, str(first_col), y_label
        return None

# ==========================================
# PUBLIC API WRAPPER
# ==========================================
def generate_chart_from_query(df: pd.DataFrame, query: str, code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Generate a chart from a natural-language query, optionally using generated code first."""
    return ChartGeneratorService.generate_chart_from_query(df, query, code)


def generate_chart(df: pd.DataFrame, code: str) -> Optional[Dict[str, Any]]:
    """Execute generated chart code and return the resulting chart payload."""
    return ChartGeneratorService.generate_chart(df, code)


if __name__ == "__main__":
    # Basic test case
    df_test = pd.read_csv('/Users/rwk3030/Downloads/products-100.csv')

    # code = "This visualization will help identify which categories have higher price points and inform pricing strategies."
    code_ = "\nresult = df.groupby('category')['price'].mean().reset_index()"
    chart = generate_chart(df_test, code_)
    if chart:
        preview_figure = go.Figure(chart['data'])
        preview_figure.show()
    print(chart)