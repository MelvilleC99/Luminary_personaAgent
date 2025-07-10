"""
Enhanced Session Manager with Redis Integration.
Manages persona building sessions with fast Redis caching and database backup.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from database.models import PersonaSession, SessionStatus, QuestionResponse
from orchestrator.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Enhanced session manager with Redis integration for fast session access.
    Uses Redis for active session caching and database for persistence.
    """
    
    def __init__(self, redis_context_manager=None, database=None):
        """
        Initialize session manager.
        
        Args:
            redis_context_manager: Redis context manager for caching
            database: Database client for persistence
        """
        self.redis_context = redis_context_manager
        self.database = database
        
        # Configuration
        self.session_timeout = timedelta(hours=settings.session_timeout_hours)
        
        # In-memory cache for active sessions (fallback)
        self.active_sessions = {}
        
        logger.info("Initialized Enhanced Session Manager with Redis support")
    
    async def create_session(self, user_id: Optional[str] = None) -> PersonaSession:
        """
        Create a new persona building session.
        
        Args:
            user_id: Optional user identifier
            
        Returns:
            Created PersonaSession
        """
        session_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + self.session_timeout
        
        session = PersonaSession(
            id=session_id,
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            current_question=1,
            questions_completed=0,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc)
        )
        
        # Store in Redis cache
        await self._cache_session_in_redis(session)
        
        # Store in database (background task)
        if self.database:
            asyncio.create_task(self._create_session_in_db(session))
        
        # Cache in memory as fallback
        self.active_sessions[session_id] = session
        
        logger.info(f"Created new session: {session_id}")
        return session
    
    async def _cache_session_in_redis(self, session: PersonaSession):
        """Cache session in Redis."""
        if not self.redis_context or not self.redis_context._redis_connected:
            return
        
        try:
            session_key = f"session:{session.id}"
            session_data = {
                "id": session.id,
                "user_id": session.user_id if session.user_id else "",
                "status": session.status.value,
                "current_question": str(session.current_question),
                "questions_completed": str(session.questions_completed),
                "completion_percentage": str(session.completion_percentage),
                "framework_completion_percentage": str(session.framework_completion_percentage),
                "conversation_turn_count": str(session.conversation_turn_count),
                "total_information_extracted": str(session.total_information_extracted),
                "awaiting_follow_up": str(session.awaiting_follow_up),
                "follow_up_attempts": str(session.follow_up_attempts),
                "website_url": session.website_url if session.website_url else "",
                "website_scraped": str(session.website_scraped),
                "persona_generated": str(session.persona_generated),
                "total_cost": str(session.total_cost),
                "total_tokens": str(session.total_tokens),
                "total_api_calls": str(session.total_api_calls),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "last_activity_at": session.last_activity_at.isoformat(),
                "expires_at": session.expires_at.isoformat() if session.expires_at else ""
            }
            
            # Store in Redis with TTL
            await self.redis_context.redis.hmset(session_key, session_data)
            await self.redis_context.redis.expire(session_key, int(self.session_timeout.total_seconds()))
            
            logger.debug(f"Cached session {session.id} in Redis")
            
        except Exception as e:
            logger.error(f"Failed to cache session in Redis: {e}")
    
    async def _create_session_in_db(self, session: PersonaSession):
        """Background task to create session in database."""
        try:
            if self.database and hasattr(self.database, 'create_session'):
                await self.database.create_session(session)
        except Exception as e:
            logger.error(f"Failed to create session in database: {e}")
    
    async def get_session(self, session_id: str) -> Optional[PersonaSession]:
        """
        Retrieve a session by ID from Redis cache or database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            PersonaSession if found, None otherwise
        """
        # Try Redis cache first
        session = await self._get_session_from_redis(session_id)
        if session:
            # Check if session has expired
            if session.expires_at and datetime.now(timezone.utc) > session.expires_at:
                await self.expire_session(session_id)
                return None
            
            # Update last activity
            session.last_activity_at = datetime.now(timezone.utc)
            await self._cache_session_in_redis(session)
            
            return session
        
        # Try in-memory cache
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            
            # Check expiration
            if session.expires_at and datetime.now(timezone.utc) > session.expires_at:
                await self.expire_session(session_id)
                return None
            
            return session
        
        # Try database
        session = await self._get_session_from_db(session_id)
        if session:
            # Check expiration
            if session.expires_at and datetime.now(timezone.utc) > session.expires_at:
                await self.expire_session(session_id)
                return None
            
            # Cache in Redis and memory
            await self._cache_session_in_redis(session)
            self.active_sessions[session_id] = session
            
            return session
        
        return None
    
    async def _get_session_from_redis(self, session_id: str) -> Optional[PersonaSession]:
        """Get session from Redis cache."""
        if not self.redis_context or not self.redis_context._redis_connected:
            return None
        
        try:
            session_key = f"session:{session_id}"
            session_data = await self.redis_context.redis.hgetall(session_key)
            
            if not session_data:
                return None
            
            # Convert Redis data to PersonaSession
            session = PersonaSession(
                id=session_data["id"],
                user_id=session_data["user_id"] if session_data["user_id"] else None,
                status=SessionStatus(session_data["status"]),
                current_question=int(session_data["current_question"]),
                questions_completed=int(session_data["questions_completed"]),
                completion_percentage=float(session_data["completion_percentage"]),
                framework_completion_percentage=float(session_data["framework_completion_percentage"]),
                conversation_turn_count=int(session_data["conversation_turn_count"]),
                total_information_extracted=int(session_data["total_information_extracted"]),
                awaiting_follow_up=session_data["awaiting_follow_up"] == "True",
                follow_up_attempts=int(session_data["follow_up_attempts"]),
                website_url=session_data["website_url"] if session_data["website_url"] else None,
                website_scraped=session_data["website_scraped"] == "True",
                persona_generated=session_data["persona_generated"] == "True",
                total_cost=float(session_data["total_cost"]),
                total_tokens=int(session_data["total_tokens"]),
                total_api_calls=int(session_data["total_api_calls"]),
                created_at=datetime.fromisoformat(session_data["created_at"]),
                updated_at=datetime.fromisoformat(session_data["updated_at"]),
                last_activity_at=datetime.fromisoformat(session_data["last_activity_at"]),
                expires_at=datetime.fromisoformat(session_data["expires_at"]) if session_data["expires_at"] else None
            )
            
            logger.debug(f"Retrieved session {session_id} from Redis")
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session from Redis: {e}")
            return None
    
    async def _get_session_from_db(self, session_id: str) -> Optional[PersonaSession]:
        """Get session from database."""
        if not self.database:
            return None
        
        try:
            if hasattr(self.database, 'get_session'):
                return await self.database.get_session(session_id)
        except Exception as e:
            logger.error(f"Failed to get session from database: {e}")
        
        return None
    
    async def update_session(self, session: PersonaSession) -> PersonaSession:
        """
        Update a session with fast Redis caching and database backup.
        
        Args:
            session: Session to update
            
        Returns:
            Updated session
        """
        session.updated_at = datetime.now(timezone.utc)
        session.last_activity_at = datetime.now(timezone.utc)
        
        # Update Redis cache immediately
        await self._cache_session_in_redis(session)
        
        # Update in-memory cache
        self.active_sessions[session.id] = session
        
        # Update database asynchronously (non-blocking)
        if self.database:
            asyncio.create_task(self._update_session_in_db(session))
        
        logger.debug(f"Updated session: {session.id}")
        return session
    
    async def _update_session_in_db(self, session: PersonaSession):
        """Background task for database updates."""
        try:
            if self.database and hasattr(self.database, 'update_session'):
                await self.database.update_session(session)
        except Exception as e:
            logger.error(f"Failed to update session in database: {e}")
    
    async def update_framework_progress(self, session_id: str, 
                                      completion_percentage: float,
                                      information_extracted: int = 0) -> Optional[PersonaSession]:
        """
        Update framework completion progress for a session.
        
        Args:
            session_id: Session identifier
            completion_percentage: Overall completion percentage (0-100)
            information_extracted: Number of information items extracted
            
        Returns:
            Updated PersonaSession or None if not found
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for framework progress update")
            return None
        
        # Update framework completion
        session.framework_completion_percentage = completion_percentage
        session.total_information_extracted += information_extracted
        session.conversation_turn_count += 1
        
        # Update status based on completion
        if completion_percentage >= 100:
            session.status = SessionStatus.COMPLETED
        elif completion_percentage >= 80:
            session.status = SessionStatus.ACTIVE  # Close to completion
        
        return await self.update_session(session)
    
    async def advance_question(self, session_id: str) -> PersonaSession:
        """
        Advance to the next question in the session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.current_question += 1
        session.questions_completed += 1
        session.awaiting_follow_up = False
        session.follow_up_attempts = 0
        
        # Check if all questions are completed
        if session.current_question > 30:
            session.status = SessionStatus.COMPLETED
            logger.info(f"Session completed: {session_id}")
        
        return await self.update_session(session)
    
    async def set_follow_up_needed(self, session_id: str) -> PersonaSession:
        """
        Mark session as awaiting follow-up response.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.awaiting_follow_up = True
        session.follow_up_attempts += 1
        
        return await self.update_session(session)
    
    async def clear_follow_up_state(self, session_id: str) -> PersonaSession:
        """
        Clear follow-up state (when follow-up is satisfactory).
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.awaiting_follow_up = False
        session.follow_up_attempts = 0
        
        return await self.update_session(session)
    
    async def set_website_url(self, session_id: str, website_url: str) -> PersonaSession:
        """
        Set the website URL for a session.
        
        Args:
            session_id: Session identifier
            website_url: Company website URL
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.website_url = website_url
        return await self.update_session(session)
    
    async def mark_website_scraped(self, session_id: str) -> PersonaSession:
        """
        Mark the website as scraped for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.website_scraped = True
        return await self.update_session(session)
    
    async def mark_persona_generated(self, session_id: str) -> PersonaSession:
        """
        Mark the persona as generated for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.persona_generated = True
        session.status = SessionStatus.COMPLETED
        return await self.update_session(session)
    
    async def pause_session(self, session_id: str) -> PersonaSession:
        """
        Pause a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.status = SessionStatus.PAUSED
        logger.info(f"Paused session: {session_id}")
        return await self.update_session(session)
    
    async def resume_session(self, session_id: str) -> PersonaSession:
        """
        Resume a paused session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Extend expiration time
        session.expires_at = datetime.now(timezone.utc) + self.session_timeout
        session.status = SessionStatus.ACTIVE
        
        logger.info(f"Resumed session: {session_id}")
        return await self.update_session(session)
    
    async def expire_session(self, session_id: str):
        """
        Expire a session.
        
        Args:
            session_id: Session identifier
        """
        session = await self.get_session(session_id)
        if session:
            session.status = SessionStatus.EXPIRED
            await self.update_session(session)
        
        # Remove from caches
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        # Remove from Redis
        if self.redis_context and self.redis_context._redis_connected:
            try:
                session_key = f"session:{session_id}"
                await self.redis_context.redis.delete(session_key)
            except Exception as e:
                logger.error(f"Failed to delete session from Redis: {e}")
        
        logger.info(f"Expired session: {session_id}")
    
    async def get_session_progress(self, session_id: str) -> Dict[str, Any]:
        """
        Get session progress information.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Progress information
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        return {
            "session_id": session_id,
            "current_question": session.current_question,
            "questions_completed": session.questions_completed,
            "completion_percentage": session.completion_percentage,
            "framework_completion_percentage": session.framework_completion_percentage,
            "conversation_turn_count": session.conversation_turn_count,
            "total_information_extracted": session.total_information_extracted,
            "status": session.status.value,
            "website_scraped": session.website_scraped,
            "persona_generated": session.persona_generated,
            "awaiting_follow_up": session.awaiting_follow_up,
            "follow_up_attempts": session.follow_up_attempts,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat()
        }
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions from memory and Redis."""
        current_time = datetime.now(timezone.utc)
        expired_sessions = []
        
        # Check in-memory cache
        for session_id, session in self.active_sessions.items():
            if session.expires_at and current_time > session.expires_at:
                expired_sessions.append(session_id)
        
        # Expire sessions
        for session_id in expired_sessions:
            await self.expire_session(session_id)
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    async def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about current sessions.
        
        Returns:
            Session statistics
        """
        try:
            # Get stats from Redis if available
            if self.redis_context and self.redis_context._redis_connected:
                session_keys = await self.redis_context.redis.keys("session:*")
                redis_session_count = len(session_keys)
            else:
                redis_session_count = 0
            
            # Get stats from memory cache
            memory_session_count = len(self.active_sessions)
            
            # Count by status from memory cache
            status_counts = {}
            completion_percentages = []
            
            for session in self.active_sessions.values():
                status = session.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                
                completion = session.framework_completion_percentage
                completion_percentages.append(completion)
            
            # Calculate average completion
            avg_completion = sum(completion_percentages) / len(completion_percentages) if completion_percentages else 0.0
            
            return {
                "redis_sessions": redis_session_count,
                "memory_sessions": memory_session_count,
                "status_distribution": status_counts,
                "average_completion_percentage": round(avg_completion, 2),
                "sessions_near_completion": len([c for c in completion_percentages if c >= 80]),
                "sessions_just_started": len([c for c in completion_percentages if c < 20]),
                "redis_connected": self.redis_context._redis_connected if self.redis_context else False
            }
            
        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {"error": str(e)}
    
    async def get_user_sessions(self, user_id: str, limit: int = 10) -> List[PersonaSession]:
        """
        Get sessions for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            
        Returns:
            List of user sessions
        """
        try:
            # Filter from active sessions cache
            user_sessions = [
                session for session in self.active_sessions.values()
                if session.user_id == user_id
            ]
            
            # Sort by creation time (newest first)
            user_sessions.sort(key=lambda x: x.created_at, reverse=True)
            
            # Return limited results
            return user_sessions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []
    
    async def update_session_costs(self, session_id: str, 
                                 cost: float, tokens: int, api_calls: int = 1) -> Optional[PersonaSession]:
        """
        Update session cost tracking.
        
        Args:
            session_id: Session identifier
            cost: Additional cost in USD
            tokens: Number of tokens used
            api_calls: Number of API calls made
            
        Returns:
            Updated PersonaSession or None if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        session.total_cost += cost
        session.total_tokens += tokens
        session.total_api_calls += api_calls
        
        return await self.update_session(session)
