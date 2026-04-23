"""
Integration Guide: Adding Schema-First Architecture to Existing API

This shows how to integrate the new EnhancedDataAnalystAgent into your existing
FastAPI application without breaking existing functionality.
"""

# ============================================================================
# OPTION 1: Feature Flag (Recommended for A/B Testing)
# ============================================================================

# File: backend/app/api/analyze.py

from fastapi import APIRouter, HTTPException, Depends
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.agents.data_analyst import DataAnalystAgent  # Old
from app.agents.data_analyst_v2 import EnhancedDataAnalystAgent  # New
import os
import pandas as pd

router = APIRouter()

# Feature flag - can be controlled via environment variable
USE_SCHEMA_FIRST = os.getenv("USE_SCHEMA_FIRST", "true").lower() == "true"
COLUMN_RAG_THRESHOLD = int(os.getenv("COLUMN_RAG_THRESHOLD", "50"))


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(request: AnalyzeRequest):
    """
    Analyze data using natural language query.
    Automatically uses schema-first approach for large datasets.
    """
    try:
        # Load the DataFrame
        df = load_dataframe(request.file_id)
        
        # Choose agent based on feature flag and dataset size
        if USE_SCHEMA_FIRST:
            # Use new schema-first agent
            agent = EnhancedDataAnalystAgent(
                df=df,
                conversation_memory=request.conversation_history,
                enable_column_rag=len(df.columns) > COLUMN_RAG_THRESHOLD,
                max_columns_in_context=20
            )
        else:
            # Use original agent
            agent = DataAnalystAgent(
                df=df,
                conversation_memory=request.conversation_history
            )
        
        # Analyze (same interface for both agents!)
        result = agent.analyze(request.query)
        
        # Add metadata about which agent was used
        result['agent_version'] = 'v2-schema-first' if USE_SCHEMA_FIRST else 'v1-original'
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OPTION 2: Direct Replacement (Simplest)
# ============================================================================

# File: backend/app/api/analyze.py

from fastapi import APIRouter, HTTPException
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
# Import new agent with alias for backward compatibility
from app.agents.data_analyst_v2 import EnhancedDataAnalystAgent as DataAnalystAgent
import pandas as pd

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(request: AnalyzeRequest):
    """Analyze data using natural language query."""
    try:
        df = load_dataframe(request.file_id)
        
        # Uses EnhancedDataAnalystAgent transparently
        agent = DataAnalystAgent(
            df=df,
            conversation_memory=request.conversation_history
        )
        
        result = agent.analyze(request.query)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OPTION 3: Auto-Select Based on Dataset Size (Smart)
# ============================================================================

# File: backend/app/api/analyze.py

from fastapi import APIRouter, HTTPException
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.agents.data_analyst import DataAnalystAgent
from app.agents.data_analyst_v2 import EnhancedDataAnalystAgent
import pandas as pd

router = APIRouter()

