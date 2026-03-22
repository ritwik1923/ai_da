from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import pandas as pd
import uuid, json
from datetime import datetime
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.models.models import Conversation, Message, UploadedFile
from app.schemas.schemas import ChatRequest, ChatResponse, ConversationHistory, ChatMessage
# from app.agents.data_analyst_v2 import DataAnalystAgent
from app.agents.data_analyst_v3 import build_data_analyst_agent as DataAnalystAgent

router = APIRouter()


def _load_dataframe(file_type: str, file_path: str) -> pd.DataFrame:
    if file_type == '.csv':
        return pd.read_csv(file_path)
    return pd.read_excel(file_path)


def _run_agent_analysis(df: pd.DataFrame, conversation_memory: list, query: str):
    agent = DataAnalystAgent(df, conversation_memory,query)
    return agent.analyze()


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message and get AI response
    """
    
    # Get or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.session_id == request.session_id
    ).first()
    
    if not conversation:
        conversation = Conversation(
            session_id=request.session_id,
            file_id=request.file_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.commit()
    
    try:
        # Load file data if file_id is provided
        df = None
        if request.file_id or conversation.file_id:
            file_id = request.file_id or conversation.file_id
            file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
            
            if not file:
                raise HTTPException(status_code=404, detail="File not found")
            
            df = await run_in_threadpool(_load_dataframe, file.file_type, file.file_path)
        
        if df is None:
            raise HTTPException(
                status_code=400,
                detail="No data file associated with this conversation. Please upload a file first."
            )
        
        # Get conversation history for memory
        previous_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp).all()
        
        conversation_memory = [
            {"role": msg.role, "content": msg.content}
            for msg in previous_messages[:-1]  # Exclude the current message
        ]
        # TODO remove this memory limit after we have better handling in the agent
        conversation_memory = []
        result = await run_in_threadpool(
            _run_agent_analysis,
            df,
            conversation_memory,
            request.message,
        )
        # 1. SAFETY CHECK: Catch the None object before it crashes the DB insertion
        if result is None:
            raise ValueError("The Agent returned a None object. Check your data_analyst_v3.py script and ensure all paths (especially recursive retries) have a 'return' statement.")

        # 2. PRINT FIX: Use json.dumps with default=str to handle any datetime/custom objects safely
        print(f"\n\nAgent Result: {json.dumps(result, default=str)}")
        # Save assistant response
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result["answer"],
            generated_code=result.get("generated_code"),
            chart_data=result.get("chart_data")
        )
        db.add(assistant_message)
        db.commit()
        
        return ChatResponse(
            session_id=request.session_id,
            response=result.get("answer") or "Failed to Answer. Please retry again.",            generated_code=result.get("generated_code"),
            execution_result=result.get("execution_result"),
            chart_data=result.get("chart_data"),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        # Save error message
        error_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"I encountered an error: {str(e)}"
        )
        db.add(error_message)
        db.commit()
        print(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=ConversationHistory)
async def get_conversation_history(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get conversation history for a session
    """
    conversation = db.query(Conversation).filter(
        Conversation.session_id == session_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.timestamp).all()
    
    chat_messages = [
        ChatMessage(
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
            generated_code=msg.generated_code,
            chart_data=msg.chart_data
        )
        for msg in messages
    ]
    
    # Get file info if available
    file_info = None
    if conversation.file_id:
        file = db.query(UploadedFile).filter(
            UploadedFile.id == conversation.file_id
        ).first()
        if file:
            file_info = {
                "id": file.id,
                "filename": file.original_filename,
                "row_count": file.row_count,
                "columns": [col["name"] for col in file.columns]
            }
    
    return ConversationHistory(
        session_id=session_id,
        messages=chat_messages,
        file_info=file_info
    )


@router.post("/new-session")
async def create_new_session():
    """
    Create a new conversation session
    """
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    """
    Delete a conversation session
    """
    conversation = db.query(Conversation).filter(
        Conversation.session_id == session_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted successfully"}
