"""Base prompt tool implementation for MCP."""

import os
from typing import Dict, Any, List
import structlog
from mcp.types import Tool, TextContent

logger = structlog.get_logger(__name__)


class BasePromptTool:
    """Base MCP tool for serving ready-to-use prompts."""
    
    def __init__(self, tool_name: str, description: str, prompt_filename: str):
        """Initialize the prompt tool.
        
        Args:
            tool_name: Name of the MCP tool
            description: Description of what the tool does
            prompt_filename: Name of the prompt file (e.g., 'analysis_prompt.txt')
        """
        self.tool_name = tool_name
        self.description = description
        self.prompt_filename = prompt_filename
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {},
                "title": f"{self.tool_name}Arguments"
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the prompt tool.
        
        Args:
            arguments: Tool arguments (none required)
            
        Returns:
            List[TextContent]: The ready-to-use prompt
        """
        try:
            logger.info("Serving ready-to-use prompt", tool=self.tool_name, file=self.prompt_filename)
            
            # Return the prompt content
            prompt_content = self._get_prompt()
            
            return [TextContent(type="text", text=prompt_content)]
            
        except Exception as e:
            logger.error("Unexpected error in prompt tool", tool=self.tool_name, error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Unexpected Error**\n\n"
                     f"An unexpected error occurred: {e}\n\n"
                     f"Please try again or contact support if the issue persists."
            )]
    
    def _get_prompt(self) -> str:
        """Get the ready-to-use prompt from external file.
        
        Returns:
            str: The prompt content
        """
        try:
            # Get the path to the prompt file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up two levels: from src/tools to project root, then to src/prompts
            project_root = os.path.dirname(os.path.dirname(current_dir))
            prompt_file_path = os.path.join(project_root, "src", "prompts", self.prompt_filename)
            
            # Read the prompt content from file and return as-is
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read().strip()
            
            return prompt_content
            
        except FileNotFoundError:
            logger.error("Prompt file not found", path=prompt_file_path)
            return f"""❌ **Prompt File Not Found**

The prompt file `src/prompts/{self.prompt_filename}` could not be found.
Please ensure the file exists and contains your prompt content."""
            
        except Exception as e:
            logger.error("Error reading prompt file", error=str(e))
            return f"""❌ **Error Reading Prompt File**

An error occurred while reading the prompt file: {str(e)}
Please check the file permissions and content."""


# Concrete implementation for analysis prompt
class AnalysisPromptTool(BasePromptTool):
    """MCP tool for serving analysis prompts."""
    
    def __init__(self):
        super().__init__(
            tool_name="get_analysis_prompt",
            description="Get a ready-to-use prompt for analysis",
            prompt_filename="analysis_prompt.txt"
        )


# Global prompt tool instance
_analysis_prompt_tool = AnalysisPromptTool()


def get_analysis_prompt_tool() -> AnalysisPromptTool:
    """Get the global analysis prompt tool instance."""
    return _analysis_prompt_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for get_analysis_prompt."""
    return _analysis_prompt_tool.get_tool_definition()


async def execute_analysis_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the get_analysis_prompt tool."""
    return await _analysis_prompt_tool.execute(arguments)
