"""
LinkedIn Persona Builder - Evaluation Node

Analyze user responses and determine next actions.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.conversation_manager import conversation_manager
from agent.components.state_manager import state_manager
from agent.components.validation_manager import validation_manager
from memory.context_manager import context_manager
from data.redis.redis_utils import redis_manager
from knowledge.framework_loader import framework_loader
from orchestrator.config import settings

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def evaluation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze user responses and determine next actions
    
    Input: User response, current criterion, context
    Output: Evaluation results, persona updates, routing decision
    Routing: → FollowUpNode | → QuestionNode | → TransitionNode
    """
    try:
        session_id = state["session_id"]
        user_input = state["user_input"]
        current_section = state["current_section"]
        current_criterion = state["current_criterion"]
        follow_up_attempts = state.get("follow_up_attempts", 0)
        
        logger.info(f"Entering evaluation node - session: {session_id}, "
                   f"criterion: {current_criterion}, attempts: {follow_up_attempts}")
        
        # Handle special user inputs
        special_handling = await _handle_special_inputs(state)
        if special_handling:
            return state
        
        # Get criterion definition
        criterion_data = framework_loader.get_criterion(current_section, current_criterion)
        if not criterion_data:
            logger.error(f"Criterion not found: {current_criterion}")
            state["next_node"] = "question"
            return state
        
        # Evaluate response quality
        evaluation = await conversation_manager.evaluate_response(user_input, criterion_data)
        
        # Check for cross-section matches
        cross_matches = await conversation_manager.check_cross_section_matches(
            user_input, current_section
        )
        
        # Get existing persona data for validation
        persona_data = await state_manager.get_persona_data(session_id)
        
        # Validate consistency
        validation_result = None
        if persona_data and evaluation.quality_score >= 6:
            validation_result = await validation_manager.validate_consistency(
                evaluation, persona_data
            )
        
        # Handle validation conflicts
        if validation_result and not validation_result.valid:
            await _handle_validation_conflicts(state, validation_result)
            return state
        
        # Update persona data with evaluation results
        update_success = await state_manager.update_persona_criterion(
            session_id=session_id,
            section_number=current_section,
            criterion_name=current_criterion,
            evaluation=evaluation,
            user_response=user_input
        )
        
        # Update cross-section matches
        if cross_matches:
            cross_updates = await state_manager.update_cross_section_matches(session_id, cross_matches)
            logger.info(f"Updated {len(cross_matches)} cross-section matches")
        
        # Determine next action based on evaluation
        await _determine_routing(state, evaluation, follow_up_attempts)
        
        # Add conversation turn
        await redis_manager.add_conversation_turn(session_id, {
            "user_input": user_input,
            "agent_response": state.get("agent_response", ""),
            "section_number": current_section,
            "criterion_name": current_criterion,
            "node_type": "evaluation",
            "quality_score": evaluation.quality_score,
            "confidence_score": evaluation.confidence,
            "timestamp": datetime.now().isoformat(),
            "token_count": (len(user_input) + len(state.get("agent_response", ""))) // 4
        })
        
        logger.info(f"Response evaluated - quality: {evaluation.quality_score}, next: {state['next_node']}")
        
        return state
        
    except Exception as e:
        logger.error(f"Evaluation node failed: {e}", extra={"session_id": state.get("session_id")})
        state["error_message"] = str(e)
        state["agent_response"] = "Thank you for that response. Let me ask you another question."
        state["next_node"] = "question"
        state["requires_user_input"] = True
        return state


