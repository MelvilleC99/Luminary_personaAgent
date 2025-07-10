"""
Modular LangGraph Persona Agent with enhanced context management.
Refactored into manageable components for better maintainability.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage

from .components.models import PersonaConversationState
from .components.workflow_nodes import WorkflowNodes
from .components.workflow_router import WorkflowRouter
from memory.redis_context_manager import RedisContextManager
from memory.managers.conversation_state import ConversationStateManager, ConversationStage
from memory.managers.enhanced_context_manager import EnhancedContextManager
from orchestrator.config import settings

logger = logging.getLogger(__name__)


class ModularLangGraphPersonaAgent:
    """
    Modular LangGraph-powered persona agent with intelligent section completion.
    Broken down into manageable components for better maintenance.
    """
    
    def __init__(self, llm_tool=None, session_manager=None, 
                 context_manager=None, database=None, **kwargs):
        """Initialize the modular persona agent."""
        self.llm_tool = llm_tool
        self.session_manager = session_manager
        self.database = database
        
        # Load framework criteria
        self.framework_criteria = self._load_framework_criteria()
        
        # Initialize Redis context manager if not provided
        if context_manager is None:
            self.context_manager = RedisContextManager(
                redis_url=settings.redis_url,
                database=database,
                llm_tool=llm_tool,
                max_token_limit=settings.max_context_tokens,
                recent_message_limit=settings.recent_message_limit
            )
        else:
            self.context_manager = context_manager
        
        # Initialize conversation state manager
        self.conversation_state_manager = ConversationStateManager(
            redis_context_manager=self.context_manager,
            database=database,
            framework_sections=self.framework_criteria
        )
        
        # Keep legacy enhanced context manager for backward compatibility
        self.enhanced_context_manager = EnhancedContextManager(database, llm_tool) if database else None
        
        # Initialize workflow components
        self.workflow_nodes = WorkflowNodes(llm_tool, self.framework_criteria)
        self.workflow_router = WorkflowRouter()
        
        # Build and compile the workflow
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        
        logger.info("Modular LangGraph Persona Agent initialized")
    
    def _load_framework_criteria(self) -> Dict[str, Any]:
        """Load framework criteria from YAML file."""
        try:
            criteria_path = Path(__file__).parent.parent / "knowledge" / "framework_criteria.yaml"
            with open(criteria_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load framework criteria: {e}")
            return {}
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph conversation workflow."""
        workflow = StateGraph(PersonaConversationState)
        
        # Add workflow nodes
        workflow.add_node("analyze_input", self.workflow_nodes.analyze_user_input)
        workflow.add_node("answer_question", self.workflow_nodes.answer_user_question)
        workflow.add_node("extract_and_respond", self.workflow_nodes.extract_and_respond)
        workflow.add_node("check_completion", self.workflow_nodes.check_completion)
        workflow.add_node("wrap_up", self.workflow_nodes.wrap_up_conversation)
        
        # Set entry point
        workflow.set_entry_point("analyze_input")
        
        # Add conditional routing
        workflow.add_conditional_edges(
            "analyze_input",
            self.workflow_router.route_after_analyze,
            {
                "answer_question": "answer_question",
                "extract_and_respond": "extract_and_respond"
            }
        )
        
        # Route from answer_question back to extraction
        workflow.add_edge("answer_question", "extract_and_respond")
        
        # Route from extraction to completion check
        workflow.add_edge("extract_and_respond", "check_completion")
        
        # Conditional routing after completion check
        workflow.add_conditional_edges(
            "check_completion",
            self.workflow_router.route_after_completion_check,
            {
                "extract_and_respond": "extract_and_respond",
                "wrap_up": "wrap_up",
                "__end__": END
            }
        )
        
        # End after wrap up
        workflow.add_edge("wrap_up", END)
        
        return workflow
    
    async def start_conversation(self, session_id: str) -> Dict[str, Any]:
        """Start a new conversation with proper greeting sequence."""
        try:
            # Step 1: Initial greeting - exactly as specified
            opening_message = """Hello, I'm Paul. I'm here to assist you in creating your personal persona. Let me know when you are ready to start."""
            
            # Initialize conversation state with greeting stage tracking
            initial_state = {
                "messages": [],
                "business_context": {},
                "framework_extractions": {},
                "current_section": 1,
                "current_focus": None,
                "user_intent": None,
                "conversation_stage": "initial_greeting",  # Track greeting stage
                "session_id": session_id,
                "completion_percentage": 0.0,
                "token_usage": {},
                "framework_progress": {},
                "conversation_state_manager": self.conversation_state_manager,
                "context_manager": self.context_manager
            }
            
            return {
                "status": "conversation_started",
                "message": opening_message,
                "conversation_type": "persona_building",
                "completion_percentage": 0.0,
                "session_id": session_id,
                "conversation_stage": "initial_greeting"
            }
            
        except Exception as e:
            logger.error(f"Failed to start conversation: {e}")
            return {
                "status": "error",
                "message": "I'm sorry, I encountered an issue starting our conversation. Please try again.",
                "error": str(e)
            }
    
    async def process(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        Backward compatibility method for coordinator.
        Routes to process_input method.
        """
        return await self.process_input(session_id, user_input)
    
    async def process_input(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """Process user input through the LangGraph workflow."""
        try:
            # Add user message to context if available
            if self.context_manager:
                await self.context_manager.add_message(
                    session_id=session_id,
                    role="user",
                    content=user_input
                )
            
            # Debug: Ensure user_input is a string
            logger.debug(f"Processing user input: {type(user_input)} = {user_input}")
            
            # Get conversation context and build initial state
            conversation_context = ""
            token_count = 0
            if self.context_manager:
                conversation_context, token_count = await self.context_manager.get_context_for_llm(session_id)
            
            # Build state for workflow - ensure user_input is a string
            if not isinstance(user_input, str):
                logger.error(f"user_input is not a string: {type(user_input)} = {user_input}")
                user_input = str(user_input)
            
            # Get current conversation stage
            conversation_stage = "initial_greeting"  # Default for new conversations
            if self.conversation_state_manager:
                current_state = await self.conversation_state_manager.get_conversation_state(session_id)
                
                # Handle ConversationState object properly
                if hasattr(current_state, 'conversation_stage'):
                    conversation_stage = getattr(current_state, 'conversation_stage', "initial_greeting")
                elif isinstance(current_state, dict):
                    conversation_stage = current_state.get("conversation_stage", "initial_greeting")
            
            logger.info(f"Conversation stage: {conversation_stage}")
            
            # Handle greeting sequence stages
            if conversation_stage == "initial_greeting":
                return await self._handle_ready_response(session_id, user_input, current_state if self.conversation_state_manager else None)
            elif conversation_stage == "waiting_for_section_confirm":
                return await self._handle_section_start(session_id, user_input, current_state if self.conversation_state_manager else None)
            elif conversation_stage == "resuming":
                return await self._handle_resume(session_id, user_input, current_state if self.conversation_state_manager else None)
            
            # Continue with normal section work
            state = {
                "messages": [HumanMessage(content=user_input)],
                "business_context": {},
                "framework_extractions": {},
                "current_focus": None,
                "user_intent": None,
                "conversation_stage": "gathering",
                "session_id": session_id,
                "completion_percentage": 0.0,
                "token_usage": {"input_tokens": token_count},
                "framework_progress": {},
                "conversation_state_manager": self.conversation_state_manager,
                "context_manager": self.context_manager
            }
            
            # Run through workflow with recursion limit
            result = await self.app.ainvoke(
                state, 
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 10  # Prevent infinite loops
                }
            )
            
            # Extract response message
            assistant_messages = [msg for msg in result["messages"] if msg.type == "ai"]
            logger.info(f"Found {len(assistant_messages)} AI messages in result")
            logger.info(f"Total messages in result: {len(result.get('messages', []))}")
            
            if assistant_messages:
                # Ensure content is a string
                content = assistant_messages[-1].content
                logger.info(f"AI message content: '{content}' (type: {type(content)})")
                
                # Check if the AI response is just echoing the user input (bug detection)
                user_messages = [msg for msg in result["messages"] if msg.type == "human"]
                if user_messages and content.strip().lower() == user_messages[-1].content.strip().lower():
                    logger.warning("Detected AI echoing user input - generating proper response")
                    # Generate a proper greeting response
                    if any(word in content.lower() for word in ["hi", "hello", "hey", "good morning", "good afternoon"]):
                        response_message = "Hello! I'm here to help you build your personal brand persona. To get started, could you tell me about your area of expertise? What's the domain you work in?"
                    else:
                        response_message = "Thank you for sharing that information. To build your persona effectively, I'd like to understand more about your expertise. What's your primary area of specialization?"
                else:
                    # Use the actual AI response
                    if isinstance(content, dict):
                        response_message = content.get("message", "I'd like to learn more about your expertise.")
                    elif isinstance(content, str):
                        response_message = content
                    else:
                        response_message = str(content)
                    
                logger.info(f"Final response message: '{response_message[:100]}...'")
            else:
                logger.warning("No AI messages found in workflow result - using fallback")
                response_message = "Hello! I'm here to help you build your personal brand persona. What would you like to work on today?"
            
            # Add assistant response to context if available
            if self.context_manager:
                await self.context_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_message,
                    agent_type="persona_agent"
                )
            
            # Update session progress if session manager available
            if self.session_manager and result.get("completion_percentage", 0) > 0:
                try:
                    await self.session_manager.update_framework_progress(
                        session_id, 
                        result["completion_percentage"]
                    )
                except Exception as e:
                    logger.warning(f"Could not update session progress: {e}")
            
            return {
                "status": "success",
                "message": response_message,
                "completion_percentage": result.get("completion_percentage", 0),
                "conversation_stage": result.get("conversation_stage", "gathering"),
                "token_usage": result.get("token_usage", {}),
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing input: {e}")
            return {
                "status": "error",
                "message": "I encountered an issue processing your response. Could you try rephrasing that?",
                "error": str(e),
                "session_id": session_id
            }
    
    async def get_framework_progress(self, session_id: str) -> Dict[str, Any]:
        """Get framework progress - alias for get_progress."""
        return await self.get_progress(session_id)
    
    async def get_progress(self, session_id: str) -> Dict[str, Any]:
        """Get detailed progress information for the session."""
        try:
            if not self.conversation_state_manager:
                return {
                    "error": "Conversation state manager not available",
                    "overall_completion": 0,
                    "current_section": 1,
                    "total_sections": 6,
                    "sections": {}
                }
            
            # Get framework progress summary
            progress_summary = await self.conversation_state_manager.get_framework_progress_summary(session_id)
            
            return progress_summary
            
        except Exception as e:
            logger.error(f"Error getting progress: {e}")
            return {
                "error": str(e),
                "overall_completion": 0,
                "current_section": 1,
                "total_sections": 6,
                "sections": {}
            }
    
    async def _handle_ready_response(self, session_id: str, user_input: str, state) -> Dict[str, Any]:
        """Handle user response to initial greeting."""
        user_lower = user_input.lower().strip()
        ready_words = ["ready", "yes", "sure", "okay", "let's go", "lets go", "start", "begin", "go", "ok", "let's start", "lets start"]
        
        if any(word in user_lower for word in ready_words):
            # User is ready to start - begin with first section
            section_start = """Great! Let's dive into your persona.

**Section 1: Core Expertise & Ideal Customer Profile**

This helps me understand your expertise and who you serve.

What's a broad topic or domain you understand deeply - one you could speak on confidently for hours?"""
            
            # Update conversation stage
            if self.conversation_state_manager:
                try:
                    await self.conversation_state_manager.set_conversation_stage(
                        session_id, 
                        ConversationStage.SECTION_WORK
                    )
                except Exception as e:
                    logger.warning(f"Could not update conversation stage: {e}")
            
            # Add assistant message to context
            if self.context_manager:
                try:
                    await self.context_manager.add_message(
                        session_id=session_id,
                        role="assistant", 
                        content=section_start
                    )
                except Exception as e:
                    logger.warning(f"Could not add message to context: {e}")
            
            return {
                "status": "section_started",
                "message": section_start,
                "conversation_stage": "section_work",
                "current_section": 1,
                "session_id": session_id
            }
        else:
            fallback_msg = "No problem! Just let me know when you're ready to start building your personal persona."
            
            if self.context_manager:
                try:
                    await self.context_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=fallback_msg
                    )
                except Exception as e:
                    logger.warning(f"Could not add message to context: {e}")
            
            return {
                "status": "waiting_for_ready",
                "message": fallback_msg,
                "conversation_stage": "initial_greeting",
                "session_id": session_id
            }

    async def _handle_section_start(self, session_id: str, user_input: str, state) -> Dict[str, Any]:
        """Handle confirmation to start section work."""
        user_lower = user_input.lower().strip()
        confirm_words = ["yes", "ready", "sure", "okay", "let's go", "start", "begin", "ok"]
        
        if any(word in user_lower for word in confirm_words):
            # Step 3: Begin section work
            # Note: We can't call the missing methods, so we'll handle this through the workflow
            
            section_start = """Great! 

Section 1: Core Expertise & Ideal Customer Profile

What's a broad topic or domain you understand deeply - one you could speak on confidently for hours?"""
            
            if self.context_manager:
                await self.context_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=section_start
                )
            
            return {
                "status": "section_work", 
                "message": section_start,
                "conversation_stage": "section_work",
                "current_section": 1,
                "session_id": session_id
            }
        else:
            wait_msg = "Take your time! Just let me know when you're ready to start with the first section."
            
            if self.context_manager:
                await self.context_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=wait_msg
                )
            
            return {
                "status": "waiting_for_confirmation",
                "message": wait_msg,
                "conversation_stage": "waiting_for_section_confirm",
                "session_id": session_id
            }

    async def _handle_resume(self, session_id: str, user_input: str, state) -> Dict[str, Any]:
        """Handle session resumption."""
        user_lower = user_input.lower().strip()
        ready_words = ["ready", "yes", "continue", "sure", "okay", "let's continue", "ok"]
        
        if any(word in user_lower for word in ready_words):
            # Resume normal section work
            # Note: We can't call the missing methods, so we'll handle this through the workflow
            
            current_section = 1
            completion = 0.0
            
            # Try to get state information if available
            if state and hasattr(state, 'current_section'):
                current_section = getattr(state, 'current_section', 1)
                completion = getattr(state, 'completion_percentage', 0.0)
            elif isinstance(state, dict):
                current_section = state.get("current_section", 1)
                completion = state.get("completion_percentage", 0.0)
            
            resume_message = f"Perfect! Let's continue with Section {current_section}. We're about {completion:.0f}% complete overall."
            
            if self.context_manager:
                await self.context_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=resume_message
                )
            
            return {
                "status": "section_work",
                "message": resume_message,
                "conversation_stage": "section_work",
                "current_section": current_section,
                "completion_percentage": completion,
                "session_id": session_id
            }
        else:
            wait_msg = "No rush! Let me know when you're ready to continue where we left off."
            
            if self.context_manager:
                await self.context_manager.add_message(
                    session_id=session_id,
                    role="assistant", 
                    content=wait_msg
                )
            
            return {
                "status": "waiting_for_resume",
                "message": wait_msg,
                "conversation_stage": "resuming",
                "session_id": session_id
            }

    async def resume_session(self, session_id: str) -> Dict[str, Any]:
        """Resume a paused session."""
        try:
            if not self.conversation_state_manager:
                return await self.start_conversation(session_id)
            
            state = await self.conversation_state_manager.get_conversation_state(session_id)
            
            if not state:
                return await self.start_conversation(session_id)
            
            # Handle ConversationState object properly
            current_section = state.current_section
            completion = await self.conversation_state_manager.get_overall_completion(session_id)
            conversation_stage = getattr(state, 'conversation_stage', 'section_work')
            
            section_names = [
                "Core Expertise & Ideal Customer Profile",
                "Brand Personality & Profile DNA", 
                "Positioning & Expertise", 
                "Voice, Style & Tone",
                "Content Goals & Target Audience",
                "Long-Term Vision & Success Metrics"
            ]
            
            if conversation_stage == "initial_greeting":
                resume_msg = "Welcome back! I'm still here to help you create your personal persona. Let me know when you're ready to start."
            elif conversation_stage == "waiting_for_section_confirm":
                resume_msg = "Welcome back! We were about to start working on the six persona sections. Are you ready to begin?"
            elif current_section <= 6:
                section_name = section_names[current_section-1] if current_section <= len(section_names) else "the final section"
                resume_msg = f"Hey! We ended off working on Section {current_section}: {section_name}. We're about {completion:.0f}% complete overall. Let me know if you're ready to continue."
            else:
                resume_msg = "Welcome back! We've completed all sections and your persona is ready."
            
            # Note: We can't call the missing update_conversation_stage method
            # The workflow will handle the conversation stage transitions
            
            return {
                "status": "resumed",
                "message": resume_msg,
                "conversation_stage": "resuming",
                "current_section": current_section,
                "completion_percentage": completion,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Failed to resume session: {e}")
            return await self.start_conversation(session_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of the agent and its components."""
        health = {
            "agent_type": "modular_langgraph_persona_agent",
            "status": "healthy",
            "components": {}
        }
        
        # Check LLM tool
        health["components"]["llm_tool"] = "available" if self.llm_tool else "missing"
        
        # Check database
        health["components"]["database"] = "available" if self.database else "missing"
        
        # Check framework criteria
        health["components"]["framework_criteria"] = "loaded" if self.framework_criteria else "missing"
        
        # Check managers
        health["components"]["conversation_state_manager"] = "initialized" if self.conversation_state_manager else "missing"
        health["components"]["context_manager"] = "initialized" if self.context_manager else "missing"
        health["components"]["enhanced_context_manager"] = "initialized" if self.enhanced_context_manager else "missing"
        
        # Check workflow
        health["components"]["workflow"] = "compiled" if self.app else "missing"
        
        return health


