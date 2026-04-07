import pandas as pd
import os
import sys
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.prompts import PromptTemplate
from langchain_community.embeddings import OllamaEmbeddings

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Importing your newly refactored classes
try:
    from ..utility.AnalysisToolFactory import AnalysisToolFactory
    from ..utility.AgentGlobals import AgentGlobals
    from ..DataAnalystAgent import DataAnalystAgent
    from ..utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore
    from ..utility.CodeGenerationService import CodeGenerationService
except ImportError:  # pragma: no cover
    try:
        from utility.AnalysisToolFactory import AnalysisToolFactory
        from utility.AgentGlobals import AgentGlobals
        from backend.app.agents.DataAnalystAgent import DataAnalystAgent
        from utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore
        from utility.CodeGenerationService import CodeGenerationService
        import utility.AgentGlobals
    except ImportError:
        from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory
        from app.agents.utility.AgentGlobals import AgentGlobals
        from backend.app.agents.DataAnalystAgent import DataAnalystAgent
        from app.agents.utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore
        from app.agents.utility.CodeGenerationService import CodeGenerationService
        import app.agents.utility.AgentGlobals


# Importing your existing utilities
try:
    from ..utility.custom_llm import OllamaLocalLLM
    from ...utils.self_healing_executor import SelfHealingExecutor
    from ...utils.data_passport import generate_data_passport
    from ...utils.logger import get_production_logger
except ImportError:  # pragma: no cover
    try:
        from backend.app.agents.utility.custom_llm import OllamaLocalLLM
        from app.utils.self_healing_executor import SelfHealingExecutor
        from app.utils.data_passport import generate_data_passport
        from app.utils.logger import get_production_logger
    except ImportError:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        from backend.app.agents.utility.custom_llm import OllamaLocalLLM
        from utils.self_healing_executor import SelfHealingExecutor
        from utils.data_passport import generate_data_passport
        from utils.logger import get_production_logger
        
        
logger = get_production_logger("ai_da.globals")

