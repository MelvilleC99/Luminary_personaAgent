from typing import Optional, Dict, Any
from datetime import datetime
from data.redis.schemas import SessionState, PersonaData
from data.redis.redis_utils import redis_manager, get_session, save_session, get_persona, save_persona
from data.supabase.supabase_utils import supabase_manager
from memory.session_manager import session_manager
import logging
logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    Handles system failures, Redis fallback to Supabase, and data recovery
    """
    
    def __init__(self):
        self.recovery_timeout = 30  # seconds
    
    async def recover_session(self, session_id: str) -> bool:
        """Simple session recovery method expected by coordinator"""
        try:
            # Try to recover session state
            session_state = await self.recover_session_state(session_id, "unknown")
            return session_state is not None
        except Exception as e:
            logger.error(f"Session recovery failed: {e} - session_id: {session_id}")
            return False
    
    async def recover_session_state(self, session_id: str, user_id: str) -> Optional[SessionState]:
        """Recover session state with fallback mechanisms"""
        try:
            logger.info("Starting session recovery", session_id=session_id)
            
            # Try Redis first
            session_state = await self._try_redis_recovery(session_id)
            if session_state:
                return session_state
            
            # Fallback to Supabase
            logger.info("Redis recovery failed, trying Supabase fallback", session_id=session_id)
            session_state = await self._try_supabase_recovery(session_id, user_id)
            if session_state:
                return session_state
            
            # Create new session as last resort
            logger.warning("All recovery attempts failed, creating new session", session_id=session_id)
            new_session_id = await session_manager.create_session(user_id)
            if new_session_id:
                return await get_session(new_session_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Session recovery failed completely: {e} - session_id: {session_id}")
            return None
    
    async def _try_redis_recovery(self, session_id: str) -> Optional[SessionState]:
        """Try to recover from Redis"""
        try:
            return await get_session(session_id)
        except Exception as e:
            logger.warning(f"Redis recovery failed: {e}", session_id=session_id)
            return None
    
    async def _try_supabase_recovery(self, session_id: str, user_id: str) -> Optional[SessionState]:
        """Try to recover from Supabase backup"""
        try:
            # Use session manager's recovery method
            session_state = await session_manager.recover_session_from_backup(session_id)
            
            if session_state and session_state.user_id == user_id:
                # Also try to recover persona data
                await self._recover_persona_data(session_id)
                return session_state
            
            return None
            
        except Exception as e:
            logger.error(f"Supabase recovery failed: {e} - session_id: {session_id}")
            return None
    
    async def recover_persona_data(self, session_id: str) -> Optional[PersonaData]:
        """Recover persona data with fallback mechanisms"""
        try:
            logger.info("Starting persona data recovery", session_id=session_id)
            
            # Try Redis first
            persona_data = await self._try_redis_persona_recovery(session_id)
            if persona_data:
                return persona_data
            
            # Fallback to Supabase
            logger.info("Redis persona recovery failed, trying Supabase", session_id=session_id)
            persona_data = await self._try_supabase_persona_recovery(session_id)
            if persona_data:
                # Restore to Redis
                await save_persona(session_id, persona_data)
                return persona_data
            
            # Create empty persona as last resort
            logger.warning("Creating empty persona data", session_id=session_id)
            return PersonaData()
            
        except Exception as e:
            logger.error(f"Persona recovery failed: {e} - session_id: {session_id}")
            return PersonaData()
    
    async def _try_redis_persona_recovery(self, session_id: str) -> Optional[PersonaData]:
        """Try to recover persona data from Redis"""
        try:
            return await get_persona(session_id)
        except Exception as e:
            logger.warning(f"Redis persona recovery failed: {e}", session_id=session_id)
            return None
    
    async def _try_supabase_persona_recovery(self, session_id: str) -> Optional[PersonaData]:
        """Try to recover persona data from Supabase"""
        try:
            return await supabase_manager.get_persona_backup(session_id)
        except Exception as e:
            logger.error(f"Supabase persona recovery failed: {e} - session_id: {session_id}")
            return None
    
    async def _recover_persona_data(self, session_id: str) -> bool:
        """Recover and restore persona data to Redis"""
        try:
            persona_data = await self._try_supabase_persona_recovery(session_id)
            if persona_data:
                success = await save_persona(session_id, persona_data)
                if success:
                    logger.info("Persona data recovered and restored to Redis", session_id=session_id)
                return success
            return False
            
        except Exception as e:
            logger.error(f"Persona data recovery failed: {e} - session_id: {session_id}")
            return False
    
    async def handle_redis_failure(self, operation: str, session_id: str = None, 
                                 fallback_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle Redis failure with appropriate fallback"""
        try:
            logger.error(f"Redis failure detected for operation: {operation} - session_id: {session_id}")
            
            # Log the failure for monitoring
            await self._log_system_failure("redis", operation, session_id)
            
            # Determine fallback strategy based on operation
            if operation in ["session_read", "session_write"]:
                return await self._handle_session_failure(session_id, fallback_data)
            elif operation in ["persona_read", "persona_write"]:
                return await self._handle_persona_failure(session_id, fallback_data)
            elif operation in ["conversation_write"]:
                return await self._handle_conversation_failure(session_id, fallback_data)
            else:
                return {"success": False, "fallback": "none", "error": "Unknown operation"}
            
        except Exception as e:
            logger.error(f"Fallback handling failed: {e}")
            return {"success": False, "fallback": "failed", "error": str(e)}
    
    async def _handle_session_failure(self, session_id: str, 
                                    fallback_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle session operation failure"""
        try:
            if not session_id:
                return {"success": False, "fallback": "none", "error": "No session ID"}
            
            # Try to recover from Supabase
            if fallback_data and "user_id" in fallback_data:
                session_state = await self._try_supabase_recovery(session_id, fallback_data["user_id"])
                if session_state:
                    return {
                        "success": True, 
                        "fallback": "supabase_recovery",
                        "session_state": session_state.dict()
                    }
            
            return {"success": False, "fallback": "supabase_failed", "error": "Recovery failed"}
            
        except Exception as e:
            logger.error(f"Session failure handling failed: {e}")
            return {"success": False, "fallback": "error", "error": str(e)}
    
    async def _handle_persona_failure(self, session_id: str,
                                    fallback_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle persona operation failure"""
        try:
            # Try to sync directly to Supabase
            if fallback_data and "persona_data" in fallback_data:
                persona_data = PersonaData(**fallback_data["persona_data"])
                user_id = fallback_data.get("user_id", "unknown")
                industry = fallback_data.get("industry")
                
                success = await supabase_manager.upsert_persona(
                    session_id, persona_data, user_id, industry
                )
                
                if success:
                    return {
                        "success": True,
                        "fallback": "direct_supabase_sync",
                        "message": "Data saved to Supabase directly"
                    }
            
            return {"success": False, "fallback": "supabase_sync_failed"}
            
        except Exception as e:
            logger.error(f"Persona failure handling failed: {e}")
            return {"success": False, "fallback": "error", "error": str(e)}
    
    async def _handle_conversation_failure(self, session_id: str,
                                         fallback_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle conversation logging failure"""
        try:
            # Try to log directly to Supabase
            if fallback_data:
                success = await supabase_manager.log_conversation_turn(session_id, fallback_data)
                if success:
                    return {
                        "success": True,
                        "fallback": "direct_supabase_log",
                        "message": "Conversation logged to Supabase"
                    }
            
            return {"success": False, "fallback": "logging_lost"}
            
        except Exception as e:
            logger.error(f"Conversation failure handling failed: {e}")
            return {"success": False, "fallback": "error", "error": str(e)}
    
    async def _log_system_failure(self, component: str, operation: str, session_id: str = None):
        """Log system failure for monitoring"""
        try:
            await supabase_manager.log_system_health(
                check_type=f"{component}_failure",
                status="failed",
                details={
                    "operation": operation,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                },
                error_message=f"{component} failure during {operation}"
            )
        except Exception as e:
            logger.error(f"Failed to log system failure: {e}")
    
    async def verify_data_consistency(self, session_id: str) -> Dict[str, Any]:
        """Verify data consistency between Redis and Supabase"""
        try:
            logger.info("Verifying data consistency", session_id=session_id)
            
            # Get data from both sources
            redis_session = await get_session(session_id)
            redis_persona = await get_persona(session_id)
            
            supabase_backup = await supabase_manager.get_session_backup(session_id)
            
            consistency_report = {
                "session_id": session_id,
                "redis_session_exists": redis_session is not None,
                "redis_persona_exists": redis_persona is not None,
                "supabase_backup_exists": supabase_backup is not None,
                "consistency_issues": [],
                "recommendations": []
            }
            
            # Check for inconsistencies
            if redis_session and supabase_backup:
                redis_user_id = redis_session.user_id
                supabase_user_id = supabase_backup["persona_data"].get("user_id")
                
                if redis_user_id != supabase_user_id:
                    consistency_report["consistency_issues"].append("User ID mismatch between Redis and Supabase")
            
            # Provide recommendations
            if not redis_session and supabase_backup:
                consistency_report["recommendations"].append("Restore session from Supabase backup")
            elif redis_session and not supabase_backup:
                consistency_report["recommendations"].append("Sync session data to Supabase")
            
            return consistency_report
            
        except Exception as e:
            logger.error(f"Consistency verification failed: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "verification_failed": True
            }
    
    async def force_sync_to_supabase(self, session_id: str) -> bool:
        """Force sync all session data to Supabase"""
        try:
            logger.info("Force syncing to Supabase", session_id=session_id)
            
            # Get Redis data
            session_state = await get_session(session_id)
            persona_data = await get_persona(session_id)
            
            if not session_state:
                logger.error(f"No session state to sync - session_id: {session_id}")
                return False
            
            if persona_data:
                success = await supabase_manager.upsert_persona(
                    session_id, 
                    persona_data, 
                    session_state.user_id,
                    session_state.industry
                )
                
                if success:
                    logger.info("Force sync completed", session_id=session_id)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Force sync failed: {e} - session_id: {session_id}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Recovery manager health check"""
        try:
            # Test Redis connectivity
            redis_health = await redis_manager.health_check()
            
            # Test Supabase connectivity  
            supabase_stats = await supabase_manager.get_completion_stats(days=1)
            supabase_healthy = "error" not in supabase_stats
            
            return {
                "status": "healthy" if redis_health["status"] == "healthy" and supabase_healthy else "degraded",
                "redis_status": redis_health["status"],
                "supabase_status": "healthy" if supabase_healthy else "unhealthy",
                "fallback_available": supabase_healthy,
                "details": "Recovery mechanisms operational"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Recovery manager health check failed"
            }


# Global recovery manager instance
recovery_manager = RecoveryManager()
