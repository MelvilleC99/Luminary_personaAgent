-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. PERSONA SESSIONS TABLE
CREATE TABLE IF NOT EXISTS persona_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'expired')),
    current_question INTEGER NOT NULL DEFAULT 1,
    completion_percentage REAL DEFAULT 0.0,
    website_url TEXT,
    framework_completion_percentage REAL DEFAULT 0.0,
    conversation_turn_count INTEGER DEFAULT 0,
    total_information_extracted INTEGER DEFAULT 0,
    website_scraped BOOLEAN DEFAULT FALSE,
    persona_generated BOOLEAN DEFAULT FALSE,
    awaiting_follow_up BOOLEAN DEFAULT FALSE,
    follow_up_attempts INTEGER DEFAULT 0,
    total_cost DECIMAL(10,4) DEFAULT 0.0,
    total_tokens INTEGER DEFAULT 0,
    total_api_calls INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

-- 2. CONVERSATION CONTEXT TABLE
CREATE TABLE IF NOT EXISTS conversation_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    question_number INTEGER,
    agent_type TEXT CHECK (agent_type IN ('question', 'persona')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. CONVERSATION TURNS TABLE
CREATE TABLE IF NOT EXISTS conversation_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL CHECK (speaker IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    turn_number INTEGER DEFAULT 1,
    turn_type TEXT DEFAULT 'conversation',
    framework_focus TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. AGENT USAGE LOGS TABLE
CREATE TABLE IF NOT EXISTS agent_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES persona_sessions(id) ON DELETE CASCADE,
    agent_type TEXT NOT NULL,
    action TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0.0,
    processing_time_ms REAL DEFAULT 0.0,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. FRAMEWORK EXTRACTIONS TABLE
CREATE TABLE IF NOT EXISTS framework_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    framework_section TEXT NOT NULL,
    criteria_key TEXT NOT NULL,
    extracted_value TEXT NOT NULL,
    confidence_score REAL NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    reasoning TEXT,
    extraction_method TEXT DEFAULT 'langgraph_agent',
    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id, framework_section, criteria_key)
);

-- 6. PERSONA DATA TABLE
CREATE TABLE IF NOT EXISTS persona_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    strategic_client_persona JSONB,
    deep_icp_psychology JSONB,
    differentiators_mapping JSONB,
    solution_positioning JSONB,
    brand_voice_messaging JSONB,
    offer_conversion_insights JSONB,
    version INTEGER DEFAULT 1,
    generation_method TEXT DEFAULT 'langgraph_agent',
    total_criteria_extracted INTEGER DEFAULT 0,
    completion_score REAL DEFAULT 0.0,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. USAGE LOGS TABLE
CREATE TABLE IF NOT EXISTS usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES persona_sessions(id) ON DELETE CASCADE,
    agent_type TEXT,
    action TEXT,
    tokens_used INTEGER DEFAULT 0,
    cost DECIMAL(10,4) DEFAULT 0.0,
    processing_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. SCRAPED DATA TABLE
CREATE TABLE IF NOT EXISTS scraped_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    website_url TEXT NOT NULL,
    structured_data JSONB DEFAULT '{}',
    scraping_status TEXT DEFAULT 'pending' CHECK (scraping_status IN ('pending', 'completed', 'failed')),
    scraping_method TEXT,
    error_message TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_persona_sessions_user_id ON persona_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_persona_sessions_status ON persona_sessions(status);
CREATE INDEX IF NOT EXISTS idx_persona_sessions_created_at ON persona_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_conversation_context_session_id ON conversation_context(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_context_created_at ON conversation_context(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversation_turns_session_id ON conversation_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_turns_created_at ON conversation_turns(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_usage_logs_session_id ON agent_usage_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_usage_logs_created_at ON agent_usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_usage_logs_provider ON agent_usage_logs(provider, model);
CREATE INDEX IF NOT EXISTS idx_framework_extractions_session_id ON framework_extractions(session_id);
CREATE INDEX IF NOT EXISTS idx_framework_extractions_section ON framework_extractions(framework_section, criteria_key);
CREATE INDEX IF NOT EXISTS idx_persona_data_session_id ON persona_data(session_id);

-- TIMESTAMP UPDATE FUNCTION AND TRIGGER
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_activity_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

CREATE TRIGGER update_persona_sessions_updated_at 
    BEFORE UPDATE ON persona_sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
