from langchain_community.vectorstores.faiss import FAISS
from langchain_core.documents import Document
import traceback

# ==========================================
# CUSTOM EXCEPTIONS
# ==========================================
class VectorDBInitializationError(Exception):
    """Raised when FAISS fails to build the index (e.g., embedding model offline)."""
    pass

class MalformedExampleError(Exception):
    """Raised when the golden examples list is missing required keys."""
    pass

class FewShotExampleStore:
    """Manages storage and retrieval of safe coding examples with graceful fallbacks."""
    
    def __init__(self, embeddings_model, examples: list[dict]):
        self.embeddings = embeddings_model
        self.vector_db = None
        
        try:
            self.vector_db = self._initialize_db(examples)
            print(f"[FewShotExampleStore] ✅ Successfully initialized FAISS with {len(examples)} examples.")
        except Exception as e:
            # We catch this here so the main app doesn't crash if embeddings fail on startup
            print(f"[FewShotExampleStore] ⚠️ Initialization failed. DB is offline. Error: {e}")

    def _initialize_db(self, examples: list[dict]) -> FAISS:
        if not examples:
            raise ValueError("The 'examples' list cannot be empty.")
            
        docs = []
        for index, ex in enumerate(examples):
            try:
                # Validation: Catch typos in your golden_examples dictionary keys
                docs.append(Document(page_content=ex["task"], metadata={"code": ex["code"]}))
            except KeyError as e:
                raise MalformedExampleError(f"Example at index {index} is missing required key: {e}")
            except TypeError as e:
                raise MalformedExampleError(f"Example at index {index} is not a valid dictionary. Error: {e}")
                
        try:
            # This is the riskiest call: it hits the embedding model (e.g., Ollama) 
            # and compiles the FAISS index in C++.
            return FAISS.from_documents(docs, self.embeddings)
        except Exception as e:
            raise VectorDBInitializationError(f"Failed to generate embeddings or build FAISS index: {e}")

    def get_context_string(self, task_description: str, k: int = 2) -> str:
        """
        Retrieves matching examples safely. If it fails, it returns an empty string
        so the prompt generation can still proceed without examples.
        """
        # 1. Guardrail: DB never initialized
        if self.vector_db is None:
            print("[FewShotExampleStore] ⚠️ Vector DB is offline. Returning empty context.")
            return ""
            
        # 2. Guardrail: Bad input
        if not task_description or not isinstance(task_description, str):
            print("[FewShotExampleStore] ⚠️ Invalid task description provided to similarity search.")
            return ""

        try:
            # 3. Guardrail: Prevent FAISS warning if k > number of documents in DB
            num_docs = self.vector_db.index.ntotal
            safe_k = min(k, num_docs)
            
            # Perform the search
            similar_docs = self.vector_db.similarity_search(task_description, k=safe_k)
            
            return "\n".join([
                f"Similar Task: {doc.page_content}\nVerified Code: {doc.metadata['code']}\n"
                for doc in similar_docs
            ])
            
        except Exception as e:
            # Catching generic exceptions here (like embedding API timeouts during search)
            # We return "" instead of raising, so the LLM pipeline stays alive!
            error_traceback = traceback.format_exc()
            print(f"[FewShotExampleStore] ❌ Similarity search failed: {e}\n{error_traceback}")
            return ""
        
class ReAct_FewShotExampleStore(FewShotExampleStore):
    
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

    def __init__(self, embeddings_model):
        # Automatically pass the ReAct examples to the parent FewShotExampleStore
        super().__init__(embeddings_model=embeddings_model, examples=self.react_golden_examples)
        
    @property
    def vector_db_type(self) -> str:
        return "ReAct for Reasoning"
    

class Code_FewShotExampleStore(FewShotExampleStore):
    
    coding_golden_examples = [
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

    def __init__(self, embeddings_model):
        # Automatically pass the Coding examples to the parent FewShotExampleStore
        super().__init__(embeddings_model=embeddings_model, examples=self.coding_golden_examples)
        
    @property
    def vector_db_type(self) -> str:
        return "FewShot for Coding"

