#!/usr/bin/env python3
"""
Test script for the Splunk MCP Server
"""

import asyncio
import json
import subprocess
import sys
import os
from typing import Dict, Any

async def test_mcp_server():
    """Test the MCP server functionality."""
    
    # Set environment variables for the test
    env = os.environ.copy()
    env.update({
        'SPLUNK_HOST': 'localhost',
        'SPLUNK_USERNAME': 'admin',
        'SPLUNK_PASSWORD': 'changeme123',
        'SPLUNK_VERIFY_SSL': 'false',
        'SPLUNK_PORT': '8089',
        'SPLUNK_SCHEME': 'https'
    })
    
    print("🚀 Testing Splunk MCP Server...")
    
    # Start the MCP server process
    process = subprocess.Popen(
        [sys.executable, '-m', 'src.server'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    try:
        # Test 1: Initialize the server
        print("\n📋 Test 1: Initialize MCP Server")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"✅ Initialize response: {response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
        else:
            print("❌ No response to initialize")
            return False
        
        # Test 2: List tools
        print("\n🔧 Test 2: List Tools")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_tools_request) + '\n')
        process.stdin.flush()
        
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            tools = response.get('result', {}).get('tools', [])
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"   - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
        else:
            print("❌ No response to list tools")
            return False
        
        # Test 3: List resources
        print("\n📚 Test 3: List Resources")
        list_resources_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_resources_request) + '\n')
        process.stdin.flush()
        
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            resources = response.get('result', {}).get('resources', [])
            print(f"✅ Found {len(resources)} resources:")
            for resource in resources:
                print(f"   - {resource.get('name', 'Unknown')}: {resource.get('description', 'No description')}")
        else:
            print("❌ No response to list resources")
            return False
        
        # Test 4: Read connection info resource
        print("\n🔗 Test 4: Read Connection Info Resource")
        read_resource_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {
                "uri": "splunk://connection-info"
            }
        }
        
        process.stdin.write(json.dumps(read_resource_request) + '\n')
        process.stdin.flush()
        
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            contents = response.get('result', {}).get('contents', [])
            if contents:
                connection_info = json.loads(contents[0].get('text', '{}'))
                print(f"✅ Connection status: {connection_info.get('status', 'unknown')}")
                if connection_info.get('status') == 'connected':
                    print(f"   - Splunk version: {connection_info.get('version', 'unknown')}")
                    print(f"   - Server name: {connection_info.get('server_name', 'unknown')}")
                else:
                    print(f"   - Error: {connection_info.get('error', 'unknown')}")
        else:
            print("❌ No response to read resource")
            return False
        
        print("\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)
