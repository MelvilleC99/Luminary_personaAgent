"""
Pydantic models for LangGraph Persona Agent.
Structured data models for LLM interactions and state management.
"""

from typing import Dict, Any, List, Optional, TypedDict, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


class ExtractionItem(BaseModel):
    """Model for extracted framework criteria."""
    framework_section: str
    criteria_key: str
    extracted_value: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class UserIntent(BaseModel):
    """Model for analyzing user intent in conversation."""
    intent_type: Literal["answering", "questioning", "clarifying", "ready_to_start", "greeting"]
    question_content: Optional[str] = None
    topics_mentioned: List[str] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    """Model for LLM conversation responses."""
    message: str
    user_intent: Optional[UserIntent] = None
    extractions: List[ExtractionItem] = Field(default_factory=list)
    next_focus_area: Optional[str] = None
    conversation_stage: Literal["opening", "gathering", "follow_up", "completion"] = "gathering"


class PersonaConversationState(TypedDict):
    """LangGraph state definition for persona conversations."""
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
    section_completion_manager: Any  # Will be injected
    enhanced_context_manager: Any   # Will be injected
