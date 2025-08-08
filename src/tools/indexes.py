"""Index management tool implementation for MCP."""

from typing import Dict, Any, List, Optional
import structlog
from mcp.types import Tool, TextContent
from ..splunk.client import SplunkClient, SplunkConnectionError
from ..config import get_config, Config

logger = structlog.get_logger(__name__)


class SplunkIndexesTool:
    """MCP tool for listing and managing Splunk indexes."""
    
    def __init__(self):
        """Initialize the indexes tool."""
        self.config: Optional[Config] = None
        self._client: Optional[SplunkClient] = None
    
    def _get_config(self):
        """Get configuration, loading it if necessary."""
        if self.config is None:
            self.config = get_config()
        return self.config
    
    def get_client(self) -> SplunkClient:
        """Get or create Splunk client instance."""
        if self._client is None:
            config = self._get_config()
            self._client = SplunkClient(config.splunk)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for splunk_indexes."""
        return Tool(
            name="splunk_indexes",
            description="List and get information about Splunk indexes",
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
        """Execute the splunk_indexes tool.
        
        Args:
            arguments: Tool arguments containing filter and sort options
            
        Returns:
            List[TextContent]: Index information and metadata
        """
        try:
            # Extract arguments
            filter_pattern = arguments.get("filter_pattern")
            include_disabled = arguments.get("include_disabled", True)
            sort_by = arguments.get("sort_by", "name")
            sort_order = arguments.get("sort_order", "asc")
            
            logger.info("Listing Splunk indexes", 
                       filter_pattern=filter_pattern,
                       include_disabled=include_disabled,
                       sort_by=sort_by,
                       sort_order=sort_order)
            
            # Get client and retrieve indexes
            client = self.get_client()
            indexes = client.get_indexes(filter_pattern=filter_pattern)
            
            # Filter disabled indexes if requested
            if not include_disabled:
                indexes = [idx for idx in indexes if not idx.get('disabled', False)]
            
            # Sort indexes
            indexes = self._sort_indexes(indexes, sort_by, sort_order)
            
            # Format results for MCP response
            return self._format_indexes_results(indexes, filter_pattern, sort_by, sort_order)
            
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
        """Sort indexes by specified field and order.
        
        Args:
            indexes: List of index dictionaries
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')
            
        Returns:
            List[Dict[str, Any]]: Sorted indexes
        """
        reverse = sort_order == "desc"
        
        def safe_int_key(x, field):
            """Safely convert field to int for sorting."""
            value = x.get(field, 0)
            try:
                if isinstance(value, str):
                    return int(value) if value.isdigit() else 0
                return int(value)
            except (ValueError, TypeError):
                return 0
        
        def safe_float_key(x, field):
            """Safely convert field to float for sorting."""
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
            # Default to name sorting
            return sorted(indexes, key=lambda x: str(x.get('name', '')), reverse=reverse)
    
    def _format_indexes_results(self, indexes: List[Dict[str, Any]], filter_pattern: Optional[str], 
                               sort_by: str, sort_order: str) -> List[TextContent]:
        """Format indexes results for MCP response.
        
        Args:
            indexes: List of index information
            filter_pattern: Applied filter pattern
            sort_by: Sort field used
            sort_order: Sort order used
            
        Returns:
            List[TextContent]: Formatted results
        """
        index_count = len(indexes)
        
        # Create summary
        summary = f"✅ **Splunk Indexes Retrieved**\n\n"
        summary += f"**Total Indexes:** {index_count}\n"
        
        if filter_pattern:
            summary += f"**Filter Applied:** `{filter_pattern}`\n"
        
        summary += f"**Sorted By:** {sort_by} ({sort_order})\n\n"
        
        if index_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No indexes found matching the specified criteria."
            )]
        
        # Format index details
        formatted_results = summary + "**Index Details:**\n\n"
        
        # Calculate totals (with type conversion)
        total_events = 0
        total_size_mb = 0.0
        
        for idx in indexes:
            # Convert event count to int
            try:
                events = idx.get('total_event_count', 0)
                if isinstance(events, str):
                    events = int(events) if events.isdigit() else 0
                total_events += events
            except (ValueError, TypeError):
                pass
            
            # Convert size to float
            try:
                size = idx.get('current_db_size_mb', 0)
                if isinstance(size, str):
                    size = float(size) if size.replace('.', '').isdigit() else 0.0
                total_size_mb += size
            except (ValueError, TypeError):
                pass
        
        # Add summary statistics
        formatted_results += f"**Summary Statistics:**\n"
        formatted_results += f"- Total Events: {total_events:,}\n"
        formatted_results += f"- Total Size: {total_size_mb:,.1f} MB ({total_size_mb/1024:.2f} GB)\n"
        formatted_results += f"- Active Indexes: {len([idx for idx in indexes if not idx.get('disabled', False)])}\n"
        formatted_results += f"- Disabled Indexes: {len([idx for idx in indexes if idx.get('disabled', False)])}\n\n"
        
        # Format individual indexes
        for i, index in enumerate(indexes[:20], 1):  # Show first 20 indexes in detail
            name = index.get('name', 'Unknown')
            
            # Convert events to int
            events = index.get('total_event_count', 0)
            try:
                if isinstance(events, str):
                    events = int(events) if events.isdigit() else 0
            except (ValueError, TypeError):
                events = 0
            
            # Convert size to float
            size_mb = index.get('current_db_size_mb', 0)
            try:
                if isinstance(size_mb, str):
                    size_mb = float(size_mb) if size_mb.replace('.', '').isdigit() else 0.0
            except (ValueError, TypeError):
                size_mb = 0.0
            
            earliest = index.get('earliest_time', 'N/A')
            latest = index.get('latest_time', 'N/A')
            disabled = index.get('disabled', False)
            max_size = index.get('max_data_size', 'auto')
            
            status = "🔴 Disabled" if disabled else "🟢 Active"
            
            formatted_results += f"**{i}. {name}** {status}\n"
            formatted_results += f"   - **Events:** {events:,}\n"
            formatted_results += f"   - **Size:** {size_mb:,.1f} MB\n"
            formatted_results += f"   - **Max Size:** {max_size}\n"
            formatted_results += f"   - **Time Range:** {earliest} to {latest}\n"
            formatted_results += "\n"
        
        # Add truncation notice if needed
        if index_count > 20:
            formatted_results += f"... and {index_count - 20} more indexes.\n\n"
        
        # Add usage suggestions
        formatted_results += self._generate_usage_suggestions(indexes)
        
        return [TextContent(type="text", text=formatted_results)]
    
    def _generate_usage_suggestions(self, indexes: List[Dict[str, Any]]) -> str:
        """Generate usage suggestions based on index information.
        
        Args:
            indexes: List of index information
            
        Returns:
            str: Usage suggestions
        """
        if not indexes:
            return ""
        
        suggestions = "**💡 Usage Suggestions:**\n\n"
        
        # Find largest indexes by events (with safe conversion)
        def safe_event_count(idx):
            """Safely get event count for sorting."""
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
        
        # Find indexes with recent data
        recent_indexes = [idx for idx in indexes if idx.get('latest_time') and 'N/A' not in str(idx.get('latest_time', ''))]
        if recent_indexes:
            recent_index = recent_indexes[0]['name']
            suggestions += f"- **Recent Data Analysis:** `index={recent_index} earliest=-1h | stats count by sourcetype`\n"
        
        # Suggest index comparison
        if len(indexes) > 1:
            index_names = [idx['name'] for idx in indexes[:3]]
            index_list = ' OR '.join([f'index={name}' for name in index_names])
            suggestions += f"- **Compare Indexes:** `({index_list}) | stats count by index`\n"
        
        # Suggest size analysis
        suggestions += f"- **Index Size Analysis:** Use the results above to identify large indexes for optimization\n"
        
        # Suggest disabled index review
        disabled_count = len([idx for idx in indexes if idx.get('disabled', False)])
        if disabled_count > 0:
            suggestions += f"- **Review Disabled Indexes:** {disabled_count} disabled indexes found - consider cleanup\n"
        
        suggestions += "\n"
        return suggestions
    
    def cleanup(self):
        """Clean up resources."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception as e:
                logger.warning("Error during client cleanup", error=str(e))
            finally:
                self._client = None


# Global indexes tool instance
_indexes_tool = SplunkIndexesTool()


def get_indexes_tool() -> SplunkIndexesTool:
    """Get the global indexes tool instance."""
    return _indexes_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for splunk_indexes."""
    return _indexes_tool.get_tool_definition()


async def execute_indexes(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the splunk_indexes tool."""
    return await _indexes_tool.execute(arguments)
