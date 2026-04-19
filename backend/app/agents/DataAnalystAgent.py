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
from app.agents.AgentGlobals import AgentGlobals
from app.agents.analysis_components import (
    DataProfiler,
    ResponseNormalizer,
    ChartOrchestrator,
)
from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory
from app.agents.utility.CodeGenerationService import CodeGenerationService
logger = get_production_logger("ai_da.brain_v4")

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
        
        if self.reasoning_llm is None or self.coding_llm is None:
            raise RuntimeError(
                "LLM resources are not available. Check AgentGlobals.initialize() and model configuration."
            )

        self.data_passport = generate_data_passport(df, max_sample_rows=3)
        # Pre-cache the context to avoid repeated processing [cite: 12, 18]
        self.schema_context = self.data_passport.to_prompt_context()
        self.executor = SelfHealingExecutor(df=df, max_retries=3)
        # 4. Wire up the Code Generation Service
        self.code_service = CodeGenerationService(
            coding_llm=self.coding_llm,
            example_store=self.example_store,
            visualization_store=self.visualization_store,
            df=df,
            executor=self.executor
        )
            # 2. Generate Request-Specific Data Context
        print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
        self.data_passport = generate_data_passport(df, max_sample_rows=3)
        self.tool_factory = AnalysisToolFactory(
        data_passport=self.data_passport,
        code_service=self.code_service,
        df=df
        )

    async def _is_direct_calculation(self, query: str) -> bool:
        """
        Heuristic-based router to bypass the ReAct manager for standard tasks.
        """
        keywords = ["median", "average", "sum", "plot", "chart", "mean", "min", "max", "count"]
        return any(k in query.lower() for k in keywords)

    async def analyze(self, query : str, history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point that routes between 'Fast-Path' and 'Reasoning-Path'.
        """
        history = history or []
        
        # 1. INTENT ROUTING: Slash latency by detecting direct data tasks
        calc_keywords = ["median", "average", "sum", "mean", "plot", "max", "min", "count", "exact"]
        if any(k in query.lower() for k in calc_keywords):
            logger.info(f"⚡ Fast-Path: Routing direct to Coding LLM for query: '{query}'")
            return await self._execute_direct_code_path(query)
        
        logger.info(f"🧠 ReAct-Path: Routing to Reasoning Manager for query: '{query}'")
        return await self._execute_reasoning_path(query, history)

    async def _execute_direct_code_path(self, query: str) -> Dict[str, Any]:
        """
        Generates code, executes it, and summarizes the actual data for the user.
        """
        # A. RETRIEVE EXAMPLES [cite: 8, 11]
        code_examples = self.example_store.get_context_string(query, k=2)
        
        # B. GENERATE CODE (DeepSeek) [cite: 6]
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
        """)
        
        code_chain = code_prompt | self.coding_llm | StrOutputParser()
        generated_code = await code_chain.ainvoke({
            "schema": self.schema_context,
            "query": query,
            "examples": code_examples
        })
        # C. EXECUTE CODE (Self-Healing Executor) [cite: 10, 37]
        # Using run_in_threadpool to keep the executor from blocking the event loop
        execution_result = await run_in_threadpool(self.executor.execute_with_healing, generated_code)
        raw_data = execution_result.get("output", "No data retrieved.")

        # D. SUMMARIZE DATA (Llama 3.1) [cite: 6]
        # This replaces generic confirmations with the actual numerical/data answer
        summary_prompt = PromptTemplate.from_template("""
            You are a Professional Data Analyst. 
            The user asked: "{query}"
            The analysis found: {result}
            
            Provide a direct, natural language answer. Be precise with numbers.
        """)
        
        summary_chain = summary_prompt | self.reasoning_llm | StrOutputParser()
        final_answer = await summary_chain.ainvoke({
            "query": query,
            "result": str(raw_data)
        })

        # E. PREDICATED RETURN: Strictly matches ChatResponse dict schema 
        return {
            "answer": final_answer,
            "generated_code": generated_code,
            "execution_result": {
                "status": "success",
                "raw_output": raw_data,
                "engine": "fast-path-v4"
            },
            "chart_data": execution_result.get("chart_data")
        }

    async def _execute_reasoning_path(self, query: str, history: List[Dict]) -> Dict[str, Any]:
        """
        Standard ReAct loop for complex multi-step analysis [cite: 19-28].
        """
        react_examples = self.react_store.get_context_string(query, k=1)
        history_text = "".join([f"{msg['role']}: {msg['content']}\n" for msg in history])
        
        # Refined ReAct Prompt removing problematic markdown [cite: 25, 32]
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
            "input": query
        })
        
        return {
            "answer": response,
            "generated_code": None,
            "execution_result": {"status": "reasoning_complete"},
            "chart_data": None
        }

    async def analyze_dataset(self) -> Dict[str, Any]:
        """
        Run a structured dataset understanding chain for KPI and visualization planning.
        Delegates to AIAnalysisService and ResponseNormalizer for clean separation of concerns.
        """
        ai_service = AIAnalysisService(self.reasoning_llm, self.schema_context, self.df)
        raw_response = await ai_service.analyze_dataset()

        # Normalize the AI response
        normalizer = ResponseNormalizer()
        parsed = normalizer.parse_json_response(raw_response)
        normalized = normalizer.normalize_analysis_output(parsed, self.df)

        # Log the generated visual recommendations for debugging
        if normalized.get("visual_recommendations"):
            logger.info(f"Generated {len(normalized['visual_recommendations'])} visual recommendations:")
            for i, rec in enumerate(normalized["visual_recommendations"]):
                logger.info(f"  {i+1}. {rec['title']}: {rec['suggested_query']}")

        return normalized

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
        if self.reasoning_llm is None:
            return {
                "ai_summary": "AI analysis is unavailable because the reasoning model is not initialized.",
                "data_quality": None,
                "analysis_insights": None,
                "visual_recommendations": None,
            }

        # Include actual column names and types in the prompt
        available_columns = ""
        if self.df is not None:
            numeric_cols = self.df.select_dtypes(include=['number']).columns.tolist()
            categorical_cols = self.df.select_dtypes(include=['object', 'category']).columns.tolist()
            datetime_cols = self.df.select_dtypes(include=['datetime64']).columns.tolist()
            available_columns = f"""

        AVAILABLE COLUMNS IN THIS DATASET:
        - Numeric (for Y-axis): {', '.join(numeric_cols) if numeric_cols else 'None'}
        - Categorical (for grouping): {', '.join(categorical_cols) if categorical_cols else 'None'}
        - Date/Time (for X-axis): {', '.join(datetime_cols) if datetime_cols else 'None'}

        CRITICAL: Only use columns listed above. Do NOT suggest visualizations for columns like 'revenue', 'sales', etc. unless they actually appear in the list above.
            """

        prompt = PromptTemplate.from_template("""
            You are an expert data analyst creating business intelligence dashboards for executives and managers with no technical background.
            Your goal is to provide clear, actionable insights through both text summaries and automated chart generation.

            Dataset Context:
            {schema}{available_columns}

            CRITICAL REQUIREMENTS for visual_recommendations:
            - Each visualization must have a clear business purpose
            - suggested_query must be written in natural English that a business user would understand
            - ONLY use column names that are listed above under AVAILABLE COLUMNS
            - Every visual_recommendation must be distinct. Do NOT repeat the same metric/category pairing, chart intent, or suggested_query with different wording.
            - The recommendations must cover different analytical angles when possible: ranking, relationship, distribution, trend, and secondary breakdown.
            - Prefer top-5 or top-10 ranked category charts instead of showing every category when the dataset has many categories
            - For "distribution by category" KPIs, prefer a sorted horizontal bar chart over a pie chart or unsorted vertical bars
            - Focus on queries that will generate meaningful charts using actual columns:
              * "Show [metric] by [category]" - ONLY if both columns exist
              * "Compare [metric] across [time]" - ONLY if both exist
              * "Display distribution of [column]" - ONLY if column exists
              * "Show relationship between [col1] and [col2]" - ONLY if both exist
              * "Show top items by [metric]" - ONLY if columns exist

            Output a JSON object with keys:
            - ai_summary: Executive summary in plain business language (2-3 sentences)
            - data_quality: Array of data quality issues found, each with metric, status (good/warning/critical), description
            - analysis_insights: Array of business insights, each with title, description, key_findings array, recommendations array
            - visual_recommendations: Array of 3 to 5 unique visualization recommendations, each with:
              * title: Clear, business-friendly title
              * description: 2-sentence explanation of business value
              * suggested_query: Natural language query using ONLY columns that exist (from AVAILABLE COLUMNS)

            Focus on the most impactful visualizations that would help business decision-making.
        """)

        chain = prompt | self.reasoning_llm | StrOutputParser()
        try:
            raw_response = await chain.ainvoke({"schema": self.schema_context, "available_columns": available_columns})
        except TimeoutError as timeout_error:
            logger.warning(f"KPI AI analysis timed out: {timeout_error}")
            return {
                "ai_summary": (
                    "The local KPI reasoning model timed out while generating narrative insights. "
                    "Basic KPI metrics and fallback visualizations are still available."
                ),
                "data_quality": None,
                "analysis_insights": None,
                "visual_recommendations": None,
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
                "visual_recommendations": None,
            }

        normalizer = ResponseNormalizer()
        parsed = normalizer.parse_json_response(raw_response)
        normalized = normalizer.normalize_analysis_output(parsed, self.df)

        fallback_visuals = self._build_fallback_visual_recommendations() or []
        normalized_visuals = normalized.get("visual_recommendations") or []

        if normalized_visuals:
            normalized["visual_recommendations"] = self._merge_unique_visual_recommendations(
                normalized_visuals,
                fallback_visuals,
                limit=5,
            )
        else:
            normalized["visual_recommendations"] = fallback_visuals or None
            if normalized["visual_recommendations"]:
                logger.info(
                    "AI response did not include usable visual_recommendations; generated %s deterministic fallback recommendations",
                    len(normalized["visual_recommendations"]),
                )

        if normalized.get("visual_recommendations"):
            logger.info(f"Generated {len(normalized['visual_recommendations'])} KPI visual recommendations")

        return normalized

    def _merge_unique_visual_recommendations(
        self,
        primary: List[Dict[str, str]],
        fallback: List[Dict[str, str]],
        limit: int = 5,
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

    def _build_fallback_visual_recommendations(self) -> Optional[List[Dict[str, str]]]:
        """Create deterministic chart recommendations when the LLM omits them."""
        if self.df is None or self.df.empty:
            return None

        numeric_cols = self.df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = self.df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = self.df.select_dtypes(include=['datetime64', 'datetime64[ns]']).columns.tolist()

        recommendations: List[Dict[str, str]] = []
        seen_queries: set[str] = set()

        def label(column: str) -> str:
            return str(column).replace('_', ' ').strip().title()

        def add_recommendation(title: str, description: str, suggested_query: str) -> None:
            if suggested_query in seen_queries:
                return
            seen_queries.add(suggested_query)
            recommendations.append({
                "title": title,
                "description": description,
                "suggested_query": suggested_query,
            })

        if categorical_cols and numeric_cols:
            add_recommendation(
                title=f"Top {label(categorical_cols[0])} by {label(numeric_cols[0])}",
                description=(
                    f"This view ranks the leading {label(categorical_cols[0]).lower()} values by {label(numeric_cols[0]).lower()}. "
                    "It helps identify which groups contribute the most and should be monitored first."
                ),
                suggested_query=f"Show top 10 {categorical_cols[0]} by {numeric_cols[0]}"
            )

        if len(numeric_cols) >= 2 and categorical_cols:
            add_recommendation(
                title=f"{label(numeric_cols[0])} vs {label(numeric_cols[1])} by {label(categorical_cols[0])}",
                description=(
                    f"This chart compares {label(numeric_cols[0]).lower()} and {label(numeric_cols[1]).lower()} across {label(categorical_cols[0]).lower()} values. "
                    "It helps surface category-level tradeoffs and outliers."
                ),
                suggested_query=f"Show the relationship between {numeric_cols[0]} and {numeric_cols[1]} by {categorical_cols[0]}"
            )

        if datetime_cols and numeric_cols:
            add_recommendation(
                title=f"{label(numeric_cols[0])} Trend Over {label(datetime_cols[0])}",
                description=(
                    f"This trend view shows how {label(numeric_cols[0]).lower()} changes over {label(datetime_cols[0]).lower()}. "
                    "It helps identify movement over time and timing effects."
                ),
                suggested_query=f"Compare {numeric_cols[0]} across {datetime_cols[0]}"
            )

        if numeric_cols:
            add_recommendation(
                title=f"Distribution of {label(numeric_cols[0])}",
                description=(
                    f"This distribution view shows how {label(numeric_cols[0]).lower()} values are spread across the dataset. "
                    "It helps spot skew, concentration, and unusual values."
                ),
                suggested_query=f"Display distribution of {numeric_cols[0]}"
            )

        if len(categorical_cols) >= 2 and numeric_cols:
            add_recommendation(
                title=f"{label(numeric_cols[0])} by {label(categorical_cols[1])}",
                description=(
                    f"This comparison breaks down {label(numeric_cols[0]).lower()} by {label(categorical_cols[1]).lower()}. "
                    "It helps identify secondary grouping patterns that may be hidden in the overall totals."
                ),
                suggested_query=f"Show {numeric_cols[0]} by {categorical_cols[1]}"
            )

        return recommendations[:5] or None


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
    import asyncio
    import plotly.graph_objects as go
    from app.utils.chart_generator import generate_chart

    # --- AI & Vector DB Initialization ---
    try:
        # This will load your LLMs and build the FAISS index in memory
        AgentGlobals.initialize()
        # app.state.code_learning = AgentGlobals.learn_code_4r_feedback
        # app.state.react_learning = AgentGlobals.learn_react_4r_feedback
        # app.state.vector_database_connection = True
        logger.info("✅ AI Globals and Vector DB initialized successfully.")
    except Exception as e:
        # app.state.vector_database_connection = False
        # 2. FIX: Updated logger message so you know exactly what failed
        logger.error("❌ AI & Vector DB initialization failed during startup: %s", e)
        

    async def run_test():
        # 1. Load the data
        df_test = pd.read_csv('/Users/rwk3030/Downloads/products-100.csv')
        
        # 2. Initialize the agent
        agent = DataAnalystAgent(df_test)
        
        print("⏳ Generating KPI Report... please wait.")
        
        # 3. AWAIT the async function to get the actual dictionary
        report = await agent.generate_kpi_report()
        print("KPI Report Generated:")
        print(json.dumps(report, indent=2))
        # 4. Safely extract the visual recommendations (using the correct key name)
        recommendations = report.get("visual_recommendations", [])
        
        if recommendations and len(recommendations) > 0:
            chart = recommendations[0].get("chart_data")
            if chart:
                print("✅ Chart generated successfully! Opening browser...")
                fig = go.Figure(chart['data'])
                fig.show()
            else:
                print("⚠️ First recommendation did not contain 'chart_data'.")
        else:
            print("⚠️ No visual recommendations were generated by the AI.")
    async def code_gen():
        df_test = pd.read_csv('/Users/rwk3030/Downloads/products-100.csv')
        agent = DataAnalystAgent(df_test)
        code_result = agent.code_service.generate_and_execute("This bar chart will help us visualize the distribution of customers across different countries, allowing us to identify potential markets and areas for growth.")
        print("Generated Code:")
        print(code_result.get("code"))
        print("Execution Result:")
        print(code_result.get("result"))

        chart_data = generate_chart(df_test, code_result.get("code"))
        logger.info("✅ Chart generation complete")
        
        if chart_data:
            fig = go.Figure(chart_data["data"])
            fig.show()

        
    # 5. Execute the async loop
    # asyncio.run(run_test())
    asyncio.run(code_gen())