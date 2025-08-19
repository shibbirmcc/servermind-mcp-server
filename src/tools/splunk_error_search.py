"""Splunk Error Search tool for MCP with standalone invocation, plan chaining, and detailed no-results info."""

"""
Design notes for splunk_error_search:

1. Richer "no logs found" explanation:
   - Include exactly which indices were searched.
   - Include all time ranges attempted (whether user-specified or auto-broadened).
   - Clearly state that no matching 'ERROR'/'error' logs were found in any attempt.
   - Provide possible next steps (adjust time range, indices, or keywords) so Cline can echo suggestions naturally.

2. Standalone invocation support:
   - Tool can be invoked directly by the user (outside of chain).
   - Accepts `indices` and `earliest_time`/`latest_time` as arguments.
   - If `earliest_time` is provided, do NOT auto-broaden search — respect the exact user request.
   - If `earliest_time` is omitted, automatically broaden search progressively (-24h, -48h, -72h) until results found or max range reached.

3. Chaining behavior:
   - If results are found and running as part of a multi-step plan, return both:
       a) Raw logs (JSON) for next tool consumption.
       b) A plan JSON object instructing the next step (group_error_logs).
"""

from typing import Dict, Any, List
import json
from pathlib import Path
from string import Template
import structlog
from mcp.types import Tool, TextContent
from .search import execute_splunk_query_raw_only

logger = structlog.get_logger(__name__)


class SplunkErrorSearchTool:
    """MCP tool for finding recent error logs in given Splunk indices and chaining to grouping step."""

    def __init__(self):
        self._plan_tpl_path = Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt"
        self._plan_tpl = Template(self._plan_tpl_path.read_text(encoding="utf-8"))

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="splunk_error_search",
            description=(
                "Search for error logs in Splunk indices. Use this tool in two scenarios:\n\n"
                "1. **Initial workflow step**: When routing from splunk_indexes with structured parameters\n"
                "2. **User feedback routing**: When user provides feedback after 'no logs found' and you can confidently extract specific indices\n\n"
                "User feedback examples that should route here:\n"
                "- 'try payment indices instead' → extract ['prod_payments', 'prod_billing']\n"
                "- 'search the auth logs' → extract ['prod_auth', 'prod_authentication']\n"
                "- 'use prod_users and prod_billing' → extract ['prod_users', 'prod_billing']\n"
                "- 'search longer time range' → use same indices, extend earliest_time\n\n"
                "Only use if you can confidently (≥70%) extract specific index names. If user feedback is vague "
                "('try other stuff', 'search somewhere else'), ask for clarification instead.\n\n"
                "Alternative routing:\n"
                "- If user wants to explore available indices first → use splunk_indexes\n"
                "- If user wants to start completely over → use logs_debug_entry"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "indices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific Splunk index names to search (e.g., ['prod_payments', 'prod_auth'])"
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time for search. Use '-24h' for initial searches, extend to '-48h', '-7d' for retry scenarios. If omitted, will auto-broaden."
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time for search (default 'now').",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 500,
                        "minimum": 1,
                        "maximum": 10000
                    },
                    "context_note": {
                        "type": "string",
                        "description": "Optional note about why this search is being performed (e.g., 'user requested payment indices', 'retry with longer time range')"
                    }
                },
                "required": ["indices"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            indices = arguments.get("indices")
            if not indices or not isinstance(indices, list):
                raise ValueError("At least one index must be provided as a list of strings.")

            latest_time = arguments.get("latest_time", "now")
            max_results = arguments.get("max_results", 500)
            user_provided_earliest = "earliest_time" in arguments and arguments["earliest_time"]

            if user_provided_earliest:
                # Only try the provided range
                time_ranges = [arguments["earliest_time"]]
            else:
                # Auto-broaden if earliest_time not specified
                time_ranges = ["-24h", "-48h", "-72h"]

            found_results = None
            used_range = None

            for tr in time_ranges:
                index_filter = " OR ".join([f'index="{idx}"' for idx in indices])
                spl = f'search ({index_filter}) ("ERROR" OR "error")'

                logger.info("Running Splunk error search", query=spl, earliest_time=tr, latest_time=latest_time)

                raw_logs = await execute_splunk_query_raw_only(
                    query=spl,
                    earliest_time=tr,
                    latest_time=latest_time,
                    max_results=max_results
                )

                if raw_logs:
                    found_results = raw_logs
                    used_range = tr
                    break

            if not found_results:
                # Build detailed no-results explanation
                attempted_ranges = ", ".join(time_ranges)
                indices_str = ", ".join(indices)
                msg = (
                    f"ℹ️ **No matching error logs found**\n\n"
                    f"- **Indices searched:** {indices_str}\n"
                    f"- **Time ranges attempted:** {attempted_ranges}\n"
                    f"- **Query pattern:** ('ERROR' OR 'error')\n\n"
                    f"Possible reasons:\n"
                    f"- No error logs were generated in these time windows.\n"
                    f"- The logs may be stored in different indices.\n"
                    f"- The error keywords differ (e.g., WARN, FAIL, etc.).\n\n"
                    f"💡 You can refine the search by:\n"
                    f"- Adjusting the time range.\n"
                    f"- Adding or changing indices.\n"
                    f"- Searching for different keywords.\n"
                )
                return [TextContent(type="text", text=msg)]

            # If found logs and invoked as part of chain → send plan for grouping
            plan_text = self._plan_tpl.substitute(
                nextTool="group_error_logs",
                argsJson=json.dumps({"logs": found_results}, ensure_ascii=False),
                reason=f"Found error logs in the last {used_range[1:]} hours, proceed to group them by similarity."
            )

            return [
                TextContent(type="text", text=plan_text)  # plan to next step with logs included
            ]

        except Exception as e:
            logger.error("Error in splunk_error_search", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Error Search Failed**\n\nError: {e}"
            )]


# Global instance
_error_search_tool = SplunkErrorSearchTool()


def get_tool_definition() -> Tool:
    return _error_search_tool.get_tool_definition()


async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _error_search_tool.execute(arguments)
