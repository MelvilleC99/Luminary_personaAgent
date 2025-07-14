"""
Unit tests for FrameworkLoader

Tests YAML framework loading and parsing
"""

import pytest
from unittest.mock import Mock, patch, mock_open
import yaml

from knowledge.framework_loader import FrameworkLoader


class TestFrameworkLoader:
    """Test suite for FrameworkLoader class"""
    
    @pytest.fixture
    def framework_loader(self):
        """Create a FrameworkLoader instance"""
        return FrameworkLoader()
    
    @pytest.fixture
    def sample_yaml_content(self):
        """Sample YAML content for testing"""
        return """
framework:
  metadata:
    version: "1.0"
    total_sections: 2
  section_1:
    name: "Test Section"
    section_number: 1
    criteria:
      test_criterion:
        name: "test_criterion"
        question: "Test question?"
        good_example: "Good answer"
        bad_example: "Bad answer"
"""
    
    def test_load_framework_success(self, framework_loader, sample_yaml_content):
        """Test successful framework loading"""
        with patch('builtins.open', mock_open(read_data=sample_yaml_content)):
            framework = framework_loader.load_current()
            
            assert framework is not None
            assert framework.metadata.version == "1.0"
            assert framework.metadata.total_sections == 2
            assert len(framework.sections) == 1
            assert "section_1" in framework.sections
    
    def test_load_framework_file_not_found(self, framework_loader):
        """Test handling of missing framework file"""
        with patch('builtins.open', side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                framework_loader.load_current()
    
    def test_parse_yaml_invalid(self, framework_loader):
        """Test handling of invalid YAML"""
        invalid_yaml = "invalid: yaml: content:"
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with patch('yaml.safe_load', side_effect=yaml.YAMLError):
                with pytest.raises(yaml.YAMLError):
                    framework_loader.load_current()
