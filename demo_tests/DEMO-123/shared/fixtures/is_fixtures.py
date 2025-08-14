"""
Service-specific fixtures for is
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def is_instance():
    """Provide a is service instance."""
    # TODO: Replace with actual service instantiation
    mock_service = Mock()
    mock_service.process.return_value = {"status": "success"}
    mock_service.validate.return_value = True
    return mock_service


@pytest.fixture
def is_config():
    """Provide configuration for is."""
    return {
        "service_name": "is",
        "language": "javascript",
        "framework": "unknown",
        "test_framework": "jest"
    }


@pytest.fixture
def is_test_data():
    """Provide test data specific to is."""
    return {
        "input_data": {"key": "value", "service": "is"},
        "expected_output": {"result": "processed", "service": "is"},
        "error_data": {"invalid": True, "service": "is"}
    }
