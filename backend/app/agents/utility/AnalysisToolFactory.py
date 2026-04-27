from langchain_classic.tools import Tool
import json
from typing import Any
from starlette.concurrency import run_in_threadpool
from .CodeGenerationService import CodeGenerationService

class AnalysisToolFactory:
    """Builds the tools required for the ReAct agent."""
    
    def __init__(self, data_passport, code_service: CodeGenerationService, df):
        self.passport = data_passport
        self.code_service = code_service
        self.df = df

    async def generate_code(self, task: str) -> str:
        response = await run_in_threadpool(self.code_service.generate_and_execute, task)
        return response.get("code", "")

    async def generate_visualisation_code(self, task: str, top_n: int = 10) -> dict[str, Any]:
        return await run_in_threadpool(self.code_service.generate_visualization_code, task, top_n)

    def create_tools(self) -> list[Tool]:
        def get_schema(_query: str) -> str:
            return self.passport.to_prompt_context()

        def execute_analysis(task: str) -> str:
            response = self.code_service.generate_and_execute(task)
            if response.get("success"):
                # Extract just the value for the LLM's 'Observation'
                result_data = response.get("result", {})
                val = result_data.get("value") if isinstance(result_data, dict) else result_data
                return f"Analysis successful. Result: {val}"
            else:
                return f"Analysis failed. Error: {response.get('error')}"

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