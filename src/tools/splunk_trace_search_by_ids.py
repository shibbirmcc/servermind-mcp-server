"""Fetch full cross-service logs for a list of trace/correlation IDs, then hand off to analysis."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, Any, List, Optional

import structlog
from mcp.types import Tool, TextContent

# Reuse the generic search tool
from .search import execute_splunk_query_raw_only

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
    Inputs: `field_name` (type of ID field) and `ids` (list of trace/correlation IDs).
    Behavior:
      - Build SPL that fetches ALL logs for the given IDs across candidate ID fields (equality) with a fallback to _raw.
      - Execute via splunk_search (raw_return=True) with auto-broadening time ranges (24h → 48h → 72h until results found).
      - Uses default settings: all indices, 4000 max results per chunk.
      - Bucket events by the ID value (best-effort field detection; fallback to _raw contains).
      - Emit machine-readable `{"traces":[{"id":..., "events":[...]}, ...]}` and a plan to the analysis step.
    """

    def __init__(self):
        self._plan_tpl_path = Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt"
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
                    "field_name": {
                        "type": "string",
                        "description": "The type of ID field found (e.g., 'trace_id', 'correlation_id', 'request_id')."
                    },
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Trace/correlation IDs to fetch."
                    }
                },
                "required": ["field_name", "ids"]
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            ids: List[str] = arguments.get("ids") or []
            if not ids or not all(isinstance(i, str) and i.strip() for i in ids):
                return [TextContent(type="text", text="❌ 'ids' must be a non-empty list of strings.")]

            field_name = arguments.get("field_name", "unknown")
            # Use default values for simplified interface
            indices: Optional[List[str]] = None  # Search all indices
            latest = "now"     # Search up to now
            max_results = 4000 # Default result limit

            logger.info("Starting trace search with auto-broadening", 
                       field_name=field_name, 
                       id_count=len(ids))

            # Auto-broaden search time range: 24h → 48h → 72h
            time_ranges = ["-24h", "-48h", "-72h"]
            all_raw_logs: List[str] = []
            used_range = None

            for time_range in time_ranges:
                logger.info("Trying time range", time_range=time_range)
                
                # Build and run in chunks to avoid overly long SPL queries
                range_raw_logs: List[str] = []
                id_chunks = [ids[i:i + ID_CHUNK_SIZE] for i in range(0, len(ids), ID_CHUNK_SIZE)]

                for chunk in id_chunks:
                    spl = self._build_trace_spl(chunk, indices)
                    logger.info("Trace search chunk", ids=len(chunk), time_range=time_range)
                    raw_logs = await execute_splunk_query_raw_only(
                        query=spl,
                        earliest_time=time_range,
                        latest_time=latest,
                        max_results=max_results
                    )
                    range_raw_logs.extend(raw_logs)

                # Check if we found any logs in this time range
                if range_raw_logs:
                    all_raw_logs = range_raw_logs
                    used_range = time_range
                    logger.info("Found traces in time range", time_range=time_range, log_count=len(all_raw_logs))
                    break
                else:
                    logger.info("No traces found in time range", time_range=time_range)

            # Group raw logs by ID (using _raw contains matching)
            traces = self._group_raw_logs_by_ids(all_raw_logs, ids)
            earliest = used_range or "-72h"  # Use the successful range or max range for reporting

            # Always proceed to analysis step, even with empty traces
            if not traces or all(len(t.get("events", [])) == 0 for t in traces):
                logger.info("No detailed trace data found, proceeding with empty traces to analysis")
                # Create empty traces structure for the requested IDs
                traces = [{"id": trace_id, "events": []} for trace_id in ids]
                reason = (
                    f"ℹ️ No detailed trace logs found for IDs: {', '.join(ids)} in time range {earliest} → {latest}. "
                    "Proceeding with analysis using original error logs from previous steps."
                )
            else:
                reason = "Full logs collected per ID — proceed to cross-service narrative and root-cause analysis."

            # Plan to analysis step (Step 8) — adjust nextTool name if different
            plan_json = self._plan_tpl.substitute(
                nextTool="analyze_traces_narrative",
                argsJson=json.dumps({"traces": traces}, ensure_ascii=False),
                reason=reason
            )
            return [TextContent(type="text", text=plan_json)]

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

    def _group_raw_logs_by_ids(self, raw_logs: List[str], ids: List[str]) -> List[Dict[str, Any]]:
        """
        Group raw log strings into traces per requested ID and parse JSON events.
        Uses _raw contains matching since we only have the raw log strings.
        """
        # map id -> parsed events
        buckets: Dict[str, List[Dict[str, Any]]] = {i: [] for i in ids}

        # Match raw logs to IDs by string contains
        for raw_log in raw_logs:
            if not raw_log:
                continue
                
            # Find which IDs are mentioned in this log (only assign if exactly one match to avoid ambiguity)
            matches = [i for i in ids if i and i in raw_log]
            if len(matches) == 1:
                # Parse JSON if possible, otherwise create a structured event
                parsed_event = self._parse_log_event(raw_log)
                buckets[matches[0]].append(parsed_event)

        # Convert to expected format with parsed events
        traces: List[Dict[str, Any]] = []
        for i in ids:
            events_for_id = buckets.get(i, [])
            traces.append({"id": i, "events": events_for_id})

        return traces

    def _parse_log_event(self, raw_log: str) -> Dict[str, Any]:
        """
        Parse a raw log string into a structured event object.
        Attempts JSON parsing first, falls back to structured plain text parsing.
        """
        try:
            # Try to parse as JSON
            parsed = json.loads(raw_log)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fallback: create structured event from plain text log
        return {
            "raw": raw_log,
            "message": raw_log,
            "parsed": False,
            "format": "plain_text"
        }


# Global instance + exports
_tool = SplunkTraceSearchByIdsTool()

def get_tool_definition() -> Tool:
    return _tool.get_tool_definition()

def get_splunk_trace_search_by_ids_tool() -> SplunkTraceSearchByIdsTool:
    """Get the global splunk trace search by ids tool instance."""
    return _tool

async def execute(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _tool.execute(arguments)
