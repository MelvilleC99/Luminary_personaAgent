"""
Test fixtures for LinkedIn Persona Builder

Provides reusable test data and mock objects
"""

import pytest
from datetime import datetime


@pytest.fixture
def sample_framework_data():
    """Sample framework data matching YAML structure"""
    return {
        "metadata": {
            "version": "1.0",
            "total_sections": 4,
            "estimated_time": "20-25 minutes"
        },
        "sections": {
            "section_1": {
                "name": "Core Expertise & Ideal Customer",
                "section_number": 1,
                "criteria": {
                    "broad_domain_expertise": {
                        "name": "broad_domain_expertise",
                        "question": "What's a broad domain where you have deep expertise?",
                        "good_example": "SaaS marketing strategies",
                        "bad_example": "Business stuff",
                        "threshold": 0.8
                    }
                }
            }
        }
    }
