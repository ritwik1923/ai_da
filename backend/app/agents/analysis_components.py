"""
Data analysis components following SOLID principles.
Each class has a single, well-defined responsibility.
"""

import json
import re
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.utils.chart_generator import generate_chart, generate_chart_from_query
from app.utils.logger import get_production_logger
from app.agents.utility.CodeGenerationService import CodeGenerationService

logger = get_production_logger("ai_da.analysis")


class DataProfiler:
    """
    Single Responsibility: Extract data profiling metrics from a DataFrame.
    No AI, no chart generation - just data analysis.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def profile(self) -> Dict[str, Any]:
        """Generate comprehensive data profile."""
        total_rows = len(self.df)
        total_columns = len(self.df.columns)
        missing_count = int(self.df.isna().sum().sum())
        missing_percent = round(
            (missing_count / (total_rows * total_columns) * 100)
            if total_rows and total_columns else 0, 2
        )

        numeric_df = self.df.select_dtypes(include=['number'])
        categorical_df = self.df.select_dtypes(include=['object', 'category'])

        return {
            "total_rows": total_rows,
            "total_columns": total_columns,
            "numeric_count": len(numeric_df.columns),
            "categorical_count": len(categorical_df.columns),
            "missing_count": missing_count,
            "missing_percent": missing_percent,
            "numeric_df": numeric_df,
            "categorical_df": categorical_df,
        }

    def get_summary(self, profile: Dict[str, Any]) -> Dict[str, int]:
        """Get summary statistics."""
        return {
            "rows": profile["total_rows"],
            "columns": profile["total_columns"],
            "numeric_columns": profile["numeric_count"],
            "categorical_columns": profile["categorical_count"],
            "missing_values": profile["missing_count"],
            "missing_percent": profile["missing_percent"],
        }

    def get_metrics(self, profile: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate metric cards for dashboard."""
        metrics = [
            {"label": "Total rows", "value": f"{profile['total_rows']:,}"},
            {"label": "Columns", "value": f"{profile['total_columns']}"},
            {"label": "Numeric columns", "value": f"{profile['numeric_count']}"},
            {"label": "Categorical columns", "value": f"{profile['categorical_count']}"},
            {"label": "Missing values", "value": f"{profile['missing_count']} ({profile['missing_percent']}%)"},
        ]

        # Add numeric column averages
        if profile["numeric_count"]:
            numeric_summary = profile["numeric_df"].agg(['min', 'mean', 'max']).transpose().reset_index()
            top_metrics = numeric_summary.sort_values(by='mean', ascending=False).head(3)
            for _, row in top_metrics.iterrows():
                metrics.append({
                    "label": f"Avg {row['index']}",
                    "value": f"{row['mean']:.2f}"
                })

        return metrics

    def get_categories(self, profile: Dict[str, Any], limit: int = 3) -> Optional[List[Dict[str, Any]]]:
        """Extract top categories from categorical columns."""
        categories = []
        if profile["categorical_count"]:
            for column in profile["categorical_df"].columns:
                counts = self.df[column].value_counts(dropna=False)
                if len(counts) <= 12 and len(counts) > 0:
                    categories.append({
                        "column": column,
                        "value": str(counts.index[0]),
                        "count": int(counts.iloc[0])
                    })
                    if len(categories) >= limit:
                        break
        return categories if categories else None

    def get_date_insights(self) -> Optional[Tuple[List[Dict[str, str]], List[str]]]:
        """Extract date/time ranges and insights."""
        metrics = []
        insights = []

        for column in self.df.columns:
            if 'date' in column.lower() or 'time' in column.lower():
                try:
                    parsed = pd.to_datetime(self.df[column], errors='coerce')
                    if parsed.notna().sum() / max(1, len(parsed)) > 0.5:
                        date_range = parsed.dropna().agg(['min', 'max']).to_dict()
                        metrics.append({
                            "label": f"{column} range",
                            "value": f"{date_range['min'].date()} → {date_range['max'].date()}"
                        })
                        insights.append(
                            f"{column} ranges from {date_range['min'].date()} to {date_range['max'].date()}"
                        )
                except Exception:
                    continue

        return (metrics, insights) if metrics else (None, None)


