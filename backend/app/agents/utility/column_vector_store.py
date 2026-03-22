import os
import sys

from langchain_community.embeddings import OllamaEmbeddings
# Importing your existing utilities

try:
    from app.utils.custom_llm import OllamaLocalLLM
    from FewShotExampleStore import FewShotExampleStore
except ImportError:
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from utils.custom_llm import OllamaLocalLLM


# ... [Keep all your imports and try/except blocks exactly the same] ...

# ==========================================
# 1. GLOBAL DEPENDENCY MANAGER (SINGLETON)
# ==========================================
class AgentGlobals:
    """
    Holds heavy, dataset-independent components in memory.
    These are initialized ONCE when the backend server starts.
    """
    _initialized = False
    reasoning_llm = None
    coding_llm = None
    example_store = None

    @classmethod
    def initialize(cls):
        if cls._initialized:
            return
            
        print("🚀 [Startup] Initializing Global LLMs and Vector DB...")
        
        # 1. Load LLMs
        cls.reasoning_llm = OllamaLocalLLM(model="llama3.1:8b", temperature=0.0)
        cls.coding_llm = OllamaLocalLLM(model="deepseek-coder-v2:16b", temperature=0.0)
        embeddings_model = OllamaEmbeddings(model="llama3.1:8b")

        # 2. Initialize Vector DB
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

            # --- 2. CHART / PLOTLY EXAMPLES ---
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
        
        # Build FAISS index in memory
        cls.example_store = FewShotExampleStore(embeddings_model=embeddings_model, examples=golden_examples)
        
        # --- 2. NEW: ReAct Vector DB for Llama 3.1 ---
        # These examples teach the LLM exactly how to use tools and format its answers.
        react_golden_examples = [
            {
                "task": "What is the median price of all products?",
                "code": "Thought: I need to calculate the median price using the analysis tool.\nAction: execute_analysis\nAction Input: Calculate the median price.\nObservation: 407.5\nThought: The analysis tool returned 407.5. I will now format this as the final answer.\nFinal Answer: The exact median price of all products is 407.5."
            },
            {
                "task": "What columns are in the dataset?",
                "code": "Thought: The user is asking about the dataset schema. I need to check the available columns.\nAction: get_dataframe_schema\nAction Input: schema\nObservation: Columns are Name, Price, Category.\nThought: I have the schema and can answer the user.\nFinal Answer: The dataset contains the following columns: Name, Price, and Category."
            },
            {
                "task": "Create a bar chart of the top 5 brands.",
                "code": "Thought: The user wants a visualization. I will pass this exact request to the analysis tool to generate a chart.\nAction: execute_analysis\nAction Input: Create a bar chart of the top 5 brands.\nObservation: Generated chart.\nThought: The chart was successfully generated.\nFinal Answer: I have generated the bar chart showing the top 5 brands for you."
            },
            {
                "task": "Hello! How are you?",
                "code": "Thought: The user is just greeting me. I do not need to use any data tools for this.\nFinal Answer: Hello! I am your AI Data Analyst. How can I help you explore your dataset today?"
            }
        ]
        cls.react_example_store = FewShotExampleStore(embeddings_model=embeddings_model, examples=react_golden_examples)
        
        cls._initialized = True
        print("✅ [Startup] Global AI Resources Ready.")

