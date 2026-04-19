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

class FewShotExampleStore_old:
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
        
import os
# from langchain_community.vectorstores.faiss import FAISS
# from langchain_core.documents import Document
# import traceback

class FewShotExampleStore:
    """Manages storage, retrieval, AND continuous learning of coding examples."""
    
        
    def __init__(self, embeddings_model, examples: list[dict], db_path: str):
        self.embeddings = embeddings_model
        self.examples = examples
        self.db_path = db_path # Where to save the brain on disk
        self.vector_db = None
        self._load_knowdeges()
 
    
    def _load_knowdeges(self):
        
        try:
            # 1. Try to load the existing brain from disk first
            if os.path.exists(self.db_path):
                print(f"🧠 Loading existing LLM memory from {self.db_path}...")                
                try:
                    # Try the newer LangChain syntax (v0.1.13+)
                    self.vector_db = FAISS.load_local(
                        folder_path=self.db_path, 
                        embeddings=self.embeddings, 
                        allow_dangerous_deserialization=True
                    )
                except TypeError:
                    # Fallback for older LangChain versions
                    self.vector_db = FAISS.load_local(
                        folder_path=self.db_path,
                        embeddings=self.embeddings
                    )
                    
            print(f"🧠 Loading existing LLM memory from golden example...") 
            # 2. If no brain exists, initialize with your hardcoded golden examples
            self.vector_db = self._initialize_db(self.examples)
            self.vector_db.save_local(self.db_path) # Save it immediately
            print(f"🌱 Loaded with existing knowledge...")
        except Exception as e:
            print(f"[FewShotExampleStore] ⚠️ Initialization failed. DB is offline. Error: {e}")
            
            
    def _initialize_db(self, examples: list[dict]) -> FAISS:
        if not examples: raise ValueError("The 'examples' list cannot be empty.")
        docs = []
        for ex in examples:
            metadata = {key: value for key, value in ex.items() if key != "task"}
            docs.append(Document(page_content=ex["task"], metadata=metadata))
        return FAISS.from_documents(docs, self.embeddings)

    def learn_new_example(self, task_description: str, successful_code: str):
        """
        TEACHES THE LLM: Injects a newly verified successful action into the Vector DB
        and permanently saves it to disk.
        """
        if self.vector_db is None:
            return
            
        print(f"🎓 LLM is learning a new successful action: '{task_description}'")
        try:
            # 1. Create the new memory document
            new_memory = Document(
                page_content=task_description, 
                metadata={"code": successful_code, "learned_dynamically": True}
            )
            # 2. Add it to the active FAISS index
            self.vector_db.add_documents([new_memory])
            # 3. Save the updated brain to disk
            self.vector_db.save_local(self.db_path)
            print("✅ Memory permanently saved to disk.")
        except Exception as e:
            print(f"❌ Failed to save new memory: {e}")

    def get_context_string(self, task_description: str, k: int = 2) -> str:
        # ... [Keep your existing get_context_string logic] ...
        if self.vector_db is None or not task_description: return ""
        try:
            similar_docs = self.get_similar_examples(task_description, k=k)
            return "\n".join([
                self._format_document_context(doc)
                for doc in similar_docs
            ])
        except Exception as e:
            return ""

    def get_similar_examples(self, task_description: str, k: int = 2) -> list[Document]:
        if self.vector_db is None or not task_description:
            return []
        safe_k = min(k, self.vector_db.index.ntotal)
        return self.vector_db.similarity_search(task_description, k=safe_k)

    def _format_document_context(self, doc: Document) -> str:
        lines = [f"Similar Task: {doc.page_content}"]
        if doc.metadata.get("chart_family"):
            lines.append(f"Chart Family: {doc.metadata['chart_family']}")
        if doc.metadata.get("template"):
            lines.append(f"Visualization Template: {doc.metadata['template']}")
        if doc.metadata.get("rationale"):
            lines.append(f"Rendering Guidance: {doc.metadata['rationale']}")
        if doc.metadata.get("code"):
            lines.append(f"Verified Code: {doc.metadata['code']}")
        return "\n".join(lines) + "\n"

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
            "task": "Show price distribution by category as a KPI chart.",
            "code": "Thought: This is a visualization-quality request, so I should use the dedicated visualization tool to retrieve the best rendering pattern from the vector DB before generating chart code.\nAction: visualisation_tool\nAction Input: Show price distribution by category as a KPI chart.\nObservation: Retrieved ranked horizontal bar guidance and generated chart code for the top categories.\nThought: I now know the correct visualization pattern and can confirm the KPI chart was prepared.\nFinal Answer: I have prepared a top-ranked category chart for price distribution using the visualization tool's reference examples."
        },
        {
            "task": "Hello! How are you?",
            "code": "Thought: The user is just greeting me. I do not need to use any data tools for this.\nFinal Answer: Hello! I am your AI Data Analyst. How can I help you explore your dataset today?"
        }
    ]

    def __init__(self, embeddings_model):
        super().__init__(
            embeddings_model=embeddings_model, 
            examples=self.react_golden_examples,
            db_path="./agent_memory/react_brain" # <-- Saves to this folder
        )
    def get_context_string(self, task_description: str, k: int = 1) -> str:
        if self.vector_db is None or not task_description: return ""
        try:
            safe_k = min(k, self.vector_db.index.ntotal)
            similar_docs = self.vector_db.similarity_search(task_description, k=safe_k)
            
            # Format as a conversation, NOT as "Similar Task/Verified Code"
            return "\n\n".join([
                f"Example Question: {doc.page_content}\nCorrect ReAct Trajectory:\n{doc.metadata['code']}"
                for doc in similar_docs
            ])
        except Exception:
            return ""   
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
            "code": "category_summary = df.groupby('Category', dropna=False).agg(Average_Price=('Price', 'mean'), Average_Stock=('Stock', 'mean'), Product_Count=('Category', 'size')).reset_index().sort_values('Product_Count', ascending=False).head(12)\nresult = px.scatter(category_summary, x='Average_Price', y='Average_Stock', color='Category', size='Product_Count', text='Category', title='Average Price vs Average Stock by Category')\nresult.update_traces(textposition='top center')"
        },
        {
            "task": "Show the distribution of product prices.",
            "code": "result = px.histogram(df, x='Price', nbins=30, title='Distribution of Prices')"
        }
    ]

    def __init__(self, embeddings_model):
        super().__init__(
            embeddings_model=embeddings_model, 
            examples=self.coding_golden_examples,
            db_path="./agent_memory/code_brain" # <-- Saves to this folder
        )
        
    @property
    def vector_db_type(self) -> str:
        return "FewShot for Coding"


