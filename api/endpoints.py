"""
FastAPI endpoints for the Luminary Persona Agent.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator.coordinator import PersonaCoordinator
from orchestrator.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Luminary Persona Agent API",
    description="API for building marketing personas through guided conversations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global coordinator instance
coordinator: Optional[PersonaCoordinator] = None


class QueryRequest(BaseModel):
    """Request model for chat queries."""
    query: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    website_url: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for chat queries."""
    aiResponse: str
    sessionId: Optional[str] = None
    sessionEnded: bool = False
    error: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize the coordinator on startup."""
    global coordinator
    try:
        coordinator = PersonaCoordinator()
        logger.info("✅ Persona coordinator initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize coordinator: {e}")
        # Don't fail startup, but log the error
        coordinator = None


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "Luminary Persona Agent API", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    
    health = await coordinator.health_check()
    return health


@app.post("/api/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Main endpoint for handling chat queries.
    Compatible with the existing chat interface.
    """
    if coordinator is None:
        logger.error("Coordinator not initialized")
        return QueryResponse(
            aiResponse="I'm sorry, but the system is not ready yet. Please try again in a moment.",
            error="System not initialized"
        )
    
    try:
        logger.info(f"🔄 Processing query: '{request.query[:100]}...'")
        
        # If no session_id provided, start a new session
        if not request.session_id:
            logger.info("🆕 Starting new session")
            session_result = await coordinator.start_session(
                user_id=request.user_id,
                website_url=request.website_url
            )
            
            if "error" in session_result:
                logger.error(f"❌ Failed to start session: {session_result['error']}")
                return QueryResponse(
                    aiResponse="I'm sorry, I couldn't start a new session. Please try again.",
                    error=session_result["error"]
                )
            
            return QueryResponse(
                aiResponse=session_result["message"],
                sessionId=session_result["session_id"]
            )
        
        # Process user input for existing session
        logger.info(f"💬 Processing input for session: {request.session_id}")
        result = await coordinator.process_user_input(request.session_id, request.query)
        
        if "error" in result:
            logger.error(f"❌ Error processing input: {result['error']}")
            return QueryResponse(
                aiResponse="I'm sorry, I encountered an issue processing your response. Could you try again?",
                sessionId=request.session_id,
                error=result["error"]
            )
        
        # Determine if session is complete
        session_ended = result.get("status") in ["completed", "all_questions_completed"]
        
        return QueryResponse(
            aiResponse=result["message"],
            sessionId=request.session_id,
            sessionEnded=session_ended
        )
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in query handler: {e}")
        return QueryResponse(
            aiResponse="I apologize, but I encountered an unexpected error. Please try again.",
            error=str(e),
            sessionId=request.session_id
        )


@app.post("/api/session/start")
async def start_session(user_id: Optional[str] = None, website_url: Optional[str] = None):
    """Start a new persona building session."""
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    
    try:
        result = await coordinator.start_session(user_id=user_id, website_url=website_url)
        return result
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}")
async def get_session_status(session_id: str):
    """Get session status and progress."""
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    
    try:
        result = await coordinator.get_session_status(session_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Failed to get session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a paused session."""
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    
    try:
        result = await coordinator.resume_session(session_id)
        return result
    except Exception as e:
        logger.error(f"Failed to resume session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=getattr(settings, 'api_host', 'localhost'),
        port=getattr(settings, 'api_port', 8000)
    )