# ==========================================
# 2. PER-REQUEST AGENT BUILDER
# ==========================================
def build_data_analyst_agent() -> DataAnalystAgent:
    """
    Factory function to assemble the EnhancedDataAnalystAgent.
    Now super fast because it reuses the global LLMs and Vector DB!
    """
    # conversation_memory = conversation_memory or []

    # 1. Grab Global Dependencies (Instant)
    reasoning_llm = AgentGlobals.reasoning_llm
    coding_llm = AgentGlobals.coding_llm
    example_store = AgentGlobals.example_store
    react_examples_context = AgentGlobals.react_example_store

    # 2. Generate Request-Specific Data Context
    # print(f"Generating data passport for {len(df)} rows × {len(df.columns)} columns...")
    # data_passport = generate_data_passport(df, max_sample_rows=3)

    # 3. Initialize Request-Specific Execution Engine
    # executor = SelfHealingExecutor(df=df, max_retries=3)

    # 4. Wire up the Code Generation Service
    # code_service = CodeGenerationService(
    #     coding_llm=coding_llm,
    #     example_store=example_store,
    #     df=df,
    #     executor=executor
    # )

    # # 5. Create Request-Specific LangChain Tools
    # tool_factory = AnalysisToolFactory(
    #     data_passport=data_passport,
    #     code_service=code_service,
    #     df=df
    # )
    # tools = tool_factory.create_tools()
    # # 1. Fetch dynamic ReAct examples based on what the user just asked!
    # react_examples_context = AgentGlobals.react_example_store.get_context_string(current_query, k=1)
    # # 6. Build the ReAct Agent Prompt (Depends on current df and chat history)
    # schema_context = data_passport.to_prompt_context()
    # history_text = "".join([f"{msg['role']}: {msg['content']}\n" for msg in conversation_memory])
    
    # prompt = PromptTemplate(
    #     template="""You are a Data Analyst Manager... 
    #     Context: {schema_context}
    #     History: {history_text}
    #     Tools: {tool_names} {tools}
    #     Question: {input}
        
    #     ### EXAMPLES OF CORRECT FORMATTING ###
    # Mimic this exact formatting for your response:
    # {react_examples_context}
    # ######################################
        
    # ## Rules:
    # 1. Review the Schema and Previous Conversation. 
    # 2. If the data needed is missing, DO NOT use a tool. Proceed directly to Final Answer.
    # 3. If the data exists and you need to perform an analysis, call a tool.
    # 4. ALWAYS use get_dataframe_schema first if you need to check available columns.


    # ## STRICT FORMATTING RULES (CRITICAL):
    # You must choose EXACTLY ONE of the following options. 

    # OPTION 1: Use a Tool (Do NOT include Final Answer)
    # Thought: [your reasoning]
    # Action: [MUST be EXACTLY one of: {tool_names}]
    

    # OR

    # OPTION 2: Give the Final Answer (Do NOT include Action)
    # Thought: I already know the answer.
    # Final Answer: [Your exact answer]

    #     {agent_scratchpad}""",
    #     input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
    #     partial_variables={
    #         "schema_context": schema_context, 
    #         "history_text": history_text,
    #         "react_examples_context": react_examples_context
    #     }
    # )
    prompt = PromptTemplate(
        template="""You are a strict Data Analyst Manager.
        Context: {schema_context}
        History: {history_text}
        Tools: {tool_names} {tools}
        
    ### EXAMPLES OF CORRECT FORMATTING ###
    Mimic this exact Thought/Action/Observation formatting:
    {react_examples_context}
    ######################################
        
    ## Rules:
    1. If you call a tool, you will receive an 'Observation'.
    2. Use that 'Observation' IMMEDIATELY to provide your 'Final Answer'.
    3. DO NOT start a new analysis or ask new questions.
    4. Review the Schema and Previous Conversation. 
    5. If you need to perform an analysis, use a tool.
    6. You run in a loop. After you output an Action, the system will execute it and return an "Observation:". 
    7. Once you see the "Observation:", you MUST proceed to OPTION 2 and give the Final Answer.

    ## STRICT FORMATTING RULES (CRITICAL):
    You must choose EXACTLY ONE of the following options per response. 
    DO NOT USE MARKDOWN. NEVER use `##`, `**`, or bold text for the keywords. They must be exactly "Thought:", "Action:", "Action Input:", and "Final Answer:".

    OPTION 1: Use a Tool (Do NOT include Final Answer)
    Thought: [your reasoning]
    Action: [MUST be EXACTLY one of: {tool_names}]
    Action Input: [Provide the tool input]

    OR

    OPTION 2: Give the Final Answer (Do NOT include Action)
    Thought: Based on the observation, I now know the answer.
    Final Answer: [Your exact answer]

    ---
    Question: {input}
    {agent_scratchpad}""",
        input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
        partial_variables={
            "schema_context": schema_context, 
            "history_text": history_text,
            "react_examples_context": react_examples_context
        }
    )
    def _handle_parsing_error(error: Exception) -> str:
        error_str = str(error)
        
        # If the LLM tried to do an Action and a Final Answer at the same time
        if "both a final answer and a parse-able action" in error_str:
            return (
                "FORMATTING ERROR: You provided BOTH an Action and a Final Answer. "
                "You must choose ONLY ONE. If you have the answer, use 'Thought:' followed by 'Final Answer:'."
            )
            
        # Standard strict formatting reminder
        return (
            "CRITICAL FORMATTING ERROR. LangChain could not parse your response. "
            "1. Remove ALL markdown headers (like ##) and bolding (**). "
            "2. Ensure your keywords are exactly 'Thought:', 'Action:', 'Action Input:', or 'Final Answer:'.\n"
            "Please try again using the exact unformatted keywords."
        )
    
    # 7. Assemble the Agent
    # langchain_agent = create_react_agent(reasoning_llm, tools, prompt)
    # agent_executor = AgentExecutor(
    #     agent=langchain_agent,
    #     tools=tools,
    #     verbose=True, 
    #     max_iterations=4,
    #     handle_parsing_errors=_handle_parsing_error,
    #     return_intermediate_steps=True
    # )
    
    # 8. Return the Final Facade
    return DataAnalystAgent(
        # executor=executor,
        reasoning_llm=reasoning_llm,
        coding_llm=coding_llm,

        example_store=example_store,
        react_store=react_examples_context,
        # data_passport=data_passport
        
    )
    
        # query: str,
        # df: pd.DataFrame, 
        # reasoning_llm, 
        # coding_llm, 
        # example_store: AgentGlobals, 
        # react_store: AgentGlobals,
        # data_passport