"""Chain 2: root cause identification prompt tool (final step)."""

from __future__ import annotations

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


class RootCauseIdentificationPromptTool(BasePromptTool):
    def __init__(self):
        super().__init__(
            tool_name="root_cause_identification_prompt",
            description=(
                "From the incident analysis, propose up to 3 root-cause hypotheses. "
                "For each: evidence (log lines/services), mechanism, confidence (0–1), "
                "and a quick test to confirm/falsify. Outputs FINAL JSON (no further plan)."
            ),
            prompt_filename="root_cause_identification_prompt.txt",
        )


_root_cause_tool = RootCauseIdentificationPromptTool()


def get_root_cause_identification_prompt_tool() -> RootCauseIdentificationPromptTool:
    return _root_cause_tool


def get_tool_definition() -> Tool:
    return _root_cause_tool.get_tool_definition()


async def execute_root_cause_identification_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Expected args:
      { "analysis": "<string>" }
    Returns FINAL JSON with hypotheses; does not schedule another tool.
    """
    return await _root_cause_tool.execute(arguments)
