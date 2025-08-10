"""Resolve splunk index tool implementation for MCP."""

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


class ResolveSplunkIndexTool(BasePromptTool):
    """MCP tool for serving resolve splunk index."""

    def __init__(self):
        super().__init__(
            tool_name="get_resolve_splunk_index",
            description=(
                "Determine the correct Splunk environment and index(es) to query for a debugging "
                "request in a deployed environment (prod, staging, qa, uat, preprod, dev, canary, "
                "preview, playground, sandbox, demo, beta, or custom). This tool delegates index "
                "discovery to find_splunk_index_in_repo, which may return multiple candidate indices "
                "when the user is at a parent folder containing several services. After candidates are "
                "found, this tool forwards ALL indices to splunk_query_prompt so the seed query can "
                "search across them. If no indices are known yet, it plans a call to "
                "find_splunk_index_in_repo with loop-safety (status/attempt)."
            ),
            prompt_filename="resolve_splunk_index.txt",
        )


# Global resolve splunk index tool instance
_resolve_splunk_index_tool = ResolveSplunkIndexTool()


def get_resolve_splunk_index_tool() -> ResolveSplunkIndexTool:
    """Get the global resolve splunk index tool instance."""
    return _resolve_splunk_index_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for resolve splunk index."""
    return _resolve_splunk_index_tool.get_tool_definition()


def _resolve_env(arguments: Dict[str, Any]) -> Optional[str]:
    """Resolve target env from hints, config, or userIntent tokens."""
    hints = arguments.get("hints") or {}
    config = arguments.get("config") or {}
    user_intent = (arguments.get("userIntent") or "").strip()

    if hints.get("envAny"):
        return str(hints["envAny"])
    if config.get("env"):
        return str(config["env"])
    if config.get("defaultEnv"):
        return str(config["defaultEnv"])

    # naive token scan from user intent (kept simple on purpose)
    for token in user_intent.lower().split():
        if token in ENV_TOKENS:
            return token
    return None


def _unique_indices(found_indices: List[Dict[str, Any]]) -> List[str]:
    """Extract unique non-empty index strings from helper results."""
    seen = set()
    result: List[str] = []
    for item in found_indices or []:
        if not isinstance(item, dict):
            continue
        ix = (item.get("index") or "").strip()
        if ix and ix not in seen:
            seen.add(ix)
            result.append(ix)
    return result


def _render_plan_template(next_tool: str, args: Dict[str, Any], reason: str) -> str:
    """Load the txt template and inject nextTool/argsJson/reason."""
    template = _resolve_splunk_index_tool._get_prompt()
    plan_text = template.replace("{{nextTool}}", next_tool)
    plan_text = plan_text.replace("{{argsJson}}", json.dumps(args))
    plan_text = plan_text.replace("{{reason}}", reason)
    return plan_text


async def execute_resolve_splunk_index(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the resolve splunk index tool."""
    env = _resolve_env(arguments) or ""

    status = (arguments.get("status") or "").strip()  # "found" | "ambiguous" | "not_found" | ""
    attempt = int(arguments.get("attempt") or 0)

    # Accept both shapes: foundIndices(list) or legacy foundIndex(str)
    found_indices_list = arguments.get("foundIndices") or []
    legacy_single = arguments.get("foundIndex")
    if legacy_single and not found_indices_list:
        found_indices_list = [{
            "index": legacy_single, "env": env or None,
            "servicePath": None, "sourceFile": ""
        }]

    indices = _unique_indices(found_indices_list)

    # 1) If we have indices (from found/ambiguous), forward ALL to splunk_query_prompt
    if status in ("found", "ambiguous") and indices:
        args = {
            "hints": {"envAny": env},
            "config": {
                "env": env,
                "indices": indices,          # 1..N indices to OR together
                "defaultIndex": indices[0],  # harmless fallback for consumers expecting one
            },
        }
        reason = (
            f"Resolved {len(indices)} index candidate(s) for env '{env}'. "
            f"Status: {status}."
        )
        plan_text = _render_plan_template("splunk_query_prompt", args, reason)
        return [TextContent(type="text", text=plan_text)]

    # 2) If helper reported not_found, guard against infinite loops
    if status == "not_found":
        if attempt < 2:
            # Retry: broaden search space and bump attempt
            args = {"env": env, "attempt": attempt + 1, "broaden": True}
            reason = "Retry repo scan with broader paths/patterns."
            plan_text = _render_plan_template("find_splunk_index_in_repo", args, reason)
            return [TextContent(type="text", text=plan_text)]
        else:
            # Stop looping — ask user to specify index explicitly
            # Return a prompt that expects JSON { "indices": ["idx1","idx2"] } or { "index":"idx" }
            prompt_text = (
                "No Splunk index was found for env='"
                + env
                + "'.\n"
                "Please provide one or more indices to use (e.g., [\"prod_app\"]).\n"
                "Respond JSON only as either:\n"
                "{ \"indices\": [\"<index>\", \"<index2>\"] }\n"
                "or\n"
                "{ \"index\": \"<index>\" }\n"
            )
            plan_text = json.dumps({
                "kind": "plan",
                "next": [
                    {
                        "type": "prompt",
                        "title": "Specify Splunk indices",
                        "prompt": prompt_text
                    }
                ],
                "autoExecuteHint": True
            })
            return [TextContent(type="text", text=plan_text)]

    # 3) Default: no indices known yet → delegate to helper to search the repo
    args = {"env": env, "attempt": attempt}
    reason = "Need to locate Splunk index/indices for env before querying."
    plan_text = _render_plan_template("find_splunk_index_in_repo", args, reason)
    return [TextContent(type="text", text=plan_text)]
