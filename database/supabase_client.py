"""
Basic Supabase client for session persistence.
"""

import logging
from typing import Dict, Any, Optional, List
from database.models import PersonaSession, ChatMessage

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Basic Supabase client for the persona agent."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client with connection limits."""
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client = None
        
        # Initialize real Supabase connection
        try:
            from supabase import create_client, Client
            
            # Create Supabase client with standard configuration
            self.client: Client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase client connected successfully")
        except ImportError:
            logger.error("❌ Supabase package not installed. Install with: pip install supabase")
            self.client = None
            # Initialize fallback storage
            self._sessions = {}
            self._messages = {}
            logger.warning("⚠️ Falling back to simulation mode")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            self.client = None
            # Initialize fallback storage
            self._sessions = {}
            self._messages = {}
            logger.warning("⚠️ Falling back to simulation mode")
    
    async def create_session(self, session: PersonaSession) -> PersonaSession:
        """Create a new session."""
        if self.client:
            try:
                # Create a simplified session data dict that matches actual DB schema
                session_data = {
                    'id': session.id,
                    'user_id': session.user_id,
                    'status': session.status,
                    'website_url': session.website_url,
                    'framework_completion_percentage': 0.0,
                    'conversation_turn_count': 0,
                    'total_information_extracted': 0,
                    'created_at': session.created_at.isoformat() if session.created_at else None,
                    'updated_at': session.updated_at.isoformat() if session.updated_at else None,
                    'last_activity_at': session.updated_at.isoformat() if session.updated_at else None
                }
                
                # Remove None values to avoid issues
                session_data = {k: v for k, v in session_data.items() if v is not None}
                
                result = self.client.table('persona_sessions').insert(session_data).execute()
                logger.info(f"✅ Session created in database: {session.id}")
                return session
            except Exception as e:
                logger.error(f"❌ Failed to create session in database: {e}")
                # Fallback to simulation
                if not hasattr(self, '_sessions'):
                    self._sessions = {}
                self._sessions[session.id] = session.dict()
                logger.info(f"📝 Session created (fallback): {session.id}")
                return session
        else:
            # Simulation mode
            if not hasattr(self, '_sessions'):
                self._sessions = {}
            self._sessions[session.id] = session.dict()
            logger.info(f"📝 Session created (simulation): {session.id}")
            return session
    
    async def get_session(self, session_id: str) -> Optional[PersonaSession]:
        """Get a session by ID."""
        if self.client:
            try:
                result = self.client.table('persona_sessions').select('*').eq('id', session_id).execute()
                if result.data:
                    session_data = result.data[0]
                    # Add default values for missing fields to match model
                    session_data.setdefault('framework_completion_percentage', 0.0)
                    session_data.setdefault('conversation_turn_count', 0)
                    session_data.setdefault('total_information_extracted', 0)
                    session_data.setdefault('persona_generated', False)
                    session_data.setdefault('website_scraped', False)
                    session_data.setdefault('awaiting_follow_up', False)
                    session_data.setdefault('follow_up_attempts', 0)
                    return PersonaSession(**session_data)
                return None
            except Exception as e:
                logger.error(f"❌ Failed to get session from database: {e}")
                # Fallback to simulation
                if not hasattr(self, '_sessions'):
                    self._sessions = {}
                session_data = self._sessions.get(session_id)
                if session_data:
                    return PersonaSession(**session_data)
                return None
        else:
            # Simulation mode
            if not hasattr(self, '_sessions'):
                self._sessions = {}
            session_data = self._sessions.get(session_id)
            if session_data:
                return PersonaSession(**session_data)
            return None
    
    async def update_session(self, session: PersonaSession) -> PersonaSession:
        """Update a session."""
        if self.client:
            try:
                # Create a simplified session data dict that matches actual DB schema
                session_data = {
                    'status': session.status,
                    'website_url': session.website_url,
                    'framework_completion_percentage': getattr(session, 'framework_completion_percentage', 0.0),
                    'conversation_turn_count': getattr(session, 'conversation_turn_count', 0),
                    'total_information_extracted': getattr(session, 'total_information_extracted', 0),
                    'updated_at': session.updated_at.isoformat() if session.updated_at else None,
                    'last_activity_at': session.updated_at.isoformat() if session.updated_at else None
                }
                
                # Remove None values
                session_data = {k: v for k, v in session_data.items() if v is not None}
                
                result = self.client.table('persona_sessions').update(session_data).eq('id', session.id).execute()
                logger.info(f"✅ Session updated in database: {session.id}")
                return session
            except Exception as e:
                logger.error(f"❌ Failed to update session in database: {e}")
                # Fallback to simulation
                if not hasattr(self, '_sessions'):
                    self._sessions = {}
                self._sessions[session.id] = session.dict()
                logger.info(f"📝 Session updated (fallback): {session.id}")
                return session
        else:
            # Simulation mode
            if not hasattr(self, '_sessions'):
                self._sessions = {}
            self._sessions[session.id] = session.dict()
            logger.info(f"📝 Session updated (simulation): {session.id}")
            return session
    
    async def create_message(self, message: ChatMessage) -> ChatMessage:
        """Create a new message."""
        if self.client:
            try:
                # Create a simplified message data dict that matches actual DB schema
                message_data = {
                    'id': message.id,
                    'session_id': message.session_id,
                    'speaker': message.role,  # conversation_turns uses 'speaker' instead of 'role'
                    'content': message.content,
                    'turn_number': getattr(message, 'turn_number', 1),  # Add turn number
                    'turn_type': getattr(message, 'turn_type', 'conversation'),
                    'framework_focus': getattr(message, 'framework_focus', None),
                    'created_at': message.timestamp.isoformat() if message.timestamp else None
                }
                
                # Remove None values and fields that don't exist in DB
                message_data = {k: v for k, v in message_data.items() if v is not None and k != 'agent_type'}
                
                result = self.client.table('conversation_turns').insert(message_data).execute()
                logger.debug(f"✅ Message created in database for session: {message.session_id}")
                return message
            except Exception as e:
                logger.error(f"❌ Failed to create message in database: {e}")
                # Fallback to simulation
                if not hasattr(self, '_messages'):
                    self._messages = {}
                if message.session_id not in self._messages:
                    self._messages[message.session_id] = []
                self._messages[message.session_id].append(message.dict())
                logger.debug(f"📝 Message created (fallback) for session: {message.session_id}")
                return message
        else:
            # Simulation mode
            if not hasattr(self, '_messages'):
                self._messages = {}
            if message.session_id not in self._messages:
                self._messages[message.session_id] = []
            self._messages[message.session_id].append(message.dict())
            logger.debug(f"📝 Message created (simulation) for session: {message.session_id}")
            return message
    
    async def get_session_messages(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get messages for a session."""
        if self.client:
            try:
                query = self.client.table('conversation_turns').select('*').eq('session_id', session_id).order('created_at')
                if limit:
                    query = query.limit(limit)
                result = query.execute()
                return [ChatMessage(**msg_data) for msg_data in result.data]
            except Exception as e:
                logger.error(f"❌ Failed to get messages from database: {e}")
                # Fallback to simulation
                messages_data = self._messages.get(session_id, [])
                if limit:
                    messages_data = messages_data[-limit:]
                return [ChatMessage(**msg_data) for msg_data in messages_data]
        else:
            # Simulation mode
            messages_data = self._messages.get(session_id, [])
            if limit:
                messages_data = messages_data[-limit:]
            return [ChatMessage(**msg_data) for msg_data in messages_data]
    
    async def clear_session_messages(self, session_id: str):
        """Clear messages for a session."""
        if self.client:
            try:
                self.client.table('conversation_turns').delete().eq('session_id', session_id).execute()
                logger.info(f"✅ Messages cleared from database for session: {session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to clear messages from database: {e}")
                # Fallback to simulation
                if session_id in self._messages:
                    del self._messages[session_id]
        else:
            # Simulation mode
            if session_id in self._messages:
                del self._messages[session_id]
            logger.info(f"📝 Messages cleared (simulation) for session: {session_id}")
    
    async def log_agent_interaction(self, log_entry: Dict[str, Any]):
        """Log agent interaction."""
        if self.client:
            try:
                # Try to log to usage_logs table, but don't fail if it doesn't exist
                self.client.table('usage_logs').insert(log_entry).execute()
                logger.debug(f"✅ Usage logged: {log_entry.get('agent_type', 'unknown')}")
            except Exception as e:
                # Don't log this as an error since usage_logs is optional
                logger.debug(f"📝 Usage logging skipped (table may not exist): {log_entry.get('agent_type', 'unknown')}")
        else:
            # For simulation, just log it
            logger.info(f"📝 Agent interaction logged (simulation): {log_entry.get('agent_type', 'unknown')}")
    
    def get_session_count(self) -> int:
        """Get total number of sessions."""
        if self.client:
            try:
                result = self.client.table('persona_sessions').select('id', count='exact').execute()
                return result.count or 0
            except Exception as e:
                logger.error(f"❌ Failed to get session count: {e}")
                return len(self._sessions)
        else:
            return len(self._sessions)
    
    def get_message_count(self) -> int:
        """Get total number of messages."""
        if self.client:
            try:
                result = self.client.table('conversation_turns').select('id', count='exact').execute()
                return result.count or 0
            except Exception as e:
                logger.error(f"❌ Failed to get message count: {e}")
                return sum(len(messages) for messages in self._messages.values())
        else:
            return sum(len(messages) for messages in self._messages.values())
