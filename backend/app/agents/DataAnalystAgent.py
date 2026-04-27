import traceback
import os
import sys
import json
import re
import pandas as pd
import plotly.graph_objects as go
import asyncio
import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from starlette.concurrency import run_in_threadpool

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.utils.logger import get_production_logger
from app.utils.self_healing_executor import SelfHealingExecutor
from app.utils.data_passport import generate_data_passport
from app.utils.chart_generator import generate_chart, ChartGenerationError
from app.agents.AgentGlobals import AgentGlobals
from app.agents.analysis_components import (
    DataProfiler,
    ResponseNormalizer,
    ChartOrchestrator,
)
from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory
from app.agents.utility.CodeGenerationService import CodeGenerationService
logger = get_production_logger("ai_da.brain_v4")


def _normalize_generated_code(code: str) -> str:
    cleaned_code = code.strip()
    if "```" in cleaned_code:
        cleaned_code = re.sub(r"^```(?:python)?\s*", "", cleaned_code)
        cleaned_code = re.sub(r"\s*```$", "", cleaned_code)

    if re.search(r"(^|\n)\s*result\s*=", cleaned_code):
        return cleaned_code

    assignment_matches = re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*$", cleaned_code, flags=re.MULTILINE)
    if assignment_matches:
        last_assigned_name = assignment_matches[-1]
        return f"{cleaned_code}\nresult = {last_assigned_name}"

    return cleaned_code

