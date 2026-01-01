# AI-Powered Data Analyst Agent 🤖📊

An autonomous data analysis agent that generates and executes SQL/Python code from natural language prompts, built with FastAPI, LangChain, and React.

## 🎯 Project Overview

This AI-powered application allows users to upload CSV/Excel files and ask questions in plain English. The agent automatically:
- Analyzes data using AI-generated Python (Pandas) code
- Creates visualizations and charts
- Maintains conversation memory for follow-up questions
- Provides intelligent insights from your data

## 🚀 Features

- **Natural Language Queries**: Ask questions like "Why did sales drop in July?"
- **Autonomous Code Generation**: AI generates Python/Pandas code to analyze data
- **Interactive Visualizations**: Dynamic charts and graphs powered by Plotly
- **Conversation Memory**: Ask follow-up questions with context awareness
- **Multi-Format Support**: Upload CSV, Excel, or connect to databases
- **Real-time Analysis**: Fast data processing and instant results
- **Secure Execution**: Sandboxed code execution environment

## 🛠️ Tech Stack

### Backend
- **FastAPI**: High-performance async API framework
- **LangChain**: AI orchestration and agent framework
- **Pandas**: Data manipulation and analysis
- **PostgreSQL**: Database for conversation history and metadata
- **SQLAlchemy**: ORM for database operations
- **Plotly**: Interactive chart generation

### Frontend
- **React 18**: Modern UI framework
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool and dev server
- **TailwindCSS**: Utility-first styling
- **Recharts/Plotly.js**: Chart visualization
- **Axios**: HTTP client

### AI/ML
- **OpenAI GPT-4**: Language model for code generation
- **LangChain Agents**: Tool-calling and reasoning
- **Python Code Interpreter**: Safe code execution

## 📁 Project Structure

```
ai_DA/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangChain agents
│   │   ├── api/             # API routes
│   │   ├── core/            # Configuration
│   │   ├── models/          # Database models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   └── utils/           # Utilities
│   ├── uploads/             # Temporary file storage
│   ├── requirements.txt     # Python dependencies
│   └── main.py             # Application entry point
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   ├── hooks/          # Custom hooks
│   │   └── types/          # TypeScript types
│   ├── package.json        # Node dependencies
│   └── vite.config.ts      # Vite configuration
├── docker-compose.yml      # Container orchestration
└── README.md              # This file
```

## 🔧 Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 14+
- OpenAI API Key

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and DATABASE_URL

# Run database migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Set environment variables
cp .env.example .env
# Edit .env if needed (API URL)

# Start development server
npm run dev
```

### Docker Setup (Recommended)

```bash
# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## 📖 Usage

1. **Upload Data**: Upload a CSV or Excel file containing your data
2. **Ask Questions**: Type natural language questions about your data
3. **View Results**: See AI-generated analysis, charts, and insights
4. **Follow-up**: Ask follow-up questions with conversation context

### Example Queries

```
"What are the top 5 products by revenue?"
"Show me sales trends over the last 6 months"
"Why did sales drop in July?"
"Compare this quarter to last quarter"
"Which region has the highest growth rate?"
```

## 🧠 How It Works

1. **User uploads data** → File is processed and stored
2. **User asks question** → Query is sent to LangChain agent
3. **Agent analyzes** → LLM generates Python/Pandas code
4. **Code executes** → Safe execution in sandboxed environment
5. **Results visualized** → Charts/tables returned to frontend
6. **Memory updated** → Conversation context saved for follow-ups

## 🔐 Security Features

- Input validation and sanitization
- Sandboxed code execution with RestrictedPython
- Rate limiting on API endpoints
- CORS configuration
- SQL injection protection
- File type validation

## 🚀 Advanced Features

- **Multi-file Analysis**: Compare data across multiple files
- **SQL Database Connection**: Query PostgreSQL/MySQL directly
- **Export Results**: Download analysis as PDF or Excel
- **Scheduled Reports**: Automated daily/weekly insights
- **Custom Visualizations**: User-defined chart templates
- **API Access**: RESTful API for integration

## 📊 Sample Use Cases

- Sales performance analysis
- Financial data exploration
- Marketing campaign analytics
- Inventory management insights
- Customer behavior analysis
- HR analytics and reporting

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 📝 API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License

## 👨‍💻 Author

Built by an AI Engineering enthusiast for the AI Startup ecosystem.

## 🔗 Resume Headline

**"Autonomous Data Analysis Agent capable of generating SQL/Python execution plans from natural language prompts"**

---

**Portfolio Highlights:**
- Full-stack AI application with production-ready architecture
- LangChain agent implementation with tool-calling
- Real-time data analysis and visualization
- Conversation memory and context management
- Secure code execution sandbox
- Modern React frontend with TypeScript
- RESTful API design with FastAPI
- PostgreSQL integration for persistence
