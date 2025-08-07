#!/usr/bin/env python3
"""
Test script to verify the MCP server can start and basic functionality works.
"""

import os
import sys
import asyncio
import json
from unittest.mock import patch

# Add src to path
sys.path.insert(0, 'src')

# Set test environment variables before importing
os.environ.update({
    'SPLUNK_HOST': 'test-host',
    'SPLUNK_USERNAME': 'test-user',
    'SPLUNK_PASSWORD': 'test-pass'
})

from src.config import ConfigLoader, SplunkConfig, MCPConfig
from src.splunk.utils import validate_spl_query, parse_time_range, estimate_search_cost


async def test_configuration():
    """Test configuration loading."""
    print("Testing configuration loading...")
    
    # Test with environment variables
    with patch.dict(os.environ, {
        'SPLUNK_HOST': 'test-host',
        'SPLUNK_USERNAME': 'test-user',
        'SPLUNK_PASSWORD': 'test-pass'
    }):
        loader = ConfigLoader("nonexistent.json")
        config = loader.load()
        
        assert config.splunk.host == "test-host"
        assert config.splunk.username == "test-user"
        assert config.splunk.password == "test-pass"
        print("✓ Configuration loading works")


def test_spl_validation():
    """Test SPL query validation."""
    print("Testing SPL validation...")
    
    # Test valid queries
    valid_queries = [
        "index=main error",
        "search error",
        "| stats count by host"
    ]
    
    for query in valid_queries:
        is_valid, error = validate_spl_query(query)
        assert is_valid, f"Query should be valid: {query}"
    
    # Test invalid queries
    invalid_queries = [
        "",
        "index=main | delete *"
    ]
    
    for query in invalid_queries:
        is_valid, error = validate_spl_query(query)
        assert not is_valid, f"Query should be invalid: {query}"
    
    print("✓ SPL validation works")


def test_time_parsing():
    """Test time range parsing."""
    print("Testing time range parsing...")
    
    valid_times = ["-1h", "-24h", "-1d", "now", "2023-01-01"]
    for time_str in valid_times:
        result = parse_time_range(time_str)
        assert result is not None, f"Time should be valid: {time_str}"
    
    invalid_times = ["invalid", "2023-13-01"]
    for time_str in invalid_times:
        result = parse_time_range(time_str)
        assert result is None, f"Time should be invalid: {time_str}"
    
    print("✓ Time parsing works")


def test_cost_estimation():
    """Test search cost estimation."""
    print("Testing cost estimation...")
    
    # Low cost query
    low_cost = estimate_search_cost("index=main | head 10", "-1h")
    assert low_cost["cost_level"] == "Low"
    
    # High cost query
    high_cost = estimate_search_cost(
        "index=* | join host [search index=other] | transaction host | cluster field=message", 
        "-1y"
    )
    assert high_cost["cost_level"] in ["High", "Very High"]
    
    print("✓ Cost estimation works")


async def test_search_tool():
    """Test search tool initialization."""
    print("Testing search tool...")
    
    # Import here to avoid global config loading issues
    from src.tools.search import SplunkSearchTool
    
    # Test tool definition
    tool = SplunkSearchTool()
    definition = tool.get_tool_definition()
    
    assert definition.name == "splunk_search"
    assert "query" in definition.inputSchema["properties"]
    
    print("✓ Search tool initialization works")


async def main():
    """Run all tests."""
    print("🧪 Running MCP Server Tests\n")
    
    try:
        await test_configuration()
        test_spl_validation()
        test_time_parsing()
        test_cost_estimation()
        await test_search_tool()
        
        print("\n✅ All tests passed! The MCP server basic functionality is working.")
        print("\n📋 Next steps:")
        print("1. Copy config.example.json to config.json and update with your Splunk credentials")
        print("2. Run: python -m src.server")
        print("3. Configure your MCP client to connect to this server")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
