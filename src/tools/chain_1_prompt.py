"""Chain 1 prompt tool implementation for MCP."""

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

class Chain1PromptTool(BasePromptTool):
    """MCP tool for serving Chain 1 prompts."""
    
    def __init__(self):
        super().__init__(
            tool_name="get_chain_1_prompt",
            description="Starts the test tool planning flow (Chain 1). Use this when the user asks to begin the planning test or run Chain 1. Accepts the user’s intent in natural language and returns a structured plan JSON with a next list of recommended actions, ranked by priority, with the best next step in next[0]. This plan drives the remainder of Chain 1 and hands off to Chain 2 and Chain 3 as the workflow progresses.",
            prompt_filename="chain_1_prompt.txt"
        )


# Global prompt tool instance
_chain_1_prompt_tool = Chain1PromptTool()


def get_chain_1_prompt_tool() -> Chain1PromptTool:
    """Get the global Chain 1 prompt tool instance."""
    return _chain_1_prompt_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for get_chain_1_prompt."""
    return _chain_1_prompt_tool.get_tool_definition()


async def execute_chain_1_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the get_chain_1_prompt tool."""
    return await _chain_1_prompt_tool.execute(arguments)
