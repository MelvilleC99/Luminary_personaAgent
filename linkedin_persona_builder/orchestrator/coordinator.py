"""
LinkedIn Persona Builder - Request Coordinator

Handles request routing and component coordination between API layer and core agent.
"""

import uuid
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

# Pydantic models for request/response validation
from pydantic import BaseModel, ValidationError

# Import internal components
from agent.main_agent import PersonaAgent
from memory.recovery_manager import RecoveryManager
from data.redis.redis_utils import RedisManager
from data.supabase.supabase_utils import SupabaseManager
from orchestrator.config import settings

# Configure logging
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """Pydantic model for incoming chat requests"""
    session_id: str
    user_input: str
    user_id: str
    user_name: Optional[str] = None


class ChatResponse(BaseModel):
    """Pydantic model for chat responses"""
    agent_response: str
    session_id: str
    requires_user_input: bool = True
    session_complete: bool = False
    progress: Dict[str, Any] = {}
    current_section: int = 1
    current_criterion: str = ""
    error: Optional[str] = None
    success: bool = True


class ProgressRequest(BaseModel):
    """Pydantic model for progress requests"""
    session_id: str


class ProgressResponse(BaseModel):
    """Pydantic model for progress responses"""
    session_id: str
    overall_completion: float
    section_progress: Dict[str, float]
    current_section: int
    current_criterion: str
    total_criteria: int
    completed_criteria: int
    success: bool = True
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response model"""
    error_type: str
    error_message: str
    session_id: Optional[str] = None
    timestamp: str
    success: bool = False


class RequestCoordinator:
    """
    Coordinates requests between API layer and core agent components.
    Handles request routing, error handling, and response formatting.
    """
    
    def __init__(self):
        """Initialize coordinator with required components"""
        self.persona_agent = PersonaAgent()
        self.recovery_manager = RecoveryManager()
        self.redis_manager = RedisManager()
        self.supabase_manager = SupabaseManager()
        
        logger.info("RequestCoordinator initialized successfully")
    
    async def route_chat_request(self, request: ChatRequest) -> ChatResponse:
        """
        Route chat requests to appropriate components
        
        Process:
        1. Validate request via Pydantic
        2. Check session existence
        3. Route to MainAgent for processing
        4. Handle errors and fallbacks
        5. Format response for API
        """
        try:
            # Validate request
            validated_request = ChatRequest.parse_obj(request.dict())
            logger.info(f"Processing chat request for session: {validated_request.session_id}")
            
            # Check if session exists or needs recovery
            session_exists = await self._validate_session(validated_request.session_id)
            if not session_exists:
                # Attempt session recovery
                recovery_success = await self.recovery_manager.recover_session(validated_request.session_id)
                if not recovery_success:
                    # Create new session if recovery fails
                    logger.warning(f"Session {validated_request.session_id} not found, creating new session")
                    # Note: In real implementation, you might want to return an error
                    # asking the client to create a new session
            
            # Route to main agent for processing
            result = await self.persona_agent.process_user_input(
                session_id=validated_request.session_id,
                user_input=validated_request.user_input,
                user_id=validated_request.user_id,
                user_name=validated_request.user_name
            )
            
            # Convert to response format
            if result.get("success", False):
                response = ChatResponse(
                    agent_response=result["agent_response"],
                    session_id=validated_request.session_id,
                    requires_user_input=result.get("requires_user_input", True),
                    session_complete=result.get("session_complete", False),
                    progress=result.get("progress", {}),
                    current_section=result.get("current_section", 1),
                    current_criterion=result.get("current_criterion", ""),
                    error=result.get("error"),
                    success=True
                )
            else:
                response = ChatResponse(
                    agent_response=result.get("agent_response", "I'm sorry, I encountered an issue."),
                    session_id=validated_request.session_id,
                    error=result.get("error", "Unknown error"),
                    success=False
                )
            
            return response
            
        except ValidationError as e:
            logger.error(f"Request validation failed: {e}")
            return ChatResponse(
                agent_response="Your request contains invalid data. Please try again.",
                session_id=request.session_id if hasattr(request, 'session_id') else str(uuid.uuid4()),
                error=f"Validation error: {str(e)}",
                success=False
            )
            
        except Exception as e:
            logger.error(f"Chat request routing failed: {e}")
            return await self.handle_system_errors(
                error=e, 
                request_context={"session_id": request.session_id, "user_id": request.user_id}
            )
    
    async def route_progress_request(self, request: ProgressRequest) -> ProgressResponse:
        """
        Route progress requests to get session completion status
        """
        try:
            # Validate request
            validated_request = ProgressRequest.parse_obj(request.dict())
            logger.info(f"Processing progress request for session: {validated_request.session_id}")
            
            # Get session progress from persona agent
            progress_data = await self.persona_agent.get_session_progress(validated_request.session_id)
            
            if progress_data:
                return ProgressResponse(
                    session_id=validated_request.session_id,
                    overall_completion=progress_data.get("overall_completion", 0.0),
                    section_progress=progress_data.get("section_progress", {}),
                    current_section=progress_data.get("current_section", 1),
                    current_criterion=progress_data.get("current_criterion", ""),
                    total_criteria=progress_data.get("total_criteria", 0),
                    completed_criteria=progress_data.get("completed_criteria", 0),
                    success=True
                )
            else:
                return ProgressResponse(
                    session_id=validated_request.session_id,
                    overall_completion=0.0,
                    section_progress={},
                    current_section=1,
                    current_criterion="",
                    total_criteria=0,
                    completed_criteria=0,
                    success=False,
                    error="Session not found"
                )
                
        except ValidationError as e:
            logger.error(f"Progress request validation failed: {e}")
            return ProgressResponse(
                session_id=request.session_id if hasattr(request, 'session_id') else "",
                overall_completion=0.0,
                section_progress={},
                current_section=1,
                current_criterion="",
                total_criteria=0,
                completed_criteria=0,
                success=False,
                error=f"Validation error: {str(e)}"
            )
            
        except Exception as e:
            logger.error(f"Progress request routing failed: {e}")
            return ProgressResponse(
                session_id=request.session_id,
                overall_completion=0.0,
                section_progress={},
                current_section=1,
                current_criterion="",
                total_criteria=0,
                completed_criteria=0,
                success=False,
                error=str(e)
            )
    
    async def create_session(self, user_id: str, user_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create new conversation session
        """
        try:
            session_id = str(uuid.uuid4())
            logger.info(f"Creating new session: {session_id} for user: {user_id}")
            
            # Initialize session via persona agent
            result = await self.persona_agent.create_session(
                session_id=session_id,
                user_id=user_id,
                user_name=user_name
            )
            
            if result.get("success", False):
                return {
                    "session_id": session_id,
                    "greeting_message": result.get("greeting_message", "Welcome! Let's build your LinkedIn persona."),
                    "success": True
                }
            else:
                raise Exception(f"Session creation failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    async def handle_system_errors(self, error: Exception, request_context: Dict[str, Any]) -> ChatResponse:
        """
        Centralized error handling and recovery
        
        Error Types:
        - Redis failures → Supabase fallback
        - LLM API failures → Retry with backoff
        - Validation errors → User-friendly messages
        - System errors → Logging and alerts
        """
        session_id = request_context.get("session_id", str(uuid.uuid4()))
        
        # Determine error type and response strategy
        if "redis" in str(error).lower() or "connection" in str(error).lower():
            # Redis connection failure
            logger.warning(f"Redis failure detected, attempting Supabase fallback for session: {session_id}")
            
            try:
                # Attempt to continue with Supabase as backup
                recovery_success = await self.recovery_manager.handle_redis_failure(session_id)
                if recovery_success:
                    return ChatResponse(
                        agent_response="I'm experiencing some technical issues but continuing with your session. There might be slight delays.",
                        session_id=session_id,
                        error="redis_failure_recovered",
                        success=True
                    )
            except Exception as recovery_error:
                logger.error(f"Recovery attempt failed: {recovery_error}")
        
        elif "openai" in str(error).lower() or "api" in str(error).lower():
            # LLM API failure
            logger.error(f"LLM API failure: {error}")
            return ChatResponse(
                agent_response="I'm having trouble connecting to my language service. Please try again in a moment.",
                session_id=session_id,
                error="llm_api_failure",
                success=False
            )
        
        elif "validation" in str(error).lower():
            # Validation error
            logger.warning(f"Validation error: {error}")
            return ChatResponse(
                agent_response="I didn't understand your input. Could you please rephrase that?",
                session_id=session_id,
                error="validation_error",
                success=False
            )
        
        # Generic system error
        logger.error(f"System error in coordinator: {error}")
        
        # Log error for monitoring
        await self._log_system_error(error, request_context)
        
        return ChatResponse(
            agent_response="I'm experiencing technical difficulties. Please try again in a moment.",
            session_id=session_id,
            error="system_error",
            success=False
        )
    
    async def _validate_session(self, session_id: str) -> bool:
        """
        Validate if session exists in Redis or Supabase
        """
        try:
            # Check Redis first
            session_exists = await self.redis_manager.session_exists(session_id)
            if session_exists:
                return True
            
            # Check Supabase as fallback
            supabase_session = await self.supabase_manager.get_session(session_id)
            return supabase_session is not None
            
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False
    
    async def _log_system_error(self, error: Exception, context: Dict[str, Any]):
        """
        Log system errors for monitoring and alerting
        """
        try:
            error_log = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "component": "RequestCoordinator"
            }
            
            # Store in Supabase for analysis
            await self.supabase_manager.log_system_error(
                error_type=error_log["error_type"],
                error_message=error_log["error_message"],
                session_id=context.get("session_id") if context else None,
                context=context
            )
            
        except Exception as log_error:
            # Don't let logging errors crash the system
            logger.error(f"Failed to log system error: {log_error}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all system components
        """
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Check Redis
        try:
            redis_healthy = await self.redis_manager.health_check()
            health_status["components"]["redis"] = {
                "status": "healthy" if redis_healthy else "failed",
                "response_time_ms": await self._measure_redis_response_time()
            }
        except Exception as e:
            health_status["components"]["redis"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Check Supabase
        try:
            supabase_healthy = await self.supabase_manager.health_check()
            health_status["components"]["supabase"] = {
                "status": "healthy" if supabase_healthy else "failed",
                "response_time_ms": await self._measure_supabase_response_time()
            }
        except Exception as e:
            health_status["components"]["supabase"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Check PersonaAgent
        try:
            agent_healthy = await self.persona_agent.health_check()
            health_status["components"]["persona_agent"] = {
                "status": "healthy" if agent_healthy else "failed"
            }
        except Exception as e:
            health_status["components"]["persona_agent"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Overall status
        all_healthy = all(
            comp.get("status") == "healthy" 
            for comp in health_status["components"].values()
        )
        health_status["overall_status"] = "healthy" if all_healthy else "degraded"
        
        return health_status
    
    async def _measure_redis_response_time(self) -> int:
        """Measure Redis response time in milliseconds"""
        try:
            start_time = asyncio.get_event_loop().time()
            await self.redis_manager.ping()
            end_time = asyncio.get_event_loop().time()
            return int((end_time - start_time) * 1000)
        except:
            return -1
    
    async def _measure_supabase_response_time(self) -> int:
        """Measure Supabase response time in milliseconds"""
        try:
            start_time = asyncio.get_event_loop().time()
            await self.supabase_manager.health_check()
            end_time = asyncio.get_event_loop().time()
            return int((end_time - start_time) * 1000)
        except:
            return -1


# Global request coordinator instance
request_coordinator = RequestCoordinator()
