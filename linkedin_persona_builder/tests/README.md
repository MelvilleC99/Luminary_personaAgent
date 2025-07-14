# LinkedIn Persona Builder - Testing Guide

## Overview

This document provides a comprehensive guide for testing the LinkedIn Persona Builder project. The test suite is organized into unit tests and integration tests to ensure code quality and reliability.

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration
├── fixtures/            # Test data and fixtures
│   └── test_data.py    # Reusable test fixtures
├── unit/               # Unit tests for individual components
│   ├── test_persona_builder.py
│   ├── test_validation_manager.py
│   ├── test_state_manager.py
│   ├── test_coordinator.py
│   └── test_api_endpoints.py
└── integration/        # Integration tests
    └── test_full_flow.py
```

## Running Tests

### Quick Start

```bash
# Run all tests
python run_tests.py

# Run only unit tests
python run_tests.py unit

# Run only integration tests
python run_tests.py integration

# Run with verbose output
python run_tests.py -v

# Run with coverage report
python run_tests.py -c
```


### Using Pytest Directly

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_persona_builder.py

# Run specific test
pytest tests/unit/test_persona_builder.py::TestPersonaBuilder::test_compile_persona_success

# Run with markers
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Test Categories

### 1. Unit Tests

Unit tests focus on testing individual components in isolation.

#### PersonaBuilder Tests (`test_persona_builder.py`)
- ✅ Persona compilation
- ✅ Completeness validation
- ✅ Key insights extraction
- ✅ Modification handling
- ✅ JSON export functionality

#### ValidationManager Tests (`test_validation_manager.py`)
- ✅ Consistency checking
- ✅ Conflict detection
- ✅ Empty data handling

#### StateManager Tests (`test_state_manager.py`)
- ✅ Data retrieval
- ✅ Data persistence
- ✅ Session management

#### Coordinator Tests (`test_coordinator.py`)
- ✅ Request routing
- ✅ Response formatting
- ✅ Error handling

#### API Endpoint Tests (`test_api_endpoints.py`)
- ✅ Health check endpoint
- ✅ Chat endpoint
- ✅ Request validation
- ✅ Error responses


### 2. Integration Tests

Integration tests verify that components work correctly together.

#### Full Flow Tests (`test_full_flow.py`)
- ✅ Complete persona building conversation
- ✅ Concurrent session handling
- ✅ Data persistence across requests

## Writing New Tests

### Test Structure Template

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestYourComponent:
    @pytest.fixture
    def your_component(self):
        """Create component with mocked dependencies"""
        # Setup mocks
        return component
    
    @pytest.mark.asyncio
    async def test_async_function(self, your_component):
        """Test description"""
        # Arrange
        # Act
        # Assert
```

### Best Practices

1. **Use descriptive test names** - Test names should clearly indicate what is being tested
2. **Follow AAA pattern** - Arrange, Act, Assert
3. **Mock external dependencies** - Use unittest.mock for isolation
4. **Test edge cases** - Include tests for error conditions
5. **Use fixtures** - Reuse common test data and setup

## Coverage Goals

- Unit test coverage: >80%
- Integration test coverage: >60%
- Critical path coverage: 100%

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    - name: Run tests
      run: python run_tests.py -c
```
