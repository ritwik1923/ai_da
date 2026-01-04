"""
Column Vector Store - RAG for High-Dimensional Data (1000+ columns)
Uses semantic search to find relevant columns for queries.
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path


class ColumnVectorStore:
    """
    Manages semantic search over column metadata.
    Solves the "1000 columns problem" by retrieving only relevant columns
    instead of sending all column names to the LLM.
    """
    
    def __init__(self, 
                 collection_name: str = "columns",
                 persist_directory: Optional[str] = None,
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Args:
            collection_name: Name for the ChromaDB collection
            persist_directory: Where to persist the vector DB (None = in-memory)
            embedding_model: SentenceTransformer model to use for embeddings
        """
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        
        # Initialize embedding model
        self.embedder = SentenceTransformer(embedding_model)
        
        # Initialize ChromaDB
        if persist_directory:
            persist_path = Path(persist_directory)
            persist_path.mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=str(persist_path),
                settings=Settings(anonymized_telemetry=False)
            )
        else:
            self.client = chromadb.EphemeralClient(
                settings=Settings(anonymized_telemetry=False)
            )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Column metadata for semantic search"}
        )
    
    def add_columns(self, column_descriptions: Dict[str, str], metadata: Optional[Dict[str, Dict]] = None):
        """
        Add column descriptions to the vector store.
        
        Args:
            column_descriptions: Dict mapping column_name -> natural language description
            metadata: Optional dict mapping column_name -> additional metadata dict
        """
        if not column_descriptions:
            return
        
        column_names = list(column_descriptions.keys())
        descriptions = list(column_descriptions.values())
        
        # Generate embeddings
        embeddings = self.embedder.encode(descriptions, convert_to_numpy=True).tolist()
        
        # Prepare metadata
        metadatas = []
        for col_name in column_names:
            col_meta = {"column_name": col_name}
            if metadata and col_name in metadata:
                col_meta.update(metadata[col_name])
            metadatas.append(col_meta)
        
        # Add to collection
        self.collection.add(
            ids=column_names,
            embeddings=embeddings,
            documents=descriptions,
            metadatas=metadatas
        )
    
    def search_columns(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for columns relevant to a natural language query.
        
        Args:
            query: Natural language query (e.g., "revenue by city")
            top_k: Number of top columns to return
            
        Returns:
            List of dicts with column info and relevance scores
        """
        # Generate query embedding
        query_embedding = self.embedder.encode([query], convert_to_numpy=True).tolist()[0]
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Format results
        columns = []
        if results['ids'] and len(results['ids']) > 0:
            for i, col_id in enumerate(results['ids'][0]):
                columns.append({
                    "column_name": col_id,
                    "description": results['documents'][0][i] if results['documents'] else "",
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "relevance_score": 1 - results['distances'][0][i] if results['distances'] else 0.0
                })
        
        return columns
    
    def filter_columns(self, 
                      data_type: Optional[str] = None,
                      min_unique: Optional[int] = None,
                      max_null_pct: Optional[float] = None) -> List[str]:
        """
        Filter columns by metadata criteria.
        
        Args:
            data_type: Filter by data type ('numeric', 'categorical', 'datetime')
            min_unique: Minimum number of unique values
            max_null_pct: Maximum null percentage allowed
            
        Returns:
            List of column names matching criteria
        """
        where_clause = {}
        
        if data_type:
            where_clause["data_type"] = data_type
        
        # Note: ChromaDB's where clause is limited, so we fetch and filter
        all_results = self.collection.get()
        
        matching_columns = []
        for i, col_id in enumerate(all_results['ids']):
            metadata = all_results['metadatas'][i] if all_results['metadatas'] else {}
            
            # Apply filters
            if data_type and metadata.get('data_type') != data_type:
                continue
            
            if min_unique and metadata.get('unique_count', 0) < min_unique:
                continue
            
            if max_null_pct and metadata.get('null_percentage', 100) > max_null_pct:
                continue
            
            matching_columns.append(col_id)
        
        return matching_columns
    
    def get_all_columns(self) -> List[str]:
        """Get all column names in the store."""
        results = self.collection.get()
        return results['ids'] if results['ids'] else []
    
    def clear(self):
        """Clear all columns from the store."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Column metadata for semantic search"}
        )
    
    def get_column_context(self, query: str, top_k: int = 10) -> str:
        """
        Get a formatted string with relevant columns for LLM context.
        
        Args:
            query: User's natural language query
            top_k: Number of columns to retrieve
            
        Returns:
            Formatted string describing relevant columns
        """
        relevant_columns = self.search_columns(query, top_k)
        
        if not relevant_columns:
            return "No relevant columns found."
        
        context = f"## Relevant Columns for Query: '{query}'\n\n"
        context += f"Found {len(relevant_columns)} most relevant columns:\n\n"
        
        for i, col in enumerate(relevant_columns, 1):
            context += f"{i}. **{col['column_name']}** (relevance: {col['relevance_score']:.2f})\n"
            context += f"   {col['description']}\n"
            
            # Add metadata if available
            if col['metadata']:
                meta = col['metadata']
                if 'data_type' in meta:
                    context += f"   - Type: {meta['data_type']}\n"
                if 'unique_count' in meta:
                    context += f"   - Unique values: {meta['unique_count']}\n"
                if 'null_percentage' in meta:
                    context += f"   - Null %: {meta['null_percentage']:.1f}%\n"
            context += "\n"
        
        context += "\n**Instructions**: Use these column names in your pandas code. "
        context += "The DataFrame is available as `df`.\n"
        
        return context


