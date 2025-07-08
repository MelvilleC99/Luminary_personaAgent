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
from memory.managers.section_completion_manager import SectionCompletionManager
from memory.managers.enhanced_context_manager import EnhancedContextManager

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
        self.context_manager = context_manager
        self.database = database
        
        # Load framework criteria
        self.framework_criteria = self._load_framework_criteria()
        
        # Initialize enhanced managers
        self.section_completion_manager = SectionCompletionManager(database)
        self.enhanced_context_manager = EnhancedContextManager(database, llm_tool)
        
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
        """Start a new conversation with opening message."""
        try:
            # Initialize conversation state
            initial_state = {
                "messages": [],
                "business_context": {},
                "framework_extractions": {},
                "current_focus": None,
                "user_intent": None,
                "conversation_stage": "opening",
                "session_id": session_id,
                "completion_percentage": 0.0,
                "token_usage": {},
                "framework_progress": {},
                "section_completion_manager": self.section_completion_manager,
                "enhanced_context_manager": self.enhanced_context_manager
            }
            
            # Don't generate a hardcoded opening message - let the workflow handle the first response
            
            return {
                "status": "conversation_started",
                "session_id": session_id
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
            # Add user message to enhanced context
            await self.enhanced_context_manager.add_message(
                session_id=session_id,
                role="user",
                content=user_input
            )
            
            # Debug: Ensure user_input is a string
            logger.debug(f"Processing user input: {type(user_input)} = {user_input}")
            
            # Get conversation context and build initial state
            conversation_context, token_count = await self.enhanced_context_manager.get_context_for_llm(session_id)
            
            # Build state for workflow - ensure user_input is a string
            if not isinstance(user_input, str):
                logger.error(f"user_input is not a string: {type(user_input)} = {user_input}")
                user_input = str(user_input)
            
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
                "section_completion_manager": self.section_completion_manager,
                "enhanced_context_manager": self.enhanced_context_manager
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
            
            # Add assistant response to enhanced context
            await self.enhanced_context_manager.add_message(
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
            conversation_state = await self.section_completion_manager.get_conversation_state(session_id)
            
            # Build progress response
            progress = {
                "overall_completion": self.section_completion_manager._calculate_overall_completion(conversation_state),
                "current_section": conversation_state.current_section,
                "total_sections": conversation_state.total_sections,
                "sections": {}
            }
            
            # Add section details
            for section_num, section_progress in conversation_state.section_progress.items():
                progress["sections"][section_progress.section_name] = {
                    "completed": len(section_progress.criteria_completed),
                    "total": len(section_progress.criteria_completed) + len(section_progress.criteria_missing),
                    "percentage": section_progress.completion_percentage,
                    "status": "Complete" if section_progress.is_complete else "In Progress",
                    "completed_items": [
                        {"key": key, "description": f"{key.replace('_', ' ').title()}"}
                        for key in section_progress.criteria_completed
                    ],
                    "missing_items": [
                        {"key": key, "description": f"{key.replace('_', ' ').title()}"}
                        for key in section_progress.criteria_missing
                    ]
                }
            
            return progress
            
        except Exception as e:
            logger.error(f"Error getting progress: {e}")
            return {
                "error": str(e),
                "overall_completion": 0,
                "current_section": 1,
                "total_sections": 6,
                "sections": {}
            }
    
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
        health["components"]["section_completion_manager"] = "initialized" if self.section_completion_manager else "missing"
        health["components"]["enhanced_context_manager"] = "initialized" if self.enhanced_context_manager else "missing"
        
        # Check workflow
        health["components"]["workflow"] = "compiled" if self.app else "missing"
        
        return health


# Maintain backwards compatibility
LangGraphPersonaAgent = ModularLangGraphPersonaAgent
