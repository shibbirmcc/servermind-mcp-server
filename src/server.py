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
from src.tools.indexes import get_indexes_tool
from src.tools.export import get_export_tool
from src.tools.monitor import get_monitor_tool
from src.tools.chain_1_prompt import get_chain_1_prompt_tool
from src.tools.chain_2_prompt import get_chain_2_prompt_tool
from src.tools.chain_3_prompt import get_chain_3_prompt_tool
from src.tools.expand_fetch_by_traceids import get_expand_fetch_by_traceids_tool
from src.tools.find_splunk_index_in_repo import get_find_splunk_index_in_repo_tool
from src.tools.group_results_by_traceid import get_group_results_by_traceid_tool
from src.tools.logs_debug_entry import get_logs_debug_entry_tool
from src.tools.logs_evaluation_prompt import get_splunk_log_evaluation_tool
from src.tools.resolve_splunk_index import get_resolve_splunk_index_tool
from src.tools.root_cause_identification_prompt import get_root_cause_identification_prompt_tool
from src.tools.splunk_log_analysis import get_splunk_log_analysis_prompt_tool
from src.tools.splunk_query_prompt import get_splunk_query_prompt_tool

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

@mcp.tool()
async def splunk_indexes(
    context: Context = None
) -> str:
    """List available Splunk indexes with their metadata"""
    try:
        # Get the indexes tool and execute
        indexes_tool = get_indexes_tool()
        arguments = {}
        
        results = await indexes_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No indexes found"
            
    except Exception as e:
        return f"Error retrieving indexes: {str(e)}"

@mcp.tool()
async def splunk_export(
    query: str,
    format: str = "json",
    earliest_time: str = "-24h",
    latest_time: str = "now",
    max_results: int = 1000,
    timeout: int = 300,
    fields: List[str] = None,
    context: Context = None
) -> str:
    """Export Splunk search results to various formats (JSON, CSV, XML)"""
    try:
        # Get the export tool and execute
        export_tool = get_export_tool()
        arguments = {
            "query": query,
            "format": format,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "max_results": max_results,
            "timeout": timeout
        }
        
        if fields is not None:
            arguments["fields"] = fields
        
        results = await export_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from export"
            
    except Exception as e:
        return f"Error executing export: {str(e)}"

@mcp.tool()
async def splunk_monitor(
    action: str,
    query: str = None,
    interval: int = 60,
    max_results: int = 1000,
    timeout: int = 60,
    clear_buffer: bool = True,
    context: Context = None
) -> str:
    """Start continuous monitoring of Splunk logs with specified intervals. 
    
    This tool creates a single monitoring session that runs in the background, collecting logs 
    at regular intervals and buffering results for analysis. Only one monitoring session 
    can be active at a time.
    
    Actions:
    - start: Begin monitoring with a query and interval
    - stop: Stop the current monitoring session
    - status: Get status of the current monitoring session
    - get_results: Retrieve buffered results from the session
    """
    try:
        # Get the monitor tool and execute
        monitor_tool = get_monitor_tool()
        arguments = {
            "action": action
        }
        
        if query is not None:
            arguments["query"] = query
        if interval != 60:
            arguments["interval"] = interval
        if max_results != 1000:
            arguments["max_results"] = max_results
        if timeout != 60:
            arguments["timeout"] = timeout
        if not clear_buffer:
            arguments["clear_buffer"] = clear_buffer
        
        results = await monitor_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from monitor"
            
    except Exception as e:
        return f"Error executing monitor: {str(e)}"

@mcp.tool()
async def get_chain_1_prompt(
    context: Context = None
) -> str:
    """Get a ready-to-use prompt for Chain 1 processing"""
    try:
        # Get the chain 1 prompt tool and execute
        chain_1_tool = get_chain_1_prompt_tool()
        arguments = {}
        
        results = await chain_1_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No chain 1 prompt found"
            
    except Exception as e:
        return f"Error retrieving chain 1 prompt: {str(e)}"

@mcp.tool()
async def get_chain_2_prompt(
    context: Context = None
) -> str:
    """Get a ready-to-use prompt for Chain 2 processing"""
    try:
        # Get the chain 2 prompt tool and execute
        chain_2_tool = get_chain_2_prompt_tool()
        arguments = {}
        
        results = await chain_2_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No chain 2 prompt found"
            
    except Exception as e:
        return f"Error retrieving chain 2 prompt: {str(e)}"

@mcp.tool()
async def get_chain_3_prompt(
    context: Context = None
) -> str:
    """Get a ready-to-use prompt for Chain 3 processing"""
    try:
        # Get the chain 3 prompt tool and execute
        chain_3_tool = get_chain_3_prompt_tool()
        arguments = {}
        
        results = await chain_3_tool.execute(arguments)
        
        # Convert TextContent results to string
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No chain 3 prompt found"
            
    except Exception as e:
        return f"Error retrieving chain 3 prompt: {str(e)}"

@mcp.tool()
async def expand_fetch_by_traceids(
    traceIds: List[str],
    env: str = "",
    context: Context = None
) -> str:
    """Expand and fetch logs by trace IDs"""
    try:
        expand_tool = get_expand_fetch_by_traceids_tool()
        arguments = {
            "traceIds": traceIds,
            "env": env
        }
        
        results = await expand_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from expand fetch"
            
    except Exception as e:
        return f"Error executing expand fetch: {str(e)}"

