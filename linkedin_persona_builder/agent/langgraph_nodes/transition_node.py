"""
LinkedIn Persona Builder - Transition Node

Manage section-to-section transitions.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.conversation_manager import conversation_manager
from agent.components.state_manager import state_manager
from data.redis.redis_utils import redis_manager
from knowledge.framework_loader import framework_loader

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def transition_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manage transitions between conversation sections
    
    Input: Completed section data, next section info
    Output: Transition message, state updates
    Routing: → QuestionNode (next section) | → ReviewNode (if final section)
    """
    try:
        session_id = state["session_id"]
        current_section = state["current_section"]
        user_name = state.get("user_name", "there")
        
        logger.info(f"Entering transition node - session: {session_id}, "
                   f"from section: {current_section}")
        
        # Generate section summary
        section_summary = await _generate_section_summary(session_id, current_section)
        
        # Determine next section
        framework = framework_loader.load_current()
        next_section = current_section + 1
        
        if next_section > framework.metadata.total_sections:
            # All sections complete - move to review
            state["agent_response"] = f"Excellent work, {user_name}! You've completed all {framework.metadata.total_sections} sections. Let me prepare your persona summary for review."
            state["next_node"] = "review"
            state["requires_user_input"] = False
            
        else:
            # Generate transition message to next section
            transition_message = await conversation_manager.generate_section_transition(
                completed_section=current_section,
                section_summary=section_summary,
                next_section=next_section,
                user_name=user_name
            )
            
            # Update state for next section
            state["agent_response"] = transition_message
            state["current_section"] = next_section
            state["current_criterion"] = await _get_first_criterion_for_section(next_section)
            state["next_node"] = "question"
            state["requires_user_input"] = True
            state["follow_up_attempts"] = 0  # Reset for new section
            
            # Update session state
            await state_manager.update_session_state(
                session_id, 
                current_section=next_section, 
                current_criterion=state["current_criterion"]
            )
        
        # Add transition turn to conversation history
        await redis_manager.add_conversation_turn(session_id, {
            "agent_response": state["agent_response"],
            "section_number": current_section,
            "criterion_name": f"section_{current_section}_transition",
            "node_type": "transition",
            "timestamp": datetime.now().isoformat(),
            "token_count": len(state["agent_response"]) // 4
        })
        
        logger.info(f"Section transition completed - from: {current_section}, "
                   f"to: {next_section if next_section <= framework.metadata.total_sections else 'review'}")
        
        return state
        
    except Exception as e:
        logger.error(f"Transition node failed: {e}", extra={"session_id": state.get("session_id")})
        
        # Fallback transition
        current_section = state.get("current_section", 1)
        state["agent_response"] = "Great progress! Let's continue to the next section."
        state["current_section"] = current_section + 1
        state["next_node"] = "question"
        state["requires_user_input"] = True
        return state


async def _generate_section_summary(session_id: str, section_number: int) -> str:
    """Generate summary of completed section"""
    try:
        persona_data = await state_manager.get_persona_data(session_id)
        if not persona_data:
            return "Section completed"
        
        # Find the section data
        section_data = None
        for section in persona_data.get("sections", []):
            if section.get("section_number") == section_number:
                section_data = section
                break
        
        if not section_data:
            return f"Section {section_number} completed"
        
        # Collect completed responses
        completed_items = []
        for criterion_name, criterion_data in section_data.get("criteria", {}).items():
            if criterion_data.get("complete", False):
                # Summarize response (first 50 chars)
                response = criterion_data.get("response", "")
                summary = response[:50] + "..." if len(response) > 50 else response
                formatted_name = criterion_name.replace('_', ' ').title()
                completed_items.append(f"{formatted_name}: {summary}")
        
        if completed_items:
            section_name = section_data.get("section_name", f"Section {section_number}")
            return f"In {section_name}, we captured: " + "; ".join(completed_items[:3])
        else:
            return f"Completed {section_data.get('section_name', f'Section {section_number}')}"
            
    except Exception as e:
        logger.error(f"Section summary generation failed: {e}")
        return "Section completed successfully"


async def _get_first_criterion_for_section(section_number: int) -> str:
    """Get the first criterion for a given section"""
    try:
        section_data = framework_loader.get_section(section_number)
        if section_data and section_data.criteria:
            # Return first criterion name
            return list(section_data.criteria.keys())[0]
        
        # Fallback based on known structure from requirements
        section_first_criteria = {
            1: "broad_domain_expertise",
            2: "professional_communication_style", 
            3: "unique_value_proposition"
        }
        
        return section_first_criteria.get(section_number, "broad_domain_expertise")
        
    except Exception as e:
        logger.error(f"First criterion lookup failed for section {section_number}: {e}")
        return "broad_domain_expertise"
