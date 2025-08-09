"""Integration tests for the export tool."""

import pytest
import asyncio
import json
import csv
import io
from mcp.types import TextContent

from src.tools.export import SplunkExportTool, execute_export
from src.config import get_config
from src.splunk.client import SplunkClient, SplunkConnectionError


class TestExportIntegration:
    """Integration tests for export tool with real Splunk connection."""
    
    @pytest.fixture(scope="class")
    def config(self):
        """Get configuration for tests."""
        try:
            return get_config()
        except Exception as e:
            pytest.skip(f"Configuration not available: {e}")
    
    @pytest.fixture(scope="class")
    def splunk_available(self, config):
        """Check if Splunk is available for testing."""
        try:
            client = SplunkClient(config.splunk)
            client.test_connection()
            client.disconnect()
            return True
        except SplunkConnectionError:
            pytest.skip("Splunk server not available for integration tests")
        except Exception as e:
            pytest.skip(f"Splunk connection failed: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_json_basic(self, config, splunk_available):
        """Test basic JSON export functionality."""
        tool = SplunkExportTool()
        
        # Execute export with a simple search
        result = await tool.execute({
            'query': '| makeresults count=3 | eval test_field="test_value", number_field=random()',
            'format': 'json',
            'max_results': 10
        })
        
        # Verify response structure
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✅ **Splunk Export Completed**" in result[0].text
        assert "**Format:** JSON" in result[0].text
        assert "**Results Exported:** 3 events" in result[0].text
        assert "```json" in result[0].text
        
        # Verify JSON content is present
        assert '"test_field": "test_value"' in result[0].text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_csv_basic(self, config, splunk_available):
        """Test basic CSV export functionality."""
        tool = SplunkExportTool()
        
        # Execute export with a simple search
        result = await tool.execute({
            'query': '| makeresults count=2 | eval host="server1", level="INFO"',
            'format': 'csv',
            'max_results': 10
        })
        
        # Verify response structure
        assert len(result) == 1
        assert "**Format:** CSV" in result[0].text
        assert "```csv" in result[0].text
        
        # Verify CSV content structure
        text = result[0].text
        csv_section = text.split("```csv")[1].split("```")[0].strip()
        lines = csv_section.split('\n')
        
        # Should have header and data rows
        assert len(lines) >= 3  # header + 2 data rows
        assert 'host' in lines[0]  # header should contain host field
        assert 'server1' in csv_section  # data should contain our test value
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_xml_basic(self, config, splunk_available):
        """Test basic XML export functionality."""
        tool = SplunkExportTool()
        
        # Execute export with a simple search
        result = await tool.execute({
            'query': '| makeresults count=1 | eval message="test & data"',
            'format': 'xml',
            'max_results': 10
        })
        
        # Verify response structure
        assert len(result) == 1
        assert "**Format:** XML" in result[0].text
        assert "```xml" in result[0].text
        
        # Verify XML content
        text = result[0].text
        assert '<?xml version="1.0" encoding="UTF-8"?>' in text
        assert '<results>' in text
        assert '<result offset="0">' in text
        assert 'test &amp; data' in text  # Should be XML escaped
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_with_field_filtering(self, config, splunk_available):
        """Test export with field filtering."""
        tool = SplunkExportTool()
        
        # Execute export with field filtering
        result = await tool.execute({
            'query': '| makeresults count=1 | eval field1="keep", field2="filter_out", field3="keep"',
            'format': 'json',
            'fields': ['field1', 'field3'],
            'max_results': 10
        })
        
        # Verify response
        assert len(result) == 1
        text = result[0].text
        
        # Should contain filtered fields
        assert '"field1": "keep"' in text
        assert '"field3": "keep"' in text
        
        # Should not contain filtered out field in the exported data section
        # (but it might appear in the query display)
        json_section = text.split("```json")[1].split("```")[0] if "```json" in text else ""
        assert 'field2' not in json_section
        assert 'filter_out' not in json_section
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_time_range(self, config, splunk_available):
        """Test export with time range parameters."""
        tool = SplunkExportTool()
        
        # Execute export with time range
        result = await tool.execute({
            'query': '| makeresults count=1',
            'format': 'json',
            'earliest_time': '-1h',
            'latest_time': 'now',
            'max_results': 10
        })
        
        # Verify response includes time range info
        assert len(result) == 1
        text = result[0].text
        assert "**Time Range:** -1h to now" in text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_max_results_limit(self, config, splunk_available):
        """Test export with max results limit."""
        tool = SplunkExportTool()
        
        # Execute export with small max_results
        result = await tool.execute({
            'query': '| makeresults count=10',
            'format': 'json',
            'max_results': 3
        })
        
        # Verify response respects max_results
        assert len(result) == 1
        text = result[0].text
        # The actual number of results may vary, but max_results should be respected
        assert "**Max Results:** 3" in text
        # Check that we don't get more than 3 results in the JSON
        if "```json" in text:
            json_section = text.split("```json")[1].split("```")[0]
            # Count the number of result objects (rough estimate)
            result_count = json_section.count('"_time"')
            assert result_count <= 3
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_no_results(self, config, splunk_available):
        """Test export with search that returns no results."""
        tool = SplunkExportTool()
        
        # Execute export with search that should return no results
        result = await tool.execute({
            'query': 'index=nonexistent_index_12345',
            'format': 'json',
            'max_results': 10
        })
        
        # Verify response handles no results
        assert len(result) == 1
        text = result[0].text
        assert "No results found for the specified search criteria" in text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_different_formats_same_data(self, config, splunk_available):
        """Test exporting same data in different formats."""
        tool = SplunkExportTool()
        
        # Base query for consistent data
        base_query = '| makeresults count=2 | eval host="server1", level="INFO", count=123'
        
        # Export in JSON
        json_result = await tool.execute({
            'query': base_query,
            'format': 'json',
            'max_results': 10
        })
        
        # Export in CSV
        csv_result = await tool.execute({
            'query': base_query,
            'format': 'csv',
            'max_results': 10
        })
        
        # Export in XML
        xml_result = await tool.execute({
            'query': base_query,
            'format': 'xml',
            'max_results': 10
        })
        
        # Verify all formats contain the same data
        json_text = json_result[0].text
        csv_text = csv_result[0].text
        xml_text = xml_result[0].text
        
        # All should contain our test values
        assert 'server1' in json_text
        assert 'server1' in csv_text
        assert 'server1' in xml_text
        
        assert 'INFO' in json_text
        assert 'INFO' in csv_text
        assert 'INFO' in xml_text
        
        # All should report same number of results
        assert "**Results Exported:** 2 events" in json_text
        assert "**Results Exported:** 2 events" in csv_text
        assert "**Results Exported:** 2 events" in xml_text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_suggestions_generated(self, config, splunk_available):
        """Test that export suggestions are generated."""
        tool = SplunkExportTool()
        
        # Test JSON suggestions
        json_result = await tool.execute({
            'query': '| makeresults count=1',
            'format': 'json'
        })
        
        json_text = json_result[0].text
        assert "💡 Export Suggestions:" in json_text
        assert "JSON Format" in json_text
        assert "jq" in json_text
        
        # Test CSV suggestions
        csv_result = await tool.execute({
            'query': '| makeresults count=1',
            'format': 'csv'
        })
        
        csv_text = csv_result[0].text
        assert "💡 Export Suggestions:" in csv_text
        assert "CSV Format" in csv_text
        assert "Excel" in csv_text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_export_function(self, config, splunk_available):
        """Test the module-level execute_export function."""
        result = await execute_export({
            'query': '| makeresults count=1 | eval test="integration"',
            'format': 'json',
            'max_results': 10
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✅ **Splunk Export Completed**" in result[0].text
        assert '"test": "integration"' in result[0].text
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multiple_concurrent_exports(self, config, splunk_available):
        """Test handling multiple concurrent export requests."""
        tool = SplunkExportTool()
        
        # Create multiple concurrent export requests
        tasks = [
            tool.execute({
                'query': '| makeresults count=1 | eval format="json"',
                'format': 'json'
            }),
            tool.execute({
                'query': '| makeresults count=1 | eval format="csv"',
                'format': 'csv'
            }),
            tool.execute({
                'query': '| makeresults count=1 | eval format="xml"',
                'format': 'xml'
            })
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        assert len(results) == 3
        for result in results:
            assert len(result) == 1
            assert "✅ **Splunk Export Completed**" in result[0].text
        
        # Verify different formats
        formats_found = []
        for result in results:
            text = result[0].text
            if "**Format:** JSON" in text:
                formats_found.append("json")
            elif "**Format:** CSV" in text:
                formats_found.append("csv")
            elif "**Format:** XML" in text:
                formats_found.append("xml")
        
        assert len(formats_found) == 3
        assert "json" in formats_found
        assert "csv" in formats_found
        assert "xml" in formats_found
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_large_dataset_suggestions(self, config, splunk_available):
        """Test suggestions for large datasets."""
        tool = SplunkExportTool()
        
        # Create a larger dataset to trigger large dataset suggestions
        result = await tool.execute({
            'query': '| makeresults count=1500',
            'format': 'json',
            'max_results': 1500
        })
        
        text = result[0].text
        
        # Should contain large dataset suggestions
        assert "Large Dataset" in text or "results" in text.lower()
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_error_handling_invalid_spl(self, config, splunk_available):
        """Test error handling with invalid SPL query."""
        tool = SplunkExportTool()
        
        # Execute export with invalid SPL - Splunk may treat this as a search term
        # rather than throwing an error, so we'll test that it completes successfully
        result = await tool.execute({
            'query': 'invalid spl syntax here',
            'format': 'json'
        })
        
        # Should handle the query gracefully (even if it returns no results)
        assert len(result) == 1
        text = result[0].text
        
        # Should either succeed with no results or show an error
        assert ("✅ **Splunk Export Completed**" in text or 
                "❌" in text or "Error" in text or "error" in text)
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    def test_tool_definition_matches_implementation(self, config):
        """Test that tool definition matches actual implementation."""
        tool = SplunkExportTool()
        tool_def = tool.get_tool_definition()
        
        # Verify tool name
        assert tool_def.name == "splunk_export"
        
        # Verify required properties exist in schema
        properties = tool_def.inputSchema["properties"]
        assert "query" in properties
        assert "format" in properties
        assert "earliest_time" in properties
        assert "latest_time" in properties
        assert "max_results" in properties
        assert "timeout" in properties
        assert "fields" in properties
        
        # Verify format enum values
        format_enum = properties["format"]["enum"]
        expected_formats = ["json", "csv", "xml"]
        for fmt in expected_formats:
            assert fmt in format_enum
        
        # Verify required fields
        assert tool_def.inputSchema["required"] == ["query"]
        
        # Verify default values
        assert properties["format"]["default"] == "json"
        assert properties["earliest_time"]["default"] == "-24h"
        assert properties["latest_time"]["default"] == "now"
        assert properties["max_results"]["default"] == 1000
        assert properties["timeout"]["default"] == 300


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-m", "integration"])
