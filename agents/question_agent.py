"""
Question Agent for handling Q&A flow with intelligent assessment.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from agents.base.agent_interface import BaseAgent
from tools.assessment_tool import AssessmentTool
from database.models import QuestionResponse, QuestionStatus

logger = logging.getLogger(__name__)


class QuestionAgent(BaseAgent):
    """Agent responsible for question flow and answer assessment."""
    
    def __init__(self, llm_tool=None, session_manager=None, 
                 context_manager=None, database=None, **kwargs):
        """Initialize the Question Agent."""
        super().__init__(llm_tool, session_manager, context_manager, database, **kwargs)
        
        self.assessment_tool = AssessmentTool(llm_tool)
        self.questions = {}
        self.system_prompt = self._load_system_prompt()
        self._load_questions()
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt from text file."""
        try:
            prompt_path = Path(__file__).parent.parent / "prompts" / "question_agent_prompt.txt"
            with open(prompt_path, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            return "You are a helpful question agent for persona building."
    
    def _load_questions(self):
        """Load questions from knowledge base."""
        try:
            questions_path = Path(__file__).parent.parent / "knowledge" / "questions.json"
            with open(questions_path, 'r') as f:
                data = json.load(f)
            
            # Flatten questions into a dictionary
            for section in data.get("sections", []):
                for question in section.get("questions", []):
                    self.questions[question["id"]] = question
            
            logger.info(f"Loaded {len(self.questions)} questions")
        except Exception as e:
            logger.error(f"Failed to load questions: {e}")
            self.questions = {}
    
    async def process(self, session_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user input and determine next action.
        """
        start_time = time.time()
        user_input = input_data.get("user_input", "")
        current_question = input_data.get("current_question", 1)
        
        logger.info(f"🤖 QuestionAgent processing Q{current_question} for session {session_id}")
        logger.info(f"📝 User answer: '{user_input[:100]}...'")
        
        try:
            # Validate input
            if not user_input or not user_input.strip():
                return {"error": "Empty input provided"}
            if not isinstance(current_question, int) or current_question < 1:
                return {"error": "Invalid question ID"}
            
            # Get session to check follow-up state
            session = await self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found"}
            
            logger.info(f"📋 Session state: Q{session.current_question}, awaiting_follow_up={session.awaiting_follow_up}, attempts={session.follow_up_attempts}")
            
            # FAST PATH: If this is a follow-up response, handle it quickly
            if session.awaiting_follow_up and session.follow_up_attempts > 0:
                logger.info("🚀 FAST PATH: Processing follow-up response")
                return await self._handle_follow_up_response(session_id, user_input, session)
            
            # NORMAL PATH: First attempt at a question
            logger.info("🔄 NORMAL PATH: Processing initial question response")
            return await self._handle_initial_response(session_id, user_input, session)
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ Error after {total_time:.2f}s: {e}")
            return await self.handle_error(e, {"session_id": session_id, "input_data": input_data})
    
    async def _handle_follow_up(self, session_id: str, assessment: Dict[str, Any], 
                              question_id: int) -> Dict[str, Any]:
        """Handle case where follow-up is needed."""
        
        # Check if this is already a follow-up attempt
        session = await self.session_manager.get_session(session_id) if self.session_manager else None
        
        # For now, be more lenient and advance after 1 follow-up
        # Use the specific follow-up from rubrics if available
        follow_up_question = assessment.get("follow_up_question")
        
        if follow_up_question:
            # Use your specific rubric follow-up
            response = f"""
I want to make sure I get this right for your persona.

{follow_up_question}

The more specific you can be, the better I can tailor this to really resonate with your ideal clients.
            """.strip()
        else:
            # Fallback for questions without rubrics
            response = "Could you give me a bit more detail here? The more specific, the better!"
        
        # Add context message with follow-up metadata
        if self.context_manager:
            await self.context_manager.add_message(
                session_id, "assistant", response, question_id, 
                metadata={"type": "follow-up", "follow_up_attempt": True}
            )
        
        return {
            "status": "needs_follow_up",
            "message": response,
            "assessment": assessment,
            "question_id": question_id,
            "follow_up_attempt": True
        }
    
    async def _handle_question_complete(self, session_id: str, assessment: Dict[str, Any], 
                                      question_id: int) -> Dict[str, Any]:
        """Handle case where question is satisfactorily answered."""
        
        # Positive feedback based on score
        score = assessment.get("score", 5)
        
        if score >= 9:
            feedback = "Excellent! That's exactly the kind of specific detail that helps me create a powerful persona for you."
        elif score >= 7:
            feedback = "Great! That gives me good insight to work with."
        else:
            feedback = "Thanks for that - let's keep building this picture together."
        
        # Move to next question
        next_question = question_id + 1
        
        # Update session to advance question
        if self.session_manager:
            await self.session_manager.advance_question(session_id)
        
        if next_question <= len(self.questions):
            next_q_info = self.questions.get(next_question)
            if next_q_info:
                next_message = f"""
{feedback}

Question {next_question}/30 - {next_q_info['section']}

{next_q_info['text']}
                """.strip()
                
                # Add context message
                if self.context_manager:
                    await self.context_manager.add_assistant_message(
                        session_id, next_message, next_question
                    )
                
                return {
                    "status": "question_completed",
                    "message": next_message,
                    "assessment": assessment,
                    "completed_question": question_id,
                    "next_question": next_question,
                    "progress": f"{next_question-1}/30"
                }
        
        # All questions completed
        completion_message = f"""
{feedback}

🎉 Congratulations! You've completed all 30 questions. 

I'm now processing your responses to create your comprehensive marketing persona. This will include your strategic positioning, target audience psychology, brand voice, and conversion insights.

Your persona will be ready shortly!
        """.strip()
        
        if self.context_manager:
            await self.context_manager.add_assistant_message(
                session_id, completion_message
            )
        
        return {
            "status": "all_questions_completed",
            "message": completion_message,
            "assessment": assessment,
            "completed_question": question_id,
            "total_questions": len(self.questions)
        }
    
    async def get_question(self, question_id: int) -> Dict[str, Any]:
        """Get a specific question by ID."""
        if question_id in self.questions:
            question = self.questions[question_id]
            return {
                "id": question_id,
                "text": question["text"],
                "section": question["section"],
                "has_assessment_prompt": self.assessment_tool.has_assessment_prompt(question_id)
            }
        else:
            return {"error": f"Question {question_id} not found"}
    
    async def start_questions(self, session_id: str) -> Dict[str, Any]:
        """Start the question flow."""
        first_question = self.questions.get(1)
        if not first_question:
            return {"error": "No questions available"}
        
        message = f"""
Welcome! I'll guide you through 30 questions to build your comprehensive marketing persona.

Question 1/30 - {first_question['section']}

{first_question['text']}
        """.strip()
        
        if self.context_manager:
            await self.context_manager.add_assistant_message(
                session_id, message, 1
            )
        
        return {
            "status": "questions_started",
            "message": message,
            "current_question": 1,
            "total_questions": len(self.questions)
        }
    
    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "question_management",
            "answer_assessment", 
            "intelligent_follow_up",
            "progress_tracking"
        ]
    
    async def _handle_follow_up_response(self, session_id: str, user_input: str, session) -> Dict[str, Any]:
        """Handle follow-up response with fast processing (minimal LLM usage)."""
        
        # Quick quality check - if longer than 30 chars and has some specificity, accept it
        if len(user_input.strip()) >= 30:
            logger.info("✅ Follow-up response has good length - advancing")
            await self.session_manager.clear_follow_up_state(session_id)
            return await self._handle_question_complete(session_id, {
                "score": 7,
                "category": "good",
                "reasoning": "Follow-up response with sufficient detail",
                "needs_follow_up": False
            }, session.current_question)
        else:
            # Still too short, ask one more time but be more specific
            logger.info("⚠️ Follow-up still needs more detail")
            if session.follow_up_attempts >= 3:
                # Give up after 3 attempts and advance anyway
                logger.info("🔄 Max follow-up attempts reached, advancing anyway")
                await self.session_manager.clear_follow_up_state(session_id)
                return await self._handle_question_complete(session_id, {
                    "score": 6,
                    "category": "acceptable",
                    "reasoning": "Max follow-up attempts reached",
                    "needs_follow_up": False
                }, session.current_question)
            else:
                # Ask for more detail
                await self.session_manager.set_follow_up_needed(session_id)
                response = f"I'd love to get a bit more detail here to create the best persona for you. Can you expand on that?"
                
                if self.context_manager:
                    await self.context_manager.add_message(
                        session_id, "assistant", response, session.current_question,
                        metadata={"type": "follow-up", "attempt": session.follow_up_attempts + 1}
                    )
                
                return {
                    "status": "needs_follow_up",
                    "message": response,
                    "question_id": session.current_question,
                    "follow_up_attempt": session.follow_up_attempts + 1
                }
    
    async def _handle_initial_response(self, session_id: str, user_input: str, session) -> Dict[str, Any]:
        """Handle initial response to a question (streamlined LLM assessment)."""
        
        # Get question info
        if session.current_question not in self.questions:
            logger.error(f"❌ Question {session.current_question} not found")
            return {"error": f"Question {session.current_question} not found"}
        
        question_info = self.questions[session.current_question]
        logger.info(f"📋 Processing: {question_info['text'][:50]}...")
        
        # Use streamlined LLM-based assessment (no context injection)
        assessment_start = time.time()
        assessment = await self.assessment_tool.assess_answer(
            session.current_question, user_input, "question_agent", {}, session_id
        )
        assessment_time = time.time() - assessment_start
        logger.info(f"✅ Assessment: {assessment_time:.2f}s - Score: {assessment.get('score')}")
        
        # Determine next action
        if assessment.get("needs_follow_up", False):
            logger.info("🔄 Needs follow-up")
            await self.session_manager.set_follow_up_needed(session_id)
            result = await self._handle_follow_up(session_id, assessment, session.current_question)
        else:
            logger.info("✅ Advancing to next question")
            result = await self._handle_question_complete(session_id, assessment, session.current_question)
        
        return result
