"""
Main entry point for the Luminary Persona Agent system.
"""

import asyncio
import logging
from orchestrator.coordinator import PersonaCoordinator
from orchestrator.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def initialize_system():
    """Initialize the persona agent system."""
    try:
        # Validate configuration
        settings.validate_required_keys()
        logger.info("Configuration validated successfully")
        
        # Initialize coordinator
        coordinator = PersonaCoordinator()
        
        # TODO: Initialize and register agents
        # from agents.question_agent import QuestionAgent
        # question_agent = QuestionAgent(...)
        # coordinator.register_agent("question_agent", question_agent)
        
        logger.info("System initialized successfully")
        return coordinator
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        raise


async def main():
    """Main function for running the system."""
    coordinator = await initialize_system()
    
    # Perform health check
    health = await coordinator.health_check()
    logger.info(f"Health check: {health}")
    
    # Example usage
    try:
        # Start a test session
        result = await coordinator.start_session(
            user_id="test_user",
            website_url="https://example.com"
        )
        logger.info(f"Test session result: {result}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")


if __name__ == "__main__":
    asyncio.run(main())
