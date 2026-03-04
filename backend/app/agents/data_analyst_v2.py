"""
Enhanced Data Analyst Agent with Hybrid Architecture
Reasoning: Llama 3.1 8B | Coding: DeepSeek-Coder-V2 16B
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from typing import Dict, Any, Optional
import pandas as pd
import json
import traceback
import sys

from app.core.config import settings
from app.utils.code_executor import safe_execute_pandas_code
from app.utils.chart_generator import generate_chart
from app.utils.custom_llm import OllamaLocalLLM
from app.utils.data_passport import generate_data_passport
from app.utils.self_healing_executor import SelfHealingExecutor

class EnhancedDataAnalystAgent:
    """
    Hybrid Agent for large-scale data analysis.
    Delegates common-sense reasoning to Llama and syntax-heavy coding to DeepSeek.
    """
    
    def __init__(self, 
                 df: pd.DataFrame, 
                 conversation_memory: Optional[list] = None):
        self.df = df
        self.conversation_memory = conversation_memory or [] # <--- ADD THIS
        # 1. Initialize Hybrid LLMs
        # reasoning_llm handles "Can I actually do this?"
        self.reasoning_llm = OllamaLocalLLM(model="llama3.1:8b", temperature=0.0)
        # coding_llm handles "How do I write the exact syntax?"
        self.coding_llm = OllamaLocalLLM(model="deepseek-coder-v2:16b", temperature=0.0)
        
        # 2. Metadata Generation
        print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
        self.passport = generate_data_passport(df, max_sample_rows=3)
        
        # 3. Self-Healing Wrapper
        self.healing_executor = SelfHealingExecutor(
            df=df,
            max_retries=2,
            llm_fix_callback=self._llm_fix_code
        )
        
        # 4. Agent Setup
        self.tools = self._create_tools()
        self.agent = self._create_agent()

    def _llm_fix_code(self, code: str, error: str) -> str:
        """Uses DeepSeek specifically to fix syntactically broken code."""
        fix_prompt = f"""
        Fix this Python/Pandas code.
        Error: {error}
        Original Code: {code}
        Data columns: {list(self.df.columns)}
        Return ONLY the fixed code.
        """
        response = self.coding_llm.invoke(fix_prompt)
        fixed = response.content if hasattr(response, 'content') else str(response)
        return fixed.replace("```python", "").replace("```", "").strip()

    def _create_tools(self) -> list:
        """Tools available to the Llama-based Manager."""
        
        def get_dataframe_schema(query: str) -> str:
            """Provides schema and sanity check info."""
            schema = self.passport.to_prompt_context()
            numeric_cols = self.df.select_dtypes(include='number').columns.tolist()
            
            if not numeric_cols:
                return schema + "\n\nCRITICAL: This dataset has NO numeric columns. You cannot sum, mean, or correlate."
            return schema

        def execute_analysis_task(task_description: str) -> str:
            """Hands off a logic task to DeepSeek for code generation and execution."""
            # Coding specialist prompt
            coding_prompt = f"""
            Generate Python code using the 'df' variable.
            Task: {task_description}
            Schema Context: {self.df.columns.tolist()}
            Rule: 
            1. Store the result in a variable named 'result'.
            2. dont use dummy data to perform the analysis, use the provided dataframe 'df' and its columns.
            3. generate syntax free code without markdown formatting.
            Return ONLY code.
            """
            
            # Step A: DeepSeek generates the syntax
            code_response = self.coding_llm.invoke(coding_prompt)
            raw_code = code_response.content if hasattr(code_response, 'content') else str(code_response)
            
            # Step B: Safe Execution with healing
            try:
                exec_result = self.healing_executor.execute_with_healing(raw_code)
                if exec_result.success:
                    return json.dumps({
                        "success": True, 
                        "result": exec_result.result, 
                        "code": raw_code
                    }, default=str)
                return json.dumps({"success": False, "error": exec_result.error})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})

        return [
            Tool(
                name="get_dataframe_schema",
                func=get_dataframe_schema,
                description="Use this FIRST. Returns column names, types, and stats."
            ),
            Tool(
                name="execute_analysis",
                func=execute_analysis_task,
                description="Describe the analysis task in plain English. DeepSeek will write the code."
            )
        ]
    def _create_agent(self) -> AgentExecutor:
        # History formatting (keep your existing history loop here)
        history_text = ""
        if hasattr(self, 'conversation_memory') and self.conversation_memory:
            history_text = "## Previous Conversation:\n"
            for msg in self.conversation_memory:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_text += f"{role}: {msg.get('content')}\n"
            history_text += "\n"

        template = f"""You are a Data Analyst Manager. 

{history_text}
## Rules:
1. ALWAYS use get_dataframe_schema first to check available columns.
2. If the data needed is missing, STOP and provide a Final Answer.
3. If the data exists, call execute_analysis.

## STRICT FORMATTING:
You must ONLY output the Thought, Action, and Action Input. 
**DO NOT generate the Observation.** The system will provide the Observation.

Thought: [your reasoning]
Action: [tool_name]
Action Input: [tool input]

When you have the final answer:
Thought: I have the final conclusion.
Final Answer: [Your exact answer]

Available Tools: {{tool_names}}
{{tools}}

Question: {{input}}
{{agent_scratchpad}}"""

        prompt = PromptTemplate(
            template=template, 
            input_variables=["input", "tools", "tool_names", "agent_scratchpad"]
        )
        
        agent = create_react_agent(self.reasoning_llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True, 
            max_iterations=5, 
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    def analyze(self, query: str) -> Dict[str, Any]:
        """Entry point for FastAPI chat endpoint."""
        try:
            print(f"\nQUERY: {query}\n")
            
            # 1. Run the agent
            response = self.agent.invoke({"input": query, "agent_scratchpad": ""})
            output = response.get("output", str(response))
            
            # 2. Extract code and chart data
            generated_code = None
            intermediate_steps = response.get("intermediate_steps", [])
            for action, obs in intermediate_steps:
                if action.tool == "execute_analysis":
                    try:
                        obs_data = json.loads(obs)
                        generated_code = obs_data.get("code")
                    except: pass

            chart_data = None
            if generated_code and any(k in query.lower() for k in ['plot', 'chart', 'visualize']):
                chart_data = generate_chart(self.df, query, generated_code)

            return {
                "answer": output,
                "generated_code": generated_code,
                "chart_data": chart_data,
                "success": True,
                "metadata": {"dataset_shape": self.df.shape}
            }
            
        except Exception as e:
            return {
                "answer": f"Analysis Error: {str(e)}",
                "success": False,
                "traceback": traceback.format_exc()
            }

# Alias for chat.py
DataAnalystAgent = EnhancedDataAnalystAgent