class Visualization_FewShotExampleStore(FewShotExampleStore):

    visualization_golden_examples = [
        {
            "task": "Price Distribution by Category",
            "chart_family": "ranked_horizontal_bar",
            "template": "Aggregate price by category, sort descending, and display the top 10 categories as a horizontal bar chart using a sequential blue palette.",
            "rationale": "Category-heavy KPI charts become unreadable when every category is shown. Ranking and limiting to the top 10 makes the highest price-volume categories immediately clear.",
            "code": "category_price = df.groupby('Category', dropna=False)['Price'].sum().reset_index().sort_values('Price', ascending=False).head(10)\nresult = px.bar(category_price, x='Price', y='Category', orientation='h', color='Price', color_continuous_scale='Blues', title='Top 10 Categories by Total Price')\nresult.update_layout(coloraxis_showscale=False, yaxis={'categoryorder': 'total ascending'})"
        },
        {
            "task": "Top categories by stock or quantity",
            "chart_family": "ranked_horizontal_bar",
            "template": "Aggregate the metric by category, sort descending, and keep only the top 5 or top 10 categories before plotting.",
            "rationale": "Top-N ranking avoids clutter and keeps category comparisons readable in KPI dashboards.",
            "code": "top_categories = df.groupby('Category', dropna=False)['Stock'].sum().reset_index().sort_values('Stock', ascending=False).head(10)\nresult = px.bar(top_categories, x='Stock', y='Category', orientation='h', color='Stock', color_continuous_scale='Tealgrn', title='Top 10 Categories by Stock')\nresult.update_layout(coloraxis_showscale=False, yaxis={'categoryorder': 'total ascending'})"
        },
        {
            "task": "Relationship between two metrics by category",
            "chart_family": "aggregated_bubble_scatter",
            "template": "Aggregate both metrics by category, show one labeled point per category, and use bubble size for record count.",
            "rationale": "For KPI relationship charts, aggregated labeled bubbles preserve the comparison while avoiding unreadable point clouds.",
            "code": "category_summary = df.groupby('Category', dropna=False).agg(Average_Price=('Price', 'mean'), Average_Stock=('Stock', 'mean'), Product_Count=('Category', 'size')).reset_index().sort_values('Product_Count', ascending=False).head(12)\nresult = px.scatter(category_summary, x='Average_Price', y='Average_Stock', color='Category', size='Product_Count', title='Average Price vs Average Stock by Category')\nfor trace in result.data:\n    trace.text = [trace.name] * len(trace.x)\n    trace.mode = 'markers+text'\n    trace.textposition = 'top center'"
        }
    ]

    def __init__(self, embeddings_model):
        super().__init__(
            embeddings_model=embeddings_model,
            examples=self.visualization_golden_examples,
            db_path="./agent_memory/visualization_brain"
        )

    @property
    def vector_db_type(self) -> str:
        return "FewShot for Visualization"
    

