"""
Enhanced Data Analyst Agent with Schema-First Architecture
Handles 100k+ rows × 1000+ columns efficiently using RAG and self-healing execution.
"""

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
from app.utils.data_passport import generate_data_passport, DataPassport
from app.utils.column_vector_store import ColumnVectorStore, ColumnSelector
from app.utils.self_healing_executor import SelfHealingExecutor
from app.prompts.expert_prompts import (
    MASTER_ANALYST_SYSTEM_PROMPT,
    SCHEMA_FIRST_PROMPT,
    COLUMN_SELECTION_PROMPT,
    get_error_fix_prompt,
    format_schema_for_prompt
)


class EnhancedDataAnalystAgent:
    """
    Advanced LangChain agent for large-scale data analysis.
    
    Key Features:
    - Schema-First: Sends only metadata to LLM, not raw data
    - RAG-Based Column Selection: Handles 1000+ columns via semantic search
    - Self-Healing: Automatically fixes code errors
    - Zero Data Leakage: Raw data never sent to external APIs
    """
    
    def __init__(self, 
                 df: pd.DataFrame, 
                 conversation_memory: Optional[list] = None,
                 enable_column_rag: bool = True,
                 max_columns_in_context: int = 20):
        """
        Args:
            df: DataFrame to analyze
            conversation_memory: Previous conversation for context
            enable_column_rag: Enable RAG for column selection (recommended for 50+ columns)
            max_columns_in_context: Max columns to include in LLM context
        """
        self.df = df
        self.enable_column_rag = enable_column_rag and len(df.columns) > 50
        self.max_columns_in_context = max_columns_in_context
        
        # Generate data passport (metadata only)
        print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
        self.passport = generate_data_passport(df, max_sample_rows=3)
        
        # Initialize column vector store if needed
        self.column_store = None
        self.column_selector = None
        if self.enable_column_rag:
            print("Initializing RAG for column selection...")
            self._initialize_column_rag()
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Initialize self-healing executor
        self.healing_executor = SelfHealingExecutor(
            df=df,
            max_retries=3,
            llm_fix_callback=self._llm_fix_code
        )
        
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
                max_tokens=3000
            )
        else:  # Default to OpenAI
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=0,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=3000
            )
    
    def _initialize_column_rag(self):
        """Initialize RAG system for column selection."""
        self.column_store = ColumnVectorStore(
            collection_name=f"cols_{self.passport._get_fingerprint()}",
            persist_directory=None  # In-memory for now
        )
        
        # Get column descriptions
        column_descriptions = self.passport.get_column_descriptions()
        
        # Prepare metadata
        metadata = {}
        for col in self.passport.passport['schema']:
            metadata[col['name']] = {
                'data_type': col['category'],
                'unique_count': col['unique_count'],
                'null_percentage': col['null_percentage']
            }
        
        # Add to vector store
        self.column_store.add_columns(column_descriptions, metadata)
        
        # Initialize selector
        self.column_selector = ColumnSelector(
            self.column_store,
            self.passport.to_dict()
        )
    
    def _llm_fix_code(self, code: str, error: str) -> str:
        """Use LLM to fix code errors."""
        prompt = get_error_fix_prompt(code, error, list(self.df.columns))
        
        try:
            response = self.llm.invoke(prompt)
            # Extract code from response
            if hasattr(response, 'content'):
                fixed_code = response.content
            else:
                fixed_code = str(response)
            
            # Remove markdown code blocks if present
            if "```python" in fixed_code:
                fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
            elif "```" in fixed_code:
                fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
            
            return fixed_code
        except Exception as e:
            print(f"LLM fix failed: {e}")
            return code
    
    def _create_tools(self) -> list:
        """Create tools for the agent to use."""
        
        def get_dataframe_schema(query: str) -> str:
            """Get schema information about the dataframe (NO RAW DATA)."""
            if self.enable_column_rag:
                # Use RAG to find relevant columns
                relevant_cols = self.column_selector.select_columns(
                    query, 
                    max_columns=self.max_columns_in_context
                )
                focused_schema = self.column_selector.get_focused_schema(relevant_cols)
                schema_text = format_schema_for_prompt(focused_schema)
                
                return f"""
# Dataset Overview
- Total Rows: {len(self.df):,}
- Total Columns: {len(self.df.columns):,}
- Memory: {self.passport.passport['metadata']['memory_usage_mb']:.2f} MB

# Relevant Columns for Query: "{query}"
{schema_text}

**Note**: This dataset has {len(self.df.columns)} columns total. 
Showing only the {len(relevant_cols)} most relevant columns.
Use these column names EXACTLY as shown.
"""
            else:
                # Show all columns (for smaller datasets)
                return self.passport.to_prompt_context()
        
        def execute_pandas_code(code: str) -> str:
            """Execute Pandas code with self-healing."""
            try:
                # Use self-healing executor
                result = self.healing_executor.execute_with_healing(code)
                
                if result.success:
                    return json.dumps({
                        'success': True,
                        'result': result.result,
                        'attempts': result.attempt_number
                    }, default=str)
                else:
                    return json.dumps({
                        'success': False,
                        'error': result.error,
                        'attempts': result.attempt_number,
                        'help': 'Check column names and data types in schema'
                    }, default=str)
                    
            except Exception as e:
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }, default=str)
        
        def search_columns(query: str) -> str:
            """Search for relevant columns by semantic similarity."""
            if not self.enable_column_rag:
                return json.dumps({
                    'message': 'Column RAG not enabled',
                    'all_columns': list(self.df.columns)
                })
            
            relevant = self.column_store.search_columns(query, top_k=15)
            return json.dumps({
                'relevant_columns': [
                    {
                        'name': col['column_name'],
                        'relevance': col['relevance_score'],
                        'description': col['description'][:100]
                    }
                    for col in relevant
                ]
            }, indent=2)
        
        def get_data_quality_report(query: str) -> str:
            """Get data quality information."""
            quality = self.passport.passport['data_quality']
            stats = self.passport.passport['statistics']
            
            return json.dumps({
                'completeness_score': quality['completeness_score'],
                'total_nulls': stats['total_null_cells'],
                'null_percentage': stats['null_percentage'],
                'duplicate_rows': stats['duplicate_rows'],
                'issues': quality['issues'][:5],
                'warning': 'Consider handling nulls/duplicates before analysis'
            }, indent=2)
        
        return [
            Tool(
                name="get_dataframe_schema",
                func=get_dataframe_schema,
                description="""Get the schema and metadata of the DataFrame. 
                CRITICAL: This shows column names, types, and statistics WITHOUT showing raw data.
                Always use this FIRST to understand what columns are available.
                For large datasets (1000+ cols), this returns only the most relevant columns."""
            ),
            Tool(
                name="execute_pandas_code",
                func=execute_pandas_code,
                description="""Execute Python/Pandas code to analyze the DataFrame.
                The DataFrame is available as 'df'. 
                ALWAYS store your result in a variable called 'result'.
                This tool has SELF-HEALING: it will automatically fix common errors like typos in column names.
                Follow the Master Analyst patterns for comprehensive analysis."""
            ),
            Tool(
                name="search_columns",
                func=search_columns,
                description="""Search for columns related to your query using semantic search.
                Use this when you need to find specific columns in a large dataset (1000+ columns).
                Example: search_columns('revenue by city') -> finds 'Total_Revenue', 'City_Name', etc."""
            ),
            Tool(
                name="get_data_quality_report",
                func=get_data_quality_report,
                description="""Get information about data quality issues like nulls, duplicates, etc.
                Use this when you need to understand data completeness before analysis."""
            )
        ]
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent using ReAct pattern with expert prompts."""
        
        # Build context about dataset size
        dataset_info = f"""
