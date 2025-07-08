# memory/__init__.py
"""Memory package for session and context management."""

# Import managers only when needed to avoid circular imports
__all__ = ['SessionManager', 'ContextManager']

def get_session_manager():
    from .session_manager import SessionManager
    return SessionManager

def get_context_manager():
    from .context_manager import ContextManager
    return ContextManager
