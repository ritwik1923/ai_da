from typing import Dict, Any
try:
    from . import CodeSanitizer
    from .FewShotExampleStore import FewShotExampleStore
except ImportError:  # pragma: no cover
    try:
        from utility import CodeSanitizer
        from utility.FewShotExampleStore import FewShotExampleStore
    except ImportError:
        import CodeSanitizer
        from FewShotExampleStore import FewShotExampleStore

class CodeGenerationService:
    """Orchestrates code generation, sanitization, and execution."""
    
    def __init__(self, coding_llm, example_store: FewShotExampleStore, df, executor):
        self.llm = coding_llm
        self.example_store = example_store
        self.df = df
        self.executor = executor 
        # Inject the fix callback into the executor
        self.executor.llm_fix_callback = self._llm_fix_code

    def _llm_fix_code(self, code: str, error: str) -> str:
        fix_prompt = f"""
        Fix this Python/Pandas code.
        Error: {error}
        Original Code: {code}
        Data columns: {list(self.df.columns)}
        Return ONLY the fixed code without markdown backticks.
        """
        response = self.llm.invoke(fix_prompt)
        raw_fixed = response.content if hasattr(response, 'content') else str(response)
        return CodeSanitizer.CodeSanitizer.sanitize(raw_fixed)

    def generate_and_execute(self, task_description: str) -> Dict[str, Any]:
        examples_str = self.example_store.get_context_string(task_description)
        
        coding_prompt = f"""
        Generate Python3.9 code using the 'df' variable.
        Task: {task_description}
        Schema Context: {self.df.columns.tolist()}
        ### VERIFIED EXAMPLES ###
        {examples_str}
        ### STRICT RULES ###
        1. Store your final answer in a variable named exactly 'result'.
        2. CRITICAL: Do NOT use standard Python `for` loops, `iterrows()`, or `defaultdict`. You MUST use idiomatic, vectorized Pandas operations.
        3. CRITICAL: Augmented assignments (like += or -=) are STRICTLY FORBIDDEN.
        4. Do NOT create dummy data or mock DataFrames. Use the provided dataframe 'df'.
        5. Generate pure Python code without any markdown formatting or backticks.
        6. Do NOT use print() or return statements. The system extracts 'result' automatically.
        7. If the task is a visualization, MUST use `plotly.express` as `px`. Create the figure object and assign it DIRECTLY to the 'result' variable (e.g., `result = px.line(...)`). Do NOT use matplotlib, seaborn, or plt.show().
        8. Do NOT include any print statements or return statements. Just generate the code to compute 'result'.
        9. Always use the columns from the provided dataframe and do not make assumptions about column names or data types.
        10. CRITICAL: Do NOT use `pd.Grouper(freq=...)` or `.resample()` unless you are absolutely certain the column is a `datetime` type. Do not attempt time-series grouping on `int64` or `object` columns.
        11. Always use the columns from the provided dataframe and do not make assumptions about data types.
        12. CRITICAL TIMELINE RULE: If the user asks for a trend "over time" but the dataset lacks a `datetime` column, DO NOT use `pd.Grouper(freq=...)` or `.resample()`. Simply plot the numeric 'Index' directly on the x-axis (e.g., `x='Index'`). 
        13. Never attempt time-series frequency grouping on `int64` or `object` columns.
                
        # """
        response = self.llm.invoke(coding_prompt)
        raw_code = response.content if hasattr(response, 'content') else str(response)
        clean_code = CodeSanitizer.CodeSanitizer.sanitize(raw_code)

        try:
            exec_result = self.executor.execute_with_healing(clean_code)
            if exec_result.success:
                return {"success": True, "result": exec_result.result, "code": clean_code}
            return {"success": False, "error": exec_result.error, "code": clean_code}
        except Exception as e:
            return {"success": False, "error": str(e), "code": clean_code}