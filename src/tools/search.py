"""Generic Splunk search tool."""

from __future__ import annotations

import json
from typing import Dict, Any, List
import structlog
from mcp.types import Tool, TextContent

logger = structlog.get_logger(__name__)

class SplunkSearchTool:
    """
    Run a generic SPL query against Splunk.
    Can optionally return raw JSON results (for chaining) instead of summarizing.
    """

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="splunk_search",
            description=(
                "Execute a raw SPL query against Splunk indices and return the results. "
                "Can either summarize in plain text (default) or return the raw JSON results "
                "if raw_return=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Raw SPL query to execute."
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time (e.g., '-24h', '-2d', ISO).",
                        "default": "-24h"
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time (e.g., 'now').",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max total events to return.",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": 20000
                    },
                    "raw_return": {
                        "type": "boolean",
                        "description": "If true, return raw JSON instead of summarizing.",
                        "default": False
                    }
                },
                "required": ["query"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            query = arguments.get("query")
            if not query or not isinstance(query, str):
                return [TextContent(type="text", text="❌ 'query' must be a non-empty string.")]

            earliest = arguments.get("earliest_time", "-24h")
            latest = arguments.get("latest_time", "now")
            max_results = int(arguments.get("max_results", 1000))
            raw_return = bool(arguments.get("raw_return", False))

            # ---- Splunk API call simulation ----
            # Replace with real Splunk API integration
            simulated_results = {
                "results": [
                    {"_time": "2025-08-10T10:00:00Z", "level": "ERROR", "_raw": "Example log message 1"},
                    {"_time": "2025-08-10T10:05:00Z", "level": "ERROR", "_raw": "Example log message 2"}
                ]
            }
            # ------------------------------------

            if raw_return:
                return [TextContent(type="json", text=json.dumps(simulated_results, ensure_ascii=False))]

            # Summarized output
            summary_lines = [
                f"- {_['_time']} — {_['_raw']}" for _ in simulated_results.get("results", [])
            ]
            return [TextContent(type="text", text="\n".join(summary_lines))]

        except Exception as e:
            logger.error("splunk_search failed", error=str(e))
            return [TextContent(type="text", text=f"❌ **Search failed**\n\n{e}")]


# Global instance / exports
_tool = SplunkSearchTool()

def get_tool_definition() -> Tool:
    return _tool.get_tool_definition()

async def execute_search(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _tool.execute(arguments)


def get_search_tool() -> SplunkSearchTool:
    """Get the global search tool instance."""
    return _tool

            # Get client and execute search
            client = self.get_client()

            search_kwargs = {
                'earliest_time': earliest_time,
                'latest_time': latest_time,
                'max_results': max_results,
                'timeout': timeout
            }

            results = client.execute_search(query, **search_kwargs)

            # Format results for MCP response
            return self._format_search_results(query, results, search_kwargs, raw_return)

        except SplunkConnectionError as e:
            logger.error("Splunk connection error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Connection Error**\n\n"
                     f"Failed to connect to Splunk: {e}\n\n"
                     f"Please check your Splunk configuration and ensure the server is accessible."
            )]

        except SplunkSearchError as e:
            logger.error("Splunk search error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Search Error**\n\n"
                     f"Search execution failed: {e}\n\n"
                     f"Please check your SPL query syntax and try again."
            )]

        except ValueError as e:
            logger.error("Invalid arguments", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Invalid Arguments**\n\n"
                     f"Error: {e}\n\n"
                     f"Please provide valid search parameters."
            )]

        except Exception as e:
            logger.error("Unexpected error in search tool", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Unexpected Error**\n\n"
                     f"An unexpected error occurred: {e}\n\n"
                     f"Please try again or contact support if the issue persists."
            )]

    def _format_search_results(self, query: str, results: List[Dict[str, Any]],
                             search_kwargs: Dict[str, Any]) -> List[TextContent]:
        """Format search results for MCP response.

        Args:
            query: Original search query
            results: Search results from Splunk
            search_kwargs: Search parameters used

        Returns:
            List[TextContent]: Formatted results
        """
        result_count = len(results)

        # Create summary
        summary = (
            f"✅ **Splunk Search Completed**\n\n"
            f"**Query:** `{query}`\n"
            f"**Time Range:** {search_kwargs['earliest_time']} to {search_kwargs['latest_time']}\n"
            f"**Results:** {result_count} events\n"
            f"**Max Results:** {search_kwargs['max_results']}\n\n"
        )

        if result_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No results found for the specified search criteria."
            )]

        # Format results
        formatted_results = summary + "**Search Results:**\n\n"

        for i, result in enumerate(results[:10], 1):  # Show first 10 results in detail
            formatted_results += f"**Result {i}:**\n"

            # Show key fields first
            key_fields = ['_time', '_raw', 'host', 'source', 'sourcetype', 'index']
            shown_fields = set()

            for field in key_fields:
                if field in result:
                    value = result[field]
                    if field == '_raw':
                        # Truncate raw events if too long
                        if len(str(value)) > 200:
                            value = str(value)[:200] + "..."
                    formatted_results += f"  - **{field}:** {value}\n"
                    shown_fields.add(field)

            # Show other fields
            other_fields = {k: v for k, v in result.items()
                          if k not in shown_fields and not k.startswith('_')}

            if other_fields:
                formatted_results += "  - **Other fields:** "
                field_strs = [f"{k}={v}" for k, v in list(other_fields.items())[:5]]
                formatted_results += ", ".join(field_strs)
                if len(other_fields) > 5:
                    formatted_results += f" (and {len(other_fields) - 5} more)"
                formatted_results += "\n"

            formatted_results += "\n"

        # Add summary if more results available
        if result_count > 10:
            formatted_results += f"... and {result_count - 10} more results.\n\n"

        # Add analysis suggestions
        formatted_results += self._generate_analysis_suggestions(query, results)

        return [TextContent(type="text", text=formatted_results)]

    def _generate_analysis_suggestions(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Generate analysis suggestions based on search results.

        Args:
            query: Original search query
            results: Search results

        Returns:
            str: Analysis suggestions
        """
        if not results:
            return ""

        suggestions = "**💡 Analysis Suggestions:**\n\n"

        # Analyze common fields
        common_fields = {}
        for result in results:
            for field in result.keys():
                if not field.startswith('_'):
                    common_fields[field] = common_fields.get(field, 0) + 1

        # Suggest field analysis
        if common_fields:
            top_fields = sorted(common_fields.items(), key=lambda x: x[1], reverse=True)[:3]
            field_names = [field for field, _ in top_fields]
            suggestions += f"- **Field Analysis:** Consider analyzing fields: {', '.join(field_names)}\n"
            suggestions += f"  Example: `{query} | stats count by {field_names[0]}`\n\n"

        # Suggest time-based analysis
        if any('_time' in result for result in results):
            suggestions += f"- **Time Analysis:** Analyze patterns over time\n"
            suggestions += f"  Example: `{query} | timechart count`\n\n"

        # Suggest error analysis if query contains error-related terms
        error_terms = ['error', 'fail', 'exception', 'warning', 'critical']
        if any(term in query.lower() for term in error_terms):
            suggestions += f"- **Error Analysis:** Investigate error patterns\n"
            suggestions += f"  Example: `{query} | stats count by host, source`\n\n"

        # Suggest top values analysis
        suggestions += f"- **Top Values:** Find most common occurrences\n"
        suggestions += f"  Example: `{query} | top limit=10 host`\n\n"

        return suggestions

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


def get_search_tool() -> SplunkSearchTool:
    """Get the global search tool instance."""
    return _search_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for splunk_search."""
    return _search_tool.get_tool_definition()


async def execute_search(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the splunk_search tool."""
    return await _search_tool.execute(arguments)
