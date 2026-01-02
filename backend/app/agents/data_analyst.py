from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from typing import Dict, Any, Optional
import pandas as pd
import json
import traceback
from io import StringIO
import sys

from app.core.config import settings
from app.utils.code_executor import safe_execute_pandas_code
from app.utils.chart_generator import generate_chart
from app.utils.custom_llm import CompanyGenAILLM


class DataAnalystAgent:
    """
    LangChain agent for autonomous data analysis.
    Generates and executes Python/Pandas code based on natural language queries.
    Supports multiple LLM providers: OpenAI or Company GenAI API
    """
    
    def __init__(self, df: pd.DataFrame, conversation_memory: Optional[list] = None):
        self.df = df
        
        # Initialize LLM based on provider setting
        self.llm = self._initialize_llm()
        
        # Initialize conversation memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Load previous conversation if provided
        if conversation_memory:
            for msg in conversation_memory:
                if msg['role'] == 'user':
                    self.memory.chat_memory.add_user_message(msg['content'])
                elif msg['role'] == 'assistant':
                    self.memory.chat_memory.add_ai_message(msg['content'])
        
        # Create tools for the agent
        self.tools = self._create_tools()
        
        # Create the agent
        self.agent = self._create_agent()
    
    def _initialize_llm(self):
        """Initialize the appropriate LLM based on configuration."""
        provider = settings.LLM_PROVIDER.lower()
        
        if provider == "company":
            return CompanyGenAILLM(
                api_key=settings.COMPANY_API_KEY,
                model=settings.COMPANY_MODEL,
                user_id=settings.COMPANY_USER_ID if settings.COMPANY_USER_ID else None,
                base_url=settings.COMPANY_BASE_URL,
                client_id=settings.COMPANY_CLIENT_ID,
                temperature=0,
                max_tokens=2000  # Higher for code generation
            )
        else:  # Default to OpenAI
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=0,
                api_key=settings.OPENAI_API_KEY
            )
    
    def _create_tools(self) -> list:
        """Create tools for the agent to use"""
        
        def get_dataframe_info(query: str) -> str:
            """Get information about the dataframe structure"""
            buffer = StringIO()
            self.df.info(buf=buffer)
            info = buffer.getvalue()
            
            return f"""
DataFrame Information:
{info}

First 5 rows:
{self.df.head().to_string()}

Column Statistics:
{self.df.describe().to_string()}
"""
        
        def execute_pandas_code(code: str) -> str:
            """Execute Pandas code and return results"""
            try:
                result = safe_execute_pandas_code(code, self.df)
                return json.dumps(result, default=str)
            except Exception as e:
                return f"Error executing code: {str(e)}\n{traceback.format_exc()}"
        
        def analyze_column(column_name: str) -> str:
            """Analyze a specific column"""
            if column_name not in self.df.columns:
                return f"Column '{column_name}' not found. Available columns: {list(self.df.columns)}"
            
            col_data = self.df[column_name]
            analysis = {
                "name": column_name,
                "dtype": str(col_data.dtype),
                "null_count": int(col_data.isnull().sum()),
                "unique_values": int(col_data.nunique())
            }
            
            if pd.api.types.is_numeric_dtype(col_data):
                analysis.update({
                    "mean": float(col_data.mean()),
                    "median": float(col_data.median()),
                    "std": float(col_data.std()),
                    "min": float(col_data.min()),
                    "max": float(col_data.max())
                })
            
            return json.dumps(analysis, indent=2)
        
        return [
            Tool(
                name="get_dataframe_info",
                func=get_dataframe_info,
                description="Get detailed information about the dataframe structure, columns, and basic statistics. Use this first to understand the data."
            ),
            Tool(
                name="execute_pandas_code",
                func=execute_pandas_code,
                description="Execute Python/Pandas code to analyze the dataframe. The dataframe is available as 'df'. Return the results as a dictionary."
            ),
            Tool(
                name="analyze_column",
                func=analyze_column,
                description="Get detailed statistics about a specific column. Useful for understanding individual column characteristics."
            )
        ]
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent using ReAct pattern"""
        
        # ReAct prompt template
        template = """You are a data analyst. Answer questions by executing Python code on a pandas DataFrame called 'df'.

You have these tools:
{tools}

Tool names: {tool_names}

ALWAYS use this exact format:

Question: the question to answer
Thought: I need to execute code to get the answer
Action: execute_pandas_code
Action Input: result = df['column'].sum()
Observation: {{"type": "scalar", "value": 123}}
Thought: I now have the answer
Final Answer: The total is 123

Question: {input}
Thought:{agent_scratchpad}"""

        prompt = PromptTemplate.from_template(template)
        
        agent = create_react_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
            return_intermediate_steps=False
        )
    
    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Analyze data based on natural language query
        
        Args:
            query: Natural language question about the data
            
        Returns:
            Dictionary with analysis results
        """
        try:
            # Run the agent
            response = self.agent.invoke({"input": query})
            
            # Extract the output
            output = response.get("output", str(response))
            
            # Extract generated code if any
            generated_code = self._extract_code_from_response(response)
            
            # Generate chart if applicable
            chart_data = None
            if self._should_create_chart(query, response):
                chart_data = self._generate_chart(query, generated_code)
            
            return {
                "answer": output,
                "generated_code": generated_code,
                "chart_data": chart_data,
                "success": True
            }
            
        except Exception as e:
            return {
                "answer": f"I encountered an error while analyzing the data: {str(e)}",
                "generated_code": None,
                "chart_data": None,
                "success": False,
                "error": str(e)
            }
    
    def _extract_code_from_response(self, response: Dict) -> Optional[str]:
        """Extract Python code from agent response"""
        # Try to extract code from the output text
        output = response.get("output", "")
        
        # Look for code blocks in the response
        if "```python" in output:
            start = output.find("```python") + 9
            end = output.find("```", start)
            if end != -1:
                return output[start:end].strip()
        
        # Look for result = pattern
        if "result = " in output:
            lines = output.split('\n')
            code_lines = [line for line in lines if 'result = ' in line or 'df[' in line or 'df.' in line]
            if code_lines:
                return '\n'.join(code_lines)
        
        return None
    
    def _should_create_chart(self, query: str, response: Dict) -> bool:
        """Determine if a chart should be created based on the query"""
        chart_keywords = ['plot', 'chart', 'graph', 'visualize', 'show', 'trend', 'compare', 'distribution']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in chart_keywords)
    
    def _generate_chart(self, query: str, code: Optional[str]) -> Optional[Dict]:
        """Generate chart configuration based on query and code"""
        try:
            return generate_chart(self.df, query, code)
        except Exception as e:
            print(f"Chart generation error: {e}")
            return None
