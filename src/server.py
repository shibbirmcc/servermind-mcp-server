#!/usr/bin/env python3
"""
Splunk MCP Server

A Model Context Protocol (MCP) server that provides seamless integration with Splunk
for log access, search, and analysis capabilities.
"""

import asyncio
import sys
from typing import Any, Sequence
import structlog
from mcp.server import Server
from mcp.types import (
    CallToolRequest,
    ListToolsRequest,
    Tool,
    TextContent,
    Resource,
    ListResourcesRequest,
    ReadResourceRequest,
)

from .config import get_config, Config
from .tools.search import get_search_tool, execute_search
from .splunk.client import SplunkClient, SplunkConnectionError
from .transport.sse import SSETransport

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class SplunkMCPServer:
    """Splunk MCP Server implementation."""
    
    def __init__(self):
        """Initialize the Splunk MCP server."""
        self.config: Config = None
        self.server = Server("splunk-mcp-server")
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up MCP server handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """Handle list tools request."""
            try:
                logger.info("Listing available tools")
                
                tools = [
                    get_search_tool().get_tool_definition(),
                ]
                
                logger.info("Tools listed successfully", tool_count=len(tools))
                return tools
                
            except Exception as e:
                logger.error("Error listing tools", error=str(e))
                raise
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
            """Handle tool execution request."""
            try:
                logger.info("Executing tool", tool_name=name, arguments=arguments)
                
                if name == "splunk_search":
                    result = await execute_search(arguments)
                    logger.info("Tool executed successfully", tool_name=name)
                    return result
                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error(error_msg, tool_name=name)
                    return [TextContent(
                        type="text",
                        text=f"❌ **Error**: {error_msg}"
                    )]
                    
            except Exception as e:
                logger.error("Error executing tool", tool_name=name, error=str(e))
                return [TextContent(
                    type="text",
                    text=f"❌ **Tool Execution Error**\n\n"
                         f"Failed to execute tool '{name}': {e}"
                )]
        
        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """Handle list resources request."""
            try:
                logger.info("Listing available resources")
                
                resources = [
                    Resource(
                        uri="splunk://connection-info",
                        name="Splunk Connection Information",
                        description="Information about the current Splunk connection",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="splunk://indexes",
                        name="Splunk Indexes",
                        description="List of available Splunk indexes",
                        mimeType="application/json"
                    ),
                ]
                
                logger.info("Resources listed successfully", resource_count=len(resources))
                return resources
                
            except Exception as e:
                logger.error("Error listing resources", error=str(e))
                raise
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Handle resource read request."""
            try:
                logger.info("Reading resource", uri=uri)
                
                if uri == "splunk://connection-info":
                    return await self._get_connection_info()
                elif uri == "splunk://indexes":
                    return await self._get_indexes_info()
                else:
                    error_msg = f"Unknown resource: {uri}"
                    logger.error(error_msg, uri=uri)
                    raise ValueError(error_msg)
                    
            except Exception as e:
                logger.error("Error reading resource", uri=uri, error=str(e))
                raise
    
    async def _get_connection_info(self) -> str:
        """Get Splunk connection information."""
        try:
            config = get_config()
            client = SplunkClient(config.splunk)
            
            try:
                connection_info = client.test_connection()
                return f"""{{
    "status": "connected",
    "host": "{config.splunk.host}",
    "port": {config.splunk.port},
    "scheme": "{config.splunk.scheme}",
    "version": "{connection_info.get('version', 'unknown')}",
    "build": "{connection_info.get('build', 'unknown')}",
    "server_name": "{connection_info.get('server_name', 'unknown')}",
    "license_state": "{connection_info.get('license_state', 'unknown')}",
    "mode": "{connection_info.get('mode', 'unknown')}"
}}"""
            except SplunkConnectionError as e:
                return f"""{{
    "status": "disconnected",
    "host": "{config.splunk.host}",
    "port": {config.splunk.port},
    "scheme": "{config.splunk.scheme}",
    "error": "{str(e)}"
}}"""
            finally:
                client.disconnect()
                
        except Exception as e:
            logger.error("Error getting connection info", error=str(e))
            return f'{{"status": "error", "error": "{str(e)}"}}'
    
    async def _get_indexes_info(self) -> str:
        """Get Splunk indexes information."""
        try:
            config = get_config()
            client = SplunkClient(config.splunk)
            
            try:
                indexes = client.get_indexes()
                indexes_json = "[\n"
                for i, index in enumerate(indexes):
                    if i > 0:
                        indexes_json += ",\n"
                    indexes_json += f"""  {{
    "name": "{index['name']}",
    "total_event_count": {index.get('total_event_count', 0)},
    "current_db_size_mb": {index.get('current_db_size_mb', 0)},
    "max_data_size": "{index.get('max_data_size', 'auto')}",
    "disabled": {str(index.get('disabled', False)).lower()},
    "earliest_time": "{index.get('earliest_time', '')}",
    "latest_time": "{index.get('latest_time', '')}"
  }}"""
                indexes_json += "\n]"
                return indexes_json
                
            except SplunkConnectionError as e:
                return f'{{"error": "Failed to retrieve indexes: {str(e)}"}}'
            finally:
                client.disconnect()
                
        except Exception as e:
            logger.error("Error getting indexes info", error=str(e))
            return f'{{"error": "Error retrieving indexes: {str(e)}"}}'
    
    async def run(self):
        """Run the MCP server."""
        try:
            # Load configuration
            self.config = get_config()
            logger.info("Splunk MCP Server starting", 
                       server_name=self.config.mcp.server_name,
                       version=self.config.mcp.version,
                       splunk_host=self.config.splunk.host)
            
            # Test Splunk connection on startup
            await self._test_initial_connection()
            
            # Create and run SSE transport
            sse_transport = SSETransport(self.server, host="127.0.0.1", port=9090)
            logger.info("MCP server running on SSE transport", host="127.0.0.1", port=9090)
            await sse_transport.run()
                
        except KeyboardInterrupt:
            logger.info("Server shutdown requested")
        except Exception as e:
            logger.error("Server error", error=str(e))
            raise
        finally:
            await self._cleanup()
    
    async def _test_initial_connection(self):
        """Test initial connection to Splunk."""
        try:
            logger.info("Testing initial Splunk connection")
            client = SplunkClient(self.config.splunk)
            
            try:
                connection_info = client.test_connection()
                logger.info("Initial Splunk connection successful",
                           version=connection_info.get('version'),
                           server_name=connection_info.get('server_name'))
            except SplunkConnectionError as e:
                logger.warning("Initial Splunk connection failed", error=str(e))
                logger.info("Server will continue running, but Splunk operations may fail")
            finally:
                client.disconnect()
                
        except Exception as e:
            logger.error("Error during initial connection test", error=str(e))
    
    async def _cleanup(self):
        """Clean up server resources."""
        try:
            logger.info("Cleaning up server resources")
            
            # Clean up search tool
            search_tool = get_search_tool()
            search_tool.cleanup()
            
            logger.info("Server cleanup completed")
            
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))


async def main():
    """Main entry point for the Splunk MCP server."""
    try:
        server = SplunkMCPServer()
        await server.run()
    except Exception as e:
        logger.error("Fatal server error", error=str(e))
        sys.exit(1)


def sync_main():
    """Synchronous main entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    sync_main()
