from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import uuid
import asyncio
import json
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.config import settings, resolve_upload_path
from app.models.models import UploadedFile
from app.schemas.schemas import FileUploadResponse, KPIResponse, DataQualityInsight, AnalysisInsight
from app.agents.DataAnalystAgent import DataAnalystAgent as ai_engg

router = APIRouter()


def _read_dataframe(file_ext: str, file_path: str) -> pd.DataFrame:
    if file_ext == '.csv':
        return pd.read_csv(file_path)
    if file_ext in ['.xlsx', '.xls']:
        return pd.read_excel(file_path)
    raise ValueError("Unsupported file format")

# Ensure upload directory exists
Path(resolve_upload_path(settings.UPLOAD_DIR)).mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV or Excel file for analysis
    """
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    # TODO : save the files in remote storage like S3, GCP, Azure Blob Storage etc.
    file_path = resolve_upload_path(os.path.join(settings.UPLOAD_DIR, unique_filename))
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(content)
    
    try:
        df = await run_in_threadpool(_read_dataframe, file_ext, file_path)
        
        # Extract metadata
        columns_info = []
        for col in df.columns:
            columns_info.append({
                "name": col,
                "dtype": str(df[col].dtype)
            })
        
        # Create database record
        db_file = UploadedFile(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            file_type=file_ext,
            columns=columns_info,
            row_count=len(df)
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        return FileUploadResponse(
            id=db_file.id,
            filename=db_file.filename,
            original_filename=db_file.original_filename,
            file_size=db_file.file_size,
            row_count=db_file.row_count,
            columns=[col["name"] for col in columns_info],
            upload_date=db_file.upload_date
        )
        
    except Exception as e:
        # Clean up file if processing failed
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/")
async def list_files(db: Session = Depends(get_db)):
    """
    Get list of all uploaded files
    """
    files = db.query(UploadedFile).order_by(UploadedFile.upload_date.desc()).all()
    return files


@router.get("/{file_id}")
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """
    Get details of a specific file
    """
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.delete("/{file_id}")
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    """
    Delete an uploaded file
    """
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete physical file
    resolved_path = resolve_upload_path(file.file_path)
    if os.path.exists(resolved_path):
        os.remove(resolved_path)
    
    # Delete database record
    db.delete(file)
    db.commit()
    
    return {"message": "File deleted successfully"}


@router.get("/{file_id}/preview")
async def preview_file(file_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get preview of file data
    """
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Load data
        if file.file_type == '.csv':
            df = pd.read_csv(resolve_upload_path(file.file_path))
        else:
            df = pd.read_excel(resolve_upload_path(file.file_path))
        
        return {
            "columns": list(df.columns),
            "data": df.head(limit).to_dict(orient='records'),
            "total_rows": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


@router.get("/{file_id}/kpis", response_model=KPIResponse)
async def get_file_kpis(file_id: int, db: Session = Depends(get_db)):
    """
    Get comprehensive KPI insights for an uploaded file with AI-powered analysis.
    
    This endpoint delegates all analysis logic to the DataAnalystAgent class,
    which handles:
    1. Data profiling and health checks
    2. Feature-specific KPI generation  
    3. AI-powered analysis and visualization recommendations
    4. Automatic chart generation from AI suggestions
    """
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Load data
        if file.file_type == '.csv':
            df = pd.read_csv(file.file_path)
        else:
            df = pd.read_excel(file.file_path)

        # Delegate all KPI analysis to DataAnalystAgent
        agent = ai_engg(df=df)
        kpi_data = await agent.generate_kpi_report()

        # Return structured KPI response
        return KPIResponse(
            file_id=file_id,
            summary=kpi_data['summary'],
            data_profiling=kpi_data.get('data_profiling'),
            metrics=kpi_data['metrics'],
            charts=kpi_data['charts'],
            top_categories=kpi_data['top_categories'],
            date_insights=kpi_data['date_insights'],
            data_quality=kpi_data['data_quality'],
            analysis_insights=kpi_data['analysis_insights'],
            ai_summary=kpi_data['ai_summary'],
            key_metrics=kpi_data['key_metrics'],
            visual_recommendations=kpi_data['visual_recommendations']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing KPIs: {str(e)}")
