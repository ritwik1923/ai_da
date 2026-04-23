@echo off
REM AI Data Analyst - Quick Setup Script for Windows
REM This script automates the setup process for the AI Data Analyst Agent

echo.
echo AI Data Analyst Agent - Setup Script
echo ========================================
echo.

REM Check prerequisites
echo Checking prerequisites...

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.9 or higher.
    pause
    exit /b 1
)
echo Python found: 
python --version

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo Node.js is not installed. Please install Node.js 18 or higher.
    pause
    exit /b 1
)
echo Node.js found:
node --version

echo.
echo Setting up backend...
cd backend

REM Create virtual environment
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

REM Create .env file
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit backend\.env and add your OPENAI_API_KEY
    echo.
)

REM Create uploads directory
if not exist "uploads" mkdir uploads

cd ..

echo.
echo Setting up frontend...
cd frontend

REM Install dependencies
echo Installing Node.js dependencies...
call npm install

REM Create .env file
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
)

cd ..

echo.
echo Setup complete!
echo.
echo Next steps:
echo.
echo 1. Add your OpenAI API key to backend\.env:
echo    OPENAI_API_KEY=sk-your-key-here
echo.
echo 2. Start PostgreSQL (or use Docker):
echo    docker-compose up -d postgres
echo.
echo 3. Start the backend server:
echo    cd backend
echo    venv\Scripts\activate
echo    uvicorn main:app --reload
echo.
echo 4. In a new terminal, start the frontend:
echo    cd frontend
echo    npm run dev
echo.
echo 5. Open http://localhost:5173 in your browser
echo.
echo Or use Docker: docker-compose up --build
echo.
pause
