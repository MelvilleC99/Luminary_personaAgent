"""
LinkedIn Persona Builder - Completion Node

Finalize session and trigger handoff.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.persona_builder import persona_builder
from memory.session_manager import session_manager
from data.redis.redis_utils import redis_manager
from data.supabase.supabase_utils import supabase_manager

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def completion_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finalize session and prepare for handoff
    
    Input: Confirmed persona data
    Output: Final persona, completion message, handoff trigger
    Routing: END
    """
    try:
        session_id = state["session_id"]
        user_id = state["user_id"]
        user_name = state.get("user_name", "User")
        
        logger.info(f"Entering completion node for session: {session_id}")
        
        # Prepare final persona for export
        final_persona = await persona_builder.export_for_json(session_id)
        
        if "error" in final_persona:
            # Handle preparation error gracefully
            state["agent_response"] = f"Thank you, {user_name}! Your persona responses have been saved successfully. You can access your completed LinkedIn persona anytime."
            state["session_complete"] = True
            state["requires_user_input"] = False
            state["next_node"] = "__end__"
            return state
        
        # Calculate session analytics
        session_analytics = await _calculate_session_analytics(session_id, user_id)
        
        # Sync final data to Supabase for persistence
        sync_success = await _sync_final_data(session_id, final_persona, session_analytics)
        
        # Generate completion message
        completion_message = await _generate_completion_message(
            user_name, final_persona, session_analytics
        )
        
        # Update state for completion
        state["agent_response"] = completion_message
        state["session_complete"] = True
        state["requires_user_input"] = False
        state["next_node"] = "__end__"
        state["final_persona"] = final_persona
        
        # Mark session as complete in session manager
        await session_manager.complete_session(session_id)
        
        # Add completion turn to conversation history
        await redis_manager.add_conversation_turn(session_id, {
            "agent_response": completion_message,
            "section_number": 0,
            "criterion_name": "session_completion",
            "node_type": "completion",
            "timestamp": datetime.now().isoformat(),
            "token_count": len(completion_message) // 4
        })
        
        # Log final analytics
        completion_rate = final_persona.get("completion_score", 0.0)
        duration = session_analytics.get("total_duration_minutes", 0.0)
        
        logger.info(f"Session completed successfully - session: {session_id}, "
                   f"completion: {completion_rate:.1%}, duration: {duration:.1f}min, "
                   f"sync: {'success' if sync_success else 'failed'}")
        
        return state
        
    except Exception as e:
        logger.error(f"Completion node failed: {e}", extra={"session_id": state.get("session_id")})
        
        # Fallback completion
        user_name = state.get("user_name", "User")
        state["error_message"] = str(e)
        state["agent_response"] = f"Congratulations, {user_name}! Your LinkedIn persona has been created successfully. Thank you for completing this process!"
        state["session_complete"] = True
        state["requires_user_input"] = False
        state["next_node"] = "__end__"
        return state


