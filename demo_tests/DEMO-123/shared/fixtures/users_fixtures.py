"""
Service-specific fixtures for users
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def users_instance():
    """Provide a users service instance."""
    # TODO: Replace with actual service instantiation
    mock_service = Mock()
    mock_service.process.return_value = {"status": "success"}
    mock_service.validate.return_value = True
    return mock_service


@pytest.fixture
def users_config():
    """Provide configuration for users."""
    return {
        "service_name": "users",
        "language": "javascript",
        "framework": "unknown",
        "test_framework": "jest"
    }


@pytest.fixture
def users_test_data():
    """Provide test data specific to users."""
    return {
        "input_data": {"key": "value", "service": "users"},
        "expected_output": {"result": "processed", "service": "users"},
        "error_data": {"invalid": True, "service": "users"}
    }
