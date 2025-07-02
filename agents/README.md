# Agents

Specialized AI agents for different aspects of persona building.

## Files:

- **`base/agent_interface.py`** - Base class that all agents inherit from
- **`question_agent.py`** - Handles Q&A flow and answer assessment
- **`scraper_agent.py`** - Website content extraction (to be implemented)
- **`persona_agent.py`** - Final persona generation (to be implemented)

## Current Status:

✅ **Question Agent** - Fully implemented with:
- Sequential question presentation
- Answer quality assessment using rubrics
- Intelligent follow-up questions
- Session progression management

🚧 **Scraper Agent** - Planned for website data extraction
🚧 **Persona Agent** - Planned for final synthesis using Luminary Hub methodology

## Architecture:

All agents inherit from `BaseAgent` which provides:
- Standardized `process()` method
- Error handling and logging
- Database and LLM tool integration
