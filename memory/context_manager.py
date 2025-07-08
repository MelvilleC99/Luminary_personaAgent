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
    async def get_efficient_context(self, session_id: str, max_recent_turns: int = 10) -> List[Dict[str, Any]]:
        """
        Get efficient context with recent detailed + older summarized.
        
        Args:
            session_id: Session identifier
            max_recent_turns: Number of recent turns to keep in detail
            
        Returns:
            Efficient context list optimized for token usage
        """
        try:
            # Get all messages for the session
            all_messages = await self.get_conversation_history(session_id)
            
            if not all_messages:
                return []
            
            # If we have fewer messages than the limit, return all
            if len(all_messages) <= max_recent_turns:
                return [self._message_to_dict(msg) for msg in all_messages]
            
            # Split into recent and older
            recent_messages = all_messages[-max_recent_turns:]
            older_messages = all_messages[:-max_recent_turns]
            
            # Create efficient context
            efficient_context = []
            
            # Add older messages summary if we have older messages
            if older_messages:
                summary = await self._summarize_older_messages(older_messages)
                efficient_context.append({
                    "role": "system",
                    "content": f"Previous conversation summary: {summary}",
                    "is_summary": True,
                    "summarized_count": len(older_messages)
                })
            
            # Add recent messages in detail
            for msg in recent_messages:
                efficient_context.append(self._message_to_dict(msg))
            
            logger.info(f"Generated efficient context: {len(older_messages)} summarized, {len(recent_messages)} detailed")
            return efficient_context
            
        except Exception as e:
            logger.error(f"Failed to get efficient context for session {session_id}: {e}")
            return []
    
    async def _summarize_older_messages(self, messages: List[ChatMessage]) -> str:
        """
        Summarize older messages for efficient context.
        
        Args:
            messages: List of older messages to summarize
            
        Returns:
            Summarized text
        """
        if not messages:
            return ""
        
        # Extract key information from older messages
        user_inputs = []
        assistant_responses = []
        
        for msg in messages:
            if msg.role == "user":
                user_inputs.append(msg.content)
            elif msg.role == "assistant":
                assistant_responses.append(msg.content)
        
        # Create summary
        summary_parts = []
        
        if user_inputs:
            # Get key themes from user inputs
            user_themes = self._extract_themes(user_inputs)
            summary_parts.append(f"User shared information about: {', '.join(user_themes)}")
        
        if assistant_responses:
            # Extract key topics from assistant responses
            assistant_themes = self._extract_themes(assistant_responses)
            summary_parts.append(f"Discussed topics: {', '.join(assistant_themes)}")
        
        return " | ".join(summary_parts)
    
    def _extract_themes(self, messages: List[str]) -> List[str]:
        """
        Extract key themes from messages for summarization.
        
        Args:
            messages: List of message contents
            
        Returns:
            List of key themes
        """
        # Simple theme extraction - could be enhanced with NLP
        themes = []
        
        # Common business/persona themes
        theme_keywords = {
            "expertise": ["expert", "expertise", "specialization", "skill", "knowledge"],
            "clients": ["client", "customer", "target", "audience", "market"],
            "services": ["service", "offer", "product", "solution", "help"],
            "values": ["value", "principle", "belief", "mission", "vision"],
            "goals": ["goal", "objective", "aim", "target", "want"],
            "challenges": ["challenge", "problem", "issue", "struggle", "difficulty"],
            "brand": ["brand", "personality", "voice", "tone", "style"],
            "content": ["content", "marketing", "message", "communication"],
            "business": ["business", "company", "organization", "firm"],
            "results": ["result", "outcome", "success", "achievement", "impact"]
        }
        
        combined_text = " ".join(messages).lower()
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                themes.append(theme)
        
        return themes[:5]  # Return top 5 themes
    
    def _message_to_dict(self, message: ChatMessage) -> Dict[str, Any]:
        """Convert ChatMessage to dictionary format."""
        return {
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat() if message.timestamp else None,
            "question_id": message.question_id,
            "agent_type": message.agent_type.value if message.agent_type else None,
            "metadata": message.metadata
        }
    
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
                    "last_activity": None,
                    "key_themes": []
                }
            
            # Count messages by type
            message_counts = {
                "user": 0,
                "assistant": 0,
                "system": 0
            }
            
            for msg in messages:
                if msg.role in message_counts:
                    message_counts[msg.role] += 1
            
            # Extract themes
            all_content = [msg.content for msg in messages if msg.role in ["user", "assistant"]]
            themes = self._extract_themes(all_content)
            
            return {
                "total_messages": len(messages),
                "user_messages": message_counts["user"],
                "assistant_messages": message_counts["assistant"],
                "system_messages": message_counts["system"],
                "conversation_started": messages[0].timestamp.isoformat() if messages[0].timestamp else None,
                "last_activity": messages[-1].timestamp.isoformat() if messages[-1].timestamp else None,
                "key_themes": themes,
                "conversation_turns": len([msg for msg in messages if msg.role == "user"])
            }
            
        except Exception as e:
            logger.error(f"Failed to get context summary for session {session_id}: {e}")
            return {"error": str(e)}
    
    async def add_framework_extraction(self, session_id: str, 
                                     extraction_data: Dict[str, Any]) -> None:
        """
        Add framework extraction metadata to context.
        
        Args:
            session_id: Session identifier
            extraction_data: Framework extraction information
        """
        try:
            # Add as system message for context
            await self.add_system_message(
                session_id,
                f"Framework extraction: {extraction_data.get('framework_section', 'unknown')} - {extraction_data.get('criteria_key', 'unknown')}",
                metadata={
                    "type": "framework_extraction",
                    "extraction_data": extraction_data
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to add framework extraction to context: {e}")
    
    async def optimize_context_for_tokens(self, session_id: str, 
                                        max_tokens: int = 3000) -> List[Dict[str, Any]]:
        """
        Optimize context to fit within token limits.
        
        Args:
            session_id: Session identifier
            max_tokens: Maximum tokens allowed
            
        Returns:
            Optimized context list
        """
        try:
            # Start with efficient context
            context = await self.get_efficient_context(session_id)
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = sum(len(msg.get("content", "")) for msg in context) // 4
            
            if estimated_tokens <= max_tokens:
                return context
            
            # If still too large, reduce recent messages
            while estimated_tokens > max_tokens and len(context) > 1:
                # Remove oldest non-summary message
                for i, msg in enumerate(context):
                    if not msg.get("is_summary", False):
                        context.pop(i)
                        break
                
                # Recalculate tokens
                estimated_tokens = sum(len(msg.get("content", "")) for msg in context) // 4
            
            logger.info(f"Optimized context to ~{estimated_tokens} tokens ({len(context)} messages)")
            return context
            
        except Exception as e:
            logger.error(f"Failed to optimize context for tokens: {e}")
            return await self.get_efficient_context(session_id, max_recent_turns=5)
