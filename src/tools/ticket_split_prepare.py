"""Service-level ticket split tool (inputs: analysis + root_cause → outputs: ticket items list)."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List, Optional

import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class TicketSplitPrepareTool(BasePromptTool):
    """
    Step 10 — Prepare ticket-ready items:
      - One MAIN ticket per trace (storytelling + trace_id [+ services involved, optional window/impact]).
      - SUB tickets per service that has errors (service-scoped analysis + root-cause identification).

    Input:
      - analysis: JSON object (or JSON string) from analyze_traces_narrative.
      - root_cause: JSON object (or JSON string) from root_cause_identification_prompt.

    Output:
      - FINAL JSON: a list of ticket items (each item has type: "main" | "sub").
      - Plan to automated_issue_creation for creating actual issues from the ticket items.
    """

    def __init__(self):
        super().__init__(
            tool_name="ticket_split_prepare",
            description=(
                "Create ticket-ready items by combining cross-service analysis with per-service root causes. "
                "Emits a strict JSON list of items: one 'main' per trace (story + trace_id), and 'sub' per service with "
                "analysis and root-cause details. Then chains to automated issue creation."
            ),
            prompt_filename="ticket_split_prepare.txt",
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
                        "description": "Structured analysis from analyze_traces_narrative, or a JSON string.",
                        "oneOf": [{"type": "object"}, {"type": "string"}]
                    },
                    "root_cause": {
                        "description": "Structured root-cause output, or a JSON string.",
                        "oneOf": [{"type": "object"}, {"type": "string"}]
                    },
                    "title_prefix": {
                        "type": "string",
                        "description": "Optional prefix for generated ticket titles (e.g., team or incident tag).",
                        "default": ""
                    },
                    "mode": {
                        "type": "string",
                        "description": "auto | strict (affects how aggressively subs are created).",
                        "default": "auto",
                        "enum": ["auto", "strict"]
                    }
                },
                "required": ["analysis", "root_cause"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # Normalize inputs to dicts
        analysis = arguments.get("analysis")
        if isinstance(analysis, str):
            try:
                analysis = json.loads(analysis)
            except Exception:
                return [TextContent(type="text", text="❌ 'analysis' must be a JSON object or valid JSON string.")]
        if not isinstance(analysis, dict):
            return [TextContent(type="text", text="❌ 'analysis' must be a JSON object.")]

        root_cause = arguments.get("root_cause")
        if isinstance(root_cause, str):
            try:
                root_cause = json.loads(root_cause)
            except Exception:
                return [TextContent(type="text", text="❌ 'root_cause' must be a JSON object or valid JSON string.")]
        if not isinstance(root_cause, dict):
            return [TextContent(type="text", text="❌ 'root_cause' must be a JSON object.")]

        title_prefix = arguments.get("title_prefix", "")
        mode = arguments.get("mode", "auto")

        # Get the ticket split preparation prompt instructions (keep exactly as is)
        prompt_instructions = self._get_prompt()
        
        # Add instruction to analyze the inputData
        full_prompt = f"""{prompt_instructions}

Please analyze the inputData below and provide the ticket split preparation as specified above."""

        # Prepare the arguments for the prompt
        prompt_arguments = {
            "analysis": analysis,
            "root_cause": root_cause,
            "title_prefix": title_prefix,
            "mode": mode
        }

        # Prepare the next step args
        next_step_args = {
            "splunk_query": "index=main error",  # Default query, will be refined based on ticket content
            "platform": "auto",
            "earliest_time": "-24h",
            "latest_time": "now",
            "max_results": 100,
            "severity_threshold": "medium",
            "group_similar_errors": True
        }
        
        # Construct JSON response using enhanced shared plan template
        response_data = {
            "kind": "plan",
            "prompt": full_prompt,
            "inputData": prompt_arguments,
            "next": [
                {
                    "type": "tool",
                    "toolName": "automated_issue_creation",
                    "args": next_step_args,
                    "reason": "Automatically analyze ticket items and create GitHub or JIRA issues via external MCP servers"
                }
            ],
            "autoExecuteHint": True
        }
        response_json = json.dumps(response_data, indent=2)
        
        return [TextContent(type="text", text=response_json)]


# Global instance / exports
_tool = TicketSplitPrepareTool()

def get_tool_definition() -> Tool:
    return _tool.get_tool_definition()

async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _tool.execute(arguments)
