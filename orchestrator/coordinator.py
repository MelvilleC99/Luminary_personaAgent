"""
Main Coordinator - Orchestrates all agents and manages the persona building workflow.
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from memory.redis_context_manager import RedisContextManager
from tools.llm_tool import LLMTool
from database.models import PersonaSession, SessionStatus, AgentType
from orchestrator.config import settings

logger = logging.getLogger(__name__)


class PersonaCoordinator:
    """Main coordinator for the persona building agent system."""
    
    def __init__(self, database=None):
        """
        Initialize the coordinator with all necessary components.
        
        Args:
            database: Database client for persistence
        """
        # Initialize database if not provided
        if database is None:
            try:
                from database.supabase_client import SupabaseClient
                database = SupabaseClient(settings.supabase_url, settings.supabase_key)
                logger.info("Database client initialized")
            except Exception as e:
                logger.warning(f"Database initialization failed: {e}")
                database = None
        
        self.database = database
        
        # Initialize LLM tool with multi-provider support and database
        self.llm_tool = LLMTool(
            api_keys=settings.api_keys,
            llm_assignments=settings.llm_config,
            database=database
        )
        
        # Initialize Redis context manager
        self.redis_context_manager = RedisContextManager(
            redis_url=settings.redis_url,
            database=database,
            llm_tool=self.llm_tool,
            max_token_limit=settings.max_context_tokens,
            recent_message_limit=settings.recent_message_limit
        )
        
        # Initialize enhanced session manager with Redis support
        from memory.managers.session_manager import SessionManager
        self.session_manager = SessionManager(
            redis_context_manager=self.redis_context_manager,
            database=database
        )
        
        # Agent registry - will be populated as agents are initialized
        self.agents = {}
        
        # Initialize agents
        self._initialize_agents()
        
        # Task queue for managing agent workload
        self.task_queue = asyncio.Queue()
        
        logger.info("Coordinator initialized successfully")
    
    def register_agent(self, agent_type: str, agent_instance):
        """
        Register an agent with the coordinator.
        
        Args:
            agent_type: Type/name of the agent
            agent_instance: The agent instance
        """
        self.agents[agent_type] = agent_instance
        logger.info(f"Registered agent: {agent_type}")
    
    async def start_session(self, user_id: Optional[str] = None, 
                          website_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a new persona building session.
        
        Args:
            user_id: Optional user identifier
            website_url: Optional company website URL
            
        Returns:
            Session information and initial response
        """
        try:
            # Create new session
            session = await self.session_manager.create_session(user_id)
            
            # Add website URL if provided
            if website_url:
                await self.session_manager.set_website_url(session.id, website_url)
            
            # Start conversation using Persona Agent (no conflicting system message)
            if "persona_agent" in self.agents:
                response = await self.agents["persona_agent"].start_conversation(session.id)
                
                return {
                    "session_id": session.id,
                    "status": response.get("status", "started"),
                    "message": response.get("message", ""),
                    "conversation_type": response.get("conversation_type", "persona_building"),
                    "completion_percentage": response.get("completion_percentage", 0.0),
                    "conversation_stage": response.get("conversation_stage", "initial_greeting"),
                    "progress": await self.session_manager.get_session_progress(session.id)
                }
            else:
                # Fallback to basic conversation
                fallback_message = "Welcome! I'm excited to help you build a comprehensive brand persona. What's something about your business that you could talk about for hours?"
                
                return {
                    "session_id": session.id,
                    "status": "conversation_started",
                    "message": fallback_message,
                    "conversation_type": "persona_building",
                    "completion_percentage": 0.0,
                    "progress": await self.session_manager.get_session_progress(session.id)
                }
            
            logger.info(f"Started new session: {session.id}")
            
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def resume_session(self, session_id: str) -> Dict[str, Any]:
        """
        Resume an existing conversational session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session status and continuation prompt
        """
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found", "status": "not_found"}
            
            # Resume if paused
            if session.status == SessionStatus.PAUSED:
                session = await self.session_manager.resume_session(session_id)
            
            # Check if session is completed
            if session.status == SessionStatus.COMPLETED:
                return {
                    "session_id": session_id,
                    "status": "completed",
                    "message": "Your persona building session is complete! Your comprehensive brand persona has been generated.",
                    "framework_progress": await self._get_framework_progress(session_id)
                }
            
            # Get continuation prompt based on current progress
            if "persona_agent" in self.agents:
                # Get current framework progress
                progress = await self.agents["persona_agent"].get_framework_progress(session_id)
                
                # Generate continuation message
                continuation_message = await self._generate_continuation_message(progress)
                
                return {
                    "session_id": session_id,
                    "status": "resumed",
                    "message": continuation_message,
                    "framework_progress": progress
                }
            else:
                return {
                    "session_id": session_id,
                    "status": "resumed",
                    "message": "Let's continue building your brand persona. What would you like to explore next?",
                    "framework_progress": await self._get_framework_progress(session_id)
                }
            
        except Exception as e:
            logger.error(f"Failed to resume session {session_id}: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def process_user_input(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        Process user input through conversational persona building.
        
        Args:
            session_id: Session identifier
            user_input: User's conversational input
            
        Returns:
            Response from the persona agent
        """
        start_time = time.time()
        logger.info(f"🎯 Processing conversational input for session {session_id}: '{user_input[:50]}...'")
        
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found", "status": "not_found"}
            
            logger.info(f"📋 Session found - Status: {session.status}")
            
            # Route to persona agent for conversational processing
            if "persona_agent" in self.agents:
                logger.info("🤖 Routing to persona agent...")
                agent_start = time.time()
                
                response = await self.agents["persona_agent"].process(session_id, user_input)
                
                agent_time = time.time() - agent_start
                logger.info(f"✅ Persona agent completed in {agent_time:.2f}s")
                
                # Update session status if needed
                if response.get("status") == "completion":
                    await self.session_manager.mark_persona_generated(session_id)
                
            else:
                logger.warning("⚠️ Persona agent not available, using fallback")
                response = await self._basic_conversational_processing(session_id, user_input)
            
            total_time = time.time() - start_time
            logger.info(f"🏁 Total processing time: {total_time:.2f}s")
            
            return response
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ Failed to process input for session {session_id} after {total_time:.2f}s: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def get_next_question(self, session_id: str) -> Dict[str, Any]:
        """
        Get the next question for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Next question information
        """
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found"}
            
            # Check if all questions are completed
            if session.current_question > 30:
                return await self._handle_session_completion(session_id)
            
            # Load questions from knowledge base
            questions = await self._load_questions()
            current_q = next(
                (q for q in questions if q["id"] == session.current_question), 
                None
            )
            
            if not current_q:
                return {"error": f"Question {session.current_question} not found"}
            
            # Format the question message
            message = f"Question {session.current_question}/30 - {current_q['section']}\n\n{current_q['text']}"
            
            # Add assistant message to context
            await self.context_manager.add_assistant_message(
                session_id, message, session.current_question, AgentType.QUESTION
            )
            
            return {
                "message": message,
                "question": current_q,
                "status": "question_ready"
            }
            
        except Exception as e:
            logger.error(f"Failed to get next question for session {session_id}: {e}")
            return {"error": str(e)}
    
    async def _basic_question_processing(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        Basic question processing when question agent is not available.
        
        Args:
            session_id: Session identifier
            user_input: User's answer
            
        Returns:
            Processing result
        """
        # Simple length-based assessment
        if len(user_input.strip()) < 20:
            return {
                "status": "needs_more_detail",
                "message": "Could you provide more detail? I'd love to understand this better to create an effective persona."
            }
        
        # Move to next question
        session = await self.session_manager.advance_question(session_id)
        
        if session.current_question <= 30:
            next_q = await self.get_next_question(session_id)
            return {
                "status": "question_completed",
                "message": f"Perfect! Let's move on.\n\n{next_q['message']}",
                "question": next_q.get("question")
            }
        else:
            return await self._handle_session_completion(session_id)
    
    async def _handle_session_completion(self, session_id: str) -> Dict[str, Any]:
        """
        Handle session completion logic.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Completion response
        """
        await self.session_manager.mark_persona_generated(session_id)
        
        completion_message = """
        Congratulations! You've completed all 30 questions. 
        
        I'm now processing your responses to create your comprehensive marketing persona. 
        This includes your strategic positioning, target audience psychology, brand voice, 
        and conversion insights.
        
        Your persona will be ready shortly!
        """
        
        await self.context_manager.add_assistant_message(
            session_id, completion_message.strip()
        )
        
        return {
            "status": "completed",
            "message": completion_message.strip()
        }
    
    async def _load_questions(self) -> List[Dict[str, Any]]:
        """Load questions from the knowledge base."""
        try:
            import json
            from pathlib import Path
            
            questions_path = Path(__file__).parent.parent / "knowledge" / "questions.json"
            with open(questions_path, 'r') as f:
                data = json.load(f)
            
            # Flatten questions into a list
            questions = []
            for section in data.get("sections", []):
                for question in section.get("questions", []):
                    questions.append(question)
            
            logger.info(f"Loaded {len(questions)} questions from knowledge base")
            return questions
            
        except Exception as e:
            logger.error(f"Failed to load questions: {e}")
            # Fallback to placeholder
            return [
                {"id": i, "text": f"Question {i}", "section": "Sample"}
                for i in range(1, 31)
            ]
    
    async def _generate_continuation_message(self, progress: Dict[str, Any]) -> str:
        """Generate continuation message based on current progress."""
        
        completion = progress.get("overall_completion", 0)
        next_focus = progress.get("next_focus")
        
        if completion < 20:
            return "Welcome back! We're just getting started with your persona. Let's continue exploring your expertise and ideal clients."
        elif completion < 50:
            return "Great to have you back! We've made good progress on your persona. Let's continue building the complete picture."
        elif completion < 80:
            return "Welcome back! We're making excellent progress on your persona. Let's finish gathering the remaining insights."
        else:
            return "Welcome back! Your persona is nearly complete. Let's wrap up the final details and generate your comprehensive brand persona."
    
    async def _basic_conversational_processing(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """Basic conversational processing when persona agent is not available."""
        
        # Simple acknowledgment and follow-up
        if len(user_input.strip()) < 30:
            return {
                "status": "follow_up",
                "message": "That's interesting! Could you tell me more about that? I'd love to understand the details to build a comprehensive persona for you."
            }
        
        # Acknowledge and ask follow-up
        return {
            "status": "acknowledge_and_continue",
            "message": "Thank you for sharing that! That gives me valuable insight. What else would you like to tell me about your business and ideal clients?"
        }
    
    async def get_framework_progress(self, session_id: str) -> Dict[str, Any]:
        """Get detailed framework progress for the session."""
        if "persona_agent" in self.agents:
            return await self.agents["persona_agent"].get_framework_progress(session_id)
        else:
            return await self._get_framework_progress(session_id)
    
    async def _get_framework_progress(self, session_id: str) -> Dict[str, Any]:
        """Fallback framework progress when persona agent not available."""
        return {
            "overall_completion": 0.0,
            "sections_completed": 0,
            "total_sections": 6,
            "section_summaries": {},
            "next_focus": None
        }
    
    async def generate_persona_document(self, session_id: str) -> Dict[str, Any]:
        """Generate the final persona document."""
        if "persona_agent" in self.agents:
            return await self.agents["persona_agent"].generate_persona_document(session_id)
        else:
            return {"error": "Persona generation not available"}
    
    async def get_conversation_suggestions(self, session_id: str) -> List[str]:
        """Get conversation suggestions based on current progress."""
        if "persona_agent" in self.agents:
            return await self.agents["persona_agent"].get_conversation_suggestions(session_id)
        else:
            return [
                "Tell me about your expertise",
                "Who are your ideal clients?",
                "What makes you different?"
            ]
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive session status."""
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found"}
            
            framework_progress = await self.get_framework_progress(session_id)
            context_summary = await self.context_manager.get_context_summary(session_id)
            
            return {
                "session": session.dict(),
                "framework_progress": framework_progress,
                "context_summary": context_summary,
                "available_agents": list(self.agents.keys()),
                "llm_providers": self.llm_tool.get_available_providers(),
                "conversation_type": "persona_building"
            }
            
        except Exception as e:
            logger.error(f"Failed to get session status {session_id}: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on all components."""
        health = {
            "coordinator": "healthy",
            "session_manager": "healthy",
            "redis_context_manager": "healthy" if self.redis_context_manager._redis_connected else "disconnected",
            "llm_tool": {
                "status": "healthy",
                "providers": self.llm_tool.get_available_providers()
            },
            "agents": {name: "healthy" for name in self.agents.keys()},
            "database": "not_implemented" if not self.database else "healthy",
            "architecture": "conversational_persona_building_with_redis"
        }
        
        return health
    
    def _initialize_agents(self):
        """Initialize agents with proper dependencies."""
        try:
            # Use the modular LangGraph agent (the new one)
            from agents.modular_langgraph_persona_agent import ModularLangGraphPersonaAgent

            persona_agent = ModularLangGraphPersonaAgent(
                llm_tool=self.llm_tool,
                session_manager=self.session_manager,
                context_manager=self.redis_context_manager,
                database=self.database
            )

            self.register_agent("persona_agent", persona_agent)
            logger.info("✅ Modular LangGraph Persona agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize modular LangGraph persona agent: {e}")
            raise Exception("Unable to initialize persona agent")
