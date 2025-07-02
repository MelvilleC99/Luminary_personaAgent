# Database

Database models, schemas, and client implementations for Supabase integration.

## Files:

- **`models.py`** - Pydantic models for all data structures
- **`simplified_schema.py`** - Essential database tables (recommended)
- **`schema.py`** - Full schema (comprehensive but may be overkill)
- **`supabase_client.py`** - Simulation client for testing
- **`production_client.py`** - Real Supabase integration

## Essential Tables:

1. **`persona_sessions`** - Main session tracking
2. **`chat_messages`** - Conversation history  
3. **`question_responses`** - Q&A data with scores
4. **`persona_data`** - Generated persona output

## Pydantic Models:

- `PersonaSession` - Session state and progress
- `ChatMessage` - Individual conversation messages
- `QuestionResponse` - User answers with assessment data
- `PersonaData` - Final generated persona
- `SessionStatus` / `QuestionStatus` - Enum types

## Usage:

```python
from database.models import PersonaSession, SessionStatus
from database.production_client import ProductionSupabaseClient

# Create session
session = PersonaSession(id="123", status=SessionStatus.ACTIVE)
client = ProductionSupabaseClient(url, key)
await client.create_session(session)
```

## Setup:

1. Use `simplified_schema.py` for essential tables
2. Copy SQL to Supabase SQL editor  
3. Run `setup_database.py` to verify
