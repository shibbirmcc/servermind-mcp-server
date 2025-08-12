"""Service-level ticket split tool (inputs: analysis + root_cause → outputs: ticket items list)."""

from __future__ import annotations

import json
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
      - FINAL JSON ONLY: a list of ticket items (each item has type: "main" | "sub").
      - No follow-on plan from this tool.
    """

    def __init__(self):
        super().__init__(
            tool_name="ticket_split_prepare",
            description=(
                "Create ticket-ready items by combining cross-service analysis with per-service root causes. "
                "Emits a strict JSON list of items: one 'main' per trace (story + trace_id), and 'sub' per service with "
                "analysis and root-cause details."
            ),
            prompt_filename="ticket_split_prepare.txt",
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

        # Call LLM with normalized inputs
        llm_outputs = await super().execute({
            "analysis": analysis,
            "root_cause": root_cause,
            "title_prefix": title_prefix,
            "mode": mode
        })
        if not llm_outputs or not getattr(llm_outputs[0], "text", None):
            return [TextContent(type="text", text="❌ Ticket split step produced no output.")]

        raw = llm_outputs[0].text

        # Strict parse & shape validation: must be a LIST of ticket items
        try:
            parsed = json.loads(raw)
        except Exception:
            logger.warning("ticket_split_prepare returned non-JSON.")
            return [TextContent(type="text", text="❌ Expected FINAL JSON list, but received non-JSON output.")]

        # Validate top-level list
        if not isinstance(parsed, list):
            return [TextContent(type="text", text="❌ Expected a JSON array of ticket items as the top-level value.")]

        # Validate each item has minimal required fields based on type
        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                return [TextContent(type="text", text=f"❌ Item {i} is not an object.")]
            typ = item.get("type")
            if typ not in ("main", "sub"):
                return [TextContent(type="text", text=f"❌ Item {i} missing or invalid 'type' ('main'|'sub').")]
            if typ == "main":
                if "trace_id" not in item or "story" not in item:
                    return [TextContent(type="text", text=f"❌ Main item {i} must include 'trace_id' and 'story'.")]
                if not isinstance(item["story"], list):
                    return [TextContent(type="text", text=f"❌ Main item {i} 'story' must be an array of bullets.")]
            if typ == "sub":
                if "service" not in item or "root_cause" not in item or "analysis" not in item:
                    return [TextContent(type="text", text=f"❌ Sub item {i} must include 'service', 'analysis', and 'root_cause'.")]

        # Everything looks good — emit machine-readable JSON
        return [TextContent(type="json", text=json.dumps(parsed, ensure_ascii=False))]


# Global instance / exports
_tool = TicketSplitPrepareTool()

def get_tool_definition() -> Tool:
    return _tool.get_tool_definition()

async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _tool.execute(arguments)
