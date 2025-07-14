from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from orchestrator.coordinator import request_coordinator, ChatRequest, ChatResponse
from orchestrator.config import settings, validate_config
from system_logs.logger_config import configure_logging
import logging
logger = logging.getLogger(__name__)
import uvicorn

# Configure logging
configure_logging(settings.log_level, settings.environment)

# Create FastAPI app
app = FastAPI(
    title="LinkedIn Persona Builder API",
    description="Conversational AI agent for building LinkedIn personas",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Validate configuration
        validate_config()
        logger.info("Configuration validated successfully")
        
        # Initialize database connections
        from data.redis.redis_config import initialize_redis
        from data.supabase.supabase_config import initialize_supabase
        
        redis_success = await initialize_redis()
        supabase_success = await initialize_supabase()
        
        if redis_success and supabase_success:
            logger.info("✅ All services initialized successfully")
        else:
            logger.warning("⚠️ Some services failed to initialize")
            
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint for conversational persona building
    """
    try:
        response = await request_coordinator.route_chat_request(request)
        return response
    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        health_status = await request_coordinator.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LinkedIn Persona Builder API",
        "version": "1.0.0",
        "status": "operational"
    }


if __name__ == "__main__":
    uvicorn.run(
        "api.endpoints:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
