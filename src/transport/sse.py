#!/usr/bin/env python3
"""
SSE Transport for MCP Server

Implements Server-Sent Events transport for streaming MCP communication.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, Optional, AsyncGenerator
import structlog
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse
from mcp.server import Server
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse, JSONRPCError

logger = structlog.get_logger(__name__)


class SSETransport:
    """Server-Sent Events transport for MCP."""
    
    def __init__(self, server: Server, host: str = "127.0.0.1", port: int = 8000):
        """Initialize SSE transport.
        
        Args:
            server: MCP server instance
            host: Host to bind to
            port: Port to bind to
        """
        self.server = server
        self.host = host
        self.port = port
        self.app = FastAPI(title="Splunk MCP Server", version="1.0.0")
        self.clients: Dict[str, asyncio.Queue] = {}
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up FastAPI routes for SSE transport."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint with server information."""
            return {
                "name": "Splunk MCP Server",
                "version": "1.0.0",
                "transport": "sse",
                "endpoints": {
                    "connect": "/connect",
                    "message": "/message"
                }
            }
        
        @self.app.get("/connect")
        async def connect(request: Request):
            """SSE endpoint for client connections."""
            client_id = str(uuid.uuid4())
            logger.info("New SSE client connecting", client_id=client_id)
            
            # Create message queue for this client
            message_queue = asyncio.Queue()
            self.clients[client_id] = message_queue
            
            async def event_generator():
                try:
                    # Send connection established event
                    yield {
                        "event": "connected",
                        "data": json.dumps({
                            "client_id": client_id,
                            "server": "Splunk MCP Server",
                            "version": "1.0.0"
                        })
                    }
                    
                    # Process messages from queue
                    while True:
                        try:
                            # Wait for message with timeout
                            message = await asyncio.wait_for(
                                message_queue.get(), timeout=30.0
                            )
                            
                            if message is None:  # Shutdown signal
                                break
                                
                            yield {
                                "event": "message",
                                "data": json.dumps(message)
                            }
                            
                        except asyncio.TimeoutError:
                            # Send keepalive
                            yield {
                                "event": "keepalive",
                                "data": json.dumps({"timestamp": asyncio.get_event_loop().time()})
                            }
                            
                except asyncio.CancelledError:
                    logger.info("SSE client disconnected", client_id=client_id)
                    raise
                except Exception as e:
                    logger.error("Error in SSE event generator", 
                               client_id=client_id, error=str(e))
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": str(e)})
                    }
                finally:
                    # Clean up client
                    if client_id in self.clients:
                        del self.clients[client_id]
                    logger.info("SSE client cleaned up", client_id=client_id)
            
            return EventSourceResponse(event_generator())
        
        @self.app.post("/message/{client_id}")
        async def handle_message(client_id: str, request: Request):
            """Handle incoming MCP messages from clients."""
            try:
                if client_id not in self.clients:
                    raise HTTPException(status_code=404, detail="Client not found")
                
                # Parse JSON-RPC message
                body = await request.json()
                logger.debug("Received message", client_id=client_id, message=body)
                
                # Process message through MCP server
                response = await self._process_mcp_message(body)
                
                # Send response back to client via SSE
                if response:
                    await self.clients[client_id].put(response)
                
                return {"status": "ok"}
                
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in message", client_id=client_id, error=str(e))
                raise HTTPException(status_code=400, detail="Invalid JSON")
            except Exception as e:
                logger.error("Error processing message", 
                           client_id=client_id, error=str(e))
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_mcp_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process MCP message through the server.
        
        Args:
            message: JSON-RPC message
            
        Returns:
            Response message or None
        """
        try:
            # Create a mock transport for processing
            mock_transport = MockTransport()
            
            # Process the message
            if "method" in message:
                # This is a request
                request = JSONRPCRequest(**message)
                response = await self._handle_request(request)
                return response.model_dump() if response else None
            else:
                # This might be a response or notification
                logger.debug("Received non-request message", message=message)
                return None
                
        except Exception as e:
            logger.error("Error processing MCP message", error=str(e))
            # Return JSON-RPC error response
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    async def _handle_request(self, request: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Handle MCP request.
        
        Args:
            request: JSON-RPC request
            
        Returns:
            JSON-RPC response or None
        """
        try:
            method = request.method
            params = request.params or {}
            
            logger.info("Processing MCP request", method=method, id=request.id)
            
            # Route to appropriate handler based on the server's registered handlers
            result = None
            
            if method == "tools/list":
                # Call the server's list_tools handler
                if hasattr(self.server, '_list_tools_handler') and self.server._list_tools_handler:
                    result = await self.server._list_tools_handler()
                else:
                    result = []
            elif method == "tools/call":
                # Call the server's call_tool handler
                if hasattr(self.server, '_call_tool_handler') and self.server._call_tool_handler:
                    result = await self.server._call_tool_handler(params.get("name"), params.get("arguments", {}))
                else:
                    raise ValueError(f"Tool not found: {params.get('name')}")
            elif method == "resources/list":
                # Call the server's list_resources handler
                if hasattr(self.server, '_list_resources_handler') and self.server._list_resources_handler:
                    result = await self.server._list_resources_handler()
                else:
                    result = []
            elif method == "resources/read":
                # Call the server's read_resource handler
                if hasattr(self.server, '_read_resource_handler') and self.server._read_resource_handler:
                    result = await self.server._read_resource_handler(params.get("uri"))
                else:
                    raise ValueError(f"Resource not found: {params.get('uri')}")
            else:
                raise ValueError(f"Unknown method: {method}")
            
            return JSONRPCResponse(
                id=request.id,
                result=result
            )
            
        except Exception as e:
            logger.error("Error handling request", method=request.method, error=str(e))
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32603,
                    message="Internal error",
                    data=str(e)
                )
            )
    
    async def broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
        """
        if not self.clients:
            return
            
        logger.debug("Broadcasting message to clients", 
                    client_count=len(self.clients))
        
        # Send to all clients
        for client_id, queue in self.clients.items():
            try:
                await queue.put(message)
            except Exception as e:
                logger.error("Error sending message to client", 
                           client_id=client_id, error=str(e))
    
    async def run(self):
        """Run the SSE transport server."""
        import uvicorn
        
        logger.info("Starting SSE transport server", 
                   host=self.host, port=self.port)
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        await server.serve()


class MockTransport:
    """Mock transport for internal message processing."""
    
    def __init__(self):
        self.closed = False
    
    async def read_message(self):
        """Mock read message."""
        return None
    
    async def write_message(self, message):
        """Mock write message."""
        pass
    
    async def close(self):
        """Mock close."""
        self.closed = True
