"""
Base agent interface for all Luminary Persona agents.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agent implementations.
    
    This interface ensures consistency across all agents and provides
    a standardized contract for the orchestration layer.
    """
    
    def __init__(self, 
                 llm_tool=None,
                 session_manager=None,
                 context_manager=None,
                 database=None,
                 **kwargs):
        """
        Initialize the base agent.
        
        Args:
            llm_tool: LLM tool for AI interactions
            session_manager: Session management for persistence
            context_manager: Context manager for conversation history
            database: Database client for persistence
            **kwargs: Additional agent-specific parameters
        """
        self.llm_tool = llm_tool
        self.session_manager = session_manager
        self.context_manager = context_manager
        self.database = database
        self.agent_name = self.__class__.__name__
        
        # Agent-specific configuration
        self.config = kwargs
        
        logger.info(f"Initialized {self.agent_name}")
    
    @abstractmethod
    async def process(self, session_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the input data and return the result.
        
        Args:
            session_id: The session identifier
            input_data: Input data for processing
            
        Returns:
            Dict containing the processing result
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Return a list of capabilities this agent provides.
        
        Returns:
            List of capability strings
        """
        pass
    
    async def log_interaction(self, session_id: str, action: str, 
                            input_data: Dict[str, Any], 
                            result: Dict[str, Any],
                            duration: Optional[float] = None):
        """
        Log agent interaction for monitoring and debugging.
        
        Args:
            session_id: The session identifier
            action: The action performed
            input_data: Input data
            result: Result data
            duration: Processing duration in seconds
        """
        log_entry = {
            "agent_name": self.agent_name,
            "session_id": session_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": duration,
            "input_size": len(str(input_data)),
            "result_size": len(str(result)),
            "success": "error" not in result
        }
        
        logger.info(f"{self.agent_name} completed {action}", extra=log_entry)
        
        # Store in database if available
        if self.database:
            try:
                await self.database.log_agent_interaction(log_entry)
            except Exception as e:
                logger.warning(f"Failed to log interaction to database: {e}")
    
    def validate_input(self, input_data: Dict[str, Any], required_fields: List[str]) -> bool:
        """
        Validate that required fields are present in input data.
        
        Args:
            input_data: Data to validate
            required_fields: List of required field names
            
        Returns:
            True if valid, raises ValueError if not
        """
        missing_fields = [field for field in required_fields 
                         if field not in input_data or input_data[field] is None]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        return True
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle errors in a standardized way.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            
        Returns:
            Standardized error response
        """
        error_response = {
            "error": str(error),
            "error_type": type(error).__name__,
            "agent": self.agent_name,
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.error(f"{self.agent_name} error: {error}", extra=error_response)
        
        return error_response
