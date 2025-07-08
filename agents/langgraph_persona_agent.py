"""
LangGraph-based Persona Agent with full context awareness.
Replaces the fragmented tool chain with unified state management.
"""

import logging
from typing import Dict, Any, List, Optional, TypedDict, Literal
from datetime import datetime
import json
import yaml
from pathlib import Path

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Pydantic models for structured LLM responses
class ExtractionItem(BaseModel):
    framework_section: str
    criteria_key: str
    extracted_value: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str

class UserIntent(BaseModel):
    intent_type: Literal["answering", "questioning", "clarifying", "ready_to_start", "greeting"]
    question_content: Optional[str] = None
    topics_mentioned: List[str] = Field(default_factory=list)

class ConversationResponse(BaseModel):
    message: str
    user_intent: Optional[UserIntent] = None
    extractions: List[ExtractionItem] = Field(default_factory=list)
    next_focus_area: Optional[str] = None
    conversation_stage: Literal["opening", "gathering", "follow_up", "completion"] = "gathering"

# LangGraph State Definition
class PersonaConversationState(TypedDict):
    messages: List[BaseMessage]
    business_context: Dict[str, Any]
    framework_extractions: Dict[str, Dict[str, Any]]
    current_focus: Optional[str]
    user_intent: Optional[str]
    conversation_stage: str
    session_id: str
    completion_percentage: float
    token_usage: Dict[str, int]
    framework_progress: Dict[str, Dict[str, Any]]


