import redis
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from orchestrator.config import settings
from data.redis.schemas import (
    SessionState, PersonaData, ConversationHistory, 
    LLMCacheEntry, REDIS_KEYS, TTL_CONFIG
)
import logging
logger = logging.getLogger(__name__)


class RedisConnectionError(Exception):
    """Redis connection error"""
    pass


class RedisManager:
    """
    Redis operations manager with connection pooling and error handling
    """
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize Redis connection with pool"""
        try:
            self.connection_pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                decode_responses=True
            )
            
            self.client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            self.client.ping()
            logger.info("Redis connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise RedisConnectionError(f"Redis connection failed: {e}")
    
    def _get_key(self, key_pattern: str, **kwargs) -> str:
        """Format Redis key with parameters"""
        if key_pattern in REDIS_KEYS:
            return REDIS_KEYS[key_pattern].format(**kwargs)
        return key_pattern
    
    def _serialize_data(self, data: Any) -> str:
        """Serialize data for Redis storage"""
        if hasattr(data, 'dict'):  # Pydantic model
            return json.dumps(data.dict(), default=str)
        elif hasattr(data, '__dict__'):  # Regular object
            return json.dumps(data.__dict__, default=str)
        else:
            return json.dumps(data, default=str)
    
    def _deserialize_data(self, data: str, model_class=None):
        """Deserialize data from Redis"""
        try:
            parsed = json.loads(data)
            if model_class:
                return model_class(**parsed)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"JSON deserialization error: {e}")
            return None
    
    # Session Management
    async def set_session_data(self, session_id: str, session_state: SessionState) -> bool:
        """Store session state in Redis"""
        try:
            key = self._get_key("session", session_id=session_id)
            
            # Use pipeline for atomic operation
            pipe = self.client.pipeline()
            
            # Store as hash for easier field updates
            session_dict = session_state.dict()
            pipe.hset(key, mapping={k: self._serialize_data(v) for k, v in session_dict.items()})
            pipe.expire(key, TTL_CONFIG["session"])
            
            pipe.execute()
            
            logger.info("Session data stored", session_id=session_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store session data: {e} - session_id: {session_id}")
            raise RedisConnectionError(f"Session storage failed: {e}")
    
    async def get_session_data(self, session_id: str) -> Optional[SessionState]:
        """Retrieve session state from Redis"""
        try:
            key = self._get_key("session", session_id=session_id)
            data = self.client.hgetall(key)
            
            if not data:
                return None
            
            # Deserialize hash fields
            deserialized = {}
            for field, value in data.items():
                try:
                    deserialized[field] = json.loads(value)
                except json.JSONDecodeError:
                    deserialized[field] = value
            
            return SessionState(**deserialized)
            
        except Exception as e:
            logger.error(f"Failed to retrieve session data: {e} - session_id: {session_id}")
            return None
    
    async def update_session_field(self, session_id: str, field: str, value: Any) -> bool:
        """Update specific session field"""
        try:
            key = self._get_key("session", session_id=session_id)
            
            # Update specific field and reset TTL
            pipe = self.client.pipeline()
            pipe.hset(key, field, self._serialize_data(value))
            pipe.expire(key, TTL_CONFIG["session"])
            pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session field {field}: {e} - session_id: {session_id}")
            return False
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists in Redis"""
        try:
            key = self._get_key("session", session_id=session_id)
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check session existence: {e} - session_id: {session_id}")
            return False
    
    # Persona Data Management
    async def set_persona_data(self, session_id: str, persona_data: PersonaData) -> bool:
        """Store persona data in Redis"""
        try:
            key = self._get_key("persona", session_id=session_id)
            
            serialized = self._serialize_data(persona_data)
            self.client.setex(key, TTL_CONFIG["persona"], serialized)
            
            logger.info("Persona data stored", session_id=session_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store persona data: {e} - session_id: {session_id}")
            return False
    
    async def get_persona_data(self, session_id: str) -> Optional[PersonaData]:
        """Retrieve persona data from Redis"""
        try:
            key = self._get_key("persona", session_id=session_id)
            data = self.client.get(key)
            
            if not data:
                return None
            
            return self._deserialize_data(data, PersonaData)
            
        except Exception as e:
            logger.error(f"Failed to retrieve persona data: {e} - session_id: {session_id}")
            return None
    
    # Conversation History Management
    async def add_conversation_turn(self, session_id: str, turn_data: Dict[str, Any]) -> bool:
        """Add conversation turn to history"""
        try:
            key = self._get_key("history", session_id=session_id)
            
            # Add to front of list and trim to max length
            pipe = self.client.pipeline()
            pipe.lpush(key, self._serialize_data(turn_data))
            pipe.ltrim(key, 0, 11)  # Keep last 12 turns
            pipe.expire(key, TTL_CONFIG["history"])
            pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add conversation turn: {e} - session_id: {session_id}")
            return False
    
    async def get_conversation_history(self, session_id: str, count: int = 12) -> List[Dict[str, Any]]:
        """Get conversation history"""
        try:
            key = self._get_key("history", session_id=session_id)
            data = self.client.lrange(key, 0, count - 1)
            
            history = []
            for item in data:
                parsed = self._deserialize_data(item)
                if parsed:
                    history.append(parsed)
            
            return history[::-1]  # Return in chronological order
            
        except Exception as e:
            logger.error(f"Failed to retrieve conversation history: {e} - session_id: {session_id}")
            return []
    
    # Token Usage Tracking
    async def increment_token_usage(self, session_id: str, tokens: int) -> int:
        """Increment token usage for session"""
        try:
            key = self._get_key("tokens", session_id=session_id)
            
            pipe = self.client.pipeline()
            pipe.incrby(key, tokens)
            pipe.expire(key, TTL_CONFIG["tokens"])
            result = pipe.execute()
            
            return result[0]  # New total
            
        except Exception as e:
            logger.error(f"Failed to increment token usage: {e} - session_id: {session_id}")
            return 0
    
    async def get_token_usage(self, session_id: str) -> int:
        """Get current token usage for session"""
        try:
            key = self._get_key("tokens", session_id=session_id)
            result = self.client.get(key)
            return int(result) if result else 0
            
        except Exception as e:
            logger.error(f"Failed to get token usage: {e} - session_id: {session_id}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connection health and performance"""
        try:
            start_time = datetime.now()
            
            # Test basic connectivity
            self.client.ping()
            
            # Test write/read operations
            test_key = "health_check_test"
            test_value = "test_data"
            
            # Write test
            self.client.setex(test_key, 10, test_value)
            
            # Read test
            result = self.client.get(test_key)
            
            # Clean up
            self.client.delete(test_key)
            
            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if result == test_value:
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "details": "Redis connection and operations working correctly"
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time_ms": round(response_time, 2),
                    "details": "Redis read/write test failed"
                }
                
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "response_time_ms": 0,
                "details": f"Redis connection error: {str(e)}"
            }# Global Redis manager instance
