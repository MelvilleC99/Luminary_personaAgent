"""
SIMPLIFIED Database schema - only essential tables for persona agent.
"""

# ESSENTIAL TABLES ONLY

PERSONA_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS persona_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'expired')),
    current_question INTEGER NOT NULL DEFAULT 1,
    questions_completed INTEGER NOT NULL DEFAULT 0,
    website_url TEXT,
    website_scraped BOOLEAN DEFAULT FALSE,
    persona_generated BOOLEAN DEFAULT FALSE,
    
    -- Basic metrics
    total_cost DECIMAL(10,4) DEFAULT 0.0,
    total_tokens INTEGER DEFAULT 0,
    total_api_calls INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);
"""

CHAT_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    question_id INTEGER,
    agent_type TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

QUESTION_RESPONSES_TABLE = """
CREATE TABLE IF NOT EXISTS question_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL,
    answer TEXT NOT NULL,
    quality_score DECIMAL(3,1),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'answered', 'needs_follow_up', 'complete')),
    follow_ups TEXT[],
    attempts INTEGER DEFAULT 0,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

PERSONA_DATA_TABLE = """
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
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

# OPTIONAL - Can add later
SCRAPED_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS scraped_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES persona_sessions(id) ON DELETE CASCADE,
    website_url TEXT NOT NULL,
    structured_data JSONB DEFAULT '{}',
    scraping_status TEXT DEFAULT 'pending',
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

# FOR MONITORING - Can add later  
USAGE_LOGS_TABLE = """
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
"""

# CORE TABLES ONLY (Start with these)
ESSENTIAL_TABLES = [
    PERSONA_SESSIONS_TABLE,
    CHAT_MESSAGES_TABLE, 
    QUESTION_RESPONSES_TABLE,
    PERSONA_DATA_TABLE
]

# ADD LATER
OPTIONAL_TABLES = [
    SCRAPED_DATA_TABLE,
    USAGE_LOGS_TABLE
]

ESSENTIAL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_persona_sessions_user_id ON persona_sessions(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_question_responses_session_id ON question_responses(session_id);",
]
