"""Group expanded logs by traceKey for Chain 2 analysis."""

from __future__ import annotations

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


class GroupResultsByTraceIdTool(BasePromptTool):
    """
    Takes expanded logs and produces an array of traces, where each item is all logs
    (time-ordered) for a single traceKey. Returns a plan to the analysis step.
    """

    def __init__(self):
        super().__init__(
            tool_name="group_results_by_traceid",
            description=(
                "Group expanded Splunk results by the normalized identifier 'traceKey' "
                "(traceId/correlationId/requestId variants) and produce a structured list "
                "of traces suitable for narrative analysis. Returns a plan to analysis."
            ),
            prompt_filename="group_results_by_traceid.txt",
        )


_group_tool = GroupResultsByTraceIdTool()


def get_group_results_by_traceid_tool() -> GroupResultsByTraceIdTool:
    return _group_tool


def get_tool_definition() -> Tool:
    return _group_tool.get_tool_definition()


async def execute_group_results_by_traceid(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Expected args:
      { "logsRef": "state.expandLogs" }
    The prompt will group by traceKey and hand off to Chain 2.
    """
    return await _group_tool.execute(arguments)
