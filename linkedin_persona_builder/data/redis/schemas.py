from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class NodeType(str, Enum):
    GREETING = "greeting"
    QUESTION = "question"
    EVALUATION = "evaluation"
    FOLLOW_UP = "follow_up"
    TRANSITION = "transition"
    REVIEW = "review"
    COMPLETION = "completion"


class SessionState(BaseModel):
    """Redis session state schema"""
    user_id: str
    current_section: int = 1
    current_criterion: str = ""
    follow_up_attempts: int = 0
    industry: Optional[str] = "unknown"
    communication_style: Optional[str] = "unknown"
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    framework_version: str = "1.0"
    
    class Config:
        use_enum_values = True


class CriterionData(BaseModel):
    """Individual criterion completion data"""
    name: str
    response: str = ""
    confidence: float = 0.0
    quality_score: int = 0
    complete: bool = False
    attempts: int = 0
    timestamp: Optional[datetime] = None
    cross_section_source: bool = False  # True if updated via cross-section matching


class SectionProgress(BaseModel):
    """Section-level progress tracking"""
    section_number: int
    section_name: str
    completion_percentage: float = 0.0
    criteria: Dict[str, CriterionData] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PersonaData(BaseModel):
    """Complete persona data structure"""
    sections: List[SectionProgress] = Field(default_factory=list)
    overall_completion: float = 0.0
    total_criteria: int = 0
    completed_criteria: int = 0
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def calculate_completion(self) -> float:
        """Calculate overall completion percentage"""
        if not self.sections:
            return 0.0
        
        total_completion = sum(section.completion_percentage for section in self.sections)
        return total_completion / len(self.sections)
    
    def get_section(self, section_number: int) -> Optional[SectionProgress]:
        """Get section by number"""
        for section in self.sections:
            if section.section_number == section_number:
                return section
        return None


class ConversationTurn(BaseModel):
    """Individual conversation turn"""
    turn_id: int
    user_input: Optional[str] = None
    agent_response: str
    section_number: int
    criterion_name: str
    node_type: NodeType
    quality_score: Optional[int] = None
    confidence_score: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    token_count: Optional[int] = None
    
    class Config:
        use_enum_values = True


class ConversationHistory(BaseModel):
    """Complete conversation history"""
    session_id: str
    turns: List[ConversationTurn] = Field(default_factory=list)
    total_turns: int = 0
    
    def add_turn(self, turn: ConversationTurn):
        """Add new conversation turn"""
        turn.turn_id = self.total_turns + 1
        self.turns.append(turn)
        self.total_turns += 1
    
    def get_recent_turns(self, count: int = 5) -> List[ConversationTurn]:
        """Get most recent turns"""
        return self.turns[-count:] if self.turns else []


class LLMCacheEntry(BaseModel):
    """LLM response cache entry"""
    response: str
    timestamp: datetime = Field(default_factory=datetime.now)
    model: str
    operation: str
    hit_count: int = 1
    original_prompt_hash: str


class ValidationConflict(BaseModel):
    """Data validation conflict"""
    type: str  # "contradiction", "inconsistency"
    existing_criterion: str
    existing_value: str
    new_criterion: str
    new_value: str
    confidence: float


class ValidationResult(BaseModel):
    """Validation result with conflicts"""
    valid: bool = True
    conflicts: List[ValidationConflict] = Field(default_factory=list)
    resolution_needed: bool = False


class EvaluationResult(BaseModel):
    """Response evaluation result"""
    quality_score: int = Field(ge=1, le=10)
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_info: str
    specificity_score: int = Field(ge=1, le=10)
    relevance_score: int = Field(ge=1, le=10)
    professional_value_score: int = Field(ge=1, le=10)
    improvement_suggestions: List[str] = Field(default_factory=list)
    reasoning: str = ""


class CrossSectionMatch(BaseModel):
    """Cross-section criterion match"""
    criterion_name: str
    section_number: int
    similarity_score: float
    evaluation_result: EvaluationResult


class ContextData(BaseModel):
    """Conversation context for question generation"""
    industry: str = "unknown"
    communication_style: str = "unknown"
    previous_responses: List[str] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    detected_patterns: Dict[str, Any] = Field(default_factory=dict)


class FollowUpMetadata(BaseModel):
    """Follow-up question metadata"""
    strategy_used: str
    examples_provided: List[str] = Field(default_factory=list)
    attempt_number: int
    original_response_type: str


class QuestionMetadata(BaseModel):
    """Question generation metadata"""
    base_question: str
    adaptations_made: List[str] = Field(default_factory=list)
    examples_provided: bool = False
    context_used: Optional[ContextData] = None


class SessionAnalytics(BaseModel):
    """Session analytics data"""
    session_id: str
    user_id: str
    total_duration_minutes: Optional[float] = None
    completion_rate: float = 0.0
    drop_off_section: Optional[int] = None
    total_turns: int = 0
    average_quality_score: Optional[float] = None
    follow_up_count: int = 0
    modification_count: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    average_response_time_ms: Optional[int] = None
    industry: Optional[str] = None
    completion_method: Optional[str] = None  # "natural", "timeout", "abandoned"
    error_count: int = 0


# Redis key patterns
REDIS_KEYS = {
    "session": "session:{session_id}",
    "persona": "persona:{session_id}", 
    "history": "history:{session_id}",
    "tokens": "session_tokens:{session_id}",
    "llm_cache": "llm_cache:{operation}:{hash}",
    "temp": "temp:{session_id}:{operation}",
    "health": "system_health:{component}",
    "metrics": "metrics:daily:{date}",
    "learning": "successful_followups",
    "audio": "audio:{session_id}:{timestamp}"
}


# TTL configurations
TTL_CONFIG = {
    "session": 86400,  # 24 hours
    "persona": 86400,  # 24 hours  
    "history": 86400,  # 24 hours
    "tokens": 86400,   # 24 hours
    "llm_cache": 3600, # 1 hour
    "temp": 3600,      # 1 hour
    "health": 300,     # 5 minutes
    "metrics": 604800, # 7 days
    "audio": 3600      # 1 hour
}
