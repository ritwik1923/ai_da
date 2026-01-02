@echo off
REM Quick test runner script for Windows

echo ======================================================================
echo   AI Data Analyst - Test Suite Runner
echo ======================================================================
echo.

REM Check if in correct directory
if not exist "requirements.txt" (
    echo Error: Please run this script from the backend directory
    exit /b 1
)

REM Run tests
python3 run_tests.py %*
