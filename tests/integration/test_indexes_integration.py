"""Integration tests for the indexes tool."""

import pytest
import asyncio
from mcp.types import TextContent

from src.tools.indexes import SplunkIndexesTool, execute_indexes
from src.config import get_config
from src.splunk.client import SplunkClient, SplunkConnectionError


class TestIndexesIntegration:
    """Integration tests for indexes tool with real Splunk connection."""
    
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
    async def test_list_indexes_basic(self, config, splunk_available):
        """Test basic index listing functionality."""
        tool = SplunkIndexesTool()
        
        # Execute with default parameters
        result = await tool.execute({})
        
        # Verify response structure
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✅ **Splunk Indexes Retrieved**" in result[0].text
        assert "**Total Indexes:**" in result[0].text
        assert "**Summary Statistics:**" in result[0].text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_indexes_with_sorting(self, config, splunk_available):
        """Test index listing with different sorting options."""
        tool = SplunkIndexesTool()
        
        # Test sorting by name (ascending)
        result_name_asc = await tool.execute({
            'sort_by': 'name',
            'sort_order': 'asc'
        })
        
        assert "**Sorted By:** name (asc)" in result_name_asc[0].text
        
        # Test sorting by events (descending)
        result_events_desc = await tool.execute({
            'sort_by': 'events',
            'sort_order': 'desc'
        })
        
        assert "**Sorted By:** events (desc)" in result_events_desc[0].text
        
        # Test sorting by size
        result_size = await tool.execute({
            'sort_by': 'size',
            'sort_order': 'asc'
        })
        
        assert "**Sorted By:** size (asc)" in result_size[0].text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_indexes_with_filter(self, config, splunk_available):
        """Test index listing with filter pattern."""
        tool = SplunkIndexesTool()
        
        # First get all indexes to see what's available
        all_result = await tool.execute({})
        all_text = all_result[0].text
        
        # Extract an index name from the results for filtering
        import re
        index_matches = re.findall(r'\*\*\d+\. (\w+)\*\*', all_text)
        
        if index_matches:
            # Use first few characters of first index as filter
            test_index = index_matches[0]
            filter_pattern = test_index[:3]  # First 3 characters
            
            # Test with filter
            filtered_result = await tool.execute({
                'filter_pattern': filter_pattern
            })
            
            assert f"**Filter Applied:** `{filter_pattern}`" in filtered_result[0].text
            
            # Should contain the index we're filtering for
            assert test_index in filtered_result[0].text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_indexes_exclude_disabled(self, config, splunk_available):
        """Test excluding disabled indexes."""
        tool = SplunkIndexesTool()
        
        # Get all indexes
        all_result = await tool.execute({'include_disabled': True})
        all_text = all_result[0].text
        
        # Get only active indexes
        active_result = await tool.execute({'include_disabled': False})
        active_text = active_result[0].text
        
        # Extract total counts
        import re
        all_match = re.search(r'\*\*Total Indexes:\*\* (\d+)', all_text)
        active_match = re.search(r'\*\*Total Indexes:\*\* (\d+)', active_text)
        
        if all_match and active_match:
            all_count = int(all_match.group(1))
            active_count = int(active_match.group(1))
            
            # Active count should be <= all count
            assert active_count <= all_count
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_usage_suggestions_generated(self, config, splunk_available):
        """Test that usage suggestions are generated."""
        tool = SplunkIndexesTool()
        
        result = await tool.execute({})
        text = result[0].text
        
        # Should contain usage suggestions
        assert "💡 Usage Suggestions:" in text
        
        # Should contain at least one suggestion
        suggestions_section = text.split("💡 Usage Suggestions:")[1]
        assert len(suggestions_section.strip()) > 0
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_indexes_function(self, config, splunk_available):
        """Test the module-level execute_indexes function."""
        result = await execute_indexes({
            'sort_by': 'name',
            'sort_order': 'asc'
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✅ **Splunk Indexes Retrieved**" in result[0].text
        assert "**Sorted By:** name (asc)" in result[0].text
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, config, splunk_available):
        """Test handling multiple concurrent requests."""
        tool = SplunkIndexesTool()
        
        # Create multiple concurrent requests
        tasks = [
            tool.execute({'sort_by': 'name'}),
            tool.execute({'sort_by': 'events'}),
            tool.execute({'sort_by': 'size'})
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        assert len(results) == 3
        for result in results:
            assert len(result) == 1
            assert "✅ **Splunk Indexes Retrieved**" in result[0].text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_with_invalid_sort(self, config, splunk_available):
        """Test error handling with invalid sort parameters."""
        tool = SplunkIndexesTool()
        
        # Test with invalid sort field (should default to name)
        result = await tool.execute({
            'sort_by': 'invalid_field',
            'sort_order': 'asc'
        })
        
        # Should still work (defaults to name sorting)
        assert "✅ **Splunk Indexes Retrieved**" in result[0].text
        
        # Clean up
        tool.cleanup()
    
    @pytest.mark.integration
    def test_tool_definition_matches_implementation(self, config):
        """Test that tool definition matches actual implementation."""
        tool = SplunkIndexesTool()
        tool_def = tool.get_tool_definition()
        
        # Verify tool name
        assert tool_def.name == "splunk_indexes"
        
        # Verify required properties exist in schema
        properties = tool_def.inputSchema["properties"]
        assert "filter_pattern" in properties
        assert "include_disabled" in properties
        assert "sort_by" in properties
        assert "sort_order" in properties
        
        # Verify enum values for sort_by
        sort_by_enum = properties["sort_by"]["enum"]
        expected_sort_fields = ["name", "size", "events", "earliest", "latest"]
        for field in expected_sort_fields:
            assert field in sort_by_enum
        
        # Verify enum values for sort_order
        sort_order_enum = properties["sort_order"]["enum"]
        assert "asc" in sort_order_enum
        assert "desc" in sort_order_enum


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-m", "integration"])