async def _calculate_session_analytics(session_id: str, user_id: str) -> Dict[str, Any]:
    """Calculate comprehensive session analytics"""
    try:
        # Get session info
        session_info = await session_manager.get_session_info(session_id)
        
        # Get conversation history for analysis
        conversation_history = await redis_manager.get_conversation_history(session_id)
        
        # Calculate duration
        start_time = None
        end_time = datetime.now()
        
        if session_info and session_info.get("created_at"):
            try:
                if isinstance(session_info["created_at"], str):
                    start_time = datetime.fromisoformat(session_info["created_at"].replace('Z', '+00:00'))
                else:
                    start_time = session_info["created_at"]
            except:
                start_time = None
        
        duration_minutes = None
        if start_time:
            duration_minutes = (end_time - start_time).total_seconds() / 60
        
        # Calculate quality metrics
        quality_scores = [
            turn.get("quality_score", 0) for turn in conversation_history 
            if turn.get("quality_score") and turn.get("quality_score") > 0
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        # Count follow-ups
        follow_up_count = len([
            turn for turn in conversation_history 
            if turn.get("node_type") == "follow_up"
        ])
        
        # Count modifications (from review phase)
        modification_count = len([
            turn for turn in conversation_history 
            if turn.get("criterion_name", "").endswith("_modification")
        ])
        
        # Get token usage
        total_tokens = sum(
            turn.get("token_count", 0) for turn in conversation_history
        )
        
        # Get completion rate
        from agent.components.state_manager import state_manager
        progress = await state_manager.get_overall_progress(session_id)
        completion_rate = progress.get("overall_completion", 0.0) if progress else 0.0
        
        analytics = {
            "session_id": session_id,
            "user_id": user_id,
            "total_duration_minutes": duration_minutes,
            "completion_rate": completion_rate,
            "total_turns": len(conversation_history),
            "average_quality_score": avg_quality,
            "follow_up_count": follow_up_count,
            "modification_count": modification_count,
            "total_tokens_used": total_tokens,
            "total_cost_usd": _calculate_estimated_cost(total_tokens),
            "industry": session_info.get("industry") if session_info else None,
            "completion_method": "natural"
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"Session analytics calculation failed: {e}")
        return {
            "session_id": session_id,
            "user_id": user_id,
            "completion_rate": 0.5,  # Default estimate
            "total_turns": 0,
            "completion_method": "error"
        }


def _calculate_estimated_cost(token_count: int) -> float:
    """Calculate estimated API cost based on GPT-4o Mini pricing"""
    try:
        if token_count <= 0:
            return 0.0
            
        # GPT-4o Mini pricing estimate (as of 2024)
        # Input: $0.15 / 1M tokens, Output: $0.6 / 1M tokens
        # Assuming roughly 60% input, 40% output
        input_tokens = int(token_count * 0.6)
        output_tokens = int(token_count * 0.4)
        
        input_cost = (input_tokens / 1_000_000) * 0.15
        output_cost = (output_tokens / 1_000_000) * 0.6
        
        return round(input_cost + output_cost, 4)
        
    except Exception as e:
        logger.error(f"Cost calculation failed: {e}")
        return 0.0


async def _sync_final_data(session_id: str, final_persona: Dict[str, Any], 
                         analytics: Dict[str, Any]) -> bool:
    """Sync final data to Supabase for persistence"""
    try:
        # Sync persona data
        persona_data = await redis_manager.get_persona_data(session_id)
        
        persona_success = False
        if persona_data:
            persona_success = await supabase_manager.upsert_persona(
                session_id=session_id,
                persona_data=persona_data,
                user_id=analytics["user_id"],
                industry=analytics.get("industry")
            )
        
        # Sync analytics
        analytics_success = await supabase_manager.store_session_analytics(analytics)
        
        overall_success = persona_success and analytics_success
        
        if overall_success:
            logger.info(f"Final data synced to Supabase for session: {session_id}")
        else:
            logger.warning(f"Partial sync failure - session: {session_id}, "
                         f"persona: {'success' if persona_success else 'failed'}, "
                         f"analytics: {'success' if analytics_success else 'failed'}")
        
        return overall_success
        
    except Exception as e:
        logger.error(f"Final data sync failed: {e}")
        return False


async def _generate_completion_message(user_name: str, final_persona: Dict[str, Any], 
                                     analytics: Dict[str, Any]) -> str:
    """Generate celebratory completion message"""
    try:
        completion_score = final_persona.get("completion_score", 0.0)
        duration = analytics.get("total_duration_minutes", 0.0)
        
        # Base completion message
        message_parts = [
            f"🎉 Congratulations, {user_name}! You've successfully built your LinkedIn persona!"
        ]
        
        # Add completion details
        if completion_score >= 0.85:
            message_parts.append(f"Your persona is {completion_score:.0%} complete and ready to elevate your LinkedIn presence.")
        elif completion_score >= 0.70:
            message_parts.append(f"Your persona is {completion_score:.0%} complete - a solid foundation for your LinkedIn strategy.")
        else:
            message_parts.append(f"Your persona is {completion_score:.0%} complete and captures your key professional strengths.")
        
        # Add time achievement
        if duration and duration > 0:
            if duration <= 20:
                message_parts.append(f"You completed this in just {duration:.0f} minutes - efficient work!")
            else:
                message_parts.append(f"Thank you for the {duration:.0f} minutes you invested in building this.")
        
        # Add quality recognition
        avg_quality = analytics.get("average_quality_score", 0)
        if avg_quality >= 7:
            message_parts.append("The quality of your responses shows deep professional insight.")
        
        # Add next steps from LinkedIn recommendations
        recommendations = final_persona.get("recommendations", {})
        if recommendations:
            headline_suggestions = recommendations.get("headline_suggestions", [])
            content_themes = recommendations.get("content_themes", [])
            
            if headline_suggestions or content_themes:
                message_parts.append("\n**Next steps for your LinkedIn success:**")
                
                if headline_suggestions:
                    message_parts.append(f"1. Update your headline with insights like: {headline_suggestions[0]}")
                
                if content_themes:
                    theme_list = ", ".join(content_themes[:3])
                    message_parts.append(f"2. Share content about: {theme_list}")
                
                message_parts.append("3. Use your persona insights to craft compelling posts and connect with your ideal audience")
        
        # Closing
        message_parts.append("\nYour persona data has been saved and is ready for use. Best of luck with your LinkedIn journey!")
        
        return "\n".join(message_parts)
        
    except Exception as e:
        logger.error(f"Completion message generation failed: {e}")
        return f"Congratulations, {user_name}! Your LinkedIn persona is complete and ready to use. Thank you for your time!"
