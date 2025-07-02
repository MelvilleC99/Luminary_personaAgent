"""
Enhanced logging system for debugging and error tracking.
"""

import logging
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class PersonaLogger:
    """Enhanced logger for the persona agent system."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup comprehensive logging."""
        
        # Clear existing handlers
        self.logger.handlers.clear()
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler (for development)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        
        # File handler (for all logs)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"persona_agent_{today}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        # Error handler (for errors only)
        error_file = LOGS_DIR / f"errors_{today}.log"
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
    
    def log_assessment(self, session_id: str, question_id: int, 
                      answer: str, assessment: Dict[str, Any]):
        """Log assessment details for debugging."""
        log_data = {
            "session_id": session_id,
            "question_id": question_id,
            "answer_length": len(answer),
            "answer_preview": answer[:50] + "..." if len(answer) > 50 else answer,
            "score": assessment.get("score"),
            "category": assessment.get("category"),
            "needs_follow_up": assessment.get("needs_follow_up")
        }
        self.logger.info(f"ASSESSMENT: {json.dumps(log_data)}")


# Global logger instance
persona_logger = PersonaLogger("persona_agent")
