#!/usr/bin/env python3
"""
MCP server with SSE transport exposing Splunk, JIRA, and GitHub tools
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
from src.tools.jira import (
    execute_jira_search, execute_jira_projects, execute_jira_create_issue, execute_jira_issue
)
from src.tools.github import (
    execute_github_repositories, execute_github_repository, 
    execute_github_issues, execute_github_create_issue, execute_github_pull_requests
)
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

# JIRA Tools (only registered if JIRA is configured)
if config.jira is not None:
    @mcp.tool()
    async def jira_search(
        jql: str,
        max_results: int = 50,
        fields: List[str] = None,
        context: Context = None
    ) -> str:
        """Search for JIRA issues using JQL (JIRA Query Language).
        
        Args:
            jql: JQL query string (e.g., 'project = PROJ AND status = Open', 'assignee = currentUser()')
            max_results: Maximum number of results to return (1-1000, default: 50)
            fields: List of fields to include (e.g., ['key', 'summary', 'status', 'assignee'])
        
        Returns:
            Formatted JIRA search results with analysis suggestions
        """
        try:
            arguments = {"jql": jql, "max_results": max_results}
            if fields is not None:
                arguments["fields"] = fields
            
            results = await execute_jira_search(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No results returned from JIRA search"
                
        except Exception as e:
            return f"Error executing JIRA search: {str(e)}"

    @mcp.tool()
    async def jira_projects(context: Context = None) -> str:
        """Get list of available JIRA projects.
        
        Returns:
            List of JIRA projects with details and usage examples
        """
        try:
            results = await execute_jira_projects({})
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No projects found"
                
        except Exception as e:
            return f"Error getting JIRA projects: {str(e)}"

    @mcp.tool()
    async def jira_create_issue(
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "Medium",
        assignee: str = None,
        labels: List[str] = None,
        context: Context = None
    ) -> str:
        """Create a new JIRA issue from error analysis or problem report.
        
        Args:
            project_key: JIRA project key where the issue should be created (e.g., 'PROJ', 'DEV')
            summary: Brief summary of the issue or error
            description: Detailed description of the error, analysis, and steps to reproduce
            issue_type: Type of issue to create ('Bug', 'Task', 'Story', 'Epic', 'Incident')
            priority: Priority level ('Highest', 'High', 'Medium', 'Low', 'Lowest')
            assignee: Username to assign the issue to (optional)
            labels: Labels to add to the issue (e.g., ['error-analysis', 'splunk', 'urgent'])
        
        Returns:
            Created JIRA issue details with direct link
        """
        try:
            arguments = {
                "project_key": project_key,
                "summary": summary,
                "description": description,
                "issue_type": issue_type,
                "priority": priority
            }
            if assignee is not None:
                arguments["assignee"] = assignee
            if labels is not None:
                arguments["labels"] = labels
            
            results = await execute_jira_create_issue(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "Failed to create JIRA issue"
                
        except Exception as e:
            return f"Error creating JIRA issue: {str(e)}"

    @mcp.tool()
    async def jira_issue(
        issue_key: str,
        fields: List[str] = None,
        context: Context = None
    ) -> str:
        """Get detailed information about a specific JIRA issue.
        
        Args:
            issue_key: JIRA issue key (e.g., 'PROJ-123', 'DEV-456')
            fields: List of fields to include (optional)
        
        Returns:
            Detailed JIRA issue information
        """
        try:
            arguments = {"issue_key": issue_key}
            if fields is not None:
                arguments["fields"] = fields
            
            results = await execute_jira_issue(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No issue found"
                
        except Exception as e:
            return f"Error getting JIRA issue: {str(e)}"

# GitHub Tools (only registered if GitHub is configured)
if config.github is not None:
    @mcp.tool()
    async def github_repositories(
        user_or_org: str = None,
        repo_type: str = "all",
        max_results: int = 30,
        context: Context = None
    ) -> str:
        """Get list of GitHub repositories for a user or organization.
        
        Args:
            user_or_org: Username or organization name (leave empty for authenticated user's repositories)
            repo_type: Repository type filter ('all', 'owner', 'public', 'private', 'member')
            max_results: Maximum number of results to return (1-100, default: 30)
        
        Returns:
            List of GitHub repositories with statistics and usage suggestions
        """
        try:
            arguments = {"repo_type": repo_type, "max_results": max_results}
            if user_or_org is not None:
                arguments["user_or_org"] = user_or_org
            
            results = await execute_github_repositories(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No repositories found"
                
        except Exception as e:
            return f"Error getting GitHub repositories: {str(e)}"

    @mcp.tool()
    async def github_repository(
        repo_name: str,
        context: Context = None
    ) -> str:
        """Get detailed information about a specific GitHub repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')
        
        Returns:
            Detailed GitHub repository information
        """
        try:
            arguments = {"repo_name": repo_name}
            
            results = await execute_github_repository(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No repository found"
                
        except Exception as e:
            return f"Error getting GitHub repository: {str(e)}"

    @mcp.tool()
    async def github_issues(
        repo_name: str,
        state: str = "open",
        labels: List[str] = None,
        assignee: str = None,
        max_results: int = 30,
        context: Context = None
    ) -> str:
        """Get issues from a GitHub repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')
            state: Issue state filter ('open', 'closed', 'all')
            labels: List of label names to filter by (e.g., ['bug', 'enhancement'])
            assignee: Username to filter by assignee
            max_results: Maximum number of results to return (1-100, default: 30)
        
        Returns:
            List of GitHub issues with analysis
        """
        try:
            arguments = {"repo_name": repo_name, "state": state, "max_results": max_results}
            if labels is not None:
                arguments["labels"] = labels
            if assignee is not None:
                arguments["assignee"] = assignee
            
            results = await execute_github_issues(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No issues found"
                
        except Exception as e:
            return f"Error getting GitHub issues: {str(e)}"

    @mcp.tool()
    async def github_create_issue(
        repo_name: str,
        title: str,
        body: str,
        labels: List[str] = None,
        assignees: List[str] = None,
        context: Context = None
    ) -> str:
        """Create a new GitHub issue from error analysis or problem report.
        
        Args:
            repo_name: Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')
            title: Brief title of the issue or error
            body: Detailed description of the error, analysis, and steps to reproduce
            labels: Labels to add to the issue (e.g., ['bug', 'error-analysis', 'splunk', 'urgent'])
            assignees: Usernames to assign the issue to (e.g., ['username1', 'username2'])
        
        Returns:
            Created GitHub issue details with direct link
        """
        try:
            arguments = {
                "repo_name": repo_name,
                "title": title,
                "body": body
            }
            if labels is not None:
                arguments["labels"] = labels
            if assignees is not None:
                arguments["assignees"] = assignees
            
            results = await execute_github_create_issue(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "Failed to create GitHub issue"
                
        except Exception as e:
            return f"Error creating GitHub issue: {str(e)}"

    @mcp.tool()
    async def github_pull_requests(
        repo_name: str,
        state: str = "open",
        max_results: int = 30,
        context: Context = None
    ) -> str:
        """Get pull requests from a GitHub repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')
            state: Pull request state filter ('open', 'closed', 'all')
            max_results: Maximum number of results to return (1-100, default: 30)
        
        Returns:
            List of GitHub pull requests with analysis
        """
        try:
            arguments = {"repo_name": repo_name, "state": state, "max_results": max_results}
            
            results = await execute_github_pull_requests(arguments)
            
            if results and len(results) > 0:
                return results[0].text
            else:
                return "No pull requests found"
                
        except Exception as e:
            return f"Error getting GitHub pull requests: {str(e)}"

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
    
    # JIRA tools (if configured)
    if config.jira is not None:
        print("  JIRA Tools:")
        print(f"    - jira_create_issue: Create new JIRA issues from error analysis")
    else:
        print("  JIRA Tools: Not configured (set JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN)")
    
    # GitHub tools (if configured)
    if config.github is not None:
        print("  GitHub Tools:")
        print(f"    - github_create_issue: Create new GitHub issues from error analysis")
    else:
        print("  GitHub Tools: Not configured (set GITHUB_TOKEN)")
    
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
