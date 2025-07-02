#!/bin/bash

# Startup script for Luminary Persona Agent API

echo "🚀 Starting Luminary Persona Agent API..."

# Navigate to the project directory
cd /Users/melville/Documents/luminary_persona_agent

# Activate virtual environment
echo "📁 Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Please copy .env.example to .env and configure your settings."
    echo "   cp .env.example .env"
    echo "   Then edit .env with your API keys and configuration."
    exit 1
fi

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -q fastapi uvicorn

# Start the API server
echo "🌟 Starting FastAPI server on http://localhost:8000"
echo "📖 API docs will be available at http://localhost:8000/docs"
echo ""
echo "🔄 Starting server..."

uvicorn api.endpoints:app --reload --host localhost --port 8000