class DataAnalystAgent:
    """
    Production-grade Brain for ai_da. 
    Implements Intent Routing and Async Parallelism to reduce latency from 30s to <10s.
    """
    
    def __init__(
        self, 
        df: pd.DataFrame,
        reasoning_llm = None,
        coding_llm = None,
        example_store = None,
        react_store = None,
        visualization_store = None

    ):
        self.df = df
        # Ensure AI globals are initialized if this class is used outside startup
        if not AgentGlobals._initialized:
            try:
                AgentGlobals.initialize()
            except Exception as init_error:
                raise RuntimeError(
                    "Failed to initialize AgentGlobals. Ensure the app startup sequence has initialized AI resources."
                ) from init_error

        self.reasoning_llm = reasoning_llm or AgentGlobals.reasoning_llm  # llama3.1:8b 
        self.coding_llm = coding_llm or AgentGlobals.coding_llm        # deepseek-coder-v2:16b 
        self.example_store = example_store or AgentGlobals.example_store  # Code_FewShotExampleStore 
        self.react_store = react_store or AgentGlobals.react_example_store      # ReAct_FewShotExampleStore 
        self.visualization_store = visualization_store or AgentGlobals.visualization_store

        if not all([self.reasoning_llm, self.coding_llm, self.example_store, self.react_store]):
            raise RuntimeError(
                "AgentGlobals failed to initialize required AI resources."
            )

        self.data_passport = generate_data_passport(df, max_sample_rows=3)
        self.schema_context = self.data_passport.to_prompt_context()
        self.executor = SelfHealingExecutor(df=df, max_retries=3)
        self.code_service = CodeGenerationService(
            coding_llm=self.coding_llm,
            example_store=self.example_store,
            visualization_store=self.visualization_store,
            df=df,
            executor=self.executor
        )

        print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
        self.tool_factory = AnalysisToolFactory(
            data_passport=self.data_passport,
            code_service=self.code_service,
            df=df,
        )

        self.available_columns = ""
        if self.df is not None:
            numeric_cols = self._get_numeric_analysis_columns()
            categorical_cols = self.df.select_dtypes(include=['object', 'category']).columns.tolist()
            datetime_cols = self._infer_datetime_columns()
            categorical_cols = [
                col for col in categorical_cols
                if not self._is_identifier_like_column(col)
            ]
            self.available_columns = f"""

        AVAILABLE COLUMNS IN THIS DATASET:
        - Numeric (for Y-axis): {', '.join(numeric_cols) if numeric_cols else 'None'}
        - Categorical (for grouping): {', '.join(categorical_cols) if categorical_cols else 'None'}
        - Date/Time (for X-axis): {', '.join(datetime_cols) if datetime_cols else 'None'}

        CRITICAL: Only use columns listed above. Do NOT suggest visualizations for columns like 'revenue', 'sales', etc. unless they actually appear in the list above.
            """

    def _should_use_code_path(self, query: str) -> bool:
        normalized_query = query.lower().strip()
        direct_keywords = {
            "median", "average", "avg", "sum", "mean", "plot", "chart", "max",
            "min", "count", "exact", "top", "bottom", "highest", "lowest", "largest",
            "smallest", "rank", "ranking", "revenue", "sales", "profit", "total",
        }
        ranking_patterns = [
            r"\btop\s+\d+\b",
            r"\bbottom\s+\d+\b",
            r"\bhighest\b",
            r"\blowest\b",
            r"\bsort(?:ed)?\s+by\b",
            r"\bgroup(?:ed)?\s+by\b",
        ]

        if any(keyword in normalized_query for keyword in direct_keywords):
            return True

        return any(re.search(pattern, normalized_query) for pattern in ranking_patterns)

    @staticmethod
    def _is_chart_query(query: str) -> bool:
        chart_keywords = {
            "plot", "chart", "graph", "visualize", "visualise", "scatter",
            "bar", "line", "histogram", "pie", "trend",
        }
        normalized_query = query.lower()
        return any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized_query)
            for keyword in chart_keywords
        )

    @staticmethod
    def _looks_like_reasoning_plan(response: str) -> bool:
        normalized_response = response.strip().lower()
        plan_markers = [
            "to answer the question",
            "i will use the following steps",
            "here's how i would",
            "to solve this question",
            "i will use the analysis tool",
            "we need to use the analysis tool",
            "follow these steps",
            "thought process",
            "similar thought process",
            "i will follow",
            "we need to",
            "thought:",
            "action:",
            "final answer:",
        ]
        return any(marker in normalized_response for marker in plan_markers)

    @staticmethod
    def _format_scalar_answer(raw_data: Dict[str, Any]) -> Optional[str]:
        if raw_data.get("type") != "scalar":
            return None

        value = raw_data.get("value")
        if value is None:
            return None

        return str(value)

    async def analyze(self, query: str, history: List[Dict] = None) -> Dict[str, Any]:
        """Main entry point that routes between fast-path code and reasoning path."""
        history = history or []

        if self._should_use_code_path(query):
            logger.info(f"⚡ Fast-Path: Routing direct to Coding LLM for query: '{query}'")
            return await self._execute_direct_code_path(query)

        logger.info(f"🧠 ReAct-Path: Routing to Reasoning Manager for query: '{query}'")
        return await self._execute_reasoning_path(query, history)

    async def _execute_direct_code_path(self, query: str) -> Dict[str, Any]:
        """Generate code, execute it, and summarize results for direct analytic prompts."""
        chart_query = self._is_chart_query(query)
        code_examples = self.example_store.get_context_string(query, k=2)

        code_prompt = PromptTemplate.from_template("""
            You are an expert Python Data Scientist. Use the pre-loaded 'df' variable.
            Schema: {schema}
            Task: {query}

            Successful Patterns:
            {examples}

            RULES:
            1. Return ONLY executable Python code.
            2. No explanations or markdown headers.
            3. Use the 'df' variable directly.
            4. Assign the final answer to a variable named result.
        """)

        code_chain = code_prompt | self.coding_llm | StrOutputParser()
        generated_code = await code_chain.ainvoke({
            "schema": self.schema_context,
            "query": query,
            "examples": code_examples,
        })
        generated_code = _normalize_generated_code(generated_code)

        if chart_query:
            try:
                chart_data = await run_in_threadpool(generate_chart, self.df, query, generated_code)
            except ChartGenerationError:
                chart_data = await run_in_threadpool(generate_chart, self.df, query)

            if not chart_data:
                raise RuntimeError("Chart generation failed")

            chart_type = chart_data.get("type", "chart")
            return {
                "answer": f"Generated {chart_type} chart for the requested analysis.",
                "generated_code": generated_code,
                "execution_result": {
                    "status": "success",
                    "raw_output": {"type": "chart", "chart_type": chart_type},
                    "engine": "fast-path-v4",
                },
                "chart_data": chart_data,
            }

        execution_result = await run_in_threadpool(self.executor.execute_with_healing, generated_code)
        if not execution_result.success:
            raise RuntimeError(execution_result.error or "Code execution failed")

        raw_data = execution_result.result or {"type": "unknown", "value": "No data retrieved."}

        scalar_answer = self._format_scalar_answer(raw_data)
        if scalar_answer is not None:
            return {
                "answer": scalar_answer,
                "generated_code": generated_code,
                "execution_result": {
                    "status": "success",
                    "raw_output": raw_data,
                    "engine": "fast-path-v4",
                },
                "chart_data": None,
            }

        summary_prompt = PromptTemplate.from_template("""
            You are a Professional Data Analyst.
            The user asked: "{query}"
            The analysis found: {result}

            Provide a direct, natural language answer. Be precise with numbers.
        """)

        summary_chain = summary_prompt | self.reasoning_llm | StrOutputParser()
        final_answer = await summary_chain.ainvoke({
            "query": query,
            "result": str(raw_data),
        })

        if self._looks_like_reasoning_plan(final_answer):
            final_answer = str(raw_data)

        return {
            "answer": final_answer,
            "generated_code": generated_code,
            "execution_result": {
                "status": "success",
                "raw_output": raw_data,
                "engine": "fast-path-v4",
            },
            "chart_data": None,
        }

    async def _execute_reasoning_path(self, query: str, history: List[Dict]) -> Dict[str, Any]:
        """Run the reasoning manager loop for multi-step questions."""
        react_examples = self.react_store.get_context_string(query, k=1)
        history_text = "".join([f"{msg['role']}: {msg['content']}\n" for msg in history])

        prompt = PromptTemplate.from_template("""
            Context: {schema_context}
            History: {history_text}

            {react_examples}

            Thought: [reasoning]
            Action: [tool_name]
            Action Input: [input]

            OR

            Final Answer: [exact answer based on tools]

            Question: {input}
        """)

        chain = prompt | self.reasoning_llm | StrOutputParser()
        response = await chain.ainvoke({
            "schema_context": self.schema_context,
            "history_text": history_text,
            "react_examples": react_examples,
            "input": query,
        })

        if self._looks_like_reasoning_plan(response):
            logger.info("Reasoning path returned a plan instead of an answer. Falling back to code path.")
            return await self._execute_direct_code_path(query)

        return {
            "answer": response,
            "generated_code": None,
            "execution_result": None,
            "chart_data": None,
        }
    

    async def generate_kpi_report(self) -> Dict[str, Any]:
        """
        Comprehensive KPI report generation using SOLID-principle components.
        Orchestrates DataProfiler, AIAnalysisService, ChartOrchestrator, and ResponseNormalizer.
        
        Returns: KPI dashboard data with metrics, insights, and visual recommendations.
        """
        try:
            # 1. Data Profiling using dedicated component
            profiler = DataProfiler(self.df)
            profile = profiler.profile()

            summary = profiler.get_summary(profile)
            metrics = profiler.get_metrics(profile)
            top_categories = profiler.get_categories(profile)
            date_metrics, date_insights = profiler.get_date_insights() or (None, None)

            # Keep profiling payload JSON-safe by excluding DataFrame objects.
            data_profiling = {
                "total_rows": profile["total_rows"],
                "total_columns": profile["total_columns"],
                "numeric_count": profile["numeric_count"],
                "categorical_count": profile["categorical_count"],
                "missing_count": profile["missing_count"],
                "missing_percent": profile["missing_percent"],
                "numeric_columns": profile["numeric_df"].columns.tolist(),
                "categorical_columns": profile["categorical_df"].columns.tolist(),
            }

            # Append date metrics if available
            if date_metrics:
                metrics.extend(date_metrics)

            # 3. AI-Powered Deep Analysis
            ai_summary = None
            data_quality_insights = None
            analysis_insights_list = None
            key_metrics = [
                f"Total Records: {profile['total_rows']:,}",
                f"Unique Features: {profile['total_columns']}",
                f"Data Completeness: {100 - profile['missing_percent']}%"
            ]
            if top_categories:
                key_metrics.append(f"Top Category: {top_categories[0]['value']}")
            visual_recommendations = None
            chart_data = []  # Initialize as empty list to ensure we always have a list
            try:
                # Run AI analysis
                ai_result = await self.analyze_dataset_kpi()
                ai_summary = ai_result.get("ai_summary")
                data_quality_insights = ai_result.get("data_quality")
                analysis_insights_list = ai_result.get("analysis_insights")
                visual_recommendations = ai_result.get("visual_recommendations")

                # 4. Chart Generation using dedicated orchestrator
                if visual_recommendations:
                    logger.info(f"📊 Starting chart generation for {len(visual_recommendations)} recommendations...")

                    chart_orchestrator = ChartOrchestrator(self.df, tool_factory=self.tool_factory)
                    await chart_orchestrator.generate_charts(visual_recommendations)
                    logger.info("✅ Chart generation complete")

                    # Keep the top-level charts list in sync with the enriched visual recommendations
                    chart_data = [
                        {
                            "title": rec.get("title", "Unknown"),
                            "data": rec.get("chart_data", {})
                        }
                        for rec in visual_recommendations
                        if rec.get("chart_data")
                    ]
                else:   
                    logger.warning("⚠️ No visual recommendations were generated by the AI.")

            except Exception as ai_error:
                logger.error(f"AI analysis error: {ai_error}")
                ai_summary = (
                    "AI-generated KPI insights are temporarily unavailable because the local Ollama model "
                    "could not complete the request. Returning deterministic KPI metrics and fallback charts."
                )
                # Continue with basic KPIs only
                chart_data = []

            # 5. if AI not able to generate charts, create basic ones from the profile (ensures we always return some visual insights)
            if not chart_data:
                chart_data = self._generate_basic_charts(profile)

            # 6. Return Complete KPI Report
            return {
                "summary": summary,
                "data_profiling": data_profiling,
                "metrics": metrics,
                "charts": chart_data,
                "top_categories": top_categories,
                "date_insights": date_insights,
                "data_quality": data_quality_insights,
                "analysis_insights": analysis_insights_list,
                "ai_summary": ai_summary,
                "key_metrics": key_metrics,
                "visual_recommendations": visual_recommendations
            }

        except Exception as e:
            logger.error(f"Error generating KPI report: {str(e)}")
            raise

    async def analyze_dataset_kpi(self) -> Dict[str, Any]:
        """Run AI dataset analysis."""
        safe_fallback_visuals = self._build_fallback_visual_recommendations(limit=15) or self._build_minimum_safe_visual_recommendations(limit=15)

        if self.reasoning_llm is None:
            return {
                "ai_summary": "AI analysis is unavailable because the reasoning model is not initialized.",
                "data_quality": None,
                "analysis_insights": None,
                "visual_recommendations": safe_fallback_visuals,
            }

        visualization_plan = self._build_visualization_plan()
        visualization_plan_text = self._format_visualization_plan_for_prompt(visualization_plan)

        # Include actual column names and types in the prompt
        available_columns = ""
        if self.df is not None:
            numeric_cols = self._get_numeric_analysis_columns()
            categorical_cols = self.df.select_dtypes(include=['object', 'category']).columns.tolist()
            datetime_cols = self._infer_datetime_columns()
            
            # CRITICAL: Strip out IDs and Indexes before they reach the LLM
            numeric_cols = [col for col in numeric_cols if not self._is_identifier_like_column(col)]
            categorical_cols = [col for col in categorical_cols if not self._is_identifier_like_column(col)]
            datetime_cols = [col for col in datetime_cols if not self._is_identifier_like_column(col)]

            available_columns = f"""

        AVAILABLE COLUMNS IN THIS DATASET:
        - Numeric (for Y-axis): {', '.join(numeric_cols) if numeric_cols else 'None'}
        - Categorical (for grouping): {', '.join(categorical_cols) if categorical_cols else 'None'}
        - Date/Time (for X-axis): {', '.join(datetime_cols) if datetime_cols else 'None'}

        CRITICAL: Only use columns listed above. Do NOT suggest visualizations for columns like 'revenue', 'sales', etc. unless they actually appear in the list above.
            """
 
        prompt = PromptTemplate.from_template("""
            You are an Expert Lead Data Scientist and Business Intelligence Strategist.
            Your goal is to provide clear, actionable insights through both text summaries and highly analytical, compound chart generation.

            Dataset Context:
            {schema}{available_columns}

            VISUALIZATION COVERAGE PLAN:
            {visualization_plan}

            ### ADVANCED ANALYTICS DIRECTIVE (CRITICAL) ###
            To generate world-class KPIs, you must mentally classify the dataset into:
            1. TARGET VARIABLES (Outcomes): What are the primary outcomes being measured? (e.g., Price, Profit, Stress_Level, Depression, Stock).
            2. DRIVER VARIABLES (Inputs): What factors influence those outcomes? (e.g., Category, Region, Age, Screen_Time, Smoking).

            Your visualization recommendations MUST explore the relationships between Drivers and Targets. 
            When applicable, COMBINE related driver variables to show compounding effects against a target variable.
            For example:
            - "Show [Target] rates compared across [Driver 1] and [Driver 2]" 
            - "Compare average [Target] by [Driver 1] clustered by [Driver 2]"

            CRITICAL REQUIREMENTS for visual_recommendations:
            - NEVER use IDs, Indexes, Person_ID, or Primary Keys for aggregations or trends.
            - Look for compounding variables: If multiple columns represent similar themes (e.g., 'Alcohol' and 'Smoking', or 'Price' and 'Stock'), combine them in the analysis.
            - suggested_query must be written in natural English that a business user would understand.
            - ONLY use column names that are listed above under AVAILABLE COLUMNS.
            - Every visual_recommendation must be distinct. Do NOT repeat the same metric/category pairing.
            - Focus on insightful queries:
              * "Compare [Target] by [Driver 1] and [Driver 2]" - (Compounding analysis)
              * "Show relationship between [Continuous Driver] and [Target]" - (Scatter/Correlation)
              * "Show top 10 [Categorical] by [Target]" - (Ranking)

            Output a JSON object with keys:
            - ai_summary: Executive summary outlining the relationship between the key drivers and target variables (2-3 sentences).
            - data_quality: Array of data quality issues found, each with metric, status (good/warning/critical), description
            - analysis_insights: Array of business insights, each with title, description, key_findings array, recommendations array
            - visual_recommendations: Array of 10 to 15 unique visualization recommendations, each with:
              * title: Clear, analytical title (e.g., "Compound Impact of Smoking & Alcohol on Anxiety")
              * description: 2-sentence explanation of the analytical/business value.
              * suggested_query: Natural language query using ONLY columns that exist (from AVAILABLE COLUMNS).

            STRICT OUTPUT RULES (MANDATORY):
            - Return ONLY valid JSON (RFC 8259).
            - Do NOT output markdown, headings, bullet lists, code fences, comments, or extra prose.
            - Use only double quotes for keys and strings.
            - Ensure the top-level object includes all keys: ai_summary, data_quality, analysis_insights, visual_recommendations.
            - If unsure, return empty arrays for data_quality / analysis_insights / visual_recommendations, not null.

            REQUIRED JSON SHAPE:
                        {{
                            "ai_summary": "string",
                            "data_quality": [
                                {{"metric": "string", "status": "good|warning|critical", "description": "string"}}
                            ],
                            "analysis_insights": [
                                {{
                                    "title": "string",
                                    "description": "string",
                                    "key_findings": ["string"],
                                    "recommendations": ["string"]
                                }}
                            ],
                            "visual_recommendations": [
                                {{
                                    "title": "string",
                                    "description": "string",
                                    "suggested_query": "string"
                                }}
                            ]
                        }}
            
            Focus on the most impactful, multi-variable visualizations that would drive real-world decision-making.
        """)

        chain = prompt | self.reasoning_llm | StrOutputParser()
        try:
            raw_response = await chain.ainvoke({
                "schema": self.schema_context,
                "available_columns": available_columns,
                "visualization_plan": visualization_plan_text,
            })
        except TimeoutError as timeout_error:
            logger.warning(f"KPI AI analysis timed out: {timeout_error}")
            return {
                "ai_summary": (
                    "The local KPI reasoning model timed out while generating narrative insights. "
                    "Basic KPI metrics and fallback visualizations are still available."
                ),
                "data_quality": None,
                "analysis_insights": None,
                "visual_recommendations": safe_fallback_visuals,
            }
        except ValueError as llm_error:
            logger.warning(f"KPI AI analysis unavailable: {llm_error}")
            return {
                "ai_summary": (
                    "The local KPI reasoning model is currently unavailable. "
                    "Basic KPI metrics and fallback visualizations are still available."
                ),
                "data_quality": None,
                "analysis_insights": None,
                "visual_recommendations": safe_fallback_visuals,
            }

        normalizer = ResponseNormalizer()
        parsed_response = normalizer.parse_json_response(raw_response)
        normalized = normalizer.normalize_analysis_output(parsed_response, self.df)

        ai_visuals = normalized.get("visual_recommendations") or []
        filtered_visuals = self._filter_visual_recommendations(ai_visuals, limit=15)

        if len(filtered_visuals) < 10:
            fallback_visuals = self._build_fallback_visual_recommendations(limit=15) or self._build_minimum_safe_visual_recommendations(limit=15)
            filtered_visuals = self._merge_unique_visual_recommendations(filtered_visuals, fallback_visuals, limit=15)

        if len(filtered_visuals) < 10:
            minimum_visuals = self._build_minimum_safe_visual_recommendations(limit=15)
            filtered_visuals = self._merge_unique_visual_recommendations(filtered_visuals, minimum_visuals, limit=15)

        if filtered_visuals:
            normalized["visual_recommendations"] = filtered_visuals

        if not normalized.get("visual_recommendations"):
            normalized["visual_recommendations"] = safe_fallback_visuals

        return normalized
        # return raw_response
    #TODO Use AI to find the identifirer-like columns, then apply heuristic rules to exclude them from being treated as analytical KPIs. This prevents the common mistake of using ID fields as measures in charts.
    # Using the .is_unique Property
    # Checking for Unique + Non-Null
    # Comparing Unique Count vs. Total Rows
    def _is_identifier_like_column(self, column_name: str) -> bool:
        """Heuristic to detect identifier-like columns that should not drive KPI aggregations."""
        name = str(column_name).strip().lower().replace("-", " ")
        tokens = set(re.findall(r"[a-z0-9]+", name))

        if name.endswith("_id") or name.endswith(" id"):
            return True

        identifier_tokens = {
            "id", "uuid", "guid", "index", "key", "ean", "identifier", "internalid",
        }
        if tokens.intersection(identifier_tokens):
            return True

        compact_name = name.replace(" ", "")
        if "personid" in compact_name or "customerid" in compact_name or "userid" in compact_name:
            return True

        # Fall back to data-shape heuristics when naming is ambiguous.
        if self.df is None or column_name not in self.df.columns:
            return False

        series = self.df[column_name]
        non_null = series.dropna()
        if non_null.empty:
            return False

        total_rows = len(series)
        non_null_count = int(series.notna().sum())
        unique_non_null_count = int(non_null.nunique(dropna=True))
        unique_ratio = unique_non_null_count / max(1, non_null_count)

        # .is_unique + non-null coverage strongly indicates a record key.
        if non_null.is_unique and non_null_count >= max(10, int(total_rows * 0.8)):
            if pd.api.types.is_integer_dtype(non_null) or pd.api.types.is_string_dtype(non_null):
                return True

        # Compare distinct count to row count: near-unique integer columns are likely surrogate keys.
        if unique_ratio >= 0.98 and pd.api.types.is_integer_dtype(non_null):
            return True

        return False

    # TODO: Use AI to get numeric colums
    def _get_numeric_analysis_columns(self) -> List[str]:
        """Return numeric columns that are suitable for KPI analysis (excluding identifier-like fields)."""

        numeric_cols = self.df.select_dtypes(include=['number']).columns.tolist()
        usable_cols: List[str] = []

        for column in numeric_cols:
            if self._is_identifier_like_column(column):
                continue

            series = self.df[column].dropna()
            if series.empty:
                continue

            unique_ratio = series.nunique() / max(1, len(series))
            if unique_ratio >= 0.98 and pd.api.types.is_integer_dtype(series):
                # Near-unique integer columns are usually surrogate keys, not business metrics.
                continue

            usable_cols.append(column)

        return usable_cols

    def _filter_visual_recommendations(
        self,
        recommendations: List[Dict[str, str]],
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Drop low-quality recommendations such as ID-based metrics and invalid trend axes."""
        if not recommendations:
            return []

        identifier_columns = [
            str(column)
            for column in (self.df.columns.tolist() if self.df is not None else [])
            if self._is_identifier_like_column(str(column))
        ]
        datetime_columns = [str(column).lower() for column in self._infer_datetime_columns()]

        filtered: List[Dict[str, str]] = []
        for item in recommendations:
            title = str(item.get("title", ""))
            suggested_query = str(item.get("suggested_query", ""))
            text = f"{title} {suggested_query}".lower()

            # Remove charts where identifier fields are treated like analytical measures.
            if any(identifier.lower() in text for identifier in identifier_columns):
                if "count of records" not in text and "count of" not in text:
                    continue

            # Trend recommendations must reference a datetime-capable axis.
            is_trend_intent = "trend" in text or "over" in text or "across" in text
            if is_trend_intent and "across" in text and datetime_columns:
                if not any(datetime_col in text for datetime_col in datetime_columns):
                    continue

            filtered.append(item)
            if len(filtered) >= limit:
                break

        return filtered

    def _infer_datetime_columns(self, sample_size: int = 50) -> List[str]:
        """Infer datetime-capable columns, including object columns with date-like values."""
        if self.df is None or self.df.empty:
            return []

        datetime_cols = self.df.select_dtypes(include=['datetime64', 'datetime64[ns]']).columns.tolist()
        for column in self.df.columns:
            if column in datetime_cols:
                continue
            if pd.api.types.is_numeric_dtype(self.df[column]):
                continue
            column_name = str(column).lower()
            if not any(token in column_name for token in ['date', 'day', 'month', 'year', 'datetime', 'timestamp']):
                continue
            sample = self.df[column].head(sample_size)
            try:
                parsed = pd.to_datetime(sample, errors='coerce')
            except (TypeError, ValueError):
                continue
            if parsed.notna().sum() >= max(1, int(len(sample) * 0.8)):
                datetime_cols.append(column)

        return datetime_cols

    def _build_visualization_plan(self, analysis_insights: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, str]]:
        """Create deterministic coverage slots for KPI visual recommendations."""
        if self.df is None or self.df.empty:
            return []

        numeric_cols = self._get_numeric_analysis_columns()
        categorical_cols = self.df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = self._infer_datetime_columns()

        categorical_cols = [
            col for col in categorical_cols
            if not self._is_identifier_like_column(col)
        ]

        plan: List[Dict[str, str]] = []
        seen_slots: set[str] = set()
        insight_text = " ".join(
            f"{item.get('title', '')} {item.get('description', '')}"
            for item in (analysis_insights or [])
            if isinstance(item, dict)
        ).lower()

        def label(column: str) -> str:
            return str(column).replace('_', ' ').strip().title()

        def add_slot(slot: str, family: str, title: str, description: str, suggested_query: str, required_columns: List[str]) -> None:
            if slot in seen_slots:
                return
            seen_slots.add(slot)
            plan.append({
                "slot": slot,
                "family": family,
                "title": title,
                "description": description,
                "suggested_query": suggested_query,
                "required_columns": ", ".join(required_columns),
            })

        if categorical_cols and numeric_cols:
            add_slot(
                slot="ranking_primary",
                family="ranking",
                title=f"Top {label(categorical_cols[0])} by {label(numeric_cols[0])}",
                description=(
                    f"Rank the leading {label(categorical_cols[0]).lower()} values by {label(numeric_cols[0]).lower()} to reveal the strongest contributors. "
                    "This is the primary performance view for category-level decisions."
                ),
                suggested_query=f"Show top 10 {categorical_cols[0]} by {numeric_cols[0]}",
                required_columns=[categorical_cols[0], numeric_cols[0]],
            )

        if len(numeric_cols) >= 2:
            relationship_query = (
                f"Show the relationship between {numeric_cols[0]} and {numeric_cols[1]} by {categorical_cols[0]}"
                if categorical_cols else f"Show the relationship between {numeric_cols[0]} and {numeric_cols[1]}"
            )
            relationship_columns = [numeric_cols[0], numeric_cols[1], *categorical_cols[:1]]
            add_slot(
                slot="relationship_primary",
                family="relationship",
                title=(
                    f"{label(numeric_cols[0])} vs {label(numeric_cols[1])} by {label(categorical_cols[0])}"
                    if categorical_cols else f"{label(numeric_cols[0])} vs {label(numeric_cols[1])}"
                ),
                description=(
                    f"Compare {label(numeric_cols[0]).lower()} and {label(numeric_cols[1]).lower()} to expose tradeoffs, clusters, or outliers. "
                    "This is the main relationship view for operational insights."
                ),
                suggested_query=relationship_query,
                required_columns=relationship_columns,
            )

        if datetime_cols and numeric_cols:
            add_slot(
                slot="trend_primary",
                family="trend",
                title=f"{label(numeric_cols[0])} Trend Over {label(datetime_cols[0])}",
                description=(
                    f"Track how {label(numeric_cols[0]).lower()} changes over {label(datetime_cols[0]).lower()} to identify timing effects and trend shifts. "
                    "This is the core time-based view when a date axis exists."
                ),
                suggested_query=f"Compare {numeric_cols[0]} across {datetime_cols[0]}",
                required_columns=[datetime_cols[0], numeric_cols[0]],
            )

        if numeric_cols:
            add_slot(
                slot="distribution_primary",
                family="distribution",
                title=f"Distribution of {label(numeric_cols[0])}",
                description=(
                    f"Inspect the spread of {label(numeric_cols[0]).lower()} values to identify skew, concentration, and unusual values. "
                    "This is the primary distribution view for data quality and variability."
                ),
                suggested_query=f"Display distribution of {numeric_cols[0]}",
                required_columns=[numeric_cols[0]],
            )

        if len(categorical_cols) >= 2 and numeric_cols:
            add_slot(
                slot="secondary_breakdown",
                family="breakdown",
                title=f"{label(numeric_cols[0])} by {label(categorical_cols[1])}",
                description=(
                    f"Break down {label(numeric_cols[0]).lower()} by {label(categorical_cols[1]).lower()} to reveal secondary segmentation patterns. "
                    "This adds a second business lens beyond the primary category ranking."
                ),
                suggested_query=f"Show {numeric_cols[0]} by {categorical_cols[1]}",
                required_columns=[categorical_cols[1], numeric_cols[0]],
            )
        elif categorical_cols:
            add_slot(
                slot="breakdown_counts",
                family="breakdown",
                title=f"Record Count by {label(categorical_cols[0])}",
                description=(
                    f"Count records by {label(categorical_cols[0]).lower()} to understand category concentration and coverage. "
                    "This helps assess composition when a secondary breakdown is unavailable."
                ),
                suggested_query=f"Show count of records by {categorical_cols[0]}",
                required_columns=[categorical_cols[0]],
            )

        # Add more deterministic slots so fallback can satisfy 10-15 recommendations.
        if len(categorical_cols) >= 2 and len(numeric_cols) >= 2:
            add_slot(
                slot="ranking_secondary",
                family="ranking",
                title=f"Top {label(categorical_cols[1])} by {label(numeric_cols[1])}",
                description=(
                    f"Rank {label(categorical_cols[1]).lower()} values by {label(numeric_cols[1]).lower()} to identify a second priority leaderboard. "
                    "This complements the primary ranking with a different KPI lens."
                ),
                suggested_query=f"Show top 10 {categorical_cols[1]} by {numeric_cols[1]}",
                required_columns=[categorical_cols[1], numeric_cols[1]],
            )

        if len(numeric_cols) >= 3:
            relationship_query = (
                f"Show the relationship between {numeric_cols[0]} and {numeric_cols[2]} by {categorical_cols[0]}"
                if categorical_cols else f"Show the relationship between {numeric_cols[0]} and {numeric_cols[2]}"
            )
            add_slot(
                slot="relationship_secondary",
                family="relationship",
                title=(
                    f"{label(numeric_cols[0])} vs {label(numeric_cols[2])} by {label(categorical_cols[0])}"
                    if categorical_cols else f"{label(numeric_cols[0])} vs {label(numeric_cols[2])}"
                ),
                description=(
                    f"Analyze how {label(numeric_cols[0]).lower()} and {label(numeric_cols[2]).lower()} interact to expose non-obvious clusters. "
                    "This gives a secondary correlation view for strategy decisions."
                ),
                suggested_query=relationship_query,
                required_columns=[numeric_cols[0], numeric_cols[2], *categorical_cols[:1]],
            )

        if len(numeric_cols) >= 2:
            add_slot(
                slot="distribution_secondary",
                family="distribution",
                title=f"Distribution of {label(numeric_cols[1])}",
                description=(
                    f"Inspect the spread of {label(numeric_cols[1]).lower()} to validate consistency and outlier behavior. "
                    "This adds a second quality check beyond the primary metric distribution."
                ),
                suggested_query=f"Display distribution of {numeric_cols[1]}",
                required_columns=[numeric_cols[1]],
            )

        if datetime_cols and len(numeric_cols) >= 2:
            add_slot(
                slot="trend_secondary",
                family="trend",
                title=f"{label(numeric_cols[1])} Trend Over {label(datetime_cols[0])}",
                description=(
                    f"Track {label(numeric_cols[1]).lower()} over {label(datetime_cols[0]).lower()} to confirm trend consistency across KPIs. "
                    "This complements the primary trend line with a second time-series metric."
                ),
                suggested_query=f"Compare {numeric_cols[1]} across {datetime_cols[0]}",
                required_columns=[datetime_cols[0], numeric_cols[1]],
            )

        if len(categorical_cols) >= 2 and numeric_cols:
            add_slot(
                slot="compound_breakdown",
                family="breakdown",
                title=f"{label(numeric_cols[0])} by {label(categorical_cols[0])} and {label(categorical_cols[1])}",
                description=(
                    f"Compare {label(numeric_cols[0]).lower()} across combined {label(categorical_cols[0]).lower()} and {label(categorical_cols[1]).lower()} segments. "
                    "This reveals compounding effects across two categorical drivers."
                ),
                suggested_query=f"Compare {numeric_cols[0]} by {categorical_cols[0]} and {categorical_cols[1]}",
                required_columns=[numeric_cols[0], categorical_cols[0], categorical_cols[1]],
            )

        if len(categorical_cols) >= 3 and numeric_cols:
            add_slot(
                slot="tertiary_breakdown",
                family="breakdown",
                title=f"{label(numeric_cols[0])} by {label(categorical_cols[2])}",
                description=(
                    f"Break down {label(numeric_cols[0]).lower()} by {label(categorical_cols[2]).lower()} to expand segmentation coverage. "
                    "This adds another angle for stakeholder comparison."
                ),
                suggested_query=f"Show {numeric_cols[0]} by {categorical_cols[2]}",
                required_columns=[numeric_cols[0], categorical_cols[2]],
            )

        if len(numeric_cols) >= 3:
            add_slot(
                slot="compound_numeric",
                family="relationship",
                title=f"Combined Effect of {label(numeric_cols[1])} and {label(numeric_cols[2])} on {label(numeric_cols[0])}",
                description=(
                    f"Assess how {label(numeric_cols[1]).lower()} and {label(numeric_cols[2]).lower()} jointly relate to {label(numeric_cols[0]).lower()}. "
                    "This is a compounding-driver view for multi-factor analysis."
                ),
                suggested_query=f"Compare {numeric_cols[0]} by {numeric_cols[1]} and {numeric_cols[2]}",
                required_columns=[numeric_cols[0], numeric_cols[1], numeric_cols[2]],
            )

        if categorical_cols and len(numeric_cols) >= 2:
            add_slot(
                slot="metric_comparison_by_category",
                family="comparison",
                title=f"{label(numeric_cols[0])} vs {label(numeric_cols[1])} by {label(categorical_cols[0])}",
                description=(
                    f"Compare {label(numeric_cols[0]).lower()} and {label(numeric_cols[1]).lower()} across {label(categorical_cols[0]).lower()} groups. "
                    "This highlights category-level tradeoffs between two KPIs."
                ),
                suggested_query=f"Compare average {numeric_cols[0]} and {numeric_cols[1]} by {categorical_cols[0]}",
                required_columns=[categorical_cols[0], numeric_cols[0], numeric_cols[1]],
            )

        if len(categorical_cols) >= 2:
            add_slot(
                slot="segment_size_matrix",
                family="distribution",
                title=f"Record Count by {label(categorical_cols[0])} and {label(categorical_cols[1])}",
                description=(
                    f"Quantify how records are distributed across {label(categorical_cols[0]).lower()} and {label(categorical_cols[1]).lower()} combinations. "
                    "This is useful for identifying dominant and underrepresented segments."
                ),
                suggested_query=f"Show count of records by {categorical_cols[0]} and {categorical_cols[1]}",
                required_columns=[categorical_cols[0], categorical_cols[1]],
            )

        if insight_text:
            def score(item: Dict[str, str]) -> tuple[int, str]:
                score_value = 0
                if item["family"] in insight_text:
                    score_value += 2
                for required in item["required_columns"].split(", "):
                    if required and required.lower() in insight_text:
                        score_value += 1
                return (-score_value, item["slot"])

            plan.sort(key=score)

        return plan

    def _format_visualization_plan_for_prompt(self, plan: List[Dict[str, str]]) -> str:
        """Format visualization slots for the KPI reasoning prompt."""
        if not plan:
            return "No deterministic visualization slots are available for this dataset."

        return "\n".join(
            [
                f"- Slot: {item['slot']} | Family: {item['family']} | Columns: {item['required_columns']}\n"
                f"  Title Hint: {item['title']}\n"
                f"  Business Goal: {item['description']}\n"
                f"  Suggested Query Seed: {item['suggested_query']}"
                for item in plan
            ]
        )

    def _merge_unique_visual_recommendations(
        self,
        primary: List[Dict[str, str]],
        fallback: List[Dict[str, str]],
        limit: int = 15,
    ) -> List[Dict[str, str]]:
        """Merge AI and fallback recommendations while keeping the final set unique."""
        merged: List[Dict[str, str]] = []
        seen_signatures: set[tuple[str, tuple[str, ...]]] = set()

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

        for item in [*primary, *fallback]:
            title = item.get("title", "Visualization")
            suggested_query = item.get("suggested_query", "")
            signature = build_signature(title, suggested_query)
            if not suggested_query or signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            merged.append(item)
            if len(merged) >= limit:
                break

        return merged

    def _build_fallback_visual_recommendations(
        self,
        analysis_insights: Optional[List[Dict[str, Any]]] = None,
        limit: int = 15,
    ) -> Optional[List[Dict[str, str]]]:
        """Create deterministic chart recommendations from the visualization coverage plan."""
        plan = self._build_visualization_plan(analysis_insights)
        if not plan:
            return None
        return [
            {
                "title": item["title"],
                "description": item["description"],
                "suggested_query": item["suggested_query"],
            }
            for item in plan[:limit]
        ] or None

    def _build_minimum_safe_visual_recommendations(self, limit: int = 15) -> List[Dict[str, str]]:
        """Build a minimal, always-safe recommendation set to avoid returning null results."""
        if self.df is None or self.df.empty:
            return []

        def label(column: str) -> str:
            return str(column).replace('_', ' ').strip().title()

        numeric_cols = self._get_numeric_analysis_columns()
        categorical_cols = [
            col for col in self.df.select_dtypes(include=['object', 'category']).columns.tolist()
            if not self._is_identifier_like_column(col)
        ]

        recommendations: List[Dict[str, str]] = []

        if categorical_cols:
            recommendations.append({
                "title": f"Record Count by {label(categorical_cols[0])}",
                "description": (
                    f"Count records by {label(categorical_cols[0]).lower()} to understand dataset composition and concentration."
                ),
                "suggested_query": f"Show count of records by {categorical_cols[0]}",
            })

        if len(categorical_cols) >= 2:
            recommendations.append({
                "title": f"Record Count by {label(categorical_cols[1])}",
                "description": (
                    f"Compare record counts across {label(categorical_cols[1]).lower()} groups to identify concentration patterns."
                ),
                "suggested_query": f"Show count of records by {categorical_cols[1]}",
            })

        if numeric_cols:
            recommendations.append({
                "title": f"Distribution of {label(numeric_cols[0])}",
                "description": (
                    f"Inspect the spread of {label(numeric_cols[0]).lower()} values to identify variability and unusual observations."
                ),
                "suggested_query": f"Display distribution of {numeric_cols[0]}",
            })

        if len(numeric_cols) >= 2:
            recommendations.append({
                "title": f"Relationship Between {label(numeric_cols[0])} and {label(numeric_cols[1])}",
                "description": (
                    f"Analyze how {label(numeric_cols[0]).lower()} and {label(numeric_cols[1]).lower()} move together to find correlation or tradeoffs."
                ),
                "suggested_query": f"Show relationship between {numeric_cols[0]} and {numeric_cols[1]}",
            })

        if numeric_cols and categorical_cols:
            recommendations.append({
                "title": f"Average {label(numeric_cols[0])} by {label(categorical_cols[0])}",
                "description": (
                    f"Compare average {label(numeric_cols[0]).lower()} across {label(categorical_cols[0]).lower()} groups for a quick segmented view."
                ),
                "suggested_query": f"Show average {numeric_cols[0]} by {categorical_cols[0]}",
            })

        if len(numeric_cols) >= 2 and categorical_cols:
            recommendations.append({
                "title": f"Average {label(numeric_cols[1])} by {label(categorical_cols[0])}",
                "description": (
                    f"Compare average {label(numeric_cols[1]).lower()} across {label(categorical_cols[0]).lower()} groups for a second KPI lens."
                ),
                "suggested_query": f"Show average {numeric_cols[1]} by {categorical_cols[0]}",
            })

        if self._infer_datetime_columns() and numeric_cols:
            dt_col = self._infer_datetime_columns()[0]
            recommendations.append({
                "title": f"Trend of {label(numeric_cols[0])} Over {label(dt_col)}",
                "description": (
                    f"Track {label(numeric_cols[0]).lower()} over {label(dt_col).lower()} to surface trend shifts."
                ),
                "suggested_query": f"Compare {numeric_cols[0]} across {dt_col}",
            })

        return recommendations[:limit]

    def _generate_basic_charts(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate basic fallback charts when AI charts aren't available."""
        chart_data = []

        if profile["numeric_count"]:
            numeric_summary = profile["numeric_df"].agg(['min', 'mean', 'max']).transpose().reset_index()
            top_metrics = numeric_summary.sort_values(by='mean', ascending=False).head(3)

            chart_data.append({
                "title": "Numeric KPI Overview",
                "data": {
                    "data": [
                        {
                            "type": "bar",
                            "x": top_metrics['index'].tolist(),
                            "y": top_metrics['mean'].round(2).tolist(),
                            "marker": {"color": ["#2563eb", "#9333ea", "#0f766e"]}
                        }
                    ],
                    "layout": {
                        "title": "Top numeric column averages",
                        "xaxis": {"title": "Column"},
                        "yaxis": {"title": "Average value"},
                        "margin": {"t": 40, "b": 40, "l": 40, "r": 20}
                    }
                }
            })

        return chart_data


if __name__ == "__main__":
    logger.info("DataAnalystAgent module loaded. Use app entrypoints to run analysis workflows.")