Dataset: {len(self.df):,} rows × {len(self.df.columns):,} columns ({self.passport.passport['metadata']['memory_usage_mb']:.1f} MB)
Column RAG: {'Enabled' if self.enable_column_rag else 'Disabled'}
"""
        
        template = MASTER_ANALYST_SYSTEM_PROMPT + """

## Current Dataset
""" + dataset_info + """

## Available Tools
{tools}

Tool Names: {tool_names}

## CRITICAL CHART RULE
- NEVER save charts to files (no plt.savefig, no .png files, no matplotlib)
- ONLY return the aggregated DATA as a dictionary or dataframe
- The frontend will automatically create interactive visualizations from your data
- Example: result = df.groupby('Category')['Revenue'].sum().to_dict()

## Workflow

1. ALWAYS start with get_dataframe_schema to see available columns
2. For 1000+ column datasets, use search_columns to find relevant fields
3. Write comprehensive pandas code following the patterns above
4. Execute with execute_pandas_code (it will auto-fix errors)
5. Provide insights, not just numbers

## Response Format

Question: {input}
Thought: Let me understand the schema first
Action: get_dataframe_schema
Action Input: {input}
Observation: [schema info]
Thought: Now I'll write comprehensive analysis code
Action: execute_pandas_code
Action Input: [python code]
Observation: [results]
Thought: I now have enough information to provide a complete answer
Final Answer: [insight with context and recommendations]

