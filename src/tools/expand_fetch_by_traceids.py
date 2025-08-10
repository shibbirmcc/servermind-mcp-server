"""Expand-by-traceIds tool implementation for MCP (ID-agnostic via traceKey)."""

from __future__ import annotations

import json
from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


class ExpandFetchByTraceIdsTool(BasePromptTool):
    """
    Build ONE consolidated SPL to fetch ALL logs for the selected traceKeys across indices,
    in the given time window. No level filter; sort ascending for narrative.
    """

    def __init__(self):
        super().__init__(
            tool_name="expand_fetch_by_traceids",
            description=(
                "Given a list of representative traceIds (traceKeys) and a time window, "
                "emit ONE Splunk query that pulls all logs for those traceKeys across one or more indices. "
                "Normalize the identifier into traceKey with coalesce(traceId, correlationId, requestId, ...). "
                "Return a plan to run splunk_search."
            ),
            prompt_filename="expand_fetch_by_traceids.txt",
        )


_expand_fetch_tool = ExpandFetchByTraceIdsTool()


def get_expand_fetch_by_traceids_tool() -> ExpandFetchByTraceIdsTool:
    return _expand_fetch_tool


def get_tool_definition() -> Tool:
    return _expand_fetch_tool.get_tool_definition()


async def execute_expand_fetch_by_traceids(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Expected args:
      {
        "traceIds": ["t1","t2",...],          # required
        "indices": ["idxA","idxB"],           # optional (but recommended)
        "earliest": "-4h", "latest": "now"    # optional defaults
      }
    """
    # Pass through to prompt; it will build the SPL and return plan → splunk_search
    args = dict(arguments or {})
    args.setdefault("earliest", "-4h")
    args.setdefault("latest", "now")
    args["traceIds"] = list(dict.fromkeys(args.get("traceIds") or []))  # dedupe
    return await _expand_fetch_tool.execute(args)
