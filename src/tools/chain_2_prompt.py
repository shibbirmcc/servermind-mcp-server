"""Chain 2 prompt tool implementation for MCP."""

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

class Chain2PromptTool(BasePromptTool):
    """MCP tool for serving Chain 2 prompts."""
    
    def __init__(self):
        super().__init__(
            tool_name="get_chain_2_prompt",
            description="When user wants to test tool planning, this tool gets a ready-to-use prompt for Chain 2 processing",
            prompt_filename="chain_2_prompt.txt"
        )


# Global prompt tool instance
_chain_2_prompt_tool = Chain2PromptTool()


def get_chain_2_prompt_tool() -> Chain2PromptTool:
    """Get the global Chain 2 prompt tool instance."""
    return _chain_2_prompt_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for get_chain_2_prompt."""
    return _chain_2_prompt_tool.get_tool_definition()


async def execute_chain_2_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the get_chain_2_prompt tool."""
    return await _chain_2_prompt_tool.execute(arguments)
