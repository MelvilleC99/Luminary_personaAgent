# New Database Schema for Conversational Persona Agent

## Overview
This schema supports the new conversational persona agent architecture that extracts comprehensive brand persona information across 6 framework sections through natural conversation.

## New Tables

### 1. persona_sessions
Enhanced session tracking for conversational flow.

```sql
CREATE TABLE persona_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active', -- active, paused, completed, archived
    framework_completion_percentage DECIMAL(5,2) DEFAULT 0.0,
    conversation_turn_count INTEGER DEFAULT 0,
    total_information_extracted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    website_url VARCHAR(500),
    completion_metadata JSONB, -- Final persona data when complete
    
    -- Indexes
    INDEX idx_persona_sessions_user_id (user_id),
    INDEX idx_persona_sessions_status (status),
    INDEX idx_persona_sessions_last_activity (last_activity_at)
);
```

### 2. framework_state
Tracks completion of 60+ framework criteria per session.

```sql
CREATE TABLE framework_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES persona_sessions(id) ON DELETE CASCADE,
    framework_section VARCHAR(100) NOT NULL, -- core_expertise, brand_personality, etc.
    criteria_key VARCHAR(100) NOT NULL, -- broad_expertise, niche_expertise, etc.
    
    -- Information tracking
    extracted_value TEXT, -- The actual extracted information
    confidence_score DECIMAL(3,2) DEFAULT 0.0, -- 0.0 to 1.0
    is_sufficient BOOLEAN DEFAULT FALSE,
    extraction_source_turn INTEGER, -- Which conversation turn this came from
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validation_notes TEXT,
    
    -- Ensure unique criteria per session
    UNIQUE(session_id, framework_section, criteria_key),
    
    -- Indexes
    INDEX idx_framework_state_session (session_id),
    INDEX idx_framework_state_section (framework_section),
    INDEX idx_framework_state_sufficient (is_sufficient)
);
```

### 3. conversation_turns
Efficient conversation tracking with smart context management.

```sql
CREATE TABLE conversation_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES persona_sessions(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    speaker VARCHAR(20) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    
    -- Context management
    is_summarized BOOLEAN DEFAULT FALSE, -- TRUE if this turn has been summarized
    summary_content TEXT, -- Condensed version for context efficiency
    token_count INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    turn_type VARCHAR(50), -- question, follow_up, confirmation, transition
    framework_focus VARCHAR(100), -- Which framework section this turn addresses
    
    -- Indexes
    INDEX idx_conversation_turns_session (session_id),
    INDEX idx_conversation_turns_number (session_id, turn_number),
    INDEX idx_conversation_turns_recent (session_id, created_at),
    INDEX idx_conversation_turns_summarized (is_summarized)
);
```

### 4. information_extractions
Detailed tracking of information extracted from conversations.

```sql
CREATE TABLE information_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES persona_sessions(id) ON DELETE CASCADE,
    turn_id UUID REFERENCES conversation_turns(id) ON DELETE CASCADE,
    
    -- Extraction details
    framework_section VARCHAR(100) NOT NULL,
    criteria_key VARCHAR(100) NOT NULL,
    extracted_value TEXT NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    extraction_method VARCHAR(50) DEFAULT 'llm', -- llm, pattern, keyword
    
    -- Context
    source_text TEXT, -- The part of user input this came from
    reasoning TEXT, -- Why this extraction was made
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_confirmed BOOLEAN DEFAULT FALSE,
    confirmation_turn_id UUID REFERENCES conversation_turns(id),
    
    -- Indexes
    INDEX idx_information_extractions_session (session_id),
    INDEX idx_information_extractions_turn (turn_id),
    INDEX idx_information_extractions_framework (framework_section, criteria_key)
);
```

### 5. context_summaries
Efficient context management for token optimization.

```sql
CREATE TABLE context_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES persona_sessions(id) ON DELETE CASCADE,
    
    -- Summary details
    summary_type VARCHAR(50) NOT NULL, -- conversation, framework_state, extraction
    summary_content TEXT NOT NULL,
    token_count INTEGER,
    
    -- Range covered
    from_turn_number INTEGER,
    to_turn_number INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    replaced_by_id UUID REFERENCES context_summaries(id),
    
    -- Indexes
    INDEX idx_context_summaries_session (session_id),
    INDEX idx_context_summaries_active (session_id, is_active),
    INDEX idx_context_summaries_type (summary_type)
);
```

## Modified Existing Tables

### Update conversation_context (if keeping)
Add framework awareness to existing context table.

```sql
ALTER TABLE conversation_context ADD COLUMN framework_section VARCHAR(100);
ALTER TABLE conversation_context ADD COLUMN turn_type VARCHAR(50);
ALTER TABLE conversation_context ADD COLUMN is_summarized BOOLEAN DEFAULT FALSE;
ALTER TABLE conversation_context ADD COLUMN summary_content TEXT;
```

## Views for Efficient Queries

### 1. session_framework_progress
Get framework completion status per session.

```sql
CREATE VIEW session_framework_progress AS
SELECT 
    s.id as session_id,
    s.user_id,
    s.status,
    fs.framework_section,
    COUNT(fs.criteria_key) as total_criteria,
    COUNT(CASE WHEN fs.is_sufficient = TRUE THEN 1 END) as completed_criteria,
    ROUND(
        (COUNT(CASE WHEN fs.is_sufficient = TRUE THEN 1 END) * 100.0 / 
         COUNT(fs.criteria_key)), 2
    ) as completion_percentage,
    AVG(fs.confidence_score) as avg_confidence
FROM persona_sessions s
LEFT JOIN framework_state fs ON s.id = fs.session_id
GROUP BY s.id, s.user_id, s.status, fs.framework_section;
```

### 2. recent_conversation_context
Get recent conversation context for efficient loading.

```sql
CREATE VIEW recent_conversation_context AS
SELECT 
    ct.session_id,
    ct.turn_number,
    ct.speaker,
    CASE 
        WHEN ct.is_summarized = TRUE THEN ct.summary_content
        ELSE ct.content
    END as display_content,
    ct.framework_focus,
    ct.turn_type,
    ct.created_at
FROM conversation_turns ct
WHERE ct.turn_number > (
    SELECT MAX(turn_number) - 10 
    FROM conversation_turns 
    WHERE session_id = ct.session_id
)
ORDER BY ct.session_id, ct.turn_number;
```

## Token Efficiency Features

1. **Smart Summarization**: Older conversation turns get summarized
2. **Context Views**: Load only recent detailed + older summarized
3. **Framework State**: Track extracted info separately from conversation
4. **Efficient Queries**: Views optimized for minimal data transfer

## Migration Notes

1. **Existing Data**: Can migrate existing persona_sessions and conversation_context
2. **New Workflow**: Framework-based tracking replaces question-based
3. **Backward Compatibility**: Keep old tables initially for fallback

## Expected Token Usage

- **Recent Context**: ~3K tokens (10 recent turns)
- **Framework Summary**: ~500 tokens (current state)
- **Context Summaries**: ~300 tokens (older conversation)
- **Total**: ~4K tokens (vs 25K+ in naive approach)

---

**Next Steps**: 
1. Create these tables in Supabase
2. Update database client connections
3. Create migration scripts if needed
