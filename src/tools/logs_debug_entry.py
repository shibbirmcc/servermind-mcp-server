"""Logs debug entry tool implementation for MCP."""

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional

from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


ENV_TOKENS = {
    "prod", "production", "staging", "qa", "uat", "preprod",
    "dev", "canary", "preview", "playground", "sandbox",
    "demo", "beta"
}


class LogsDebugEntryTool(BasePromptTool):
    """MCP tool for serving logs debug entry (on-ramp into the debug chain)."""

    def __init__(self):
        super().__init__(
            tool_name="get_logs_debug_entry",
            description=(
                "Generate the first Splunk query for debugging issues in a deployed environment "
                "(any env name: prod, staging, qa, uat, preprod, dev, canary, preview, playground, "
                "sandbox, demo, beta, or custom). When the user asks to inspect backend/app logs "
                "for anomalies/errors/incidents in a running deployment, produce one SPL seed query "
                "that finds recent error-like events and their traceIds in the correct environment/index. "
                "This is the entry point for any log-based debugging of deployed code; call this when "
                "users say check logs / debug / investigate / what's wrong / anything strange in any "
                "deployed environment."
            ),
            prompt_filename="logs_debug_entry.txt",
        )


# Global logs debug entry tool instance
_logs_debug_entry_tool = LogsDebugEntryTool()


def get_logs_debug_entry_tool() -> LogsDebugEntryTool:
    """Get the global logs debug entry tool instance."""
    return _logs_debug_entry_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for logs debug entry."""
    return _logs_debug_entry_tool.get_tool_definition()


def _render_plan_template(next_tool: str, args: Dict[str, Any], reason: str) -> str:
    """Load the txt template and inject nextTool/argsJson/reason."""
    template = _logs_debug_entry_tool._get_prompt()
    plan_text = template.replace("{{nextTool}}", next_tool)
    plan_text = plan_text.replace("{{argsJson}}", json.dumps(args))
    plan_text = plan_text.replace("{{reason}}", reason)
    return plan_text


def _coalesce_user_intent(arguments: Dict[str, Any]) -> str:
    """
    Try hard to recover the user's raw request text if Cline didn't pass userIntent.
    We check a few common context keys as a safety net.
    """
    # 1) Prefer explicit userIntent
    ui = arguments.get("userIntent")
    if isinstance(ui, str) and ui.strip():
        return ui.strip()

    # 2) Try common context keys Cline/UIs may attach
    for k in (
        "__clineLastUserMessage",
        "lastUserMessage",
        "message",
        "input",
        "query",
    ):
        v = arguments.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 3) Fallback to empty
    return ""


def _maybe_parse_env_from_text(text: str) -> Optional[str]:
    """
    Naive token-based env extraction for robustness.
    Accepts free-form tokens like 'playground' as well if explicitly present.
    """
    if not text:
        return None
    tokens = [t.strip(".,:;()[]{}").lower() for t in text.split()]
    # Exact known tokens
    for t in tokens:
        if t in ENV_TOKENS:
            return t
    # Heuristic: words that look like env tags (e.g., 'playground', 'preview')
    # Keep it permissive: if the text literally mentions 'playground'/'preview' etc. keep as-is.
    for t in tokens:
        if any(marker in t for marker in ("playground", "preview", "canary", "sandbox", "demo", "beta")):
            return t
    return None


async def execute_logs_debug_entry(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Execute the logs debug entry tool.

    Behavior:
    - This is a pure on-ramp. It forwards the incoming context to the resolver.
    - It is robust to missing args; will recover userIntent and env hints when possible.
    - It does not run an LLM; it renders a plan (from the template) to call get_resolve_splunk_index.
    """
    arguments = dict(arguments or {})

    # Build args for resolver, with safety nets
    user_intent = _coalesce_user_intent(arguments)
    incoming_hints = arguments.get("hints") or {}
    incoming_config = arguments.get("config") or {}

    # If no env hint provided, try to parse from the user text; otherwise keep user's hint
    env_hint = incoming_hints.get("envAny")
    if not env_hint:
        parsed_env = _maybe_parse_env_from_text(user_intent)
        if parsed_env:
            incoming_hints = dict(incoming_hints)  # copy
            incoming_hints["envAny"] = parsed_env

    args_for_resolver: Dict[str, Any] = {}
    if user_intent:
        args_for_resolver["userIntent"] = user_intent
    if incoming_hints:
        args_for_resolver["hints"] = incoming_hints
    if incoming_config:
        args_for_resolver["config"] = incoming_config

    # Render plan → get_resolve_splunk_index
    plan_text = _render_plan_template(
        next_tool="get_resolve_splunk_index",
        args=args_for_resolver,
        reason="Start debug chain: resolve environment/index before querying.",
    )

    return [TextContent(type="text", text=plan_text)]
