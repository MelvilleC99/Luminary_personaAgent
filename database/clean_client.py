"""
Updated Supabase client using the clean 4-table schema.
"""

import logging
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
from database.models import PersonaSession, ChatMessage
from orchestrator.config import settings

logger = logging.getLogger(__name__)


class CleanSupabaseClient:
    """Clean Supabase client with 4-table schema."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client."""
        try:
            self.client: Client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase client connected")
        except Exception as e:
            logger.error(f"❌ Supabase connection failed: {e}")
            raise
    
    # SESSIONS TABLE
    async def create_session(self, session: PersonaSession) -> PersonaSession:
        """Create session in persona_sessions table."""
        try:
            data = {
                'id': session.id,
                'user_id': session.user_id,
                'current_question': session.current_question,
                'questions_completed': session.questions_completed,
                'status': session.status,
                'website_url': session.website_url,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'expires_at': session.expires_at.isoformat() if session.expires_at else None
            }
            
            result = self.client.table('persona_sessions').insert(data).execute()
            logger.info(f"✅ Session created: {session.id}")
            return session
        except Exception as e:
            logger.error(f"❌ Failed to create session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[PersonaSession]:
        """Get session from persona_sessions table."""
        try:
            result = self.client.table('persona_sessions').select('*').eq('id', session_id).execute()
            if result.data:
                return PersonaSession(**result.data[0])
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get session: {e}")
            return None
    
    async def update_session(self, session: PersonaSession) -> PersonaSession:
        """Update session in persona_sessions table."""
        try:
            data = {
                'current_question': session.current_question,
                'questions_completed': session.questions_completed,
                'status': session.status,
                'updated_at': session.updated_at.isoformat()
            }
            
            result = self.client.table('persona_sessions').update(data).eq('id', session.id).execute()
            logger.info(f"✅ Session updated: {session.id}")
            return session
        except Exception as e:
            logger.error(f"❌ Failed to update session: {e}")
            raise
    
    # MESSAGES TABLE
    async def create_message(self, message: ChatMessage) -> ChatMessage:
        """Create message in chat_messages table."""
        try:
            data = {
                'id': message.id,
                'session_id': message.session_id,
                'role': message.role,
                'content': message.content,
                'question_id': message.question_id,
                'metadata': message.metadata,
                'created_at': message.timestamp.isoformat()
            }
            
            result = self.client.table('chat_messages').insert(data).execute()
            logger.debug(f"✅ Message created for session: {message.session_id}")
            return message
        except Exception as e:
            logger.error(f"❌ Failed to create message: {e}")
            raise
    
    async def get_session_messages(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get messages from chat_messages table."""
        try:
            query = self.client.table('chat_messages').select('*').eq('session_id', session_id).order('created_at')
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            return [ChatMessage(**msg) for msg in result.data]
        except Exception as e:
            logger.error(f"❌ Failed to get messages: {e}")
            return []
    
    # QUESTION RESPONSES TABLE
    async def save_question_response(self, session_id: str, question_id: int, 
                                   original_answer: str, score: float, 
                                   needs_follow_up: bool, follow_up_answers: List[str] = None):
        """Save response to question_responses table."""
        try:
            data = {
                'session_id': session_id,
                'question_id': question_id,
                'original_answer': original_answer,
                'follow_up_answers': follow_up_answers or [],
                'combined_answer': ' '.join([original_answer] + (follow_up_answers or [])),
                'quality_score': score,
                'needs_follow_up': needs_follow_up,
                'completed_at': None if needs_follow_up else 'now()'
            }
            
            result = self.client.table('question_responses').insert(data).execute()
            logger.info(f"✅ Q{question_id} response saved for session: {session_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save question response: {e}")
    
    # USAGE LOGS TABLE
    async def log_usage(self, session_id: str, agent_type: str, action: str,
                       provider: str = None, model: str = None,
                       input_tokens: int = 0, output_tokens: int = 0,
                       cost_usd: float = 0.0, processing_time_ms: int = 0,
                       success: bool = True, error_message: str = None):
        """Log usage to usage_logs table."""
        try:
            data = {
                'session_id': session_id,
                'agent_type': agent_type,
                'action': action,
                'provider': provider,
                'model': model,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
                'cost_usd': cost_usd,
                'processing_time_ms': processing_time_ms,
                'success': success,
                'error_message': error_message
            }
            
            result = self.client.table('usage_logs').insert(data).execute()
            logger.debug(f"✅ Usage logged: {agent_type} - {action}")
        except Exception as e:
            logger.error(f"❌ Failed to log usage: {e}")