async def _handle_special_inputs(state: Dict[str, Any]) -> bool:
    """Handle special user inputs like clarification requests"""
    try:
        user_input = state["user_input"].lower().strip()
        session_id = state["session_id"]
        current_section = state["current_section"]
        current_criterion = state["current_criterion"]
        
        # Check for clarification requests
        clarification_signals = [
            "can you explain", "what do you mean", "i don't understand",
            "can you clarify", "what's that", "explain", "help", "example"
        ]
        
        if any(signal in user_input for signal in clarification_signals):
            # User wants clarification
            criterion_data = framework_loader.get_criterion(current_section, current_criterion)
            if criterion_data:
                # Get context for industry-specific examples
                context = await context_manager.build_question_context(session_id)
                industry = context.industry if context else "unknown"
                
                clarification = await conversation_manager.handle_clarification_request(
                    criterion_data, industry
                )
                
                state["agent_response"] = clarification
                state["next_node"] = "evaluation"  # Stay in evaluation, wait for real answer
                state["requires_user_input"] = True
                
                # Add clarification turn
                await redis_manager.add_conversation_turn(session_id, {
                    "user_input": state["user_input"],
                    "agent_response": clarification,
                    "section_number": current_section,
                    "criterion_name": current_criterion + "_clarification",
                    "node_type": "evaluation",
                    "timestamp": datetime.now().isoformat(),
                    "token_count": (len(state["user_input"]) + len(clarification)) // 4
                })
                
                return True
        
        # Check for modification requests
        modification_signals = [
            "change my", "update my", "modify", "actually", "correction", "i meant"
        ]
        
        if any(signal in user_input for signal in modification_signals):
            # User wants to modify previous answer
            state["agent_response"] = "I'll note that you'd like to make a change. For now, let's continue and we can review all your answers at the end."
            state["next_node"] = "question"
            state["requires_user_input"] = True
            return True
        
        return False  # No special handling needed
        
    except Exception as e:
        logger.error(f"Special input handling failed: {e}")
        return False


async def _handle_validation_conflicts(state: Dict[str, Any], validation_result):
    """Handle validation conflicts"""
    try:
        session_id = state["session_id"]
        user_name = state.get("user_name", "there")
        
        # Generate conflict resolution prompt
        conflict_prompt = f"""
{user_name}, I notice something that might need clarification. You mentioned something that seems different from what you said earlier. 

{validation_result.conflicts[0] if validation_result.conflicts else "There seems to be an inconsistency."}

Could you help me understand which information is correct, or how both can be true?
"""
        
        state["agent_response"] = conflict_prompt
        state["next_node"] = "evaluation"  # Stay in evaluation for clarification
        state["requires_user_input"] = True
        
        # Add conflict turn
        await redis_manager.add_conversation_turn(session_id, {
            "user_input": state["user_input"],
            "agent_response": conflict_prompt,
            "section_number": state["current_section"],
            "criterion_name": state["current_criterion"] + "_conflict",
            "node_type": "evaluation",
            "timestamp": datetime.now().isoformat(),
            "token_count": (len(state["user_input"]) + len(conflict_prompt)) // 4
        })
        
        logger.warning(f"Validation conflict handled for session: {session_id}")
        
    except Exception as e:
        logger.error(f"Conflict handling failed: {e}")


async def _determine_routing(state: Dict[str, Any], evaluation, follow_up_attempts: int):
    """Determine next node based on evaluation results"""
    try:
        session_id = state["session_id"]
        current_section = state["current_section"]
        quality_score = evaluation.quality_score
        confidence = evaluation.confidence
        max_follow_up_attempts = getattr(settings, 'max_follow_up_attempts', 2)
        
        # Decision logic based on spec
        if quality_score >= 8:
            # Excellent response - move to next question
            state["agent_response"] = "Perfect! That's very helpful."
            state["next_node"] = "question"
            state["follow_up_attempts"] = 0  # Reset for next criterion
            
        elif quality_score >= 6:
            # Good response - accept and continue
            state["agent_response"] = "Great, thanks for that detail."
            state["next_node"] = "question"
            state["follow_up_attempts"] = 0  # Reset for next criterion
            
        elif quality_score < 6 and follow_up_attempts < max_follow_up_attempts:
            # Poor response but can try follow-up
            state["next_node"] = "follow_up"
            state["follow_up_attempts"] = follow_up_attempts + 1
            # agent_response will be set by follow_up node
            
        else:
            # Poor response and max attempts reached - park and move on
            await state_manager.park_criterion(
                session_id, current_section, state["current_criterion"], "max_attempts"
            )
            
            state["agent_response"] = "Thanks for that. Let's move on to the next topic."
            state["next_node"] = "question"
            state["follow_up_attempts"] = 0  # Reset for next criterion
        
        # Check if section should transition
        section_complete = await state_manager.is_section_complete(session_id, current_section)
        if section_complete and state["next_node"] == "question":
            state["next_node"] = "transition"
        
        # Check if all sections complete (3 sections total)
        if current_section >= 3:
            overall_progress = await state_manager.get_overall_progress(session_id)
            completion_threshold = getattr(settings, 'section_completion_threshold', 0.9)
            if overall_progress.get("overall_completion", 0.0) >= completion_threshold:
                state["next_node"] = "review"
        
        state["requires_user_input"] = True
        
    except Exception as e:
        logger.error(f"Routing determination failed: {e}")
        # Default fallback
        state["next_node"] = "question"
        state["requires_user_input"] = True
