from langchain_classic.tools import Tool
import json
from typing import Any, Dict, List, Optional
from starlette.concurrency import run_in_threadpool
from .CodeGenerationService import CodeGenerationService

class AnalysisToolFactory:
    """Builds the tools required for the ReAct agent."""
    
    def __init__(self, data_passport, code_service: CodeGenerationService, df):
        self.passport = data_passport
        self.code_service = code_service
        self.df = df
        self._execute_analysis_history: List[Dict[str, Any]] = []

    def get_execute_analysis_history(self) -> List[Dict[str, Any]]:
        """Return execute_analysis call history captured during a single agent run."""
        return list(self._execute_analysis_history)

    def _compact_result_for_observation(self, result_data: Any) -> Any:
        """Trim heavy result payloads before feeding observations back to the reasoning LLM."""
        if not isinstance(result_data, dict):
            return result_data

        compact = dict(result_data)

        # Keep chart payload for API response, but never echo full chart JSON into the ReAct loop.
        compact.pop("chart_data", None)

        if compact.get("type") == "dataframe":
            rows = compact.get("data") or []
            if isinstance(rows, list):
                compact["data"] = rows[:5]

        if compact.get("type") == "series":
            data = compact.get("data") or {}
            if isinstance(data, dict):
                compact["data"] = dict(list(data.items())[:10])

        if compact.get("type") == "collection":
            data = compact.get("data")
            if isinstance(data, list):
                compact["data"] = data[:10]

        return compact

    async def generate_code(self, task: str) -> str:
        response = await run_in_threadpool(self.code_service.generate_and_execute, task)
        return response.get("code", "")

    async def generate_visualisation_code(self, task: str, top_n: int = 10) -> dict[str, Any]:
        return await run_in_threadpool(self.code_service.generate_visualization_code, task, top_n)

    def create_tools(self) -> list[Tool]:
        def get_schema(_query: str) -> str:
            return self.passport.to_prompt_context()

        def summarize_result(result_data: Any) -> str:
            if not isinstance(result_data, dict):
                return f"Analysis completed. Result: {result_data}"

            result_type = result_data.get("type")

            if result_type == "scalar":
                return f"Computed value: {result_data.get('value')}"

            if result_type == "series":
                data = result_data.get("data") or {}
                if isinstance(data, dict) and data:
                    top_items = list(data.items())[:5]
                    preview = ", ".join([f"{k}: {v}" for k, v in top_items])
                    return f"Computed ranked values. Top entries: {preview}"
                return "Computed a ranked series result."

            if result_type == "dataframe":
                rows = result_data.get("data") or []
                if isinstance(rows, list) and rows:
                    first_row = rows[0]
                    if isinstance(first_row, dict):
                        first_row_preview = ", ".join([f"{k}: {v}" for k, v in list(first_row.items())[:4]])
                        return (
                            f"Computed tabular results with {len(rows)} rows. "
                            f"Top row preview: {first_row_preview}"
                        )
                return "Computed tabular results."

            if result_type == "plotly_figure":
                title = result_data.get("title") or "Generated chart"
                trace_count = result_data.get("trace_count", 0)
                return f"Generated chart '{title}' with {trace_count} trace(s)."

            return "Analysis completed successfully."

        def execute_analysis(task: str) -> str:
            response = self.code_service.generate_and_execute(task)
            if response.get("success"):
                result_data = response.get("result", {})
                chart_data = result_data.get("chart_data") if isinstance(result_data, dict) else None

                full_payload = {
                    "status": "success",
                    "tool": "execute_analysis",
                    "task": task,
                    "summary": summarize_result(result_data),
                    "result_data": result_data,
                    "generated_code": response.get("code"),
                    "chart_data": chart_data,
                }
                self._execute_analysis_history.append(full_payload)

                observation_payload = {
                    "status": "success",
                    "tool": "execute_analysis",
                    "task": task,
                    "summary": full_payload["summary"],
                    "result_data": self._compact_result_for_observation(result_data),
                    "generated_code": response.get("code"),
                    "has_chart_data": chart_data is not None,
                }
                return json.dumps(observation_payload, default=str)
            else:
                payload = {
                    "status": "error",
                    "tool": "execute_analysis",
                    "task": task,
                    "error": response.get("error"),
                    "generated_code": response.get("code"),
                }
                self._execute_analysis_history.append(payload)
                return json.dumps(payload, default=str)

        def visualisation_tool(task: str) -> str:
            response = self.code_service.generate_visualization_code(task)
            code = response.get("code", "")
            examples = response.get("examples", "")
            if not code:
                return "Visualization generation failed. No visualization code was returned."
            return json.dumps({
                "status": "success",
                "tool": "visualisation_tool",
                "generated_code": code,
                "retrieved_examples": examples,
                "top_n": response.get("top_n", 10),
            })

        return [
            Tool(name="get_dataframe_schema", func=get_schema, description="Returns column names, types, and stats."),
            Tool(name="execute_analysis", func=execute_analysis, description="Generates and runs Pandas code."),
            Tool(name="visualisation_tool", func=visualisation_tool, description="Retrieves visualization golden examples from the vector DB and generates KPI chart code using those references.")
        ]