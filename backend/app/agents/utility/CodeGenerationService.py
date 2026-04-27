from typing import Dict, Any
from . import CodeSanitizer
from .FewShotExampleStore import FewShotExampleStore

class CodeGenerationService:
    """Orchestrates code generation, sanitization, and execution."""
    
    def __init__(self, coding_llm, example_store: FewShotExampleStore, df, executor, visualization_store: FewShotExampleStore | None = None):
        if coding_llm is None:
            raise ValueError("CodeGenerationService requires a coding_llm instance.")

        self.llm = coding_llm
        self.example_store = example_store
        self.visualization_store = visualization_store or example_store
        self.df = df
        self.executor = executor 
        # Inject the fix callback into the executor
        self.executor.llm_fix_callback = self._llm_fix_code

    def _build_prompt(self, task_description: str, examples_str: str, visualization_guidance: str = "") -> str:
        return f"""
        Generate Python3.9 code using the 'df' variable.
        Task: {task_description}
        Schema Context: {self.df.columns.tolist()}
        ### VERIFIED EXAMPLES ###
        {examples_str}
        ### VISUALIZATION GUIDANCE ###
        {visualization_guidance}
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
        14. Build charts for non-technical business users. Prefer aggregated summaries over row-level plots when the raw chart would contain many points or categories.
        15. For category comparisons, group the data first and sort the result so the ranking is obvious. Limit to the top 10-12 categories unless the user explicitly asks for all categories.
        16. Avoid raw scatter plots with dozens of colored categories. If the task compares two numeric metrics and a category dimension exists, first aggregate by that category and plot one labeled point per category, using bubble size for count when helpful.
        17. Prefer chart types that match the question: use bar charts for comparisons, histograms or box plots for distributions, and only use scatter plots for clear metric-vs-metric relationships.
        18. Use clear chart titles that describe the insight in business language, and make the figure readable by adding labels or ordering where appropriate.
        19. For price/category distribution KPIs, prefer a sorted horizontal bar chart and default to the top 5 or top 10 categories instead of plotting every category.
        """

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
        examples_str = ""
        if self.example_store is not None:
            examples_str = self.example_store.get_context_string(task_description)
        coding_prompt = self._build_prompt(task_description, examples_str)

        # """
        response = self.llm.invoke(coding_prompt)
        raw_code = response.content if hasattr(response, 'content') else str(response)
        clean_code = CodeSanitizer.CodeSanitizer.sanitize(raw_code)

        try:
            exec_result = self.executor.execute_with_healing(clean_code)
            if exec_result.success:
                return {"success": True, "result": exec_result.result, "code": clean_code}
            return {"success": False, "error": exec_result.error, "code": clean_code}
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {"success": False, "error": str(e), "code": clean_code}

    def generate_visualization_code(self, task_description: str, top_n: int = 10) -> Dict[str, Any]:
        visualization_examples = ""
        if self.visualization_store is not None:
            visualization_examples = self.visualization_store.get_context_string(task_description, k=2)

        visualization_guidance = (
            f"Use the retrieved visualization examples as the primary rendering reference. "
            f"Unless the user explicitly asks otherwise, keep only the top {top_n} categories for category-heavy KPI charts. "
            "Prefer sorted horizontal bars for ranked category distributions and preserve readable labels."
        )

        coding_prompt = self._build_prompt(task_description, visualization_examples, visualization_guidance)
        response = self.llm.invoke(coding_prompt)
        raw_code = response.content if hasattr(response, 'content') else str(response)
        clean_code = CodeSanitizer.CodeSanitizer.sanitize(raw_code)
        return {
            "success": bool(clean_code),
            "code": clean_code,
            "examples": visualization_examples,
            "top_n": top_n,
        }