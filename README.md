# Comprehensive LLM-Powered Persona Agent

## Overview

This is a sophisticated conversational persona building system that extracts comprehensive brand persona information through natural conversation rather than rigid questionnaires. The system uses a single intelligent LLM agent to conduct natural conversations that systematically gather information across 6 framework sections with 60+ criteria.

## Architecture

### Core Components

- **PersonaAgent**: Master conversational agent for persona building
- **FrameworkAssessmentTool**: Comprehensive framework evaluation and next-step determination
- **InformationExtractionTool**: Intelligent extraction of framework information from conversations
- **Efficient Context Management**: Smart token management with recent detailed + older summarized
- **Framework Criteria System**: 60+ information points across 6 sections

### 6 Framework Sections

1. **Core Expertise & Ideal Customer Profile (ICP)**
   - Domain expertise, niche specialization, target audience, core problems, outcomes

2. **Brand Personality & Profile DNA**
   - Brand personality, core values, reputation, formative stories, origin story

3. **Positioning & Expertise**
   - Elevator pitch, sweet spot audience, unique methods, services, contrarian beliefs

4. **Voice, Style & Tone**
   - Communication style, content approach, reference styles, signature phrases

5. **Content Goals & Target Audience**
   - Content objectives, audience struggles, desires, success stories, emotional impact

6. **Long-Term Vision & Success Metrics**
   - Future vision, legacy aspirations, success signals, feelings of success

## Key Features

### Conversational Intelligence
- Natural conversation flow vs. rigid questionnaires
- One response can fill multiple framework areas
- Intelligent follow-up questions based on response quality
- Context-aware transitions between framework sections

### Efficient Token Management
- Recent detailed context (last 8-10 exchanges ~3K tokens)
- Older summarized context (~500 tokens)
- Framework state tracking (separate from conversation)
- Total target: ~4K tokens (vs 25K+ in naive approach)

### Intelligent Assessment
- Framework-based evaluation vs. simple scoring
- Confidence thresholds for each criteria
- Contextual follow-up generation
- Completion status tracking across all sections

## File Structure

```
backend agent/
├── agents/
│   ├── persona_agent.py              # Master conversational agent
│   ├── question_agent.py             # Legacy fallback (optional)
│   └── base/
│       └── agent_interface.py        # Base agent interface
├── tools/
│   ├── framework_assessment_tool.py  # Framework evaluation
│   ├── information_extraction_tool.py # Extract framework info
│   ├── assessment_tool.py            # Legacy assessment (fallback)
│   └── llm_tool.py                   # LLM provider management
├── knowledge/
│   └── framework_criteria.yaml       # 60+ criteria definitions
├── prompts/
│   ├── persona_agent_prompt.txt      # Conversational system prompt
│   └── question_agent_prompt.txt     # Legacy prompt (fallback)
├── memory/
│   ├── session_manager.py            # Enhanced session management
│   └── context_manager.py            # Efficient context management
├── orchestrator/
│   └── coordinator.py                # Main orchestration logic
├── database/
│   ├── NEW_SCHEMA.md                 # Database schema documentation
│   └── models.py                     # Database models
└── api/
    └── endpoints.py                  # API endpoints
```

## Database Schema

### New Tables
- `persona_sessions`: Enhanced session tracking with framework completion
- `framework_state`: Tracks 60+ criteria completion per session
- `conversation_turns`: Efficient conversation tracking with summarization
- `information_extractions`: Detailed extraction tracking
- `context_summaries`: Efficient context management

### Token Efficiency Features
- Smart summarization of older conversation turns
- Context views for efficient loading
- Framework state tracking separate from conversation
- Optimized queries for minimal data transfer

## Usage

### Starting a Session
```python
# Start conversational persona building
response = await coordinator.start_session(user_id="user123")
# Returns natural conversation opener
```

### Processing User Input
```python
# Process conversational input
response = await coordinator.process_user_input(
    session_id="session123",
    user_input="I help manufacturing companies eliminate waste through lean methodologies..."
)
# Returns intelligent follow-up or transition
```

### Framework Progress
```python
# Get comprehensive framework progress
progress = await coordinator.get_framework_progress(session_id="session123")
# Returns completion status across all 6 sections
```

### Persona Generation
```python
# Generate final persona document
persona = await coordinator.generate_persona_document(session_id="session123")
# Returns comprehensive brand persona
```

## API Endpoints

- `POST /start` - Start new conversational session
- `POST /chat` - Process conversational input
- `GET /progress/{session_id}` - Get framework progress
- `GET /suggestions/{session_id}` - Get conversation suggestions
- `POST /generate/{session_id}` - Generate final persona
- `GET /health` - System health check

## Configuration

### Environment Variables
```bash
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# LLM Providers
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Session Management
SESSION_TIMEOUT_HOURS=24
MAX_CONTEXT_TURNS=10
```

### LLM Configuration
```python
llm_config = {
    "persona_agent": "openai",
    "information_extractor": "anthropic",
    "framework_assessor": "openai"
}
```

## Development

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Setup database
python setup_database.py

# Start API server
bash start_api.sh
```

### Testing
```bash
# Test individual components
python -m pytest tests/

# Test conversation flow
python test_conversation_flow.py

# Test framework extraction
python test_framework_extraction.py
```

## Migration from 30-Question System

### What Changed
- ❌ Removed: Fixed 30-question sequence
- ❌ Removed: Simple 1-10 scoring system
- ❌ Removed: Question-by-question progression
- ✅ Added: Natural conversational flow
- ✅ Added: Framework-based information extraction
- ✅ Added: Intelligent context management
- ✅ Added: Comprehensive persona generation

### Backward Compatibility
- Legacy QuestionAgent available as fallback
- Existing database tables preserved
- API endpoints maintain compatibility
- Gradual migration path available

## Performance Optimizations

### Token Efficiency
- 4K token target vs 25K+ naive approach
- Smart context summarization
- Framework state caching
- Efficient database queries

### Response Time
- Streamlined LLM calls
- Parallel processing where possible
- Intelligent caching strategies
- Optimized database operations

## Monitoring & Analytics

### Key Metrics
- Framework completion rates
- Average conversation turns to completion
- Token usage per session
- User satisfaction scores
- Persona quality assessments

### Health Checks
- LLM provider availability
- Database connectivity
- Token usage monitoring
- Session management health

## Future Enhancements

### Planned Features
- Multi-language support
- Voice interface integration
- Advanced NLP for better extraction
- Persona template marketplace
- Integration with marketing tools

### Scalability
- Horizontal scaling support
- Advanced caching strategies
- Queue-based processing
- Real-time analytics dashboard

---

**Note**: This system represents a significant evolution from question-based to conversation-based persona building, providing a more natural and comprehensive approach to brand persona development.