class ColumnSelector:
    """
    High-level interface for intelligent column selection.
    Combines vector search with heuristics.
    """
    
    def __init__(self, vector_store: ColumnVectorStore, passport: Dict[str, Any]):
        """
        Args:
            vector_store: Initialized ColumnVectorStore
            passport: Data passport from DataPassport.to_dict()
        """
        self.vector_store = vector_store
        self.passport = passport
        self.schema = {col['name']: col for col in passport['schema']}
    
    def select_columns(self, query: str, max_columns: int = 20) -> List[str]:
        """
        Intelligently select columns for a query.
        Combines semantic search with data type heuristics.
        
        Args:
            query: Natural language query
            max_columns: Maximum number of columns to return
            
        Returns:
            List of column names to use
        """
        # Start with semantic search
        relevant_cols = self.vector_store.search_columns(query, top_k=max_columns)
        selected_columns = [col['column_name'] for col in relevant_cols]
        
        # Apply heuristics based on query keywords
        query_lower = query.lower()
        
        # If query mentions aggregation, prioritize numeric columns
        agg_keywords = ['sum', 'average', 'mean', 'total', 'count', 'max', 'min']
        if any(kw in query_lower for kw in agg_keywords):
            numeric_cols = [col['name'] for col in self.passport['schema'] 
                          if col['category'] == 'numeric']
            # Boost numeric columns in results
            for col in numeric_cols[:5]:
                if col not in selected_columns:
                    selected_columns.insert(0, col)
        
        # If query mentions time/trend, prioritize datetime columns
        time_keywords = ['trend', 'over time', 'by date', 'by month', 'by year', 'timeline']
        if any(kw in query_lower for kw in time_keywords):
            datetime_cols = [col['name'] for col in self.passport['schema'] 
                           if col['category'] == 'datetime']
            for col in datetime_cols:
                if col not in selected_columns:
                    selected_columns.insert(0, col)
        
        # Limit to max_columns
        return selected_columns[:max_columns]
    
    def get_focused_schema(self, columns: List[str]) -> List[Dict[str, Any]]:
        """
        Get schema information for only the selected columns.
        
        Args:
            columns: List of column names
            
        Returns:
            List of schema dicts for selected columns
        """
        return [self.schema[col] for col in columns if col in self.schema]
