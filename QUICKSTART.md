# 🚀 Quick Start Guide

## Project Successfully Initialized! ✅

All Python dependencies have been installed. Follow these 3 simple steps to run your AI Data Analyst:

---

## Step 1: Add Your OpenAI API Key 🔑

1. **Get your API key**: https://platform.openai.com/api-keys
2. **Open** `backend/.env`
3. **Replace** `your-openai-api-key-here` with your actual API key:
   ```
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
   ```

> ⚠️ **CRITICAL**: The app won't work without a valid OpenAI API key!

---

## Step 2: Start the Backend Server 🖥️

```powershell
cd "\\wsl.localhost\Ubuntu-22.04\home\rwk\ai_DA\backend"
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Test it**: Open http://localhost:8000/docs in your browser to see the API documentation!

---

## Step 3: Test with the Sample Data 📊

1. **Upload the sample file**: Use the API docs at http://localhost:8000/docs
   - Go to `POST /api/files/upload`
   - Click "Try it out"
   - Upload `examples/sample_sales_data.csv`

2. **Ask questions**:
   - Go to `POST /api/chat/message`
   - Try: "What are the total sales by region?"
   - Try: "Show me a bar chart of revenue by product"
   - Try: "Which month had the highest sales?"

---

## 🎯 What You Built

- ✅ **FastAPI Backend** with AI-powered data analysis
- ✅ **LangChain Agent** that writes and executes Python/Pandas code
- ✅ **Automatic Chart Generation** (Plotly charts)
- ✅ **Conversation Memory** for follow-up questions
- ✅ **SQLite Database** (no PostgreSQL setup needed!)
- ✅ **Secure Code Execution** with RestrictedPython

---

## 📱 Optional: Frontend Setup

If you want the React UI (not required for testing):

1. **Install Node.js**: https://nodejs.org/ (LTS version)
2. **Install dependencies**:
   ```powershell
   cd "\\wsl.localhost\Ubuntu-22.04\home\rwk\ai_DA\frontend"
   npm install
   ```
3. **Start frontend**:
   ```powershell
   npm run dev
   ```
4. **Open**: http://localhost:5173

---

## 🐛 Troubleshooting

### "Cannot connect to database"
- The SQLite database will be created automatically on first run
- File location: `backend/ai_analyst.db`

### "OpenAI API error"
- Check your API key in `backend/.env`
- Ensure you have credits in your OpenAI account

### "Module not found"
- Reinstall dependencies: `python -m pip install -r requirements.txt`

### Need PostgreSQL instead?
Edit `backend/.env`:
```
DATABASE_URL=postgresql://ai_analyst:secure_password_123@localhost:5432/ai_data_analyst
```
Then start PostgreSQL and create the database.

---

## 📚 Next Steps

1. **Review the code**: Check out `backend/app/agents/data_analyst.py` to see how the AI agent works
2. **Add more tools**: Extend the agent with custom analysis tools
3. **Try your own data**: Upload CSV/Excel files and ask questions
4. **Read the docs**: See `README.md` for full documentation

---

## 🎓 Portfolio Tips

This project demonstrates:
- **AI/ML Engineering**: LangChain, OpenAI GPT-4, prompt engineering
- **Full-Stack Development**: FastAPI, React, TypeScript, REST APIs
- **Data Engineering**: Pandas, SQL, data transformation
- **DevOps**: Docker, environment configuration
- **Security**: Code sandboxing, input validation

**Resume Headline**: *"Autonomous Data Analysis Agent with Natural Language Interface - GPT-4, LangChain, FastAPI"*

---

## Need Help?

- API Docs: http://localhost:8000/docs (when backend is running)
- Full Documentation: See `README.md`
- Architecture: See `ARCHITECTURE.md`
- Examples: See `examples/example_queries.md`

**Ready to impress recruiters!** 🚀
