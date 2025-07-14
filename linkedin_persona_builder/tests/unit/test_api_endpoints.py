"""
Unit tests for API endpoints

Tests FastAPI endpoints including:
- Chat endpoint
- Health check
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

# Import the app
from api.endpoints import app
from orchestrator.coordinator import ChatRequest, ChatResponse


class TestAPIEndpoints:
    """Test suite for API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_coordinator(self):
        """Mock the request coordinator"""
        with patch('api.endpoints.request_coordinator') as mock:
            yield mock
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "LinkedIn Persona Builder API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"

    def test_health_check_success(self, client, mock_coordinator):
        """Test health check endpoint when healthy"""
        # Setup
        mock_coordinator.health_check = AsyncMock(return_value={
            "status": "healthy",
            "services": {
                "redis": "connected",
                "supabase": "connected",
                "llm": "available"
            }
        })
        
        # Execute
        response = client.get("/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
    
    def test_chat_endpoint_success(self, client, mock_coordinator):
        """Test chat endpoint with valid request"""
        # Setup
        chat_response = ChatResponse(
            agent_response="Hello! Tell me about your expertise.",
            session_id="test-123",
            requires_user_input=True,
            session_complete=False,
            progress={"overall": 0.0},
            current_section=1,
            current_criterion="broad_domain_expertise"
        )
        mock_coordinator.route_chat_request = AsyncMock(return_value=chat_response)
        
        # Execute
        request_data = {
            "session_id": "test-123",
            "user_input": "Hello",
            "user_id": "user-456"
        }
        response = client.post("/chat", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-123"
        assert data["requires_user_input"] is True
    
    def test_chat_endpoint_invalid_request(self, client):
        """Test chat endpoint with invalid request data"""
        # Missing required fields
        response = client.post("/chat", json={"invalid": "data"})
        assert response.status_code == 422  # Validation error
