from .utility.custom_llm import OllamaLocalLLM
from langchain_community.embeddings import OllamaEmbeddings
from .utility.FewShotExampleStore import Code_FewShotExampleStore, ReAct_FewShotExampleStore

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
        embeddings_model = OllamaEmbeddings(model="llama3.1:8b")

        # 3. Initialize Vector DBs using the Embeddings Model
        cls.example_store = Code_FewShotExampleStore(embeddings_model=embeddings_model)
        cls.react_example_store = ReAct_FewShotExampleStore(embeddings_model=embeddings_model)
        
        cls._initialized = True
        print("✅ [Startup] Global AI Resources Ready.")
    @classmethod
    def learn_react_4r_feedback(cls,task,return_code):
        # Send it to the Vector DB to learn permanently
        AgentGlobals.react_example_store.learn_new_example(
            task_description=task,
            successful_code=return_code
        )
    @classmethod
    def learn_code_4r_feedback(cls,task,return_code):
        # Send it to the Vector DB to learn permanently
        AgentGlobals.example_store.learn_new_example(
            task_description=task,
            successful_code=return_code
        )