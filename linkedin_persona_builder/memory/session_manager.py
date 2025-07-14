import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from data.redis.schemas import SessionState, SessionStatus
from data.redis.redis_utils import redis_manager, get_session, save_session
from data.supabase.supabase_utils import supabase_manager
from orchestrator.config import settings
import logging
logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session lifecycle, creation, recovery, and cleanup
    """
    
    def __init__(self):
        self.session_ttl = settings.session_ttl_seconds
    
    async def create_session(self, user_id: str, user_context: Dict[str, Any] = None) -> str:
        """Create new session and return session ID"""
        try:
            session_id = str(uuid.uuid4())
            
            # Create session state
            session_state = SessionState(
                user_id=user_id,
                current_section=1,
                current_criterion="broad_domain_expertise",  # First criterion
                status=SessionStatus.ACTIVE,
                framework_version="1.0"
            )
            
            # Store in Redis
            success = await save_session(session_id, session_state)
            
            if success:
                persona_logger.session_started(session_id, user_id)
                logger.info(f"Session created - session_id: {session_id} - user_id: {user_id}")
                return session_id
            else:
                logger.error(f"Failed to store new session - user_id: {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Session creation failed: {e} - user_id: {user_id}")
            return None
    
    async def get_or_create_session(self, session_id: str, user_id: str) -> Optional[SessionState]:
        """Get existing session or create new one"""
        try:
            # Try to get existing session
            if session_id:
                session_state = await get_session(session_id)
                if session_state:
                    # Verify user_id matches
                    if session_state.user_id == user_id:
                        logger.info(f"Session retrieved - session_id: {session_id}")
                        return session_state
                    else:
                        logger.warning(f"Session user_id mismatch - session_id: {session_id}")
            
            # Create new session if none exists or doesn't match
            new_session_id = await self.create_session(user_id)
            if new_session_id:
                return await get_session(new_session_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Get or create session failed: {e}")
            return None
    
    async def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """Update session status"""
        try:
            success = await redis_manager.update_session_field(session_id, "status", status.value)
            if success:
                logger.info(f"Session status updated - session_id: {session_id} - status: {status.value}")
            return success
            
        except Exception as e:
            logger.error(f"Session status update failed: {e} - session_id: {session_id}")
            return False
    
    async def update_session_progress(self, session_id: str, section: int, 
                                    criterion: str, follow_up_attempts: int = 0) -> bool:
        """Update session progress"""
        try:
            updates = {
                "current_section": section,
                "current_criterion": criterion,
                "follow_up_attempts": follow_up_attempts,
                "updated_at": datetime.now()
            }
            
            success = True
            for field, value in updates.items():
                field_success = await redis_manager.update_session_field(session_id, field, value)
                success = success and field_success
            
            if success:
                logger.info("Session progress updated", 
                          f"Session progress updated - session_id: {session_id} - section: {section} - criterion: {criterion}")
            
            return success
            
        except Exception as e:
            logger.error(f"Session progress update failed: {e} - session_id: {session_id}")
            return False
    
    async def pause_session(self, session_id: str) -> bool:
        """Pause session"""
        try:
            success = await self.update_session_status(session_id, SessionStatus.PAUSED)
            if success:
                logger.info(f"Session paused - session_id: {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Session pause failed: {e} - session_id: {session_id}")
            return False
    
    async def resume_session(self, session_id: str) -> bool:
        """Resume paused session"""
        try:
            session_state = await get_session(session_id)
            if not session_state:
                return False
            
            if session_state.status == SessionStatus.PAUSED:
                success = await self.update_session_status(session_id, SessionStatus.ACTIVE)
                if success:
                    logger.info(f"Session resumed - session_id: {session_id}")
                return success
            
            return True  # Already active
            
        except Exception as e:
            logger.error(f"Session resume failed: {e} - session_id: {session_id}")
            return False
    
    async def complete_session(self, session_id: str) -> bool:
        """Mark session as complete"""
        try:
            success = await self.update_session_status(session_id, SessionStatus.COMPLETE)
            if success:
                # Update completion timestamp
                await redis_manager.update_session_field(session_id, "completed_at", datetime.now())
                logger.info(f"Session completed - session_id: {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Session completion failed: {e} - session_id: {session_id}")
            return False
    
    async def abandon_session(self, session_id: str) -> bool:
        """Mark session as abandoned"""
        try:
            success = await self.update_session_status(session_id, SessionStatus.ABANDONED)
            if success:
                logger.info(f"Session abandoned - session_id: {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Session abandon failed: {e} - session_id: {session_id}")
            return False
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        try:
            return await redis_manager.session_exists(session_id)
        except Exception as e:
            logger.error(f"Session existence check failed: {e}")
            return False
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive session information"""
        try:
            session_state = await get_session(session_id)
            if not session_state:
                return None
            
            # Get additional metrics
            token_usage = await redis_manager.get_token_usage(session_id)
            conversation_history = await redis_manager.get_conversation_history(session_id, count=5)
            
            return {
                "session_id": session_id,
                "user_id": session_state.user_id,
                "status": session_state.status,
                "current_section": session_state.current_section,
                "current_criterion": session_state.current_criterion,
                "follow_up_attempts": session_state.follow_up_attempts,
                "industry": session_state.industry,
                "communication_style": session_state.communication_style,
                "created_at": session_state.created_at,
                "updated_at": session_state.updated_at,
                "framework_version": session_state.framework_version,
                "token_usage": token_usage,
                "recent_turns": len(conversation_history)
            }
            
        except Exception as e:
            logger.error(f"Get session info failed: {e} - session_id: {session_id}")
            return None
    
    async def recover_session_from_backup(self, session_id: str) -> Optional[SessionState]:
        """Recover session from Supabase backup"""
        try:
            logger.info(f"Attempting session recovery from Supabase - session_id: {session_id}")
            
            # Get backup data from Supabase
            backup_data = await supabase_manager.get_session_backup(session_id)
            if not backup_data:
                logger.warning(f"No backup data found - session_id: {session_id}")
                return None
            
            persona_data = backup_data.get("persona_data", {})
            
            # Reconstruct session state
            session_state = SessionState(
                user_id=persona_data.get("user_id", "unknown"),
                current_section=1,  # Reset to beginning for safety
                current_criterion="broad_domain_expertise",
                status=SessionStatus.ACTIVE,
                industry=persona_data.get("industry", "unknown"),
                framework_version=persona_data.get("framework_version", "1.0"),
                created_at=datetime.fromisoformat(persona_data.get("created_at", datetime.now().isoformat())),
                updated_at=datetime.now()
            )
            
            # Save recovered session to Redis
            success = await save_session(session_id, session_state)
            if success:
                logger.info(f"Session recovered successfully - session_id: {session_id}")
                return session_state
            
            return None
            
        except Exception as e:
            logger.error(f"Session recovery failed: {e} - session_id: {session_id}")
            return None
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (called by maintenance job)"""
        try:
            cleaned_count = await redis_manager.cleanup_expired_sessions()
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session completely"""
        try:
            success = await redis_manager.delete_session(session_id)
            if success:
                logger.info(f"Session deleted - session_id: {session_id}")
            return success
            
        except Exception as e:
            logger.error(f"Session deletion failed: {e} - session_id: {session_id}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Session manager health check"""
        try:
            # Test session creation
            test_session_id = await self.create_session("health_check_user")
            if test_session_id:
                await self.delete_session(test_session_id)
                return {
                    "status": "healthy",
                    "details": "Session creation/deletion working"
                }
            else:
                return {
                    "status": "unhealthy",
                    "details": "Session creation failed"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "details": f"Health check failed: {e}"
            }


# Global session manager instance
session_manager = SessionManager()
