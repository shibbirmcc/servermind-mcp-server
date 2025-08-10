"""Chain 2: narrative analysis prompt tool."""

from __future__ import annotations

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


class SplunkLogAnalysisPromptTool(BasePromptTool):
    def __init__(self):
        super().__init__(
            tool_name="splunk_log_analysis_prompt",
            description=(
                "Analyze grouped multi-service logs and produce a concise chronology, "
                "causal links, anomalies, unknowns, and confidence. Returns a plan "
                "to root_cause_identification_prompt with the analysis text."
            ),
            prompt_filename="splunk_log_analysis_prompt.txt",
        )


_analysis_tool = SplunkLogAnalysisPromptTool()


def get_splunk_log_analysis_prompt_tool() -> SplunkLogAnalysisPromptTool:
    return _analysis_tool


def get_tool_definition() -> Tool:
    return _analysis_tool.get_tool_definition()


async def execute_splunk_log_analysis_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Expected args:
      { "logsRef": "state.groupedTraces" }
    """
    return await _analysis_tool.execute(arguments)
