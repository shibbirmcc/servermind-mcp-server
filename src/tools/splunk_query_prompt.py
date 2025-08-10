"""Splunk query prompt tool implementation for MCP (multi-index seed, ID-agnostic)."""

from __future__ import annotations

import json
from typing import Dict, Any, List

from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


# Include common variants so results are inspectable
FIELDS = [
    "_time", "host", "service", "level", "logger", "msg",
    "traceId", "trace_id", "correlationId", "correlation_id", "corrId",
    "requestId", "reqId", "req_id", "status", "path", "errorCode", "traceKey"
]


class SplunkQueryPromptTool(BasePromptTool):
    """MCP tool that emits a seed SPL query over ONE OR MORE indices (ID-agnostic via traceKey)."""

    def __init__(self):
        super().__init__(
            tool_name="get_splunk_query_prompt",
            description=(
                "Emit a single seed Splunk query over one or more indices (OR'ed) to harvest error-like "
                "events in the given time window (default -4h..now). No env/partition filters at this stage. "
                "Normalize the request/trace/correlation identifier into 'traceKey' using common field names "
                "(traceId, correlationId, requestId, etc.) and ensure traceKey is non-empty. Include stitching "
                "fields, sort newest first, and cap rows."
            ),
            prompt_filename="splunk_query_prompt.txt",
        )


_splunk_query_prompt_tool = SplunkQueryPromptTool()


def get_splunk_query_prompt_tool() -> SplunkQueryPromptTool:
    return _splunk_query_prompt_tool


def get_tool_definition() -> Tool:
    return _splunk_query_prompt_tool.get_tool_definition()


def _window(hints: Dict[str, Any]) -> tuple[str, str]:
    earliest = (hints.get("earliest") or "-4h").strip()
    latest = (hints.get("latest") or "now").strip()
    return earliest, latest


def _indices_clause(indices: List[str]) -> str:
    clean = [str(ix).strip() for ix in (indices or []) if str(ix).strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return f"index={clean[0]}"
    ors = " OR ".join(f"index={ix}" for ix in clean)
    return f"({ors})"


def _build_seed_query(indices: List[str], earliest: str, latest: str) -> str:
    idx_clause = _indices_clause(indices)
    fields = " ".join(FIELDS)
    if not idx_clause:
        return ""
    # Normalize id → traceKey, then filter on it
    return (
        f'{idx_clause} earliest={earliest} latest={latest} '
        f'| eval traceKey=coalesce(traceId, trace_id, correlationId, correlation_id, corrId, requestId, reqId, req_id) '
        f'| fields {fields} '
        f'| eval _lvl=lower(coalesce(level,"")) '
        f'| eval _err=if(_lvl="error" OR _lvl="fatal" OR _lvl="critical" OR status>=500 '
        f'OR isnotnull(errorCode) OR like(lower(msg), "%exception%") OR like(lower(msg), "%error%"), 1, 0) '
        f'| where _err=1 AND isnotnull(traceKey) AND traceKey!="" '
        f'| sort - _time '
        f'| table {fields} '
        f'| head 5000'
    )


def _render_plan(query: str, indices: List[str], template: str, earliest: str, latest: str) -> str:
    idx_preview = ", ".join(indices[:3]) + ("…" if len(indices) > 3 else "")
    reason = f"Probe indices [{idx_preview}] to harvest error-like seeds via traceKey ({earliest}..{latest})."
    return template.replace("{{query}}", json.dumps(query)[1:-1]).replace("{{reason}}", reason)


async def execute_splunk_query_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    arguments = dict(arguments or {})
    hints = arguments.get("hints") or {}
    config = arguments.get("config") or {}

    indices = config.get("indices") or []
    if not indices:
        fallback = json.dumps({
            "kind": "plan",
            "next": [{
                "type": "prompt",
                "title": "Provide indices",
                "prompt": (
                    "No indices were provided to splunk_query_prompt.\n"
                    "Respond JSON only as { \"indices\": [\"<index>\", \"<index2>\"] }."
                )
            }],
            "autoExecuteHint": True
        })
        return [TextContent(type="text", text=fallback)]

    earliest, latest = _window(hints)
    query = _build_seed_query(indices, earliest, latest)
    template = _splat_template()
    plan_text = _render_plan(query, indices, template, earliest, latest)
    return [TextContent(type="text", text=plan_text)]


def _splat_template() -> str:
    try:
        return _splunk_query_prompt_tool._get_prompt()
    except Exception:
        return (
            '{\n'
            '  "kind": "plan",\n'
            '  "next": [\n'
            '    { "type": "tool", "toolName": "splunk_search", "args": { "query": "{{query}}" }, "reason": "{{reason}}" }\n'
            '  ],\n'
            '  "autoExecuteHint": true\n'
            '}\n'
        )
