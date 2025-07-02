"""
Session Manager for handling persona building sessions.
"""

import asyncio
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from database.models import PersonaSession, SessionStatus, QuestionResponse
from orchestrator.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages persona building sessions with persistence."""
    
    def __init__(self, database=None):
        """
        Initialize session manager.
        
        Args:
            database: Database client for persistence
        """
        self.database = database
        self.active_sessions = {}  # In-memory cache for active sessions
        self.session_timeout = timedelta(hours=settings.session_timeout_hours)
    
    async def create_session(self, user_id: Optional[str] = None) -> PersonaSession:
        """
        Create a new persona building session.
        
        Args:
            user_id: Optional user identifier
            
        Returns:
            Created PersonaSession
        """
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + self.session_timeout
        
        session = PersonaSession(
            id=session_id,
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            current_question=1,
            questions_completed=0,
            expires_at=expires_at
        )
        
        # Store in database
        if self.database:
            await self.database.create_session(session)
        
        # Cache in memory
        self.active_sessions[session_id] = session
        
        logger.info(f"Created new session: {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[PersonaSession]:
        """
        Retrieve a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            PersonaSession if found, None otherwise
        """
        # Check in-memory cache first
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            
            # Check if session has expired
            if session.expires_at and datetime.utcnow() > session.expires_at:
                await self.expire_session(session_id)
                return None
            
            return session
        
        # Check database
        if self.database:
            session = await self.database.get_session(session_id)
            if session:
                # Check expiration
                if session.expires_at and datetime.utcnow() > session.expires_at:
                    await self.expire_session(session_id)
                    return None
                
                # Add to cache
                self.active_sessions[session_id] = session
                return session
        
        return None
    
    async def update_session(self, session: PersonaSession) -> PersonaSession:
        """
        Update a session with non-blocking database operations.
        
        Args:
            session: Session to update
            
        Returns:
            Updated session
        """
        session.updated_at = datetime.utcnow()
        
        # Update cache immediately
        self.active_sessions[session.id] = session
        
        # Update database asynchronously (non-blocking)
        if self.database:
            # Fire-and-forget database update to prevent blocking OpenAI calls
            task = asyncio.create_task(self._update_session_in_db(session))
            # Prevent unhandled task exceptions from affecting main flow
            task.add_done_callback(lambda t: None if t.exception() is None else 
                                  logger.error(f"Background session update failed: {t.exception()}"))
        
        logger.info(f"Updated session: {session.id}")
        return session
    
    async def _update_session_in_db(self, session: PersonaSession):
        """Background task for database updates."""
        try:
            await self.database.update_session(session)
        except Exception as e:
            logger.error(f"Background database update failed for session {session.id}: {e}")
    
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
        # Clear follow-up state when advancing
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
        session.expires_at = datetime.utcnow() + self.session_timeout
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
        
        # Remove from cache
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
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
        
        total_questions = 30
        progress_percentage = (session.questions_completed / total_questions) * 100
        
        return {
            "session_id": session_id,
            "current_question": session.current_question,
            "questions_completed": session.questions_completed,
            "total_questions": total_questions,
            "progress_percentage": progress_percentage,
            "status": session.status,
            "website_scraped": session.website_scraped,
            "persona_generated": session.persona_generated
        }
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions from memory and database."""
        current_time = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if session.expires_at and current_time > session.expires_at:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self.expire_session(session_id)
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
