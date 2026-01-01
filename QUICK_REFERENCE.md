# Quick Reference Card

## Development Commands

### Backend

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Run server
uvicorn main:app --reload

# Run tests
pytest

# Database migrations (if using Alembic)
alembic upgrade head

# Check code
flake8 app/
black app/
```

### Frontend

```bash
# Setup
cd frontend
npm install
cp .env.example .env

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

### Docker

```bash
# Build and start all services
docker-compose up --build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Rebuild single service
docker-compose up --build backend
```

## API Endpoints

### Files API

```bash
# Upload file
curl -X POST http://localhost:8000/api/files/upload \
  -F "file=@data.csv"

# List files
curl http://localhost:8000/api/files/files

# Get file details
curl http://localhost:8000/api/files/files/1

# Preview file
curl http://localhost:8000/api/files/files/1/preview?limit=10

# Delete file
curl -X DELETE http://localhost:8000/api/files/files/1
```

### Chat API

```bash
# Create session
curl -X POST http://localhost:8000/api/chat/new-session

# Send message
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "message": "What are the top 5 products?",
    "file_id": 1
  }'

# Get conversation history
curl http://localhost:8000/api/chat/history/your-session-id

# Delete session
curl -X DELETE http://localhost:8000/api/chat/session/your-session-id
```

### Analysis API

```bash
# Run analysis
curl -X POST http://localhost:8000/api/analysis/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": 1,
    "query": "Calculate total revenue"
  }'

# Get analysis history
curl http://localhost:8000/api/analysis/history/1
```

## Environment Variables

### Backend (.env)

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# Security
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# File Upload
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=.csv,.xlsx,.xls

# Agent
MAX_ITERATIONS=10
AGENT_VERBOSE=True
ENVIRONMENT=development
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
```

## Common Issues & Solutions

### Backend won't start

**Error**: `ModuleNotFoundError: No module named 'app'`
```bash
# Make sure you're in the backend directory
cd backend
# And virtual environment is activated
source venv/bin/activate
```

**Error**: `could not connect to server: Connection refused`
```bash
# Start PostgreSQL
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql
# Windows: Start PostgreSQL service
# Or use Docker: docker-compose up postgres
```

**Error**: `AuthenticationError: No API key provided`
```bash
# Set your OpenAI API key in backend/.env
echo "OPENAI_API_KEY=sk-your-key-here" >> .env
```

### Frontend won't start

**Error**: `Cannot find module 'react'`
```bash
# Install dependencies
npm install
```

**Error**: `Network error when calling API`
```bash
# Make sure backend is running on port 8000
# Check VITE_API_URL in .env
# Check CORS settings in backend
```

### Database issues

**Reset database**:
```bash
# With Docker
docker-compose down -v
docker-compose up postgres

# Without Docker
dropdb ai_data_analyst
createdb ai_data_analyst
```

**Run migrations**:
```python
# In Python console
from app.core.database import engine
from app.models import models
models.Base.metadata.create_all(bind=engine)
```

## File Structure Quick Reference

```
backend/app/
├── agents/          # AI agents (LangChain)
│   └── data_analyst.py
├── api/             # API routes
│   ├── chat.py
│   ├── files.py
│   └── analysis.py
├── core/            # Configuration
│   ├── config.py
│   └── database.py
├── models/          # Database models
│   └── models.py
├── schemas/         # Pydantic schemas
│   └── schemas.py
└── utils/           # Utilities
    ├── code_executor.py
    └── chart_generator.py

frontend/src/
├── components/      # React components
│   ├── FileUpload.tsx
│   └── MessageBubble.tsx
├── pages/          # Page components
│   ├── HomePage.tsx
│   └── ChatPage.tsx
├── services/       # API services
│   └── chatService.ts
└── types/          # TypeScript types
    └── index.ts
```

## Code Snippets

### Add a new LangChain tool

```python
from langchain.tools import Tool

def my_custom_tool(input: str) -> str:
    """Custom tool logic"""
    return f"Processed: {input}"

tool = Tool(
    name="my_custom_tool",
    func=my_custom_tool,
    description="Description for the AI agent"
)

# Add to agent tools
self.tools.append(tool)
```

### Add a new API endpoint

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/my-endpoint")
async def my_endpoint():
    return {"message": "Hello"}

# In main.py
app.include_router(router, prefix="/api/my", tags=["My API"])
```

### Add a new React component

```tsx
interface MyComponentProps {
  data: string;
}

export default function MyComponent({ data }: MyComponentProps) {
  return (
    <div className="card">
      <h2>{data}</h2>
    </div>
  );
}
```

## Testing Commands

```bash
# Backend tests
cd backend
pytest
pytest -v  # Verbose
pytest tests/test_agent.py  # Specific file
pytest -k "test_simple"  # Specific test

# Frontend tests (if configured)
cd frontend
npm test

# Test coverage
pytest --cov=app tests/
```

## Deployment Quick Commands

```bash
# Build Docker images
docker-compose build

# Deploy to Heroku
heroku container:push web -a your-app
heroku container:release web -a your-app

# Deploy to AWS (with configured credentials)
eb deploy

# Check health
curl http://your-domain/health
```

## Useful SQL Queries

```sql
-- View recent conversations
SELECT * FROM conversations ORDER BY created_at DESC LIMIT 10;

-- Count messages per conversation
SELECT conversation_id, COUNT(*) 
FROM messages 
GROUP BY conversation_id;

-- Find conversations with errors
SELECT DISTINCT c.* 
FROM conversations c
JOIN messages m ON c.id = m.conversation_id
WHERE m.content LIKE '%error%';

-- Clean up old conversations (older than 30 days)
DELETE FROM conversations 
WHERE created_at < NOW() - INTERVAL '30 days';
```

## Git Commands

```bash
# Initial setup
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main

# Make changes
git add .
git commit -m "Add feature X"
git push

# Create feature branch
git checkout -b feature/new-feature
git push -u origin feature/new-feature
```

## Monitoring & Debugging

```bash
# View backend logs
docker-compose logs -f backend

# View all logs
docker-compose logs -f

# Check database connections
docker-compose exec postgres psql -U ai_analyst -d ai_data_analyst -c "SELECT COUNT(*) FROM conversations;"

# Monitor resource usage
docker stats

# Check API health
watch -n 5 curl http://localhost:8000/health
```

## Performance Tips

1. **Database indexing**: Ensure indexes on frequently queried columns
2. **Connection pooling**: Configure in production
3. **Caching**: Add Redis for session/result caching
4. **Code execution timeout**: Set reasonable limits
5. **File size limits**: Enforce in backend and frontend
6. **Query optimization**: Use EXPLAIN ANALYZE for slow queries

## Security Checklist

- [ ] Change default passwords
- [ ] Rotate SECRET_KEY
- [ ] Enable HTTPS in production
- [ ] Configure CORS properly
- [ ] Validate all user inputs
- [ ] Use environment variables for secrets
- [ ] Enable rate limiting
- [ ] Set up monitoring/alerting
- [ ] Regular dependency updates
- [ ] Backup database regularly
