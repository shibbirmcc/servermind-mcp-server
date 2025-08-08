"""Unit tests for the indexes tool."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from mcp.types import TextContent

from src.tools.indexes import SplunkIndexesTool, get_indexes_tool, execute_indexes
from src.splunk.client import SplunkConnectionError


class TestSplunkIndexesTool:
    """Test cases for SplunkIndexesTool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SplunkIndexesTool()
    
    def test_get_tool_definition(self):
        """Test tool definition generation."""
        tool_def = self.tool.get_tool_definition()
        
        assert tool_def.name == "splunk_indexes"
        assert "List and get information about Splunk indexes" in tool_def.description
        assert "filter_pattern" in tool_def.inputSchema["properties"]
        assert "include_disabled" in tool_def.inputSchema["properties"]
        assert "sort_by" in tool_def.inputSchema["properties"]
        assert "sort_order" in tool_def.inputSchema["properties"]
    
    @patch('src.tools.indexes.get_config')
    @patch('src.tools.indexes.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_client_class, mock_get_config):
        """Test successful execution of indexes tool."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock index data
        mock_indexes = [
            {
                'name': 'main',
                'total_event_count': 1000,
                'current_db_size_mb': 50.5,
                'max_data_size': 'auto',
                'disabled': False,
                'earliest_time': '2024-01-01T00:00:00',
                'latest_time': '2024-01-02T00:00:00'
            },
            {
                'name': 'security',
                'total_event_count': 500,
                'current_db_size_mb': 25.0,
                'max_data_size': '1GB',
                'disabled': False,
                'earliest_time': '2024-01-01T12:00:00',
                'latest_time': '2024-01-02T12:00:00'
            }
        ]
        mock_client.get_indexes.return_value = mock_indexes
        
        # Execute tool
        arguments = {
            'sort_by': 'name',
            'sort_order': 'asc'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✅ **Splunk Indexes Retrieved**" in result[0].text
        assert "**Total Indexes:** 2" in result[0].text
        assert "main" in result[0].text
        assert "security" in result[0].text
        assert "1,000" in result[0].text  # Event count formatting
        assert "50.5 MB" in result[0].text  # Size formatting
        
        # Verify client was called correctly
        mock_client.get_indexes.assert_called_once_with(filter_pattern=None)
    
    @patch('src.tools.indexes.get_config')
    @patch('src.tools.indexes.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_with_filter(self, mock_client_class, mock_get_config):
        """Test execution with filter pattern."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock filtered index data
        mock_indexes = [
            {
                'name': 'security',
                'total_event_count': 500,
                'current_db_size_mb': 25.0,
                'max_data_size': '1GB',
                'disabled': False,
                'earliest_time': '2024-01-01T12:00:00',
                'latest_time': '2024-01-02T12:00:00'
            }
        ]
        mock_client.get_indexes.return_value = mock_indexes
        
        # Execute tool with filter
        arguments = {
            'filter_pattern': 'sec',
            'sort_by': 'events',
            'sort_order': 'desc'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results
        assert len(result) == 1
        assert "**Filter Applied:** `sec`" in result[0].text
        assert "**Sorted By:** events (desc)" in result[0].text
        assert "security" in result[0].text
        
        # Verify client was called with filter
        mock_client.get_indexes.assert_called_once_with(filter_pattern='sec')
    
    @patch('src.tools.indexes.get_config')
    @patch('src.tools.indexes.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_exclude_disabled(self, mock_client_class, mock_get_config):
        """Test execution excluding disabled indexes."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock index data with disabled index
        mock_indexes = [
            {
                'name': 'main',
                'total_event_count': 1000,
                'current_db_size_mb': 50.5,
                'disabled': False
            },
            {
                'name': 'old_index',
                'total_event_count': 0,
                'current_db_size_mb': 0,
                'disabled': True
            }
        ]
        mock_client.get_indexes.return_value = mock_indexes
        
        # Execute tool excluding disabled
        arguments = {
            'include_disabled': False
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results - should only show active index
        assert "**Total Indexes:** 1" in result[0].text
        assert "main" in result[0].text
        assert "old_index" not in result[0].text
    
    @patch('src.tools.indexes.get_config')
    @patch('src.tools.indexes.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_connection_error(self, mock_client_class, mock_get_config):
        """Test execution with connection error."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock client to raise connection error
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_indexes.side_effect = SplunkConnectionError("Connection failed")
        
        # Execute tool
        result = await self.tool.execute({})
        
        # Verify error handling
        assert len(result) == 1
        assert "❌ **Splunk Connection Error**" in result[0].text
        assert "Connection failed" in result[0].text
    
    @patch('src.tools.indexes.get_config')
    @patch('src.tools.indexes.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_unexpected_error(self, mock_client_class, mock_get_config):
        """Test execution with unexpected error."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_get_config.return_value = mock_config
        
        # Mock client to raise unexpected error
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_indexes.side_effect = Exception("Unexpected error")
        
        # Execute tool
        result = await self.tool.execute({})
        
        # Verify error handling
        assert len(result) == 1
        assert "❌ **Unexpected Error**" in result[0].text
        assert "Unexpected error" in result[0].text
    
    def test_sort_indexes_by_name(self):
        """Test sorting indexes by name."""
        indexes = [
            {'name': 'zebra', 'total_event_count': 100},
            {'name': 'alpha', 'total_event_count': 200},
            {'name': 'beta', 'total_event_count': 150}
        ]
        
        # Sort ascending
        sorted_asc = self.tool._sort_indexes(indexes, 'name', 'asc')
        assert [idx['name'] for idx in sorted_asc] == ['alpha', 'beta', 'zebra']
        
        # Sort descending
        sorted_desc = self.tool._sort_indexes(indexes, 'name', 'desc')
        assert [idx['name'] for idx in sorted_desc] == ['zebra', 'beta', 'alpha']
    
    def test_sort_indexes_by_events(self):
        """Test sorting indexes by event count."""
        indexes = [
            {'name': 'low', 'total_event_count': 100},
            {'name': 'high', 'total_event_count': 300},
            {'name': 'medium', 'total_event_count': 200}
        ]
        
        # Sort ascending
        sorted_asc = self.tool._sort_indexes(indexes, 'events', 'asc')
        assert [idx['total_event_count'] for idx in sorted_asc] == [100, 200, 300]
        
        # Sort descending
        sorted_desc = self.tool._sort_indexes(indexes, 'events', 'desc')
        assert [idx['total_event_count'] for idx in sorted_desc] == [300, 200, 100]
    
    def test_sort_indexes_by_size(self):
        """Test sorting indexes by size."""
        indexes = [
            {'name': 'small', 'current_db_size_mb': 10.5},
            {'name': 'large', 'current_db_size_mb': 100.0},
            {'name': 'medium', 'current_db_size_mb': 50.2}
        ]
        
        # Sort ascending
        sorted_asc = self.tool._sort_indexes(indexes, 'size', 'asc')
        assert [idx['current_db_size_mb'] for idx in sorted_asc] == [10.5, 50.2, 100.0]
        
        # Sort descending
        sorted_desc = self.tool._sort_indexes(indexes, 'size', 'desc')
        assert [idx['current_db_size_mb'] for idx in sorted_desc] == [100.0, 50.2, 10.5]
    
    def test_generate_usage_suggestions(self):
        """Test usage suggestions generation."""
        indexes = [
            {
                'name': 'main',
                'total_event_count': 1000,
                'latest_time': '2024-01-02T00:00:00'
            },
            {
                'name': 'security',
                'total_event_count': 500,
                'latest_time': '2024-01-01T00:00:00'
            },
            {
                'name': 'disabled_index',
                'total_event_count': 0,
                'disabled': True
            }
        ]
        
        suggestions = self.tool._generate_usage_suggestions(indexes)
        
        assert "💡 Usage Suggestions:" in suggestions
        assert "index=main" in suggestions  # Largest index
        assert "Compare Indexes" in suggestions
        assert "disabled indexes found" in suggestions
    
    def test_cleanup(self):
        """Test cleanup method."""
        # Mock client
        mock_client = Mock()
        self.tool._client = mock_client
        
        # Call cleanup
        self.tool.cleanup()
        
        # Verify client was disconnected and cleared
        mock_client.disconnect.assert_called_once()
        assert self.tool._client is None
    
    def test_cleanup_with_error(self):
        """Test cleanup method with error."""
        # Mock client that raises error on disconnect
        mock_client = Mock()
        mock_client.disconnect.side_effect = Exception("Disconnect error")
        self.tool._client = mock_client
        
        # Call cleanup - should not raise exception
        self.tool.cleanup()
        
        # Verify client was cleared despite error
        assert self.tool._client is None


class TestModuleFunctions:
    """Test module-level functions."""
    
    def test_get_indexes_tool(self):
        """Test get_indexes_tool function."""
        tool = get_indexes_tool()
        assert isinstance(tool, SplunkIndexesTool)
        
        # Should return same instance
        tool2 = get_indexes_tool()
        assert tool is tool2
    
    @pytest.mark.asyncio
    async def test_execute_indexes(self):
        """Test execute_indexes function."""
        with patch.object(get_indexes_tool(), 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [TextContent(type="text", text="test")]
            
            arguments = {'test': 'value'}
            result = await execute_indexes(arguments)
            
            mock_execute.assert_called_once_with(arguments)
            assert len(result) == 1
            assert result[0].text == "test"


if __name__ == "__main__":
    pytest.main([__file__])
