"""
Redis-Optimized Context Manager with LangChain Integration.
Provides fast, efficient context management using Redis as primary storage.
"""

import asyncio
import logging
import uuid
import json
import tiktoken
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

import redis.asyncio as redis
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from .context_manager import BaseContextManager
from database.models import ChatMessage, AgentType

logger = logging.getLogger(__name__)


class RedisContextManager(BaseContextManager):
    """
    Redis-optimized context manager with LangChain integration.
    Uses Redis for fast access and LangChain for intelligent summarization.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 database=None, llm_tool=None, **kwargs):
        """
        Initialize Redis context manager.
        
        Args:
            redis_url: Redis connection URL
            database: Database client for backup/persistence
            llm_tool: LLM tool for summarization
            **kwargs: Additional configuration options
        """
        super().__init__(database, **kwargs)
        
        self.redis_url = redis_url
        self.llm_tool = llm_tool
        
        # Initialize Redis connection
        self.redis = None
        self._redis_connected = False
        
        # Initialize tokenizer for precise token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
            
        # LangChain memory instances per session
        self.memory_instances = {}
        
        # Context configuration
        self.max_token_limit = kwargs.get("max_token_limit", 3000)
        self.recent_message_limit = kwargs.get("recent_message_limit", 10)
        
        # Initialize Redis connection
        asyncio.create_task(self._init_redis())
    
    async def _init_redis(self):
        """Initialize Redis connection asynchronously."""
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            self._redis_connected = True
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._redis_connected = False
    
    async def _ensure_redis_connected(self):
        """Ensure Redis connection is established."""
        if not self._redis_connected:
            await self._init_redis()
        return self._redis_connected
    
    def _get_or_create_memory(self, session_id: str) -> ConversationSummaryBufferMemory:
        """
        Get or create LangChain memory instance for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationSummaryBufferMemory instance
        """
        if session_id not in self.memory_instances:
            try:
                # Create Redis chat message history
                chat_history = RedisChatMessageHistory(
                    session_id=f"session:{session_id}",
                    url=self.redis_url,
                    key_prefix="langchain:chat:"
                )
                
                # Create memory with LLM for summarization
                llm = self._get_llm_for_summarization()
                
                self.memory_instances[session_id] = ConversationSummaryBufferMemory(
                    chat_memory=chat_history,
                    llm=llm,
                    max_token_limit=self.max_token_limit,
                    return_messages=True
                )
                
                logger.debug(f"Created LangChain memory for session {session_id}")
                
            except Exception as e:
                logger.error(f"Failed to create memory for session {session_id}: {e}")
                # Fallback to simple buffer memory
                from langchain.memory import ConversationBufferWindowMemory
                self.memory_instances[session_id] = ConversationBufferWindowMemory(
                    k=self.recent_message_limit,
                    return_messages=True
                )
        
        return self.memory_instances[session_id]
    
    def _get_llm_for_summarization(self):
        """Get LLM wrapper for summarization."""
        if not self.llm_tool:
            return None
            
        from langchain.llms.base import LLM
        
        llm_tool = self.llm_tool
        
        class LLMToolWrapper(LLM):
            def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
                try:
                    # Use the existing LLM tool for summarization
                    result = asyncio.run(llm_tool.generate_for_agent(
                        agent_name="context_summarizer",
                        prompt=prompt,
                        session_id="memory",
                        max_tokens=200,
                        temperature=0.1
                    ))
                    return result
                except Exception as e:
                    logger.warning(f"LLM summarization failed: {e}")
                    return "Previous conversation context unavailable."
            
            @property
            def _llm_type(self) -> str:
                return "llm_tool_wrapper"
        
        return LLMToolWrapper()
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken for accuracy."""
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            return super().count_tokens(text)
    
    async def add_message(self, session_id: str, role: str, content: str,
                         question_id: Optional[int] = None,
                         agent_type: Optional[AgentType] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> ChatMessage:
        """
        Add message to Redis and LangChain memory.
        
        Args:
            session_id: Session identifier
            role: Message role ("user", "assistant", "system")
            content: Message content
            question_id: Optional question ID
            agent_type: Optional agent type
            metadata: Optional additional metadata
            
        Returns:
            Created ChatMessage
        """
        message_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Create message object
        message = ChatMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            question_id=question_id,
            agent_type=agent_type,
            metadata=metadata or {},
            timestamp=timestamp
        )
        
        # Store in Redis for fast access
        await self._store_message_in_redis(message)
        
        # Add to LangChain memory
        await self._add_to_langchain_memory(session_id, role, content)
        
        # Background database backup (non-blocking)
        if self.database:
            asyncio.create_task(self._backup_message_to_db(message))
        
        logger.debug(f"Added {role} message to Redis for session {session_id}")
        return message
    
    async def _store_message_in_redis(self, message: ChatMessage):
        """Store message in Redis."""
        if not await self._ensure_redis_connected():
            logger.warning("Redis not connected, skipping Redis storage")
            return
        
        try:
            # Store individual message
            message_key = f"message:{message.session_id}:{message.id}"
            message_data = {
                "id": message.id,
                "session_id": message.session_id,
                "role": message.role,
                "content": message.content,
                "question_id": str(message.question_id) if message.question_id else "",
                "agent_type": message.agent_type.value if message.agent_type else "",
                "metadata": json.dumps(message.metadata),
                "timestamp": message.timestamp.isoformat()
            }
            
            await self.redis.hmset(message_key, message_data)
            await self.redis.expire(message_key, 86400 * 7)  # 7 days TTL
            
            # Add to session message list
            session_key = f"session:{message.session_id}:messages"
            await self.redis.lpush(session_key, message.id)
            await self.redis.expire(session_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error(f"Failed to store message in Redis: {e}")
    
    async def _add_to_langchain_memory(self, session_id: str, role: str, content: str):
        """Add message to LangChain memory."""
        try:
            memory = self._get_or_create_memory(session_id)
            
            if role == "user":
                memory.chat_memory.add_user_message(content)
            elif role == "assistant":
                memory.chat_memory.add_ai_message(content)
            else:
                # For system messages, add as AI message with prefix
                memory.chat_memory.add_ai_message(f"[System] {content}")
            
        except Exception as e:
            logger.error(f"Failed to add message to LangChain memory: {e}")
    
    async def _backup_message_to_db(self, message: ChatMessage):
        """Background task to backup message to database."""
        try:
            if self.database and hasattr(self.database, 'create_message'):
                await self.database.create_message(message)
        except Exception as e:
            logger.error(f"Failed to backup message to database: {e}")
    
    async def get_conversation_history(self, session_id: str, 
                                     limit: Optional[int] = None) -> List[ChatMessage]:
        """
        Get conversation history from Redis.
        
        Args:
            session_id: Session identifier
            limit: Optional limit on messages
            
        Returns:
            List of ChatMessage objects
        """
        if not await self._ensure_redis_connected():
            return await self._get_history_from_db(session_id, limit)
        
        try:
            # Get message IDs from session list
            session_key = f"session:{session_id}:messages"
            message_ids = await self.redis.lrange(session_key, 0, limit - 1 if limit else -1)
            
            messages = []
            for msg_id in reversed(message_ids):  # Reverse to get chronological order
                message_key = f"message:{session_id}:{msg_id}"
                message_data = await self.redis.hgetall(message_key)
                
                if message_data:
                    message = self._redis_data_to_message(message_data)
                    messages.append(message)
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get conversation history from Redis: {e}")
            return await self._get_history_from_db(session_id, limit)
    
    async def _get_history_from_db(self, session_id: str, 
                                  limit: Optional[int] = None) -> List[ChatMessage]:
        """Fallback to get history from database."""
        if self.database and hasattr(self.database, 'get_session_messages'):
            try:
                return await self.database.get_session_messages(session_id, limit)
            except Exception as e:
                logger.error(f"Failed to get history from database: {e}")
        
        return []
    
    def _redis_data_to_message(self, data: Dict[str, str]) -> ChatMessage:
        """Convert Redis data to ChatMessage object."""
        return ChatMessage(
            id=data["id"],
            session_id=data["session_id"],
            role=data["role"],
            content=data["content"],
            question_id=int(data["question_id"]) if data.get("question_id") and data["question_id"] else None,
            agent_type=AgentType(data["agent_type"]) if data.get("agent_type") and data["agent_type"] else None,
            metadata=json.loads(data.get("metadata", "{}")),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
        )
    
    async def get_context_for_llm(self, session_id: str, 
                                 max_tokens: int = 3000) -> Tuple[str, int]:
        """
        Get optimized context for LLM using LangChain memory.
        
        Args:
            session_id: Session identifier
            max_tokens: Maximum tokens allowed
            
        Returns:
            Tuple of (context_string, token_count)
        """
        try:
            memory = self._get_or_create_memory(session_id)
            
            # Get the buffer from LangChain memory (includes summarization)
            if hasattr(memory, 'buffer'):
                context = memory.buffer
            else:
                # Fallback to manual context building
                messages = await self.get_conversation_history(session_id, self.recent_message_limit)
                context = self.format_messages_for_llm(messages)
            
            token_count = self.count_tokens(context)
            
            # Trim if still too long
            if token_count > max_tokens:
                context = self._trim_context_to_tokens(context, max_tokens)
                token_count = self.count_tokens(context)
            
            logger.debug(f"Generated context for {session_id}: {token_count} tokens")
            return context, token_count
            
        except Exception as e:
            logger.error(f"Failed to get context for LLM: {e}")
            # Fallback to simple context
            messages = await self.get_conversation_history(session_id, 5)
            context = self.format_messages_for_llm(messages)
            return context, self.count_tokens(context)
    
    def _trim_context_to_tokens(self, context: str, max_tokens: int) -> str:
        """Trim context to fit within token limit."""
        lines = context.split('\n')
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
    
    async def clear_session_context(self, session_id: str):
        """Clear session context from Redis and LangChain memory."""
        try:
            # Clear LangChain memory
            if session_id in self.memory_instances:
                self.memory_instances[session_id].clear()
                del self.memory_instances[session_id]
            
            # Clear Redis data
            if await self._ensure_redis_connected():
                # Get all message IDs
                session_key = f"session:{session_id}:messages"
                message_ids = await self.redis.lrange(session_key, 0, -1)
                
                # Delete individual messages
                for msg_id in message_ids:
                    message_key = f"message:{session_id}:{msg_id}"
                    await self.redis.delete(message_key)
                
                # Delete session message list
                await self.redis.delete(session_key)
                
                # Clear LangChain Redis history
                langchain_key = f"langchain:chat:session:{session_id}"
                await self.redis.delete(langchain_key)
            
            logger.info(f"Cleared Redis context for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear Redis context: {e}")
    
    async def get_memory_stats(self, session_id: str) -> Dict[str, Any]:
        """Get memory statistics for a session."""
        try:
            memory = self._get_or_create_memory(session_id)
            
            # Get message count from Redis
            message_count = 0
            if await self._ensure_redis_connected():
                session_key = f"session:{session_id}:messages"
                message_count = await self.redis.llen(session_key)
            
            # Get buffer info
            buffer_info = {}
            if hasattr(memory, 'buffer'):
                buffer_info["has_buffer"] = True
                buffer_info["buffer_tokens"] = self.count_tokens(memory.buffer)
            
            if hasattr(memory, 'moving_summary_buffer'):
                buffer_info["has_summary"] = bool(memory.moving_summary_buffer)
                if memory.moving_summary_buffer:
                    buffer_info["summary_tokens"] = self.count_tokens(memory.moving_summary_buffer)
            
            return {
                "session_id": session_id,
                "redis_connected": self._redis_connected,
                "message_count": message_count,
                "langchain_memory_type": type(memory).__name__,
                "buffer_info": buffer_info,
                "max_token_limit": self.max_token_limit
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"error": str(e)}
