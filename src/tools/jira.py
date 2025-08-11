"""JIRA tool implementation for MCP."""

from typing import Dict, Any, List, Optional
import structlog
from mcp.types import Tool, TextContent
from ..jira.client import JiraClient, JiraOperationError, JiraConnectionError, JiraAuthenticationError
from ..config import get_config

logger = structlog.get_logger(__name__)


class JiraSearchTool:
    """MCP tool for searching JIRA issues."""
    
    def __init__(self):
        """Initialize the JIRA search tool."""
        self.config = get_config()
        self._client: Optional[JiraClient] = None
    
    def get_client(self) -> Optional[JiraClient]:
        """Get or create JIRA client instance."""
        if self.config.jira is None:
            return None
        
        if self._client is None:
            self._client = JiraClient(self.config.jira)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for jira_search."""
        return Tool(
            name="jira_search",
            description="Search for JIRA issues using JQL (JIRA Query Language)",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string (e.g., 'project = PROJ AND status = Open', 'assignee = currentUser()')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 1000
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fields to include (e.g., ['key', 'summary', 'status', 'assignee'])",
                        "default": ["key", "summary", "status", "assignee", "reporter", "created", "updated", "priority", "issuetype"]
                    }
                },
                "required": ["jql"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the jira_search tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **JIRA Not Configured**\n\n"
                         "JIRA integration is not configured. Please set the following environment variables:\n"
                         "- JIRA_BASE_URL\n"
                         "- JIRA_USERNAME\n"
                         "- JIRA_API_TOKEN"
                )]
            
            # Extract arguments
            jql = arguments.get("jql")
            if not jql:
                raise ValueError("JQL query parameter is required")
            
            max_results = arguments.get("max_results", 50)
            fields = arguments.get("fields", ["key", "summary", "status", "assignee", "reporter", "created", "updated", "priority", "issuetype"])
            
            logger.info("Executing JIRA search", jql=jql, max_results=max_results)
            
            # Execute search
            results = client.search_issues(jql, max_results, fields)
            
            # Format results for MCP response
            return self._format_search_results(jql, results, max_results)
            
        except JiraConnectionError as e:
            logger.error("JIRA connection error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **JIRA Connection Error**\n\n"
                     f"Failed to connect to JIRA: {e}\n\n"
                     f"Please check your JIRA configuration and ensure the server is accessible."
            )]
        
        except JiraAuthenticationError as e:
            logger.error("JIRA authentication error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **JIRA Authentication Error**\n\n"
                     f"Authentication failed: {e}\n\n"
                     f"Please check your JIRA credentials (username and API token)."
            )]
        
        except JiraOperationError as e:
            logger.error("JIRA operation error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **JIRA Operation Error**\n\n"
                     f"Operation failed: {e}\n\n"
                     f"Please check your JQL query syntax and try again."
            )]
        
        except ValueError as e:
            logger.error("Invalid arguments", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Invalid Arguments**\n\n"
                     f"Error: {e}\n\n"
                     f"Please provide valid search parameters."
            )]
        
        except Exception as e:
            logger.error("Unexpected error in JIRA search tool", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Unexpected Error**\n\n"
                     f"An unexpected error occurred: {e}\n\n"
                     f"Please try again or contact support if the issue persists."
            )]
    
    def _format_search_results(self, jql: str, results: List[Dict[str, Any]], max_results: int) -> List[TextContent]:
        """Format search results for MCP response."""
        result_count = len(results)
        
        # Create summary
        summary = (
            f"✅ **JIRA Search Completed**\n\n"
            f"**JQL Query:** `{jql}`\n"
            f"**Results:** {result_count} issues\n"
            f"**Max Results:** {max_results}\n\n"
        )
        
        if result_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No issues found for the specified JQL query."
            )]
        
        # Format results
        formatted_results = summary + "**Issues Found:**\n\n"
        
        for i, issue in enumerate(results[:10], 1):  # Show first 10 issues in detail
            formatted_results += f"**{i}. {issue['key']}**\n"
            
            # Show key fields
            fields = issue.get('fields', {})
            if 'summary' in fields and fields['summary']:
                formatted_results += f"  - **Summary:** {fields['summary']}\n"
            if 'status' in fields and fields['status']:
                formatted_results += f"  - **Status:** {fields['status']}\n"
            if 'assignee' in fields and fields['assignee']:
                formatted_results += f"  - **Assignee:** {fields['assignee']}\n"
            if 'priority' in fields and fields['priority']:
                formatted_results += f"  - **Priority:** {fields['priority']}\n"
            if 'issuetype' in fields and fields['issuetype']:
                formatted_results += f"  - **Type:** {fields['issuetype']}\n"
            if 'created' in fields and fields['created']:
                formatted_results += f"  - **Created:** {fields['created']}\n"
            if 'updated' in fields and fields['updated']:
                formatted_results += f"  - **Updated:** {fields['updated']}\n"
            
            formatted_results += "\n"
        
        # Add summary if more results available
        if result_count > 10:
            formatted_results += f"... and {result_count - 10} more issues.\n\n"
        
        # Add analysis suggestions
        formatted_results += self._generate_analysis_suggestions(jql, results)
        
        return [TextContent(type="text", text=formatted_results)]
    
    def _generate_analysis_suggestions(self, jql: str, results: List[Dict[str, Any]]) -> str:
        """Generate analysis suggestions based on search results."""
        if not results:
            return ""
        
        suggestions = "**💡 Analysis Suggestions:**\n\n"
        
        # Analyze common patterns
        statuses = {}
        assignees = {}
        priorities = {}
        issue_types = {}
        
        for issue in results:
            fields = issue.get('fields', {})
            
            if 'status' in fields and fields['status']:
                statuses[fields['status']] = statuses.get(fields['status'], 0) + 1
            if 'assignee' in fields and fields['assignee']:
                assignees[fields['assignee']] = assignees.get(fields['assignee'], 0) + 1
            if 'priority' in fields and fields['priority']:
                priorities[fields['priority']] = priorities.get(fields['priority'], 0) + 1
            if 'issuetype' in fields and fields['issuetype']:
                issue_types[fields['issuetype']] = issue_types.get(fields['issuetype'], 0) + 1
        
        # Suggest status analysis
        if statuses:
            top_status = max(statuses.items(), key=lambda x: x[1])
            suggestions += f"- **Status Distribution:** Most issues are in '{top_status[0]}' status ({top_status[1]} issues)\n"
            suggestions += f"  Example: `project = PROJ AND status = '{top_status[0]}'`\n\n"
        
        # Suggest assignee analysis
        if assignees:
            top_assignee = max(assignees.items(), key=lambda x: x[1])
            suggestions += f"- **Workload Analysis:** '{top_assignee[0]}' has the most assigned issues ({top_assignee[1]} issues)\n"
            suggestions += f"  Example: `assignee = '{top_assignee[0]}' AND status != Done`\n\n"
        
        # Suggest priority analysis
        if priorities:
            high_priority_count = sum(count for priority, count in priorities.items() if 'high' in priority.lower() or 'critical' in priority.lower())
            if high_priority_count > 0:
                suggestions += f"- **Priority Analysis:** {high_priority_count} high-priority issues found\n"
                suggestions += f"  Example: `priority in (High, Critical) AND status != Done`\n\n"
        
        return suggestions
    
    def cleanup(self):
        """Clean up resources."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception as e:
                logger.warning("Error during client cleanup", error=str(e))
            finally:
                self._client = None


