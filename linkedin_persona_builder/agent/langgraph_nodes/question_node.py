"""
LinkedIn Persona Builder - Question Node

Generate and present adaptive questions based on current criterion.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.conversation_manager import conversation_manager
from agent.components.state_manager import state_manager
from memory.context_manager import context_manager
from data.redis.redis_utils import redis_manager
from knowledge.framework_loader import framework_loader

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def question_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate and present adaptive questions based on conversation context
    
    Input: Session state, current criterion, context
    Output: Adaptive question, updated history
    Routing: → EvaluationNode
    """
    try:
        session_id = state["session_id"]
        current_section = state["current_section"]
        current_criterion = state.get("current_criterion", "")
        
        logger.info(f"Entering question node - session: {session_id}, "
                   f"section: {current_section}, criterion: {current_criterion}")
        
        # Get next criterion if current one is complete or empty
        if not current_criterion:
            current_criterion = await _get_next_criterion(session_id, current_section)
            if not current_criterion:
                # No more criteria in this section, transition
                state["next_node"] = "transition"
                return state
            
            # Update state with new criterion
            state["current_criterion"] = current_criterion
        
        # Check if current criterion is already complete (from cross-section updates)
        criterion_complete = await _check_criterion_completion(session_id, current_section, current_criterion)
        if criterion_complete:
            # Move to next criterion
            next_criterion = await _get_next_criterion(session_id, current_section, skip_current=True)
            if next_criterion:
                state["current_criterion"] = next_criterion
                current_criterion = next_criterion
            else:
                # Section complete, transition
                state["next_node"] = "transition"
                return state
        
        # Get criterion definition from framework
        criterion_data = framework_loader.get_criterion(current_section, current_criterion)
        if not criterion_data:
            logger.error(f"Criterion not found: {current_criterion} in section {current_section}")
            state["error_message"] = "Question generation failed"
            state["next_node"] = "transition"
            return state
        
        # Build conversation context
        context = await context_manager.build_question_context(session_id)
        
        # Generate adaptive question
        question = await conversation_manager.generate_question(
            criterion=criterion_data,
            context=context
        )
        
        # Update state
        state["agent_response"] = question
        state["next_node"] = "evaluation"  # Always go to evaluation after question
        state["requires_user_input"] = True
        state["follow_up_attempts"] = 0  # Reset for new question
        
        # Add conversation turn
        await redis_manager.add_conversation_turn(session_id, {
            "agent_response": question,
            "section_number": current_section,
            "criterion_name": current_criterion,
            "node_type": "question",
            "timestamp": datetime.now().isoformat(),
            "token_count": len(question) // 4
        })
        
        logger.info(f"Question generated for criterion: {current_criterion}")
        
        return state
        
    except Exception as e:
        logger.error(f"Question node failed: {e}", extra={"session_id": state.get("session_id")})
        state["error_message"] = str(e)
        state["agent_response"] = "Let me ask you about your professional expertise. What's an area where you have deep knowledge?"
        state["next_node"] = "evaluation"
        state["requires_user_input"] = True
        return state


async def _get_next_criterion(session_id: str, section_number: int, skip_current: bool = False) -> str:
    """Get next incomplete criterion in section"""
    try:
        # Get list of incomplete criteria from state manager
        incomplete_criteria = await state_manager.get_incomplete_criteria(session_id, section_number)
        
        if not incomplete_criteria:
            return None
        
        if skip_current and len(incomplete_criteria) > 1:
            # Skip the first one (current) and get the next
            return incomplete_criteria[1]
        
        return incomplete_criteria[0]
        
    except Exception as e:
        logger.error(f"Next criterion lookup failed: {e}")
        return None


async def _check_criterion_completion(session_id: str, section_number: int, criterion_name: str) -> bool:
    """Check if criterion is already complete"""
    try:
        persona_data = await state_manager.get_persona_data(session_id)
        if not persona_data:
            return False
        
        # Find the section
        for section in persona_data.get("sections", []):
            if section.get("section_number") == section_number:
                criteria = section.get("criteria", {})
                criterion_data = criteria.get(criterion_name, {})
                return criterion_data.get("complete", False)
        
        return False
        
    except Exception as e:
        logger.error(f"Criterion completion check failed: {e}")
        return False
