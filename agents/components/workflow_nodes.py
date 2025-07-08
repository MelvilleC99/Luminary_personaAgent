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
from database.models import FrameworkExtraction

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """Collection of workflow nodes for the persona agent."""
    
    def __init__(self, llm_tool, framework_criteria):
        self.llm_tool = llm_tool
        self.framework_criteria = framework_criteria
        
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
    
    async def analyze_user_input(self, state: PersonaConversationState) -> PersonaConversationState:
        """Analyze user input to determine intent and extract topics."""
        try:
            user_message = state["messages"][-1].content if state["messages"] else ""
            
            # Get conversation context
            context_manager = state.get("enhanced_context_manager")
            if context_manager:
                context, token_count = await context_manager.get_context_for_llm(state["session_id"])
                state["token_usage"]["context_tokens"] = token_count
            
            # Analyze user intent
            intent_prompt = f"""
            Analyze the user's message and determine their intent.
            
            User message: "{user_message}"
            
            Determine:
            1. What type of intent this represents
            2. Any specific question content if they're asking something
            3. Topics mentioned that relate to business/expertise
            """
            
            try:
                if self.instructor_client:
                    intent = await self._get_structured_response(intent_prompt, UserIntent)
                else:
                    intent_response = await self.llm_tool.generate_for_agent(
                        agent_name="persona_agent",
                        prompt=intent_prompt,
                        session_id=state["session_id"],
                        max_tokens=300,
                        temperature=0.1
                    )
                    intent = self._parse_json_response(intent_response, UserIntent)
                
                state["user_intent"] = intent.intent_type
                logger.info(f"Analyzed input - Intent: {intent.intent_type}, Topics: {intent.topics_mentioned}")
                
            except Exception as e:
                logger.warning(f"Intent analysis failed: {e}")
                state["user_intent"] = "answering"  # Default fallback
            
            return state
            
        except Exception as e:
            logger.error(f"Error in analyze_user_input: {e}")
            state["user_intent"] = "answering"
            return state
    
    async def answer_user_question(self, state: PersonaConversationState
) -> PersonaConversationState:
        """Handle user questions before proceeding with extraction."""
        try:
            user_message = state["messages"][-1].content if state["messages"] else ""
            business_context = state.get("business_context", {})
            
            # Build context for answering questions
            answer_prompt = f"""
            The user has asked a question. Answer it helpfully and then guide back to persona building.
            
            User question: "{user_message}"
            
            Business context so far: {json.dumps(business_context, indent=2)}
            
            Provide a helpful answer and then smoothly transition back to gathering persona information.
            Be direct and conversational, avoid excessive fluff.
            """
            
            response = await self.llm_tool.generate_for_agent(
                agent_name="persona_agent",
                prompt=answer_prompt,
                session_id=state["session_id"],
                max_tokens=400,
                temperature=0.3
            )
            
            # Add response to messages
            state["messages"].append(AIMessage(content=response))
            logger.info("Agent answered the specific question!")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in answer_user_question: {e}")
            return state
    
    async def extract_and_respond(self, state: PersonaConversationState) -> PersonaConversationState:
        """Main extraction and response generation node."""
        try:
            # Get section completion context
            completion_manager = state.get("section_completion_manager")
            if not completion_manager:
                logger.error("No section completion manager available")
                return state
            
            conversation_state = await completion_manager.get_conversation_state(state["session_id"])
            section_context = completion_manager.build_context_for_llm(conversation_state)
            
            # Get enhanced conversation context
            context_manager = state.get("enhanced_context_manager")
            conversation_context = ""
            if context_manager:
                conversation_context, _ = await context_manager.get_context_for_llm(
                    state["session_id"], 
                    include_system_context=section_context
                )
            
            # Build extraction prompt
            extraction_prompt = f"""
            {section_context}
            
            CONVERSATION HISTORY:
            {conversation_context}
            
            CRITICAL INSTRUCTIONS:
            The user just provided NEW information in their latest message. You MUST:
            1. ACKNOWLEDGE what they specifically just told you (don't ignore their response)
            2. BUILD UPON their previous responses - never repeat the same question
            3. SHOW you understand their business/expertise area they mentioned
            4. EXTRACT any framework criteria from their response
            5. Ask the NEXT logical question that builds on what they've shared
            
            NEVER repeat questions. ALWAYS progress the conversation forward by building on what they've told you.
            
            Your response should:
            - Start by acknowledging their specific input ("Great! I see you work with...")
            - Extract relevant framework information with confidence scores (0.0-1.0)
            - Ask a natural follow-up question that digs deeper into their expertise
            - Reference what they've already shared to show continuity
            
            RESPOND WITH JSON containing extracted information AND a conversational response that builds on their input.
            """
            
            try:
                if self.instructor_client:
                    response = await self._get_structured_response(extraction_prompt, ConversationResponse)
                else:
                    response_text = await self.llm_tool.generate_for_agent(
                        agent_name="persona_agent",
                        prompt=extraction_prompt,
                        session_id=state["session_id"],
                        max_tokens=800,
                        temperature=0.4
                    )
                    logger.info(f"LLM raw response: {response_text[:200]}...")
                    response = self._parse_json_response(response_text, ConversationResponse)
                    logger.info(f"Parsed response message: {response.message[:100]}...")
                
                # Process extractions
                if response.extractions:
                    framework_extractions = []
                    for extraction in response.extractions:
                        framework_extractions.append(FrameworkExtraction(
                            session_id=state["session_id"],
                            framework_section=extraction.framework_section,
                            criteria_key=extraction.criteria_key,
                            extracted_value=extraction.extracted_value,
                            confidence_score=extraction.confidence_score,
                            reasoning=extraction.reasoning
                        ))
                    
                    # Update section progress
                    updated_state = await completion_manager.update_extractions(
                        state["session_id"], 
                        framework_extractions
                    )
                    
                    # Update completion percentage
                    state["completion_percentage"] = completion_manager._calculate_overall_completion(updated_state)
                    
                    logger.info(f"Extracted {len(response.extractions)} items, completion: {state['completion_percentage']:.1f}%")
                
                # Add response to messages
                state["messages"].append(AIMessage(content=response.message))
                state["current_focus"] = response.next_focus_area
                state["conversation_stage"] = response.conversation_stage
                
                return state
                
            except Exception as e:
                logger.error(f"Structured extraction failed: {e}")
                # Fallback to basic response
                fallback_response = await self._generate_fallback_response(state)
                state["messages"].append(AIMessage(content=fallback_response))
                return state
            
        except Exception as e:
            logger.error(f"Error in extract_and_respond: {e}")
            return state
    
    async def check_completion(self, state: PersonaConversationState) -> PersonaConversationState:
        """Check if conversation is complete or should continue."""
        try:
            completion_manager = state.get("section_completion_manager")
            if not completion_manager:
                return state
            
            # Check section completion
            is_complete, status = await completion_manager.check_section_completion(state["session_id"])
            
            # Only update completion percentage if we got a valid result
            overall_completion = status.get("overall_completion", 0)
            if overall_completion > 0:
                state["completion_percentage"] = overall_completion
            
            # Determine conversation stage
            current_completion = state.get("completion_percentage", 0)
            if current_completion >= 80:
                state["conversation_stage"] = "completion"
            elif len(status.get("missing_criteria", [])) <= 2:
                state["conversation_stage"] = "follow_up"
            else:
                state["conversation_stage"] = "gathering"
            
            # Add aggressive loop protection to prevent infinite loops
            loop_count = state.get("loop_count", 0) + 1
            state["loop_count"] = loop_count
            
            if loop_count >= 3:  # Prevent infinite loops aggressively
                logger.warning(f"Loop protection activated after {loop_count} iterations - forcing completion")
                state["conversation_stage"] = "completion"
            
            logger.info(f"Completion check: {current_completion:.1f}% complete, stage: {state['conversation_stage']}, loop: {loop_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error in check_completion: {e}")
            return state
    
    async def wrap_up_conversation(self, state: PersonaConversationState) -> PersonaConversationState:
        """Generate completion message and offer persona generation."""
        try:
            wrap_up_message = """
            Excellent! We've gathered comprehensive information about your expertise and brand. 
            I now have enough detail to generate your complete persona profile.
            
            Would you like me to generate your detailed marketing persona based on our conversation?
            """
            
            state["messages"].append(AIMessage(content=wrap_up_message))
            state["conversation_stage"] = "completion"
            
            logger.info("Conversation wrapped up successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error in wrap_up_conversation: {e}")
            return state
    
    async def _get_structured_response(self, prompt: str, response_model):
        """Get structured response using instructor."""
        try:
            response = await self.instructor_client.chat.completions.create(
                model="gpt-4o",
                response_model=response_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3
            )
            return response
        except Exception as e:
            logger.error(f"Instructor request failed: {e}")
            raise
    
    def _parse_json_response(self, response_text: str, model_class):
        """Parse JSON response from LLM."""
        try:
            # Extract JSON from response
            if "```json" in response_text:
                json_part = response_text.split("```json")[1].split("```")[0].strip()
            else:
                json_part = response_text.strip()
            
            # Parse JSON
            data = json.loads(json_part)
            return model_class(**data)
            
        except Exception as e:
            logger.error(f"JSON parsing failed: {e}")
            # Return default instance
            if model_class == UserIntent:
                return UserIntent(intent_type="answering", topics_mentioned=[])
            elif model_class == ConversationResponse:
                return ConversationResponse(
                    message="I'd like to learn more about your expertise. Can you tell me about your area of specialization?",
                    extractions=[],
                    conversation_stage="gathering"
                )
            else:
                raise
    
    async def _generate_fallback_response(self, state: PersonaConversationState) -> str:
        """Generate fallback response when structured extraction fails."""
        try:
            fallback_prompt = f"""
            Continue the persona building conversation. Ask a natural follow-up question 
            to gather more information about the user's expertise and business.
            
            Recent context: {state.get('business_context', {})}
            
            Be conversational and direct, minimal fluff.
            """
            
            response = await self.llm_tool.generate_for_agent(
                agent_name="persona_agent",
                prompt=fallback_prompt,
                session_id=state["session_id"],
                max_tokens=200,
                temperature=0.4
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Fallback response generation failed: {e}")
            return "Can you tell me more about your area of expertise?"