redis_manager = RedisManager()


# Async context manager for Redis operations
class RedisContext:
    """Context manager for Redis operations with error handling"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = datetime.now()
        return redis_manager
    
    async def __aexiter__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000
            logger.error(
                f"Redis operation failed: {self.operation_name}",
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                duration_ms=duration
            )
            return False  # Don't suppress the exception
        return None


# Convenience functions for common operations
async def get_session(session_id: str) -> Optional[SessionState]:
    """Convenience function to get session data"""
    async with RedisContext("get_session"):
        return await redis_manager.get_session_data(session_id)


async def save_session(session_id: str, session_state: SessionState) -> bool:
    """Convenience function to save session data"""
    async with RedisContext("save_session"):
        return await redis_manager.set_session_data(session_id, session_state)


async def get_persona(session_id: str) -> Optional[PersonaData]:
    """Convenience function to get persona data"""
    async with RedisContext("get_persona"):
        return await redis_manager.get_persona_data(session_id)


async def save_persona(session_id: str, persona_data: PersonaData) -> bool:
    """Convenience function to save persona data"""
    async with RedisContext("save_persona"):
        return await redis_manager.set_persona_data(session_id, persona_data)


async def add_conversation_turn(session_id: str, turn_data: Dict[str, Any]) -> bool:
    """Convenience function to add conversation turn"""
    async with RedisContext("add_conversation_turn"):
        return await redis_manager.add_conversation_turn(session_id, turn_data)


async def track_tokens(session_id: str, tokens: int) -> int:
    """Convenience function to track token usage"""
    async with RedisContext("track_tokens"):
        return await redis_manager.increment_token_usage(session_id, tokens)
