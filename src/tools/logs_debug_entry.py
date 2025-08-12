"""Logs debug entry tool (minimal on-ramp → next: splunk_indexes)."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List

import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class LogsDebugEntryTool(BasePromptTool):
    """
    Minimal entry point for the log-based debugging workflow.

    Purpose:
      - Catch user intent for investigating issues/errors/anomalies in a deployed environment.
      - Do not perform any parsing or validation here.
      - Immediately hand off to step 2 (`splunk_indexes`) with the incoming arguments.

    Notes:
      - Keep this tool lightweight so it's easy to invoke as the gateway into the MCP chain.
      - Any environment/index resolution happens in later steps.
    """

    def __init__(self):
        super().__init__(
            tool_name="get_logs_debug_entry",
            description=(
    "On-ramp and gatekeeper for the log-based debugging chain. "
    "Its sole job is to read the user's request and decide if BOTH are true: "
    "1) something is wrong (anomaly/error/incident/unexpected behaviour), AND "
    "2) the problem concerns a DEPLOYED environment (prod/staging/qa/uat/preprod/dev/canary/"
    "preview/playground/sandbox/demo/beta or a custom named deployment). "
    "Do NOT rely on repo files or env configs to infer deployment context—decide from the user's words. "
    "If BOTH conditions appear true, proceed to the next step (e.g., list Splunk indices). "
    "If either is missing, stop and give brief guidance (ask which deployed env, or suggest local repro). "
    "Positive cues (deployed): mentions of prod/staging/qa/canary, clusters/pods/services, URLs, release tags, "
    "on-call alerts, 5xx spikes, timeouts in ‘the site/app’. "
    "Negative cues (local): phrases like ‘my test is failing’, ‘unit test fails’, ‘pytest/jest failure’, "
    "‘docker-compose up’, ‘localhost’, ‘feature branch only’, or purely how-to questions. "
    "Trigger on language like ‘check logs’, ‘debug’, ‘investigate’, ‘what’s wrong’, ‘anything strange’ "
    "ONLY when it’s clearly about a deployed system."
),
            # No LLM prompt needed; we just render a plan.
            prompt_filename=None,
        )
        # Shared plan template (JSON with {{nextTool}} / {{argsJson}} / {{reason}})
        self._plan_tpl = Template(
            (Path(__file__).parent.parent / "shared_plan_template.txt").read_text(encoding="utf-8")
        )

    def get_tool_definition(self) -> Tool:
        # Accept any object; we just pass it along to the next step.
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "additionalProperties": True
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # Pass through whatever we received; no heuristics.
        args_for_next = dict(arguments or {})

        plan_json = self._plan_tpl.substitute(
            nextTool="splunk_indexes",
            argsJson=json.dumps(args_for_next, ensure_ascii=False),
            reason="Start log debug chain: list available Splunk indexes."
        )
        return [TextContent(type="text", text=plan_json)]


# Global instance / exports
_logs_debug_entry_tool = LogsDebugEntryTool()

def get_logs_debug_entry_tool() -> LogsDebugEntryTool:
    return _logs_debug_entry_tool

def get_tool_definition() -> Tool:
    return _logs_debug_entry_tool.get_tool_definition()

async def execute_logs_debug_entry(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _logs_debug_entry_tool.execute(arguments)
