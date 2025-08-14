"""Index management tool implementation for MCP."""

from typing import Dict, Any, List, Optional
from pathlib import Path
import structlog
import json
from string import Template
from mcp.types import Tool, TextContent
from ..splunk.client import SplunkClient, SplunkConnectionError
from ..config import get_config, Config

logger = structlog.get_logger(__name__)

PLAN_TEMPLATE = Template(
    (Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt")
        .read_text(encoding="utf-8")
)


class SplunkIndexesTool:
    """
    MCP tool for listing and managing Splunk indexes.
    
    This is Step 2 in the log debug chain:
    - Use it after the entry gate (Step 1) confirms we’re in a deployed environment.
    - Lists all relevant Splunk indexes for further filtering/search.
    - Hands over to Step 4 to build the first ERROR-only Splunk query.
    """

    def __init__(self):
        self.config: Optional[Config] = None
        self._client: Optional[SplunkClient] = None

    def _get_config(self):
        if self.config is None:
            self.config = get_config()
        return self.config

    def get_client(self) -> SplunkClient:
        if self._client is None:
            config = self._get_config()
            self._client = SplunkClient(config.splunk)
        return self._client

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="splunk_indexes",
            description=(
                "List available indexes (for exploring data structure before searching). "
                "Step 2 in the log debug chain: lists Splunk indexes after environment check."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_pattern": {
                        "type": "string",
                        "description": "Optional pattern to filter index names (case-insensitive substring match)",
                        "default": None
                    },
                    "include_disabled": {
                        "type": "boolean",
                        "description": "Whether to include disabled indexes in the results",
                        "default": True
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort results by",
                        "enum": ["name", "size", "events", "earliest", "latest"],
                        "default": "name"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order",
                        "enum": ["asc", "desc"],
                        "default": "asc"
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            filter_pattern = arguments.get("filter_pattern")
            include_disabled = arguments.get("include_disabled", True)
            sort_by = arguments.get("sort_by", "name")
            sort_order = arguments.get("sort_order", "asc")

            logger.info("Listing Splunk indexes",
                        filter_pattern=filter_pattern,
                        include_disabled=include_disabled,
                        sort_by=sort_by,
                        sort_order=sort_order)

            client = self.get_client()
            indexes = client.get_indexes(filter_pattern=filter_pattern)

            if not include_disabled:
                indexes = [idx for idx in indexes if not idx.get('disabled', False)]

            indexes = self._sort_indexes(indexes, sort_by, sort_order)

            # Prepare list of index names for Step 4
            index_names = [idx.get("name") for idx in indexes if "name" in idx]

            # Plan payload to hand over to search tool
            plan_json = PLAN_TEMPLATE.substitute(
                nextTool="splunk_error_search",  # Jump directly to search tool
                argsJson=json.dumps({
                    "query": f"index={' OR index='.join(index_names)} | head 100",
                    "earliest_time": "-24h",
                    "latest_time": "now",
                    "max_results": 100
                }, ensure_ascii=False),
                reason="Indexes listed — proceed to search across all available indexes."
            )

            formatted_results = self._format_indexes_results(indexes, filter_pattern, sort_by, sort_order)
            formatted_results.append(TextContent(type="text", text=plan_json))
            return formatted_results

        except SplunkConnectionError as e:
            logger.error("Splunk connection error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Connection Error**\n\n"
                     f"Failed to connect to Splunk: {e}\n\n"
                     f"Please check your Splunk configuration and ensure the server is accessible."
            )]
        except Exception as e:
            logger.error("Unexpected error in indexes tool", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Unexpected Error**\n\n"
                     f"An unexpected error occurred: {e}\n\n"
                     f"Please try again or contact support if the issue persists."
            )]

    def _sort_indexes(self, indexes: List[Dict[str, Any]], sort_by: str, sort_order: str) -> List[Dict[str, Any]]:
        reverse = sort_order == "desc"

        def safe_int_key(x, field):
            value = x.get(field, 0)
            try:
                if isinstance(value, str):
                    return int(value) if value.isdigit() else 0
                return int(value)
            except (ValueError, TypeError):
                return 0

        def safe_float_key(x, field):
            value = x.get(field, 0)
            try:
                if isinstance(value, str):
                    return float(value) if value.replace('.', '').isdigit() else 0.0
                return float(value)
            except (ValueError, TypeError):
                return 0.0

        if sort_by == "name":
            return sorted(indexes, key=lambda x: str(x.get('name', '')), reverse=reverse)
        elif sort_by == "size":
            return sorted(indexes, key=lambda x: safe_float_key(x, 'current_db_size_mb'), reverse=reverse)
        elif sort_by == "events":
            return sorted(indexes, key=lambda x: safe_int_key(x, 'total_event_count'), reverse=reverse)
        elif sort_by == "earliest":
            return sorted(indexes, key=lambda x: str(x.get('earliest_time', '')), reverse=reverse)
        elif sort_by == "latest":
            return sorted(indexes, key=lambda x: str(x.get('latest_time', '')), reverse=reverse)
        else:
            return sorted(indexes, key=lambda x: str(x.get('name', '')), reverse=reverse)

    def _determine_index_status(self, index: Dict[str, Any]) -> tuple[str, str]:
        """Determine the actual status of an index based on multiple indicators.
        
        Returns:
            tuple: (status_emoji, status_description)
        """
        name = index.get('name', 'Unknown')
        events = 0
        try:
            events = index.get('total_event_count', 0)
            if isinstance(events, str):
                events = int(events) if events.isdigit() else 0
        except (ValueError, TypeError):
            events = 0
        
        earliest = index.get('earliest_time', 'N/A')
        latest = index.get('latest_time', 'N/A')
        disabled_flag = index.get('disabled', False)
        
        # Normalize None values to 'N/A' for consistent comparison
        if earliest is None:
            earliest = 'N/A'
        if latest is None:
            latest = 'N/A'
        
        # Determine status based on data presence and freshness, not just disabled flag
        if events > 0 and latest not in ['N/A', 'None', None]:
            # Index has data and time range - likely active
            return "🟢", "Active"
        elif events > 0:
            # Has historical data but no clear time range
            return "🟡", "Has Data"
        elif disabled_flag and events == 0:
            # Explicitly disabled and no data
            return "🔴", "Disabled"
        else:
            # No data but not explicitly disabled - might be new/unused
            return "⚪", "Empty"

    def _format_indexes_results(self, indexes: List[Dict[str, Any]], filter_pattern: Optional[str],
                                sort_by: str, sort_order: str) -> List[TextContent]:
        index_count = len(indexes)
        summary = f"✅ **Splunk Indexes Retrieved**\n\n**Total Indexes:** {index_count}\n"
        if filter_pattern:
            summary += f"**Filter Applied:** `{filter_pattern}`\n"
        summary += f"**Sorted By:** {sort_by} ({sort_order})\n\n"

        if index_count == 0:
            return [TextContent(type="text", text=summary + "No indexes found matching the specified criteria.")]

        formatted_results = summary + "**Index Details:**\n\n"

        total_events = 0
        total_size_mb = 0.0
        status_counts = {"Active": 0, "Has Data": 0, "Disabled": 0, "Empty": 0}
        
        for idx in indexes:
            try:
                events = idx.get('total_event_count', 0)
                if isinstance(events, str):
                    events = int(events) if events.isdigit() else 0
                total_events += events
            except (ValueError, TypeError):
                pass

            try:
                size = idx.get('current_db_size_mb', 0)
                if isinstance(size, str):
                    size = float(size) if size.replace('.', '').isdigit() else 0.0
                total_size_mb += size
            except (ValueError, TypeError):
                pass
            
            # Count status types
            _, status_desc = self._determine_index_status(idx)
            status_counts[status_desc] = status_counts.get(status_desc, 0) + 1

        formatted_results += f"**Summary Statistics:**\n"
        formatted_results += f"- Total Events: {total_events:,}\n"
        formatted_results += f"- Total Size: {total_size_mb:,.1f} MB ({total_size_mb/1024:.2f} GB)\n"
        formatted_results += f"- Active Indexes: {status_counts['Active']}\n"
        formatted_results += f"- Indexes with Data: {status_counts['Has Data']}\n"
        formatted_results += f"- Empty Indexes: {status_counts['Empty']}\n"
        formatted_results += f"- Disabled Indexes: {status_counts['Disabled']}\n\n"

        for i, index in enumerate(indexes[:20], 1):
            name = index.get('name', 'Unknown')
            try:
                events = index.get('total_event_count', 0)
                if isinstance(events, str):
                    events = int(events) if events.isdigit() else 0
            except (ValueError, TypeError):
                events = 0

            try:
                size_mb = index.get('current_db_size_mb', 0)
                if isinstance(size_mb, str):
                    size_mb = float(size_mb) if size_mb.replace('.', '').isdigit() else 0.0
            except (ValueError, TypeError):
                size_mb = 0.0

            earliest = index.get('earliest_time', 'N/A')
            latest = index.get('latest_time', 'N/A')
            max_size = index.get('max_data_size', 'auto')
            
            # Use improved status determination
            status_emoji, status_desc = self._determine_index_status(index)
            status = f"{status_emoji} {status_desc}"

            formatted_results += f"**{i}. {name}** {status}\n"
            formatted_results += f"   - **Events:** {events:,}\n"
            formatted_results += f"   - **Size:** {size_mb:,.1f} MB\n"
            formatted_results += f"   - **Max Size:** {max_size}\n"
            formatted_results += f"   - **Time Range:** {earliest} to {latest}\n\n"

        if index_count > 20:
            formatted_results += f"... and {index_count - 20} more indexes.\n\n"

        formatted_results += self._generate_usage_suggestions(indexes)
        return [TextContent(type="text", text=formatted_results)]

    def _generate_usage_suggestions(self, indexes: List[Dict[str, Any]]) -> str:
        if not indexes:
            return ""
        suggestions = "**💡 Usage Suggestions:**\n\n"

        def safe_event_count(idx):
            events = idx.get('total_event_count', 0)
            try:
                if isinstance(events, str):
                    return int(events) if events.isdigit() else 0
                return int(events)
            except (ValueError, TypeError):
                return 0

        largest_by_events = sorted(indexes, key=safe_event_count, reverse=True)[:3]
        if largest_by_events and safe_event_count(largest_by_events[0]) > 0:
            top_index = largest_by_events[0]['name']
            suggestions += f"- **Search Popular Index:** `index={top_index} | head 10`\n"

        recent_indexes = [idx for idx in indexes if idx.get('latest_time') and 'N/A' not in str(idx.get('latest_time', ''))]
        if recent_indexes:
            recent_index = recent_indexes[0]['name']
            suggestions += f"- **Recent Data Analysis:** `index={recent_index} earliest=-1h | stats count by sourcetype`\n"

        if len(indexes) > 1:
            index_names = [idx['name'] for idx in indexes[:3]]
            index_list = ' OR '.join([f'index={name}' for name in index_names])
            suggestions += f"- **Compare Indexes:** `({index_list}) | stats count by index`\n"

        suggestions += f"- **Index Size Analysis:** Use the results above to identify large indexes for optimization\n"

        disabled_count = len([idx for idx in indexes if idx.get('disabled', False)])
        if disabled_count > 0:
            suggestions += f"- **Review Disabled Indexes:** {disabled_count} disabled indexes found - consider cleanup\n"

        suggestions += "\n"
        return suggestions

    def cleanup(self):
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception as e:
                logger.warning("Error during client cleanup", error=str(e))
            finally:
                self._client = None


_indexes_tool = SplunkIndexesTool()


def get_indexes_tool() -> SplunkIndexesTool:
    return _indexes_tool

def get_tool_definition() -> Tool:
    return _indexes_tool.get_tool_definition()


async def execute_indexes(arguments: Dict[str, Any]) -> List[TextContent]:
    return await _indexes_tool.execute(arguments)
