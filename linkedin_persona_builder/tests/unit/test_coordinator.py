"""
Unit tests for RequestCoordinator

Tests request routing and coordination including:
- Chat request handling
- Error handling
- Response formatting
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from orchestrator.coordinator import (
    RequestCoordinator, 
    ChatRequest, 
    ChatResponse,
    ProgressRequest,
    ProgressResponse,
    ErrorResponse
)


class TestRequestCoordinator:
    """Test suite for RequestCoordinator class"""
    
    @pytest.fixture
    def coordinator(self):
        """Create a RequestCoordinator instance with mocked dependencies"""
        with patch('orchestrator.coordinator.PersonaAgent') as mock_agent, \
             patch('orchestrator.coordinator.RecoveryManager') as mock_recovery, \
             patch('orchestrator.coordinator.RedisManager') as mock_redis, \
             patch('orchestrator.coordinator.SupabaseManager') as mock_supabase:
            
            coordinator = RequestCoordinator()
            return coordinator

    @pytest.mark.asyncio
    async def test_route_chat_request_success(self, coordinator):
        """Test successful chat request routing"""
        # Setup
        request = ChatRequest(
            session_id="test-123",
            user_input="I help startups with marketing",
            user_id="user-456",
            user_name="Test User"
        )
        
        expected_response = {
            "agent_response": "Great! Tell me more about your marketing expertise.",
            "requires_user_input": True,
            "session_complete": False,
            "progress": {"overall": 0.25},
            "current_section": 1,
            "current_criterion": "broad_domain_expertise"
        }
        
        coordinator.persona_agent.process = AsyncMock(return_value=expected_response)
        
        # Execute
        response = await coordinator.route_chat_request(request)
        
        # Assert
        assert isinstance(response, ChatResponse)
        assert response.session_id == "test-123"
        assert response.success is True
        assert response.requires_user_input is True
        
    def test_chat_request_validation(self):
        """Test Pydantic validation for ChatRequest"""
        # Valid request
        request = ChatRequest(
            session_id="test-123",
            user_input="Test input",
            user_id="user-456"
        )
        assert request.session_id == "test-123"
        assert request.user_name is None  # Optional field
        
        # Invalid request should raise ValidationError
        with pytest.raises(Exception):  # Pydantic will raise validation error
            ChatRequest(
                session_id="test-123",
                # Missing required fields
            )
