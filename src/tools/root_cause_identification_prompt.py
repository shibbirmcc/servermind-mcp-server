"""Chain 2: root cause identification prompt tool (then → ticket split)."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List
import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class RootCauseIdentificationPromptTool(BasePromptTool):
    """
    Step 9 — Confirm service-level root causes based on the narrative analysis AND
    pass through story metadata for ticketing.

    Input:
      - analysis: structured JSON from analyze_traces_narrative (or JSON string).
        Must include per_trace[*].story (cross-service story bullets) and per_trace[*].services[*].

    Behavior:
      - No cross-service aggregation: produce root causes PER SERVICE.
      - Also emit data needed for main tickets (story, services involved) via the prompt output.
      - THEN: emit a plan to the ticket-prep step, passing both the original analysis and root-cause output.

    Output:
      - JSON block with root_cause results.
      - Plan block to `ticket_split_prepare` (or your chosen tool name).
    """

    def __init__(self):
        super().__init__(
            tool_name="root_cause_identification_prompt",
            description=(
                "Confirm per-service root causes from the analysis and pass along story details "
                "for main ticket creation (one main per trace). Produces JSON and chains to ticket prep."
            ),
            prompt_filename="root_cause_identification_prompt.txt",
        )
        # Shared plan template: contains {{nextTool}}, {{argsJson}}, {{reason}}
        self._plan_tpl = Template(
            (Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt").read_text(encoding="utf-8")
        )

    def get_tool_definition(self) -> Tool:
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis": {
                        "description": "Structured analysis object from analyze_traces_narrative, or a JSON string.",
                        "oneOf": [
                            {"type": "object"},
                            {"type": "string"}
                        ]
                    },
                    "mode": {
                        "type": "string",
                        "description": "auto | strict | exploratory (advisory for the prompt).",
                        "default": "auto",
                        "enum": ["auto", "strict", "exploratory"]
                    },
                    "confidence_floor": {
                        "type": "number",
                        "description": "Minimum confidence to keep a hypothesis.",
                        "default": 0.6,
                        "minimum": 0.0,
                        "maximum": 1.0
                    }
                },
                "required": ["analysis"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # 1) Normalize analysis
        analysis = arguments.get("analysis")
        if isinstance(analysis, str):
            try:
                analysis = json.loads(analysis)
            except Exception:
                return [TextContent(type="text", text="❌ 'analysis' must be a JSON object or a JSON string.")]

        if not isinstance(analysis, dict):
            return [TextContent(type="text", text="❌ 'analysis' must be a JSON object.")]

        mode = arguments.get("mode", "auto")
        confidence_floor = float(arguments.get("confidence_floor", 0.6))

        # Prepare the next step args
        next_step_args = {
            "analysis": analysis,  # Pass through the original analysis
            "root_cause": "{{RESULT_FROM_ANALYSIS}}",  # Placeholder for root cause results
            "title_prefix": "",
            "mode": "auto"
        }

        # Use Template.substitute() with $ placeholders for shared template
        next_tool = "automated_issue_creation"
        args_json = json.dumps(next_step_args)
        reason = "Create GitHub/JIRA issues directly from root cause analysis"

        # Format input data with mode and confidence_floor
        input_data = {
            "analysis": analysis,
            "mode": mode,
            "confidence_floor": confidence_floor
        }

        # Simple template substitution - no string manipulation needed!
        prompt_template = Template(self._get_prompt())
        full_prompt = prompt_template.substitute(
            INPUT_ANALYSIS=json.dumps(input_data, indent=2),
            nextTool=next_tool,
            argsJson=args_json,
            reason=reason
        )
        
        return [TextContent(type="text", text=full_prompt)]


# Global instance / exports
_root_cause_tool = RootCauseIdentificationPromptTool()

def get_root_cause_identification_prompt_tool() -> RootCauseIdentificationPromptTool:
    return _root_cause_tool

def get_tool_definition() -> Tool:
    return _root_cause_tool.get_tool_definition()

async def execute_root_cause_identification_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Expected args:
      {
        "analysis": { ... },                  # or a JSON string
        "mode": "auto|strict|exploratory",    # optional
        "confidence_floor": 0.0–1.0           # optional
      }
    Returns:
      - JSON (root cause results)
      - Plan to `ticket_split_prepare` with { analysis, root_cause }
    """
    return await _root_cause_tool.execute(arguments)
