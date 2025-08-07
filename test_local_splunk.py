#!/usr/bin/env python3
"""
Test script to verify MCP server connectivity with local Splunk instance.
Tests connection, index access, and search functionality.
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Dict, Any

# Add src to path
sys.path.insert(0, 'src')

# Load test environment
from dotenv import load_dotenv
load_dotenv('.env.test')

from src.config import get_config
from src.splunk.client import SplunkClient
from src.tools.search import SplunkSearchTool


def test_connection():
    """Test basic Splunk connection."""
    print("🔗 Testing Splunk Connection...")
    
    try:
        config = get_config()
        client = SplunkClient(config.splunk)
        
        # Test connection
        info = client.get_server_info()
        print(f"✅ Connected to Splunk {info.get('version', 'Unknown')} (Build: {info.get('build', 'Unknown')})")
        print(f"   Server: {config.splunk.host}:{config.splunk.port}")
        print(f"   Scheme: {config.splunk.scheme}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_indexes():
    """Test index listing and access."""
    print("\n📚 Testing Index Access...")
    
    try:
        config = get_config()
        client = SplunkClient(config.splunk)
        
        # Get all indexes
        indexes = client.get_indexes()
        print(f"✅ Found {len(indexes)} indexes:")
        
        kubernetes_found = False
        for index in indexes:
            name = index.get('name', 'Unknown')
            total_events = index.get('total_event_count', 0)
            size = index.get('current_db_size_mb', 0)
            
            if name == 'kubernetes':
                kubernetes_found = True
                print(f"   🎯 {name}: {total_events} events, {size}MB")
            else:
                print(f"   📁 {name}: {total_events} events, {size}MB")
        
        if not kubernetes_found:
            print("⚠️  Warning: 'kubernetes' index not found!")
            print("   Available indexes:", [idx.get('name') for idx in indexes])
        
        return kubernetes_found
        
    except Exception as e:
        print(f"❌ Index access failed: {e}")
        return False


def test_kubernetes_search():
    """Test searching the kubernetes index."""
    print("\n🔍 Testing Kubernetes Index Search...")
    
    try:
        config = get_config()
        client = SplunkClient(config.splunk)
        
        # Test basic search
        query = "index=kubernetes"
        print(f"   Query: {query}")
        
        results = client.search(
            query=query,
            earliest_time="-24h",
            latest_time="now",
            max_results=10
        )
        
        if results:
            print(f"✅ Found {len(results)} events in kubernetes index")
            
            # Show sample event
            if results:
                sample = results[0]
                print("   📄 Sample event fields:")
                for key, value in list(sample.items())[:5]:
                    if key.startswith('_'):
                        continue
                    value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    print(f"      {key}: {value_str}")
        else:
            print("⚠️  No events found in kubernetes index (may be empty)")
            
        return True
        
    except Exception as e:
        print(f"❌ Kubernetes search failed: {e}")
        return False


async def test_mcp_tool():
    """Test the MCP search tool."""
    print("\n🛠️  Testing MCP Search Tool...")
    
    try:
        # Test tool initialization
        tool = SplunkSearchTool()
        definition = tool.get_tool_definition()
        print(f"✅ Tool initialized: {definition.name}")
        
        # Test search via MCP tool
        search_args = {
            "query": "index=kubernetes | head 5",
            "earliest_time": "-24h",
            "max_results": 5
        }
        
        print(f"   Testing search: {search_args['query']}")
        result = await tool.execute(search_args)
        
        # Check if result indicates an error (starts with ❌)
        if result and len(result) > 0:
            result_text = result[0].text
            if result_text.startswith("❌"):
                print(f"❌ MCP tool search failed: {result_text.split('**')[1] if '**' in result_text else 'Unknown error'}")
                return False
            else:
                print("✅ MCP tool search successful")
                
                # Try to extract event count from result
                if "Results:" in result_text:
                    # Extract the number after "Results:"
                    try:
                        results_line = [line for line in result_text.split('\n') if 'Results:' in line][0]
                        event_count = results_line.split('Results:')[1].split('events')[0].strip()
                        print(f"   {event_count} events found")
                    except:
                        pass
                
                # Show first few lines of result
                lines = result_text.split('\n')[:5]
                for line in lines:
                    if line.strip() and not line.startswith('**'):
                        print(f"   {line[:80]}...")
                        break
        else:
            print("❌ MCP tool returned empty result")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ MCP tool test failed: {e}")
        return False


async def test_advanced_queries():
    """Test more advanced Splunk queries."""
    print("\n🚀 Testing Advanced Queries...")
    
    queries = [
        "index=kubernetes | stats count by host",
        "index=kubernetes | stats count by sourcetype",
        "index=kubernetes earliest=-1h | timechart span=10m count",
        "index=kubernetes | head 3 | table _time, host, source"
    ]
    
    try:
        tool = SplunkSearchTool()
        
        for i, query in enumerate(queries, 1):
            print(f"   Query {i}: {query}")
            
            search_args = {
                "query": query,
                "earliest_time": "-24h",
                "max_results": 10
            }
            
            result = await tool.execute(search_args)
            
            if result and len(result) > 0:
                result_text = result[0].text
                if result_text.startswith("❌"):
                    print(f"      ❌ Failed: {result_text.split('**')[1] if '**' in result_text else 'Unknown error'}")
                else:
                    print(f"      ✅ Success")
            else:
                print(f"      ❌ Failed: Empty result")
                
        return True
        
    except Exception as e:
        print(f"❌ Advanced queries test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling with invalid queries."""
    print("\n🚨 Testing Error Handling...")
    
    try:
        tool = SplunkSearchTool()
        
        # Test invalid query
        search_args = {
            "query": "index=nonexistent_index",
            "earliest_time": "-1h",
            "max_results": 10
        }
        
        print("   Testing invalid index query...")
        result = await tool.execute(search_args)
        
        if result and len(result) > 0:
            result_text = result[0].text
            if result_text.startswith("❌"):
                print("✅ Error handling works - invalid query properly rejected")
            else:
                print("⚠️  Expected error but query succeeded (index might exist)")
        else:
            print("❌ Error handling test failed - empty result")
        
        # Test malformed query
        search_args = {
            "query": "index=kubernetes | invalid_command",
            "earliest_time": "-1h",
            "max_results": 10
        }
        
        print("   Testing malformed query...")
        result = await tool.execute(search_args)
        
        if result and len(result) > 0:
            result_text = result[0].text
            if result_text.startswith("❌"):
                print("✅ Error handling works - malformed query properly rejected")
            else:
                print("⚠️  Expected error but query succeeded")
        else:
            print("❌ Error handling test failed - empty result")
            
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🧪 Testing Splunk MCP Server with Local Instance")
    print("=" * 60)
    
    # Load configuration
    try:
        config = get_config()
        print(f"📋 Configuration loaded:")
        print(f"   Host: {config.splunk.host}:{config.splunk.port}")
        print(f"   Username: {config.splunk.username}")
        print(f"   Scheme: {config.splunk.scheme}")
        print(f"   SSL Verify: {config.splunk.verify_ssl}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return
    
    # Run tests
    tests = [
        ("Connection Test", test_connection),
        ("Index Access Test", test_indexes),
        ("Kubernetes Search Test", test_kubernetes_search),
        ("MCP Tool Test", test_mcp_tool),
        ("Advanced Queries Test", test_advanced_queries),
        ("Error Handling Test", test_error_handling),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                results[test_name] = await test_func()
            else:
                results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! MCP server is ready for use with your Splunk instance.")
        print("\n📋 Next steps:")
        print("1. Copy .env.test to .env for permanent configuration")
        print("2. Build and run the Docker container")
        print("3. Configure Cline to use the MCP server")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
