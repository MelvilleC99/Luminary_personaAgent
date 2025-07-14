"""
Unit tests for PersonaBuilder component

Tests the core persona building functionality including:
- Persona compilation
- Validation
- Modification handling
- Export functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from agent.components.persona_builder import PersonaBuilder, PersonaSummary


class TestPersonaBuilder:
    """Test suite for PersonaBuilder class"""
    
    @pytest.fixture
    def persona_builder(self):
        """Create a PersonaBuilder instance with mocked dependencies"""
        with patch('agent.components.persona_builder.state_manager') as mock_state_manager, \
             patch('agent.components.persona_builder.validation_manager') as mock_validation_manager, \
             patch('agent.components.persona_builder.llm_cache') as mock_llm_cache, \
             patch('agent.components.persona_builder.framework_loader') as mock_framework_loader:
            
            builder = PersonaBuilder()
            builder.state_manager = mock_state_manager
            builder.validation_manager = mock_validation_manager
            builder.llm_cache = mock_llm_cache
            builder.framework_loader = mock_framework_loader
            
            return builder
    
    @pytest.fixture
    def sample_persona_data(self):
        """Sample persona data for testing"""
        return {
            "session_id": "test-session-123",
            "framework_version": "1.0",
            "total_criteria": 16,
            "completed_criteria": 14,
            "detected_industry": "technology",
            "sections": [
                {
                    "section_number": 1,
                    "section_name": "Core Expertise & Ideal Customer",
                    "criteria": {
                        "broad_domain_expertise": {
                            "response": "AI and Machine Learning for healthcare",
                            "complete": True,
                            "confidence": 0.9
                        },
                        "ideal_client_definition": {
                            "response": "Healthcare startups with 10-50 employees",
                            "complete": True,
                            "confidence": 0.85
                        }
                    }
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_compile_persona_success(self, persona_builder, sample_persona_data):
        """Test successful persona compilation"""
        # Setup
        session_id = "test-session-123"
        persona_builder.state_manager.get_persona_data = AsyncMock(return_value=sample_persona_data)
        persona_builder.validate_completeness = AsyncMock(return_value={
            "completion_score": 0.875,
            "valid": True
        })
        persona_builder._generate_overall_summary = AsyncMock(
            return_value="Professional AI/ML expert focused on healthcare solutions"
        )
        persona_builder._generate_linkedin_recommendations_simple = AsyncMock(
            return_value=["Update headline", "Share AI insights", "Connect with healthcare leaders"]
        )
        
        # Execute
        result = await persona_builder.compile_persona(session_id)
        
        # Assert
        assert result["session_id"] == session_id
        assert result["completion_score"] == 0.875
        assert result["ready_for_content_creation"] is True
        assert "persona_summary" in result
        assert "overall_summary" in result["persona_summary"]
        assert len(result["persona_summary"]["linkedin_recommendations"]) == 3
    
    @pytest.mark.asyncio
    async def test_compile_persona_no_data(self, persona_builder):
        """Test compilation when no persona data exists"""
        # Setup
        session_id = "nonexistent-session"
        persona_builder.state_manager.get_persona_data = AsyncMock(return_value=None)
        
        # Execute
        result = await persona_builder.compile_persona(session_id)
        
        # Assert
        assert result["error"] == "No persona data found"
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_validate_completeness(self, persona_builder, sample_persona_data):
        """Test persona completeness validation"""
        # Setup
        session_id = "test-session-123"
        persona_builder.state_manager.get_persona_data = AsyncMock(return_value=sample_persona_data)
        
        # Mock framework with expected structure
        mock_framework = Mock()
        mock_framework.sections = {
            "section_1": Mock(
                section_number=1,
                criteria={
                    "broad_domain_expertise": {},
                    "ideal_client_definition": {},
                    "specific_niche_focus": {},
                    "target_customer_problems": {}
                }
            )
        }
        persona_builder.framework_loader.load_current = Mock(return_value=mock_framework)
        
        # Execute
        result = await persona_builder.validate_completeness(session_id)
        
        # Assert
        assert result["valid"] is True  # 2/4 = 50% < 70% threshold
        assert result["completion_score"] == 0.5
        assert result["total_criteria"] == 4
        assert result["completed_criteria"] == 2
    
    def test_extract_key_insights_simple(self, persona_builder, sample_persona_data):
        """Test key insights extraction"""
        # Execute
        insights = persona_builder._extract_key_insights_simple(sample_persona_data)
        
        # Assert
        assert len(insights) >= 3
        assert len(insights) <= 5
        assert all(isinstance(insight, str) for insight in insights)

    def test_parse_modification_simple(self, persona_builder):
        """Test simple modification parsing"""
        # Test expertise modification
        result = persona_builder._parse_modification_simple("Change my expertise to cybersecurity")
        assert result["success"] is True
        assert result["target_criterion"] == "broad_domain_expertise"
        
        # Test client modification
        result = persona_builder._parse_modification_simple("Update my ideal client to enterprise companies")
        assert result["success"] is True
        assert result["target_criterion"] == "ideal_client_definition"
        
        # Test unrecognized modification
        result = persona_builder._parse_modification_simple("Something random")
        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_handle_modification_success(self, persona_builder, sample_persona_data):
        """Test successful modification handling"""
        # Setup
        session_id = "test-session-123"
        persona_builder.state_manager.get_persona_data = AsyncMock(return_value=sample_persona_data)
        persona_builder._apply_simple_modification = AsyncMock(return_value=True)
        
        # Execute
        result = await persona_builder.handle_modification(
            session_id, 
            "Change my expertise to blockchain technology"
        )
        
        # Assert
        assert result["success"] is True
        assert "updated_criterion" in result
    
    @pytest.mark.asyncio
    async def test_export_for_json(self, persona_builder, sample_persona_data):
        """Test JSON export functionality"""
        # Setup
        session_id = "test-session-123"
        compiled_persona = {
            "session_id": session_id,
            "completion_score": 0.875,
            "ready_for_content_creation": True,
            "persona_summary": {
                "overall_summary": "Test summary",
                "key_insights": ["Insight 1", "Insight 2"],
                "linkedin_recommendations": ["Rec 1", "Rec 2"]
            },
            "data": sample_persona_data,
            "metadata": {"framework_version": "1.0"}
        }
        persona_builder.compile_persona = AsyncMock(return_value=compiled_persona)
        
        # Execute
        result = await persona_builder.export_for_json(session_id)
        
        # Assert
        assert "persona_id" in result
        assert result["persona_id"] == session_id
        assert "created_at" in result
        assert result["ready_for_use"] is True
        assert "summary" in result
        assert "sections" in result
