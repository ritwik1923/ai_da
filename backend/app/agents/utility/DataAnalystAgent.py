import traceback
import os
import sys

try:
    # Import the custom exception here!
    from app.utils.chart_generator import generate_chart, ChartGenerationError
except ImportError:  # pragma: no cover
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from utils.chart_generator import generate_chart, ChartGenerationError

class DataAnalystAgent:
    """Main facade orchestrating the analysis workflow."""
    
    def __init__(self, df, reasoning_llm, agent_executor, code_service, max_retries=2):
        self.df = df
        self.reasoning_llm = reasoning_llm
        self.agent = agent_executor
        self.code_service = code_service
        self.max_retries = max_retries

    def analyze(self, query: str, attempt=1,prev_errors = "") -> dict:
        try:
            chart_query = any(k in query.lower() for k in ['plot', 'chart', 'visualize'])
            
            # Fast-path for charts
            if chart_query and attempt <= self.max_retries:
                analysis_output = self.code_service.generate_and_execute(query)
                generated_code = analysis_output.get("code")
                chart_data = generate_chart(self.df, query, generated_code)
                        
                            
                return {
                    "answer": f"Generated chart.",
                    "generated_code": generated_code,
                    "chart_data": chart_data,
                    "success": True
                }       

        except ChartGenerationError as chart_e:
            error_msg = str(chart_e)
            print(f"[DataAnalystAgent] ⚠️ Chart attempt {attempt} failed: {error_msg}")
            prev_errors += f"\nAttempt {attempt} error: {error_msg}" 
            query_with_errors = f"{query}\n\nPrevious Errors:\n{prev_errors}"
            return self.analyze(query_with_errors, attempt=attempt+1, prev_errors=prev_errors)
        except Exception as e:
             return {
                "answer": f"Analysis Error: {str(e)}",
                "success": False,
                "traceback": traceback.format_exc()
            }