@mcp.tool()
async def find_splunk_index_in_repo(
    env: str,
    attempt: int = 0,
    broaden: bool = False,
    context: Context = None
) -> str:
    """Search the user's codebase and configuration files to find the Splunk index name(s) for a specific environment"""
    try:
        find_tool = get_find_splunk_index_in_repo_tool()
        arguments = {
            "env": env,
            "attempt": attempt,
            "broaden": broaden
        }
        
        results = await find_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from find index"
            
    except Exception as e:
        return f"Error finding splunk index: {str(e)}"

@mcp.tool()
async def group_results_by_traceid(
    results: str,
    context: Context = None
) -> str:
    """Group search results by trace ID"""
    try:
        group_tool = get_group_results_by_traceid_tool()
        arguments = {
            "results": results
        }
        
        results = await group_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from grouping"
            
    except Exception as e:
        return f"Error grouping results: {str(e)}"

@mcp.tool()
async def logs_debug_entry(
    userIntent: str,
    context: Context = None
) -> str:
    """Entry point for logs debugging workflow"""
    try:
        debug_tool = get_logs_debug_entry_tool()
        arguments = {
            "userIntent": userIntent
        }
        
        results = await debug_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from debug entry"
            
    except Exception as e:
        return f"Error in debug entry: {str(e)}"

@mcp.tool()
async def get_logs_evaluation_prompt(
    context: Context = None
) -> str:
    """Get a ready-to-use prompt for logs evaluation"""
    try:
        eval_tool = get_splunk_log_evaluation_tool()
        arguments = {}
        
        results = await eval_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No logs evaluation prompt found"
            
    except Exception as e:
        return f"Error retrieving logs evaluation prompt: {str(e)}"

@mcp.tool()
async def get_resolve_splunk_index(
    env: str = "",
    status: str = "",
    attempt: int = 0,
    foundIndices: List[Dict[str, Any]] = None,
    hints: Dict[str, Any] = None,
    config: Dict[str, Any] = None,
    userIntent: str = "",
    context: Context = None
) -> str:
    """Determine the correct Splunk environment and index(es) to query for a debugging request"""
    try:
        resolve_tool = get_resolve_splunk_index_tool()
        arguments = {
            "env": env,
            "status": status,
            "attempt": attempt
        }
        
        if foundIndices is not None:
            arguments["foundIndices"] = foundIndices
        if hints is not None:
            arguments["hints"] = hints
        if config is not None:
            arguments["config"] = config
        if userIntent:
            arguments["userIntent"] = userIntent
        
        results = await resolve_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from resolve index"
            
    except Exception as e:
        return f"Error resolving splunk index: {str(e)}"

@mcp.tool()
async def get_root_cause_identification_prompt(
    context: Context = None
) -> str:
    """Get a ready-to-use prompt for root cause identification"""
    try:
        root_cause_tool = get_root_cause_identification_prompt_tool()
        arguments = {}
        
        results = await root_cause_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No root cause identification prompt found"
            
    except Exception as e:
        return f"Error retrieving root cause identification prompt: {str(e)}"

@mcp.tool()
async def splunk_log_analysis(
    logs: str,
    context: Context = None
) -> str:
    """Analyze Splunk logs for patterns and insights"""
    try:
        analysis_tool = get_splunk_log_analysis_prompt_tool()
        arguments = {
            "logs": logs
        }
        
        results = await analysis_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from log analysis"
            
    except Exception as e:
        return f"Error analyzing logs: {str(e)}"

@mcp.tool()
async def get_splunk_query_prompt(
    hints: Dict[str, Any] = None,
    config: Dict[str, Any] = None,
    context: Context = None
) -> str:
    """Emit a single seed Splunk query over one or more indices to harvest error-like events"""
    try:
        query_tool = get_splunk_query_prompt_tool()
        arguments = {}
        
        if hints is not None:
            arguments["hints"] = hints
        if config is not None:
            arguments["config"] = config
        
        results = await query_tool.execute(arguments)
        
        if results and len(results) > 0:
            return results[0].text
        else:
            return "No splunk query prompt found"
            
    except Exception as e:
        return f"Error retrieving splunk query prompt: {str(e)}"

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
    print(f"  - splunk_indexes: List available Splunk indexes")
    print(f"  - splunk_export: Export Splunk search results to various formats")
    print(f"  - splunk_monitor: Start continuous monitoring of Splunk logs")
    print(f"  - get_chain_1_prompt: Get a ready-to-use prompt for Chain 1 processing")
    print(f"  - get_chain_2_prompt: Get a ready-to-use prompt for Chain 2 processing")
    print(f"  - get_chain_3_prompt: Get a ready-to-use prompt for Chain 3 processing")
    print(f"  - expand_fetch_by_traceids: Expand and fetch logs by trace IDs")
    print(f"  - find_splunk_index_in_repo: Search codebase for Splunk index names")
    print(f"  - group_results_by_traceid: Group search results by trace ID")
    print(f"  - logs_debug_entry: Entry point for logs debugging workflow")
    print(f"  - get_logs_evaluation_prompt: Get a ready-to-use prompt for logs evaluation")
    print(f"  - get_resolve_splunk_index: Determine correct Splunk environment and indices")
    print(f"  - get_root_cause_identification_prompt: Get a ready-to-use prompt for root cause identification")
    print(f"  - splunk_log_analysis: Analyze Splunk logs for patterns and insights")
    print(f"  - get_splunk_query_prompt: Get a ready-to-use prompt for Splunk queries")
    
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
