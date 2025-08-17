from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List
import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class SplunkLogAnalysisPromptTool(BasePromptTool):
    def __init__(self):
        super().__init__(
            tool_name="analyze_traces_narrative",
            description="Analyze traces and generate narrative analysis with cross-service story and per-service breakdown",
            prompt_filename="analyze_traces_narrative.txt"
        )

    def get_tool_definition(self) -> Tool:
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "traces": {
                        "type": "array",
                        "description": "Preferred: [{ id: string, events: array<object> }].",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "events": {"type": "array", "items": {"type": "object"}}
                            },
                            "required": ["events"]
                        }
                    },
                    "events": {
                        "type": "array",
                        "description": "Fallback: a single trace's events array; will be wrapped into traces[0].",
                        "items": {"type": "object"}
                    },
                    "id": {
                        "type": "string",
                        "description": "Optional id for the single-trace 'events' fallback."
                    },
                    "kind": {
                        "type": "string",
                        "description": "If present and == 'data', may include 'traces' wrapper from previous step."
                    },
                    "mode": {
                        "type": "string",
                        "default": "auto",
                        "enum": ["auto", "simple", "full"]
                    },
                    "verbosity": {
                        "type": "string",
                        "default": "normal",
                        "enum": ["brief", "normal", "verbose"]
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        # Normalize inputs into traces = [{id, events}]
        traces = self._coerce_to_traces(arguments)
        if not traces:
            return [TextContent(type="text", text="❌ Expected traces or events. Provide either `traces` (array of {id, events}) or `events` (single trace).")]

        mode = arguments.get("mode", "auto")
        verbosity = arguments.get("verbosity", "normal")

        # Prepare the next step args
        next_step_args = {
            "analysis": "{{RESULT_FROM_ANALYSIS}}",  # Placeholder for analysis results
            "mode": "auto",
            "confidence_floor": 0.6
        }

        # Use Template.substitute() with $ placeholders for shared template
        next_tool = "root_cause_identification_prompt"
        args_json = json.dumps(next_step_args)
        reason = "Confirm service-level root causes based on narrative analysis and prepare for ticket creation"

        # Format input data with mode and verbosity
        input_data = {
            "traces": traces,
            "mode": mode,
            "verbosity": verbosity
        }

        # Simple template substitution - no string manipulation needed!
        prompt_template = Template(self._get_prompt())
        full_prompt = prompt_template.substitute(
            INPUT_TRACES=json.dumps(input_data, indent=2),
            nextTool=next_tool,
            argsJson=args_json,
            reason=reason
        )
        
        return [TextContent(type="text", text=full_prompt)]

    # --- helpers ---
    def _coerce_to_traces(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Preferred: direct traces
        traces = args.get("traces")
        if isinstance(traces, list) and traces:
            # Ensure each item has {events}; id optional
            normalized = []
            for t in traces:
                if isinstance(t, dict) and isinstance(t.get("events"), list):
                    normalized.append({"id": t.get("id") or "unknown", "events": t["events"]})
            if normalized:
                return normalized

        # Wrapper: kind=data with traces
        if args.get("kind") == "data" and isinstance(args.get("traces"), list):
            return self._coerce_to_traces({"traces": args["traces"]})

        # Single-trace fallback: events [+ id]
        events = args.get("events")
        if isinstance(events, list) and events:
            return [{"id": args.get("id") or "unknown", "events": events}]

        return []


# Global instance / exports
_analyze_traces_narrative_tool = SplunkLogAnalysisPromptTool()

def get_analyze_traces_narrative_tool() -> SplunkLogAnalysisPromptTool:
    return _analyze_traces_narrative_tool

def get_tool_definition() -> Tool:
    return _analyze_traces_narrative_tool.get_tool_definition()

async def execute_analyze_traces_narrative(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Expected args:
      {
        "traces": [{ id: string, events: array<object> }],  # preferred
        "events": array<object>,                            # fallback for single trace
        "id": string,                                       # optional id for single trace
        "kind": string,                                     # if "data", may include traces wrapper
        "mode": "auto|simple|full",                         # optional
        "verbosity": "brief|normal|verbose"                 # optional
      }
    Returns:
      - JSON (analysis results)
      - Plan to `root_cause_identification_prompt` with analysis
    """
    return await _analyze_traces_narrative_tool.execute(arguments)
