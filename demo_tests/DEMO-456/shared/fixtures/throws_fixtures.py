"""
Service-specific fixtures for throws
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def throws_instance():
    """Provide a throws service instance."""
    # TODO: Replace with actual service instantiation
    mock_service = Mock()
    mock_service.process.return_value = {"status": "success"}
    mock_service.validate.return_value = True
    return mock_service


@pytest.fixture
def throws_config():
    """Provide configuration for throws."""
    return {
        "service_name": "throws",
        "language": "javascript",
        "framework": "unknown",
        "test_framework": "jest"
    }


@pytest.fixture
def throws_test_data():
    """Provide test data specific to throws."""
    return {
        "input_data": {"key": "value", "service": "throws"},
        "expected_output": {"result": "processed", "service": "throws"},
        "error_data": {"invalid": True, "service": "throws"}
    }
