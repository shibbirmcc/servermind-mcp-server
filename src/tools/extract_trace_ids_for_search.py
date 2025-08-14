"""Extract trace IDs from grouped error logs and provide manual extraction prompt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

import structlog
from mcp.types import Tool, TextContent

logger = structlog.get_logger(__name__)


class ExtractTraceIdsForSearchTool:
    """
    Step 5.5 in the chain - Manual ID extraction prompt tool.
    Input: JSON output from group_error_logs containing grouped error patterns.
    Behavior: 
      - Returns a detailed prompt instructing the user to manually extract trace IDs
      - Includes the grouped logs data for the user to work with
      - Provides clear instructions on how to proceed to the next step
    Output: Prompt for manual trace ID extraction with grouped logs data.
    """

    def __init__(self):
        self.tool_name = "extract_trace_ids_for_search"
        self.description = (
            "Provide manual extraction prompt for trace/correlation IDs from grouped error logs output. "
            "Returns detailed instructions and the grouped logs data for manual ID extraction."
        )
        # Load the extraction prompt
        self._prompt_path = Path(__file__).parent.parent / "prompts" / "extract_trace_ids_for_search.txt"
        self._prompt_template = self._prompt_path.read_text(encoding="utf-8")

    def get_tool_definition(self) -> Tool:
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "grouped_logs": {
                        "type": "string",
                        "description": "JSON string output from group_error_logs containing grouped error patterns with chosen_id values."
                    },
                    "deduplicate": {
                        "type": "boolean",
                        "description": "Whether to remove duplicate trace IDs (default: true).",
                        "default": True
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time for trace search (default: -24h).",
                        "default": "-24h"
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time for trace search (default: now).",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results per trace search (default: 4000).",
                        "default": 4000
                    }
                },
                "required": ["grouped_logs"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # 1) Parse input arguments
        grouped_logs_str = arguments.get("grouped_logs", "")
        earliest_time = arguments.get("earliest_time", "-24h")
        latest_time = arguments.get("latest_time", "now")
        max_results = arguments.get("max_results", 4000)

        if not grouped_logs_str:
            return [TextContent(type="text", text="❌ Missing required 'grouped_logs' parameter.")]

        # 2) Validate the grouped logs JSON format
        try:
            grouped_logs = json.loads(grouped_logs_str)
        except json.JSONDecodeError as e:
            return [TextContent(type="text", text=f"❌ Invalid JSON in grouped_logs: {e}")]

        if not isinstance(grouped_logs, list):
            return [TextContent(type="text", text="❌ Expected grouped_logs to be a JSON array of groups.")]

        # 3) Quick analysis of the data for context
        total_groups = len(grouped_logs)
        groups_with_chosen_id = sum(1 for group in grouped_logs 
                                   if isinstance(group, dict) and group.get("chosen_id"))

        # 4) Construct the response with prompt and data
        response_parts = [
            "📋 **MANUAL TRACE ID EXTRACTION REQUIRED**",
            "",
            "Please follow the instructions below to extract trace IDs from the grouped error logs.",
            "",
            "=" * 80,
            "EXTRACTION INSTRUCTIONS",
            "=" * 80,
            "",
            self._prompt_template,
            "",
            "=" * 80,
            "GROUPED LOGS DATA TO PROCESS",
            "=" * 80,
            "",
            f"**Context:** {total_groups} error groups found, {groups_with_chosen_id} groups have chosen_id values",
            "",
            "```json",
            json.dumps(grouped_logs, indent=2),
            "```",
            "",
            "=" * 80,
            "NEXT STEP PARAMETERS",
            "=" * 80,
            "",
            "After extracting the trace IDs, use these parameters for splunk_trace_search_by_ids:",
            f"- earliest_time: \"{earliest_time}\"",
            f"- latest_time: \"{latest_time}\"",
            f"- max_results: {max_results}",
            "",
            "**Remember:** The extracted trace IDs should be passed as the 'trace_ids' parameter to splunk_trace_search_by_ids."
        ]

        response_text = "\n".join(response_parts)
        return [TextContent(type="text", text=response_text)]


# Global instance + exports
_extract_tool = ExtractTraceIdsForSearchTool()


def get_tool_definition() -> Tool:
    return _extract_tool.get_tool_definition()


async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _extract_tool.execute(arguments)
