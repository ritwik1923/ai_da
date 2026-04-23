#!/bin/bash
# Setup script for debugging AI Data Analyst backend locally

set -e

WORKSPACE="/Users/rwk3030/dev/ai_da"

echo "==========================================="
echo "AI Data Analyst - Debug Setup"
echo "==========================================="
echo ""

# Step 1: Create and activate venv
echo "📦 Step 1: Setting up Python virtual environment..."
cd "$WORKSPACE"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "✓ Virtual environment created"
else
  echo "✓ Virtual environment already exists"
fi

source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Step 2: Install dependencies
echo "📚 Step 2: Installing dependencies..."
cd "$WORKSPACE/backend"
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Step 3: Docker setup message
echo "🐳 Step 3: Start Docker services (run in separate terminal):"
echo ""
echo "   Terminal 1:"
echo "   -----------"
echo "   cd $WORKSPACE"
echo "   docker-compose down -v  # Clean slate (optional)"
echo "   docker-compose up postgres frontend"
echo ""
echo "   Wait for 'ai_da_frontend | VITE v5.x.x ready in X ms'"
echo ""

# Step 4: Backend debug message
echo "🐛 Step 4: Start backend debugger (VS Code):"
echo ""
echo "   Terminal 2 (or VS Code):"
echo "   --------"
echo "   press F5 in VS Code"
echo "   OR run manually:"
echo "   cd $WORKSPACE/backend"
echo "   source ../.venv/bin/activate"
echo "   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""

# Step 5: Test
echo "🧪 Step 5: Test the setup:"
echo ""
echo "   Open in browser: http://localhost:5173"
echo ""
echo "   Or test via curl:"
echo "   curl -X POST http://localhost:8000/api/chat/message \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"session_id\":\"debug\",\"file_id\":1,\"message\":\"hello\"}'"
echo ""

echo "==========================================="
echo "✅ Setup complete! Follow the instructions above."
echo "==========================================="
echo ""
echo "💡 Tips:"
echo "   • Set breakpoints in VS Code before pressing F5"
echo "   • F10 = step over, F11 = step in"
echo "   • View variables in left panel"
echo "   • Use Debug Console to evaluate expressions"
echo ""
