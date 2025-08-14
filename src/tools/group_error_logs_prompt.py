"""Group ERROR logs into semantic clusters and pick one representative trace/correlation ID per group."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List, Optional

import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class GroupErrorLogsTool(BasePromptTool):
    """
    Step 5 in the chain.
    Input: raw Splunk events from Step 4 under arguments["logs"] (a JSON array).
    Behavior: prompts the model (via group_error_logs_prompt.txt) to:
      - detect the best trace/correlation ID field (name- or pattern-based),
      - semantically cluster messages (normalize/mask variables, merge near-duplicates),
      - pick ONE representative id per cluster ("chosen_id"),
      - output strict JSON: [{ pattern, template, count, chosen_id, all_ids?, sample_events[] }, ...].
    Then: this tool extracts the list of chosen IDs and plans the next step to fetch full traces.
    """

    def __init__(self):
        super().__init__(
            tool_name="group_error_logs",
            description=(
                "Given raw Splunk ERROR events (as JSON array under 'logs'), detect a trace/correlation ID field, "
                "semantically group similar error messages, and select one representative ID per group. "
                "Outputs the groups and a plan to the next step to fetch full traces by those IDs."
            ),
            prompt_filename="group_error_logs_prompt.txt",
        )
        # Shared plan template for chaining
        self._plan_template_path = Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt"
        self._plan_template = Template(self._plan_template_path.read_text(encoding="utf-8"))

    def get_tool_definition(self) -> Tool:
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "logs": {
                        "type": "array",
                        "description": "Raw Splunk events (array of objects) from splunk_error_search.",
                        "items": {"type": "object"}
                    },
                    "max_groups": {
                        "type": "integer",
                        "description": "Soft cap for number of groups to aim for (model-level guidance).",
                        "default": 10
                    }
                },
                "required": ["logs"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # 1) basic input checks
        logs = arguments.get("logs")
        if not isinstance(logs, list):
            return [TextContent(type="text", text="❌ Expected 'logs' to be a JSON array of events.")]
        max_groups = int(arguments.get("max_groups", 10))

        # 2) hand the payload to the prompt LLM (BasePromptTool will read prompt file)
        #    We pass the logs and hints as arguments so the prompt can see them.
        #    BasePromptTool returns a list[TextContent]; first item should contain JSON (or a warning + JSON).
        llm_outputs = await super().execute({"logs": logs, "max_groups": max_groups})
        if not llm_outputs:
            return [TextContent(type="text", text="❌ Grouping step produced no output.")]

        raw_text = llm_outputs[0].text if hasattr(llm_outputs[0], "text") else ""
        if not raw_text:
            return [TextContent(type="text", text="❌ Grouping step returned empty content.")]

        # 3) try to extract strict JSON array from the model output
        groups, warning_prefix = self._extract_groups_json(raw_text)

        # If the model signaled "no suitable ID", just pass that through and stop.
        if groups is None and "No suitable trace/correlation ID found" in raw_text:
            return [TextContent(type="text", text=raw_text)]

        if groups is None:
            # Could not parse JSON—return the raw text to help debugging.
            logger.warning("Failed to parse grouping JSON; returning raw text.")
            return [TextContent(type="text", text=raw_text)]

        # 4) collect chosen IDs for the next step
        chosen_ids = [g.get("chosen_id") for g in groups if g.get("chosen_id")]
        chosen_ids = list(dict.fromkeys(chosen_ids))  # de-dupe, preserve order

        # If no IDs, we can still return the groups, but we cannot proceed to trace fan-out.
        outputs: List[TextContent] = []
        # include any warning line before JSON
        if warning_prefix:
            outputs.append(TextContent(type="text", text=warning_prefix))
        outputs.append(TextContent(type="json", text=json.dumps(groups, ensure_ascii=False)))

        if not chosen_ids:
            outputs.append(TextContent(
                type="text",
                text="ℹ️ Grouping completed, but no trace/correlation IDs were available to proceed. "
                     "You may widen the time range or adjust indices and retry."
            ))
            return outputs

        # 5) plan next step: fetch full logs for each chosen id (fan-out by ID list)
        #    Adjust 'nextTool' to your actual tool name for Step 6/7.
        plan_json = self._plan_template.substitute(
            nextTool="splunk_trace_search_by_ids",
            argsJson=json.dumps({"ids": chosen_ids}, ensure_ascii=False),
            reason="Select one representative ID per group and fetch full cross-service logs for each."
        )
        outputs.append(TextContent(type="text", text=plan_json))
        return outputs

    # --- helpers --------------------------------------------------------------

    def _extract_groups_json(self, text: str) -> tuple[Optional[List[Dict[str, Any]]], str]:
        """
        Extracts the JSON array of groups from the LLM output.
        - Allows an optional single warning line before the JSON (per prompt rules).
        - Returns (groups, warning_prefix). If parsing fails, (None, "").
        """
        stripped = text.lstrip()
        warning_prefix = ""
        # If there is a leading warning line (starts with "⚠️" or plain text), keep it but strip before JSON.
        if stripped.startswith("⚠️"):
            # take first line as warning, keep it as-is
            first_newline = stripped.find("\n")
            if first_newline != -1:
                warning_prefix = stripped[:first_newline].strip()
                stripped = stripped[first_newline:].lstrip()
            else:
                # Warning only, no JSON
                return None, warning_prefix

        # Find the first '[' and last ']' to get the JSON array
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start == -1 or end == -1 or end < start:
            return None, warning_prefix

        json_blob = stripped[start:end + 1]
        try:
            data = json.loads(json_blob)
            if isinstance(data, list):
                return data, (warning_prefix + "\n" if warning_prefix else "")
            return None, warning_prefix
        except Exception:
            return None, warning_prefix


# Global instance + exports
_group_tool = GroupErrorLogsTool()


def get_tool_definition() -> Tool:
    return _group_tool.get_tool_definition()


async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _group_tool.execute(arguments)