class ResponseNormalizer:
    """
    Single Responsibility: Parse and normalize API responses into standardized structures.
    Handles JSON parsing, string normalization, and fallback generation.
    """

    @staticmethod
    def normalize_string(value: Any) -> Optional[str]:
        """Normalize any value to string."""
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            return value.get("text") or value.get("summary") or json.dumps(value)
        return str(value)

    @staticmethod
    def normalize_string_list(value: Any) -> List[str]:
        """Normalize any value to list of strings."""
        if isinstance(value, list):
            return [str(item).strip() for item in value if item is not None and str(item).strip()]
        if isinstance(value, str):
            lines = [line.strip() for line in re.split(r"[\n\r]+", value) if line.strip()]
            if len(lines) > 1:
                return lines
            return [part.strip() for part in re.split(r"[,;•\-–]+", value) if part.strip()]
        return []

    @staticmethod
    def parse_json_response(response: Any) -> Dict[str, Any]:
        """Safely parse JSON from various response formats."""
        if isinstance(response, dict):
            return response
        if not isinstance(response, str):
            return {"ai_summary": ResponseNormalizer.normalize_string(response)}

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            extracted = ResponseNormalizer._extract_json(response)
            if extracted:
                try:
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    pass
        return {"ai_summary": response}

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """Extract JSON from text."""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return None

    def normalize_analysis_output(self, parsed: Any, df: pd.DataFrame) -> Dict[str, Any]:
        """Normalize AI analysis output."""
        if not isinstance(parsed, dict):
            return {
                "ai_summary": self.normalize_string(parsed),
                "data_quality": None,
                "analysis_insights": None,
                "visual_recommendations": None,
            }

        ai_summary = self.normalize_string(parsed.get("ai_summary"))
        data_quality = self._normalize_data_quality(parsed.get("data_quality"))
        analysis_insights = self._normalize_analysis_insights(parsed.get("analysis_insights"))
        visual_recommendations = self._normalize_visual_recommendations(
            parsed.get("visual_recommendations"), df
        )

        return {
            "ai_summary": ai_summary,
            "data_quality": data_quality,
            "analysis_insights": analysis_insights,
            "visual_recommendations": visual_recommendations,
        }

    def _normalize_data_quality(self, value: Any) -> Optional[List[Dict[str, Any]]]:
        """Normalize data quality array."""
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, str):
            return [{
                "metric": "data_quality",
                "status": "warning",
                "description": value,
            }]
        return value if isinstance(value, list) else None

    def _normalize_analysis_insights(self, value: Any) -> Optional[List[Dict[str, Any]]]:
        """Normalize analysis insights array."""
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, str) or not isinstance(value, list):
            return None

        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "title": self.normalize_string(item.get("title")) or "Insight",
                "description": self.normalize_string(item.get("description")) or "",
                "key_findings": self.normalize_string_list(item.get("key_findings")),
                "recommendations": self.normalize_string_list(item.get("recommendations")),
            })
        return normalized if normalized else None

    def _normalize_visual_recommendations(self, value: Any, df: pd.DataFrame) -> Optional[List[Dict[str, str]]]:
        """Normalize visual recommendations array."""
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return None

        normalized = []
        seen_signatures = set()

        def build_signature(title: str, suggested_query: str) -> tuple[str, tuple[str, ...]]:
            query_lower = (suggested_query or "").strip().lower()
            title_lower = (title or "").strip().lower()

            if any(token in query_lower for token in ["relationship", "correlation", " vs ", " versus "]):
                intent = "relationship"
            elif any(token in query_lower for token in ["distribution", "histogram"]):
                intent = "distribution"
            elif any(token in query_lower for token in ["trend", "over time", "across time"]):
                intent = "trend"
            elif any(token in query_lower for token in ["top ", "rank", "highest", "lowest"]):
                intent = "ranking"
            else:
                intent = "comparison"

            stopwords = {
                "show", "display", "compare", "relationship", "between", "across", "over", "time",
                "top", "by", "the", "and", "of", "for", "to", "with", "a", "an", "vs", "versus"
            }
            tokens = re.findall(r"[a-zA-Z_]{3,}", f"{title_lower} {query_lower}")
            keywords = tuple(sorted({token for token in tokens if token not in stopwords}))
            return intent, keywords

        for item in value:
            if not isinstance(item, dict):
                continue
            title = self.normalize_string(item.get("title")) or "Visualization"
            description = self.normalize_string(item.get("description")) or ""
            suggested_query = self.normalize_string(item.get("suggested_query")) or ""
            if suggested_query and len(suggested_query.split()) >= 3:
                signature = build_signature(title, suggested_query)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                normalized.append({
                    "title": title,
                    "description": description,
                    "suggested_query": suggested_query,
                })

        return normalized if normalized else None



