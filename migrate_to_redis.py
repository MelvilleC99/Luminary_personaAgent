#!/usr/bin/env python3
"""
Migration script to set up Redis and test the new memory system.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from memory.redis_context_manager import RedisContextManager
from memory.managers.session_manager import SessionManager
from memory.managers.conversation_state import ConversationStateManager
from orchestrator.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_redis_connection():
    """Test Redis connection."""
    try:
        redis_context = RedisContextManager(redis_url=settings.redis_url)
        await redis_context._init_redis()
        
        if redis_context._redis_connected:
            logger.info("✅ Redis connection successful")
            return True
        else:
            logger.error("❌ Redis connection failed")
            return False
    except Exception as e:
        logger.error(f"❌ Redis connection error: {e}")
        return False


async def test_memory_system():
    """Test the new memory system."""
    try:
        # Initialize components
        redis_context = RedisContextManager(redis_url=settings.redis_url)
        session_manager = SessionManager(redis_context_manager=redis_context)
        
        # Test session creation
        session = await session_manager.create_session(user_id="test_user")
        logger.info(f"✅ Created test session: {session.id}")
        
        # Test message storage
        await redis_context.add_message(
            session_id=session.id,
            role="user",
            content="Test message for memory system"
        )
        
        await redis_context.add_message(
            session_id=session.id,
            role="assistant",
            content="Test response from assistant"
        )
        
        # Test context retrieval
        context, token_count = await redis_context.get_context_for_llm(session.id)
        logger.info(f"✅ Retrieved context: {token_count} tokens")
        
        # Test conversation state
        state_manager = ConversationStateManager(
            redis_context_manager=redis_context,
            framework_sections={"1": {"section_name": "Test Section", "criteria": {"test": {}}}}
        )
        
        state = await state_manager.get_conversation_state(session.id)
        logger.info(f"✅ Retrieved conversation state: Section {state.current_section}")
        
        # Test cleanup
        await redis_context.clear_session_context(session.id)
        await session_manager.expire_session(session.id)
        logger.info("✅ Cleaned up test data")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Memory system test failed: {e}")
        return False


async def main():
    """Main migration and testing function."""
    print("🚀 Starting Redis Memory System Migration")
    print("=" * 50)
    
    # Test Redis connection
    print("1. Testing Redis connection...")
    redis_ok = await test_redis_connection()
    
    if not redis_ok:
        print("\n❌ Redis connection failed!")
        print("Please ensure Redis is running:")
        print("  - Install Redis: brew install redis (Mac) or apt-get install redis (Ubuntu)")
        print("  - Start Redis: redis-server")
        print("  - Or use Docker: docker run -d -p 6379:6379 redis")
        return False
    
    # Test memory system
    print("\n2. Testing memory system...")
    memory_ok = await test_memory_system()
    
    if not memory_ok:
        print("\n❌ Memory system test failed!")
        return False
    
    print("\n✅ Migration completed successfully!")
    print("\nNext steps:")
    print("1. Update your environment variables with Redis URL")
    print("2. Restart your application")
    print("3. The new Redis-based memory system is now active")
    print("\nRedis configuration:")
    print(f"  REDIS_URL={settings.redis_url}")
    print(f"  MAX_CONTEXT_TOKENS={settings.max_context_tokens}")
    print(f"  RECENT_MESSAGE_LIMIT={settings.recent_message_limit}")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
