"""
Service-specific fixtures for authentication
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def authentication_instance():
    """Provide a authentication service instance."""
    # TODO: Replace with actual service instantiation
    mock_service = Mock()
    mock_service.process.return_value = {"status": "success"}
    mock_service.validate.return_value = True
    return mock_service


@pytest.fixture
def authentication_config():
    """Provide configuration for authentication."""
    return {
        "service_name": "authentication",
        "language": "javascript",
        "framework": "unknown",
        "test_framework": "jest"
    }


@pytest.fixture
def authentication_test_data():
    """Provide test data specific to authentication."""
    return {
        "input_data": {"key": "value", "service": "authentication"},
        "expected_output": {"result": "processed", "service": "authentication"},
        "error_data": {"invalid": True, "service": "authentication"}
    }
