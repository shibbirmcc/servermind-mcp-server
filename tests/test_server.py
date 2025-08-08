#!/usr/bin/env python3
"""
Comprehensive tests for the FastMCP-based server
"""

import pytest
import asyncio
import subprocess
from unittest.mock import patch, MagicMock, AsyncMock
from starlette.testclient import TestClient
from starlette.applications import Starlette

from src.server import mcp, cm, create_starlette_app, main
from mcp.server.fastmcp.server import Context


class TestCommandTool:
    """Test the command execution tool."""
    
    def test_cm_successful_command(self):
        """Test successful command execution."""
        context = Context()
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "Hello World\n"
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = cm("echo 'Hello World'", context)
            
            assert "Command: echo 'Hello World'" in result
            assert "Exit code: 0" in result
            assert "Hello World" in result
            mock_run.assert_called_once_with(
                "echo 'Hello World'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
    
    def test_cm_command_with_stderr(self):
        """Test command execution with stderr output."""
        context = Context()
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.stderr = "Error message\n"
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            
            result = cm("invalid_command", context)
            
            assert "Command: invalid_command" in result
            assert "Exit code: 1" in result
            assert "Error message" in result
    
    def test_cm_command_timeout(self):
        """Test command execution timeout."""
        context = Context()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("sleep 60", 30)
            
            result = cm("sleep 60", context)
            
            assert "Command timed out: sleep 60" in result
    
    def test_cm_command_exception(self):
        """Test command execution with exception."""
        context = Context()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Unexpected error")
            
            result = cm("some_command", context)
            
            assert "Error executing command: Unexpected error" in result


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
        """Test that the cm tool is registered."""
        # The tool should be registered with the MCP instance
        assert hasattr(mcp, '_tool_manager')
        assert hasattr(mcp._tool_manager, '_tools')
        # Check if our tool function is in the registered tools
        tool_names = list(mcp._tool_manager._tools.keys())
        assert 'cm' in tool_names


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
    
    def test_cm_with_empty_command(self):
        """Test command execution with empty command."""
        context = Context()
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = cm("", context)
            
            assert "Command: " in result
            assert "Exit code: 0" in result
    
    def test_cm_with_special_characters(self):
        """Test command execution with special characters."""
        context = Context()
        command_with_special_chars = "echo 'Hello & World | Test'"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "Hello & World | Test\n"
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = cm(command_with_special_chars, context)
            
            assert f"Command: {command_with_special_chars}" in result
            assert "Hello & World | Test" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.server", "--cov-report=term-missing"])
