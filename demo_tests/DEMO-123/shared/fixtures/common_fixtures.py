"""
Shared test fixtures for ticket DEMO-123

This module contains common test fixtures that can be used across multiple test files.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock


@pytest.fixture
def ticket_context():
    """Provide ticket context for all tests."""
    return {
        "ticket_number": "DEMO-123",
        "title": "Database connection timeout in user-service",
        "services": ['authentication', 'is', 'user-service', 'users'],
        "timestamp": datetime.now(),
        "bug_analysis": "Users are experiencing timeouts when trying to authenticate. The user-service is failing to connect to the database after 30 seconds. Error logs show 'Connection timeout after 30000ms' in the authentication module.",
        "root_cause": "",
        "error_patterns": ["logs show 'Connection timeout after 30000ms' in the authentication module.", "timeout after 30000ms' in the authentication module.", "s when trying to authenticate. The user-service is failing to connect to the database after 30 seconds. Error logs show 'Connection timeout after 30000ms' in the authentication module."]
    }


@pytest.fixture
def test_database():
    """Provide a test database connection."""
    # TODO: Set up actual test database or mock
    mock_db = Mock()
    mock_db.query.return_value = []
    mock_db.insert.return_value = True
    mock_db.update.return_value = True
    mock_db.delete.return_value = True
    return mock_db


@pytest.fixture
def test_cache():
    """Provide a test cache instance."""
    mock_cache = Mock()
    mock_cache.get.return_value = None
    mock_cache.set.return_value = True
    mock_cache.delete.return_value = True
    return mock_cache


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "database_url": "sqlite:///:memory:",
        "cache_ttl": 300,
        "api_timeout": 30,
        "retry_attempts": 3,
        "debug": True
    }


@pytest.fixture
def sample_data():
    """Provide sample data for testing."""
    return {
        "valid_record": {
            "id": 1,
            "name": "test_record",
            "created_at": datetime.now().isoformat(),
            "status": "active"
        },
        "invalid_record": {
            "id": None,
            "name": "",
            "created_at": None,
            "status": "invalid"
        },
        "edge_cases": [
            {},  # Empty object
            None,  # Null value
            {"id": 0},  # Zero ID
            {"id": -1},  # Negative ID
            {"name": "x" * 1000}  # Very long name
        ]
    }


@pytest.fixture
def mock_external_services():
    """Provide mocks for external services."""
    return {
        "payment_service": Mock(),
        "notification_service": Mock(),
        "audit_service": Mock(),
        "logging_service": Mock()
    }


@pytest.fixture(scope="session")
def test_session_data():
    """Provide session-level test data."""
    return {
        "session_id": "test_session_123",
        "user_id": "test_user_456",
        "tenant_id": "test_tenant_789"
    }
