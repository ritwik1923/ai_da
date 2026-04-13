import traceback
import os
import sys
import json
import re
import pandas as pd
import asyncio
import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from starlette.concurrency import run_in_threadpool
from app.utils.logger import get_production_logger
from app.utils.self_healing_executor import SelfHealingExecutor
from app.utils.data_passport import generate_data_passport
from app.agents.AgentGlobals import AgentGlobals
from app.agents.analysis_components import (
    DataProfiler,
    ResponseNormalizer,
    AIAnalysisService,
    ChartOrchestrator,
)
from app.agents.utility import CodeGenerationService

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
        react_store = None

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
        
        if self.reasoning_llm is None or self.coding_llm is None:
            raise RuntimeError(
                "LLM resources are not available. Check AgentGlobals.initialize() and model configuration."
            )

        self.data_passport = generate_data_passport(df, max_sample_rows=3)
        # Pre-cache the context to avoid repeated processing [cite: 12, 18]
        self.schema_context = self.data_passport.to_prompt_context()
        self.executor = SelfHealingExecutor(df=df, max_retries=3)


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
            key_metrics = None
            visual_recommendations = None
            chart_data = []  # Initialize as empty list to ensure we always have a list
            try:
                # Run AI analysis
                ai_result = await self.analyze_dataset()
                ai_summary = ai_result.get("ai_summary")
                data_quality_insights = ai_result.get("data_quality")
                analysis_insights_list = ai_result.get("analysis_insights")
                visual_recommendations = ai_result.get("visual_recommendations")

                # Build key metrics
                key_metrics = [
                    f"Total Records: {profile['total_rows']:,}",
                    f"Unique Features: {profile['total_columns']}",
                    f"Data Completeness: {100 - profile['missing_percent']}%"
                ]
                if top_categories:
                    key_metrics.append(f"Top Category: {top_categories[0]['value']}")

                # 4. Chart Generation using dedicated orchestrator
                if visual_recommendations:
                    logger.info(f"📊 Starting chart generation for {len(visual_recommendations)} recommendations...")
                    chart_orchestrator = ChartOrchestrator(self.df)
                    await chart_orchestrator.generate_charts(visual_recommendations)
                    logger.info(f"✅ Chart generation complete")
                    
                    # Extract charts from visual recommendations
                    chart_data = [
                        {
                            "title": rec.get("title", "Unknown"),
                            "data": rec.get("chart_data", {})
                        }
                        for rec in visual_recommendations
                        if rec.get("chart_data")
                    ]

            except Exception as ai_error:
                logger.error(f"AI analysis error: {ai_error}")
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
