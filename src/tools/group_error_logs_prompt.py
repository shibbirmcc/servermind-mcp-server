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
    Input: raw log message strings from Step 4 under arguments["logs"] (array of strings).
    Behavior: prompts the model (via group_error_logs_prompt.txt) to:
      - detect trace/correlation IDs from the raw log content,
      - semantically cluster messages (normalize/mask variables, merge near-duplicates),
      - pick ONE representative id per cluster ("chosen_id"),
      - output strict JSON: [{ pattern, template, count, chosen_id, all_ids?, sample_events[] }, ...].
    Then: chains to extract_trace_ids_for_search to handle ID extraction and trace fetching.
    """

    def __init__(self):
        super().__init__(
            tool_name="group_error_logs",
            description=(
                "Group ERROR logs into semantic clusters and pick one representative trace/correlation ID per group. "
                "Takes an array of raw log message strings, semantically groups similar error messages, "
                "and selects one representative ID per group for trace fetching."
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
                        "description": "Array of raw log messages (strings) from splunk_error_search.",
                        "items": {"type": "string"}
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
            return [TextContent(type="text", text="❌ Expected 'logs' to be an array of raw log message strings.")]
        
        # Validate that all items are strings
        for i, log in enumerate(logs):
            if not isinstance(log, str):
                return [TextContent(type="text", text=f"❌ Expected all log entries to be strings. Item {i} is {type(log).__name__}.")]
        
        max_groups = int(arguments.get("max_groups", 10))

        # 2) Get the grouping prompt instructions (keep exactly as is)
        prompt_instructions = self._get_prompt()
        
        # 3) Add comprehensive workflow context and next-step emphasis
        full_prompt = f"""{prompt_instructions}

WORKFLOW CONTEXT: This is Step 5 in a debugging chain. Your output directly feeds into Step 6.
NEXT STEP: The chosen_id values from your groups will be used to fetch full traces via splunk_trace_search_by_ids.

Please analyze the inputData below and provide the grouped error logs as specified above.

CRITICAL WORKFLOW CONTINUATION REQUIREMENTS:
- You MUST extract trace/correlation IDs from the log events
- Every group MUST have a non-null chosen_id value
- The workflow CANNOT continue without valid chosen_id values
- After providing the JSON output, the system will automatically proceed to the NEXT STEP:
  * Tool: splunk_trace_search_by_ids  
  * Purpose: Fetch full trace details using the chosen_id values from your groups
  * This next step is ESSENTIAL for the debugging workflow to continue

MANDATORY SUCCESS CRITERIA:
- Find trace_id, span_id, or parent_span_id fields in the log events
- Use aggressive fallback strategies if primary fields are missing
- NEVER output groups with null chosen_id values
- The success of the entire debugging workflow depends on accurate chosen_id extraction

EXAMPLE LOG STRUCTURE (for reference):
{{
  "trace_id": "57bd79f420bd4ddd9718c8d94d7e2858",
  "span_id": "de0f343642384d19", 
  "parent_span_id": "584c79270145481b",
  "message": "Successfully connected to MySQL Server version 8.0.43",
  "service_name": "demo-service-user",
  "trace_context_found": true
}}"""

        # 4) Prepare the next step args for extract_trace_ids_for_search
        next_step_args = {
            "grouped_logs": "{{GROUPING_OUTPUT_JSON}}",  # Will be populated with the grouping result
            "deduplicate": True,
            "earliest_time": "-24h",
            "latest_time": "now",
            "max_results": 4000
        }
        
        # 5) Construct JSON response manually with enhanced emphasis
        response_data = {
            "kind": "plan",
            "prompt": full_prompt,
            "inputData": arguments,
            "next": [
                {
                    "type": "tool",
                    "toolName": "extract_trace_ids_for_search",
                    "args": next_step_args,
                    "reason": "🔄 NEXT STEP: Extract trace IDs from the grouped error patterns and prepare for trace fetching. This intermediate step ensures proper ID validation and deduplication before proceeding to trace search."
                }
            ],
            "autoExecuteHint": True,
            "workflowNote": "The grouped error patterns will be processed to extract trace IDs, which will then be used for detailed trace fetching.",
            "stepInfo": "Step 5 → Step 5.5: Error Grouping → ID Extraction"
        }
        response_json = json.dumps(response_data, indent=2)
        
        return [TextContent(type="text", text=response_json)]

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
