import structlog
import logging
import sys
from datetime import datetime
from typing import Any, Dict


def configure_logging(log_level: str = "INFO", environment: str = "development"):
    """
    Configure structured logging for the application
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if environment == "production" else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    return structlog.get_logger()


def get_logger(name: str = __name__):
    """Get a configured logger instance"""
    return structlog.get_logger(name)


class PersonaLogger:
    """Specialized logger for persona building events"""
    
    def __init__(self):
        self.logger = get_logger("persona_builder")
    
    def session_started(self, session_id: str, user_id: str):
        """Log session start"""
        self.logger.info(
            "session_started",
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
    
    def section_completed(self, session_id: str, section_number: int, completion_percentage: float):
        """Log section completion"""
        self.logger.info(
            "section_completed",
            session_id=session_id,
            section_number=section_number,
            completion_percentage=completion_percentage
        )
    
    def response_evaluated(self, session_id: str, criterion: str, quality_score: int, confidence: float):
        """Log response evaluation"""
        self.logger.info(
            "response_evaluated",
            session_id=session_id,
            criterion=criterion,
            quality_score=quality_score,
            confidence=confidence
        )
    
    def follow_up_generated(self, session_id: str, criterion: str, attempt_number: int):
        """Log follow-up question generation"""
        self.logger.info(
            "follow_up_generated",
            session_id=session_id,
            criterion=criterion,
            attempt_number=attempt_number
        )
    
    def session_completed(self, session_id: str, final_completion: float, duration_minutes: float):
        """Log session completion"""
        self.logger.info(
            "session_completed",
            session_id=session_id,
            final_completion=final_completion,
            duration_minutes=duration_minutes
        )
    
    def error_occurred(self, session_id: str, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Log errors with context"""
        self.logger.error(
            "error_occurred",
            session_id=session_id,
            error_type=error_type,
            error_message=error_message,
            context=context or {}
        )
