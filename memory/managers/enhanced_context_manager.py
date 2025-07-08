"""
Enhanced Context Manager with LangChain memory integration.
"""

import asyncio
import logging
import tiktoken
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from langchain.memory import ConversationSummaryBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_core.messages import BaseMessage as CoreBaseMessage

from database.models import ChatMessage
from database.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class EnhancedContextManager:
    """
    Enhanced context manager with intelligent summarization and token management.
    Uses LangChain memory for efficient context window management.
    """
    
    def __init__(self, database: SupabaseClient, llm_tool=None):
        self.database = database
        self.llm_tool = llm_tool
        
        # Initialize tokenizer for precise token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # fallback
        
        # LangChain memory for conversation summarization
        self.memory_instances = {}  # session_id -> ConversationSummaryBufferMemory
        
        # Context window management
        self.max_tokens = 4000  # Conservative limit for context
        self.recent_message_limit = 6  # Keep last 6 messages in full detail
        
    def _get_or_create_memory(self, session_id: str):
        """Get or create memory instance for session (simplified)."""
        if session_id not in self.memory_instances:
            # Use simple buffer memory to avoid deprecation warnings
            from langchain.memory import ConversationBufferWindowMemory
            self.memory_instances[session_id] = ConversationBufferWindowMemory(
                k=self.recent_message_limit,
                return_messages=True
            )
        
        return self.memory_instances[session_id]
    
    def _create_llm_wrapper(self):
        """Create a simple LLM wrapper for LangChain memory."""
        from langchain.llms.base import LLM
        
        llm_tool = self.llm_tool  # Capture reference to outer class's llm_tool
        
        class LLMToolWrapper(LLM):
            def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
                # Use the existing LLM tool for summarization
                try:
                    if llm_tool:
                        result = asyncio.run(llm_tool.generate_for_agent(
                            agent_name="memory_summarizer",
                            prompt=prompt,
                            session_id="memory",
                            max_tokens=200,
                            temperature=0.1
                        ))
                        return result
                    else:
                        return "LLM tool not available for summarization."
                except Exception as e:
                    logger.warning(f"LLM summarization failed: {e}")
                    return "Conversation summary unavailable."
            
            @property
            def _llm_type(self) -> str:
                return "llm_tool_wrapper"
        
        return LLMToolWrapper()
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            # Fallback to character estimation
            return max(1, len(text) // 4)
    
    async def add_message(self, session_id: str, role: str, content: str, 
                         question_id: Optional[int] = None, agent_type: Optional[str] = None) -> ChatMessage:
        """Add message to conversation with enhanced context management."""
        
        # Generate proper UUID for message ID
        import uuid
        message_id = str(uuid.uuid4())
        
        # Ensure content is always a string
        if isinstance(content, dict):
            content = content.get("message", str(content))
        elif not isinstance(content, str):
            content = str(content)
        
        # Create message
        message = ChatMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            question_id=question_id,
            agent_type=agent_type,
            timestamp=datetime.utcnow()
        )
        
        # Store in database
        await self.database.create_message(message)
        
        # Update LangChain memory
        memory = self._get_or_create_memory(session_id)
        
        if role == "user":
            memory.chat_memory.add_user_message(content)
        elif role == "assistant":
            memory.chat_memory.add_ai_message(content)
        
        logger.debug(f"Added message to session {session_id}: {role}")
        return message
    
    async def get_context_for_llm(self, session_id: str, include_system_context: str = "") -> Tuple[str, int]:
        """
        Get optimized context for LLM with token management.
        Returns (context_string, token_count)
        """
        
        # Get LangChain memory
        memory = self._get_or_create_memory(session_id)
        
        # Build context components
        context_parts = []
        
        # Add system context if provided
        if include_system_context:
            context_parts.append(f"SYSTEM CONTEXT:\n{include_system_context}\n")
        
        # Add conversation history from memory
        try:
            # Get messages from LangChain memory (summarized + recent)
            messages = memory.chat_memory.messages
            
            if messages:
                context_parts.append("CONVERSATION HISTORY:")
                for msg in messages:
                    if hasattr(msg, 'content'):
                        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                        context_parts.append(f"{role}: {msg.content}")
                context_parts.append("")
        
        except Exception as e:
            logger.warning(f"Could not get LangChain memory: {e}")
            # Fallback to database messages
            recent_messages = await self.get_recent_messages(session_id, limit=self.recent_message_limit)
            if recent_messages:
                context_parts.append("RECENT CONVERSATION:")
                for msg in recent_messages:
                    role = msg.role.title()
                    context_parts.append(f"{role}: {msg.content}")
                context_parts.append("")
        
        # Combine context
        full_context = "\n".join(context_parts)
        token_count = self.count_tokens(full_context)
        
        # Trim if too long
        if token_count > self.max_tokens:
            full_context = self._trim_context(full_context, self.max_tokens)
            token_count = self.count_tokens(full_context)
        
        logger.debug(f"Generated context for {session_id}: {token_count} tokens")
        return full_context, token_count
    
    def _trim_context(self, context: str, max_tokens: int) -> str:
        """Trim context to fit within token limit."""
        lines = context.split('\n')
        
        # Keep system context and recent messages
        trimmed_lines = []
        current_tokens = 0
        
        # Add lines from end (most recent) first
        for line in reversed(lines):
            line_tokens = self.count_tokens(line)
            if current_tokens + line_tokens <= max_tokens:
                trimmed_lines.insert(0, line)
                current_tokens += line_tokens
            else:
                break
        
        return '\n'.join(trimmed_lines)
    
    async def get_recent_messages(self, session_id: str, limit: int = 10) -> List[ChatMessage]:
        """Get recent messages from database."""
        try:
            return await self.database.get_session_messages(session_id, limit=limit)
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            return []
    
    async def clear_session_context(self, session_id: str):
        """Clear context for a session."""
        try:
            # Clear LangChain memory
            if session_id in self.memory_instances:
                self.memory_instances[session_id].clear()
                del self.memory_instances[session_id]
            
            # Clear database messages
            await self.database.clear_session_messages(session_id)
            
            logger.info(f"Cleared context for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to clear context: {e}")
    
    async def get_conversation_summary(self, session_id: str) -> str:
        """Get conversation summary from LangChain memory."""
        try:
            memory = self._get_or_create_memory(session_id)
            if hasattr(memory, 'moving_summary_buffer') and memory.moving_summary_buffer:
                return memory.moving_summary_buffer
            elif hasattr(memory, 'buffer'):
                return str(memory.buffer)
            else:
                return "No conversation summary available."
        except Exception as e:
            logger.warning(f"Could not get conversation summary: {e}")
            return "Summary unavailable."