class ChartOrchestrator:
    """
    Single Responsibility: Generate and manage charts from visual recommendations.
    Wraps the chart_generator utility and manages code generation.
    """

    def __init__(self, df: pd.DataFrame, tool_factory: Optional[CodeGenerationService] = None):
        self.df = df
        self.tool_factory = tool_factory

    async def generate_charts(self, visual_recommendations: Optional[List[Dict]]) -> None:
        """
        Generate charts for each visual recommendation.
        Uses description to generate pandas code via deepseek, then executes it.
        Falls back to query-based generation if code generation fails.
        """
        if not visual_recommendations:
            return

        for rec in visual_recommendations:
            generated_code = None
            chart_data = None
            title = rec.get("title", "Unknown")

            try:
                # 1. Try to generate pandas code from description using coding_llm
                if rec.get("description"):
                    logger.info(f"🔄 Generating code for: {title}")
                    visualization_request = rec.get("suggested_query") or rec["description"]
                    visualization_payload = await self.tool_factory.generate_visualisation_code(visualization_request)
                    generated_code = visualization_payload.get("code", "")
                    if generated_code:
                        rec["generated_code"] = generated_code
                        rec["visualisation_examples"] = visualization_payload.get("examples")
                        logger.info(f"✅ Generated code ({len(generated_code)} chars) for: {title}")
                    else:
                        logger.warning(f"⚠️ Code generation returned empty for: {title}")

                # 2. Generate chart using code if available, otherwise use description
                if generated_code:
                    logger.info(f"🎨 Generating chart from code for: {title}")
                    try:
                        chart_data = generate_chart(self.df, generated_code)
                        if chart_data:
                            logger.info(f"✅ Chart generated from code for: {title}")
                        else:
                            logger.warning(f"⚠️ Chart generation from code returned None for: {title}")
                            # Fallback: try without code
                            logger.info(f"🔄 Trying fallback: chart from description for: {title}")
                            chart_data = generate_chart_from_query(
                                self.df,
                                rec.get("suggested_query") or rec["description"],
                                code=generated_code,
                            )
                    except Exception as code_gen_error:
                        logger.warning(f"⚠️ Chart generation from code failed for {title}, trying fallback: {code_gen_error}")
                        # Fallback to description-based generation
                        try:
                            chart_data = generate_chart_from_query(
                                self.df,
                                rec.get("suggested_query") or rec["description"],
                                code=generated_code,
                            )
                        except Exception as fallback_error:
                            logger.error(f"❌ Fallback also failed for {title}: {fallback_error}")
                else:
                    # No code generated, use description directly
                    logger.info(f"🎨 Generating chart from description for: {title}")
                    try:
                        chart_data = generate_chart_from_query(
                            self.df,
                            rec.get("suggested_query") or rec["description"],
                        )
                        if chart_data:
                            logger.info(f"✅ Chart generated from description for: {title}")
                        else:
                            logger.warning(f"⚠️ Chart generation from description returned None for: {title}")
                    except Exception as desc_gen_error:
                        logger.error(f"❌ Chart generation from description failed for {title}: {desc_gen_error}")

                rec["chart_data"] = chart_data if chart_data else None

            except Exception as e:
                logger.error(f"❌ Unexpected error processing chart for {title}: {e}")
                rec["chart_data"] = None

    def should_hide_basic_charts(self, visual_recommendations: Optional[List[Dict]]) -> bool:
        """Determine if basic charts should be hidden (AI charts are comprehensive)."""
        if not visual_recommendations:
            return False

        valid_charts = sum(1 for rec in visual_recommendations if rec.get("chart_data"))
        return valid_charts == len(visual_recommendations) and valid_charts > 0
