# Database

Database models, schemas, and client implementations for Supabase integration.

## Files:

- **`models.py`** - Pydantic models for all data structures
- **`supabase_client.py`** - Main Supabase client with fallback simulation mode
- **`__init__.py`** - Package initialization and exports

## Essential Tables:

1. **`persona_sessions`** - Main session tracking
2. **`conversation_turns`** - Conversation history  
3. **`question_responses`** - Q&A data with scores
4. **`usage_logs`** - Agent usage tracking

## Pydantic Models:

- `PersonaSession` - Session state and progress
- `ChatMessage` - Individual conversation messages
- `QuestionResponse` - User answers with assessment data
- `PersonaData` - Final generated persona
- `SessionStatus` / `QuestionStatus` - Enum types

## Usage:

```python
from database.models import PersonaSession, SessionStatus
from database.supabase_client import SupabaseClient

# Create session
session = PersonaSession(id="123", status=SessionStatus.ACTIVE)
client = SupabaseClient(url, key)
await client.create_session(session)
```

## Setup:

1. Use `setup_tables.sql` for essential tables
2. Copy SQL to Supabase SQL editor  
3. Run `setup_database.py` to verify connection

## Features:

- **Fallback Mode**: Works without database connection (simulation mode)
- **Error Handling**: Graceful degradation when Supabase is unavailable
- **Type Safety**: Full Pydantic model integration
- **Async Support**: All operations are async for better performance
