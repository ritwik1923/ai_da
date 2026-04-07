from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FileUploadResponse(BaseModel):
    """Response schema for file upload"""
    id: int
    filename: str
    original_filename: str
    file_size: int
    row_count: int
    columns: List[str]
    upload_date: datetime
    
    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    """Schema for chat messages"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None
    generated_code: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request schema for chat"""
    session_id: str
    message: str
    file_id: Optional[int] = None


class ChatResponse(BaseModel):
    """Response schema for chat"""
    session_id: str
    message_id: int
    response: str
    generated_code: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    timestamp: datetime


class ConversationHistory(BaseModel):
    """Schema for conversation history"""
    session_id: str
    messages: List[ChatMessage]
    file_info: Optional[FileUploadResponse] = None


class AnalysisRequest(BaseModel):
    """Request schema for data analysis"""
    file_id: int
    query: str


class AnalysisResponse(BaseModel):
    """Response schema for analysis"""
    query: str
    answer: str
    generated_code: str
    result_data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    execution_time: int
    
    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

class FeedbackRequest(BaseModel):
    message_id: int # The ID of the assistant's message
    is_positive: bool # True for 👍, False for 👎
    comments: Optional[str] = None