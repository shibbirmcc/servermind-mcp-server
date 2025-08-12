"""Fetch full cross-service logs for a list of trace/correlation IDs, then hand off to analysis."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List, Optional

import structlog
from mcp.types import Tool, TextContent

# Reuse the generic search tool
from ..tools.splunk_search import execute_search

logger = structlog.get_logger(__name__)


CANDIDATE_ID_FIELDS = [
    "traceId", "trace_id", "traceID",
    "correlationId", "correlation_id",
    "requestId", "request_id",
    "x-b3-traceid", "b3TraceId"
]

# Reasonable chunk size to keep SPL length manageable
ID_CHUNK_SIZE = 25


class SplunkTraceSearchByIdsTool:
    """
    Step 6 in the chain.
    Inputs: `ids` (list of trace/correlation IDs), optional `indices`, `earliest_time`, `latest_time`, `max_results`.
    Behavior:
      - Build SPL that fetches ALL logs for the given IDs across candidate ID fields (equality) with a fallback to _raw.
      - Execute via splunk_search (raw_return=True).
      - Bucket events by the ID value (best-effort field detection; fallback to _raw contains).
      - Emit machine-readable `{"traces":[{"id":..., "events":[...]}, ...]}` and a plan to the analysis step.
    """

    def __init__(self):
        self._plan_tpl_path = Path(__file__).parent.parent / "shared_plan_template.txt"
        self._plan_tpl = Template(self._plan_tpl_path.read_text(encoding="utf-8"))

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="splunk_trace_search_by_ids",
            description=(
                "Given a list of trace/correlation IDs, retrieve all related logs across indices and time range. "
                "Returns traces grouped per ID and chains to the analysis step."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Trace/correlation IDs to fetch."
                    },
                    "indices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional Splunk indices to restrict search (defaults to all)."
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time (e.g., '-24h', '-2d', ISO).",
                        "default": "-24h"
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time (e.g., 'now').",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max total events to return (per chunk).",
                        "default": 4000,
                        "minimum": 100,
                        "maximum": 20000
                    }
                },
                "required": ["ids"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            ids: List[str] = arguments.get("ids") or []
            if not ids or not all(isinstance(i, str) and i.strip() for i in ids):
                return [TextContent(type="text", text="❌ 'ids' must be a non-empty list of strings.")]

            indices: Optional[List[str]] = arguments.get("indices")
            earliest = arguments.get("earliest_time", "-24h")
            latest = arguments.get("latest_time", "now")
            max_results = int(arguments.get("max_results", 4000))

            # Build and run in chunks to avoid overly long SPL queries
            all_events: List[Dict[str, Any]] = []
            id_chunks = [ids[i:i + ID_CHUNK_SIZE] for i in range(0, len(ids), ID_CHUNK_SIZE)]

            for chunk in id_chunks:
                spl = self._build_trace_spl(chunk, indices)
                logger.info("Trace search chunk", ids=len(chunk), earliest=earliest, latest=latest)
                content_list = await execute_search({
                    "query": spl,
                    "earliest_time": earliest,
                    "latest_time": latest,
                    "max_results": max_results,
                    "raw_return": True
                })
                if not content_list:
                    continue
                payload = json.loads(content_list[0].text)
                events = payload.get("results", []) or []
                all_events.extend(events)

            # Group events by ID (using candidate fields; fallback to _raw contains)
            traces = self._group_events_by_ids(all_events, ids)

            # Machine-readable block
            data = {"kind": "data", "earliest_time": earliest, "latest_time": latest, "traces": traces}
            outputs: List[TextContent] = [TextContent(type="json", text=json.dumps(data, ensure_ascii=False))]

            if not traces or all(len(t.get("events", [])) == 0 for t in traces):
                # Nothing to analyze; inform upstream clearly.
                msg = (
                    "ℹ️ No matching logs were found for the provided IDs in the selected time range.\n"
                    f"- IDs: {', '.join(ids)}\n"
                    f"- Time range: {earliest} → {latest}\n"
                    f"- Indices: {', '.join(indices) if indices else '(all)'}\n"
                    "You can widen the time window or verify the IDs and indices."
                )
                outputs.append(TextContent(type="text", text=msg))
                return outputs

            # Plan to analysis step (Step 8) — adjust nextTool name if different
            plan_json = self._plan_tpl.substitute(
                nextTool="analyze_traces_narrative",
                argsJson=json.dumps({"traces": traces}, ensure_ascii=False),
                reason="Full logs collected per ID — proceed to cross-service narrative and root-cause analysis."
            )
            outputs.append(TextContent(type="text", text=plan_json))
            return outputs

        except Exception as e:
            logger.error("splunk_trace_search_by_ids failed", error=str(e))
            return [TextContent(type="text", text=f"❌ **Trace search failed**\n\n{e}")]

    # ---------------------------------------------------------------------

    def _build_trace_spl(self, ids: List[str], indices: Optional[List[str]]) -> str:
        """
        Build SPL to fetch events where ANY candidate id field matches ANY of the IDs.
        Adds a conservative fallback on _raw contains for each id.
        """
        # index filter
        if indices:
            index_clause = "(" + " OR ".join(f'index="{i}"' for i in indices) + ")"
        else:
            index_clause = "index=*"

        # field IN (...) for each candidate field
        quoted_ids = ",".join(f'"{i}"' for i in ids)
        field_in_clauses = [f'{f} IN ({quoted_ids})' for f in CANDIDATE_ID_FIELDS]

        # fallback _raw contains for each id (kept last to avoid noise)
        raw_contains = " OR ".join(f'like(_raw, "%{i}%")' for i in ids)

        predicate = "(" + " OR ".join(field_in_clauses + ([raw_contains] if raw_contains else [])) + ")"

        # final SPL; no head here — rely on max_results in API
        return f"search {index_clause} {predicate} | sort _time"

    def _group_events_by_ids(self, events: List[Dict[str, Any]], ids: List[str]) -> List[Dict[str, Any]]:
        """
        Group fetched events into traces per requested ID.
        - Prefer exact matches on candidate fields.
        - Fallback: assign by _raw contains when unique and unambiguous.
        - Keep event order by _time if present (otherwise as-is).
        """
        # map id -> events
        buckets: Dict[str, List[Dict[str, Any]]] = {i: [] for i in ids}

        # Fast path: exact field match to requested IDs
        for ev in events:
            assigned = False
            for f in CANDIDATE_ID_FIELDS:
                val = ev.get(f)
                if isinstance(val, str) and val in buckets:
                    buckets[val].append(ev)
                    assigned = True
                    break

            if assigned:
                continue

            # Fallback: _raw contains match (only if exactly one id matches to avoid ambiguity)
            raw = str(ev.get("_raw", ""))[:20000]
            matches = [i for i in ids if i and i in raw]
            if len(matches) == 1:
                buckets[matches[0]].append(ev)

        # Sort each bucket by _time if present
        def _time_key(e: Dict[str, Any]):
            t = e.get("_time")
            # Splunk often returns epoch or string; leave as-is for ordering robustness
            return str(t) if t is not None else ""

        traces: List[Dict[str, Any]] = []
        for i in ids:
            evs = buckets.get(i, [])
            evs_sorted = sorted(evs, key=_time_key)
            traces.append({"id": i, "events": evs_sorted})

        return traces


# Global instance + exports
_tool = SplunkTraceSearchByIdsTool()

def get_tool_definition() -> Tool:
    return _tool.get_tool_definition()

async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _tool.execute(arguments)
