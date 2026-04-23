from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import logging
import uvicorn
import os

from app.core.config import settings
from app.core.database import engine, get_db
from app.models import models
from app.api import chat, files, analysis

# 1. FIX: Import AgentGlobals from your v3 agent file
from app.agents.AgentGlobals import AgentGlobals

logger = logging.getLogger(__name__)

# Monkey-patch Starlette to accept larger uploads
# Must be done BEFORE importing Starlette apps
from starlette.requests import Request
from starlette.datastructures import UploadFile

# Set upload limits based on environment
# Development: No limit (10GB) | Production: 100MB
upload_limit = settings.MAX_FILE_SIZE
Request.MAX_UPLOAD_SIZE = upload_limit
os.environ['STARLETTE_FORM_PARSE_MAX_SIZE'] = str(upload_limit)

env_display = f"[{settings.ENVIRONMENT.upper()}]" if settings.ENVIRONMENT else "[DEVELOPMENT]"
limit_mb = upload_limit / (1024 * 1024)
logger.info(f"📁 File Upload Limit {env_display}: {limit_mb:.0f}MB")

app = FastAPI(
    title="AI Data Analyst Agent",
    description="Autonomous data analysis agent with natural language interface",
    version="1.0.0",
)


@app.on_event("startup")
async def initialize_database() -> None:
    """Initialize databases without blocking app startup on connection failures."""
    
    # --- SQL Database Initialization ---
    try:
        models.Base.metadata.create_all(bind=engine)
        app.state.database_connected = True
        logger.info("✅ SQL Database initialized successfully.")
    except SQLAlchemyError as db_error:
        app.state.database_connected = False
        logger.error("❌ SQL Database initialization failed during startup: %s", db_error)
    
    # --- AI & Vector DB Initialization ---
    try:
        # This will load your LLMs and build the FAISS index in memory
        AgentGlobals.initialize()
        app.state.code_learning = AgentGlobals.learn_code_4r_feedback
        app.state.react_learning = AgentGlobals.learn_react_4r_feedback
        app.state.vector_database_connection = True
        logger.info("✅ AI Globals and Vector DB initialized successfully.")
    except Exception as e:
        app.state.vector_database_connection = False
        # 2. FIX: Updated logger message so you know exactly what failed
        logger.error("❌ AI & Vector DB initialization failed during startup: %s", e)
    

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Data Analyst Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        
        # 3. FIX: Expose the Vector DB status to the frontend
        return {
            "status": "healthy",
            "database": "connected",
            "database_initialized_on_startup": getattr(app.state, "database_connected", True),
            "vector_db_ready": getattr(app.state, "vector_database_connection", False)
        }
    except SQLAlchemyError as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "database_initialized_on_startup": getattr(app.state, "database_connected", False),
                "vector_db_ready": getattr(app.state, "vector_database_connection", False),
                "error": str(e)
            }
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )