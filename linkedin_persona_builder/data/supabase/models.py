from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class PersonaStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused" 
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class PersonaRecord(BaseModel):
    """Supabase personas table model"""
    id: Optional[str] = None
    session_id: str
    user_id: str
    persona_data: Dict[str, Any]
    completion_status: float = Field(ge=0.0, le=1.0)
    section_progress: Optional[Dict[str, float]] = None
    industry: Optional[str] = None
    framework_version: str = "1.0"
    status: PersonaStatus = PersonaStatus.ACTIVE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class ConversationLogRecord(BaseModel):
    """Supabase conversation_logs table model"""
    id: Optional[str] = None
    session_id: str
    turn_number: int
    user_input: Optional[str] = None
    agent_response: str
    section_number: int
    criterion_name: str
    node_type: str
    quality_score: Optional[int] = Field(None, ge=1, le=10)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    response_time_ms: Optional[int] = None
    token_count: Optional[int] = None
    timestamp: Optional[datetime] = None


class SessionAnalyticsRecord(BaseModel):
    """Supabase session_analytics table model"""
    id: Optional[str] = None
    session_id: str
    user_id: str
    total_duration_minutes: Optional[int] = None
    completion_rate: float = Field(ge=0.0, le=1.0)
    drop_off_section: Optional[int] = None
    total_turns: int = 0
    average_quality_score: Optional[float] = None
    follow_up_count: int = 0
    modification_count: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    average_response_time_ms: Optional[int] = None
    industry: Optional[str] = None
    user_agent: Optional[str] = None
    completion_method: Optional[str] = None
    error_count: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class FrameworkVersionRecord(BaseModel):
    """Supabase framework_versions table model"""
    id: Optional[str] = None
    version: str
    framework_data: Dict[str, Any]
    description: Optional[str] = None
    is_active: bool = False
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None


class SystemHealthLogRecord(BaseModel):
    """Supabase system_health_logs table model"""
    id: Optional[str] = None
    check_type: str
    status: str
    response_time_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None


class LLMUsageLogRecord(BaseModel):
    """Supabase llm_usage_logs table model"""
    id: Optional[str] = None
    session_id: Optional[str] = None
    model_used: str
    operation_type: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    response_time_ms: Optional[int] = None
    timestamp: Optional[datetime] = None


# Table names mapping
SUPABASE_TABLES = {
    "personas": "personas",
    "conversation_logs": "conversation_logs", 
    "session_analytics": "session_analytics",
    "framework_versions": "framework_versions",
    "system_health_logs": "system_health_logs",
    "llm_usage_logs": "llm_usage_logs"
}


# SQL schema for reference (not executed by this code)
SCHEMA_SQL = """
-- Personas table
CREATE TABLE personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    persona_data JSONB NOT NULL,
    completion_status FLOAT NOT NULL CHECK (completion_status >= 0 AND completion_status <= 1),
    section_progress JSONB,
    industry TEXT,
    framework_version TEXT DEFAULT '1.0',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'complete', 'abandoned')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Conversation logs table
CREATE TABLE conversation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    user_input TEXT,
    agent_response TEXT,
    section_number INTEGER,
    criterion_name TEXT,
    node_type TEXT,
    quality_score INTEGER CHECK (quality_score >= 1 AND quality_score <= 10),
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    response_time_ms INTEGER,
    token_count INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id, turn_number)
);

-- Session analytics table
CREATE TABLE session_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    total_duration_minutes INTEGER,
    completion_rate FLOAT CHECK (completion_rate >= 0 AND completion_rate <= 1),
    drop_off_section INTEGER,
    total_turns INTEGER,
    average_quality_score FLOAT,
    follow_up_count INTEGER DEFAULT 0,
    modification_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10,4) DEFAULT 0.0000,
    average_response_time_ms INTEGER,
    industry TEXT,
    user_agent TEXT,
    completion_method TEXT,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Framework versions table
CREATE TABLE framework_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version TEXT UNIQUE NOT NULL,
    framework_data JSONB NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT false,
    created_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    activated_at TIMESTAMP WITH TIME ZONE
);

-- System health logs table
CREATE TABLE system_health_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('healthy', 'degraded', 'failed')),
    response_time_ms INTEGER,
    details JSONB,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- LLM usage logs table
CREATE TABLE llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT,
    model_used TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0.000000,
    response_time_ms INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_personas_user_id ON personas(user_id);
CREATE INDEX idx_personas_session_id ON personas(session_id);
CREATE INDEX idx_personas_status ON personas(status);
CREATE INDEX idx_personas_completion_status ON personas(completion_status);
CREATE INDEX idx_conversation_logs_session_id ON conversation_logs(session_id);
CREATE INDEX idx_session_analytics_user_id ON session_analytics(user_id);
CREATE INDEX idx_session_analytics_completion_rate ON session_analytics(completion_rate);
"""
