from fastapi import FastAPI
from fastmcp import MCPServer
from src.tools.github_tool import GitHubIssueTool
import os

app = FastAPI()
mcp = MCPServer("github-mcp-server")

# Initialize GitHub tool
github_tool = GitHubIssueTool(
    api_token=os.getenv("GITHUB_TOKEN"),
    api_url=os.getenv("GITHUB_API_URL", "https://api.github.com")
)

# Register the tool
mcp.register_tool(github_tool)

# Add MCP routes
app.include_router(mcp.router)