class LangGraphPersonaAgent:
    """
    LangGraph-powered persona agent with full conversation context awareness.
    """
    
    def __init__(self, llm_tool=None, session_manager=None, 
                 context_manager=None, database=None, **kwargs):
        """Initialize the LangGraph persona agent."""
        self.llm_tool = llm_tool
        self.session_manager = session_manager
        self.context_manager = context_manager
        self.database = database
        
        # Load framework criteria
        self.framework_criteria = self._load_framework_criteria()
        
        # Build the conversation workflow
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        
        logger.info("LangGraph Persona Agent initialized")
    
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
        
        # Add nodes
        workflow.add_node("analyze_input", self._analyze_user_input)
        workflow.add_node("answer_question", self._answer_user_question)
        workflow.add_node("extract_and_respond", self._extract_and_respond)
        workflow.add_node("check_completion", self._check_completion)
        workflow.add_node("wrap_up", self._wrap_up_conversation)
        
        # Add edges with conditional routing
        workflow.set_entry_point("analyze_input")
        
        workflow.add_conditional_edges(
            "analyze_input",
            self._route_conversation,
            {
                "answer_question": "answer_question",
                "extract_info": "extract_and_respond",
                "check_completion": "check_completion",
                "wrap_up": "wrap_up"
            }
        )
        
        workflow.add_edge("answer_question", "extract_and_respond")
        workflow.add_edge("extract_and_respond", "check_completion")
        
        workflow.add_conditional_edges(
            "check_completion",
            self._completion_router,
            {
                "continue": END,
                "wrap_up": "wrap_up"
            }
        )
        
        workflow.add_edge("wrap_up", END)
        
        return workflow
    
    async def _analyze_user_input(self, state: PersonaConversationState) -> PersonaConversationState:
        """Analyze user input to understand intent and extract topics."""
        try:
            user_message = state["messages"][-1].content
            conversation_context = self._format_conversation_context(state)
            
            analysis_prompt = f"""
You are analyzing user input in a brand persona building conversation.

CONVERSATION CONTEXT:
{conversation_context}

FRAMEWORK GOAL:
Extract information across 6 persona sections: Core Expertise, Brand Personality, Positioning, Voice/Style, Content Goals, Vision.

USER'S LATEST MESSAGE: "{user_message}"

Analyze the user's intent and extract key topics mentioned.

RESPOND WITH JSON:
{{
    "intent_type": "answering|questioning|clarifying|ready_to_start|greeting",
    "question_content": "exact question if user asked one",
    "topics_mentioned": ["list", "of", "business", "topics", "mentioned"]
}}
"""
            
            # Get structured response from LLM
            response = await self.llm_tool.generate_for_agent(
                "persona_agent",
                analysis_prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            # Parse the response
            try:
                # Clean the response - remove markdown code blocks
                response_clean = response.strip()
                if response_clean.startswith('```json'):
                    response_clean = response_clean.replace('```json', '').replace('```', '').strip()
                elif response_clean.startswith('```'):
                    response_clean = response_clean.replace('```', '').strip()
                
                analysis_data = json.loads(response_clean)
                user_intent = UserIntent(**analysis_data)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse analysis response: {e}")
                logger.warning(f"Raw response was: {response}")
                # Fallback analysis
                user_intent = self._fallback_intent_analysis(user_message)
            
            # Update state
            state["user_intent"] = user_intent.intent_type
            
            # Update business context with new topics
            for topic in user_intent.topics_mentioned:
                if "expertise_areas" not in state["business_context"]:
                    state["business_context"]["expertise_areas"] = []
                if topic not in state["business_context"]["expertise_areas"]:
                    state["business_context"]["expertise_areas"].append(topic)
            
            logger.info(f"Analyzed input - Intent: {user_intent.intent_type}, Topics: {user_intent.topics_mentioned}")
            return state
            
        except Exception as e:
            logger.error(f"Error in analyze_user_input: {e}")
            state["user_intent"] = "answering"  # Safe fallback
            return state
    
    def _fallback_intent_analysis(self, user_message: str) -> UserIntent:
        """Simple fallback for intent analysis."""
        user_lower = user_message.lower()
        
        # Check for questions
        question_indicators = ["what", "how", "why", "when", "where", "?"]
        if any(indicator in user_lower for indicator in question_indicators):
            return UserIntent(
                intent_type="questioning",
                question_content=user_message,
                topics_mentioned=[]
            )
        
        # Check for ready indicators
        ready_indicators = ["ready", "yes", "sure", "okay", "let's go", "start"]
        if any(indicator in user_lower for indicator in ready_indicators):
            return UserIntent(
                intent_type="ready_to_start",
                topics_mentioned=[]
            )
        
        # Default to answering
        return UserIntent(
            intent_type="answering",
            topics_mentioned=[]
        )
    
    def _route_conversation(self, state: PersonaConversationState) -> str:
        """Route conversation based on user intent and current state."""
        user_intent = state.get("user_intent", "answering")
        completion = state.get("completion_percentage", 0.0)
        
        # If user is asking a question, answer it first
        if user_intent == "questioning":
            return "answer_question"
        
        # If completion is high, consider wrapping up
        if completion >= 85.0:
            return "check_completion"
        
        # Default: extract information and respond
        return "extract_info"
    
    async def _answer_user_question(self, state: PersonaConversationState) -> PersonaConversationState:
        """Answer user's question using business context."""
        try:
            user_message = state["messages"][-1].content
            business_context = state["business_context"]
            conversation_context = self._format_conversation_context(state)
            
            answer_prompt = f"""
You are an expert brand strategist helping build a persona. The user just asked a question.

CONVERSATION CONTEXT:
{conversation_context}

BUSINESS CONTEXT WE KNOW:
{json.dumps(business_context, indent=2)}

USER'S QUESTION: "{user_message}"

Provide a helpful, specific answer to their question using the business context we've gathered. Be conversational and knowledgeable.

After answering their question, you'll naturally transition to continuing the persona building process.

RESPOND WITH JUST YOUR ANSWER - NO EXTRA FORMATTING.
"""
            
            answer = await self.llm_tool.generate_for_agent(
                "persona_agent",
                answer_prompt,
                temperature=0.3,
                max_tokens=400
            )
            
            # Add the answer to messages
            state["messages"].append(AIMessage(content=answer.strip()))
            
            logger.info(f"Answered user question about: {user_message[:50]}...")
            return state
            
        except Exception as e:
            logger.error(f"Error answering user question: {e}")
            # Add a generic helpful response
            state["messages"].append(AIMessage(content="That's a great question! Let me continue gathering information to give you the most comprehensive persona possible."))
            return state
    
    async def _extract_and_respond(self, state: PersonaConversationState) -> PersonaConversationState:
        """Extract framework information and generate contextual response."""
        try:
            user_message = state["messages"][-1].content if isinstance(state["messages"][-1], HumanMessage) else state["messages"][-2].content
            business_context = state["business_context"]
            current_extractions = state["framework_extractions"]
            conversation_context = self._format_conversation_context(state)
            
            # Create comprehensive prompt for extraction and response
            extraction_prompt = f"""
You are an expert brand strategist conducting a persona interview. 

CONVERSATION CONTEXT:
{conversation_context}

BUSINESS CONTEXT:
{json.dumps(business_context, indent=2)}

FRAMEWORK CRITERIA (Extract information for these areas):
{self._get_framework_summary()}

CURRENT EXTRACTIONS:
{json.dumps(current_extractions, indent=2)}

USER'S RESPONSE: "{user_message}"

TASKS:
1. Extract any framework information from their response
2. Generate a natural, conversational response that:
   - Uses varied, natural language (NEVER use "Thank you for sharing that!")
   - Acknowledges what they shared with genuine interest and varied phrasing
   - Shows understanding of their business context
   - Asks a relevant follow-up question for missing framework areas
   - Feels like talking to an expert consultant, not a form

VARIED ACKNOWLEDGMENT EXAMPLES:
- "That's fascinating..."
- "I can see why that would be valuable..."
- "It sounds like you've found your niche..."
- "That's a crucial area..."
- "Perfect! That gives me insight into..."

RESPOND WITH JSON:
{{
    "message": "Your conversational response",
    "extractions": [
        {{
            "framework_section": "section_name",
            "criteria_key": "criteria_key", 
            "extracted_value": "what they said about this",
            "confidence_score": 0.8,
            "reasoning": "why this extraction was made"
        }}
    ],
    "next_focus_area": "area_to_explore_next"
}}
"""
            
            response = await self.llm_tool.generate_for_agent(
                "persona_agent",
                extraction_prompt,
                temperature=0.4,
                max_tokens=800
            )
            
            # Parse the structured response
            try:
                # Clean the response - remove markdown code blocks
                response_clean = response.strip()
                if response_clean.startswith('```json'):
                    response_clean = response_clean.replace('```json', '').replace('```', '').strip()
                elif response_clean.startswith('```'):
                    response_clean = response_clean.replace('```', '').strip()
                
                response_data = json.loads(response_clean)
                conversation_response = ConversationResponse(**response_data)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse extraction response: {e}")
                logger.warning(f"Raw response was: {response}")
                conversation_response = self._fallback_extraction_response(user_message)
            
            # Update framework extractions
            for extraction in conversation_response.extractions:
                section = extraction.framework_section
                criteria = extraction.criteria_key
                
                if section not in state["framework_extractions"]:
                    state["framework_extractions"][section] = {}
                
                state["framework_extractions"][section][criteria] = {
                    "value": extraction.extracted_value,
                    "confidence": extraction.confidence_score,
                    "reasoning": extraction.reasoning,
                    "extracted_at": datetime.now().isoformat()
                }
            
            # Update current focus
            if conversation_response.next_focus_area:
                state["current_focus"] = conversation_response.next_focus_area
            
            # Add AI response to conversation
            state["messages"].append(AIMessage(content=conversation_response.message))
            
            # Update completion percentage
            state["completion_percentage"] = self._calculate_completion_percentage(state["framework_extractions"])
            
            logger.info(f"Extracted {len(conversation_response.extractions)} items, completion: {state['completion_percentage']:.1f}%")
            return state
            
        except Exception as e:
            logger.error(f"Error in extract_and_respond: {e}")
            # Fallback response
            fallback_response = "Thank you for sharing that! Could you tell me more about your specific area of expertise?"
            state["messages"].append(AIMessage(content=fallback_response))
            return state
    
    def _fallback_extraction_response(self, user_message: str) -> ConversationResponse:
        """Fallback response when structured parsing fails."""
        return ConversationResponse(
            message="That's interesting! Could you tell me more about who your ideal clients are?",
            user_intent=UserIntent(intent_type="answering"),
            extractions=[],
            next_focus_area="target_audience",
            conversation_stage="gathering"
        )
    
    async def _check_completion(self, state: PersonaConversationState) -> PersonaConversationState:
        """Check if we have enough information for persona completion."""
        completion_percentage = state.get("completion_percentage", 0.0)
        
        if completion_percentage >= 80.0:
            state["conversation_stage"] = "completion"
        else:
            state["conversation_stage"] = "gathering"
        
        return state
    
    def _completion_router(self, state: PersonaConversationState) -> str:
        """Route to completion or continue gathering."""
        if state.get("conversation_stage") == "completion":
            return "wrap_up"
        else:
            return "continue"
    
    async def _wrap_up_conversation(self, state: PersonaConversationState) -> PersonaConversationState:
        """Generate completion message and prepare for persona generation."""
        completion_message = f"""
Excellent! I've gathered comprehensive information about your brand persona across all the key areas.

Based on our conversation, I have a clear picture of:
• Your expertise and ideal customer profile
• Your brand personality and values  
• Your unique positioning and approach
• Your communication style and voice
• Your content goals and audience insights
• Your long-term vision and success metrics

I'm now ready to create your comprehensive persona document. This will include strategic positioning, target audience psychology, brand voice guidelines, and content recommendations tailored specifically to your business.

Would you like me to generate your complete persona now?
"""
        
        state["messages"].append(AIMessage(content=completion_message.strip()))
        state["conversation_stage"] = "completion"
        
        return state
    
    def _format_conversation_context(self, state: PersonaConversationState) -> str:
        """Format recent conversation for LLM context."""
        messages = state["messages"]
        
        # Get last 6 messages (3 exchanges) for context
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        
        formatted_context = []
        for msg in recent_messages:
            role = "You" if isinstance(msg, AIMessage) else "User"
            formatted_context.append(f"{role}: {msg.content}")
        
        return "\n".join(formatted_context)
    
    def _get_framework_summary(self) -> str:
        """Get a summary of framework criteria for LLM reference."""
        if not self.framework_criteria:
            return "Framework criteria not loaded"
        
        summary = []
        sections = self.framework_criteria.get("framework_sections", {})
        
        for section_name, section_data in sections.items():
            summary.append(f"\n{section_data.get('section_name', section_name)}:")
            criteria = section_data.get("criteria", {})
            for criteria_key, criteria_info in criteria.items():
                summary.append(f"  - {criteria_key}: {criteria_info.get('description', '')}")
        
        return "\n".join(summary)
    
    def _calculate_completion_percentage(self, extractions: Dict[str, Dict[str, Any]]) -> float:
        """Calculate completion percentage based on extractions."""
        if not self.framework_criteria:
            return 0.0
        
        total_criteria = 0
        completed_criteria = 0
        
        sections = self.framework_criteria.get("framework_sections", {})
        
        for section_name, section_data in sections.items():
            criteria = section_data.get("criteria", {})
            for criteria_key in criteria.keys():
                total_criteria += 1
                
                if (section_name in extractions and 
                    criteria_key in extractions[section_name] and
                    extractions[section_name][criteria_key].get("confidence", 0.0) >= 0.6):
                    completed_criteria += 1
        
        return (completed_criteria / total_criteria) * 100 if total_criteria > 0 else 0.0
    
    def _get_detailed_progress(self, extractions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Get detailed progress breakdown for frontend display."""
        if not self.framework_criteria:
            return {"sections": {}, "overall": 0.0}
        
        sections = self.framework_criteria.get("framework_sections", {})
        progress = {"sections": {}, "overall": 0.0}
        
        total_completed = 0
        total_criteria = 0
        
        for section_name, section_data in sections.items():
            section_display = section_data.get("section_name", section_name)
            criteria = section_data.get("criteria", {})
            
            section_completed = 0
            section_total = len(criteria)
            total_criteria += section_total
            
            completed_items = []
            missing_items = []
            
            for criteria_key, criteria_info in criteria.items():
                if (section_name in extractions and 
                    criteria_key in extractions[section_name] and
                    extractions[section_name][criteria_key].get("confidence", 0.0) >= 0.6):
                    section_completed += 1
                    total_completed += 1
                    completed_items.append({
                        "key": criteria_key,
                        "description": criteria_info.get("description", ""),
                        "value": extractions[section_name][criteria_key].get("value", ""),
                        "confidence": extractions[section_name][criteria_key].get("confidence", 0.0)
                    })
                else:
                    missing_items.append({
                        "key": criteria_key,
                        "description": criteria_info.get("description", "")
                    })
            
            section_percentage = (section_completed / section_total) * 100 if section_total > 0 else 0
            
            progress["sections"][section_display] = {
                "completed": section_completed,
                "total": section_total,
                "percentage": round(section_percentage, 1),
                "status": self._get_section_status(section_percentage),
                "completed_items": completed_items,
                "missing_items": missing_items
            }
        
        progress["overall"] = round((total_completed / total_criteria) * 100, 1) if total_criteria > 0 else 0.0
        
        return progress
    
    def _get_section_status(self, percentage: float) -> str:
        """Get user-friendly status for a section."""
        if percentage >= 80:
            return "Complete"
        elif percentage >= 50:
            return "In Progress"
        elif percentage > 0:
            return "Started"
        else:
            return "Not Started"
    
    # Public interface methods
    async def process(self, session_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process user input through the LangGraph workflow."""
        try:
            user_input = input_data.get("user_input", "")
            
            # Initialize or get existing state
            state = await self._get_or_create_state(session_id, user_input)
            
            # Run through the workflow
            result = await self.app.ainvoke(state)
            
            # Save updated state
            await self._save_state(session_id, result)
            
            # Return response in expected format
            last_message = result["messages"][-1].content
            
            # Get detailed progress breakdown
            progress_details = self._get_detailed_progress(result["framework_extractions"])
            
            return {
                "status": result["conversation_stage"],
                "message": last_message,
                "completion_percentage": result["completion_percentage"],
                "framework_progress": progress_details,
                "token_usage": result.get("token_usage", {}),
                "conversation_type": "persona_building"
            }
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def _get_or_create_state(self, session_id: str, user_input: str) -> PersonaConversationState:
        """Get existing state or create new one."""
        try:
            # Try to get existing conversation context
            existing_messages = []
            if self.context_manager:
                context = await self.context_manager.get_efficient_context(session_id)
                # Convert context to BaseMessage objects
                for entry in context:
                    if entry.get("role") == "user":
                        existing_messages.append(HumanMessage(content=entry.get("content", "")))
                    elif entry.get("role") == "assistant":
                        existing_messages.append(AIMessage(content=entry.get("content", "")))
            
            # Add current user input
            existing_messages.append(HumanMessage(content=user_input))
            
            return PersonaConversationState(
                messages=existing_messages,
                business_context={},
                framework_extractions={},
                current_focus=None,
                user_intent=None,
                conversation_stage="gathering",
                session_id=session_id,
                completion_percentage=0.0,
                token_usage={"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
                framework_progress={}
            )
            
        except Exception as e:
            logger.error(f"Error creating state: {e}")
            # Minimal fallback state
            return PersonaConversationState(
                messages=[HumanMessage(content=user_input)],
                business_context={},
                framework_extractions={},
                current_focus=None,
                user_intent=None,
                conversation_stage="gathering", 
                session_id=session_id,
                completion_percentage=0.0,
                token_usage={"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
                framework_progress={}
            )
    
    async def _save_state(self, session_id: str, state: PersonaConversationState) -> None:
        """Save state back to context manager and session manager."""
        try:
            # Save the latest AI message to context
            if self.context_manager and state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, AIMessage):
                    await self.context_manager.add_assistant_message(session_id, last_message.content)
            
            # Update session progress
            if self.session_manager:
                await self.session_manager.update_framework_progress(
                    session_id,
                    state["completion_percentage"]
                )
            
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    async def start_conversation(self, session_id: str, initial_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start a new persona building conversation."""
        opening_message = """Welcome! I'm excited to help you build a comprehensive brand persona that will transform how you connect with your ideal clients.

Ready to get started?"""
        
        # Add to context
        if self.context_manager:
            await self.context_manager.add_assistant_message(session_id, opening_message)
        
        return {
            "status": "conversation_started",
            "message": opening_message,
            "conversation_type": "persona_building",
            "completion_percentage": 0.0
        }
    
    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "contextual_conversation",
            "question_answering", 
            "framework_extraction",
            "intelligent_follow_up",
            "completion_detection",
            "state_management"
        ]
    
    async def get_framework_progress(self, session_id: str) -> Dict[str, Any]:
        """Get detailed framework progress for a session."""
        try:
            # Create minimal state to get existing extractions
            state = await self._get_or_create_state(session_id, "")
            
            # Return detailed progress
            return self._get_detailed_progress(state["framework_extractions"])
            
        except Exception as e:
            logger.error(f"Error getting framework progress: {e}")
            return {"sections": {}, "overall": 0.0, "error": str(e)}
