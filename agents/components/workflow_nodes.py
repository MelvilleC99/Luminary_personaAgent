"""
Workflow nodes for LangGraph Persona Agent.
Each node handles a specific part of the conversation workflow.
"""

import logging
import json
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage
import instructor

from .models import PersonaConversationState, UserIntent, ConversationResponse, ExtractionItem
from .section_flow_manager import SectionFlowManager
from database.models import FrameworkExtraction

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """Collection of workflow nodes for the persona agent."""
    
    def __init__(self, llm_tool, framework_criteria):
        self.llm_tool = llm_tool
        self.framework_criteria = framework_criteria
        
        # Initialize section flow manager
        self.section_flow_manager = SectionFlowManager(framework_criteria)
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        # Initialize instructor client for structured responses
        try:
            # Create instructor client with OpenAI API key
            if self.llm_tool and 'openai' in self.llm_tool.providers:
                openai_provider = self.llm_tool.providers['openai']
                if hasattr(openai_provider, 'api_key'):
                    import openai
                    openai_client = openai.AsyncOpenAI(api_key=openai_provider.api_key)
                    self.instructor_client = instructor.from_openai(openai_client)
                else:
                    self.instructor_client = None
            else:
                self.instructor_client = None
        except Exception as e:
            logger.warning(f"Could not initialize instructor client: {e}")
            self.instructor_client = None
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt from file."""
        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "persona_agent_prompt.txt"
            
            if prompt_path.exists():
                with open(prompt_path, 'r') as f:
                    system_prompt = f.read().strip()
                logger.info(f"✅ Loaded system prompt ({len(system_prompt)} characters)")
                return system_prompt
            else:
                logger.error(f"❌ System prompt file not found: {prompt_path}")
                return self._get_fallback_system_prompt()
        except Exception as e:
            logger.error(f"❌ Failed to load system prompt: {e}")
            return self._get_fallback_system_prompt()
    
    def _get_fallback_system_prompt(self) -> str:
        """Fallback system prompt if file can't be loaded."""
        return """You are Paul, an expert brand strategist conducting a comprehensive persona interview through natural, flowing conversation.

Your mission is to extract comprehensive brand persona information across 6 framework sections through intelligent conversation, not rigid questionnaires.

Be conversational, acknowledge what they share, build on their insights, and ask intelligent follow-up questions that show you understand their business."""
    
    def _build_framework_context(self, current_section: int) -> str:
        """Build framework context for the current section."""
        try:
            if not self.framework_criteria:
                return ""
            
            # Get current section info
            section_keys = list(self.framework_criteria.keys())
            if current_section <= 0 or current_section > len(section_keys):
                return ""
            
            section_key = section_keys[current_section - 1]
            section_data = self.framework_criteria[section_key]
            
            # Build context
            context_parts = [
                f"CURRENT SECTION: {section_data.get('section_name', section_key)}",
                f"SECTION DESCRIPTION: {section_data.get('description', '')}",
                "",
                "CRITERIA TO GATHER IN THIS SECTION:"
            ]
            
            # Add criteria details
            criteria = section_data.get('criteria', {})
            for criteria_key, criteria_info in criteria.items():
                context_parts.append(f"- {criteria_key}: {criteria_info.get('description', '')}")
                
                # Add example questions
                if 'question' in criteria_info:
                    context_parts.append(f"  Example question: {criteria_info['question']}")
                
                # Add good/bad examples
                if 'examples' in criteria_info:
                    examples = criteria_info['examples']
                    if 'good' in examples:
                        context_parts.append(f"  Good answers: {', '.join(examples['good'][:3])}")
                    if 'bad' in examples:
                        context_parts.append(f"  Avoid answers like: {', '.join(examples['bad'][:3])}")
                
                context_parts.append("")  # Empty line between criteria
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to build framework context: {e}")
            return ""
    
    async def analyze_user_input(self, state: PersonaConversationState) -> PersonaConversationState:
        """Analyze user input to determine intent and extract topics."""
        try:
            user_message = state["messages"][-1].content if state["messages"] else ""
            
            # Simple intent analysis without LLM dependency
            intent = self._analyze_intent_simple(user_message)
            state["user_intent"] = intent
            
            logger.info(f"User intent analyzed: {intent}")
            return state
            
        except Exception as e:
            logger.error(f"Error in analyze_user_input: {e}")
            state["user_intent"] = "answering"  # Default intent
            return state
    
    def _analyze_intent_simple(self, message: str) -> str:
        """Simple intent analysis without LLM."""
        message_lower = message.lower().strip()
        
        # Check for questions
        question_words = ["what", "how", "why", "when", "where", "who", "which", "?"]
        if any(word in message_lower for word in question_words):
            return "questioning"
        
        # Check for greetings
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon"]
        if any(greeting in message_lower for greeting in greetings):
            return "greeting"
        
        # Check for ready signals
        ready_words = ["ready", "let's start", "begin", "go", "yes", "sure", "okay"]
        if any(word in message_lower for word in ready_words):
            return "ready_to_start"
        
        # Default to answering
        return "answering"
    

    
    async def extract_and_respond(self, state: PersonaConversationState) -> PersonaConversationState:
        """Main extraction and response generation node with proper LLM guidance."""
        try:
            # Get conversation state manager
            completion_manager = state.get("conversation_state_manager")
            session_id = state["session_id"]
            user_message = state["messages"][-1].content if state["messages"] else ""
            
            # Get current section
            if completion_manager:
                conversation_state = await completion_manager.get_conversation_state(session_id)
                current_section = conversation_state.current_section
            else:
                current_section = 1  # Default to first section
            
            # Build framework context for current section
            framework_context = self._build_framework_context(current_section)
            
            # Get conversation history
            context_manager = state.get("context_manager")
            conversation_history = ""
            if context_manager:
                conversation_history, _ = await context_manager.get_context_for_llm(session_id)
            
            # Build comprehensive prompt for LLM
            llm_prompt = f"""{self.system_prompt}

{framework_context}

CONVERSATION HISTORY:
{conversation_history}

USER'S LATEST MESSAGE: {user_message}

INSTRUCTIONS:
- You are currently in Section {current_section}
- Focus on gathering the criteria listed above for this section
- Be conversational and natural - don't sound like you're reading from a script
- Acknowledge what they shared and build on it
- Ask intelligent follow-up questions
- If they've provided good information, confirm your understanding and transition naturally
- If information is surface-level, dig deeper with specific questions

Generate your response as Paul, the expert brand strategist."""
            
            # Call LLM with proper guidance
            if self.llm_tool:
                try:
                    ai_response = await self.llm_tool.generate_for_agent(
                        agent_name="persona_agent",
                        prompt=llm_prompt,
                        session_id=session_id,
                        max_tokens=400,
                        temperature=0.7
                    )
                    
                    logger.info(f"✅ LLM response generated for section {current_section}")
                    
                except Exception as e:
                    logger.error(f"❌ LLM generation failed: {e}")
                    ai_response = await self._fallback_section_response_content(current_section, user_message)
            else:
                logger.warning("No LLM tool available, using fallback")
                ai_response = await self._fallback_section_response_content(current_section, user_message)
            
            # Add AI response to messages
            state["messages"].append(AIMessage(content=ai_response))
            
            # Update completion percentage based on section
            overall_progress = min((current_section / self.section_flow_manager.total_sections) * 100, 100)
            state["completion_percentage"] = overall_progress
            
            logger.info(f"Generated response for section {current_section}, progress: {overall_progress:.1f}%")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in extract_and_respond: {e}")
            return await self._fallback_section_response(state)
    
    async def _fallback_section_response_content(self, current_section: int, user_message: str) -> str:
        """Generate fallback response content."""
        try:
            # Use section flow manager for intelligent fallback
            if len(user_message.strip()) < 30:
                follow_up = self.section_flow_manager.get_follow_up_question(current_section, user_message)
                return follow_up or "Could you tell me more about that? I'd love to understand the details better."
            else:
                # Ask next logical question from current section
                next_question = self.section_flow_manager.get_next_question(current_section, [])
                return next_question or "That's interesting! What else can you tell me about this area?"
                
        except Exception as e:
            logger.error(f"Error in fallback content generation: {e}")
            return "I'd love to learn more about your expertise. Could you tell me more about that?"
    
    async def _fallback_section_response(self, state: PersonaConversationState) -> PersonaConversationState:
        """Fallback response when managers are not available."""
        try:
            user_message = state["messages"][-1].content if state["messages"] else ""
            
            # Simple fallback logic
            if len(user_message.strip()) < 30:
                ai_response = "Could you tell me more about that? I'd love to understand the details better."
            else:
                # Ask next logical question from section 1
                next_question = self.section_flow_manager.get_next_question(1, [])
                ai_response = next_question or "That's interesting! What else can you tell me about your expertise?"
            
            state["messages"].append(AIMessage(content=ai_response))
            return state
            
        except Exception as e:
            logger.error(f"Error in fallback response: {e}")
            # Ultimate fallback
            state["messages"].append(AIMessage(content="I'd love to learn more about your expertise. What's your area of specialization?"))
            return state
    
    async def check_completion(self, state: PersonaConversationState) -> PersonaConversationState:
        """Check if conversation is complete or should continue."""
        try:
            completion_manager = state.get("conversation_state_manager")
            if completion_manager:
                conversation_state = await completion_manager.get_conversation_state(state["session_id"])
                overall_completion = await completion_manager.get_overall_completion(state["session_id"])
                
                if overall_completion > 0:
                    state["completion_percentage"] = overall_completion
            
            # Determine conversation stage based on completion
            current_completion = state.get("completion_percentage", 0)
            if current_completion >= 90:
                state["conversation_stage"] = "completion"
            elif current_completion >= 70:
                state["conversation_stage"] = "follow_up"
            else:
                state["conversation_stage"] = "gathering"
            
            logger.info(f"Completion check: {current_completion:.1f}% - Stage: {state['conversation_stage']}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in check_completion: {e}")
            return state
    
    async def wrap_up_conversation(self, state: PersonaConversationState) -> PersonaConversationState:
        """Wrap up the conversation with final summary."""
        try:
            wrap_up_message = """Perfect! I've gathered comprehensive information about your business and expertise. 

Your persona document will include:
• Your core expertise and ideal customer profile
• Brand personality and unique positioning  
• Communication style and voice
• Content strategy and audience insights
• Long-term vision and success metrics

This persona will help guide your marketing, content creation, and client attraction efforts. Thank you for the detailed conversation!"""
            
            state["messages"].append(AIMessage(content=wrap_up_message))
            state["conversation_stage"] = "completed"
            
            logger.info("Conversation wrapped up successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error in wrap_up_conversation: {e}")
            return state
