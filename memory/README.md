# Memory

Session and conversation context management.

## Files:

- **`session_manager.py`** - Handles persona building sessions with persistence
- **`context_manager.py`** - Manages conversation history and chat messages

## Responsibilities:

### Session Manager:
- Create and manage persona building sessions
- Track question progress (current_question, questions_completed)
- Handle session state (active, paused, completed, expired)
- Session persistence and resume functionality

### Context Manager:  
- Store and retrieve conversation messages
- Maintain chat history for each session
- Provide conversation context for agents
- Support different message types (user, assistant, system)

## Key Features:

- **Persistent Sessions** - Sessions survive app restarts
- **Progress Tracking** - Know exactly where user left off
- **Context Retrieval** - Full conversation history available
- **Database Integration** - All data persisted to Supabase
