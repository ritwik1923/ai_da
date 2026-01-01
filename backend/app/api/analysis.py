from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime
import time

from app.core.database import get_db
from app.models.models import UploadedFile, AnalysisResult
from app.schemas.schemas import AnalysisRequest, AnalysisResponse
from app.agents.data_analyst import DataAnalystAgent

router = APIRouter()


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
        # Load dataframe
        if file.file_type == '.csv':
            df = pd.read_csv(file.file_path)
        else:
            df = pd.read_excel(file.file_path)
        
        # Measure execution time
        start_time = time.time()
        
        # Create agent and analyze (no memory)
        agent = DataAnalystAgent(df)
        result = agent.analyze(request.query)
        
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
