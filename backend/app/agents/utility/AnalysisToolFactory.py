from langchain_classic.tools import Tool
import json
from .CodeGenerationService import CodeGenerationService

class AnalysisToolFactory:
    """Builds the tools required for the ReAct agent."""
    
    def __init__(self, data_passport, code_service: CodeGenerationService, df):
        self.passport = data_passport
        self.code_service = code_service
        self.df = df

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

        return [
            Tool(name="get_dataframe_schema", func=get_schema, description="Returns column names, types, and stats."),
            Tool(name="execute_analysis", func=execute_analysis, description="Generates and runs Pandas code.")
        ]