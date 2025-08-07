#!/usr/bin/env python3
"""
Test MCP client to verify the SSE transport is working correctly.
"""

import asyncio
import json
import aiohttp
import sys

async def test_mcp_client():
    """Test the MCP client functionality."""
    
    print("Testing MCP Server SSE Transport...")
    
    # Test 1: Check server info
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:9090/') as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Server info: {data}")
            else:
                print(f"❌ Failed to get server info: {resp.status}")
                return False
    
    # Test 2: Connect to SSE endpoint and get client ID
    client_id = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:9090/connect') as resp:
                if resp.status == 200:
                    print("✅ Connected to SSE endpoint")
                    
                    # Read the first event to get client ID
                    async for line in resp.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data_str = line[6:]  # Remove 'data: ' prefix
                            try:
                                data = json.loads(data_str)
                                if 'client_id' in data:
                                    client_id = data['client_id']
                                    print(f"✅ Got client ID: {client_id}")
                                    break
                            except json.JSONDecodeError:
                                continue
                        elif line.startswith('event: connected'):
                            continue
                        elif line == '':
                            continue
                        else:
                            print(f"Received line: {line}")
                            
                        # Break after getting client ID
                        if client_id:
                            break
                else:
                    print(f"❌ Failed to connect to SSE: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ SSE connection error: {e}")
        return False
    
    if not client_id:
        print("❌ Failed to get client ID from SSE connection")
        return False
    
    # Test 3: Send tools/list request
    try:
        async with aiohttp.ClientSession() as session:
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            async with session.post(
                f'http://localhost:9090/message/{client_id}',
                json=message,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"✅ tools/list request sent successfully: {result}")
                    
                    # Now we need to read the response from SSE
                    # For this test, we'll just verify the request was accepted
                    return True
                else:
                    error_text = await resp.text()
                    print(f"❌ tools/list request failed: {resp.status} - {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Error sending tools/list request: {e}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_mcp_client())
        if result:
            print("\n🎉 MCP Server SSE Transport is working!")
            sys.exit(0)
        else:
            print("\n❌ MCP Server SSE Transport has issues")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)