# def inspect_brain(brain_path: str):
#     print(f"\n==================================================")
#     print(f"🔍 INSTRUCTING BRAIN: {brain_path}")
#     print(f"==================================================\n")

#     if not os.path.exists(brain_path):
#         print(f"❌ Error: Folder '{brain_path}' does not exist yet.")
#         return

#     # 1. We must load the exact same embedding model used to save the DB
#     print("⏳ Loading embedding model (this takes a few seconds)...")
#     embeddings_model = OllamaEmbeddings(model="llama3.1:8b")

#     # 2. Safely load the FAISS database from disk
#     try:
#         vector_db = FAISS.load_local(
#             folder_path=brain_path, 
#             embeddings=embeddings_model, 
#             allow_dangerous_deserialization=True
#         )
#     except TypeError:
#         # Fallback for older LangChain versions
#         vector_db = FAISS.load_local(
#             folder_path=brain_path, 
#             embeddings=embeddings_model
#         )

#     # 3. Extract the underlying documents (the raw text/metadata)
#     docstore = vector_db.docstore._dict
    
#     # 4. Count the memories
#     total_memories = len(docstore)
#     learned_memories = sum(1 for doc in docstore.values() if doc.metadata.get("learned_dynamically"))
    
#     print(f"📊 Stats: {total_memories} Total Memories ({learned_memories} Learned Dynamically)\n")

#     # 5. Print out every memory
#     for i, (doc_id, doc) in enumerate(docstore.items(), 1):
#         is_learned = doc.metadata.get("learned_dynamically", False)
        
#         # Add a visual tag so you can easily spot the ones the AI learned itself!
#         tag = "🎓 [LEARNED FROM FEEDBACK]" if is_learned else "🛠️ [HARDCODED BASELINE]"
        
#         print(f"--- Memory #{i} {tag} ---")
#         print(f"🗣️ User Task : {doc.page_content}")
#         print(f"🤖 Saved Code: \n{doc.metadata.get('code')}")
#         print("-" * 50 + "\n")


# if __name__ == "__main__":
#     # Point these paths to wherever your agent_memory folder is located
#     base_dir = "./agent_memory" 
    
#     code_brain_path = os.path.join(base_dir, "code_brain")
#     react_brain_path = os.path.join(base_dir, "react_brain")

#     inspect_brain(code_brain_path)
#     inspect_brain(react_brain_path)
    
    
