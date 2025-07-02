"""
Context Manager for handling conversation context and history.
"""

import asyncio
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.models import ChatMessage, AgentType

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context and chat history."""
    
    def __init__(self, database=None):
        """
        Initialize context manager.
        
        Args:
            database: Database client for persistence
        """
        self.database = database
        self.session_contexts = {}  # In-memory context cache
    
    async def add_message(self, session_id: str, role: str, content: str,
                         question_id: Optional[int] = None,
                         agent_type: Optional[AgentType] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> ChatMessage:
        """
        Add a message to the conversation context with non-blocking database operations.
        
        Args:
            session_id: Session identifier
            role: Message role ("user", "assistant", "system")
            content: Message content
            question_id: Optional question ID this message relates to
            agent_type: Optional agent type that generated this message
            metadata: Optional additional metadata
            
        Returns:
            Created ChatMessage
        """
        message_id = str(uuid.uuid4())  # Use proper UUID instead of compound format
        
        message = ChatMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            question_id=question_id,
            agent_type=agent_type,
            metadata=metadata or {}
        )
        
        # Add to in-memory context immediately
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = []
        
        self.session_contexts[session_id].append(message)
        
        # Store in database asynchronously (non-blocking)
        if self.database:
            task = asyncio.create_task(self._create_message_in_db(message))
            # Prevent unhandled task exceptions from affecting main flow
            task.add_done_callback(lambda t: None if t.exception() is None else 
                                  logger.error(f"Background message creation failed: {t.exception()}"))
        
        logger.debug(f"Added {role} message to session {session_id}")
        return message
    
    async def _create_message_in_db(self, message: ChatMessage):
        """Background task for database message creation."""
        try:
            await self.database.create_message(message)
        except Exception as e:
            logger.error(f"Background database create_message failed for {message.id}: {e}")
    
    async def get_conversation_history(self, session_id: str, 
                                     limit: Optional[int] = None) -> List[ChatMessage]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Optional limit on number of messages to return
            
        Returns:
            List of ChatMessages in chronological order
        """
        # Check in-memory cache first
        if session_id in self.session_contexts:
            messages = self.session_contexts[session_id]
            if limit:
                messages = messages[-limit:]
            return messages
        
        # Load from database
        if self.database:
            messages = await self.database.get_session_messages(session_id, limit)
            self.session_contexts[session_id] = messages
            return messages
        
        return []
    
    async def add_assistant_message(self, session_id: str, content: str,
                                  question_id: Optional[int] = None,
                                  agent_type: Optional[AgentType] = None) -> ChatMessage:
        """
        Add an assistant message to the context.
        
        Args:
            session_id: Session identifier
            content: Assistant message content
            question_id: Optional question ID
            agent_type: Optional agent type that generated this message
            
        Returns:
            Created ChatMessage
        """
        return await self.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            question_id=question_id,
            agent_type=agent_type
        )
    
    async def add_user_message(self, session_id: str, content: str,
                             question_id: Optional[int] = None) -> ChatMessage:
        """
        Add a user message to the context.
        
        Args:
            session_id: Session identifier
            content: User message content
            question_id: Optional question ID
            
        Returns:
            Created ChatMessage
        """
        return await self.add_message(
            session_id=session_id,
            role="user",
            content=content,
            question_id=question_id
        )
    
    async def add_system_message(self, session_id: str, content: str,
                               question_id: Optional[int] = None) -> ChatMessage:
        """
        Add a system message to the context.
        
        Args:
            session_id: Session identifier
            content: System message content
            question_id: Optional question ID
            
        Returns:
            Created ChatMessage
        """
        return await self.add_message(
            session_id=session_id,
            role="system",
            content=content,
            question_id=question_id
        )
    
    async def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of the conversation context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context summary information
        """
        messages = await self.get_conversation_history(session_id)
        
        user_messages = [msg for msg in messages if msg.role == "user"]
        assistant_messages = [msg for msg in messages if msg.role == "assistant"]
        system_messages = [msg for msg in messages if msg.role == "system"]
        
        # Get unique questions discussed
        questions_discussed = set()
        for msg in messages:
            if msg.question_id:
                questions_discussed.add(msg.question_id)
        
        return {
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "system_messages": len(system_messages),
            "questions_discussed": len(questions_discussed),
            "last_message_time": messages[-1].timestamp if messages else None,
            "conversation_duration": self._calculate_duration(messages)
        }
    
    def _calculate_duration(self, messages: List[ChatMessage]) -> Optional[float]:
        """Calculate conversation duration in minutes."""
        if len(messages) < 2:
            return None
        
        start_time = messages[0].timestamp
        end_time = messages[-1].timestamp
        
        duration = (end_time - start_time).total_seconds() / 60
        return round(duration, 2)
    
    async def clear_session_context(self, session_id: str):
        """
        Clear conversation context for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
        
        if self.database:
            await self.database.clear_session_messages(session_id)
        
        logger.info(f"Cleared context for session {session_id}")
