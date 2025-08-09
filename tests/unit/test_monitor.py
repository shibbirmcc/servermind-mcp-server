"""Unit tests for the monitor tool (single session version)."""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.tools.monitor import (
    MonitoringSession, 
    SplunkMonitorTool, 
    get_monitor_tool,
    get_tool_definition,
    execute_monitor
)
from src.config import Config, SplunkConfig, MCPConfig
from src.splunk.client import SplunkClient, SplunkSearchError, SplunkConnectionError
from mcp.types import Tool, TextContent


class TestMonitoringSession:
    """Test cases for MonitoringSession class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.query = "index=main error"
        self.interval = 30
        self.search_params = {"max_results": 500, "timeout": 120}
        
    def test_session_initialization(self):
        """Test MonitoringSession initialization."""
        session = MonitoringSession(
            query=self.query,
            interval=self.interval,
            **self.search_params
        )
        
        assert session.query == self.query
        assert session.interval == self.interval
        assert session.search_params == self.search_params
        assert not session.is_active
        assert session.thread is None
        assert session.last_check_time is None
        assert session.results_buffer == []
        assert session.error_count == 0
        assert session.max_errors == 5
        
    def test_session_status(self):
        """Test getting session status."""
        session = MonitoringSession(
            query=self.query,
            interval=self.interval
        )
        
        status = session.get_status()
        
        assert status['query'] == self.query
        assert status['interval'] == self.interval
        assert not status['is_active']
        assert status['error_count'] == 0
        assert status['results_in_buffer'] == 0
        assert 'created_at' in status
        assert 'last_activity' in status
        
    def test_buffered_results_management(self):
        """Test buffered results management."""
        session = MonitoringSession(
            query=self.query,
            interval=self.interval
        )
        
        # Add some test results
        test_results = [
            {"_time": "2023-01-01T10:00:00", "_raw": "test log 1"},
            {"_time": "2023-01-01T10:01:00", "_raw": "test log 2"}
        ]
        session.results_buffer.extend(test_results)
        
        # Test getting results without clearing
        results = session.get_buffered_results(clear_buffer=False)
        assert len(results) == 2
        assert len(session.results_buffer) == 2  # Buffer should still have results
        
        # Test getting results with clearing
        results = session.get_buffered_results(clear_buffer=True)
        assert len(results) == 2
        assert len(session.results_buffer) == 0  # Buffer should be empty
        
    @patch('src.tools.monitor.SplunkClient')
    @patch('src.tools.monitor.get_config')
    def test_monitor_loop_success(self, mock_get_config, mock_splunk_client):
        """Test successful monitoring loop execution."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock Splunk client
        mock_client_instance = Mock()
        mock_client_instance.execute_search.return_value = [
            {"_time": "2023-01-01T10:00:00", "_raw": "test log"}
        ]
        mock_splunk_client.return_value = mock_client_instance
        
        session = MonitoringSession(
            query=self.query,
            interval=1  # Short interval for testing
        )
        
        # Start session and let it run briefly
        session.start()
        time.sleep(2)  # Let it run for 2 seconds
        session.stop()
        
        # Verify client was called
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.execute_search.assert_called()
        mock_client_instance.disconnect.assert_called_once()
        
        # Verify results were collected
        assert len(session.results_buffer) > 0
        assert session.error_count == 0
        
    @patch('src.tools.monitor.SplunkClient')
    @patch('src.tools.monitor.get_config')
    def test_monitor_loop_error_handling(self, mock_get_config, mock_splunk_client):
        """Test error handling in monitoring loop."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock Splunk client to raise errors
        mock_client_instance = Mock()
        mock_client_instance.execute_search.side_effect = SplunkSearchError("Search failed")
        mock_splunk_client.return_value = mock_client_instance
        
        session = MonitoringSession(
            query=self.query,
            interval=1,  # Short interval for testing
            max_results=100
        )
        session.max_errors = 2  # Lower max errors for faster testing
        
        # Start session and let it run briefly
        session.start()
        time.sleep(3)  # Let it run long enough to hit max errors
        
        # Session should stop itself after max errors
        assert not session.is_active
        assert session.error_count >= session.max_errors
        
    def test_session_start_stop(self):
        """Test session start and stop functionality."""
        session = MonitoringSession(
            query=self.query,
            interval=60
        )
        
        # Initially not active
        assert not session.is_active
        assert session.thread is None
        
        # Start session
        with patch.object(session, '_monitor_loop'):
            session.start()
            assert session.is_active
            assert session.thread is not None
            
            # Stop session
            session.stop()
            assert not session.is_active


class TestSplunkMonitorTool:
    """Test cases for SplunkMonitorTool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SplunkMonitorTool()
        
    def test_tool_initialization(self):
        """Test SplunkMonitorTool initialization."""
        assert self.tool.current_session is None
        assert hasattr(self.tool, '_lock')
        
    def test_get_tool_definition(self):
        """Test getting tool definition."""
        definition = self.tool.get_tool_definition()
        
        assert isinstance(definition, Tool)
        assert definition.name == "splunk_monitor"
        assert "continuous monitoring" in definition.description.lower()
        
        # Check input schema
        schema = definition.inputSchema
        assert schema['type'] == 'object'
        assert 'action' in schema['properties']
        assert 'query' in schema['properties']
        assert 'interval' in schema['properties']
        
        # Check action enum values
        action_enum = schema['properties']['action']['enum']
        expected_actions = ["start", "stop", "status", "get_results"]
        assert all(action in action_enum for action in expected_actions)
        
    @pytest.mark.asyncio
    async def test_start_monitoring_success(self):
        """Test successful monitoring start."""
        arguments = {
            "action": "start",
            "query": "index=main error",
            "interval": 60
        }
        
        with patch.object(MonitoringSession, 'start') as mock_start:
            results = await self.tool.execute(arguments)
            
            assert len(results) == 1
            assert isinstance(results[0], TextContent)
            assert "Monitoring Session Started" in results[0].text
            assert "index=main error" in results[0].text
            
            # Verify session was created and started
            assert self.tool.current_session is not None
            mock_start.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_start_monitoring_missing_query(self):
        """Test starting monitoring without query."""
        arguments = {
            "action": "start",
            "interval": 60
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitor Tool Error" in results[0].text
        assert "Query parameter is required" in results[0].text
        
    @pytest.mark.asyncio
    async def test_start_monitoring_invalid_interval(self):
        """Test starting monitoring with invalid interval."""
        arguments = {
            "action": "start",
            "query": "index=main error",
            "interval": 5  # Too short
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitor Tool Error" in results[0].text
        assert "Interval must be between 10 and 3600 seconds" in results[0].text
        
    @pytest.mark.asyncio
    async def test_start_monitoring_replaces_existing(self):
        """Test starting monitoring replaces existing session."""
        # Create an existing session
        existing_session = Mock()
        existing_session.is_active = True
        self.tool.current_session = existing_session
        
        arguments = {
            "action": "start",
            "query": "index=main error"
        }
        
        with patch.object(MonitoringSession, 'start') as mock_start:
            results = await self.tool.execute(arguments)
            
            assert len(results) == 1
            assert "Monitoring Session Started" in results[0].text
            
            # Verify old session was stopped
            existing_session.stop.assert_called_once()
            
            # Verify new session was created
            assert self.tool.current_session is not None
            mock_start.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_stop_monitoring_success(self):
        """Test successful monitoring stop."""
        # Create a session first
        session = Mock()
        self.tool.current_session = session
        
        arguments = {
            "action": "stop"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitoring Session Stopped" in results[0].text
        assert self.tool.current_session is None
        session.stop.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_stop_monitoring_not_found(self):
        """Test stopping when no monitoring session exists."""
        arguments = {
            "action": "stop"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitor Tool Error" in results[0].text
        assert "No active monitoring session found" in results[0].text
        
    @pytest.mark.asyncio
    async def test_get_status_success(self):
        """Test getting session status."""
        # Create a mock session
        session = Mock()
        session.get_status.return_value = {
            'query': 'index=main error',
            'interval': 60,
            'is_active': True,
            'created_at': '2023-01-01T10:00:00',
            'last_activity': '2023-01-01T10:05:00',
            'last_check_time': '2023-01-01T10:05:00',
            'error_count': 0,
            'results_in_buffer': 5
        }
        self.tool.current_session = session
        
        arguments = {
            "action": "status"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitoring Session Status" in results[0].text
        assert "index=main error" in results[0].text
        assert "🟢 Active" in results[0].text
        assert "Buffered Results:** 5" in results[0].text
        
    @pytest.mark.asyncio
    async def test_get_status_no_session(self):
        """Test getting status when no session exists."""
        arguments = {
            "action": "status"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "No Active Monitoring Session" in results[0].text
        
    @pytest.mark.asyncio
    async def test_get_results_success(self):
        """Test getting monitoring results."""
        # Create a mock session with results
        session = Mock()
        test_results = [
            {
                "_time": "2023-01-01T10:00:00",
                "_raw": "test error log",
                "_monitoring_check_time": "2023-01-01T10:00:00"
            }
        ]
        session.get_buffered_results.return_value = test_results
        self.tool.current_session = session
        
        arguments = {
            "action": "get_results"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitoring Results" in results[0].text
        assert "Results Count:** 1" in results[0].text
        assert "test error log" in results[0].text
        session.get_buffered_results.assert_called_once_with(clear_buffer=True)
        
    @pytest.mark.asyncio
    async def test_get_results_no_results(self):
        """Test getting results when none available."""
        # Create a mock session with no results
        session = Mock()
        session.get_buffered_results.return_value = []
        self.tool.current_session = session
        
        arguments = {
            "action": "get_results"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "No Results Available" in results[0].text
        
    @pytest.mark.asyncio
    async def test_get_results_no_session(self):
        """Test getting results when no session exists."""
        arguments = {
            "action": "get_results"
        }
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitor Tool Error" in results[0].text
        assert "No active monitoring session found" in results[0].text
        
    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """Test handling invalid action."""
        arguments = {"action": "invalid_action"}
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitor Tool Error" in results[0].text
        assert "Unknown action" in results[0].text
        
    @pytest.mark.asyncio
    async def test_missing_action(self):
        """Test handling missing action parameter."""
        arguments = {}
        
        results = await self.tool.execute(arguments)
        
        assert len(results) == 1
        assert "Monitor Tool Error" in results[0].text
        assert "Action parameter is required" in results[0].text
        
    def test_generate_monitoring_analysis(self):
        """Test monitoring analysis generation."""
        test_results = [
            {
                "_time": "2023-01-01T10:00:00",
                "_raw": "error in application",
                "host": "server1",
                "source": "/var/log/app.log",
                "sourcetype": "application"
            },
            {
                "_time": "2023-01-01T10:01:00",
                "_raw": "critical failure detected",
                "host": "server2",
                "source": "/var/log/app.log",
                "sourcetype": "application"
            }
        ]
        
        analysis = self.tool._generate_monitoring_analysis(test_results)
        
        assert "Analysis Suggestions" in analysis
        assert "Host Analysis:** 2 unique hosts detected" in analysis
        assert "Source Type Analysis:** 1 unique source types" in analysis
        assert "Volume Analysis:** 2 events collected" in analysis
        assert "⚠️ Alert:** 2 events contain error-related keywords" in analysis
        assert "Recommendations:" in analysis
        
    def test_generate_monitoring_analysis_empty(self):
        """Test monitoring analysis with empty results."""
        analysis = self.tool._generate_monitoring_analysis([])
        
        assert analysis == ""
        
    def test_cleanup(self):
        """Test cleanup functionality."""
        # Create mock session
        session = Mock()
        self.tool.current_session = session
        
        self.tool.cleanup()
        
        # Verify session was stopped and cleared
        session.stop.assert_called_once()
        assert self.tool.current_session is None


class TestModuleFunctions:
    """Test module-level functions."""
    
    def test_get_monitor_tool(self):
        """Test get_monitor_tool function."""
        tool = get_monitor_tool()
        assert isinstance(tool, SplunkMonitorTool)
        
        # Should return the same instance (singleton pattern)
        tool2 = get_monitor_tool()
        assert tool is tool2
        
    def test_get_tool_definition(self):
        """Test get_tool_definition function."""
        definition = get_tool_definition()
        assert isinstance(definition, Tool)
        assert definition.name == "splunk_monitor"
        
    @pytest.mark.asyncio
    async def test_execute_monitor(self):
        """Test execute_monitor function."""
        arguments = {"action": "status"}
        
        results = await execute_monitor(arguments)
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert isinstance(results[0], TextContent)


class TestThreadSafety:
    """Test thread safety of monitoring tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SplunkMonitorTool()
        
    def test_concurrent_session_access(self):
        """Test concurrent session access."""
        # Create a session
        session = Mock()
        session.get_status.return_value = {"query": "test", "is_active": True}
        self.tool.current_session = session
        
        results = []
        
        def access_session():
            with self.tool._lock:
                if self.tool.current_session:
                    status = self.tool.current_session.get_status()
                    results.append(status)
                    
        threads = []
        for i in range(5):
            thread = threading.Thread(target=access_session)
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()
            
        # All threads should have accessed the session successfully
        assert len(results) == 5
        assert all(result["query"] == "test" for result in results)


if __name__ == "__main__":
    pytest.main([__file__])
