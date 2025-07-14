"""
Integration tests for LinkedIn Persona Builder

Tests the full flow of persona building including:
- Complete conversation flow
- Data persistence
- API integration
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from api.endpoints import app
from fastapi.testclient import TestClient
from orchestrator.coordinator import ChatRequest


class TestPersonaBuilderIntegration:
    """Integration tests for the complete persona building flow"""
    
    @pytest.fixture
    def client(self):
        """Create test client with mocked external dependencies"""
        with patch('data.redis.redis_config.initialize_redis') as mock_redis_init, \
             patch('data.supabase.supabase_config.initialize_supabase') as mock_supabase_init:
            
            mock_redis_init.return_value = True
            mock_supabase_init.return_value = True
            
            return TestClient(app)
    
    @pytest.mark.integration
    def test_complete_persona_flow(self, client):
        """Test a complete persona building conversation"""
        session_id = "integration-test-123"
        user_id = "test-user-456"
        
        # Step 1: Initial chat
        response = client.post("/chat", json={
            "session_id": session_id,
            "user_input": "Hello, I want to build my LinkedIn persona",
            "user_id": user_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["requires_user_input"] is True
        assert data["current_section"] == 1

        # Step 2: Provide expertise
        response = client.post("/chat", json={
            "session_id": session_id,
            "user_input": "I specialize in AI and machine learning for healthcare startups",
            "user_id": user_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "progress" in data
        
        # Step 3: Continue conversation
        response = client.post("/chat", json={
            "session_id": session_id,
            "user_input": "My specific niche is predictive analytics for patient outcomes",
            "user_id": user_id
        })
        
        assert response.status_code == 200
        
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, client):
        """Test handling multiple concurrent sessions"""
        session_ids = ["session-1", "session-2", "session-3"]
        
        async def send_chat_request(session_id):
            return client.post("/chat", json={
                "session_id": session_id,
                "user_input": "Test concurrent request",
                "user_id": f"user-{session_id}"
            })
        
        # Send concurrent requests
        tasks = [send_chat_request(sid) for sid in session_ids]
        responses = await asyncio.gather(*tasks)
        
        # Verify all succeeded
        for response in responses:
            assert response.status_code == 200
