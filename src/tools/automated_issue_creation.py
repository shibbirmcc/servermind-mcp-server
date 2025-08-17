"""Automated issue creation tool for MCP - creates issues from root cause analysis."""

import json
from typing import Dict, Any, List
import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class AutomatedIssueCreationTool(BasePromptTool):
    """MCP tool for automated issue creation from root cause analysis."""
    
    def __init__(self):
        """Initialize the automated issue creation tool."""
        super().__init__(
            tool_name="automated_issue_creation",
            description="Generate instructions for creating GitHub/JIRA issues from root cause analysis",
            prompt_filename="automated_issue_creation.txt"
        )
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for automated_issue_creation."""
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "main_ticket": {
                        "type": "object",
                        "description": "Main ticket from root cause identification",
                        "properties": {
                            "trace_id": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "services_involved": {"type": "array", "items": {"type": "string"}},
                            "priority": {"type": "string"},
                            "first_seen": {"type": "string"},
                            "last_seen": {"type": "string"}
                        }
                    },
                    "root_causes_per_service": {
                        "type": "array",
                        "description": "Root causes per service from root cause identification",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service": {"type": "string"},
                                "primary_cause": {"type": "object"},
                                "error_logs": {"type": "array"},
                                "recommended_actions": {"type": "array"}
                            }
                        }
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform to create issues on",
                        "enum": ["github", "jira", "both", "auto"],
                        "default": "auto"
                    },
                    "github_repo": {
                        "type": "string",
                        "description": "GitHub repository name in format 'owner/repo'"
                    },
                    "jira_project": {
                        "type": "string",
                        "description": "JIRA project key"
                    }
                },
                "required": []  # No rigid requirements - prompt handles flexibility
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the automated issue creation tool - returns prompt with instructions."""
        try:
            # Extract arguments
            main_ticket = arguments.get("main_ticket")
            root_causes_per_service = arguments.get("root_causes_per_service")
            platform = arguments.get("platform", "auto")
            github_repo = arguments.get("github_repo")
            jira_project = arguments.get("jira_project")
            
            logger.info("Generating issue creation instructions", 
                       main_ticket=main_ticket.get('title', 'Unknown') if main_ticket else 'Flexible Input',
                       services=len(root_causes_per_service) if root_causes_per_service else 0,
                       platform=platform)
            
            # Format input data for the prompt - pass all arguments for flexible handling
            input_data = arguments
            
            # Get the prompt content and substitute the input data
            from string import Template
            prompt_template = Template(self._get_prompt())
            full_prompt = prompt_template.substitute(
                INPUT_DATA=json.dumps(input_data, indent=2)
            )
            
            return [TextContent(type="text", text=full_prompt)]
            
        except Exception as e:
            logger.error("Error in automated issue creation", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Automated Issue Creation Failed**\n\n"
                     f"An error occurred during automated issue creation: {e}\n\n"
                     f"Please check your parameters and try again."
            )]


# Global tool instance
_automated_issue_creation_tool = AutomatedIssueCreationTool()


def get_automated_issue_creation_tool() -> AutomatedIssueCreationTool:
    """Get the global automated issue creation tool instance."""
    return _automated_issue_creation_tool


async def execute_automated_issue_creation(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the automated issue creation tool."""
    return await _automated_issue_creation_tool.execute(arguments)