# Thresholds
LARGE_DATASET_ROWS = 10000
WIDE_DATASET_COLS = 50


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(request: AnalyzeRequest):
    """
    Analyze data using natural language query.
    Automatically chooses optimal agent based on dataset size.
    """
    try:
        df = load_dataframe(request.file_id)
        
        # Auto-select agent based on dataset characteristics
        is_large = len(df) > LARGE_DATASET_ROWS
        is_wide = len(df.columns) > WIDE_DATASET_COLS
        
        if is_large or is_wide:
            # Use schema-first agent for large/wide datasets
            agent = EnhancedDataAnalystAgent(
                df=df,
                conversation_memory=request.conversation_history,
                enable_column_rag=is_wide
            )
            agent_used = 'enhanced-schema-first'
        else:
            # Use original agent for small datasets
            agent = DataAnalystAgent(
                df=df,
                conversation_memory=request.conversation_history
            )
            agent_used = 'original'
        
        result = agent.analyze(request.query)
        
        # Add metadata
        result['metadata'] = {
            **result.get('metadata', {}),
            'agent_used': agent_used,
            'dataset_size': {'rows': len(df), 'cols': len(df.columns)}
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OPTION 4: User Choice (Let User Decide)
# ============================================================================

# File: backend/app/schemas/analyze.py (update schema)

from pydantic import BaseModel
from typing import Optional, List

class AnalyzeRequest(BaseModel):
    file_id: str
    query: str
    conversation_history: Optional[List[dict]] = None
    use_schema_first: Optional[bool] = True  # New field
    enable_column_rag: Optional[bool] = None  # New field (auto if None)


# File: backend/app/api/analyze.py

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(request: AnalyzeRequest):
    """Analyze data with user-specified agent."""
    try:
        df = load_dataframe(request.file_id)
        
        if request.use_schema_first:
            # Auto-enable RAG if needed
            enable_rag = request.enable_column_rag
            if enable_rag is None:
                enable_rag = len(df.columns) > 50
            
            agent = EnhancedDataAnalystAgent(
                df=df,
                conversation_memory=request.conversation_history,
                enable_column_rag=enable_rag
            )
        else:
            agent = DataAnalystAgent(
                df=df,
                conversation_memory=request.conversation_history
            )
        
        result = agent.analyze(request.query)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Environment Variables (.env file)
# ============================================================================

"""
# Add these to your .env file:

# Enable schema-first architecture (true/false)
USE_SCHEMA_FIRST=true

# Threshold for enabling column RAG (number of columns)
COLUMN_RAG_THRESHOLD=50

# Maximum columns to include in LLM context
MAX_COLUMNS_IN_CONTEXT=20

# Maximum retries for self-healing executor
MAX_CODE_RETRIES=3
"""


# ============================================================================
# Testing the Integration
# ============================================================================

"""
# Test with small dataset (should work with both agents)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "abc123",
    "query": "What is the average revenue?"
  }'

# Test with large dataset (should use schema-first)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "large_dataset_id",
    "query": "Show me sales trends over time"
  }'

# Test with conversation history
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "abc123",
    "query": "Which region performed best?",
    "conversation_history": [
      {"role": "user", "content": "What is total revenue?"},
      {"role": "assistant", "content": "Total revenue is $1.2M"}
    ]
  }'
"""


# ============================================================================
# Monitoring & Logging
# ============================================================================

# Add logging to track which agent is being used

import logging

logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(request: AnalyzeRequest):
    try:
        df = load_dataframe(request.file_id)
        
        # Log dataset characteristics
        logger.info(f"Analyzing dataset: {len(df)} rows × {len(df.columns)} columns")
        
        if USE_SCHEMA_FIRST:
            agent = EnhancedDataAnalystAgent(df=df)
            logger.info("Using EnhancedDataAnalystAgent (schema-first)")
        else:
            agent = DataAnalystAgent(df=df)
            logger.info("Using DataAnalystAgent (original)")
        
        result = agent.analyze(request.query)
        
        # Log execution stats
        if 'metadata' in result:
            logger.info(f"Execution stats: {result['metadata']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Gradual Rollout Strategy
# ============================================================================

"""
Recommended rollout approach:

Week 1: Feature flag OFF (0% traffic)
- Deploy code with feature flag
- Test manually with select files
- Monitor logs and metrics

Week 2: Feature flag ON for large datasets only (20% traffic)
- Enable for datasets > 10k rows or > 50 columns
- Monitor performance and errors
- Collect feedback

Week 3: Feature flag ON for 50% of traffic
- A/B test both agents
- Compare response times
- Compare answer quality

Week 4: Feature flag ON for 100% of traffic
- Full rollout
- Keep original agent as fallback
- Monitor for any issues

Week 5: Remove old agent (optional)
- If no issues, deprecate old agent
- Update documentation
- Clean up code
"""


# ============================================================================
# Error Handling & Fallback
# ============================================================================

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(request: AnalyzeRequest):
    """Analyze with automatic fallback to original agent on error."""
    try:
        df = load_dataframe(request.file_id)
        
        # Try new agent first
        try:
            agent = EnhancedDataAnalystAgent(df=df)
            result = agent.analyze(request.query)
            result['agent_used'] = 'enhanced'
            return result
            
        except Exception as e:
            # Log error but don't fail
            logger.warning(f"Enhanced agent failed: {e}. Falling back to original.")
            
            # Fallback to original agent
            agent = DataAnalystAgent(df=df)
            result = agent.analyze(request.query)
            result['agent_used'] = 'original-fallback'
            result['fallback_reason'] = str(e)
            return result
            
    except Exception as e:
        logger.error(f"All agents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Summary
# ============================================================================

"""
Choose your integration approach:

1. Feature Flag (RECOMMENDED)
   - Safest for production
   - Easy to toggle on/off
   - Good for A/B testing
   - Use: Option 1

2. Direct Replacement
   - Simplest code change
   - Assumes new agent is stable
   - Use: Option 2

3. Auto-Select
   - Best user experience
   - Automatically optimizes
   - Use: Option 3

4. User Choice
   - Most flexible
   - Requires frontend changes
   - Use: Option 4

For most cases, start with Option 1 (Feature Flag) or Option 3 (Auto-Select).
"""
