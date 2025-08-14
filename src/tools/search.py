"""Pure Splunk search tool - returns structured data only."""

from __future__ import annotations

import json
from typing import Dict, Any, List
import structlog
from mcp.types import Tool, TextContent

logger = structlog.get_logger(__name__)


class SplunkSearchTool:
    """
    Pure SPL query execution tool that returns structured JSON data.
    No formatting or presentation logic - designed for tool chaining.
    """

    def __init__(self):
        """Initialize the Splunk search tool."""
        self._client = None

    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for splunk_search."""
        return Tool(
            name="splunk_search",
            description=(
                "Execute custom SPL queries directly (for advanced users who want to write their own SPL). "
                "Use this when you need to run specific Splunk queries that aren't covered by specialized tools."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "title": "Query",
                        "type": "string"
                    },
                    "earliest_time": {
                        "default": "-24h",
                        "title": "Earliest Time",
                        "type": "string"
                    },
                    "latest_time": {
                        "default": "now",
                        "title": "Latest Time",
                        "type": "string"
                    },
                    "max_results": {
                        "default": 100,
                        "title": "Max Results",
                        "type": "integer"
                    },
                    "timeout": {
                        "default": 300,
                        "title": "Timeout",
                        "type": "integer"
                    }
                },
                "required": ["query"],
                "title": "splunk_searchArguments"
            }
        )

    def get_client(self):
        """Get or create Splunk client."""
        if self._client is None:
            from ..splunk.client import SplunkClient
            from ..config import get_config
            config = get_config()
            self._client = SplunkClient(config.splunk)
        return self._client

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the splunk_search tool and return structured JSON data."""
        try:
            # Validate required arguments
            query = arguments.get("query")
            if not query or not isinstance(query, str):
                return [TextContent(
                    type="text",
                    text="❌ **Invalid Query**\n\n'query' must be a non-empty string."
                )]

            # Extract optional parameters with defaults
            earliest_time = arguments.get("earliest_time", "-24h")
            latest_time = arguments.get("latest_time", "now")
            max_results = int(arguments.get("max_results", 100))
            timeout = int(arguments.get("timeout", 300))

            # Validate parameters
            if max_results < 1 or max_results > 10000:
                return [TextContent(
                    type="text",
                    text="❌ **Invalid Parameters**\n\nmax_results must be between 1 and 10000."
                )]

            if timeout < 10 or timeout > 3600:
                return [TextContent(
                    type="text",
                    text="❌ **Invalid Parameters**\n\ntimeout must be between 10 and 3600 seconds."
                )]

            # Get client and execute search
            client = self.get_client()

            search_kwargs = {
                'earliest_time': earliest_time,
                'latest_time': latest_time,
                'max_results': max_results,
                'timeout': timeout
            }

            results = client.execute_search(query, **search_kwargs)

            # Return structured JSON data
            response_data = {
                "results": results,
                "metadata": {
                    "query": query,
                    "earliest_time": earliest_time,
                    "latest_time": latest_time,
                    "result_count": len(results),
                    "max_results": max_results,
                    "timeout": timeout
                }
            }

            return [TextContent(
                type="text",
                text=json.dumps(response_data, ensure_ascii=False, indent=2)
            )]

        except Exception as e:
            logger.error("Splunk search error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Search Error**\n\n"
                     f"Search execution failed: {e}\n\n"
                     f"Please check your SPL query syntax and try again."
            )]

    def cleanup(self):
        """Clean up resources."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception as e:
                logger.warning("Error during client cleanup", error=str(e))
            finally:
                self._client = None


# Global search tool instance
_search_tool = SplunkSearchTool()


async def execute_splunk_query(query: str, earliest_time: str = "-24h", 
                              latest_time: str = "now", max_results: int = 100, 
                              timeout: int = 300) -> Dict[str, Any]:
    """
    Vanilla helper function for internal tool-to-tool search calls.
    Returns raw dictionary instead of TextContent to avoid breaking chains.
    
    Args:
        query: SPL query string
        earliest_time: Start time for search
        latest_time: End time for search  
        max_results: Maximum number of results
        timeout: Search timeout in seconds
        
    Returns:
        Dict with 'results' and 'metadata' keys
        
    Raises:
        Exception: If search fails
    """
    # Validate parameters
    if not query or not isinstance(query, str):
        raise ValueError("'query' must be a non-empty string")
        
    if max_results < 1 or max_results > 10000:
        raise ValueError("max_results must be between 1 and 10000")
        
    if timeout < 10 or timeout > 3600:
        raise ValueError("timeout must be between 10 and 3600 seconds")
    
    # Get client and execute search
    client = _search_tool.get_client()
    
    search_kwargs = {
        'earliest_time': earliest_time,
        'latest_time': latest_time,
        'max_results': max_results,
        'timeout': timeout
    }
    
    results = client.execute_search(query, **search_kwargs)
    
    # Return structured data
    return {
        "results": results,
        "metadata": {
            "query": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "result_count": len(results),
            "max_results": max_results,
            "timeout": timeout
        }
    }


def get_search_tool() -> SplunkSearchTool:
    """Get the global search tool instance."""
    return _search_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for splunk_search."""
    return _search_tool.get_tool_definition()


async def execute_search(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the splunk_search tool."""
    return await _search_tool.execute(arguments)
