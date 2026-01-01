from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class UploadedFile(Base):
    """Model for uploaded data files"""
    __tablename__ = "uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    file_type = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    columns = Column(JSON)  # Store column names and types
    row_count = Column(Integer)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="file")
    
    def __repr__(self):
        return f"<UploadedFile {self.original_filename}>"


class Conversation(Base):
    """Model for conversation sessions"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    file = relationship("UploadedFile", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation {self.session_id}>"


class Message(Base):
    """Model for chat messages"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Metadata for assistant messages
    generated_code = Column(Text, nullable=True)
    execution_result = Column(JSON, nullable=True)
    chart_data = Column(JSON, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message {self.role}: {self.content[:50]}>"


class AnalysisResult(Base):
    """Model for storing analysis results"""
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)
    query = Column(Text, nullable=False)
    generated_code = Column(Text, nullable=False)
    result_data = Column(JSON, nullable=True)
    chart_config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    execution_time = Column(Integer)  # in milliseconds
    
    def __repr__(self):
        return f"<AnalysisResult {self.id}>"
