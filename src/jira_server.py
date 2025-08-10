from fastapi import FastAPI, HTTPException
from fastmcp import MCPServer
from src.tools.jira_tool import JiraTicketTool
import os

app = FastAPI()
mcp = MCPServer("jira-mcp-server")

# Initialize Jira tool
jira_tool = JiraTicketTool(
    base_url=os.getenv("JIRA_BASE_URL"),
    username=os.getenv("JIRA_USERNAME"),
    api_token=os.getenv("JIRA_API_TOKEN")
)

# Register the tool
mcp.register_tool(jira_tool)

# Add MCP routes
app.include_router(mcp.router)