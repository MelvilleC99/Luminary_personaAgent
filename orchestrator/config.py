"""
Configuration management for the Luminary Persona Agent.
"""

import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # LLM API Keys
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    
    # LLM Assignments
    question_agent_llm: str = os.getenv("QUESTION_AGENT_LLM", "openai")
    assessment_agent_llm: str = os.getenv("ASSESSMENT_AGENT_LLM", "deepseek")
    scraper_agent_llm: str = os.getenv("SCRAPER_AGENT_LLM", "openai")
    persona_agent_llm: str = os.getenv("PERSONA_AGENT_LLM", "claude")
    
    # Application Settings
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    max_follow_ups: int = int(os.getenv("MAX_FOLLOW_UPS", "3"))
    assessment_threshold: float = float(os.getenv("ASSESSMENT_THRESHOLD", "7.0"))
    
    # API Configuration
    api_host: str = os.getenv("API_HOST", "localhost")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    # Session Management
    session_timeout_hours: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    
    @property
    def llm_config(self) -> Dict[str, str]:
        """Get LLM assignments as a dictionary."""
        return {
            "question_agent": self.question_agent_llm,
            "assessment_agent": self.assessment_agent_llm,
            "scraper_agent": self.scraper_agent_llm,
            "persona_agent": self.persona_agent_llm
        }
    
    @property
    def api_keys(self) -> Dict[str, str]:
        """Get all API keys as a dictionary."""
        return {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "deepseek": self.deepseek_api_key,
            "claude": self.anthropic_api_key  # Alias for anthropic
        }
    
    def validate_required_keys(self) -> bool:
        """Validate that required API keys are present."""
        required_llms = set(self.llm_config.values())
        available_keys = {k: v for k, v in self.api_keys.items() if v}
        
        missing_keys = []
        for llm in required_llms:
            if llm not in available_keys:
                missing_keys.append(llm)
        
        if missing_keys:
            raise ValueError(f"Missing API keys for: {missing_keys}")
        
        return True


# Global settings instance
settings = Settings()
