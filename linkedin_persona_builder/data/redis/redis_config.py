"""Redis configuration and connection setup"""

from orchestrator.config import settings
from data.redis.redis_utils import redis_manager


async def initialize_redis():
    """Initialize Redis connection and verify connectivity"""
    try:
        health = await redis_manager.health_check()
        if health["status"] == "healthy":
            print(f"✅ Redis connected successfully (response time: {health['response_time_ms']}ms)")
            return True
        else:
            print(f"❌ Redis health check failed: {health['details']}")
            return False
    except Exception as e:
        print(f"❌ Redis initialization failed: {e}")
        return False


async def cleanup_redis():
    """Cleanup Redis connections"""
    try:
        redis_manager.close()
        print("✅ Redis connections closed")
    except Exception as e:
        print(f"⚠️  Redis cleanup warning: {e}")


# Export main components
__all__ = [
    "redis_manager",
    "initialize_redis", 
    "cleanup_redis"
]
