#!/usr/bin/env python3
"""
MCP server with SSE transport exposing Splunk search tool
Following the working FastMCP pattern
"""

import sys
from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP
import uvicorn
from mcp.server.fastmcp.server import Context
from mcp.server import Server
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from mcp.types import TextContent

from src.tools.search import get_search_tool

# Create FastMCP instance
mcp = FastMCP("splunk-mcp-server")

@mcp.tool()
async def splunk_search(
    query: str,
    earliest_time: str = "-24h",
    latest_time: str = "now", 
    max_results: int = 100,
    timeout: int = 300,
    context: Context = None
) -> str:
    """Execute a Splunk search query using SPL (Search Processing Language)"""
    try:
        # Get the search tool and execute
        search_tool = get_search_tool()
        arguments = {
            "query": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "max_results": max_results,
            "timeout": timeout
        }
        
        results = await search_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from search"
            
    except Exception as e:
        return f"Error executing search: {str(e)}"

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    sse = SseServerTransport("/messages")
    
    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )
        # Return empty response to avoid NoneType error
        return Response()
    
    async def handle_root(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )
        # Return empty response to avoid NoneType error
        return Response()
    
    return Starlette(
        debug=debug,
        routes=[
            Route("/", endpoint=handle_root),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages", app=sse.handle_post_message),
        ]
    )

def main():
    port = 8756
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    mcp_server = mcp._mcp_server
    starlette_app = create_starlette_app(mcp_server, debug=True)
    
    print(f"Splunk MCP Server running on http://localhost:{port}")
    print("Endpoints:")
    print(f"  SSE: http://localhost:{port}/sse")
    print(f"  Messages: http://localhost:{port}/messages/")
    print("Tools:")
    print(f"  - splunk_search: Execute Splunk search queries")
    
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
