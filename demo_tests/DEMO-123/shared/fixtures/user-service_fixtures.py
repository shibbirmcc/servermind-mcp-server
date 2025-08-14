"""
Service-specific fixtures for user-service
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def user-service_instance():
    """Provide a user-service service instance."""
    # TODO: Replace with actual service instantiation
    mock_service = Mock()
    mock_service.process.return_value = {"status": "success"}
    mock_service.validate.return_value = True
    return mock_service


@pytest.fixture
def user-service_config():
    """Provide configuration for user-service."""
    return {
        "service_name": "user-service",
        "language": "javascript",
        "framework": "unknown",
        "test_framework": "jest"
    }


@pytest.fixture
def user-service_test_data():
    """Provide test data specific to user-service."""
    return {
        "input_data": {"key": "value", "service": "user-service"},
        "expected_output": {"result": "processed", "service": "user-service"},
        "error_data": {"invalid": True, "service": "user-service"}
    }
