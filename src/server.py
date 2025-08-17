#!/usr/bin/env python3
"""
MCP server with SSE transport exposing Splunk tools and automated issue creation
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
from src.tools.automated_issue_creation import execute_automated_issue_creation
from src.tools.issue_reader import get_issue_reader_tool
from src.tools.test_reproduction import get_test_reproduction_tool
from src.tools.bug_fix_executor import get_bug_fix_executor_tool
from src.config import get_config

# Get configuration to determine server name
config = get_config()
server_name = config.mcp.server_name
from src.tools.logs_debug_entry import get_logs_debug_entry_tool
from src.tools.root_cause_identification_prompt import get_root_cause_identification_prompt_tool
from src.tools.splunk_trace_search_by_ids import get_splunk_trace_search_by_ids_tool
from src.tools.splunk_error_search import get_tool_definition as get_error_logs_tool, execute as execute_splunk_error_search
from src.tools.analyze_traces_narrative import get_analyze_traces_narrative_tool
from src.tools.group_error_logs_prompt import get_tool_definition as get_group_error_logs_tool, execute as execute_group_error_logs
from src.tools.ticket_split_prepare import get_tool_definition as get_ticket_split_prepare_tool
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


# Automated Issue Creation Tool (always available - uses external MCP servers)
@mcp.tool()
async def automated_issue_creation(
    main_ticket: Dict[str, Any],
    root_causes_per_service: List[Dict[str, Any]],
    platform: str = "auto",
    github_repo: str = None,
    jira_project: str = None,
    context: Context = None
) -> str:
    """Generate instructions for creating GitHub/JIRA issues from root cause analysis.

    This tool takes structured analysis data from previous debugging steps and generates
    well-formatted issue creation instructions for GitHub or JIRA.

    Args:
        main_ticket: Main ticket from root cause identification with trace_id, title, description, etc.
        root_causes_per_service: Root causes per service from root cause identification
        platform: Platform to create issues on ('github', 'jira', 'both', or 'auto' for intelligent selection)
        github_repo: GitHub repository name in format 'owner/repo' (required if platform is 'github' or 'both')
        jira_project: JIRA project key (required if platform is 'jira' or 'both')

    Returns:
        Detailed issue creation instructions with formatted titles, descriptions, and metadata
    """
    try:
        arguments = {
            "main_ticket": main_ticket,
            "root_causes_per_service": root_causes_per_service,
            "platform": platform
        }

        if github_repo is not None:
            arguments["github_repo"] = github_repo
        if jira_project is not None:
            arguments["jira_project"] = jira_project

        results = await execute_automated_issue_creation(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "Failed to execute automated issue creation"

    except Exception as e:
        return f"Error in automated issue creation: {str(e)}"

@mcp.tool()
async def splunk_trace_search_by_ids(
    trace_ids: List[str],
    indexes: List[str] = None,
    trace_id_field: str = "traceId",
    earliest_time: str = "-24h",
    latest_time: str = "now",
    max_results: int = 1000,
    timeout: int = 300,
    include_raw: bool = True,
    sort_by_time: bool = True,
    additional_fields: List[str] = None,
    context: Context = None
) -> str:
    """Search Splunk for traces by specific trace IDs.

    This tool allows you to find all log entries associated with one or more trace IDs
    across specified indexes or all available indexes.
    """
    try:
        trace_search_tool = get_splunk_trace_search_by_ids_tool()
        # Only pass parameters that the underlying tool expects
        arguments = {
            "ids": trace_ids,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "max_results": max_results
        }

        if indexes is not None:
            arguments["indices"] = indexes  # Note: "indices" not "indexes"

        results = await trace_search_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from trace search"

    except Exception as e:
        return f"Error executing trace search: {str(e)}"

@mcp.tool()
async def splunk_error_search(
    indices: List[str],
    earliest_time: str = None,
    latest_time: str = "now",
    max_results: int = 500,
    context: Context = None
) -> str:
    """Search Splunk for logs containing 'ERROR' or 'error' in one or more indices.
    If no earliest_time is provided, automatically broadens search up to 3 days.
    If still no results, returns a detailed no-results summary."""
    try:
        arguments = {
            "indices": indices,
            "latest_time": latest_time,
            "max_results": max_results
        }

        if earliest_time is not None:
            arguments["earliest_time"] = earliest_time

        results = await execute_splunk_error_search(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from error search"

    except Exception as e:
        return f"Error executing error search: {str(e)}"

@mcp.tool()
async def error_logs(
    logs: List[Dict[str, Any]],
    source: str = "unknown",
    filter_level: str = "ERROR",
    max_results: int = 100,
    group_by: str = "none",
    context: Context = None
) -> str:
    """Process and analyze error logs from various sources"""
    try:
        error_logs_tool = get_error_logs_tool()
        arguments = {
            "logs": logs,
            "source": source,
            "filter_level": filter_level,
            "max_results": max_results,
            "group_by": group_by
        }

        results = await error_logs_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from error logs processing"

    except Exception as e:
        return f"Error processing error logs: {str(e)}"

@mcp.tool()
async def analyze_traces_narrative(
    traces: List[Dict[str, Any]] = None,
    events: List[Dict[str, Any]] = None,
    id: str = None,
    kind: str = None,
    mode: str = "auto",
    verbosity: str = "normal",
    context: Context = None
) -> str:
    """Analyze traces and generate narrative analysis with cross-service story and per-service breakdown.

    This tool takes trace data and creates a comprehensive narrative analysis including:
    - Cross-service story bullets showing the flow of events
    - Per-service breakdown with detailed analysis
    - Root cause identification preparation

    Args:
        traces: Preferred format - array of trace objects with id and events (e.g., [{"id": "trace1", "events": [...]}])
        events: Fallback format - single trace's events array (will be wrapped into traces[0])
        id: Optional id for the single-trace 'events' fallback
        kind: If present and == 'data', may include 'traces' wrapper from previous step
        mode: Analysis mode - 'auto' (adaptive), 'simple' (basic), or 'full' (comprehensive) (default: 'auto')
        verbosity: Output verbosity - 'brief', 'normal', or 'verbose' (default: 'normal')

    Returns:
        JSON analysis with narrative story and service breakdown, plus plan for root cause identification
    """
    try:
        analyze_tool = get_analyze_traces_narrative_tool()
        arguments = {
            "mode": mode,
            "verbosity": verbosity
        }

        if traces is not None:
            arguments["traces"] = traces
        if events is not None:
            arguments["events"] = events
        if id is not None:
            arguments["id"] = id
        if kind is not None:
            arguments["kind"] = kind

        results = await analyze_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from trace analysis"

    except Exception as e:
        return f"Error analyzing traces: {str(e)}"

@mcp.tool()
async def logs_debug_entry(
    context: Context = None,
    **kwargs
) -> str:
    """🚀 PRIMARY ENTRY POINT for debugging issues like 'something is wrong in staging'.

    This is the recommended starting point for any general debugging scenario. It automatically
    guides you through the complete debugging workflow: discovering indexes → finding errors →
    analyzing traces → identifying root causes → creating tickets.

    Use this when you have general issues like:
    - 'Something is wrong in staging'
    - 'Users are reporting errors'
    - 'Service seems to be failing'
    - Any debugging scenario where you need to investigate problems
    """
    try:
        logs_debug_tool = get_logs_debug_entry_tool()
        results = await logs_debug_tool.execute(kwargs)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from logs debug entry"

    except Exception as e:
        return f"Error in logs debug entry: {str(e)}"

@mcp.tool()
async def group_error_logs(
    logs: List[Dict[str, Any]],
    max_groups: int = 10,
    context: Context = None
) -> str:
    """Group ERROR logs into semantic clusters and pick one representative trace/correlation ID per group.

    Args:
        logs: Raw Splunk events (array of objects) from splunk_error_search
        max_groups: Soft cap for number of groups to aim for (model-level guidance)

    Returns:
        Grouped error logs with representative IDs and plan for next step
    """
    try:
        arguments = {
            "logs": logs,
            "max_groups": max_groups
        }

        results = await execute_group_error_logs(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from error log grouping"

    except Exception as e:
        return f"Error grouping error logs: {str(e)}"


@mcp.tool()
async def root_cause_identification_prompt(
    analysis: Dict[str, Any],
    mode: str = "auto",
    confidence_floor: float = 0.6,
    context: Context = None
) -> str:
    """Confirm service-level root causes based on narrative analysis and prepare for ticket creation.

    Args:
        analysis: Structured analysis object from analyze_traces_narrative
        mode: Analysis mode - 'auto', 'strict', or 'exploratory' (default: 'auto')
        confidence_floor: Minimum confidence to keep a hypothesis (0.0-1.0, default: 0.6)

    Returns:
        Root cause analysis results and plan for ticket preparation
    """
    try:
        root_cause_tool = get_root_cause_identification_prompt_tool()
        arguments = {
            "analysis": analysis,
            "mode": mode,
            "confidence_floor": confidence_floor
        }

        results = await root_cause_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from root cause identification"

    except Exception as e:
        return f"Error in root cause identification: {str(e)}"

@mcp.tool()
async def ticket_split_prepare(
    analysis: Dict[str, Any],
    root_cause: Dict[str, Any],
    title_prefix: str = "",
    mode: str = "auto",
    context: Context = None
) -> str:
    """Create ticket-ready items by combining cross-service analysis with per-service root causes.

    Args:
        analysis: Structured analysis from analyze_traces_narrative
        root_cause: Structured root-cause output from root_cause_identification_prompt
        title_prefix: Optional prefix for generated ticket titles (e.g., team or incident tag)
        mode: Processing mode - 'auto' or 'strict' (affects how aggressively subs are created)

    Returns:
        JSON list of ticket items (main and sub tickets) and plan for automated issue creation
    """
    try:
        ticket_tool = get_ticket_split_prepare_tool()
        arguments = {
            "analysis": analysis,
            "root_cause": root_cause,
            "title_prefix": title_prefix,
            "mode": mode
        }

        results = await ticket_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from ticket split preparation"

    except Exception as e:
        return f"Error in ticket split preparation: {str(e)}"

@mcp.tool()
async def issue_reader(
    issue_reference: str = None,
    platform: str = "auto",
    previous_output: str = None,
    github_repo: str = None,
    jira_project: str = None,
    issue_number: str = None,
    context: Context = None
) -> str:
    """Read GitHub or JIRA issues using CLI (preferred) or MCP servers (fallback).

    This tool reads issue details from GitHub or JIRA using multiple methods:
    1. CLI tools (gh for GitHub, jira for JIRA) - preferred method
    2. MCP servers (GitHub/Atlassian MCP servers) - fallback method
    3. Setup instructions if both methods fail

    Args:
        issue_reference: Direct issue reference (e.g., 'owner/repo#123' for GitHub, 'PROJECT-456' for JIRA)
        platform: Explicit platform selection ('github', 'jira', or 'auto' for intelligent detection)
        previous_output: JSON output from automated_issue_creation to extract issue info
        github_repo: GitHub repository in format 'owner/repo' (if not in issue_reference)
        jira_project: JIRA project key (if not in issue_reference)
        issue_number: Issue number/key (if not in issue_reference)

    Returns:
        Detailed issue information including title, description, status, comments, and metadata
    """
    try:
        issue_reader_tool = get_issue_reader_tool()
        arguments = {
            "platform": platform
        }

        if issue_reference is not None:
            arguments["issue_reference"] = issue_reference
        if previous_output is not None:
            arguments["previous_output"] = previous_output
        if github_repo is not None:
            arguments["github_repo"] = github_repo
        if jira_project is not None:
            arguments["jira_project"] = jira_project
        if issue_number is not None:
            arguments["issue_number"] = issue_number

        results = await issue_reader_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from issue reader"

    except Exception as e:
        return f"Error reading issue: {str(e)}"

@mcp.tool()
async def test_reproduction(
    issue_reader_output: str,
    test_types: List[str] = None,
    service_discovery_mode: str = "both",
    local_search_paths: List[str] = None,
    git_repositories: List[str] = None,
    test_framework: str = "auto",
    output_directory: str = "tests/reproductions",
    context: Context = None
) -> str:
    """Generate comprehensive tests from issue reader output.

    Creates unit tests, integration tests, and reproduction tests for each ticket.
    Supports service discovery from local filesystem or git repositories.

    Args:
        issue_reader_output: JSON output from issue_reader containing multiple tickets with descriptions and analysis
        test_types: Types of tests to generate (unit, integration, reproduction, regression)
        service_discovery_mode: How to discover services (local, git, both)
        local_search_paths: Local paths to search for service folders
        git_repositories: Git repository URLs to search for services
        test_framework: Preferred testing framework (pytest, unittest, jest, junit, auto)
        output_directory: Directory to output generated tests

    Returns:
        Comprehensive test reproduction results with generated test files and instructions
    """
    try:
        test_reproduction_tool = get_test_reproduction_tool()
        arguments = {
            "issue_reader_output": issue_reader_output,
            "output_directory": output_directory
        }

        if test_types is not None:
            arguments["test_types"] = test_types
        if service_discovery_mode != "both":
            arguments["service_discovery_mode"] = service_discovery_mode
        if local_search_paths is not None:
            arguments["local_search_paths"] = local_search_paths
        if git_repositories is not None:
            arguments["git_repositories"] = git_repositories
        if test_framework != "auto":
            arguments["test_framework"] = test_framework

        results = await test_reproduction_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from test reproduction"

    except Exception as e:
        return f"Error in test reproduction: {str(e)}"

@mcp.tool()
async def bug_fix_executor(
    test_reproduction_output: str,
    issue_reader_output: str,
    service_paths: List[str] = None,
    max_iterations: int = 5,
    test_framework: str = "auto",
    fix_strategy: str = "auto",
    backup_code: bool = True,
    context: Context = None
) -> str:
    """Execute tests from test_reproduction and iteratively fix bugs until tests pass.

    Takes test reproduction output and issue reader context to implement fixes.
    Runs tests, analyzes failures, generates fixes, applies them, and repeats until tests pass.

    Args:
        test_reproduction_output: JSON output from test_reproduction containing test paths and ticket info
        issue_reader_output: JSON output from issue_reader containing ticket details and root cause analysis
        service_paths: Paths to service source code directories
        max_iterations: Maximum number of fix iterations (default: 5)
        test_framework: Test framework to use - pytest, jest, junit, auto (default: auto)
        fix_strategy: How aggressively to apply fixes - conservative, aggressive, auto (default: auto)
        backup_code: Whether to backup original code before fixing (default: True)

    Returns:
        Comprehensive bug fix execution report with iteration details and results
    """
    try:
        bug_fix_tool = get_bug_fix_executor_tool()
        arguments = {
            "test_reproduction_output": test_reproduction_output,
            "issue_reader_output": issue_reader_output,
            "max_iterations": max_iterations,
            "test_framework": test_framework,
            "fix_strategy": fix_strategy,
            "backup_code": backup_code
        }

        if service_paths is not None:
            arguments["service_paths"] = service_paths

        results = await bug_fix_tool.execute(arguments)

        if results and len(results) > 0:
            return results[0].text
        else:
            return "No results returned from bug fix executor"

    except Exception as e:
        return f"Error in bug fix executor: {str(e)}"

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
    print("  Core Splunk Tools:")
    print(f"    - splunk_search: Execute custom SPL queries (for advanced users with specific search needs)")
    print(f"    - splunk_indexes: List available indexes (for exploring data structure before searching)")
    print(f"    - splunk_error_search: Direct error search in specific indexes (when you know exact indexes to search)")
    print(f"    - splunk_export: Export search results to files (for data analysis and reporting)")
    print(f"    - splunk_monitor: Set up continuous monitoring (for ongoing surveillance of specific queries)")
    print(f"    - splunk_trace_search_by_ids: Search by known trace IDs (when you have specific trace identifiers)")
    print(f"    - error_logs: Process pre-retrieved log data (for analyzing logs already collected)")

    # Splunk tools (always available)
    print("  Splunk Tools:")
    print(f"    - splunk_search: Execute Splunk search queries")
    print(f"    - splunk_indexes: List available Splunk indexes")
    print(f"    - splunk_export: Export Splunk search results to various formats")
    print(f"    - splunk_monitor: Start continuous monitoring of Splunk logs")

    print("  Analysis & Workflow Tools:")
    print(f"    - logs_debug_entry: 🚀 START HERE for general debugging (e.g., 'something is wrong in staging')")
    print(f"    - group_error_logs: Group ERROR logs into semantic clusters and extract trace IDs")
    print(f"    - analyze_traces_narrative: Generate narrative analysis with cross-service story")
    print(f"    - root_cause_identification_prompt: Confirm service-level root causes")
    print(f"    - ticket_split_prepare: Create ticket-ready items from analysis")

    # Automated Issue Creation tool (always available - uses external MCP servers)
    print("  Issue Management & Testing:")
    print(f"    - automated_issue_creation: Analyze Splunk errors and create issues via external MCP servers")
    print(f"      Note: Requires external Atlassian or GitHub MCP servers for issue creation")
    print(f"    - issue_reader: Read GitHub or JIRA issues using CLI (preferred) or MCP servers (fallback)")
    print(f"      Note: Supports gh CLI, jira CLI, or external MCP servers")
    print(f"    - test_reproduction: Generate comprehensive tests from issue reader output")
    print(f"      Note: Creates unit, integration, and reproduction tests for tickets")
    print(f"    - bug_fix_executor: Execute tests and iteratively fix bugs until tests pass")
    print(f"      Note: Runs tests, analyzes failures, generates fixes, and applies them iteratively")

    # JIRA tools (if configured)
    if config.jira is not None:
        print("  JIRA Tools:")
        print(f"    - jira_search: Search JIRA issues using JQL")
        print(f"    - jira_projects: List available JIRA projects")
        print(f"    - jira_issue: Get detailed JIRA issue information")
    else:
        print("  JIRA Tools: Not configured (set JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN)")

    # GitHub tools (if configured)
    if config.github is not None:
        print("  GitHub Tools:")
        print(f"    - github_repositories: List GitHub repositories")
        print(f"    - github_repository: Get detailed repository information")
        print(f"    - github_issues: Get repository issues")
        print(f"    - github_pull_requests: Get repository pull requests")
    else:
        print("  GitHub Tools: Not configured (set GITHUB_TOKEN)")

    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
