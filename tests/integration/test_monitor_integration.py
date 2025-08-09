"""Integration tests for the monitor tool (single session version)."""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from datetime import datetime

from src.tools.monitor import (
    SplunkMonitorTool, 
    get_monitor_tool,
    execute_monitor
)
from src.config import get_config
from mcp.types import TextContent


class TestMonitorIntegration:
    """Integration tests for the monitoring tool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SplunkMonitorTool()
        
    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow: start -> status -> get_results -> stop."""
        
        # Mock the Splunk client to avoid real connections
        with patch('src.tools.monitor.SplunkClient') as mock_client_class, \
             patch('src.tools.monitor.get_config') as mock_get_config:
            
            # Setup mocks
            mock_config = Mock()
            mock_config.splunk = Mock()
            mock_get_config.return_value = mock_config
            
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.execute_search.return_value = [
                {
                    "_time": "2023-01-01T10:00:00",
                    "_raw": "test error message",
                    "host": "test-server",
                    "source": "/var/log/test.log",
                    "sourcetype": "test_logs"
                }
            ]
            
            # Step 1: Start monitoring
            start_args = {
                "action": "start",
                "query": "index=test error",
                "interval": 30,
                "max_results": 100
            }
            
            results = await self.tool.execute(start_args)
            assert len(results) == 1
            assert "Monitoring Session Started" in results[0].text
            assert "index=test error" in results[0].text
            assert "30 seconds" in results[0].text
            
            # Verify session was created
            assert self.tool.current_session is not None
            assert self.tool.current_session.query == "index=test error"
            assert self.tool.current_session.interval == 30
            
            # Step 2: Check status
            status_args = {"action": "status"}
            results = await self.tool.execute(status_args)
            assert len(results) == 1
            assert "Monitoring Session Status" in results[0].text
            assert "index=test error" in results[0].text
            
            # Step 3: Simulate some monitoring activity by adding results to buffer
            test_results = [
                {
                    "_time": "2023-01-01T10:00:00",
                    "_raw": "test error message",
                    "_monitoring_check_time": datetime.now().isoformat()
                }
            ]
            self.tool.current_session.results_buffer.extend(test_results)
            
            # Step 4: Get results
            results_args = {"action": "get_results"}
            results = await self.tool.execute(results_args)
            assert len(results) == 1
            assert "Monitoring Results" in results[0].text
            # The count might be 1 or 2 depending on timing of the monitoring thread
            assert "Results Count:**" in results[0].text
            assert "test error message" in results[0].text
            
            # Step 5: Stop monitoring
            stop_args = {"action": "stop"}
            results = await self.tool.execute(stop_args)
            assert len(results) == 1
            assert "Monitoring Session Stopped" in results[0].text
            
            # Verify session was removed
            assert self.tool.current_session is None
            
    @pytest.mark.asyncio
    async def test_monitoring_session_replacement(self):
        """Test that starting a new session replaces the existing one."""
        
        with patch('src.tools.monitor.SplunkClient') as mock_client_class, \
             patch('src.tools.monitor.get_config') as mock_get_config:
            
            # Setup mocks
            mock_config = Mock()
            mock_config.splunk = Mock()
            mock_get_config.return_value = mock_config
            
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.execute_search.return_value = []
            
            # Start first session
            start_args1 = {
                "action": "start",
                "query": "index=main error",
                "interval": 60
            }
            
            results = await self.tool.execute(start_args1)
            assert "Monitoring Session Started" in results[0].text
            
            first_session = self.tool.current_session
            assert first_session is not None
            assert first_session.query == "index=main error"
            
            # Start second session (should replace first)
            start_args2 = {
                "action": "start",
                "query": "index=web status=500",
                "interval": 30
            }
            
            results = await self.tool.execute(start_args2)
            assert "Monitoring Session Started" in results[0].text
            
            second_session = self.tool.current_session
            assert second_session is not None
            assert second_session.query == "index=web status=500"
            assert second_session is not first_session
            
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in various scenarios."""
        
        # Test 1: Start without query
        start_args = {"action": "start", "interval": 60}
        results = await self.tool.execute(start_args)
        assert "Monitor Tool Error" in results[0].text
        assert "Query parameter is required" in results[0].text
        
        # Test 2: Invalid interval
        start_args = {
            "action": "start",
            "query": "index=main",
            "interval": 5  # Too short
        }
        results = await self.tool.execute(start_args)
        assert "Monitor Tool Error" in results[0].text
        assert "Interval must be between 10 and 3600 seconds" in results[0].text
        
        # Test 3: Stop when no session exists
        stop_args = {"action": "stop"}
        results = await self.tool.execute(stop_args)
        assert "Monitor Tool Error" in results[0].text
        assert "No active monitoring session found" in results[0].text
        
        # Test 4: Get results when no session exists
        results_args = {"action": "get_results"}
        results = await self.tool.execute(results_args)
        assert "Monitor Tool Error" in results[0].text
        assert "No active monitoring session found" in results[0].text
        
        # Test 5: Status when no session exists
        status_args = {"action": "status"}
        results = await self.tool.execute(status_args)
        assert "No Active Monitoring Session" in results[0].text
        
        # Test 6: Invalid action
        invalid_args = {"action": "invalid"}
        results = await self.tool.execute(invalid_args)
        assert "Monitor Tool Error" in results[0].text
        assert "Unknown action" in results[0].text
        
    @pytest.mark.asyncio
    async def test_monitoring_analysis_generation(self):
        """Test monitoring analysis generation with various data patterns."""
        
        with patch('src.tools.monitor.SplunkClient') as mock_client_class, \
             patch('src.tools.monitor.get_config') as mock_get_config:
            
            # Setup mocks
            mock_config = Mock()
            mock_config.splunk = Mock()
            mock_get_config.return_value = mock_config
            
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.execute_search.return_value = []
            
            # Start monitoring session
            start_args = {
                "action": "start",
                "query": "index=main",
                "interval": 60
            }
            await self.tool.execute(start_args)
            
            # Add diverse test results to buffer
            test_results = [
                {
                    "_time": "2023-01-01T10:00:00",
                    "_raw": "ERROR: Database connection failed",
                    "host": "web-server-1",
                    "source": "/var/log/app.log",
                    "sourcetype": "application",
                    "_monitoring_check_time": "2023-01-01T10:00:00"
                },
                {
                    "_time": "2023-01-01T10:01:00",
                    "_raw": "CRITICAL: Memory usage exceeded threshold",
                    "host": "web-server-2",
                    "source": "/var/log/system.log",
                    "sourcetype": "system",
                    "_monitoring_check_time": "2023-01-01T10:00:00"
                },
                {
                    "_time": "2023-01-01T10:02:00",
                    "_raw": "INFO: User login successful",
                    "host": "web-server-1",
                    "source": "/var/log/auth.log",
                    "sourcetype": "authentication",
                    "_monitoring_check_time": "2023-01-01T10:00:00"
                }
            ]
            
            self.tool.current_session.results_buffer.extend(test_results)
            
            # Get results and check analysis
            results_args = {"action": "get_results"}
            results = await self.tool.execute(results_args)
            
            result_text = results[0].text
            
            # Check that analysis is included
            assert "Analysis Suggestions" in result_text
            assert "Host Analysis" in result_text
            assert "2 unique hosts detected" in result_text
            assert "Source Type Analysis" in result_text
            assert "3 unique source types" in result_text
            assert "Volume Analysis" in result_text
            assert "3 events collected" in result_text
            assert "⚠️ Alert" in result_text  # Should detect error keywords
            assert "Recommendations" in result_text
            
    @pytest.mark.asyncio
    async def test_buffer_management(self):
        """Test result buffer management and clearing."""
        
        with patch('src.tools.monitor.SplunkClient') as mock_client_class, \
             patch('src.tools.monitor.get_config') as mock_get_config:
            
            # Setup mocks
            mock_config = Mock()
            mock_config.splunk = Mock()
            mock_get_config.return_value = mock_config
            
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.execute_search.return_value = []
            
            # Start monitoring session
            start_args = {
                "action": "start",
                "query": "index=main",
                "interval": 60
            }
            await self.tool.execute(start_args)
            
            # Add test results
            test_results = [
                {"_time": "2023-01-01T10:00:00", "_raw": "test log 1"},
                {"_time": "2023-01-01T10:01:00", "_raw": "test log 2"}
            ]
            self.tool.current_session.results_buffer.extend(test_results)
            
            # Get results without clearing buffer
            results_args = {"action": "get_results", "clear_buffer": False}
            results = await self.tool.execute(results_args)
            assert "Results Count:** 2" in results[0].text
            assert "Buffer Cleared:** No" in results[0].text
            
            # Buffer should still have results
            assert len(self.tool.current_session.results_buffer) == 2
            
            # Get results with clearing buffer (default)
            results_args = {"action": "get_results"}
            results = await self.tool.execute(results_args)
            assert "Results Count:** 2" in results[0].text
            assert "Buffer Cleared:** Yes" in results[0].text
            
            # Buffer should now be empty
            assert len(self.tool.current_session.results_buffer) == 0
            
            # Next call should return no results
            results_args = {"action": "get_results"}
            results = await self.tool.execute(results_args)
            assert "No Results Available" in results[0].text
            
    @pytest.mark.asyncio
    async def test_module_functions(self):
        """Test module-level functions work correctly."""
        
        # Test get_monitor_tool returns singleton
        tool1 = get_monitor_tool()
        tool2 = get_monitor_tool()
        assert tool1 is tool2
        assert isinstance(tool1, SplunkMonitorTool)
        
        # Test execute_monitor function
        with patch('src.tools.monitor.SplunkClient') as mock_client_class, \
             patch('src.tools.monitor.get_config') as mock_get_config:
            
            # Setup mocks
            mock_config = Mock()
            mock_config.splunk = Mock()
            mock_get_config.return_value = mock_config
            
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.execute_search.return_value = []
            
            # Test status when no session
            results = await execute_monitor({"action": "status"})
            assert isinstance(results, list)
            assert len(results) == 1
            assert isinstance(results[0], TextContent)
            assert "No Active Monitoring Session" in results[0].text
            
    def test_cleanup_functionality(self):
        """Test cleanup stops active sessions."""
        
        # Create a mock session
        mock_session = Mock()
        self.tool.current_session = mock_session
        
        # Call cleanup
        self.tool.cleanup()
        
        # Verify session was stopped and cleared
        mock_session.stop.assert_called_once()
        assert self.tool.current_session is None


if __name__ == "__main__":
    pytest.main([__file__])
