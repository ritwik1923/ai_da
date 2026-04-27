from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime
import time
from starlette.concurrency import run_in_threadpool

from app.core.config import resolve_upload_path
from app.core.database import get_db
from app.models.models import UploadedFile, AnalysisResult
from app.schemas.schemas import AnalysisRequest, AnalysisResponse
# from backend.app.agents.extra.data_analyst_v3 import DataAnalystAgent

router = APIRouter()


def _load_dataframe(file_type: str, file_path: str) -> pd.DataFrame:
    if file_type == '.csv':
        return pd.read_csv(file_path)
    return pd.read_excel(file_path)


# def _run_agent_analysis(df: pd.DataFrame, query: str):
#     agent = DataAnalystAgent(df)
#     return agent.analyze(query)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_data(
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze data with a single query (no conversation memory)
    """
    
    # Get file
    file = db.query(UploadedFile).filter(UploadedFile.id == request.file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        df = await run_in_threadpool(_load_dataframe, file.file_type, resolve_upload_path(file.file_path))
        
        # Measure execution time
        start_time = time.time()
        
        result = await run_in_threadpool(_run_agent_analysis, df, request.query)
        
        execution_time = int((time.time() - start_time) * 1000)  # milliseconds
        
        # Save analysis result
        analysis = AnalysisResult(
            file_id=request.file_id,
            query=request.query,
            generated_code=result.get("generated_code", ""),
            result_data=result.get("execution_result"),
            chart_config=result.get("chart_data"),
            execution_time=execution_time
        )
        db.add(analysis)
        db.commit()
        
        return AnalysisResponse(
            query=request.query,
            answer=result["answer"],
            generated_code=result.get("generated_code", ""),
            result_data=result.get("execution_result"),
            chart_data=result.get("chart_data"),
            execution_time=execution_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/history/{file_id}")
async def get_analysis_history(
    file_id: int,
    db: Session = Depends(get_db)
):
    """
    Get analysis history for a file
    """
    results = db.query(AnalysisResult).filter(
        AnalysisResult.file_id == file_id
    ).order_by(AnalysisResult.created_at.desc()).all()
    
    return results
