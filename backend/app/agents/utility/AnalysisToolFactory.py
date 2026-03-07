from langchain.tools import Tool
import json
try:
    from .CodeGenerationService import CodeGenerationService
except ImportError:  # pragma: no cover
    try:
        from utility.CodeGenerationService import CodeGenerationService
    except ImportError:
        try:
            from CodeGenerationService import CodeGenerationService
        except ImportError:
            from app.agents.utility.CodeGenerationService import CodeGenerationService

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
            result = self.code_service.generate_and_execute(task)
            return json.dumps(result, default=str)

        return [
            Tool(name="get_dataframe_schema", func=get_schema, description="Returns column names, types, and stats."),
            Tool(name="execute_analysis", func=execute_analysis, description="Generates and runs Pandas code.")
        ]