# ... imports unchanged ...

class SplunkLogAnalysisPromptTool(BasePromptTool):
    # __init__ and get_tool_definition unchanged, except inputSchema widened:
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

        llm_outputs = await super().execute({"traces": traces, "mode": mode, "verbosity": verbosity})
        if not llm_outputs or not getattr(llm_outputs[0], "text", None):
            return [TextContent(type="text", text="❌ Analysis step produced no output.")]

        raw_text = llm_outputs[0].text
        try:
            parsed = json.loads(raw_text)
        except Exception:
            logger.warning("Analyzer returned non-JSON; passing through text.")
            return [TextContent(type="text", text=raw_text)]

        outputs: List[TextContent] = [TextContent(type="json", text=json.dumps(parsed, ensure_ascii=False))]

        plan_json = self._plan_tpl.substitute(
            nextTool="root_cause_identification_prompt",
            argsJson=json.dumps({"analysis": parsed}, ensure_ascii=False),
            reason="Use the narrated story and per-service breakdown to confirm root cause(s)."
        )
        outputs.append(TextContent(type="text", text=plan_json))
        return outputs

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
