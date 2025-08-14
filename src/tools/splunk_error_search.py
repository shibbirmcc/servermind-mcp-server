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
from .search import execute_search

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
                "Search Splunk for logs containing 'ERROR' or 'error' in one or more indices. "
                "If no earliest_time is provided, automatically broadens search up to 3 days. "
                "If still no results, returns a detailed no-results summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "indices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Splunk indices to search."
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time for search (e.g., '-24h', '-2d'). If omitted, will auto-broaden."
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

                search_results_content = await execute_search({
                    "query": spl,
                    "earliest_time": tr,
                    "latest_time": latest_time,
                    "max_results": max_results
                })

                if not search_results_content:
                    raise RuntimeError("Splunk search returned no content object.")

                search_payload = json.loads(search_results_content[0].text)
                results = search_payload.get("results", [])

                if results:
                    found_results = search_payload
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
                argsJson=json.dumps({"logs": found_results["results"]}, ensure_ascii=False),
                reason=f"Found error logs in the last {used_range[1:]} hours, proceed to group them by similarity."
            )

            return [
                TextContent(type="json", text=json.dumps(found_results)),  # raw logs
                TextContent(type="json", text=plan_text)                  # plan to next step
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
