from langchain_community.vectorstores.faiss import FAISS
from langchain_core.documents import Document

class FewShotExampleStore:
    """Manages storage and retrieval of safe coding examples."""
    
    def __init__(self, embeddings_model, examples: list[dict]):
        self.embeddings = embeddings_model
        self.vector_db = self._initialize_db(examples)

    def _initialize_db(self, examples: list[dict]) -> FAISS:
        docs = [Document(page_content=ex["task"], metadata={"code": ex["code"]}) for ex in examples]
        return FAISS.from_documents(docs, self.embeddings)

    def get_context_string(self, task_description: str, k: int = 2) -> str:
        similar_docs = self.vector_db.similarity_search(task_description, k=k)
        return "\n".join([
            f"Similar Task: {doc.page_content}\nVerified Code: {doc.metadata['code']}\n"
            for doc in similar_docs
        ])