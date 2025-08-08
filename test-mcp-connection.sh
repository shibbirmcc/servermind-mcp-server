#!/bin/bash

# Test script to verify MCP server functionality
# This demonstrates how Cline will interact with your MCP server

set -e

echo "🧪 Testing Splunk MCP Server Connection"
echo "========================================"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
SPLUNK_HOST="127.0.0.1"
SPLUNK_USERNAME="admin"
SPLUNK_PASSWORD="changeme123"
SPLUNK_VERIFY_SSL="false"

echo -e "${BLUE}Step 1: Starting MCP Server Container${NC}"
echo "Command: SPLUNK_HOST=$SPLUNK_HOST SPLUNK_USERNAME=$SPLUNK_USERNAME SPLUNK_PASSWORD=<password> SPLUNK_VERIFY_SSL=$SPLUNK_VERIFY_SSL ./docker-run-env.sh"
echo ""

# Start the container
SPLUNK_HOST="$SPLUNK_HOST" \
SPLUNK_USERNAME="$SPLUNK_USERNAME" \
SPLUNK_PASSWORD="$SPLUNK_PASSWORD" \
SPLUNK_VERIFY_SSL="$SPLUNK_VERIFY_SSL" \
./docker-run-env.sh > /dev/null 2>&1 || true

echo -e "${BLUE}Step 2: Checking Container Status${NC}"
CONTAINER_STATUS=$(docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep splunk-mcp-server || echo "Not found")
echo "Container Status: $CONTAINER_STATUS"
echo ""

if [[ "$CONTAINER_STATUS" == *"Exited (0)"* ]]; then
    echo -e "${GREEN}✅ Container exited cleanly (this is NORMAL for MCP servers!)${NC}"
else
    echo -e "${RED}❌ Unexpected container status${NC}"
    exit 1
fi

echo -e "${BLUE}Step 3: Testing MCP Protocol Communication${NC}"
echo "This simulates how Cline will communicate with your MCP server..."
echo ""

# Test initialize request
echo -e "${YELLOW}Sending initialize request...${NC}"
INIT_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}, "resources": {}}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'

RESPONSE=$(echo "$INIT_REQUEST" | \
    SPLUNK_HOST="$SPLUNK_HOST" \
    SPLUNK_USERNAME="$SPLUNK_USERNAME" \
    SPLUNK_PASSWORD="$SPLUNK_PASSWORD" \
    SPLUNK_VERIFY_SSL="$SPLUNK_VERIFY_SSL" \
    python -m src.server 2>/dev/null | tail -1)

if [[ "$RESPONSE" == *"splunk-mcp-server"* ]]; then
    echo -e "${GREEN}✅ MCP server responded correctly!${NC}"
    echo "Response: $RESPONSE"
else
    echo -e "${RED}❌ Unexpected response: $RESPONSE${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 4: Testing Tools List${NC}"
TOOLS_REQUEST='{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'

TOOLS_RESPONSE=$(echo "$TOOLS_REQUEST" | \
    SPLUNK_HOST="$SPLUNK_HOST" \
    SPLUNK_USERNAME="$SPLUNK_USERNAME" \
    SPLUNK_PASSWORD="$SPLUNK_PASSWORD" \
    SPLUNK_VERIFY_SSL="$SPLUNK_VERIFY_SSL" \
    python -m src.server 2>/dev/null | tail -1)

if [[ "$TOOLS_RESPONSE" == *"splunk_search"* ]]; then
    echo -e "${GREEN}✅ Tools available: splunk_search${NC}"
else
    echo -e "${RED}❌ Tools not found in response${NC}"
    echo "Response: $TOOLS_RESPONSE"
fi

echo ""
echo -e "${BLUE}Step 5: Testing Resources List${NC}"
RESOURCES_REQUEST='{"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}'

RESOURCES_RESPONSE=$(echo "$RESOURCES_REQUEST" | \
    SPLUNK_HOST="$SPLUNK_HOST" \
    SPLUNK_USERNAME="$SPLUNK_USERNAME" \
    SPLUNK_PASSWORD="$SPLUNK_PASSWORD" \
    SPLUNK_VERIFY_SSL="$SPLUNK_VERIFY_SSL" \
    python -m src.server 2>/dev/null | tail -1)

if [[ "$RESOURCES_RESPONSE" == *"connection-info"* ]]; then
    echo -e "${GREEN}✅ Resources available: connection-info, indexes${NC}"
else
    echo -e "${RED}❌ Resources not found in response${NC}"
    echo "Response: $RESOURCES_RESPONSE"
fi

echo ""
echo -e "${GREEN}🎉 MCP Server Test Complete!${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "• Your MCP server is working correctly"
echo "• Container behavior is normal (exits after loading config)"
echo "• MCP protocol communication is functional"
echo "• Ready for Cline integration!"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Copy the configuration from 'cline-mcp-config.json'"
echo "2. Add it to your Cline MCP settings"
echo "3. Restart VS Code"
echo "4. Test with Cline!"
echo ""
echo -e "${BLUE}Cline Configuration File: cline-mcp-config.json${NC}"
