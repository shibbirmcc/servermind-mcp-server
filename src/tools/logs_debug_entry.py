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
    "🚀 PRIMARY ENTRY POINT for logs debugging workflow - START HERE for general debugging! "
    "Use this tool when the user expresses ANY troubleshooting intent related to deployed environments. "
    "Trigger phrases include: 'something is wrong', 'think there's an issue', 'investigate', 'debug', "
    "'check logs', 'what's happening', 'errors in', 'problems with', 'issues in', 'look into', "
    "'troubleshoot', 'analyze', or similar investigative language. "
    "Environment indicators: prod, production, staging, qa, uat, preprod, dev, canary, preview, "
    "playground, sandbox, demo, beta, or any custom environment names. DO NOT limit to the listed ones, read behind the lines. "
    "Examples: 'think something is wrong in staging', 'debug prod issues', 'check what's happening in qa', "
    "'investigate errors in production', 'something seems off in the demo environment'. "
    "This tool accepts any arguments and passes them through to the complete debugging workflow."
),
            # No LLM prompt needed; we just render a plan.
            prompt_filename=None,
        )
        # Use shared plan template (JSON with $nextTool / $argsJson / $reason)
        self._plan_tpl = Template(
            (Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt").read_text(encoding="utf-8")
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
