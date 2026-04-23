import os
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.embeddings import OllamaEmbeddings

def inspect_brain(brain_path: str):
    print(f"\n==================================================")
    print(f"🔍 INSTRUCTING BRAIN: {brain_path}")
    print(f"==================================================\n")

    if not os.path.exists(brain_path):
        print(f"❌ Error: Folder '{brain_path}' does not exist yet.")
        return

    # 1. We must load the exact same embedding model used to save the DB
    print("⏳ Loading embedding model (this takes a few seconds)...")
    embeddings_model = OllamaEmbeddings(model="llama3.1:8b")

    # 2. Safely load the FAISS database from disk
    try:
        vector_db = FAISS.load_local(
            folder_path=brain_path, 
            embeddings=embeddings_model, 
            allow_dangerous_deserialization=True
        )
    except TypeError:
        # Fallback for older LangChain versions
        vector_db = FAISS.load_local(
            folder_path=brain_path, 
            embeddings=embeddings_model
        )

    # 3. Extract the underlying documents (the raw text/metadata)
    docstore = vector_db.docstore._dict
    
    # 4. Count the memories
    total_memories = len(docstore)
    learned_memories = sum(1 for doc in docstore.values() if doc.metadata.get("learned_dynamically"))
    
    print(f"📊 Stats: {total_memories} Total Memories ({learned_memories} Learned Dynamically)\n")

    # 5. Print out every memory
    for i, (doc_id, doc) in enumerate(docstore.items(), 1):
        is_learned = doc.metadata.get("learned_dynamically", False)
        
        # Add a visual tag so you can easily spot the ones the AI learned itself!
        tag = "🎓 [LEARNED FROM FEEDBACK]" if is_learned else "🛠️ [HARDCODED BASELINE]"
        
        print(f"--- Memory #{i} {tag} ---")
        print(f"🗣️ User Task : {doc.page_content}")
        print(f"🤖 Saved Code: \n{doc.metadata.get('code')}")
        print("-" * 50 + "\n")


if __name__ == "__main__":
    # Point these paths to wherever your agent_memory folder is located
    base_dir = "./agent_memory" 
    
    code_brain_path = os.path.join(base_dir, "code_brain")
    react_brain_path = os.path.join(base_dir, "react_brain")

    inspect_brain(code_brain_path)
    inspect_brain(react_brain_path)