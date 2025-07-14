"""
Unit tests for ValidationManager component

Tests validation functionality including:
- Consistency checking
- Conflict detection
- System prompt validation
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from agent.components.validation_manager import ValidationManager, ValidationResult


class TestValidationManager:
    """Test suite for ValidationManager class"""
    
    @pytest.fixture
    def validation_manager(self):
        """Create a ValidationManager instance with mocked dependencies"""
        with patch('agent.components.validation_manager.llm_cache') as mock_llm_cache:
            manager = ValidationManager()
            manager.llm_cache = mock_llm_cache
            return manager
    
    @pytest.mark.asyncio
    async def test_validate_consistency_no_data(self, validation_manager):
        """Test validation with missing data"""
        # Test with no existing persona
        result = await validation_manager.validate_consistency({}, None)
        assert result.valid is True
        assert len(result.conflicts) == 0
        
        # Test with no new evaluation
        result = await validation_manager.validate_consistency(None, {"some": "data"})
        assert result.valid is True
        assert len(result.conflicts) == 0

    @pytest.mark.asyncio
    async def test_validate_consistency_no_conflicts(self, validation_manager):
        """Test validation when no conflicts exist"""
        # Setup
        new_evaluation = {
            "extracted_info": "I specialize in Python development"
        }
        existing_persona = {
            "sections": [{
                "criteria": {
                    "expertise": {
                        "response": "Software development with Python",
                        "complete": True
                    }
                }
            }]
        }
        
        # Mock no conflicts found
        validation_manager._find_potential_conflicts = AsyncMock(return_value=[])
        
        # Execute
        result = await validation_manager.validate_consistency(new_evaluation, existing_persona)
        
        # Assert
        assert result.valid is True
        assert len(result.conflicts) == 0
        assert result.confidence == 1.0
