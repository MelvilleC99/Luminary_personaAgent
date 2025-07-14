"""
Unit tests for StateManager component

Tests state management functionality including:
- Session state persistence
- Persona data storage
- Progress tracking
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from agent.components.state_manager import StateManager


class TestStateManager:
    """Test suite for StateManager class"""
    
    @pytest.fixture
    def state_manager(self):
        """Create a StateManager instance with mocked Redis"""
        with patch('agent.components.state_manager.RedisManager') as mock_redis:
            manager = StateManager()
            manager.redis = mock_redis
            return manager
    
    @pytest.mark.asyncio
    async def test_get_persona_data_exists(self, state_manager):
        """Test retrieving existing persona data"""
        # Setup
        session_id = "test-123"
        expected_data = {
            "session_id": session_id,
            "sections": [{"section_number": 1, "criteria": {}}],
            "framework_version": "1.0"
        }
        state_manager.redis.get = AsyncMock(return_value=json.dumps(expected_data))
        
        # Execute
        result = await state_manager.get_persona_data(session_id)
        
        # Assert
        assert result == expected_data
        state_manager.redis.get.assert_called_once_with(f"persona:{session_id}")

    @pytest.mark.asyncio
    async def test_get_persona_data_not_found(self, state_manager):
        """Test retrieving non-existent persona data"""
        # Setup
        session_id = "nonexistent"
        state_manager.redis.get = AsyncMock(return_value=None)
        
        # Execute
        result = await state_manager.get_persona_data(session_id)
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_save_persona_data(self, state_manager):
        """Test saving persona data"""
        # Setup
        session_id = "test-123"
        persona_data = {
            "session_id": session_id,
            "sections": [],
            "framework_version": "1.0"
        }
        state_manager.redis.set = AsyncMock(return_value=True)
        
        # Execute
        result = await state_manager.save_persona_data(session_id, persona_data)
        
        # Assert
        assert result is True
        state_manager.redis.set.assert_called_once()
        call_args = state_manager.redis.set.call_args[0]
        assert call_args[0] == f"persona:{session_id}"
        assert json.loads(call_args[1]) == persona_data
