import traceback
import os
import sys

try:
    from app.utils.chart_generator import generate_chart, ChartGenerationError
except ImportError:  # pragma: no cover
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from utils.chart_generator import generate_chart, ChartGenerationError

class DataAnalystAgent:
    """Main facade orchestrating the analysis workflow."""
    
    def __init__(self,query: str, df, reasoning_llm, agent_executor, code_service, max_retries=2):
        self.df = df
        self.reasoning_llm = reasoning_llm
        self.agent = agent_executor
        self.code_service = code_service
        self.max_retries = max_retries
        self.query = query

    def analyze(self, attempt=1, current_code=None, error_msg=None) -> dict:
        try:
            chart_query = any(k in self.query.lower() for k in ['plot', 'chart', 'visualize'])
            
            # --- BASE CASE: Out of retries ---
            if chart_query and attempt > self.max_retries:
                return {
                    "answer": f"Chart Generation Failed after {self.max_retries} attempts. Last error: {error_msg}",
                    "success": False,
                    "generated_code": current_code,
                    "traceback": error_msg
                }

            # --- FAST PATH: CHARTS ---
            if chart_query:
                # Step 1: Generate or Fix Code
                if attempt == 1:
                    analysis_output = self.code_service.generate_and_execute(self.query)
                    current_code = analysis_output.get("code")
                else:
                    print(f"[DataAnalystAgent] 🛠️ Asking LLM to fix the chart code (Attempt {attempt}/{self.max_retries})...")
                    # Use the dedicated fix method so it sees both the broken code AND the error
                    current_code = self.code_service._llm_fix_code(current_code, error_msg)

                # Step 2: Try to generate the chart (will raise ChartGenerationError if exec fails)
                chart_data = generate_chart(self.df, self.query, current_code)
                
                # Step 3: Success Return
                return {
                    "answer": "Generated chart.",
                    "generated_code": current_code,
                    "chart_data": chart_data,
                    "success": True
                }

            # --- STANDARD PATH: TEXT QUERIES ---
            print(f"\n\nQuery: {self.query}\n\n")
            response = self.agent.invoke({"input": self.query, "agent_scratchpad": ""})
            
            return {
                "answer": response.get("output", str(response)),
                "success": True
            }

        except ChartGenerationError as chart_e:
            # --- RECURSIVE RETRY ---
            print(f"[DataAnalystAgent] ⚠️ Chart execution failed: {str(chart_e)}")
            # Return the recursive call, passing the exact broken code and error message
            return self.analyze(attempt=attempt + 1, current_code=current_code, error_msg=str(chart_e))
            
        except Exception as e:
            # Catch-all for other system failures
            return {
                "answer": f"Analysis Error: {str(e)}",
                "success": False,
                "traceback": traceback.format_exc()
            }