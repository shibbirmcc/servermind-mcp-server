#!/usr/bin/env python3
"""
MCP server with SSE transport exposing Splunk tools and automated issue creation
Following the working FastMCP pattern
"""

import sys
from typing import Dict, Any, List, Optional
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
from src.tools.automated_issue_creation import execute_automated_issue_creation
from src.config import get_config

# Get configuration to determine server name
config = get_config()
server_name = config.mcp.server_name

# Create FastMCP instance
mcp = FastMCP(server_name)

@mcp.tool()
async def splunk_search(
    query: str,
    earliest_time: str = "-24h",
    latest_time: str = "now", 
    max_results: int = 100,
    timeout: int = 300,
    context: Context = None
) -> str:
    """Execute a Splunk search query using SPL (Search Processing Language).
    
    Args:
        query: SPL search query to execute (e.g., 'index=main error', 'search sourcetype=access_log | stats count by host')
        earliest_time: Start time for search. Supports relative time (e.g., '-24h', '-1d', '-7d') or absolute time (e.g., '2023-01-01T00:00:00')
        latest_time: End time for search. Use 'now' for current time or absolute time (e.g., '2023-01-02T00:00:00')
        max_results: Maximum number of results to return (1-10000, default: 100)
        timeout: Search timeout in seconds (10-3600, default: 300)
    
    Returns:
        Formatted search results with analysis suggestions and metadata
    """
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
    filter_pattern: str = None,
    include_disabled: bool = True,
    sort_by: str = "name",
    sort_order: str = "asc",
    context: Context = None
) -> str:
    """List and get information about Splunk indexes with filtering and sorting options.
    
    Args:
        filter_pattern: Optional pattern to filter index names (case-insensitive substring match)
        include_disabled: Whether to include disabled indexes in the results (default: True)
        sort_by: Field to sort results by - options: 'name', 'size', 'events', 'earliest', 'latest' (default: 'name')
        sort_order: Sort order - 'asc' for ascending or 'desc' for descending (default: 'asc')
    
    Returns:
        Comprehensive index information including size, event counts, time ranges, and usage suggestions
    """
    try:
        # Get the indexes tool and execute
        indexes_tool = get_indexes_tool()
        arguments = {}
        
        if filter_pattern is not None:
            arguments["filter_pattern"] = filter_pattern
        if include_disabled is not None:
            arguments["include_disabled"] = include_disabled
        if sort_by != "name":
            arguments["sort_by"] = sort_by
        if sort_order != "asc":
            arguments["sort_order"] = sort_order
        
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
    """Export Splunk search results to various formats for data analysis and integration.
    
    Args:
        query: SPL search query to execute and export results (e.g., 'index=main | stats count by host')
        format: Export format - 'json' (programmatic use), 'csv' (spreadsheets), or 'xml' (structured data) (default: 'json')
        earliest_time: Start time for search. Supports relative time (e.g., '-24h', '-1d') or absolute time (default: '-24h')
        latest_time: End time for search. Use 'now' for current time or absolute time (default: 'now')
        max_results: Maximum number of results to export (1-50000, default: 1000)
        timeout: Search timeout in seconds (10-3600, default: 300)
        fields: Specific fields to include in export (optional, exports all fields if not specified)
    
    Returns:
        Exported data in the specified format with size information and processing suggestions
    """
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
    """Start continuous monitoring of Splunk logs with specified intervals for real-time analysis.
    
    This tool creates a single monitoring session that runs in the background, collecting logs 
    at regular intervals and buffering results for analysis. Only one monitoring session 
    can be active at a time.
    
    Args:
        action: Action to perform:
            - 'start': Begin monitoring with a query and interval (requires query parameter)
            - 'stop': Stop the current monitoring session
            - 'status': Get status of the current monitoring session
            - 'get_results': Retrieve buffered results from the session
        query: SPL search query to monitor (required for 'start' action, e.g., 'index=main error | head 100')
        interval: Monitoring interval in seconds (10-3600, default: 60) - how often to check for new data
        max_results: Maximum results per monitoring check (1-10000, default: 1000)
        timeout: Search timeout in seconds for each monitoring check (10-300, default: 60)
        clear_buffer: Whether to clear results buffer after retrieving (for get_results action, default: True)
    
    Returns:
        Monitoring session status, buffered results, or confirmation messages with analysis suggestions
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


# Automated Issue Creation Tool (available if either GitHub or JIRA is configured)
if config.github is not None or config.jira is not None:
    @mcp.tool()
    async def automated_issue_creation(
        splunk_query: str,
        platform: str = "github",
        github_repo: str = None,
        jira_project: str = None,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_results: int = 100,
        severity_threshold: str = "medium",
        group_similar_errors: bool = True,
        auto_assign: str = None,
        custom_labels: List[str] = None,
        context: Context = None
    ) -> str:
        """Automatically analyze Splunk errors and create GitHub or JIRA issues with detailed error analysis.
        
        This tool performs comprehensive error analysis on Splunk search results and automatically creates
        well-formatted issues in GitHub or JIRA with detailed error information, recommendations, and context.
        
        Args:
            splunk_query: Splunk search query to find errors (e.g., 'index=main error | head 50')
            platform: Platform to create issues on ('github', 'jira', or 'both')
            github_repo: GitHub repository name in format 'owner/repo' (required if platform is 'github' or 'both')
            jira_project: JIRA project key (required if platform is 'jira' or 'both')
            earliest_time: Start time for Splunk search (default: '-24h')
            latest_time: End time for Splunk search (default: 'now')
            max_results: Maximum number of Splunk results to analyze (1-1000, default: 100)
            severity_threshold: Minimum severity level to create issues for ('low', 'medium', 'high', 'critical')
            group_similar_errors: Whether to group similar errors into single issues (default: True)
            auto_assign: Username to automatically assign created issues to (optional)
            custom_labels: Additional custom labels to add to created issues (optional)
        
        Returns:
            Comprehensive analysis report with created issue details and error analysis
        """
        try:
            arguments = {
                "splunk_query": splunk_query,
                "platform": platform,
                "earliest_time": earliest_time,
                "latest_time": latest_time,
                "max_results": max_results,
                "severity_threshold": severity_threshold,
                "group_similar_errors": group_similar_errors
            }
            
            if github_repo is not None:
                arguments["github_repo"] = github_repo
            if jira_project is not None:
                arguments["jira_project"] = jira_project
            if auto_assign is not None:
                arguments["auto_assign"] = auto_assign
            if custom_labels is not None:
                arguments["custom_labels"] = custom_labels
            
            results = await execute_automated_issue_creation(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "Failed to execute automated issue creation"
                
        except Exception as e:
            return f"Error in automated issue creation: {str(e)}"

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
    
    # Splunk tools (always available)
    print("  Splunk Tools:")
    print(f"    - splunk_search: Execute Splunk search queries")
    print(f"    - splunk_indexes: List available Splunk indexes")
    print(f"    - splunk_export: Export Splunk search results to various formats")
    print(f"    - splunk_monitor: Start continuous monitoring of Splunk logs")
    
    # Automated Issue Creation tool (if either GitHub or JIRA is configured)
    if config.github is not None or config.jira is not None:
        print("  Automated Analysis Tools:")
        print(f"    - automated_issue_creation: Analyze Splunk errors and automatically create issues")
    else:
        print("  Automated Analysis Tools: Not available (requires GitHub or JIRA configuration)")
    
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
