# 🚀 Quick Start - Project Initialized!

## ✅ What's Been Done

1. ✅ Backend `.env` file created
2. ✅ Frontend `.env` file created
3. ✅ Python virtual environment created
4. ✅ Installing Python dependencies (in progress...)

## ⚠️ IMPORTANT: Add Your OpenAI API Key

Edit `backend/.env` and replace this line:
```
OPENAI_API_KEY=your-openai-api-key-here
```

With your actual OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

Get your API key from: https://platform.openai.com/api-keys

## 🔧 Next Steps

### Option 1: Backend Only (Recommended for Testing)

Since Node.js isn't installed, start with just the backend:

```powershell
# 1. Make sure dependencies are installed (check terminal)
# 2. Edit backend/.env and add your OPENAI_API_KEY
# 3. Start the backend:
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then test the API at:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Option 2: Full Stack (Install Node.js First)

1. **Install Node.js**: Download from https://nodejs.org/ (v18 or higher)

2. **Setup Frontend**:
```powershell
cd frontend
npm install
npm run dev
```

3. **Access App**: http://localhost:5173

### Option 3: Use Docker (If Available)

If you install Docker Desktop for Windows:

```powershell
# Add your OPENAI_API_KEY to backend/.env first!
docker-compose up --build
```

Then access: http://localhost:5173

## 📊 Test the API (Backend Only)

Once the backend is running, test with PowerShell:

```powershell
# Health check
Invoke-WebRequest -Uri "http://localhost:8000/health"

# Upload a file (use the example data)
$file = Get-Item "examples\sample_sales_data.csv"
$form = @{
    file = $file
}
Invoke-WebRequest -Uri "http://localhost:8000/api/files/upload" -Method Post -Form $form
```

## 🎯 Current Status

### ✅ Installed
- Python 3.13.0
- Backend structure
- Virtual environment

### ⚠️ Needs Installation
- Node.js (for frontend)
- Docker (optional, for easy deployment)
- PostgreSQL (or use Docker)

### 🔑 Needs Configuration
- **CRITICAL**: Add your OpenAI API key to `backend/.env`
- PostgreSQL connection (if not using Docker)

## 🗄️ Database Options

### Option 1: SQLite (Quick Test - No Setup)

For quick testing, you can use SQLite instead of PostgreSQL.

Edit `backend/.env` and change:
```
DATABASE_URL=sqlite:///./ai_analyst.db
```

### Option 2: PostgreSQL with Docker

```powershell
docker run --name ai-postgres -e POSTGRES_PASSWORD=secure_password_123 -e POSTGRES_USER=ai_analyst -e POSTGRES_DB=ai_data_analyst -p 5432:5432 -d postgres:15-alpine
```

### Option 3: Install PostgreSQL

Download from: https://www.postgresql.org/download/windows/

## 📝 Quick Commands

```powershell
# Start backend
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload

# Start frontend (after installing Node.js)
cd frontend
npm install
npm run dev

# Run tests
cd backend
.\venv\Scripts\activate
pytest
```

## 🆘 Troubleshooting

### "No module named 'app'"
- Make sure you're in the `backend` directory
- Activate virtual environment: `.\venv\Scripts\activate`

### "Connection refused" or Database errors
- Use SQLite: Change DATABASE_URL in `.env`
- Or install PostgreSQL/Docker

### "OpenAI API error"
- Check that OPENAI_API_KEY is set correctly in `backend/.env`
- Verify your API key is valid and has credits

## 📚 Documentation

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Complete setup guide
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Commands & troubleshooting
- **[README.md](README.md)** - Full project overview

## 🎉 Next Actions

1. **Right Now**: Add your OpenAI API key to `backend/.env`
2. **Then**: Start the backend (see Option 1 above)
3. **Test**: Visit http://localhost:8000/docs
4. **Later**: Install Node.js for the full frontend experience

---

**The project is initialized and ready to go! Just add your OpenAI API key to get started.** 🚀
