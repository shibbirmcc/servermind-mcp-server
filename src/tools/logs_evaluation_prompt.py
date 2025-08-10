"""Log evaluation tool implementation for MCP."""

from __future__ import annotations

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


class SplunkLogEvaluationTool(BasePromptTool):
    """
    MCP tool for evaluating whether seed Splunk logs are sufficient
    to identify a small set of representative traceKeys for full-log retrieval.

    This tool does NOT hardcode which identifier to use; the prompt
    should normalize traceId, correlationId, requestId, etc. into 'traceKey'
    and cluster by message similarity.
    """

    def __init__(self):
        super().__init__(
            tool_name="splunk_log_evaluation",
            description=(
                "Given a reference to seed logs from an earlier Splunk search, "
                "analyze whether they are sufficient to pick representative traceKeys "
                "(traceId/correlationId/requestId variants) for full-log retrieval. "
                "Cluster similar error events by message and choose up to k representatives. "
                "If none can be chosen, return 'not_sufficient'. "
                "Otherwise, return a plan to call expand_fetch_by_traceids with the chosen traceKeys, "
                "earliest/latest time window, and optionally indices."
            ),
            prompt_filename="splunk_log_evaluation.txt",
        )


# Global instance
_splunk_log_evaluation_tool = SplunkLogEvaluationTool()


def get_splunk_log_evaluation_tool() -> SplunkLogEvaluationTool:
    """Return the global Splunk log evaluation tool instance."""
    return _splunk_log_evaluation_tool


def get_tool_definition() -> Tool:
    """Return the MCP tool definition for splunk_log_evaluation."""
    return _splunk_log_evaluation_tool.get_tool_definition()


async def execute_splunk_log_evaluation(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Execute the splunk_log_evaluation tool.

    Expected arguments:
    - logsRef: reference ID or handle to the seed logs
    - earliest/latest: time window for possible expansion
    - k: optional int, max clusters/traceKeys to choose (default 5)
    - indices: optional list of indices (can be forwarded to expand step)

    The prompt will do normalization and clustering.
    """
    return await _splunk_log_evaluation_tool.execute(arguments)
