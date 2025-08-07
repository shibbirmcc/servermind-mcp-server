#!/usr/bin/env python3
"""
Debug script for the Splunk MCP Server
"""

import subprocess
import sys
import os
import json

def debug_mcp_server():
    """Debug the MCP server functionality."""
    
    # Set environment variables for the test
    env = os.environ.copy()
    env.update({
        'SPLUNK_HOST': 'localhost',
        'SPLUNK_TOKEN': 'eyJraWQiOiJzcGx1bmsuc2VjcmV0IiwiYWxnIjoiSFM1MTIiLCJ2ZXIiOiJ2MiIsInR0eXAiOiJzdGF0aWMifQ.eyJpc3MiOiJhZG1pbiBmcm9tIDhhNTQ1YWZiZjVhNiIsInN1YiI6ImFkbWluIiwiYXVkIjoibWNwLXRva2VuIiwiaWRwIjoiU3BsdW5rIiwianRpIjoiYmZjZjMxMDgwZmU2YWM1YzQ3MTYxNjY4ZmQzODRmMzFhMjJlYzYyNTc0NTA1ZWFjYmNkOTE2MjcwNDRiZGI2YSIsImlhdCI6MTc1NDU4NDI3MSwiZXhwIjoxNzg4MjEzNTg2LCJuYnIiOjE3NTQ1ODQyNzF9.2FRE8NXKxmjUF_64zBJzncf59aBWcyOV74HMNndprvpz47TR11GnNLvEoibvQq_oAokN5M6hrBGXCfu7fF2N_A',
        'SPLUNK_VERIFY_SSL': 'false',
        'SPLUNK_PORT': '8089',
        'SPLUNK_SCHEME': 'https'
    })
    
    print("🚀 Debugging Splunk MCP Server...")
    
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
        # Send initialize request
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
        
        print("📤 Sending initialize request...")
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        
        # Read all available output
        print("📥 Reading response...")
        import select
        import time
        
        # Wait a bit for response
        time.sleep(2)
        
        # Read stdout
        stdout_data = ""
        stderr_data = ""
        
        # Check if there's data available
        if process.stdout:
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    stdout_data += line
                    print(f"STDOUT: {line.strip()}")
            except:
                pass
        
        # Check stderr
        if process.stderr:
            try:
                while True:
                    line = process.stderr.readline()
                    if not line:
                        break
                    stderr_data += line
                    print(f"STDERR: {line.strip()}")
            except:
                pass
        
        print(f"\n📊 Process return code: {process.poll()}")
        print(f"📊 STDOUT length: {len(stdout_data)}")
        print(f"📊 STDERR length: {len(stderr_data)}")
        
        if stdout_data:
            print(f"\n📄 Full STDOUT:\n{stdout_data}")
        
        if stderr_data:
            print(f"\n📄 Full STDERR:\n{stderr_data}")
        
    except Exception as e:
        print(f"❌ Debug failed with error: {e}")
        
    finally:
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

if __name__ == "__main__":
    debug_mcp_server()
