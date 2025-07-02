# Orchestrator

The main coordination layer for the Luminary Persona Agent system.

## Files:

- **`coordinator.py`** - Main orchestrator that routes tasks between agents
- **`config.py`** - Configuration management with environment variables  
- **`main.py`** - Entry point for running the system

## Responsibilities:

- Session management and routing
- Agent coordination and task distribution
- Initial question loading and session startup
- Integration with memory and database layers

## Key Classes:

- `PersonaCoordinator` - Main orchestration class that manages the entire workflow
