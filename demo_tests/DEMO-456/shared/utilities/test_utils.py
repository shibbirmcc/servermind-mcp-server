"""
Shared test utilities for ticket DEMO-456

This module contains utility functions that can be used across multiple test files.
"""

import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch


class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_valid_data(service_name: str) -> Dict[str, Any]:
        """Generate valid test data for a service."""
        return {
            "id": 1,
            "service": service_name,
            "timestamp": datetime.now().isoformat(),
            "status": "active",
            "data": {"key": "value", "number": 42}
        }
    
    @staticmethod
    def generate_invalid_data(service_name: str) -> Dict[str, Any]:
        """Generate invalid test data for a service."""
        return {
            "id": None,
            "service": service_name,
            "timestamp": "invalid_date",
            "status": "",
            "data": None
        }
    
    @staticmethod
    def generate_edge_case_data() -> List[Dict[str, Any]]:
        """Generate edge case test data."""
        return [
            {},  # Empty object
            None,  # Null value
            {"id": 0},  # Zero ID
            {"id": -1},  # Negative ID
            {"very_long_field": "x" * 10000},  # Very long data
            {"unicode": "🚀🔥💯"},  # Unicode characters
            {"nested": {"deep": {"very": {"deep": "value"}}}},  # Deep nesting
        ]


class TestAssertions:
    """Custom assertion helpers for tests."""
    
    @staticmethod
    def assert_service_response(response: Dict[str, Any], expected_status: str = "success"):
        """Assert that a service response has the expected format."""
        assert isinstance(response, dict), "Response should be a dictionary"
        assert "status" in response, "Response should have a status field"
        assert response["status"] == expected_status, f"Expected status {expected_status}, got {response['status']}"
    
    @staticmethod
    def assert_error_response(response: Dict[str, Any], expected_error_type: str = None):
        """Assert that an error response has the expected format."""
        assert isinstance(response, dict), "Error response should be a dictionary"
        assert "error" in response or "status" in response, "Error response should have error or status field"
        
        if expected_error_type:
            error_info = response.get("error", response.get("status", ""))
            assert expected_error_type.lower() in str(error_info).lower(), \
                   f"Expected error type {expected_error_type} not found in {error_info}"
    
    @staticmethod
    def assert_performance_threshold(execution_time: float, max_time: float = 5.0):
        """Assert that execution time is within acceptable limits."""
        assert execution_time < max_time, \
               f"Performance threshold exceeded: {execution_time}s > {max_time}s"


class TestEnvironment:
    """Utilities for setting up and tearing down test environments."""
    
    @staticmethod
    def setup_test_environment(services: List[str]) -> Dict[str, Mock]:
        """Set up a test environment with mocked services."""
        mocked_services = {}
        
        for service_name in services:
            mock_service = Mock()
            mock_service.name = service_name
            mock_service.process.return_value = {"status": "success", "service": service_name}
            mock_service.health_check.return_value = {"status": "healthy"}
            mocked_services[service_name] = mock_service
        
        return mocked_services
    
    @staticmethod
    def cleanup_test_environment(mocked_services: Dict[str, Mock]):
        """Clean up test environment."""
        for service_name, mock_service in mocked_services.items():
            mock_service.reset_mock()
    
    @staticmethod
    def create_test_database():
        """Create a test database instance."""
        # TODO: Implement actual test database setup
        mock_db = Mock()
        mock_db.query.return_value = []
        mock_db.insert.return_value = True
        return mock_db


class AsyncTestUtils:
    """Utilities for testing async operations."""
    
    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run an async operation with a timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"Operation timed out after {timeout} seconds")
    
    @staticmethod
    async def simulate_async_delay(delay: float = 0.1):
        """Simulate an async delay for testing."""
        await asyncio.sleep(delay)
    
    @staticmethod
    def create_async_mock():
        """Create a mock that supports async operations."""
        mock = Mock()
        mock.async_method = AsyncMock()
        return mock


class PerformanceTestUtils:
    """Utilities for performance testing."""
    
    @staticmethod
    def measure_execution_time(func, *args, **kwargs):
        """Measure the execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    @staticmethod
    async def measure_async_execution_time(coro):
        """Measure the execution time of an async operation."""
        start_time = time.time()
        result = await coro
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    @staticmethod
    def create_load_test_data(count: int = 1000) -> List[Dict[str, Any]]:
        """Create a large dataset for load testing."""
        return [
            {
                "id": i,
                "data": f"test_data_{i}",
                "timestamp": datetime.now().isoformat()
            }
            for i in range(count)
        ]


# Convenience functions
def create_test_context(ticket_number: str, services: List[str]) -> Dict[str, Any]:
    """Create a test context with common test data."""
    return {
        "ticket_number": ticket_number,
        "services": services,
        "timestamp": datetime.now(),
        "test_data": TestDataGenerator.generate_valid_data("test_service"),
        "mocked_services": TestEnvironment.setup_test_environment(services)
    }


def assert_no_errors(response: Dict[str, Any]):
    """Assert that a response contains no errors."""
    assert "error" not in response or response["error"] is None, \
           f"Unexpected error in response: {response.get('error')}"


def wait_for_condition(condition_func, timeout: float = 10.0, interval: float = 0.1):
    """Wait for a condition to become true."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    
    raise AssertionError(f"Condition not met within {timeout} seconds")


# Import AsyncMock for Python 3.8+ compatibility
try:
    from unittest.mock import AsyncMock
except ImportError:
    # Fallback for older Python versions
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)
