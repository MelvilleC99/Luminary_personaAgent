#!/usr/bin/env python3
"""
Start the API server with proper configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_environment():
    """Check if environment is set up correctly."""
    print("🔧 Checking Environment")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print("❌ .env file not found")
        print("📋 Please copy .env.example to .env and fill in your values:")
        print("   cp .env.example .env")
        return False
    
    # Check for required variables
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY", 
        "OPENAI_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or "replace_this" in value or value.startswith("your_"):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Please update these variables in .env:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    print("✅ Environment looks good")
    return True

def start_server():
    """Start the FastAPI server."""
    print("\n🚀 Starting Luminary Persona Agent API")
    print("=" * 50)
    
    try:
        # Change to project directory
        project_root = Path(__file__).parent
        os.chdir(project_root)
        
        print("📍 Project directory:", project_root)
        print("🌐 Starting server on http://localhost:8000")
        print("📖 API docs at http://localhost:8000/docs")
        print()
        print("🔄 Press Ctrl+C to stop the server")
        print()
        
        # Start uvicorn
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "api.endpoints:app", 
            "--reload", 
            "--host", "localhost", 
            "--port", "8000"
        ], check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    if check_environment():
        start_server()
    else:
        print("\n❌ Please fix the environment issues above")
        sys.exit(1)
