"""
LinkedIn Persona Builder - Follow-up Node

Generate clarifying questions for poor responses.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.conversation_manager import conversation_manager
from memory.context_manager import context_manager
from data.redis.redis_utils import redis_manager
from knowledge.framework_loader import framework_loader

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def followup_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate clarifying questions for poor responses
    
    Input: Poor quality response, attempt count, context
    Output: Follow-up question with examples
    Routing: → EvaluationNode
    """
    try:
        session_id = state["session_id"]
        current_section = state["current_section"]
        current_criterion = state["current_criterion"]
        follow_up_attempts = state.get("follow_up_attempts", 1)
        
        logger.info(f"Entering follow-up node - session: {session_id}, "
                   f"criterion: {current_criterion}, attempt: {follow_up_attempts}")
        
        # Get the user's original response (last user input)
        original_response = state.get("user_input", "")
        
        # Get criterion definition
        criterion_data = framework_loader.get_criterion(current_section, current_criterion)
        if not criterion_data:
            logger.error(f"Criterion not found for follow-up: {current_criterion}")
            state["agent_response"] = "Let me ask you a different question."
            state["next_node"] = "question"
            return state
        
        # Generate follow-up question
        follow_up_question = await conversation_manager.generate_follow_up(
            session_id=session_id,
            criterion=criterion_data,
            original_response=original_response,
            attempt_number=follow_up_attempts
        )
        
        # Update state
        state["agent_response"] = follow_up_question
        state["next_node"] = "evaluation"  # Go back to evaluation for user's new response
        state["requires_user_input"] = True
        
        # Add follow-up turn to conversation history
        await redis_manager.add_conversation_turn(session_id, {
            "agent_response": follow_up_question,
            "section_number": current_section,
            "criterion_name": current_criterion,
            "node_type": "follow_up",
            "timestamp": datetime.now().isoformat(),
            "token_count": len(follow_up_question) // 4
        })
        
        logger.info(f"Follow-up question generated for criterion: {current_criterion}, attempt: {follow_up_attempts}")
        
        return state
        
    except Exception as e:
        logger.error(f"Follow-up node failed: {e}", extra={"session_id": state.get("session_id")})
        
        # Fallback follow-up
        state["agent_response"] = "Could you be more specific about that? Any additional details would be helpful."
        state["next_node"] = "evaluation"
        state["requires_user_input"] = True
        return state
