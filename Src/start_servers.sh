#!/bin/bash

# Kill background processes on exit
trap "kill 0" EXIT

echo "🚀 Starting GoldTrader Environment..."

# 1. Start Backend
echo "📡 Starting FastAPI Backend on port 8000..."
if [ -d "../venv" ]; then
    source ../venv/bin/activate
else
    echo "⚠️  Virtual environment not found at ../venv"
fi

# Run backend in background
export PORT=8000
python api/main.py &

# Wait for backend to be ready
echo "⏳ Waiting for backend to scale up..."
MAX_RETRIES=30
COUNT=0
while ! curl -s http://localhost:8000/api/config > /dev/null; do
    sleep 1
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Backend failed to start in time."
        exit 1
    fi
done
echo "✅ Backend is UP and running."

# 2. Start Frontend
echo "💻 Starting React Frontend on port 5173..."
cd frontend
npm run dev
