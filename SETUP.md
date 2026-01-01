# Quick Start Guide

## Prerequisites

Before running the AI Data Analyst Agent, ensure you have:

- Python 3.9 or higher
- Node.js 18 or higher
- PostgreSQL 14 or higher (or use Docker)
- OpenAI API Key ([Get one here](https://platform.openai.com/api-keys))

## Option 1: Docker Setup (Recommended)

This is the easiest way to get started!

### Step 1: Clone and Navigate

```bash
cd ai_DA
```

### Step 2: Set Environment Variables

Create a `.env` file in the backend directory:

```bash
cd backend
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### Step 3: Run with Docker Compose

```bash
cd ..  # Back to root directory
docker-compose up --build
```

This will start:
- PostgreSQL database on port 5432
- Backend API on http://localhost:8000
- Frontend on http://localhost:5173

### Step 4: Access the Application

Open your browser and go to: **http://localhost:5173**

## Option 2: Manual Setup

If you prefer to run without Docker:

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Make sure PostgreSQL is running and create database
createdb ai_data_analyst

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

In a new terminal:

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Set environment variables
cp .env.example .env

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5173

## Using the Application

### 1. Upload Data

- Click "Select File" or drag & drop a CSV/Excel file
- Maximum file size: 10MB
- Supported formats: .csv, .xlsx, .xls

### 2. Ask Questions

Once your file is uploaded, you can ask questions like:

- "What are the top 5 products by revenue?"
- "Show me sales trends over the last 6 months"
- "Why did sales drop in July?"
- "Which region has the highest growth rate?"
- "Compare this quarter to last quarter"

### 3. View Results

The AI will:
- Generate Python/Pandas code to analyze your data
- Execute the code safely
- Return insights, charts, and visualizations
- Remember context for follow-up questions

## API Documentation

Once the backend is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

### Backend won't start

- Check that PostgreSQL is running
- Verify DATABASE_URL in .env is correct
- Ensure OPENAI_API_KEY is set

### Frontend can't connect to backend

- Check that backend is running on port 8000
- Verify VITE_API_URL in frontend/.env

### Database errors

```bash
# Reset database (warning: deletes all data)
cd backend
python
>>> from app.core.database import engine
>>> from app.models import models
>>> models.Base.metadata.drop_all(bind=engine)
>>> models.Base.metadata.create_all(bind=engine)
```

### Port already in use

Change ports in:
- Backend: `uvicorn main:app --port 8001`
- Frontend: `vite.config.ts` - change server port
- Docker: Edit `docker-compose.yml`

## Next Steps

- Try the example datasets in the `examples/` folder
- Explore the API documentation
- Customize the agent prompts in `backend/app/agents/data_analyst.py`
- Add new chart types in `backend/app/utils/chart_generator.py`

## Support

For issues or questions:
1. Check the main README.md
2. Review API documentation
3. Check application logs

---

Enjoy analyzing your data with AI! 🚀
