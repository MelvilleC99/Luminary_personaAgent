"""
Main Coordinator - Orchestrates all agents and manages the persona building workflow.
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from memory.session_manager import SessionManager
from memory.context_manager import ContextManager
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
        
        # Initialize core components
        self.session_manager = SessionManager(database)
        self.context_manager = ContextManager(database)
        
        # Initialize LLM tool with multi-provider support and database
        self.llm_tool = LLMTool(
            api_keys=settings.api_keys,
            llm_assignments=settings.llm_config,
            database=database
        )
        
        # Agent registry - will be populated as agents are initialized
        self.agents = {}
        
        # Initialize Question Agent
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
            
            # Add welcome system message
            await self.context_manager.add_system_message(
                session.id,
                "Welcome to the Luminary Persona Agent! I'll guide you through 30 questions to build your comprehensive marketing persona."
            )
            
            # Get first question using Question Agent
            if "question_agent" in self.agents:
                response = await self.agents["question_agent"].start_questions(session.id)
            else:
                # Fallback to basic question handling
                response = await self.get_next_question(session.id)
            
            logger.info(f"Started new session: {session.id}")
            
            return {
                "session_id": session.id,
                "status": "started",
                "message": response["message"],
                "question": response.get("question"),
                "progress": await self.session_manager.get_session_progress(session.id)
            }
            
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def resume_session(self, session_id: str) -> Dict[str, Any]:
        """
        Resume an existing session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session status and next action
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
                    "message": "Your persona building session is complete!",
                    "progress": await self.session_manager.get_session_progress(session_id)
                }
            
            # Get next question or current status using Question Agent
            if "question_agent" in self.agents:
                # Get the current question
                question_data = await self.agents["question_agent"].get_question(session.current_question)
                if "error" not in question_data:
                    message = f"Let's continue with Question {session.current_question}/30 - {question_data['section']}\n\n{question_data['text']}"
                    response = {"message": message, "question": question_data}
                else:
                    response = await self.get_next_question(session_id)
            else:
                response = await self.get_next_question(session_id)
            
            return {
                "session_id": session_id,
                "status": "resumed",
                "message": response["message"],
                "question": response.get("question"),
                "progress": await self.session_manager.get_session_progress(session_id)
            }
            
        except Exception as e:
            logger.error(f"Failed to resume session {session_id}: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def process_user_input(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        Process user input and coordinate the appropriate response.
        
        Args:
            session_id: Session identifier
            user_input: User's input/answer
            
        Returns:
            Response from the appropriate agent
        """
        start_time = time.time()
        logger.info(f"🎯 Processing input for session {session_id}: '{user_input[:50]}...'")
        
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found", "status": "not_found"}
            
            logger.info(f"📋 Session found - Current question: {session.current_question}")
            
            # Add user message to context
            await self.context_manager.add_user_message(
                session_id, user_input, session.current_question
            )
            logger.info("💬 Added user message to context")
            
            # Route to question agent for processing
            if "question_agent" in self.agents:
                logger.info("🤖 Routing to question agent...")
                agent_start = time.time()
                
                response = await self.agents["question_agent"].process(
                    session_id, {
                        "user_input": user_input,
                        "current_question": session.current_question
                    }
                )
                
                agent_time = time.time() - agent_start
                logger.info(f"✅ Question agent completed in {agent_time:.2f}s")
                
            else:
                logger.warning("⚠️ Question agent not available, using fallback")
                # Fallback basic processing if question agent not available
                response = await self._basic_question_processing(session_id, user_input)
            
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
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive session status.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Complete session status
        """
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found"}
            
            progress = await self.session_manager.get_session_progress(session_id)
            context_summary = await self.context_manager.get_context_summary(session_id)
            
            return {
                "session": session.dict(),
                "progress": progress,
                "context_summary": context_summary,
                "available_agents": list(self.agents.keys()),
                "llm_providers": self.llm_tool.get_available_providers()
            }
            
        except Exception as e:
            logger.error(f"Failed to get session status {session_id}: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on all components.
        
        Returns:
            Health status of all components
        """
        health = {
            "coordinator": "healthy",
            "session_manager": "healthy",
            "context_manager": "healthy",
            "llm_tool": {
                "status": "healthy",
                "providers": self.llm_tool.get_available_providers()
            },
            "agents": {name: "healthy" for name in self.agents.keys()},
            "database": "not_implemented" if not self.database else "healthy"
        }
        
        return health
    
    def _initialize_agents(self):
        """Initialize agents with proper dependencies."""
        try:
            from agents.question_agent import QuestionAgent
            
            question_agent = QuestionAgent(
                llm_tool=self.llm_tool,
                session_manager=self.session_manager,
                context_manager=self.context_manager,
                database=self.database
            )
            
            self.register_agent("question_agent", question_agent)
            logger.info("Question agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
