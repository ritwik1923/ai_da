import traceback
import os
import sys
import re
import pandas as pd
import asyncio
import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from starlette.concurrency import run_in_threadpool
# from backend.app.utils.data_passport import generate_data_passport
# Using production-grade structural logging
try:
    from app.utils.chart_generator import generate_chart, ChartGenerationError
    from app.utils.logger import get_production_logger
    from app.utils.self_healing_executor import SelfHealingExecutor
    from app.utils.data_passport import generate_data_passport
except ImportError:  # pragma: no cover
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from utils.chart_generator import generate_chart, ChartGenerationError
    from utils.logger import get_production_logger 
    from utils.self_healing_executor import SelfHealingExecutor
    from utils.data_passport import generate_data_passport
logger = get_production_logger("ai_da.brain_v4")

from .utility.AgentGlobals import AgentGlobals
# backend/app/agents/utility/DataAnalystAgent.py


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
        reasoning_llm=None,
        coding_llm=None,
        example_store=None,
        react_store=None

    ):
        if not AgentGlobals._initialized:
            AgentGlobals.initialize()

        self.df = df
        self.reasoning_llm = reasoning_llm or AgentGlobals.reasoning_llm
        self.coding_llm = coding_llm or AgentGlobals.coding_llm
        self.example_store = example_store or AgentGlobals.example_store
        self.react_store = react_store or AgentGlobals.react_example_store

        if not all([self.reasoning_llm, self.coding_llm, self.example_store, self.react_store]):
            raise RuntimeError("AgentGlobals failed to initialize required AI resources")
        
        self.data_passport = generate_data_passport(df, max_sample_rows=3)
        # Pre-cache the context to avoid repeated processing [cite: 12, 18]
        self.schema_context = self.data_passport.to_prompt_context()
        self.executor = SelfHealingExecutor(df=df, max_retries=3)

    def _should_use_code_path(self, query: str) -> bool:
        normalized_query = query.lower().strip()
        direct_keywords = {
            "median", "average", "avg", "sum", "mean", "plot", "chart", "max",
            "min", "count", "exact", "top", "bottom", "highest", "lowest", "largest",
            "smallest", "rank", "ranking", "revenue", "sales", "profit", "total"
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
            "bar", "line", "histogram", "pie", "trend"
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


    async def analyze(self, query : str, history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point that routes between 'Fast-Path' and 'Reasoning-Path'.
        """
        history = history or []
        
        # 1. INTENT ROUTING: Slash latency by detecting direct data tasks
        if self._should_use_code_path(query):
            logger.info(f"⚡ Fast-Path: Routing direct to Coding LLM for query: '{query}'")
            return await self._execute_direct_code_path(query)
        
        logger.info(f"🧠 ReAct-Path: Routing to Reasoning Manager for query: '{query}'")
        return await self._execute_reasoning_path(query, history)

    async def _execute_direct_code_path(self, query: str) -> Dict[str, Any]:
        """
        Generates code, executes it, and summarizes the actual data for the user.
        """
        chart_query = self._is_chart_query(query)
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
            4. Assign the final answer to a variable named result.
        """)
        
        code_chain = code_prompt | self.coding_llm | StrOutputParser()
        generated_code = await code_chain.ainvoke({
            "schema": self.schema_context,
            "query": query,
            "examples": code_examples
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
                    "engine": "fast-path-v4"
                },
                "chart_data": chart_data,
            }

        # C. EXECUTE CODE (Self-Healing Executor) [cite: 10, 37]
        # Using run_in_threadpool to keep the executor from blocking the event loop
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
                    "engine": "fast-path-v4"
                },
                "chart_data": None
            }

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

        if self._looks_like_reasoning_plan(final_answer):
            final_answer = str(raw_data)

        # E. PREDICATED RETURN: Strictly matches ChatResponse dict schema 
        return {
            "answer": final_answer,
            "generated_code": generated_code,
            "execution_result": {
                "status": "success",
                "raw_output": raw_data,
                "engine": "fast-path-v4"
            },
            "chart_data": None
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

        if self._looks_like_reasoning_plan(response):
            logger.info("Reasoning path returned a plan instead of an answer. Falling back to code path.")
            return await self._execute_direct_code_path(query)
        
        return {
            "answer": response,
            "generated_code": None,
            "execution_result": None,
            "chart_data": None
        }
