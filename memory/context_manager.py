"""
Base Context Manager Interface for Memory System.
Defines the contract for all context manager implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from database.models import ChatMessage, AgentType

logger = logging.getLogger(__name__)


class BaseContextManager(ABC):
    """
    Abstract base class for context managers.
    Defines the interface that all context managers must implement.
    """
    
    def __init__(self, database=None, **kwargs):
        """
        Initialize the base context manager.
        
        Args:
            database: Database client for persistence
            **kwargs: Additional configuration options
        """
        self.database = database
        self.config = kwargs
        
    @abstractmethod
    async def add_message(self, session_id: str, role: str, content: str,
                         question_id: Optional[int] = None,
                         agent_type: Optional[AgentType] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> ChatMessage:
        """
        Add a message to the conversation context.
        
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_context_for_llm(self, session_id: str, 
                                 max_tokens: int = 3000) -> Tuple[str, int]:
        """
        Get optimized context for LLM with token management.
        
        Args:
            session_id: Session identifier
            max_tokens: Maximum tokens allowed
            
        Returns:
            Tuple of (context_string, token_count)
        """
        pass
    
    @abstractmethod
    async def clear_session_context(self, session_id: str):
        """
        Clear conversation context for a session.
        
        Args:
            session_id: Session identifier
        """
        pass
    
    # Helper methods that can be overridden but have default implementations
    
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
    
    async def add_system_message(self, session_id: str, content: str,
                               question_id: Optional[int] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> ChatMessage:
        """
        Add a system message to the context.
        
        Args:
            session_id: Session identifier
            content: System message content
            question_id: Optional question ID
            metadata: Optional additional metadata
            
        Returns:
            Created ChatMessage
        """
        return await self.add_message(
            session_id=session_id,
            role="system",
            content=content,
            question_id=question_id,
            metadata=metadata
        )
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using simple estimation.
        Override this method for more accurate token counting.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Simple estimation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)
    
    def format_messages_for_llm(self, messages: List[ChatMessage]) -> str:
        """
        Format messages for LLM consumption.
        
        Args:
            messages: List of ChatMessage objects
            
        Returns:
            Formatted string for LLM
        """
        formatted_lines = []
        
        for msg in messages:
            role_label = msg.role.title()
            timestamp = msg.timestamp.strftime("%H:%M") if msg.timestamp else "now"
            formatted_lines.append(f"{role_label} ({timestamp}): {msg.content}")
        
        return "\n".join(formatted_lines)
    
    async def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of the conversation context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context summary with key metrics
        """
        try:
            messages = await self.get_conversation_history(session_id)
            
            if not messages:
                return {
                    "total_messages": 0,
                    "user_messages": 0,
                    "assistant_messages": 0,
                    "system_messages": 0,
                    "conversation_started": None,
                    "last_activity": None
                }
            
            # Count messages by type
            message_counts = {"user": 0, "assistant": 0, "system": 0}
            
            for msg in messages:
                if msg.role in message_counts:
                    message_counts[msg.role] += 1
            
            return {
                "total_messages": len(messages),
                "user_messages": message_counts["user"],
                "assistant_messages": message_counts["assistant"],
                "system_messages": message_counts["system"],
                "conversation_started": messages[0].timestamp.isoformat() if messages[0].timestamp else None,
                "last_activity": messages[-1].timestamp.isoformat() if messages[-1].timestamp else None,
                "conversation_turns": len([msg for msg in messages if msg.role == "user"])
            }
            
        except Exception as e:
            logger.error(f"Failed to get context summary for session {session_id}: {e}")
            return {"error": str(e)}
