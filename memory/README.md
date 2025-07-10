# Memory System Documentation

## Overview

The memory system has been restructured to use Redis for fast context management with LangChain integration. This provides efficient conversation context handling and smart token management.

## Architecture

```
memory/
├── context_manager.py          # Base context interface
├── redis_context_manager.py    # Redis-optimized implementation  
└── managers/
    ├── session_manager.py      # Session lifecycle with Redis caching
    └── conversation_state.py   # Framework progress tracking
```

## Components

### BaseContextManager (context_manager.py)
- Abstract base class defining the context management interface
- Provides common helper methods for all context managers
- Ensures consistent API across implementations

### RedisContextManager (redis_context_manager.py)
- Redis-first context storage with LangChain integration
- Uses `RedisChatMessageHistory` for conversation storage
- Implements `ConversationSummaryBufferMemory` for intelligent summarization
- Provides fast context retrieval with token optimization
- Falls back to database when Redis is unavailable

### SessionManager (managers/session_manager.py)
- Enhanced session management with Redis caching
- Fast session retrieval and updates
- Background database synchronization
- Session expiration and cleanup
- Framework progress tracking

### ConversationStateManager (managers/conversation_state.py)
- Tracks persona building progress across 6 sections
- Manages criteria completion and section transitions
- Stores conversation stage and context notes
- Provides progress summaries and statistics

## Key Features

### Redis Integration
- Fast context retrieval (milliseconds vs seconds)
- LangChain memory integration for smart summarization
- Automatic fallback to database when Redis unavailable
- TTL-based expiration for memory efficiency

### Token Management
- Intelligent context window management (target: 3000 tokens)
- Recent detailed + older summarized approach
- Dynamic token counting with tiktoken
- Context trimming when needed

### Framework Progress Tracking
- Real-time section completion tracking
- Criteria-based progress evaluation
- Cross-section information handling
- Conversation stage management

## Configuration

### Environment Variables
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379

# Memory Settings
MAX_CONTEXT_TOKENS=3000
RECENT_MESSAGE_LIMIT=10
SESSION_TIMEOUT_HOURS=24
```

### Usage Example

```python
from memory.redis_context_manager import RedisContextManager
from memory.managers.session_manager import SessionManager
from memory.managers.conversation_state import ConversationStateManager

# Initialize Redis context manager
redis_context = RedisContextManager(
    redis_url="redis://localhost:6379",
    database=database_client,
    llm_tool=llm_tool
)

# Initialize session manager
session_manager = SessionManager(
    redis_context_manager=redis_context,
    database=database_client
)

# Initialize conversation state manager
state_manager = ConversationStateManager(
    redis_context_manager=redis_context,
    database=database_client,
    framework_sections=framework_criteria
)

# Create session
session = await session_manager.create_session(user_id="user123")

# Add message
await redis_context.add_message(
    session_id=session.id,
    role="user",
    content="I'm a manufacturing efficiency expert..."
)

# Get context for LLM
context, token_count = await redis_context.get_context_for_llm(session.id)

# Update progress
await state_manager.update_criteria_completion(
    session_id=session.id,
    section_number=1,
    completed_criteria=["broad_domain_expertise", "specific_niche_focus"]
)
```

## Benefits

1. **Performance**: Redis provides sub-millisecond context retrieval
2. **Scalability**: Memory-efficient with intelligent summarization
3. **Reliability**: Automatic fallback to database when Redis unavailable
4. **Intelligence**: LangChain integration for smart context management
5. **Tracking**: Detailed progress tracking across persona framework
6. **Flexibility**: Modular design allows easy extension and testing

## Dependencies

- `redis>=5.0.0` - Redis client
- `langchain>=0.1.0` - LangChain integration
- `tiktoken>=0.5.0` - Token counting
- `pydantic>=2.0.0` - Data validation

## Next Steps

1. Implement database context manager for persistence
2. Add conversation analytics and insights
3. Implement context compression for very long conversations
4. Add multi-language support for context summarization
