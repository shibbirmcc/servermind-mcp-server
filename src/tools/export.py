"""Export functionality tool implementation for MCP."""

from typing import Dict, Any, List, Optional
import structlog
import json
import csv
import io
from mcp.types import Tool, TextContent
from ..splunk.client import SplunkClient, SplunkSearchError, SplunkConnectionError
from ..config import get_config

logger = structlog.get_logger(__name__)


class SplunkExportTool:
    """MCP tool for exporting Splunk search results."""
    
    def __init__(self):
        """Initialize the export tool."""
        self.config = get_config()
        self._client: Optional[SplunkClient] = None
    
    def get_client(self) -> SplunkClient:
        """Get or create Splunk client instance."""
        if self._client is None:
            self._client = SplunkClient(self.config.splunk)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for splunk_export."""
        return Tool(
            name="splunk_export",
            description="Export Splunk search results to various formats (JSON, CSV, XML)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SPL search query to execute and export results"
                    },
                    "format": {
                        "type": "string",
                        "description": "Export format",
                        "enum": ["json", "csv", "xml"],
                        "default": "json"
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time for search (e.g., '-24h', '-1d', '2023-01-01T00:00:00')",
                        "default": "-24h"
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time for search (e.g., 'now', '2023-01-02T00:00:00')",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to export",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": 50000
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Search timeout in seconds",
                        "default": 300,
                        "minimum": 10,
                        "maximum": 3600
                    },
                    "fields": {
                        "type": "array",
                        "description": "Specific fields to include in export (optional, exports all fields if not specified)",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": ["query"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the splunk_export tool.
        
        Args:
            arguments: Tool arguments containing query and export parameters
            
        Returns:
            List[TextContent]: Export results and metadata
        """
        try:
            # Extract arguments
            query = arguments.get("query")
            if not query:
                raise ValueError("Query parameter is required")
            
            export_format = arguments.get("format", "json").lower()
            earliest_time = arguments.get("earliest_time", "-24h")
            latest_time = arguments.get("latest_time", "now")
            max_results = arguments.get("max_results", 1000)
            timeout = arguments.get("timeout", self.config.mcp.search_timeout)
            fields = arguments.get("fields")
            
            # Validate format
            if export_format not in ["json", "csv", "xml"]:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            logger.info("Executing Splunk export", 
                       query=query, 
                       format=export_format,
                       earliest_time=earliest_time,
                       latest_time=latest_time,
                       max_results=max_results,
                       fields=fields)
            
            # Get client and execute search
            client = self.get_client()
            
            search_kwargs = {
                'earliest_time': earliest_time,
                'latest_time': latest_time,
                'max_results': max_results,
                'timeout': timeout
            }
            
            results = client.execute_search(query, **search_kwargs)
            
            # Limit results to max_results (Splunk may return more than requested)
            if len(results) > max_results:
                results = results[:max_results]
            
            # Filter fields if specified
            if fields:
                filtered_results = []
                for result in results:
                    filtered_result = {field: result.get(field, '') for field in fields}
                    filtered_results.append(filtered_result)
                results = filtered_results
            
            # Export results in requested format
            exported_data = self._export_results(results, export_format)
            
            # Format response for MCP
            return self._format_export_response(query, results, export_format, exported_data, search_kwargs)
            
        except SplunkConnectionError as e:
            logger.error("Splunk connection error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Connection Error**\n\n"
                     f"Failed to connect to Splunk: {e}\n\n"
                     f"Please check your Splunk configuration and ensure the server is accessible."
            )]
        
        except SplunkSearchError as e:
            logger.error("Splunk search error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Splunk Search Error**\n\n"
                     f"Search execution failed: {e}\n\n"
                     f"Please check your SPL query syntax and try again."
            )]
        
        except ValueError as e:
            logger.error("Invalid arguments", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Invalid Arguments**\n\n"
                     f"Error: {e}\n\n"
                     f"Please provide valid export parameters."
            )]
        
        except Exception as e:
            logger.error("Unexpected error in export tool", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Unexpected Error**\n\n"
                     f"An unexpected error occurred: {e}\n\n"
                     f"Please try again or contact support if the issue persists."
            )]
    
    def _export_results(self, results: List[Dict[str, Any]], export_format: str) -> str:
        """Export results to specified format.
        
        Args:
            results: Search results from Splunk
            export_format: Export format (json, csv, xml)
            
        Returns:
            str: Exported data as string
        """
        if export_format == "json":
            return self._export_to_json(results)
        elif export_format == "csv":
            return self._export_to_csv(results)
        elif export_format == "xml":
            return self._export_to_xml(results)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
    
    def _export_to_json(self, results: List[Dict[str, Any]]) -> str:
        """Export results to JSON format.
        
        Args:
            results: Search results
            
        Returns:
            str: JSON formatted data
        """
        return json.dumps(results, indent=2, default=str)
    
    def _export_to_csv(self, results: List[Dict[str, Any]]) -> str:
        """Export results to CSV format.
        
        Args:
            results: Search results
            
        Returns:
            str: CSV formatted data
        """
        if not results:
            return ""
        
        # Get all unique field names
        fieldnames = set()
        for result in results:
            fieldnames.update(result.keys())
        
        # Sort fieldnames for consistent output, with common fields first
        common_fields = ['_time', '_raw', 'host', 'source', 'sourcetype', 'index']
        sorted_fieldnames = []
        
        # Add common fields first if they exist
        for field in common_fields:
            if field in fieldnames:
                sorted_fieldnames.append(field)
                fieldnames.remove(field)
        
        # Add remaining fields alphabetically
        sorted_fieldnames.extend(sorted(fieldnames))
        
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=sorted_fieldnames, extrasaction='ignore')
        
        writer.writeheader()
        for result in results:
            # Convert all values to strings and handle None values
            row = {field: str(result.get(field, '')) if result.get(field) is not None else '' 
                   for field in sorted_fieldnames}
            writer.writerow(row)
        
        return output.getvalue()
    
    def _export_to_xml(self, results: List[Dict[str, Any]]) -> str:
        """Export results to XML format.
        
        Args:
            results: Search results
            
        Returns:
            str: XML formatted data
        """
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<results>']
        
        for i, result in enumerate(results):
            xml_lines.append(f'  <result offset="{i}">')
            
            for field, value in result.items():
                # Escape XML special characters
                escaped_field = self._escape_xml(str(field))
                escaped_value = self._escape_xml(str(value)) if value is not None else ''
                xml_lines.append(f'    <field k="{escaped_field}"><value><text>{escaped_value}</text></value></field>')
            
            xml_lines.append('  </result>')
        
        xml_lines.append('</results>')
        return '\n'.join(xml_lines)
    
    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters.
        
        Args:
            text: Text to escape
            
        Returns:
            str: Escaped text
        """
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))
    
    def _format_export_response(self, query: str, results: List[Dict[str, Any]], 
                               export_format: str, exported_data: str,
                               search_kwargs: Dict[str, Any]) -> List[TextContent]:
        """Format export response for MCP.
        
        Args:
            query: Original search query
            results: Search results
            export_format: Export format used
            exported_data: Exported data string
            search_kwargs: Search parameters used
            
        Returns:
            List[TextContent]: Formatted response
        """
        result_count = len(results)
        data_size = len(exported_data.encode('utf-8'))
        
        # Create summary
        summary = (
            f"✅ **Splunk Export Completed**\n\n"
            f"**Query:** `{query}`\n"
            f"**Format:** {export_format.upper()}\n"
            f"**Time Range:** {search_kwargs['earliest_time']} to {search_kwargs['latest_time']}\n"
            f"**Results Exported:** {result_count:,} events\n"
            f"**Data Size:** {data_size:,} bytes ({data_size/1024:.1f} KB)\n"
            f"**Max Results:** {search_kwargs['max_results']:,}\n\n"
        )
        
        if result_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No results found for the specified search criteria."
            )]
        
        # Add export preview (first few lines for large exports)
        preview_lines = exported_data.split('\n')
        if len(preview_lines) > 20:
            preview = '\n'.join(preview_lines[:20]) + f"\n... ({len(preview_lines) - 20} more lines)"
        else:
            preview = exported_data
        
        # Format complete response
        response_text = (
            f"{summary}"
            f"**Exported Data ({export_format.upper()}):**\n\n"
            f"```{export_format}\n{preview}\n```\n\n"
        )
        
        # Add usage suggestions
        response_text += self._generate_export_suggestions(export_format, result_count, data_size)
        
        return [TextContent(type="text", text=response_text)]
    
    def _generate_export_suggestions(self, export_format: str, result_count: int, data_size: int) -> str:
        """Generate export-related suggestions.
        
        Args:
            export_format: Export format used
            result_count: Number of results exported
            data_size: Size of exported data in bytes
            
        Returns:
            str: Export suggestions
        """
        suggestions = "**💡 Export Suggestions:**\n\n"
        
        # Format-specific suggestions
        if export_format == "json":
            suggestions += "- **JSON Format:** Ideal for programmatic processing and API integration\n"
            suggestions += "- **Processing:** Use `jq` command-line tool for JSON manipulation\n"
        elif export_format == "csv":
            suggestions += "- **CSV Format:** Perfect for spreadsheet applications and data analysis\n"
            suggestions += "- **Processing:** Import into Excel, Google Sheets, or pandas DataFrame\n"
        elif export_format == "xml":
            suggestions += "- **XML Format:** Suitable for structured data exchange and XSLT processing\n"
            suggestions += "- **Processing:** Use XML parsers or XSLT transformations\n"
        
        # Size-based suggestions
        if data_size > 1024 * 1024:  # > 1MB
            suggestions += f"- **Large Export:** {data_size/1024/1024:.1f} MB of data - consider streaming for processing\n"
        
        # Result count suggestions
        if result_count >= 1000:
            suggestions += f"- **Large Dataset:** {result_count:,} results - consider pagination for better performance\n"
        
        # Field filtering suggestion
        suggestions += "- **Field Filtering:** Use the 'fields' parameter to export only needed columns\n"
        
        # Time range optimization
        suggestions += "- **Time Range:** Narrow time ranges for faster exports and smaller datasets\n"
        
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


# Global export tool instance
_export_tool = SplunkExportTool()


def get_export_tool() -> SplunkExportTool:
    """Get the global export tool instance."""
    return _export_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for splunk_export."""
    return _export_tool.get_tool_definition()


async def execute_export(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the splunk_export tool."""
    return await _export_tool.execute(arguments)
