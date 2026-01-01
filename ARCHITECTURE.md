# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (React)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ File Upload │  │ Chat Interface│  │ Visualization│       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/REST API
┌─────────────────────────▼───────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              API Layer (Routes)                      │    │
│  │  • /api/files    • /api/chat    • /api/analysis    │    │
│  └────────────────┬────────────────────────────────────┘    │
│                   │                                          │
│  ┌────────────────▼──────────────┐  ┌──────────────────┐   │
│  │   LangChain Agent Layer       │  │  Services Layer  │   │
│  │  • DataAnalystAgent           │  │  • File Handler  │   │
│  │  • Tool Management            │  │  • Code Executor │   │
│  │  • Memory Management          │  │  • Chart Gen     │   │
│  └───────────────────────────────┘  └──────────────────┘   │
│                   │                                          │
│  ┌────────────────▼──────────────────────────────────────┐  │
│  │                Database Layer (SQLAlchemy)            │  │
│  │  • Conversations  • Messages  • Files  • Results     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   PostgreSQL Database                        │
│  • Conversation history   • File metadata   • Analysis cache│
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    OpenAI GPT-4 API                         │
│  • Code generation   • Natural language understanding       │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend Architecture

**Technology**: React 18 + TypeScript + Vite

**Key Components**:
- `HomePage`: Landing page with file upload
- `ChatPage`: Main chat interface with sidebar
- `FileUpload`: Drag-and-drop file upload component
- `MessageBubble`: Chat message display with code and charts

**Services**:
- `chatService`: API calls for chat functionality
- `fileService`: API calls for file operations

**State Management**: React hooks (useState, useEffect)

### Backend Architecture

**Technology**: FastAPI + Python 3.9+

**API Routes**:

1. **Files API** (`/api/files`)
   - Upload files
   - List/Get/Delete files
   - Preview file data

2. **Chat API** (`/api/chat`)
   - Send messages
   - Get conversation history
   - Manage sessions

3. **Analysis API** (`/api/analysis`)
   - One-shot analysis (no memory)
   - Analysis history

**Core Components**:

1. **DataAnalystAgent** (`app/agents/data_analyst.py`)
   - LangChain agent orchestrator
   - Manages tools and memory
   - Coordinates code generation and execution

2. **Code Executor** (`app/utils/code_executor.py`)
   - Sandboxed Python/Pandas code execution
   - RestrictedPython for security
   - Result serialization

3. **Chart Generator** (`app/utils/chart_generator.py`)
   - Automatic chart type detection
   - Plotly chart generation
   - Multiple chart types (line, bar, pie, scatter, histogram)

### Database Schema

**UploadedFile**
- Stores file metadata
- Column information
- Row counts

**Conversation**
- Session management
- File association
- Timestamp tracking

**Message**
- Chat history
- Generated code storage
- Execution results
- Chart data

**AnalysisResult**
- Analysis cache
- Performance metrics

### AI Agent Flow

```
User Query
    ├─> LangChain Agent
    │   ├─> get_dataframe_info (Tool)
    │   ├─> execute_pandas_code (Tool)
    │   └─> analyze_column (Tool)
    ├─> Code Generation (GPT-4)
    ├─> Code Execution (RestrictedPython)
    ├─> Chart Generation (Plotly)
    └─> Response Formatting
```

## Security Features

1. **Code Execution Sandbox**
   - RestrictedPython for safe execution
   - Blacklist dangerous operations
   - Limited scope

2. **File Upload Validation**
   - File type checking
   - Size limits (10MB)
   - Extension validation

3. **API Security**
   - CORS configuration
   - Input validation
   - Error handling

4. **Database Security**
   - SQL injection protection (SQLAlchemy)
   - Parameterized queries

## Data Flow

### Upload Flow
```
1. User selects file
2. Frontend validates file type/size
3. FormData POST to /api/files/upload
4. Backend saves file to disk
5. Pandas loads and analyzes file
6. Metadata saved to database
7. Response with file info
8. Frontend redirects to chat
```

### Chat Flow
```
1. User sends message
2. Frontend POST to /api/chat/message
3. Backend loads conversation history
4. Creates DataAnalystAgent with memory
5. Agent processes query using tools
6. GPT-4 generates Python code
7. Code executed in sandbox
8. Charts generated if needed
9. Results saved to database
10. Response sent to frontend
11. Frontend renders message with charts
```

## Scalability Considerations

### Current Architecture
- Single server deployment
- Local file storage
- In-memory code execution

### Future Enhancements
- Redis for session caching
- S3 for file storage
- Celery for background tasks
- Load balancer for multiple instances
- Database read replicas

## Performance Optimizations

1. **Database Indexing**
   - Session ID indexed
   - File ID indexed
   - Timestamp indexed

2. **Query Optimization**
   - Eager loading relationships
   - Pagination support

3. **Caching**
   - Analysis results cached
   - DataFrame info cached per session

4. **Code Execution**
   - Timeout limits
   - Resource constraints

## Development Best Practices

1. **Code Organization**
   - Separation of concerns
   - Modular architecture
   - Clear dependencies

2. **Error Handling**
   - Try-catch blocks
   - Graceful degradation
   - User-friendly messages

3. **Testing Strategy**
   - Unit tests for utilities
   - Integration tests for API
   - E2E tests for workflows

4. **Documentation**
   - Code comments
   - API documentation (Swagger)
   - Architecture diagrams
