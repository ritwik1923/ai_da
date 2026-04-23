#!/bin/bash
# Quick test runner script for Unix/Linux

echo "======================================================================"
echo "  AI Data Analyst - Test Suite Runner"
echo "======================================================================"
echo ""

# Check if in correct directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Please run this script from the backend directory"
    exit 1
fi

# Run tests
python run_tests.py "$@"
