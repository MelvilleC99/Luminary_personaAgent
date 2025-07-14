#!/usr/bin/env python3
"""
LinkedIn Persona Builder - Main Server Runner

This script starts the LinkedIn Persona Builder API server.
"""

import asyncio
import uvicorn
import logging
from orchestrator.config import settings

# Configure basic logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main server startup"""
    try:
        print("🚀 Starting LinkedIn Persona Builder...")
        
        # Test basic imports
        print("📋 Testing imports...")
        
        try:
            from langchain_core.prompts import PromptTemplate
            print("✅ LangChain imports successful")
        except Exception as e:
            print(f"❌ LangChain imports failed: {e}")
            return
        
        try:
            from agent.components.conversation_manager import ConversationManager
            print("✅ Agent components imported")
        except Exception as e:
            print(f"❌ Agent components failed: {e}")
            return
        
        try:
            from knowledge.framework_loader import FrameworkLoader
            framework_loader = FrameworkLoader()
            print("✅ Framework loader imported")
        except Exception as e:
            print(f"❌ Framework loader failed: {e}")
            return
        
        print(f"""
🎉 LinkedIn Persona Builder is ready!

📊 Configuration:
   • Environment: {settings.environment}
   • Debug mode: {settings.debug}
   • Log level: {settings.log_level}

🌐 Server starting on:
   • URL: http://localhost:8000
   • Health check: http://localhost:8000/health
   • API docs: http://localhost:8000/docs

💡 Ready to build LinkedIn personas!
        """)
        
        # Start the server
        config = uvicorn.Config(
            "api.endpoints:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.debug,
            log_level=settings.log_level.lower(),
            access_log=True
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Server startup failed: {e}")
        logger.error(f"Server startup failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
