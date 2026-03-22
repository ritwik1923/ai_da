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
    from .utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore
    from .utility.CodeGenerationService import CodeGenerationService
except ImportError:  # pragma: no cover
    try:
        from utility.AnalysisToolFactory import AnalysisToolFactory
        from utility.DataAnalystAgent import DataAnalystAgent
        from utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore
        from utility.CodeGenerationService import CodeGenerationService
    except ImportError:
        from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory
        from app.agents.utility.DataAnalystAgent import DataAnalystAgent
        from app.agents.utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore
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
class AgentGlobals:
    """
    Holds heavy, dataset-independent components in memory.
    These are initialized ONCE when the backend server starts.
    """
    _initialized = False
    reasoning_llm = None
    coding_llm = None
    example_store = None
    react_example_store = None

    @classmethod
    def initialize(cls):
        if cls._initialized:
            return
            
        print("🚀 [Startup] Initializing Global LLMs and Vector DB...")
        
        # 1. Load LLMs
        cls.reasoning_llm = OllamaLocalLLM(model="llama3.1:8b", temperature=0.0)
        cls.coding_llm = OllamaLocalLLM(model="deepseek-coder-v2:16b", temperature=0.0)
        # 2. Initialize Vector DBs using our clean subclasses
        cls.example_store = Code_FewShotExampleStore(embeddings_model=cls.coding_llm)
        cls.react_example_store = ReAct_FewShotExampleStore(embeddings_model=cls.reasoning_llm)
        
        cls._initialized = True
        print("✅ [Startup] Global AI Resources Ready.")


# ==========================================
# 2. PER-REQUEST AGENT BUILDER
# ==========================================
def build_data_analyst_agent(df: pd.DataFrame, conversation_memory: list = None, current_query: str = "") -> DataAnalystAgent:
    """
    Factory function to assemble the EnhancedDataAnalystAgent.
    Now super fast because it reuses the global LLMs and Vector DB!
    """
    conversation_memory = conversation_memory or []

    # 1. Grab Global Dependencies (Instant)
    reasoning_llm = AgentGlobals.reasoning_llm
    coding_llm = AgentGlobals.coding_llm
    example_store = AgentGlobals.example_store
    react_examples_context = AgentGlobals.react_example_store

    # 2. Generate Request-Specific Data Context
    print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
    data_passport = generate_data_passport(df, max_sample_rows=3)

    # 3. Initialize Request-Specific Execution Engine
    executor = SelfHealingExecutor(df=df, max_retries=3)

    # 4. Wire up the Code Generation Service
    code_service = CodeGenerationService(
        coding_llm=coding_llm,
        example_store=example_store,
        df=df,
        executor=executor
    )

    # 5. Create Request-Specific LangChain Tools
    tool_factory = AnalysisToolFactory(
        data_passport=data_passport,
        code_service=code_service,
        df=df
    )
    tools = tool_factory.create_tools()
    # 1. Fetch dynamic ReAct examples based on what the user just asked!
    react_examples_context = AgentGlobals.react_example_store.get_context_string(current_query, k=1)
    # 6. Build the ReAct Agent Prompt (Depends on current df and chat history)
    schema_context = data_passport.to_prompt_context()
    history_text = "".join([f"{msg['role']}: {msg['content']}\n" for msg in conversation_memory])
    
    prompt = PromptTemplate(
        template="""You are a Data Analyst Manager... 
        Context: {schema_context}
        History: {history_text}
        Tools: {tool_names} {tools}
        Question: {input}
        
        ### EXAMPLES OF CORRECT FORMATTING ###
    Mimic this exact formatting for your response:
    {react_examples_context}
    ######################################
        
    ## Rules:
    1. Review the Schema and Previous Conversation. 
    2. If the data needed is missing, DO NOT use a tool. Proceed directly to Final Answer.
    3. If the data exists and you need to perform an analysis, call a tool.
    4. ALWAYS use get_dataframe_schema first if you need to check available columns.


    ## STRICT FORMATTING RULES (CRITICAL):
    You must choose EXACTLY ONE of the following options. 

    OPTION 1: Use a Tool (Do NOT include Final Answer)
    Thought: [your reasoning]
    Action: [MUST be EXACTLY one of: {tool_names}]
    

    OR

    OPTION 2: Give the Final Answer (Do NOT include Action)
    Thought: I already know the answer.
    Final Answer: [Your exact answer]

        {agent_scratchpad}""",
        input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
        partial_variables={
            "schema_context": schema_context, 
            "history_text": history_text,
            "react_examples_context": react_examples_context
        }
    )
    
    def _handle_parsing_error(error: Exception) -> str:
        return (
            "FORMATTING ERROR: Your response could not be parsed. "
            "You MUST start with 'Thought:'. "
            "Then, you must include either 'Action:' OR 'Final Answer:'. "
            "Do NOT use markdown like **Final Answer**."
        )
    
    # 7. Assemble the Agent
    langchain_agent = create_react_agent(reasoning_llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=langchain_agent,
        tools=tools,
        verbose=True, 
        max_iterations=4,
        handle_parsing_errors=_handle_parsing_error,
        return_intermediate_steps=True
    )
    
    # 8. Return the Final Facade
    return DataAnalystAgent(
        df=df,
        query=current_query,
        reasoning_llm=reasoning_llm,
        agent_executor=agent_executor,
        code_service=code_service
    )
    