{agent_scratchpad}"""

        prompt = PromptTemplate.from_template(template)
        
        agent = create_react_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=settings.AGENT_VERBOSE,
            max_iterations=settings.MAX_ITERATIONS,
            handle_parsing_errors=True,
            early_stopping_method="force",
            return_intermediate_steps=True
        )
    
    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Analyze data based on natural language query using schema-first approach.
        
        Args:
            query: Natural language question about the data
            
        Returns:
            Dictionary with analysis results, code, and insights
        """
        try:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"Dataset: {len(self.df):,} rows × {len(self.df.columns):,} columns")
            print(f"{'='*60}\n")
            
            # Run the agent
            response = self.agent.invoke({"input": query})
            
            # Extract the output
            output = response.get("output", str(response))

            # If LangChain hits an internal stop condition, avoid surfacing the raw message.
            if isinstance(output, str) and "agent stopped" in output.lower():
                output = (
                    "I couldn’t complete the full reasoning loop within my step/time budget. "
                    "Try asking a narrower question (one chart/metric at a time), or increase "
                    "`MAX_ITERATIONS` in the backend `.env`."
                )
            
            # Extract generated code from intermediate steps
            generated_code = None
            intermediate_steps = response.get("intermediate_steps", [])
            for action, observation in intermediate_steps:
                if hasattr(action, 'tool') and action.tool == 'execute_pandas_code':
                    generated_code = action.tool_input
                    break
            
            # Generate chart if applicable
            chart_data = None
            output_lower = output.lower() if isinstance(output, str) else ""
            should_skip_chart = any(
                phrase in output_lower
                for phrase in [
                    "does not contain",
                    "not found",
                    "no data file",
                    "encountered an error",
                    "analysis failed",
                ]
            )

            if generated_code and self._should_create_chart(query, response) and not should_skip_chart:
                print(f"[CHART] Attempting chart generation for query: {query[:50]}...")
                chart_data = self._generate_chart(query, generated_code)
                if chart_data:
                    print("[CHART] ✓ Chart generated successfully")
                else:
                    print("[CHART] ✗ Chart generation returned None (no suitable data/columns)")
                    # If LLM claims to have created a chart but we have no chart_data,
                    # append a clarification to the answer.
                    if "chart" in output.lower() and ("created" in output.lower() or "saved" in output.lower()):
                        output += (
                            "\n\n*Note: The code saves a chart file on the server, but it won't display here. "
                            "For interactive charts in this UI, ask me to 'show' or 'visualize' the data "
                            "without saving to a file.*"
                        )
            
            # Get execution summary
            exec_summary = self.healing_executor.get_execution_summary()
            
            return {
                "answer": output,
                "generated_code": generated_code,
                "chart_data": chart_data,
                "success": True,
                "metadata": {
                    "dataset_shape": self.df.shape,
                    "column_rag_used": self.enable_column_rag,
                    "execution_attempts": exec_summary.get("total_attempts", 1),
                    "self_healed": exec_summary.get("total_attempts", 1) > 1
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            return {
                "answer": f"I encountered an error while analyzing the data: {error_msg}",
                "generated_code": None,
                "chart_data": None,
                "success": False,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
    
    def _should_create_chart(self, query: str, response: Dict) -> bool:
        """Determine if a chart should be created based on the query."""
        chart_keywords = ['plot', 'chart', 'graph', 'visualize', 'show', 'trend', 'compare', 'distribution']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in chart_keywords)
    
    def _generate_chart(self, query: str, code: Optional[str]) -> Optional[Dict]:
        """Generate chart configuration based on query and code."""
        try:
            return generate_chart(self.df, query, code)
        except Exception as e:
            print(f"Chart generation error: {e}")
            return None
    
    def get_passport_summary(self) -> Dict[str, Any]:
        """Get summary of the data passport for debugging/inspection."""
        return {
            "shape": self.passport.passport['metadata']['shape'],
            "memory_mb": self.passport.passport['metadata']['memory_usage_mb'],
            "column_count": len(self.passport.passport['schema']),
            "sample_columns": [col['name'] for col in self.passport.passport['schema'][:10]],
            "data_quality_score": self.passport.passport['data_quality']['completeness_score'],
            "fingerprint": self.passport.passport['fingerprint']
        }


# Alias for backward compatibility
DataAnalystAgent = EnhancedDataAnalystAgent
