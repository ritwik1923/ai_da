import pandas as pd
import os
import sys
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_community.embeddings import OllamaEmbeddings

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Importing your newly refactored classes
try:
    from .utility.AnalysisToolFactory import AnalysisToolFactory
    from .utility.DataAnalystAgent import DataAnalystAgent
    from .utility.FewShotExampleStore import FewShotExampleStore
    from .utility.CodeGenerationService import CodeGenerationService
except ImportError:  # pragma: no cover
    try:
        from utility.AnalysisToolFactory import AnalysisToolFactory
        from utility.DataAnalystAgent import DataAnalystAgent
        from utility.FewShotExampleStore import FewShotExampleStore
        from utility.CodeGenerationService import CodeGenerationService
    except ImportError:
        from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory
        from app.agents.utility.DataAnalystAgent import DataAnalystAgent
        from app.agents.utility.FewShotExampleStore import FewShotExampleStore
        from app.agents.utility.CodeGenerationService import CodeGenerationService


# Importing your existing utilities
try:
    from ..utils.custom_llm import OllamaLocalLLM
    from ..utils.self_healing_executor import SelfHealingExecutor
    from ..utils.data_passport import generate_data_passport
except ImportError:  # pragma: no cover
    try:
        from app.utils.custom_llm import OllamaLocalLLM
        from app.utils.self_healing_executor import SelfHealingExecutor
        from app.utils.data_passport import generate_data_passport
    except ImportError:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        from utils.custom_llm import OllamaLocalLLM
        from utils.self_healing_executor import SelfHealingExecutor
        from utils.data_passport import generate_data_passport


# TODO make importing module agnostic and cleaner (try-except with relative imports is a bit hacky but ensures flexibility across environments)
def build_data_analyst_agent(df: pd.DataFrame, conversation_memory: list = None) -> DataAnalystAgent:
    """
    Factory function to assemble the EnhancedDataAnalystAgent and all its dependencies.
    """
    conversation_memory = conversation_memory or []

    # 1. Initialize Base Dependencies (LLMs and Embeddings)
    # If you ever want to switch to OpenAI, you ONLY change these lines.
    reasoning_llm = OllamaLocalLLM(model="llama3.1:8b", temperature=0.0)
    coding_llm = OllamaLocalLLM(model="deepseek-coder-v2:16b", temperature=0.0)
    embeddings_model = OllamaEmbeddings(model="llama3.1:8b")

    # 2. Generate Data Context
    print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
    data_passport = generate_data_passport(df, max_sample_rows=3)

    # 3. Initialize the Vector DB Repository
    # 3. Initialize the Vector DB Repository
    golden_examples = [
        
        # --- 1. NON-CHART / PANDAS AGGREGATION EXAMPLES ---
        {
            "task": "Which 3 categories have the highest total stock available?", 
            "code": "result = df.groupby('Category')['Stock'].sum().nlargest(3)"
        },
        {
            "task": "How many products contain the word 'Smart' anywhere in their name?", 
            "code": "result = len(df[df['Name'].str.contains('Smart', case=False, na=False)])"
        },
        {
            "task": "What is the exact median price of all products in the dataset?", 
            "code": "result = df['Price'].median()"
        },
        {
            "task": "What is the name and price of the single most expensive product?", 
            "code": "result = df.loc[df['Price'].idxmax(), ['Name', 'Price']].to_dict()"
        },
        {
            "task": "Calculate the average revenue for each product category.", 
            "code": "result = df.groupby('Category')['Revenue'].mean()"
        },
        {
            "task": "Find the most common color specifically among products that are on pre_order.", 
            "code": "result = df[df['Availability'] == 'pre_order']['Color'].mode().iloc[0]"
        },

        # --- 2. CHART / PLOTLY EXAMPLES (CRITICAL FIXES: Direct to 'result', No .show(), Includes Titles) ---
        {
            "task": "Create a bar chart showing the total stock for each brand.",
            "code": "result = px.bar(df.groupby('Brand', dropna=False)['Stock'].sum().reset_index(), x='Brand', y='Stock', title='Total Stock by Brand')"
        },
        {
            "task": "Show the trend of average price over time grouped by availability.",
            "code": "result = px.line(df.groupby(['Availability', 'Index'])['Price'].mean().reset_index(), x='Index', y='Price', color='Availability', title='Price Trend by Availability')"
        },
        {
            "task": "Make a pie chart showing the proportion of total stock by product category.",
            "code": "result = px.pie(df.groupby('Category')['Stock'].sum().reset_index(), names='Category', values='Stock', title='Stock Distribution by Category')"
        },
        {
            "task": "Visualize the relationship between price and stock levels.",
            "code": "result = px.scatter(df, x='Price', y='Stock', color='Category', title='Price vs Stock Relationship')"
        },
        {
            "task": "Show the distribution of product prices.",
            "code": "result = px.histogram(df, x='Price', nbins=30, title='Distribution of Prices')"
        }
    ]
    example_store = FewShotExampleStore(embeddings_model=embeddings_model, examples=golden_examples)

    # 4. Initialize Execution Engine
    executor = SelfHealingExecutor(df=df, max_retries=3)

    # 5. Wire up the Code Generation Service
    code_service = CodeGenerationService(
        coding_llm=coding_llm,
        example_store=example_store,
        df=df,
        executor=executor
    )

    # 6. Create LangChain Tools
    tool_factory = AnalysisToolFactory(
        data_passport=data_passport,
        code_service=code_service,
        df=df
    )
    tools = tool_factory.create_tools()

    # 7. Build the ReAct Agent
    # (Extracting this from the original setup to inject it into the final agent)
    schema_context = data_passport.to_prompt_context()
    history_text = "".join([f"{msg['role']}: {msg['content']}\n" for msg in conversation_memory])
    prompt = PromptTemplate(
        template="""You are a Data Analyst Manager... 
        Context: {schema_context}
        History: {history_text}
        Tools: {tool_names} {tools}
        Question: {input}
        
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

        {agent_scratchpad}""", # Keep your full original ReAct prompt here
        input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
        partial_variables={"schema_context": schema_context, "history_text": history_text}
    )
    
    langchain_agent = create_react_agent(reasoning_llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=langchain_agent,
        tools=tools,
        verbose=True, 
        max_iterations=4,
        handle_parsing_errors=True,
        return_intermediate_steps=True
    )
    print("Agent and tools initialized successfully.")
    # 8. Assemble the Final Facade
    return DataAnalystAgent(
        df=df,
        reasoning_llm=reasoning_llm,
        agent_executor=agent_executor,
        code_service=code_service
    )


# --- Usage Example ---
if __name__ == "__main__":
    # Load some dummy data
    demo_df = pd.DataFrame({"Category": ["A", "B", "A"], "Stock": [10, 20, 15]})
    
    # Build the agent
    agent = build_data_analyst_agent(demo_df)
    
    # Run a query
    result = agent.analyze("What is the total stock for category A?")
    print(result)