from pydantic_settings import BaseSettings
from typing import List, Union
from pydantic import field_validator


class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "AI Data Analyst Agent"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = "postgresql://ai_analyst:secure_password_123@localhost:5432/ai_data_analyst"
    
    # LLM Provider Settings
    LLM_PROVIDER: str = "openai"  # Options: "openai" or "company"
    
    # OpenAI Settings
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Company GenAI Settings
    COMPANY_API_KEY: str = ""
    COMPANY_MODEL: str = "ChatGPT4o"  # Options: ChatGPT4o, ChatGPT4o-mini, VertexGemini, Claude-Sonnet-4, etc.
    COMPANY_USER_ID: str = ""  # Your email in CORE ID format (optional)
    COMPANY_BASE_URL: str = "https://genai-service.stage.commandcentral.com/app-gateway"
    COMPANY_CLIENT_ID: str = "ai-data-analyst"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = "http://localhost:5173,http://localhost:3000"
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: Union[List[str], str] = ".csv,.xlsx,.xls"
    
    @field_validator('ALLOWED_EXTENSIONS', mode='before')
    @classmethod
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(',')]
        return v
    
    # Agent Settings
    MAX_ITERATIONS: int = 10
    AGENT_VERBOSE: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file


settings = Settings()
