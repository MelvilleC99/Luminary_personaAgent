from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from orchestrator.config import settings
from data.supabase.models import (
    PersonaRecord, ConversationLogRecord, SessionAnalyticsRecord,
    SUPABASE_TABLES
)
from data.redis.schemas import PersonaData, SessionAnalytics
import logging
logger = logging.getLogger(__name__)


class SupabaseConnectionError(Exception):
    """Supabase connection error"""
    pass


class SupabaseManager:
    """
    Supabase operations manager for persistent data storage
    """
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Ensure Supabase connection is initialized"""
        if not self._initialized:
            self._initialize_connection()
            self._initialized = True
    
    def _check_supabase_available(self):
        """Check if Supabase is available and raise appropriate error if not"""
        if self.client is None:
            raise SupabaseConnectionError("Supabase client not available. Please check your configuration.")
    
    def _initialize_connection(self):
        """Initialize Supabase connection"""
        try:
            # Check if Supabase credentials are provided
            if not settings.supabase_url or not settings.supabase_key:
                logger.warning("Supabase credentials not provided. Supabase features will be disabled.")
                self.client = None
                return
            
            self.client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            
            # Test connection with a simple query
            result = self.client.table("personas").select("id").limit(1).execute()
            logger.info("Supabase connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase connection: {e}")
            self.client = None
            raise SupabaseConnectionError(f"Supabase connection failed: {e}")
    
    # Persona Data Operations
    async def upsert_persona(self, session_id: str, persona_data: PersonaData, 
                           user_id: str, industry: str = None) -> bool:
        """Upsert persona data to Supabase"""
        try:
            self._ensure_initialized()
            persona_record = PersonaRecord(
                session_id=session_id,
                user_id=user_id,
                persona_data=persona_data.dict(),
                completion_status=persona_data.overall_completion,
                section_progress={
                    f"section_{section.section_number}": section.completion_percentage
                    for section in persona_data.sections
                },
                industry=industry,
                status="complete" if persona_data.overall_completion >= 0.9 else "active",
                updated_at=datetime.now()
            )
            
            # Upsert operation (insert or update)
            result = self.client.table(SUPABASE_TABLES["personas"]).upsert(
                persona_record.dict(exclude_none=True),
                on_conflict="session_id"
            ).execute()
            
            if result.data:
                logger.info("Persona data synced to Supabase", session_id=session_id)
                return True
            else:
                logger.error(f"Failed to sync persona data - session_id: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Supabase persona upsert failed: {e} - session_id: {session_id}")
            return False
    
    async def get_persona_backup(self, session_id: str) -> Optional[PersonaData]:
        """Retrieve persona data from Supabase for recovery"""
        try:
            result = self.client.table(SUPABASE_TABLES["personas"]).select("*").eq(
                "session_id", session_id
            ).execute()
            
            if result.data and len(result.data) > 0:
                record = PersonaRecord(**result.data[0])
                return PersonaData(**record.persona_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve persona backup: {e}")
            return None
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data from Supabase"""
        try:
            self._ensure_initialized()
            
            if self.client is None:
                logger.warning("Supabase client not available")
                return None
            
            result = self.client.table(SUPABASE_TABLES["personas"]).select("*").eq(
                "session_id", session_id
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session from Supabase: {e}")
            return None
    
    # Conversation Logging
    async def log_conversation_turn(self, session_id: str, turn_data: Dict[str, Any]) -> bool:
        """Log conversation turn to Supabase"""
        try:
            log_record = ConversationLogRecord(
                session_id=session_id,
                turn_number=turn_data.get("turn_id", 0),
                user_input=turn_data.get("user_input"),
                agent_response=turn_data.get("agent_response", ""),
                section_number=turn_data.get("section_number", 1),
                criterion_name=turn_data.get("criterion_name", ""),
                node_type=turn_data.get("node_type", ""),
                quality_score=turn_data.get("quality_score"),
                confidence_score=turn_data.get("confidence_score"),
                response_time_ms=turn_data.get("response_time_ms"),
                token_count=turn_data.get("token_count"),
                timestamp=datetime.now()
            )
            
            result = self.client.table(SUPABASE_TABLES["conversation_logs"]).insert(
                log_record.dict(exclude_none=True)
            ).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to log conversation turn: {e} - session_id: {session_id}")
            return False
    
    # Session Analytics
    async def store_session_analytics(self, analytics: SessionAnalytics) -> bool:
        """Store session analytics in Supabase"""
        try:
            analytics_record = SessionAnalyticsRecord(
                session_id=analytics.session_id,
                user_id=analytics.user_id,
                total_duration_minutes=analytics.total_duration_minutes,
                completion_rate=analytics.completion_rate,
                drop_off_section=analytics.drop_off_section,
                total_turns=analytics.total_turns,
                average_quality_score=analytics.average_quality_score,
                follow_up_count=analytics.follow_up_count,
                modification_count=analytics.modification_count,
                total_tokens_used=analytics.total_tokens_used,
                total_cost_usd=analytics.total_cost_usd,
                average_response_time_ms=analytics.average_response_time_ms,
                industry=analytics.industry,
                completion_method=analytics.completion_method,
                error_count=analytics.error_count,
                created_at=datetime.now(),
                completed_at=datetime.now() if analytics.completion_rate >= 0.9 else None
            )
            
            result = self.client.table(SUPABASE_TABLES["session_analytics"]).upsert(
                analytics_record.dict(exclude_none=True),
                on_conflict="session_id"
            ).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to store session analytics: {e}")
            return False
    
    # Query Operations
    async def get_user_personas(self, user_id: str, limit: int = 10) -> List[PersonaRecord]:
        """Get user's persona history"""
        try:
            result = self.client.table(SUPABASE_TABLES["personas"]).select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(limit).execute()
            
            return [PersonaRecord(**record) for record in result.data]
            
        except Exception as e:
            logger.error(f"Failed to get user personas: {e}")
            return []
    
    async def get_completion_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get completion statistics for the last N days"""
        try:
            # Check if Supabase is available
            if self.client is None:
                return {"error": "Supabase not configured"}
            
            # This would be a more complex query in production
            # For now, return basic stats structure
            
            cutoff_date = datetime.now().date() - timedelta(days=days)
            
            result = self.client.table(SUPABASE_TABLES["session_analytics"]).select(
                "completion_rate, total_duration_minutes, industry"
            ).gte("created_at", cutoff_date.isoformat()).execute()
            
            if not result.data:
                return {"total_sessions": 0}
            
            data = result.data
            completed_sessions = len([r for r in data if r["completion_rate"] >= 0.9])
            
            stats = {
                "total_sessions": len(data),
                "completed_sessions": completed_sessions,
                "completion_rate": completed_sessions / len(data) if data else 0,
                "average_duration": sum(r["total_duration_minutes"] or 0 for r in data) / len(data) if data else 0,
                "industries": list(set(r["industry"] for r in data if r["industry"]))
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get completion stats: {e}")
            return {"error": str(e)}
    
    # System Health
    async def log_system_health(self, check_type: str, status: str, 
                              response_time_ms: int = None, details: Dict[str, Any] = None,
                              error_message: str = None) -> bool:
        """Log system health check"""
        try:
            health_log = {
                "check_type": check_type,
                "status": status,
                "response_time_ms": response_time_ms,
                "details": details,
                "error_message": error_message,
                "timestamp": datetime.now()
            }
            
            result = self.client.table(SUPABASE_TABLES["system_health_logs"]).insert(
                health_log
            ).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to log system health: {e}")
            return False
    
    # Recovery Operations
    async def get_session_backup(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session backup data for recovery"""
        try:
            # Get persona data
            persona_result = self.client.table(SUPABASE_TABLES["personas"]).select("*").eq(
                "session_id", session_id
            ).execute()
            
            if not persona_result.data:
                return None
            
            persona_record = persona_result.data[0]
            
            # Get conversation history
            conversation_result = self.client.table(SUPABASE_TABLES["conversation_logs"]).select("*").eq(
                "session_id", session_id
            ).order("turn_number", desc=False).execute()
            
            return {
                "persona_data": persona_record,
                "conversation_history": conversation_result.data,
                "recovery_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get session backup: {e}")
            return None
    
    # LLM Usage Tracking
    async def log_llm_usage(self, session_id: str, model: str, operation: str,
                          prompt_tokens: int, completion_tokens: int, 
                          cost_usd: float, response_time_ms: int = None) -> bool:
        """Log LLM API usage"""
        try:
            usage_log = {
                "session_id": session_id,
                "model_used": model,
                "operation_type": operation,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost_usd": cost_usd,
                "response_time_ms": response_time_ms,
                "timestamp": datetime.now()
            }
            
            result = self.client.table(SUPABASE_TABLES["llm_usage_logs"]).insert(
                usage_log
            ).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {e}")
            return False
    
    async def log_system_error(self, error_type: str, error_message: str, 
                             session_id: str = None, context: Dict[str, Any] = None) -> bool:
        """Log system errors for monitoring"""
        try:
            error_log = {
                "error_type": error_type,
                "error_message": error_message,
                "session_id": session_id,
                "context": context or {},
                "timestamp": datetime.now()
            }
            
            # Log to a generic table or just log locally
            logger.error(f"System error logged: {error_type} - {error_message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log system error: {e}")
            return False


# Global Supabase manager instance
supabase_manager = SupabaseManager()
