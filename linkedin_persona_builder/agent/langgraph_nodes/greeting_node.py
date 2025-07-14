"""
LinkedIn Persona Builder - Greeting Node

Initial user welcome and process explanation.
"""

from typing import Dict, Any
from datetime import datetime

# Internal imports
from agent.components.conversation_manager import conversation_manager
from memory.session_manager import session_manager
from agent.components.state_manager import state_manager
from data.redis.redis_utils import redis_manager
from knowledge.framework_loader import framework_loader
from orchestrator.config import settings

# Configure logging
import logging
logger = logging.getLogger(__name__)


async def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initial user welcome and process explanation
    
    Input: New session request, user information
    Output: Welcome message, session initialization  
    Routing: → QuestionNode (if ready) | → Clarification (if questions)
    """
    try:
        session_id = state["session_id"]
        user_id = state["user_id"]
        user_input = state.get("user_input", "")
        
        logger.info(f"Entering greeting node for session: {session_id}")
        
        # Check if this is initial greeting or user response to greeting
        if not user_input:
            # Initial greeting - new session
            await _handle_initial_greeting(state)
        else:
            # User responded to greeting - check readiness
            await _handle_greeting_response(state)
        
        return state
        
    except Exception as e:
        logger.error(f"Greeting node failed: {e}", extra={"session_id": state.get("session_id")})
        state["error_message"] = str(e)
        state["agent_response"] = "Welcome! I'm Paul, and I'm here to help you build your LinkedIn persona. Are you ready to get started?"
        state["next_node"] = "greeting"
        state["requires_user_input"] = True
        return state


async def _handle_initial_greeting(state: Dict[str, Any]):
    """Handle initial session greeting"""
    try:
        session_id = state["session_id"]
        user_id = state["user_id"]
        
        # Get or create session
        session_exists = await redis_manager.session_exists(session_id)
        if not session_exists:
            # Initialize new session
            await redis_manager.create_session(session_id, user_id)
        
        # Initialize persona data if needed
        persona_data = await state_manager.initialize_persona_data(session_id)
        
        # Get framework metadata for greeting
        framework = framework_loader.load_current()
        greeting_context = {
            "user_name": state.get("user_name", "there"),
            "total_sections": framework.metadata.total_sections,
            "estimated_time": framework.metadata.estimated_time,
            "section_overview": _get_section_overview(framework)
        }
        
        # Generate personalized greeting
        greeting = await conversation_manager.generate_greeting(greeting_context)
        
        # Update state
        state["agent_response"] = greeting
        state["current_section"] = 1
        state["current_criterion"] = "broad_domain_expertise"
        state["next_node"] = "greeting"  # Wait for user response
        state["requires_user_input"] = True
        
        # Add conversation turn to history
        await redis_manager.add_conversation_turn(session_id, {
            "turn_id": 1,
            "agent_response": greeting,
            "section_number": 1,
            "criterion_name": "greeting",
            "node_type": "greeting",
            "timestamp": datetime.now().isoformat(),
            "token_count": len(greeting) // 4
        })
        
        logger.info(f"Initial greeting generated for session: {session_id}")
        
    except Exception as e:
        logger.error(f"Initial greeting failed: {e}")
        raise


async def _handle_greeting_response(state: Dict[str, Any]):
    """Handle user response to greeting"""
    try:
        session_id = state["session_id"]
        user_input = state["user_input"]
        
        # Detect user readiness using keyword analysis
        readiness = _detect_user_readiness(user_input)
        
        if readiness == "ready":
            # User is ready to start
            state["agent_response"] = "Perfect! Let's dive into building your LinkedIn persona. I'll start with some questions about your expertise."
            state["next_node"] = "question"
            state["requires_user_input"] = True
            
            # Update session to start with first criterion
            await state_manager.update_session_state(
                session_id, 
                current_section=1, 
                current_criterion="broad_domain_expertise"
            )
            
        elif readiness == "questions":
            # User has questions about the process
            framework = framework_loader.load_current()
            sections = []
            for i in range(1, framework.metadata.total_sections + 1):
                section_data = framework_loader.get_section(i)
                if section_data:
                    sections.append(f"{i}. {section_data.name}")
            
            clarification = f"""
Great questions! Here's how this works:

• We'll cover {framework.metadata.total_sections} main sections
• Each section takes about 5-7 minutes  
• Total time: {framework.metadata.estimated_time}
• You can pause and resume anytime
• I'll ask questions and you share your expertise

The sections are:
{chr(10).join(sections)}

Ready to start with section 1?
"""
            state["agent_response"] = clarification
            state["next_node"] = "greeting"  # Stay in greeting for confirmation
            state["requires_user_input"] = True
            
        else:
            # User seems hesitant or unclear
            state["agent_response"] = """
No worries! This process is designed to be easy and conversational. I'll guide you through each step.

Think of this as a friendly chat about your professional expertise. The goal is to help you clearly articulate what makes you unique on LinkedIn.

When you're ready, just let me know and we'll start with some questions about your area of expertise!
"""
            state["next_node"] = "greeting"
            state["requires_user_input"] = True
        
        # Add conversation turn
        await redis_manager.add_conversation_turn(session_id, {
            "user_input": user_input,
            "agent_response": state["agent_response"],
            "section_number": 1,
            "criterion_name": "greeting_response",
            "node_type": "greeting",
            "timestamp": datetime.now().isoformat(),
            "token_count": (len(user_input) + len(state["agent_response"])) // 4
        })
        
        logger.info(f"Greeting response handled for session: {session_id}, readiness: {readiness}")
        
    except Exception as e:
        logger.error(f"Greeting response handling failed: {e}")
        raise


def _detect_user_readiness(user_input: str) -> str:
    """Detect user readiness from their response"""
    try:
        user_lower = user_input.lower().strip()
        
        # Ready signals
        ready_signals = [
            "yes", "ready", "let's go", "start", "sure", "ok", "okay", 
            "let's do it", "i'm ready", "sounds good", "perfect"
        ]
        
        # Question signals
        question_signals = [
            "how long", "what", "when", "why", "explain", "tell me", 
            "can you", "what's", "how does", "?", "more info"
        ]
        
        # Hesitant signals
        hesitant_signals = [
            "not sure", "maybe", "thinking", "later", "busy", "don't know",
            "uncertain", "hesitant", "worried"
        ]
        
        # Check for ready signals
        if any(signal in user_lower for signal in ready_signals):
            return "ready"
        
        # Check for questions
        if any(signal in user_lower for signal in question_signals):
            return "questions"
        
        # Check for hesitation
        if any(signal in user_lower for signal in hesitant_signals):
            return "hesitant"
        
        # Default based on length and enthusiasm
        if len(user_input.strip()) > 10 and ("!" in user_input or "great" in user_lower):
            return "ready"
        elif "?" in user_input:
            return "questions"
        else:
            return "ready"  # Default to ready to keep conversation moving
            
    except Exception as e:
        logger.error(f"Readiness detection failed: {e}")
        return "ready"  # Default fallback


def _get_section_overview(framework) -> str:
    """Generate section overview for greeting"""
    try:
        sections = []
        for i in range(1, framework.metadata.total_sections + 1):
            section_data = framework_loader.get_section(i)
            if section_data:
                sections.append(section_data.name)
        
        return ", ".join(sections) if sections else "three key areas"
        
    except Exception as e:
        logger.error(f"Section overview generation failed: {e}")
        return "three key areas"
