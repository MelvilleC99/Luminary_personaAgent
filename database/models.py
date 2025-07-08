"""
Pydantic models for the Luminary Persona Agent.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SessionStatus(str, Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused" 
    COMPLETED = "completed"
    EXPIRED = "expired"


class QuestionStatus(str, Enum):
    """Question response status enumeration."""
    PENDING = "pending"
    ANSWERED = "answered"
    NEEDS_FOLLOW_UP = "needs_follow_up"
    COMPLETE = "complete"


class AgentType(str, Enum):
    """Agent type enumeration."""
    QUESTION = "question_agent"
    ASSESSMENT = "assessment_agent"
    SCRAPER = "scraper_agent"
    PERSONA = "persona_agent"


class QuestionResponse(BaseModel):
    """Model for a user's response to a question."""
    question_id: int
    answer: str
    quality_score: Optional[float] = None
    status: QuestionStatus = QuestionStatus.PENDING
    follow_ups: List[str] = Field(default_factory=list)
    follow_up_responses: List[str] = Field(default_factory=list)
    attempts: int = 0
    completed_at: Optional[datetime] = None
    

class Question(BaseModel):
    """Model for a persona building question."""
    id: int
    section: str
    text: str
    required_elements: List[str] = Field(default_factory=list)
    quality_indicators: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)


class AssessmentRubric(BaseModel):
    """Model for question assessment criteria."""
    question_id: int
    required_elements: List[str]
    quality_indicators: List[str]
    red_flags: List[str]
    scoring_criteria: Dict[str, str]
    good_example: str
    poor_example: str
    follow_up_templates: Dict[str, str]


class FrameworkExtraction(BaseModel):
    """Model for extracted framework criteria."""
    id: Optional[str] = None
    session_id: str
    framework_section: str
    criteria_key: str
    extracted_value: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    extraction_method: str = "langgraph_agent"
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class SectionProgress(BaseModel):
    """Model for tracking section completion progress."""
    session_id: str
    section_number: int
    section_name: str
    criteria_completed: List[str] = Field(default_factory=list)
    criteria_missing: List[str] = Field(default_factory=list)
    completion_percentage: float = 0.0
    is_complete: bool = False
    cross_section_data: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationState(BaseModel):
    """Model for managing conversation state and memory."""
    session_id: str
    current_section: int = 1
    total_sections: int = 6
    section_progress: Dict[int, SectionProgress] = Field(default_factory=dict)
    conversation_summary: str = ""
    recent_context: List[str] = Field(default_factory=list)
    token_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class PersonaSession(BaseModel):
    """Model for a persona building session."""
    id: str
    user_id: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    current_question: int = 1
    completion_percentage: float = 0.0
    questions_completed: int = 0
    # Framework progress tracking
    framework_completion_percentage: float = 0.0
    conversation_turn_count: int = 0
    total_information_extracted: int = 0
    # Track follow-up state
    awaiting_follow_up: bool = False
    follow_up_attempts: int = 0
    website_url: Optional[str] = None
    website_scraped: bool = False
    persona_generated: bool = False
    # Cost tracking
    total_cost: float = 0.0
    total_tokens: int = 0
    total_api_calls: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class ScrapedData(BaseModel):
    """Model for scraped company website data."""
    session_id: str
    website_url: str
    raw_content: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    scraping_status: str = "pending"
    scraped_at: Optional[datetime] = None
    

class PersonaData(BaseModel):
    """Model for generated persona data."""
    session_id: str
    strategic_client_persona: Optional[Dict[str, Any]] = None
    deep_icp_psychology: Optional[Dict[str, Any]] = None
    differentiators_mapping: Optional[Dict[str, Any]] = None
    solution_positioning: Optional[Dict[str, Any]] = None
    brand_voice_messaging: Optional[Dict[str, Any]] = None
    offer_conversion_insights: Optional[Dict[str, Any]] = None
    version: int = 1
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentTask(BaseModel):
    """Model for agent task tracking."""
    id: str
    session_id: str
    agent_type: AgentType
    task_data: Dict[str, Any]
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class ChatMessage(BaseModel):
    """Model for chat messages in the conversation."""
    id: str
    session_id: str
    role: str  # "user", "assistant", "system"
    content: str
    question_id: Optional[int] = None
    agent_type: Optional[AgentType] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionSummary(BaseModel):
    """Model for session summary data."""
    session: PersonaSession
    responses: List[QuestionResponse]
    scraped_data: Optional[ScrapedData] = None
    persona_data: Optional[PersonaData] = None
    progress_percentage: float
    next_action: str
