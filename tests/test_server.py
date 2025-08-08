#!/usr/bin/env python3
"""
Comprehensive tests for the FastMCP-based Splunk server
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from starlette.testclient import TestClient
from starlette.applications import Starlette
from mcp.types import TextContent

from src.server import mcp, splunk_search, create_starlette_app, main
from mcp.server.fastmcp.server import Context


class TestSplunkSearchTool:
    """Test the Splunk search tool."""
    
    @pytest.mark.asyncio
    async def test_splunk_search_successful(self):
        """Test successful Splunk search execution."""
        context = Context()
        
        # Mock the search tool
        with patch('src.server.get_search_tool') as mock_get_tool:
            mock_tool = MagicMock()
            mock_get_tool.return_value = mock_tool
            
            # Mock successful search results
            mock_result = TextContent(
                type="text",
                text="✅ **Splunk Search Completed**\n\nQuery: search index=main\nResults: 5 events"
            )
            mock_tool.execute = AsyncMock(return_value=[mock_result])
            
            result = await splunk_search("search index=main", context=context)
            
            assert "Splunk Search Completed" in result
            assert "Query: search index=main" in result
            mock_tool.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_splunk_search_with_parameters(self):
        """Test Splunk search with custom parameters."""
        context = Context()
        
        with patch('src.server.get_search_tool') as mock_get_tool:
            mock_tool = MagicMock()
            mock_get_tool.return_value = mock_tool
            
            mock_result = TextContent(
                type="text",
                text="✅ **Splunk Search Completed**\n\nQuery: search error\nResults: 10 events"
            )
            mock_tool.execute = AsyncMock(return_value=[mock_result])
            
            result = await splunk_search(
                query="search error",
                earliest_time="-1h",
                latest_time="now",
                max_results=50,
                timeout=120,
                context=context
            )
            
            assert "Splunk Search Completed" in result
            # Verify the arguments passed to the tool
            call_args = mock_tool.execute.call_args[0][0]
            assert call_args["query"] == "search error"
            assert call_args["earliest_time"] == "-1h"
            assert call_args["max_results"] == 50
            assert call_args["timeout"] == 120
    
    @pytest.mark.asyncio
    async def test_splunk_search_no_results(self):
        """Test Splunk search with no results."""
        context = Context()
        
        with patch('src.server.get_search_tool') as mock_get_tool:
            mock_tool = MagicMock()
            mock_get_tool.return_value = mock_tool
            
            # Mock empty results
            mock_tool.execute = AsyncMock(return_value=[])
            
            result = await splunk_search("search nonexistent", context=context)
            
            assert "No results returned from search" in result
    
    @pytest.mark.asyncio
    async def test_splunk_search_exception(self):
        """Test Splunk search with exception."""
        context = Context()
        
        with patch('src.server.get_search_tool') as mock_get_tool:
            mock_tool = MagicMock()
            mock_get_tool.return_value = mock_tool
            
            # Mock exception
            mock_tool.execute = AsyncMock(side_effect=Exception("Connection failed"))
            
            result = await splunk_search("search index=main", context=context)
            
            assert "Error executing search: Connection failed" in result


class TestStarletteApp:
    """Test the Starlette application creation and routing."""
    
    def test_create_starlette_app(self):
        """Test Starlette app creation."""
        mock_server = MagicMock()
        app = create_starlette_app(mock_server, debug=True)
        
        assert isinstance(app, Starlette)
        assert app.debug is True
        assert len(app.routes) == 3
    
    def test_create_starlette_app_default_debug(self):
        """Test Starlette app creation with default debug setting."""
        mock_server = MagicMock()
        app = create_starlette_app(mock_server)
        
        assert isinstance(app, Starlette)
        assert app.debug is False


class TestMainFunction:
    """Test the main function and server startup."""
    
    @patch('uvicorn.run')
    @patch('sys.argv', ['server.py'])
    def test_main_default_port(self, mock_uvicorn_run):
        """Test main function with default port."""
        main()
        
        mock_uvicorn_run.assert_called_once()
        args, kwargs = mock_uvicorn_run.call_args
        assert kwargs['host'] == "0.0.0.0"
        assert kwargs['port'] == 8756
    
    @patch('uvicorn.run')
    @patch('sys.argv', ['server.py', '9000'])
    def test_main_custom_port(self, mock_uvicorn_run):
        """Test main function with custom port."""
        main()
        
        mock_uvicorn_run.assert_called_once()
        args, kwargs = mock_uvicorn_run.call_args
        assert kwargs['host'] == "0.0.0.0"
        assert kwargs['port'] == 9000
    
    @patch('uvicorn.run')
    @patch('sys.argv', ['server.py', 'invalid'])
    def test_main_invalid_port(self, mock_uvicorn_run):
        """Test main function with invalid port argument."""
        with pytest.raises(ValueError):
            main()


class TestMCPServerIntegration:
    """Test MCP server integration."""
    
    def test_mcp_instance_creation(self):
        """Test that MCP instance is created correctly."""
        assert mcp is not None
        assert mcp._mcp_server is not None
        assert hasattr(mcp, '_mcp_server')
    
    def test_tool_registration(self):
        """Test that the splunk_search tool is registered."""
        # The tool should be registered with the MCP instance
        assert hasattr(mcp, '_tool_manager')
        assert hasattr(mcp._tool_manager, '_tools')
        # Check if our tool function is in the registered tools
        tool_names = list(mcp._tool_manager._tools.keys())
        assert 'splunk_search' in tool_names


class TestSSETransportIntegration:
    """Test SSE transport integration."""
    
    @patch('src.server.SseServerTransport')
    def test_sse_transport_creation(self, mock_sse_transport):
        """Test SSE transport creation in Starlette app."""
        mock_server = MagicMock()
        app = create_starlette_app(mock_server)
        
        # SSE transport should be created with correct path
        mock_sse_transport.assert_called_once_with("/messages")
    
    def test_route_configuration(self):
        """Test that routes are configured correctly."""
        mock_server = MagicMock()
        app = create_starlette_app(mock_server)
        
        # Check route paths
        route_paths = [route.path for route in app.routes]
        assert "/" in route_paths
        assert "/sse" in route_paths
        assert "/messages" in [getattr(route, 'path', None) for route in app.routes]


class TestAsyncHandlers:
    """Test async request handlers."""
    
    def test_async_handlers_exist(self):
        """Test that async handlers are properly defined."""
        mock_server = MagicMock()
        app = create_starlette_app(mock_server)
        
        # Verify that the routes exist and have callable endpoints
        route_paths = []
        async_endpoints = []
        
        for route in app.routes:
            if hasattr(route, 'path'):
                route_paths.append(route.path)
                # Only check endpoint for Route objects, not Mount objects
                if hasattr(route, 'endpoint') and route.path in ["/", "/sse"]:
                    assert callable(route.endpoint)
                    import inspect
                    if inspect.iscoroutinefunction(route.endpoint):
                        async_endpoints.append(route.path)
        
        assert "/" in route_paths
        assert "/sse" in route_paths
        assert "/messages" in route_paths
        
        # Verify that we have async endpoints for the main routes
        assert "/" in async_endpoints
        assert "/sse" in async_endpoints


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_splunk_search_with_empty_query(self):
        """Test search with empty query."""
        context = Context()
        
        with patch('src.server.get_search_tool') as mock_get_tool:
            mock_tool = MagicMock()
            mock_get_tool.return_value = mock_tool
            
            # Mock error for empty query
            mock_result = TextContent(
                type="text",
                text="❌ **Invalid Arguments**\n\nError: Query parameter is required"
            )
            mock_tool.execute = AsyncMock(return_value=[mock_result])
            
            result = await splunk_search("", context=context)
            
            assert "Invalid Arguments" in result or "Query parameter is required" in result
    
    @pytest.mark.asyncio
    async def test_splunk_search_connection_error(self):
        """Test search with connection error."""
        context = Context()
        
        with patch('src.server.get_search_tool') as mock_get_tool:
            mock_tool = MagicMock()
            mock_get_tool.return_value = mock_tool
            
            # Mock connection error
            mock_result = TextContent(
                type="text",
                text="❌ **Splunk Connection Error**\n\nFailed to connect to Splunk"
            )
            mock_tool.execute = AsyncMock(return_value=[mock_result])
            
            result = await splunk_search("search index=main", context=context)
            
            assert "Splunk Connection Error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.server", "--cov-report=term-missing"])
