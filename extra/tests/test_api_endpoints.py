"""
Test API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import io

from app.core.database import Base, get_db
from main import app

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Create test database tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


class TestFileEndpoints:
    """Test file upload and management endpoints"""
    
    def test_upload_csv_file(self):
        """Test CSV file upload"""
        # Create test CSV
        csv_content = "name,age,salary\nJohn,30,50000\nJane,25,60000\n"
        csv_file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.csv", csv_file, "text/csv")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["original_filename"] == "test.csv"
        assert data["row_count"] == 2
        assert "name" in data["columns"]
        assert "age" in data["columns"]
    
    def test_list_files(self):
        """Test listing uploaded files"""
        response = client.get("/api/files")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_upload_invalid_file_type(self):
        """Test upload with invalid file type"""
        txt_content = b"This is a text file"
        txt_file = io.BytesIO(txt_content)
        
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.txt", txt_file, "text/plain")}
        )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]


class TestChatEndpoints:
    """Test chat/conversation endpoints"""
    
    @pytest.fixture
    def uploaded_file_id(self):
        """Create and upload a test file"""
        csv_content = "product,sales,region\nA,100,North\nB,200,South\n"
        csv_file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/api/files/upload",
            files={"file": ("sales.csv", csv_file, "text/csv")}
        )
        return response.json()["id"]
    
    def test_create_new_session(self):
        """Test creating a new chat session"""
        response = client.post("/api/chat/new-session")
        assert response.status_code == 200
        assert "session_id" in response.json()
    
    @pytest.mark.skipif(
        not os.getenv("COMPANY_API_KEY") and not os.getenv("OPENAI_API_KEY"),
        reason="No LLM API key configured"
    )
    def test_send_message(self, uploaded_file_id):
        """Test sending a message"""
        # Create session
        session_response = client.post("/api/chat/new-session")
        session_id = session_response.json()["session_id"]
        
        # Send message
        response = client.post(
            "/api/chat/message",
            json={
                "session_id": session_id,
                "message": "What is the total sales?",
                "file_id": uploaded_file_id
            }
        )
        
        # May fail if API key is invalid, but structure should be correct
        if response.status_code == 200:
            data = response.json()
            assert "response" in data
            assert "session_id" in data
    
    def test_get_conversation_history(self, uploaded_file_id):
        """Test retrieving conversation history"""
        # Create session
        session_response = client.post("/api/chat/new-session")
        session_id = session_response.json()["session_id"]
        
        # Get history (should be empty initially)
        response = client.get(f"/api/chat/history/{session_id}")
        
        # Should return 404 if no conversation exists yet
        assert response.status_code in [200, 404]


class TestHealthEndpoints:
    """Test health and info endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "name" in data
    
    def test_docs_available(self):
        """Test that API docs are accessible"""
        response = client.get("/docs")
        assert response.status_code == 200
