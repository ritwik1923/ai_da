"""
Enhanced Data Analyst Agent with Hybrid Architecture & Vector DB Few-Shot Routing
Reasoning: Llama 3.1 8B | Coding: DeepSeek-Coder-V2 16B | Memory: FAISS
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
# from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.documents import Document
from typing import Dict, Any, Optional
import pandas as pd
import json
import traceback
import sys, re

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
    Uses a Vector DB to retrieve safe, verified Pandas examples to prevent RestrictedPython crashes.
    """
    
    def __init__(self, 
                 df: pd.DataFrame, 
                 conversation_memory: Optional[list] = None):
        self.df = df
        self.conversation_memory = conversation_memory or []
        
        # 1. Initialize Hybrid LLMs
        self.reasoning_llm = OllamaLocalLLM(model="llama3.1:8b", temperature=0.0)
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
        
        # 4. Initialize Vector DB for Code Examples
        self._initialize_example_db()
        
        # 5. Agent Setup
        self.tools = self._create_tools()
        self.agent = self._create_agent()

    def _initialize_example_db(self):
        """
        Seeds an in-memory FAISS vector database with golden Pandas examples.
        This forces DeepSeek to use vectorized operations instead of illegal for-loops.
        """
        print("Initializing FAISS Vector DB with safe Pandas examples...")
        # Using the existing llama3.1 model for embeddings so no extra downloads are needed
        self.embeddings = OllamaEmbeddings(model="llama3.1:8b") 
        
        golden_examples = [
            {
                "task": "Which 3 categories have the highest total stock available?", 
                "code": "result = df.groupby('Category')['Stock'].sum().nlargest(3)"
            },
            {
                "task": "Generate a bar chart showing the total stock for each product category.",
                "code": "result = df.groupby('Category', dropna=False)['Stock'].sum().reset_index()"
            },
            {
                "task": "How many products contain the word 'Smart' anywhere in their name?", 
                "code": "result = len(df[df['Name'].str.contains('Smart', case=False, na=False)])"
            },
            {
                "task": "What is the name and price of the single most expensive product?", 
                "code": "result = df.loc[df['Price'].idxmax(), ['Name', 'Price']].to_dict()"
            },
            {
                "task": "What is the exact median price of all products in the dataset?", 
                "code": "result = df['Price'].median()"
            },
            {
                "task": "Calculate the average revenue for each product category", 
                "code": "result = df.groupby('Category')['Revenue'].mean()"
            },
            {
                "task": "Find the most common color specifically among products that are on pre_order", 
                "code": "result = df[df['Availability'] == 'pre_order']['Color'].mode().iloc[0]"
            }
        ]
        
        docs = [Document(page_content=ex["task"], metadata={"code": ex["code"]}) for ex in golden_examples]
        self.vector_db = FAISS.from_documents(docs, self.embeddings)

    def _llm_fix_code(self, code: str, error: str) -> str:
        """Uses DeepSeek specifically to fix syntactically broken code."""
        fix_prompt = f"""
        Fix this Python/Pandas code.
        Error: {error}
        Original Code: {code}
        Data columns: {list(self.df.columns)}
        Return ONLY the fixed code without markdown backticks.
        """
        response = self.coding_llm.invoke(fix_prompt)
        fixed = response.content if hasattr(response, 'content') else str(response)
        return self._sanitize_deepseek_code(fixed)
    
    def _sanitize_deepseek_code(self, raw_code: str) -> str:
        """Strips DeepSeek's conversational boilerplate, imports, and rogue prints."""
        code = re.sub(r"```python\n?", "", raw_code)
        code = re.sub(r"```\n?", "", code)
        code = re.sub(r"^print\s*\(.*\)$", "", code, flags=re.MULTILINE) # Strip rogue prints
        
        lines = code.split('\n')
        cleaned_lines = [line for line in lines if not (line.strip().startswith('import ') or line.strip().startswith('from '))]
        
        code = '\n'.join(cleaned_lines)
        code = code.split("Note:")[0].split("This code")[0].split("In this example")[0].strip()
        
        return code
    
    def _create_tools(self) -> list:
        
        def get_dataframe_schema(query: str) -> str:
            schema = self.passport.to_prompt_context()
            numeric_cols = self.df.select_dtypes(include='number').columns.tolist()
            if not numeric_cols:
                return schema + "\n\nCRITICAL: This dataset has NO numeric columns. You cannot sum, mean, or correlate."
            return schema

        def execute_analysis_task(task_description: str) -> str:
            # 1. Retrieve the top 2 closest examples from the Vector DB
            similar_docs = self.vector_db.similarity_search(task_description, k=2)
            examples_str = "\n".join([f"Similar Task: {doc.page_content}\nVerified Code: {doc.metadata['code']}\n" for doc in similar_docs])
            
            # 2. Inject them into the prompt
            coding_prompt = f"""
            Generate Python3.9 code using the 'df' variable.
            Task: {task_description}
            Schema Context: {self.df.columns.tolist()}
            
            ### VERIFIED EXAMPLES (MIMIC THIS STYLE) ###
            {examples_str}
            
            ### STRICT RULES ###
            1. Store your final answer in a variable named exactly 'result'.
            2. CRITICAL: Do NOT use standard Python `for` loops, `iterrows()`, or `defaultdict`. You MUST use idiomatic, vectorized Pandas operations.
            3. CRITICAL: Augmented assignments (like += or -=) are STRICTLY FORBIDDEN.
            4. Do NOT create dummy data or mock DataFrames. Use the provided dataframe 'df'.
            5. Generate pure Python code without any markdown formatting or backticks.
            6. Do NOT use print() or return statements. The system extracts 'result' automatically.
            """
            
            code_response = self.coding_llm.invoke(coding_prompt)
            raw_code = code_response.content if hasattr(code_response, 'content') else str(code_response)
            clean_code = self._sanitize_deepseek_code(raw_code)
            
            try:
                exec_result = self.healing_executor.execute_with_healing(clean_code)
                if exec_result.success:
                    return json.dumps({
                        "success": True, 
                        "result": exec_result.result, 
                        "code": clean_code
                    }, default=str)
                return json.dumps({"success": False, "error": exec_result.error})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        # def generate_chart(df: pd.DataFrame, query: str, code: str) -> Optional[Dict[str, Any]]:
        #     chart_prompt = f"""
        #     Based on this analysis code:
        #     {code}
        #     And this question:
        #     {query}
        #     Determine if a chart would help visualize the answer. If yes, generate a JSON config for a bar chart or line chart using the 'result' variable. If not, return null.
        #     """
        #     chart_response = self.coding_llm.invoke(chart_prompt)
        #     chart_json = chart_response.content if hasattr(chart_response, 'content') else str(chart_response)
        #     try:
        #         return json.loads(chart_json)
        #     except:
        #         return None
        
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
            schema_context = self.passport.to_prompt_context()
            history_text = ""
            if hasattr(self, 'conversation_memory') and self.conversation_memory:
                history_text = "## Previous Conversation:\n"
                for msg in self.conversation_memory:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    history_text += f"{role}: {msg.get('content')}\n"
                history_text += "\n"

            template = """You are a Data Analyst Manager. 

    ## Dataset Schema (Already Loaded):
    {history_text}
    {schema_context}

    ## Rules:
    1. Review the Schema and Previous Conversation. 
    2. If the data needed is missing, or if you already know the answer from the conversation history, DO NOT use a tool. Proceed directly to Final Answer.
    3. If the data exists and you need to perform an analysis, call a tool.
    4. ALWAYS use get_dataframe_schema first if you need to check available columns or data types before performing an analysis.
    5. CRITICAL: When answering questions about top/bottom items, aggregates, or calculations, ALWAYS include the exact calculated numerical values in your Final Answer. Format large numbers with commas (e.g., 5,719,031 instead of 5719031).

    ## STRICT FORMATTING RULES (CRITICAL):
    You must choose EXACTLY ONE of the following options. 

    OPTION 1: Use a Tool (Do NOT include Final Answer)
    Thought: [your reasoning]
    Action: [MUST be EXACTLY one of: {tool_names}]
    Action Input: [Provide the input. For execute_analysis, describe the task. For get_dataframe_schema, just write "schema". For generate_chart, provide the chart description. THIS IS ALWAYS REQUIRED.]

    OR

    OPTION 2: Give the Final Answer (Do NOT include Action or Action Input)
    Thought: I already know the answer or cannot proceed.
    Final Answer: [Your exact answer]

    NEVER use "Action: None".
    NEVER put "Action" and "Final Answer" in the same response.

    Available Tools: {tool_names} {tools}

    Question: {input}
    {agent_scratchpad}"""
            prompt = PromptTemplate(
                template=template, 
                input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
                partial_variables={
                    "schema_context": schema_context,
                    "history_text": history_text
                }
            )
            
            agent = create_react_agent(self.reasoning_llm, self.tools, prompt)
            parsing_error_instruction = (
                "FORMATTING ERROR: You must output EXACTLY 'Action: execute_analysis' "
                "without any markdown, asterisks (**), or bold text. Do not add 'Please provide the Observation'."
            )
            return AgentExecutor(
                agent=agent, 
                tools=self.tools, 
                verbose=True, 
                max_iterations=4,
                handle_parsing_errors=parsing_error_instruction,
                return_intermediate_steps=True
            )

    def analyze(self, query: str) -> Dict[str, Any]:
        """Entry point for FastAPI chat endpoint."""
        try:
            print(f"\nQUERY: {query}\n")
            response = self.agent.invoke({"input": query, "agent_scratchpad": ""})
            output = response.get("output", str(response))
            
            generated_code = None
            intermediate_steps = response.get("intermediate_steps", [])
            for action, obs in intermediate_steps:
                if action.tool == "execute_analysis":
                    try:
                        obs_data = json.loads(obs)
                        generated_code = obs_data.get("code")
                    except: pass

            chart_data = None
            chart_query = any(k in query.lower() for k in ['plot', 'chart', 'visualize', 'graph'])
            if chart_query:
                chart_data = generate_chart(self.df, query, generated_code) if generated_code else generate_chart(self.df, query)
            
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