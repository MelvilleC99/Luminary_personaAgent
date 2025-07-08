"""
Workflow router for LangGraph Persona Agent.
Handles conditional routing between different workflow nodes.
"""

import logging
from typing import Literal

from .models import PersonaConversationState

logger = logging.getLogger(__name__)


class WorkflowRouter:
    """Handles routing logic for the LangGraph workflow."""
    
    @staticmethod
    def route_after_analyze(state: PersonaConversationState) -> Literal["answer_question", "extract_and_respond"]:
        """Route after analyzing user input."""
        user_intent = state.get("user_intent", "answering")
        
        if user_intent in ["questioning", "clarifying"]:
            logger.info(f"Routing to answer_question (intent: {user_intent})")
            return "answer_question"
        else:
            logger.info(f"Routing to extract_and_respond (intent: {user_intent})")
            return "extract_and_respond"
    
    @staticmethod
    def route_after_completion_check(state: PersonaConversationState) -> Literal["extract_and_respond", "wrap_up", "__end__"]:
        """Route after checking completion status."""
        conversation_stage = state.get("conversation_stage", "gathering")
        completion_percentage = state.get("completion_percentage", 0)
        loop_count = state.get("loop_count", 0)
        
        # End after response has been generated (loop_count starts at 1 after first processing)
        if loop_count >= 1:
            logger.debug(f"Ending conversation after response generation: {loop_count} loops")
            return "__end__"
        
        if completion_percentage >= 80 and conversation_stage == "completion":
            logger.debug("Routing to wrap_up")
            return "wrap_up"
        else:
            logger.debug("Routing to end - workflow complete")
            return "__end__"
    
    @staticmethod
    def should_continue(state: PersonaConversationState) -> bool:
        """Determine if conversation should continue."""
        completion_percentage = state.get("completion_percentage", 0)
        conversation_stage = state.get("conversation_stage", "gathering")
        
        # Continue if not complete or still in active stages
        return completion_percentage < 80 or conversation_stage in ["gathering", "follow_up"]
