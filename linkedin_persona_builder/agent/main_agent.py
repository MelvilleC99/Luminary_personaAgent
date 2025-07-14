"""
LinkedIn Persona Builder - Main Agent

Central orchestrator that coordinates all agent components and manages the conversation lifecycle.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Internal imports
from agent.components.conversation_manager import conversation_manager
from agent.components.state_manager import state_manager
from agent.components.workflow_manager import workflow_manager
from agent.components.validation_manager import validation_manager
from agent.components.persona_builder import persona_builder
from memory.session_manager import session_manager as session_mgr
from memory.context_manager import context_manager
from memory.recovery_manager import recovery_manager
from data.redis.redis_utils import redis_manager
from knowledge.framework_loader import framework_loader
from orchestrator.config import settings

# Configure logging
logger = logging.getLogger(__name__)


class PersonaAgent:
    """
    Main agent class that orchestrates the entire conversation process.
    
    Handles:
    - Session lifecycle management
    - LangGraph workflow coordination
    - Component integration
    - Error handling and recovery
    """
    
    def __init__(self):
        """Initialize all components and build LangGraph workflow"""
        # Initialize all components
        self.conversation_manager = conversation_manager
        self.state_manager = state_manager
        self.workflow_manager = workflow_manager
        self.validation_manager = validation_manager
        self.persona_builder = persona_builder
        self.session_manager = session_mgr
        self.context_manager = context_manager
        self.recovery_manager = recovery_manager
        
        # Load framework and build LangGraph workflow
        self.framework = framework_loader.load_current()
        self.workflow = None
        self._initialize_workflow()
        
        logger.info("PersonaAgent initialized successfully")
    
    def _initialize_workflow(self):
        """Initialize the LangGraph workflow"""
        try:
            self.workflow = self.workflow_manager.build_graph()
            logger.info("LangGraph workflow built successfully")
        except Exception as e:
            logger.error(f"Workflow initialization failed: {e}")
            self.workflow = None
    
    async def process_user_input(self, session_id: str, user_input: str, 
                                user_id: str, user_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for processing user interactions
        
        Process:
        1. Load or create session
        2. Build workflow state
        3. Execute LangGraph workflow
        4. Process results and update state
        """
        try:
            logger.info(f"Processing user input - session: {session_id}, user: {user_id}, "
                       f"input_length: {len(user_input) if user_input else 0}")
            
            # 1. Get or create session
            session_state = await self._get_or_create_session(session_id, user_id)
            if not session_state:
                return self._error_response("Failed to create or retrieve session")
            
            # 2. Get persona data
            persona_data = await self.state_manager.get_persona_data(session_id)
            if not persona_data:
                persona_data = await self.state_manager.initialize_persona_data(session_id)
            
            # 3. Build workflow state
            workflow_state = {
                'session_id': session_id,
                'user_id': user_id,
                'user_input': user_input,
                'user_name': user_name or "there",
                'current_section': session_state.get("current_section", 1),
                'current_criterion': session_state.get("current_criterion", ""),
                'follow_up_attempts': session_state.get("follow_up_attempts", 0),
                'session_state': session_state,
                'persona_data': persona_data,
                'requires_user_input': True,
                'session_complete': False,
                'next_node': 'greeting' if not user_input else 'question'
            }
            
            # 4. Execute LangGraph workflow
            if not self.workflow:
                self._initialize_workflow()
            
            if self.workflow:
                result = await self._execute_workflow(workflow_state)
            else:
                # Fallback to direct processing
                result = await self._fallback_processing(workflow_state)
            
            # 5. Process results and update state
            return await self._process_workflow_result(result, session_id)
            
        except Exception as e:
            logger.error(f"User input processing failed: {e}", extra={"session_id": session_id})
            return await self._handle_processing_error(e, session_id, user_id)
    
    async def create_session(self, user_id: str, user_name: Optional[str] = None) -> Dict[str, Any]:
        """Create new conversation session"""
        try:
            session_id = str(uuid.uuid4())
            logger.info(f"Creating new session: {session_id} for user: {user_id}")
            
            # Initialize session state
            success = await self.session_manager.create_session(session_id, user_id)
            if not success:
                raise Exception("Session creation failed")
            
            # Initialize persona data
            persona_data = await self.state_manager.initialize_persona_data(session_id)
            if not persona_data:
                raise Exception("Persona data initialization failed")
            
            # Generate greeting message
            greeting_context = {
                "user_name": user_name or "there",
                "total_sections": self.framework.metadata.total_sections,
                "estimated_time": self.framework.metadata.estimated_time,
                "section_overview": self._get_section_overview()
            }
            
            greeting_message = await self.conversation_manager.generate_greeting(greeting_context)
            
            return {
                "session_id": session_id,
                "greeting_message": greeting_message,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    async def _get_or_create_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get existing session or create new one with recovery"""
        try:
            if session_id:
                # Try to get existing session
                session_exists = await redis_manager.session_exists(session_id)
                if session_exists:
                    session_data = await redis_manager.get_session_data(session_id)
                    if session_data:
                        return session_data
            
            # Session doesn't exist, try recovery
            try:
                recovered_session = await self.recovery_manager.recover_session(session_id)
                if recovered_session:
                    return recovered_session
            except Exception as recovery_error:
                logger.warning(f"Session recovery failed: {recovery_error}")
            
            # Create new session if recovery fails
            success = await self.session_manager.create_session(session_id, user_id)
            if success:
                return await redis_manager.get_session_data(session_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Session creation/retrieval failed: {e}")
            return None
    
    async def _execute_workflow(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LangGraph workflow with proper error handling"""
        try:
            # Determine starting node based on state
            if not workflow_state.get("user_input"):
                # New session - start with greeting
                from agent.langgraph_nodes.greeting_node import greeting_node
                result = await greeting_node(workflow_state)
            else:
                # Existing session - determine node based on conversation state
                current_node = self._determine_current_node(workflow_state)
                result = await self._execute_node(current_node, workflow_state)
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return await self._fallback_processing(workflow_state)
    
    def _determine_current_node(self, state: Dict[str, Any]) -> str:
        """Determine which node to execute based on conversation state"""
        try:
            # Check if session is complete
            if state.get("session_complete", False):
                return "completion"
            
            # Check overall progress
            persona_data = state.get("persona_data", {})
            overall_completion = persona_data.get("overall_completion", 0.0)
            
            if overall_completion >= getattr(settings, 'section_completion_threshold', 0.9):
                return "review"
            
            # Check if we need to transition sections
            current_section = state.get("current_section", 1)
            if current_section > 3:  # 3 sections total
                return "review"
            
            # Default to question flow
            return "question"
            
        except Exception as e:
            logger.error(f"Node determination failed: {e}")
            return "question"
    
    async def _execute_node(self, node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute specific LangGraph node"""
        try:
            if node_name == "greeting":
                from agent.langgraph_nodes.greeting_node import greeting_node
                return await greeting_node(state)
            elif node_name == "question":
                from agent.langgraph_nodes.question_node import question_node
                return await question_node(state)
            elif node_name == "evaluation":
                from agent.langgraph_nodes.evaluation_node import evaluation_node
                return await evaluation_node(state)
            elif node_name == "follow_up":
                from agent.langgraph_nodes.followup_node import followup_node
                return await followup_node(state)
            elif node_name == "transition":
                from agent.langgraph_nodes.transition_node import transition_node
                return await transition_node(state)
            elif node_name == "review":
                from agent.langgraph_nodes.review_node import review_node
                return await review_node(state)
            elif node_name == "completion":
                from agent.langgraph_nodes.completion_node import completion_node
                return await completion_node(state)
            else:
                logger.warning(f"Unknown node: {node_name}")
                return await self._fallback_processing(state)
                
        except Exception as e:
            logger.error(f"Node execution failed for {node_name}: {e}")
            return await self._fallback_processing(state)
    
    async def _process_workflow_result(self, result: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Process workflow results and update state"""
        try:
            # Extract key information from result
            agent_response = result.get("agent_response", "I'm here to help you build your LinkedIn persona.")
            requires_user_input = result.get("requires_user_input", True)
            session_complete = result.get("session_complete", False)
            current_section = result.get("current_section", 1)
            current_criterion = result.get("current_criterion", "")
            follow_up_attempts = result.get("follow_up_attempts", 0)
            error_message = result.get("error_message", "")
            
            # Update session state if needed
            if current_section or current_criterion:
                await redis_manager.update_session_state(
                    session_id, 
                    {
                        "current_section": current_section,
                        "current_criterion": current_criterion,
                        "follow_up_attempts": follow_up_attempts,
                        "updated_at": datetime.now().isoformat()
                    }
                )
            
            # Get current progress
            progress_data = await self.state_manager.get_overall_progress(session_id)
            
            # Track token usage (estimate)
            estimated_tokens = len(agent_response) // 4  # Rough estimate
            await redis_manager.increment_token_usage(session_id, estimated_tokens)
            
            # Build response
            response = {
                "agent_response": agent_response,
                "requires_user_input": requires_user_input,
                "session_complete": session_complete,
                "progress": progress_data or {},
                "current_section": current_section,
                "current_criterion": current_criterion,
                "error": error_message if error_message else None,
                "success": True
            }
            
            # Add final persona data if session is complete
            if session_complete:
                final_persona = result.get("final_persona")
                if final_persona:
                    response["final_persona"] = final_persona
            
            logger.info(f"Workflow result processed - session: {session_id}, "
                       f"complete: {session_complete}, "
                       f"progress: {progress_data.get('overall_completion', 0) if progress_data else 0}")
            
            return response
            
        except Exception as e:
            logger.error(f"Workflow result processing failed: {e}")
            return self._error_response(f"Result processing failed: {e}")
    
    async def _fallback_processing(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback processing when LangGraph fails"""
        try:
            session_id = workflow_state["session_id"]
            user_input = workflow_state.get("user_input", "")
            current_section = workflow_state.get("current_section", 1)
            user_name = workflow_state.get("user_name", "there")
            
            logger.warning(f"Using fallback processing for session: {session_id}")
            
            if not user_input:
                # Initial greeting
                greeting_context = {
                    "user_name": user_name,
                    "total_sections": self.framework.metadata.total_sections,
                    "estimated_time": self.framework.metadata.estimated_time
                }
                greeting = await self.conversation_manager.generate_greeting(greeting_context)
                
                return {
                    "agent_response": greeting,
                    "requires_user_input": True,
                    "session_complete": False,
                    "current_section": 1,
                    "current_criterion": "broad_domain_expertise"
                }
            else:
                # Simple question flow
                incomplete_criteria = await self.state_manager.get_incomplete_criteria(
                    session_id, current_section
                )
                
                if incomplete_criteria:
                    criterion_name = incomplete_criteria[0]
                    criterion_data = framework_loader.get_criterion(current_section, criterion_name)
                    
                    if criterion_data:
                        # Build context and generate question
                        context = await self.context_manager.build_question_context(session_id)
                        question = await self.conversation_manager.generate_question(
                            criterion_data, context
                        )
                        
                        return {
                            "agent_response": question,
                            "requires_user_input": True,
                            "session_complete": False,
                            "current_section": current_section,
                            "current_criterion": criterion_name
                        }
                
                # No more criteria, complete session
                return {
                    "agent_response": f"Thank you, {user_name}! Your LinkedIn persona is complete. Let me finalize everything for you.",
                    "requires_user_input": False,
                    "session_complete": True
                }
                
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            return {
                "agent_response": "I'm here to help you build your LinkedIn persona. Let's start with some questions about your expertise.",
                "requires_user_input": True,
                "session_complete": False,
                "error": str(e)
            }
    
    async def _handle_processing_error(self, error: Exception, session_id: str, user_id: str) -> Dict[str, Any]:
        """Handle processing errors with recovery"""
        try:
            logger.error(f"Processing error: {error}")
            
            # Try recovery
            recovery_success = await self.recovery_manager.handle_redis_failure(session_id)
            
            if recovery_success:
                return {
                    "agent_response": "I encountered a brief issue but I'm ready to continue. How can I help you with your LinkedIn persona?",
                    "requires_user_input": True,
                    "session_complete": False,
                    "error": None,
                    "success": True,
                    "recovered": True
                }
            else:
                return self._error_response(f"System error: {error}")
                
        except Exception as recovery_error:
            logger.error(f"Error recovery failed: {recovery_error}")
            return self._error_response("System temporarily unavailable")
    
    def _error_response(self, error_message: str) -> Dict[str, Any]:
        """Generate standardized error response"""
        return {
            "agent_response": "I'm experiencing some technical difficulties. Please try again in a moment.",
            "requires_user_input": True,
            "session_complete": False,
            "error": error_message,
            "success": False
        }
    
    async def get_session_progress(self, session_id: str) -> Dict[str, Any]:
        """Get detailed session progress for front-end"""
        try:
            progress = await self.state_manager.get_overall_progress(session_id)
            session_data = await redis_manager.get_session_data(session_id)
            
            return {
                "overall_completion": progress.get("overall_completion", 0.0) if progress else 0.0,
                "section_progress": progress.get("section_progress", {}) if progress else {},
                "current_section": session_data.get("current_section", 1) if session_data else 1,
                "current_criterion": session_data.get("current_criterion", "") if session_data else "",
                "total_criteria": progress.get("total_criteria", 0) if progress else 0,
                "completed_criteria": progress.get("completed_criteria", 0) if progress else 0,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Progress retrieval failed: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    async def export_persona(self, session_id: str) -> Dict[str, Any]:
        """Export completed persona"""
        try:
            exported_persona = await self.persona_builder.export_for_json(session_id)
            
            if "error" not in exported_persona:
                return {
                    "persona": exported_persona,
                    "success": True
                }
            else:
                return {
                    "error": exported_persona["error"],
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"Persona export failed: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    async def health_check(self) -> bool:
        """Simple health check for coordinator"""
        try:
            # Check if workflow is initialized
            if not self.workflow:
                return False
            
            # Check framework is loaded
            if not self.framework:
                return False
            
            # Check core components
            return (
                self.conversation_manager is not None and
                self.state_manager is not None and
                self.workflow_manager is not None
            )
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def _get_section_overview(self) -> str:
        """Generate section overview for greeting"""
        try:
            sections = []
            for i in range(1, self.framework.metadata.total_sections + 1):
                section_data = framework_loader.get_section(i)
                if section_data:
                    sections.append(section_data.name)
            
            return ", ".join(sections) if sections else "three key areas"
            
        except Exception as e:
            logger.error(f"Section overview generation failed: {e}")
            return "three key areas"


# Global persona agent instance
persona_agent = PersonaAgent()