class JiraProjectsTool:
    """MCP tool for getting JIRA projects."""
    
    def __init__(self):
        """Initialize the JIRA projects tool."""
        self.config = get_config()
        self._client: Optional[JiraClient] = None
    
    def get_client(self) -> Optional[JiraClient]:
        """Get or create JIRA client instance."""
        if self.config.jira is None:
            return None
        
        if self._client is None:
            self._client = JiraClient(self.config.jira)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for jira_projects."""
        return Tool(
            name="jira_projects",
            description="Get list of available JIRA projects",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the jira_projects tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **JIRA Not Configured**\n\n"
                         "JIRA integration is not configured. Please set the following environment variables:\n"
                         "- JIRA_BASE_URL\n"
                         "- JIRA_USERNAME\n"
                         "- JIRA_API_TOKEN"
                )]
            
            logger.info("Getting JIRA projects")
            
            # Get projects
            projects = client.get_projects()
            
            # Format results for MCP response
            return self._format_projects_results(projects)
            
        except Exception as e:
            logger.error("Error getting JIRA projects", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Error Getting Projects**\n\n"
                     f"Failed to retrieve JIRA projects: {e}"
            )]
    
    def _format_projects_results(self, projects: List[Dict[str, Any]]) -> List[TextContent]:
        """Format projects results for MCP response."""
        project_count = len(projects)
        
        # Create summary
        summary = (
            f"✅ **JIRA Projects Retrieved**\n\n"
            f"**Total Projects:** {project_count}\n\n"
        )
        
        if project_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No projects found or no access to projects."
            )]
        
        # Format results
        formatted_results = summary + "**Available Projects:**\n\n"
        
        for project in projects:
            formatted_results += f"**{project['key']} - {project['name']}**\n"
            if project.get('description'):
                formatted_results += f"  - **Description:** {project['description']}\n"
            if project.get('lead'):
                formatted_results += f"  - **Lead:** {project['lead']}\n"
            if project.get('project_type'):
                formatted_results += f"  - **Type:** {project['project_type']}\n"
            formatted_results += "\n"
        
        # Add usage suggestions
        formatted_results += "**💡 Usage Examples:**\n\n"
        if projects:
            example_key = projects[0]['key']
            formatted_results += f"- Search issues in project: `project = {example_key}`\n"
            formatted_results += f"- Open issues in project: `project = {example_key} AND status != Done`\n"
            formatted_results += f"- Recent issues: `project = {example_key} AND created >= -7d`\n"
        
        return [TextContent(type="text", text=formatted_results)]


class JiraIssueTool:
    """MCP tool for getting specific JIRA issue details."""
    
    def __init__(self):
        """Initialize the JIRA issue tool."""
        self.config = get_config()
        self._client: Optional[JiraClient] = None
    
    def get_client(self) -> Optional[JiraClient]:
        """Get or create JIRA client instance."""
        if self.config.jira is None:
            return None
        
        if self._client is None:
            self._client = JiraClient(self.config.jira)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for jira_issue."""
        return Tool(
            name="jira_issue",
            description="Get detailed information about a specific JIRA issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "JIRA issue key (e.g., 'PROJ-123', 'DEV-456')"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fields to include",
                        "default": ["key", "summary", "description", "status", "assignee", "reporter", "created", "updated", "priority", "issuetype", "components", "labels"]
                    }
                },
                "required": ["issue_key"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the jira_issue tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **JIRA Not Configured**\n\n"
                         "JIRA integration is not configured. Please set the following environment variables:\n"
                         "- JIRA_BASE_URL\n"
                         "- JIRA_USERNAME\n"
                         "- JIRA_API_TOKEN"
                )]
            
            # Extract arguments
            issue_key = arguments.get("issue_key")
            if not issue_key:
                raise ValueError("Issue key parameter is required")
            
            fields = arguments.get("fields", ["key", "summary", "description", "status", "assignee", "reporter", "created", "updated", "priority", "issuetype", "components", "labels"])
            
            logger.info("Getting JIRA issue", issue_key=issue_key)
            
            # Get issue
            issue = client.get_issue(issue_key, fields)
            
            # Format results for MCP response
            return self._format_issue_results(issue)
            
        except Exception as e:
            logger.error("Error getting JIRA issue", issue_key=arguments.get("issue_key"), error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Error Getting Issue**\n\n"
                     f"Failed to retrieve JIRA issue: {e}"
            )]
    
    def _format_issue_results(self, issue: Dict[str, Any]) -> List[TextContent]:
        """Format issue results for MCP response."""
        # Create detailed issue view
        formatted_results = f"✅ **JIRA Issue Details**\n\n"
        formatted_results += f"**{issue['key']}**\n\n"
        
        fields = issue.get('fields', {})
        
        # Core fields
        if 'summary' in fields and fields['summary']:
            formatted_results += f"**Summary:** {fields['summary']}\n\n"
        
        if 'description' in fields and fields['description']:
            description = fields['description']
            if len(description) > 500:
                description = description[:500] + "..."
            formatted_results += f"**Description:** {description}\n\n"
        
        # Status and metadata
        formatted_results += "**Details:**\n"
        if 'status' in fields and fields['status']:
            formatted_results += f"- **Status:** {fields['status']}\n"
        if 'priority' in fields and fields['priority']:
            formatted_results += f"- **Priority:** {fields['priority']}\n"
        if 'issuetype' in fields and fields['issuetype']:
            formatted_results += f"- **Type:** {fields['issuetype']}\n"
        if 'assignee' in fields and fields['assignee']:
            formatted_results += f"- **Assignee:** {fields['assignee']}\n"
        if 'reporter' in fields and fields['reporter']:
            formatted_results += f"- **Reporter:** {fields['reporter']}\n"
        if 'created' in fields and fields['created']:
            formatted_results += f"- **Created:** {fields['created']}\n"
        if 'updated' in fields and fields['updated']:
            formatted_results += f"- **Updated:** {fields['updated']}\n"
        
        # Additional fields
        if 'components' in fields and fields['components']:
            components = fields['components']
            if isinstance(components, list):
                formatted_results += f"- **Components:** {', '.join(components)}\n"
            else:
                formatted_results += f"- **Components:** {components}\n"
        
        if 'labels' in fields and fields['labels']:
            labels = fields['labels']
            if isinstance(labels, list):
                formatted_results += f"- **Labels:** {', '.join(labels)}\n"
            else:
                formatted_results += f"- **Labels:** {labels}\n"
        
        return [TextContent(type="text", text=formatted_results)]


# Global tool instances
_search_tool = JiraSearchTool()
_projects_tool = JiraProjectsTool()
_issue_tool = JiraIssueTool()


def get_jira_search_tool() -> JiraSearchTool:
    """Get the global JIRA search tool instance."""
    return _search_tool


def get_jira_projects_tool() -> JiraProjectsTool:
    """Get the global JIRA projects tool instance."""
    return _projects_tool


def get_jira_issue_tool() -> JiraIssueTool:
    """Get the global JIRA issue tool instance."""
    return _issue_tool


def get_jira_tools() -> List[Tool]:
    """Get all JIRA tool definitions."""
    config = get_config()
    if config.jira is None:
        return []
    
    return [
        _search_tool.get_tool_definition(),
        _projects_tool.get_tool_definition(),
        _issue_tool.get_tool_definition()
    ]


async def execute_jira_search(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the jira_search tool."""
    return await _search_tool.execute(arguments)


async def execute_jira_projects(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the jira_projects tool."""
    return await _projects_tool.execute(arguments)


async def execute_jira_issue(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the jira_issue tool."""
    return await _issue_tool.execute(arguments)
