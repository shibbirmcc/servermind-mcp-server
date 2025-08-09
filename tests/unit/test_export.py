"""Unit tests for the export tool."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from mcp.types import TextContent

from src.tools.export import SplunkExportTool, get_export_tool, execute_export
from src.splunk.client import SplunkConnectionError, SplunkSearchError


class TestSplunkExportTool:
    """Test cases for SplunkExportTool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SplunkExportTool()
    
    def test_get_tool_definition(self):
        """Test tool definition generation."""
        tool_def = self.tool.get_tool_definition()
        
        assert tool_def.name == "splunk_export"
        assert "Export Splunk search results to various formats" in tool_def.description
        assert "query" in tool_def.inputSchema["properties"]
        assert "format" in tool_def.inputSchema["properties"]
        assert "earliest_time" in tool_def.inputSchema["properties"]
        assert "latest_time" in tool_def.inputSchema["properties"]
        assert "max_results" in tool_def.inputSchema["properties"]
        assert "timeout" in tool_def.inputSchema["properties"]
        assert "fields" in tool_def.inputSchema["properties"]
        
        # Check format enum values
        format_enum = tool_def.inputSchema["properties"]["format"]["enum"]
        assert "json" in format_enum
        assert "csv" in format_enum
        assert "xml" in format_enum
        
        # Check required fields
        assert tool_def.inputSchema["required"] == ["query"]
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_json_export(self, mock_client_class, mock_get_config):
        """Test successful JSON export."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock search results
        mock_results = [
            {
                '_time': '2024-01-01T12:00:00',
                '_raw': 'Test log entry 1',
                'host': 'server1',
                'source': '/var/log/test.log'
            },
            {
                '_time': '2024-01-01T12:01:00',
                '_raw': 'Test log entry 2',
                'host': 'server2',
                'source': '/var/log/test.log'
            }
        ]
        mock_client.execute_search.return_value = mock_results
        
        # Execute tool
        arguments = {
            'query': 'index=main error',
            'format': 'json',
            'max_results': 100
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✅ **Splunk Export Completed**" in result[0].text
        assert "**Format:** JSON" in result[0].text
        assert "**Results Exported:** 2 events" in result[0].text
        assert "```json" in result[0].text
        assert '"_time": "2024-01-01T12:00:00"' in result[0].text
        
        # Verify client was called correctly
        mock_client.execute_search.assert_called_once()
        call_args = mock_client.execute_search.call_args
        assert call_args[0][0] == 'index=main error'  # query
        assert call_args[1]['max_results'] == 100
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_csv_export(self, mock_client_class, mock_get_config):
        """Test successful CSV export."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock search results
        mock_results = [
            {
                '_time': '2024-01-01T12:00:00',
                'host': 'server1',
                'level': 'ERROR'
            },
            {
                '_time': '2024-01-01T12:01:00',
                'host': 'server2',
                'level': 'WARN'
            }
        ]
        mock_client.execute_search.return_value = mock_results
        
        # Execute tool
        arguments = {
            'query': 'index=main',
            'format': 'csv'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results
        assert len(result) == 1
        assert "**Format:** CSV" in result[0].text
        assert "```csv" in result[0].text
        assert "_time,host,level" in result[0].text
        assert "2024-01-01T12:00:00,server1,ERROR" in result[0].text
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_xml_export(self, mock_client_class, mock_get_config):
        """Test successful XML export."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock search results
        mock_results = [
            {
                '_time': '2024-01-01T12:00:00',
                'message': 'Test & message'
            }
        ]
        mock_client.execute_search.return_value = mock_results
        
        # Execute tool
        arguments = {
            'query': 'index=main',
            'format': 'xml'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results
        assert len(result) == 1
        assert "**Format:** XML" in result[0].text
        assert "```xml" in result[0].text
        assert '<?xml version="1.0" encoding="UTF-8"?>' in result[0].text
        assert '<results>' in result[0].text
        assert 'Test &amp; message' in result[0].text  # XML escaped
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_with_field_filtering(self, mock_client_class, mock_get_config):
        """Test export with field filtering."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock search results
        mock_results = [
            {
                '_time': '2024-01-01T12:00:00',
                'host': 'server1',
                'level': 'ERROR',
                'message': 'Test message',
                'extra_field': 'should be filtered out'
            }
        ]
        mock_client.execute_search.return_value = mock_results
        
        # Execute tool with field filtering
        arguments = {
            'query': 'index=main',
            'format': 'json',
            'fields': ['_time', 'host', 'level']
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results - should only contain specified fields
        assert len(result) == 1
        assert '"_time": "2024-01-01T12:00:00"' in result[0].text
        assert '"host": "server1"' in result[0].text
        assert '"level": "ERROR"' in result[0].text
        assert 'message' not in result[0].text
        assert 'extra_field' not in result[0].text
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_no_results(self, mock_client_class, mock_get_config):
        """Test export with no results."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.execute_search.return_value = []
        
        # Execute tool
        arguments = {
            'query': 'index=main nonexistent',
            'format': 'json'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify results
        assert len(result) == 1
        assert "No results found for the specified search criteria" in result[0].text
    
    @pytest.mark.asyncio
    async def test_execute_missing_query(self):
        """Test execution with missing query parameter."""
        arguments = {
            'format': 'json'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify error handling
        assert len(result) == 1
        assert "❌ **Invalid Arguments**" in result[0].text
        assert "Query parameter is required" in result[0].text
    
    @pytest.mark.asyncio
    async def test_execute_invalid_format(self):
        """Test execution with invalid format."""
        arguments = {
            'query': 'index=main',
            'format': 'invalid'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify error handling
        assert len(result) == 1
        assert "❌ **Invalid Arguments**" in result[0].text
        assert "Unsupported export format: invalid" in result[0].text
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_connection_error(self, mock_client_class, mock_get_config):
        """Test execution with connection error."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client to raise connection error
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.execute_search.side_effect = SplunkConnectionError("Connection failed")
        
        # Execute tool
        arguments = {
            'query': 'index=main',
            'format': 'json'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify error handling
        assert len(result) == 1
        assert "❌ **Splunk Connection Error**" in result[0].text
        assert "Connection failed" in result[0].text
    
    @patch('src.tools.export.get_config')
    @patch('src.tools.export.SplunkClient')
    @pytest.mark.asyncio
    async def test_execute_search_error(self, mock_client_class, mock_get_config):
        """Test execution with search error."""
        # Mock configuration
        mock_config = Mock()
        mock_config.splunk = Mock()
        mock_config.mcp.search_timeout = 300
        mock_get_config.return_value = mock_config
        
        # Mock client to raise search error
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.execute_search.side_effect = SplunkSearchError("Invalid SPL")
        
        # Execute tool
        arguments = {
            'query': 'invalid spl query',
            'format': 'json'
        }
        
        result = await self.tool.execute(arguments)
        
        # Verify error handling
        assert len(result) == 1
        assert "❌ **Splunk Search Error**" in result[0].text
        assert "Invalid SPL" in result[0].text
    
    def test_export_to_json(self):
        """Test JSON export formatting."""
        results = [
            {'field1': 'value1', 'field2': 123},
            {'field1': 'value2', 'field2': 456}
        ]
        
        json_output = self.tool._export_to_json(results)
        
        assert '"field1": "value1"' in json_output
        assert '"field2": 123' in json_output
        assert json_output.startswith('[')
        assert json_output.endswith(']')
    
    def test_export_to_csv(self):
        """Test CSV export formatting."""
        results = [
            {'_time': '2024-01-01', 'host': 'server1', 'level': 'ERROR'},
            {'_time': '2024-01-02', 'host': 'server2', 'level': 'WARN'}
        ]
        
        csv_output = self.tool._export_to_csv(results)
        
        # Check header (common fields first) - handle different line endings
        lines = csv_output.strip().replace('\r\n', '\n').split('\n')
        assert lines[0] == '_time,host,level'
        assert lines[1] == '2024-01-01,server1,ERROR'
        assert lines[2] == '2024-01-02,server2,WARN'
    
    def test_export_to_csv_empty(self):
        """Test CSV export with empty results."""
        results = []
        
        csv_output = self.tool._export_to_csv(results)
        
        assert csv_output == ""
    
    def test_export_to_xml(self):
        """Test XML export formatting."""
        results = [
            {'field1': 'value1', 'field2': 'value & test'}
        ]
        
        xml_output = self.tool._export_to_xml(results)
        
        assert xml_output.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert '<results>' in xml_output
        assert '<result offset="0">' in xml_output
        assert 'value &amp; test' in xml_output  # XML escaped
        assert '</results>' in xml_output
    
    def test_escape_xml(self):
        """Test XML character escaping."""
        text = 'Test & <tag> "quoted" \'single\''
        escaped = self.tool._escape_xml(text)
        
        assert escaped == 'Test &amp; &lt;tag&gt; &quot;quoted&quot; &#39;single&#39;'
    
    def test_generate_export_suggestions(self):
        """Test export suggestions generation."""
        # Test JSON suggestions
        json_suggestions = self.tool._generate_export_suggestions('json', 100, 1024)
        assert "JSON Format" in json_suggestions
        assert "jq" in json_suggestions
        
        # Test CSV suggestions
        csv_suggestions = self.tool._generate_export_suggestions('csv', 100, 1024)
        assert "CSV Format" in csv_suggestions
        assert "Excel" in csv_suggestions
        
        # Test XML suggestions
        xml_suggestions = self.tool._generate_export_suggestions('xml', 100, 1024)
        assert "XML Format" in xml_suggestions
        assert "XSLT" in xml_suggestions
        
        # Test large dataset suggestions
        large_suggestions = self.tool._generate_export_suggestions('json', 5000, 2*1024*1024)
        assert "Large Dataset" in large_suggestions
        assert "Large Export" in large_suggestions
    
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
    
    def test_get_export_tool(self):
        """Test get_export_tool function."""
        tool = get_export_tool()
        assert isinstance(tool, SplunkExportTool)
        
        # Should return same instance
        tool2 = get_export_tool()
        assert tool is tool2
    
    @pytest.mark.asyncio
    async def test_execute_export(self):
        """Test execute_export function."""
        with patch.object(get_export_tool(), 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [TextContent(type="text", text="test")]
            
            arguments = {'query': 'index=main', 'format': 'json'}
            result = await execute_export(arguments)
            
            mock_execute.assert_called_once_with(arguments)
            assert len(result) == 1
            assert result[0].text == "test"


if __name__ == "__main__":
    pytest.main([__file__])
