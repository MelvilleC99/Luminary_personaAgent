"""
Production Supabase client with real database operations.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
from database.models import PersonaSession, ChatMessage
from orchestrator.config import settings

logger = logging.getLogger(__name__)


class ProductionSupabaseClient:
    """Production Supabase client with real database operations."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize production Supabase client."""
        try:
            self.client: Client = create_client(supabase_url, supabase_key)
            self.url = supabase_url
            logger.info("✅ Production Supabase client initialized")
            
            # Test connection
            asyncio.create_task(self._test_connection())
            
        except Exception as e:
            logger.error(f"❌ Supabase client initialization failed: {e}")
            raise
    
    async def _test_connection(self):
        """Test database connection."""
        try:
            # Simple test query
            result = self.client.table('persona_sessions').select('*').limit(1).execute()
            logger.info(f"✅ Database connection test successful")
        except Exception as e:
            logger.warning(f"⚠️ Database connection test failed: {e}")
    
    async def create_session(self, session: PersonaSession) -> PersonaSession:
        """Create a new session in database."""
        try:
            data = session.dict()
            data['created_at'] = data['created_at'].isoformat()
            data['updated_at'] = data['updated_at'].isoformat()
            if data.get('expires_at'):
                data['expires_at'] = data['expires_at'].isoformat()
            
            result = self.client.table('persona_sessions').insert(data).execute()
            logger.info(f"✅ Session created in DB: {session.id}")
            return session
            
        except Exception as e:
            logger.error(f"❌ Failed to create session {session.id}: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[PersonaSession]:
        """Get session from database."""
        try:
            result = self.client.table('persona_sessions').select('*').eq('id', session_id).execute()
            
            if result.data:
                return PersonaSession(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get session {session_id}: {e}")
            return None
    
    async def update_session(self, session: PersonaSession) -> PersonaSession:
        """Update session in database."""
        try:
            data = session.dict()
            data['updated_at'] = data['updated_at'].isoformat()
            
            result = self.client.table('persona_sessions').update(data).eq('id', session.id).execute()
            logger.info(f"✅ Session updated in DB: {session.id}")
            return session
            
        except Exception as e:
            logger.error(f"❌ Failed to update session {session.id}: {e}")
            raise
