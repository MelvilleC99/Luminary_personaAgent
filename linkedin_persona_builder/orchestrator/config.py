import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """
    Application configuration with environment variable support
    """
    
    def __init__(self):
        # Database Configuration
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_ttl: int = int(os.getenv("REDIS_TTL", "86400"))  # 24 hours
        
        # Supabase Configuration
        self.supabase_url: str = os.getenv("SUPABASE_URL", "")
        self.supabase_key: str = os.getenv("SUPABASE_KEY", "")
        
        # OpenAI Configuration
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        
        # Application Configuration
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        
        # Session Configuration
        self.session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))  # 24 hours
        self.max_follow_up_attempts: int = int(os.getenv("MAX_FOLLOW_UP_ATTEMPTS", "2"))
        self.section_completion_threshold: float = float(os.getenv("SECTION_COMPLETION_THRESHOLD", "0.9"))
        
        # LLM Configuration
        self.max_tokens_per_session: int = int(os.getenv("MAX_TOKENS_PER_SESSION", "6000"))
        self.max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "4000"))
        self.temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
        
        # Conversation Configuration
        self.recent_turn_count: int = int(os.getenv("RECENT_TURN_COUNT", "5"))
        self.similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
        self.cache_ttl: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
        
        # Performance Configuration
        self.max_concurrent_sessions: int = int(os.getenv("MAX_CONCURRENT_SESSIONS", "50"))
        self.response_timeout_seconds: int = int(os.getenv("RESPONSE_TIMEOUT_SECONDS", "30"))


# Global settings instance
settings = Settings()


# Configuration validation
def validate_config():
    """Validate critical configuration values"""
    required_vars = [
        "openai_api_key"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not getattr(settings, var, None):
            missing_vars.append(var.upper())
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Check optional Supabase configuration
    if not settings.supabase_url or not settings.supabase_key:
        print("⚠️ Supabase credentials not provided. Supabase features will be disabled.")
    
    return True
