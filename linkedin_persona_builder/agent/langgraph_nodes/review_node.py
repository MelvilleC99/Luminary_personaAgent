"""
LinkedIn Persona Builder - Review Node

Final review and modification handling.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.persona_builder import persona_builder
from agent.components.validation_manager import validation_manager
from memory.session_manager import session_manager
from data.redis.redis_utils import redis_manager

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final review and modification handling
    
    Input: Complete persona data, user feedback
    Output: Persona summary, modification handling
    Routing: → CompletionNode | → Self (if modifications)
    """
    try:
        session_id = state["session_id"]
        user_input = state.get("user_input", "")
        user_name = state.get("user_name", "User")
        
        logger.info(f"Entering review node for session: {session_id}")
        
        # Check if this is initial review or user feedback
        if not user_input or user_input == "start_review":
            # Initial review - present persona summary
            await _handle_initial_review(state, user_name)
        else:
            # User provided feedback - handle modification or approval
            await _handle_review_feedback(state, user_input)
        
        return state
        
    except Exception as e:
        logger.error(f"Review node failed: {e}", extra={"session_id": state.get("session_id")})
        state["error_message"] = str(e)
        state["agent_response"] = "Let me prepare your LinkedIn persona summary for review."
        state["next_node"] = "review"
        state["requires_user_input"] = True
        return state


async def _handle_initial_review(state: Dict[str, Any], user_name: str):
    """Handle initial persona review presentation"""
    try:
        session_id = state["session_id"]
        
        # Compile complete persona
        compiled_persona = await persona_builder.compile_persona(session_id)
        
        if "error" in compiled_persona:
            state["agent_response"] = "I'm having trouble compiling your persona. Let me finalize what we have."
            state["next_node"] = "completion"
            return
        
        # Generate persona summary for review
        persona_summary = compiled_persona.get("persona_summary", {})
        overall_summary = persona_summary.get("overall_summary", "Your professional persona")
        key_insights = persona_summary.get("key_insights", [])
        
        # Validate completeness
        validation_report = await persona_builder.validate_completeness(session_id)
        
        # Build review message
        review_message_parts = [
            f"Perfect, {user_name}! Here's your LinkedIn persona summary:",
            "",
            f"**Overview:** {overall_summary}",
            ""
        ]
        
        if key_insights:
            review_message_parts.append("**Key Insights:**")
            for insight in key_insights[:3]:  # Show top 3 insights
                review_message_parts.append(f"• {insight}")
            review_message_parts.append("")
        
        # Add validation summary
        validation_summary = _format_validation_report(validation_report)
        if validation_summary:
            review_message_parts.append(validation_summary)
        
        review_message_parts.extend([
            "How does this summary capture your professional identity? Feel free to:",
            "• Say \"looks perfect\" if you're happy with it",
            "• Request changes like \"change my target audience to include...\"",
            "• Ask for clarifications on any section",
            "",
            "What would you like to adjust?"
        ])
        
        review_message = "\n".join(review_message_parts)
        
        state["agent_response"] = review_message
        state["next_node"] = "review"  # Stay in review for feedback
        state["requires_user_input"] = True
        
        # Add review turn to conversation history
        await redis_manager.add_conversation_turn(session_id, {
            "agent_response": review_message,
            "section_number": 0,  # Review phase
            "criterion_name": "persona_review",
            "node_type": "review",
            "timestamp": datetime.now().isoformat(),
            "token_count": len(review_message) // 4
        })
        
        logger.info(f"Initial review presented for session: {session_id}")
        
    except Exception as e:
        logger.error(f"Initial review failed: {e}")
        raise


async def _handle_review_feedback(state: Dict[str, Any], user_feedback: str):
    """Handle user feedback on persona review"""
    try:
        session_id = state["session_id"]
        user_feedback_lower = user_feedback.lower().strip()
        
        # Check for approval signals
        approval_signals = [
            "looks perfect", "looks good", "perfect", "great", "excellent",
            "that's right", "correct", "approved", "ready", "done"
        ]
        
        if any(signal in user_feedback_lower for signal in approval_signals):
            # User approved the persona
            state["agent_response"] = "Fantastic! Your LinkedIn persona is complete and ready to use. I'll finalize everything for you."
            state["next_node"] = "completion"
            state["requires_user_input"] = False
            
            logger.info(f"Persona approved by user for session: {session_id}")
            
        else:
            # User wants modifications
            await _process_modification_request(state, user_feedback)
        
        # Add feedback turn to conversation history
        await redis_manager.add_conversation_turn(session_id, {
            "user_input": user_feedback,
            "agent_response": state["agent_response"],
            "section_number": 0,
            "criterion_name": "review_feedback",
            "node_type": "review",
            "timestamp": datetime.now().isoformat(),
            "token_count": (len(user_feedback) + len(state["agent_response"])) // 4
        })
        
    except Exception as e:
        logger.error(f"Review feedback handling failed: {e}")
        # Fallback to completion
        state["agent_response"] = "Thank you for the feedback. Let me finalize your persona."
        state["next_node"] = "completion"


async def _process_modification_request(state: Dict[str, Any], modification_request: str):
    """Process user modification request"""
    try:
        session_id = state["session_id"]
        
        # Analyze modification request using persona builder
        modification_result = await persona_builder.handle_modification(
            session_id, modification_request
        )
        
        if modification_result.get("success", False):
            # Modification was successful
            updated_criterion = modification_result.get("updated_criterion", "information")
            
            state["agent_response"] = f"I've updated your {updated_criterion.replace('_', ' ')}. Let me show you the revised persona summary."
            # Trigger new review by clearing user_input
            state["user_input"] = "start_review"
            state["next_node"] = "review"
            state["requires_user_input"] = False  # Will auto-trigger review
            
        else:
            # Couldn't process modification
            error_message = modification_result.get("error", "")
            if "conflicts" in modification_result:
                state["agent_response"] = f"I understand you'd like to make changes, but that might create some inconsistencies. Could you be more specific about what you'd like to modify, or shall we proceed with the current persona?"
            else:
                state["agent_response"] = "I'm not sure exactly what you'd like to change. Could you be more specific, or shall we proceed with the current persona?"
            
            state["next_node"] = "review"
            state["requires_user_input"] = True
        
    except Exception as e:
        logger.error(f"Modification processing failed: {e}")
        state["agent_response"] = "I had trouble processing that change. Let's finalize your persona as it is."
        state["next_node"] = "completion"
        state["requires_user_input"] = False


def _format_validation_report(validation_report: Dict[str, Any]) -> str:
    """Format validation report for user display"""
    try:
        if not validation_report:
            return "**Completion: 100%** - Your persona is well-developed and ready for LinkedIn!"
        
        completion_score = validation_report.get("completion_score", 0.0)
        is_valid = validation_report.get("valid", True)
        
        if not is_valid:
            missing_info = validation_report.get("missing_info", [])
            recommendations = validation_report.get("recommendations", [])
            
            report_parts = [f"**Completion: {completion_score:.0%}**"]
            
            if missing_info:
                report_parts.append("**Areas that could be strengthened:**")
                for item in missing_info[:2]:  # Limit to top 2
                    report_parts.append(f"• {item}")
            
            if recommendations:
                report_parts.append("**Recommendations:**")
                for rec in recommendations[:2]:  # Limit to top 2
                    report_parts.append(f"• {rec}")
            
            return "\n".join(report_parts)
        
        return f"**Completion: {completion_score:.0%}** - Your persona is well-developed and ready for LinkedIn!"
        
    except Exception as e:
        logger.error(f"Validation report formatting failed: {e}")
        return "Your persona is ready for use!"
