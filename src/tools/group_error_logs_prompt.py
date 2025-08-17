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
    Input: log objects from Step 4 under arguments["logs"] (array of dict objects).
    Behavior: prompts the model (via group_error_logs_prompt.txt) to:
      - semantically group similar error messages by fuzzy matching
      - extract one representative trace ID per group
      - output simple JSON array of trace IDs: ["trace_id_1", "trace_id_2", ...]
    Then: chains directly to splunk_trace_search_by_ids to fetch full trace details.
    """

    def __init__(self):
        super().__init__(
            tool_name="group_error_logs",
            description=(
                "Group ERROR logs into semantic clusters and pick one representative trace/correlation ID per group. "
                "Takes an array of log objects (dict format), semantically groups similar error messages, "
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
                        "description": "Array of log objects from splunk_error_search.",
                        "items": {
                            "type": "object",
                            "additionalProperties": True
                        }
                    },
                    "max_groups": {
                        "type": "integer",
                        "description": "Soft cap for number of groups to aim for (model-level guidance)",
                        "default": 10
                    }
                },
                "required": ["logs"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # 1) basic input checks
        logs = arguments.get("logs")
        max_groups = arguments.get("max_groups", 10)
        
        if not isinstance(logs, list):
            return [TextContent(type="text", text="❌ Expected 'logs' to be an array of log objects.")]
        
        # Validate that all items are dict objects
        for i, log in enumerate(logs):
            if not isinstance(log, dict):
                return [TextContent(type="text", text=f"❌ Expected all log entries to be dict objects. Item {i} is {type(log).__name__}.")]
        
        # Prepare next step args
        next_step_args = {"field_name": "trace_id", "ids": ["<EXTRACTED_IDS>"]}
        
        # Use Template.substitute() with $ placeholders for shared template
        next_tool = "splunk_trace_search_by_ids"
        args_json = json.dumps(next_step_args)
        reason = "Search for detailed trace events using the extracted trace IDs to build comprehensive timeline"

        # Simple template substitution - no string manipulation needed!
        prompt_template = Template(self._get_prompt())
        
        # Generate the workflow template with substituted variables
        workflow_template = self._plan_template.substitute(
            nextTool=next_tool,
            argsJson=args_json,
            reason=reason
        )
        
        full_prompt = prompt_template.substitute(
            INPUT_LOGS=json.dumps(logs, indent=2),
            MAX_GROUPS=max_groups,
            WORKFLOW_TEMPLATE=workflow_template
        )
        
        logger.info("Executing group error logs prompt", log_count=len(logs))
        
        return [TextContent(type="text", text=full_prompt)]



# Global instance + exports
_group_tool = GroupErrorLogsTool()


def get_tool_definition() -> Tool:
    return _group_tool.get_tool_definition()


async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _group_tool.execute(arguments)
