"""
Shared mock objects for ticket DEMO-456

This module contains common mock objects that can be reused across tests.
"""

from unittest.mock import Mock, MagicMock
from datetime import datetime


class DatabaseMock:
    """Mock database class with common database operations."""
    
    def __init__(self):
        self.data = {}
        self.call_count = 0
    
    def query(self, sql, params=None):
        """Mock database query."""
        self.call_count += 1
        return []
    
    def insert(self, table, data):
        """Mock database insert."""
        self.call_count += 1
        record_id = len(self.data) + 1
        self.data[record_id] = data
        return record_id
    
    def update(self, table, data, where):
        """Mock database update."""
        self.call_count += 1
        return True
    
    def delete(self, table, where):
        """Mock database delete."""
        self.call_count += 1
        return True


class CacheMock:
    """Mock cache class with common cache operations."""
    
    def __init__(self):
        self.cache = {}
        self.call_count = 0
    
    def get(self, key):
        """Mock cache get."""
        self.call_count += 1
        return self.cache.get(key)
    
    def set(self, key, value, ttl=None):
        """Mock cache set."""
        self.call_count += 1
        self.cache[key] = value
        return True
    
    def delete(self, key):
        """Mock cache delete."""
        self.call_count += 1
        if key in self.cache:
            del self.cache[key]
        return True


class ExternalServiceMock:
    """Mock external service with common API operations."""
    
    def __init__(self, service_name="external_service"):
        self.service_name = service_name
        self.call_count = 0
        self.responses = {}
    
    def get(self, endpoint, params=None):
        """Mock GET request."""
        self.call_count += 1
        return self.responses.get(endpoint, {"status": "success", "data": []})
    
    def post(self, endpoint, data=None):
        """Mock POST request."""
        self.call_count += 1
        return {"status": "created", "id": 123}
    
    def put(self, endpoint, data=None):
        """Mock PUT request."""
        self.call_count += 1
        return {"status": "updated"}
    
    def delete(self, endpoint):
        """Mock DELETE request."""
        self.call_count += 1
        return {"status": "deleted"}
    
    def set_response(self, endpoint, response):
        """Set a specific response for an endpoint."""
        self.responses[endpoint] = response


class ServiceMockFactory:
    """Factory for creating service-specific mocks."""
    
    @staticmethod
    def create_service_mock(service_name, service_config=None):
        """Create a mock for a specific service."""
        mock = Mock()
        mock.name = service_name
        mock.config = service_config or {}
        mock.process.return_value = {"status": "success", "service": service_name}
        mock.validate.return_value = True
        mock.health_check.return_value = {"status": "healthy"}
        return mock
    
    @staticmethod
    def create_error_mock(service_name, error_message="Service error"):
        """Create a mock that raises errors."""
        mock = Mock()
        mock.name = service_name
        mock.process.side_effect = Exception(error_message)
        mock.validate.side_effect = ValueError("Validation error")
        return mock


# Pre-configured mocks for common scenarios
def get_database_mock():
    """Get a pre-configured database mock."""
    return DatabaseMock()


def get_cache_mock():
    """Get a pre-configured cache mock."""
    return CacheMock()


def get_external_service_mock(service_name="external_api"):
    """Get a pre-configured external service mock."""
    return ExternalServiceMock(service_name)


def get_error_service_mock(service_name="error_service"):
    """Get a mock that simulates service errors."""
    return ServiceMockFactory.create_error_mock(service_name)
