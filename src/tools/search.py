"""Search tool implementation for MCP."""

from typing import Dict, Any, List, Optional
import json
import structlog
from mcp.types import Tool, TextContent
from ..splunk.client import SplunkClient, SplunkSearchError, SplunkConnectionError
from ..config import get_config

logger = structlog.get_logger(__name__)


class SplunkSearchTool:
    """MCP tool for executing Splunk searches."""

    def __init__(self):
        """Initialize the search tool."""
        self.config = get_config()
        self._client: Optional[SplunkClient] = None

    def get_client(self) -> SplunkClient:
        """Get or create Splunk client instance."""
        if self._client is None:
            self._client = SplunkClient(self.config.splunk)
        return self._client

    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for splunk_search."""
        return Tool(
            name="splunk_search",
            description="Execute a Splunk search query using SPL (Search Processing Language). "
                        "Optionally return raw results for chaining.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SPL search query to execute"
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time for search (e.g., '-24h', '-1d', '2023-01-01T00:00:00')",
                        "default": "-24h"
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time for search (e.g., 'now', '2023-01-02T00:00:00')",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 10000
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Search timeout in seconds",
                        "default": 300,
                        "minimum": 10,
                        "maximum": 3600
                    },
                    "raw_return": {
                        "type": "boolean",
                        "description": "If true, return raw JSON results for MCP chaining instead of human-readable format.",
                        "default": False
                    }
                },
                "required": ["query"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the splunk_search tool.

        Args:
            arguments: Tool arguments containing query and search parameters

        Returns:
            List[TextContent]: Search results and metadata
        """
        try:
            # Extract arguments
            query = arguments.get("query")
            if not query:
                raise ValueError("Query parameter is required")

            earliest_time = arguments.get("earliest_time", "-24h")
            latest_time = arguments.get("latest_time", "now")
            max_results = arguments.get("max_results", self.config.mcp.max_results_default)
            timeout = arguments.get("timeout", self.config.mcp.search_timeout)
            raw_return = arguments.get("raw_return", False)

            logger.info("Executing Splunk search",
                        query=query,
                        earliest_time=earliest_time,
                        latest_time=latest_time,
                        max_results=max_results,
                        raw_return=raw_return)
