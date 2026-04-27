import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, Optional, Set, List, Type
import json
import re
from abc import ABC, abstractmethod
import plotly.graph_objects as go
import traceback

# ==========================================
# 1. UTILITIES & ANALYZERS (SRP)
# ==========================================
class ChartGenerationError(Exception):
    """Exception raised when LLM-generated chart code fails to execute."""
    pass
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
    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        pass
    
    def _format_response(self, fig: go.Figure, chart_type: str) -> Dict[str, Any]:
        return {
            'type': chart_type,
            'data': json.loads(fig.to_json())
        }


# ==========================================
# 3. CONCRETE STRATEGIES (LSP)
# ==========================================

class LineChartStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        date_columns = df.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns.tolist()
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()

        if not date_columns:
            name_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ["date", "time", "day", "month", "year"])]
            for c in name_candidates:
                try:
                    if pd.to_datetime(df[c].head(50), errors='coerce').notna().any():
                        date_columns.append(c)
                        break
                except Exception:
                    continue

        if not date_columns or not numeric_columns:
            return None

        x_col, y_col = date_columns[0], numeric_columns[0]
        fig = px.line(df.head(200), x=x_col, y=y_col, title=f"{y_col} over {x_col}")
        return self._format_response(fig, 'line')


class BarChartStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        categorical = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        numeric = df.select_dtypes(include=['number']).columns.tolist()

        if not categorical or not numeric:
            return None
        
        query_lower = query.lower()
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
        
        fig = px.bar(grouped, x=x_col, y=y_plot_col, title=f"{y_plot_col} by {x_col}")
        return self._format_response(fig, 'bar')


class HistogramStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        numeric = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric:
            return None
        col = numeric[0]
        fig = px.histogram(df, x=col, title=f"Distribution of {col}", nbins=30)
        return self._format_response(fig, 'histogram')


class ScatterPlotStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        numeric = df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric) < 2:
            return BarChartStrategy().generate(df, query) # Fallback
        
        query_lower = query.lower()
        x_col = QueryAnalyzer.select_column(query_lower, numeric, ["price", "x", "amount", "value", "stock", "quantity"])
        remaining_numeric = [c for c in numeric if c != x_col] or numeric
        y_col = QueryAnalyzer.select_column(query_lower, remaining_numeric, ["stock", "y", "quantity", "count", "price", "value"])
        
        fig = px.scatter(df.head(100), x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        return self._format_response(fig, 'scatter')


class PieChartStrategy(ChartStrategy):
    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        categorical = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        numeric = df.select_dtypes(include=['number']).columns.tolist()

        if not categorical or not numeric:
            return None
        
        names_col, values_col = categorical[0], numeric[0]
        grouped = df.groupby(names_col, dropna=False)[values_col].sum().reset_index().nlargest(10, values_col)
        fig = px.pie(grouped, names=names_col, values=values_col, title=f"{values_col} by {names_col}")
        return self._format_response(fig, 'pie')

# ==========================================
# 4. FACTORY & SERVICE (OCP, SRP)
# ==========================================

class ChartStrategyFactory:
    """Decides which strategy to use based on the query and context."""
    
    @staticmethod
    def get_strategy(query: str, code: Optional[str] = None) -> ChartStrategy:
        query_lower = query.lower()
        
        # Determine if we should use CodeStrategy
        if code:
            prefers_full = any(k in query_lower for k in ["for each", "each", "all", "every"])
            has_top_n = any(k in code.lower() for k in ["head(", "nlargest(", "nsmallest("])
            if not (prefers_full and has_top_n):
                return CodeStrategy(code)
                
        # Fallbacks mapping
        if any(w in query_lower for w in ['trend', 'over time', 'timeline', 'time series']):
            return LineChartStrategy()
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
    def generate_chart(df: pd.DataFrame, query: str, code: Optional[str] = None, llm_fix_callback=None) -> Optional[Dict[str, Any]]:
        if df is None or getattr(df, "empty", False):
            print("[chart_generator] DataFrame is None or empty")
            return None

        # 1. Get the strategy (Will be ExecutedCodeStrategy if DeepSeek wrote code)
        strategy = ChartStrategyFactory.get_strategy(query, code)
        
        # 2. If we do NOT have code, apply the strict NLP heuristic guardrail
        if not isinstance(strategy, CodeStrategy):
            if not QueryAnalyzer.subject_terms_match_columns(df, query.lower()):
                print("[chart_generator] Query terms don't match dataset columns. Skipping heuristic chart.")
                return None

        # 3. Generate the chart (This will run the exec() block if code is provided)
        result = strategy.generate(df, query)
        
        # 4. If Code Strategy failed gracefully (e.g. blocked Matplotlib) and returned None, try fallback
        if result is None and isinstance(strategy, CodeStrategy):
            if not QueryAnalyzer.subject_terms_match_columns(df, query.lower()):
                print("[chart_generator] Query terms don't match dataset columns. Skipping fallback chart.")
                return None
            
            fallback_strategy = ChartStrategyFactory.get_strategy(query, code=None)
            result = fallback_strategy.generate(df, query)

        return result
class CodeStrategy(ChartStrategy):
    """Generates charts by executing arbitrary python code generated by LLMs."""
    
    def __init__(self, code: str):
        self.code = code

    def generate(self, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
        try:
            # 1. Block malicious or blocking GUI calls
            if any(token in self.code.lower() for token in ['matplotlib', 'pyplot', 'plt.', '.show(', '.plot(']):
                print("[chart_generator] Blocked matplotlib code to prevent server hang.")
                return None

            # 2. Execute the code
            # We inject px into the environment so DeepSeek can use it without importing
            local_vars = {"df": df, "pd": pd, "px": px, "go": go}
            exec(self.code, {"pd": pd, "df": df, "px": px, "go": go}, local_vars)
            
            result = local_vars.get("result")
            
            # 3. FAST PATH
            if isinstance(result, go.Figure):
                return {
                    'type': result.data[0].type if result.data else 'custom',
                    'data': json.loads(result.to_json())
                }

            # 4. FALLBACK PATH
            result_df = self._normalize_result_to_dataframe(result)
            if result_df is None:
                raise ValueError(f"Executed code did not return a valid DataFrame or Plotly Figure in 'result'. Type was: {type(result)}")
            
            query_lower = query.lower()
            if len(result_df) > 20 and not any(k in query_lower for k in ['for each', 'each', 'all', 'every']):
                result_df = result_df.nlargest(20, 'Value') if 'Value' in result_df.columns else result_df.head(20)
            
            title = query.capitalize()
            if any(w in query_lower for w in ['pie', 'proportion', 'percentage']):
                fig = px.pie(result_df, names='Category', values='Value', title=title)
                return self._format_response(fig, 'pie')
            elif any(w in query_lower for w in ['line', 'trend', 'over time']):
                fig = px.line(result_df, x='Category', y='Value', title=title)
                return self._format_response(fig, 'line')
            else:
                fig = px.bar(result_df, x='Category', y='Value', title=title)
                return self._format_response(fig, 'bar')
                
        except Exception as e:
            # Raise our custom exception so the orchestrator knows to retry!
            error_traceback = traceback.format_exc()
            print(f"\n[chart_generator] ❌ CODE CRASHED:\n{error_traceback}\n")
            raise ChartGenerationError(f"Chart code execution failed:\n{error_traceback}")

    def _normalize_result_to_dataframe(self, result: Any) -> Optional[pd.DataFrame]:
        if isinstance(result, dict):
            return pd.DataFrame(list(result.items()), columns=['Category', 'Value'])
        elif isinstance(result, pd.Series):
            df = result.reset_index()
            df.columns = ['Category', 'Value']
            return df
        elif isinstance(result, pd.DataFrame) and len(result.columns) == 2:
            result.columns = ['Category', 'Value']
            return result
        return None

# ==========================================
# PUBLIC API WRAPPER
# ==========================================
def generate_chart(df: pd.DataFrame, query: str, code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Legacy wrapper for backward compatibility."""
    return ChartGeneratorService.generate_chart(df, query, code)