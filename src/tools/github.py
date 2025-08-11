"""GitHub tool implementation for MCP."""

from typing import Dict, Any, List, Optional
import structlog
from mcp.types import Tool, TextContent
from ..github.client import GitHubClient, GitHubOperationError, GitHubConnectionError, GitHubAuthenticationError
from ..config import get_config

logger = structlog.get_logger(__name__)


class GitHubRepositoriesTool:
    """MCP tool for getting GitHub repositories."""
    
    def __init__(self):
        """Initialize the GitHub repositories tool."""
        self.config = get_config()
        self._client: Optional[GitHubClient] = None
    
    def get_client(self) -> Optional[GitHubClient]:
        """Get or create GitHub client instance."""
        if self.config.github is None:
            return None
        
        if self._client is None:
            self._client = GitHubClient(self.config.github)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for github_repositories."""
        return Tool(
            name="github_repositories",
            description="Get list of GitHub repositories for a user or organization",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_or_org": {
                        "type": "string",
                        "description": "Username or organization name (leave empty for authenticated user's repositories)"
                    },
                    "repo_type": {
                        "type": "string",
                        "description": "Repository type filter",
                        "enum": ["all", "owner", "public", "private", "member"],
                        "default": "all"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": []
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the github_repositories tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **GitHub Not Configured**\n\n"
                         "GitHub integration is not configured. Please set the following environment variable:\n"
                         "- GITHUB_TOKEN"
                )]
            
            # Extract arguments
            user_or_org = arguments.get("user_or_org")
            repo_type = arguments.get("repo_type", "all")
            max_results = arguments.get("max_results", 30)
            
            logger.info("Getting GitHub repositories", user_or_org=user_or_org, repo_type=repo_type, max_results=max_results)
            
            # Get repositories
            repositories = client.get_repositories(user_or_org, repo_type, max_results)
            
            # Format results for MCP response
            return self._format_repositories_results(repositories, user_or_org, repo_type)
            
        except GitHubConnectionError as e:
            logger.error("GitHub connection error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **GitHub Connection Error**\n\n"
                     f"Failed to connect to GitHub: {e}\n\n"
                     f"Please check your GitHub configuration and ensure the API is accessible."
            )]
        
        except GitHubAuthenticationError as e:
            logger.error("GitHub authentication error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **GitHub Authentication Error**\n\n"
                     f"Authentication failed: {e}\n\n"
                     f"Please check your GitHub token."
            )]
        
        except GitHubOperationError as e:
            logger.error("GitHub operation error", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **GitHub Operation Error**\n\n"
                     f"Operation failed: {e}\n\n"
                     f"Please check your parameters and try again."
            )]
        
        except Exception as e:
            logger.error("Unexpected error in GitHub repositories tool", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Unexpected Error**\n\n"
                     f"An unexpected error occurred: {e}\n\n"
                     f"Please try again or contact support if the issue persists."
            )]
    
    def _format_repositories_results(self, repositories: List[Dict[str, Any]], user_or_org: Optional[str], repo_type: str) -> List[TextContent]:
        """Format repositories results for MCP response."""
        repo_count = len(repositories)
        
        # Create summary
        target = user_or_org if user_or_org else "authenticated user"
        summary = (
            f"✅ **GitHub Repositories Retrieved**\n\n"
            f"**Target:** {target}\n"
            f"**Type:** {repo_type}\n"
            f"**Results:** {repo_count} repositories\n\n"
        )
        
        if repo_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No repositories found for the specified criteria."
            )]
        
        # Format results
        formatted_results = summary + "**Repositories:**\n\n"
        
        for i, repo in enumerate(repositories[:10], 1):  # Show first 10 repositories in detail
            formatted_results += f"**{i}. {repo['full_name']}**\n"
            
            if repo.get('description'):
                formatted_results += f"  - **Description:** {repo['description']}\n"
            if repo.get('language'):
                formatted_results += f"  - **Language:** {repo['language']}\n"
            formatted_results += f"  - **Stars:** {repo.get('stargazers_count', 0)}\n"
            formatted_results += f"  - **Forks:** {repo.get('forks_count', 0)}\n"
            formatted_results += f"  - **Issues:** {repo.get('open_issues_count', 0)}\n"
            formatted_results += f"  - **Private:** {'Yes' if repo.get('private') else 'No'}\n"
            if repo.get('updated_at'):
                formatted_results += f"  - **Updated:** {repo['updated_at']}\n"
            formatted_results += f"  - **URL:** {repo.get('html_url', '')}\n"
            formatted_results += "\n"
        
        # Add summary if more results available
        if repo_count > 10:
            formatted_results += f"... and {repo_count - 10} more repositories.\n\n"
        
        # Add usage suggestions
        formatted_results += self._generate_repository_suggestions(repositories)
        
        return [TextContent(type="text", text=formatted_results)]
    
    def _generate_repository_suggestions(self, repositories: List[Dict[str, Any]]) -> str:
        """Generate usage suggestions based on repositories."""
        if not repositories:
            return ""
        
        suggestions = "**💡 Usage Suggestions:**\n\n"
        
        # Analyze languages
        languages = {}
        for repo in repositories:
            if repo.get('language'):
                languages[repo['language']] = languages.get(repo['language'], 0) + 1
        
        if languages:
            top_language = max(languages.items(), key=lambda x: x[1])
            suggestions += f"- **Popular Language:** {top_language[0]} ({top_language[1]} repositories)\n"
        
        # Find most active repository
        most_active = max(repositories, key=lambda x: x.get('stargazers_count', 0) + x.get('forks_count', 0))
        suggestions += f"- **Most Active:** {most_active['full_name']} ({most_active.get('stargazers_count', 0)} stars)\n"
        
        # Suggest exploring issues
        if repositories:
            example_repo = repositories[0]['full_name']
            suggestions += f"- **Explore Issues:** Use `github_issues` tool with repo: `{example_repo}`\n"
            suggestions += f"- **View Repository:** Use `github_repository` tool with repo: `{example_repo}`\n"
        
        return suggestions


class GitHubRepositoryTool:
    """MCP tool for getting specific GitHub repository details."""
    
    def __init__(self):
        """Initialize the GitHub repository tool."""
        self.config = get_config()
        self._client: Optional[GitHubClient] = None
    
    def get_client(self) -> Optional[GitHubClient]:
        """Get or create GitHub client instance."""
        if self.config.github is None:
            return None
        
        if self._client is None:
            self._client = GitHubClient(self.config.github)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for github_repository."""
        return Tool(
            name="github_repository",
            description="Get detailed information about a specific GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')"
                    }
                },
                "required": ["repo_name"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the github_repository tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **GitHub Not Configured**\n\n"
                         "GitHub integration is not configured. Please set the following environment variable:\n"
                         "- GITHUB_TOKEN"
                )]
            
            # Extract arguments
            repo_name = arguments.get("repo_name")
            if not repo_name:
                raise ValueError("Repository name parameter is required")
            
            logger.info("Getting GitHub repository", repo_name=repo_name)
            
            # Get repository
            repository = client.get_repository(repo_name)
            
            # Format results for MCP response
            return self._format_repository_results(repository)
            
        except Exception as e:
            logger.error("Error getting GitHub repository", repo_name=arguments.get("repo_name"), error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Error Getting Repository**\n\n"
                     f"Failed to retrieve GitHub repository: {e}"
            )]
    
    def _format_repository_results(self, repository: Dict[str, Any]) -> List[TextContent]:
        """Format repository results for MCP response."""
        # Create detailed repository view
        formatted_results = f"✅ **GitHub Repository Details**\n\n"
        formatted_results += f"**{repository['full_name']}**\n\n"
        
        # Core information
        if repository.get('description'):
            formatted_results += f"**Description:** {repository['description']}\n\n"
        
        # Statistics
        formatted_results += "**Statistics:**\n"
        formatted_results += f"- **Stars:** {repository.get('stargazers_count', 0)}\n"
        formatted_results += f"- **Watchers:** {repository.get('watchers_count', 0)}\n"
        formatted_results += f"- **Forks:** {repository.get('forks_count', 0)}\n"
        formatted_results += f"- **Open Issues:** {repository.get('open_issues_count', 0)}\n"
        formatted_results += f"- **Language:** {repository.get('language', 'Not specified')}\n"
        formatted_results += f"- **Private:** {'Yes' if repository.get('private') else 'No'}\n\n"
        
        # Metadata
        formatted_results += "**Details:**\n"
        if repository.get('owner'):
            formatted_results += f"- **Owner:** {repository['owner']['login']} ({repository['owner']['type']})\n"
        if repository.get('default_branch'):
            formatted_results += f"- **Default Branch:** {repository['default_branch']}\n"
        if repository.get('license'):
            formatted_results += f"- **License:** {repository['license']}\n"
        if repository.get('created_at'):
            formatted_results += f"- **Created:** {repository['created_at']}\n"
        if repository.get('updated_at'):
            formatted_results += f"- **Updated:** {repository['updated_at']}\n"
        if repository.get('pushed_at'):
            formatted_results += f"- **Last Push:** {repository['pushed_at']}\n"
        
        # Topics
        if repository.get('topics'):
            topics = repository['topics']
            if topics:
                formatted_results += f"- **Topics:** {', '.join(topics)}\n"
        
        # URLs
        formatted_results += "\n**Links:**\n"
        if repository.get('html_url'):
            formatted_results += f"- **GitHub:** {repository['html_url']}\n"
        if repository.get('clone_url'):
            formatted_results += f"- **Clone (HTTPS):** {repository['clone_url']}\n"
        if repository.get('ssh_url'):
            formatted_results += f"- **Clone (SSH):** {repository['ssh_url']}\n"
        
        return [TextContent(type="text", text=formatted_results)]


class GitHubIssuesTool:
    """MCP tool for getting GitHub issues from a repository."""
    
    def __init__(self):
        """Initialize the GitHub issues tool."""
        self.config = get_config()
        self._client: Optional[GitHubClient] = None
    
    def get_client(self) -> Optional[GitHubClient]:
        """Get or create GitHub client instance."""
        if self.config.github is None:
            return None
        
        if self._client is None:
            self._client = GitHubClient(self.config.github)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for github_issues."""
        return Tool(
            name="github_issues",
            description="Get issues from a GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')"
                    },
                    "state": {
                        "type": "string",
                        "description": "Issue state filter",
                        "enum": ["open", "closed", "all"],
                        "default": "open"
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of label names to filter by (e.g., ['bug', 'enhancement'])"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Username to filter by assignee"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["repo_name"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the github_issues tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **GitHub Not Configured**\n\n"
                         "GitHub integration is not configured. Please set the following environment variable:\n"
                         "- GITHUB_TOKEN"
                )]
            
            # Extract arguments
            repo_name = arguments.get("repo_name")
            if not repo_name:
                raise ValueError("Repository name parameter is required")
            
            state = arguments.get("state", "open")
            labels = arguments.get("labels")
            assignee = arguments.get("assignee")
            max_results = arguments.get("max_results", 30)
            
            logger.info("Getting GitHub issues", repo_name=repo_name, state=state, max_results=max_results)
            
            # Get issues
            issues = client.get_issues(repo_name, state, labels, assignee, max_results)
            
            # Format results for MCP response
            return self._format_issues_results(issues, repo_name, state, labels, assignee)
            
        except Exception as e:
            logger.error("Error getting GitHub issues", repo_name=arguments.get("repo_name"), error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Error Getting Issues**\n\n"
                     f"Failed to retrieve GitHub issues: {e}"
            )]
    
    def _format_issues_results(self, issues: List[Dict[str, Any]], repo_name: str, state: str, 
                              labels: Optional[List[str]], assignee: Optional[str]) -> List[TextContent]:
        """Format issues results for MCP response."""
        issue_count = len(issues)
        
        # Create summary
        summary = (
            f"✅ **GitHub Issues Retrieved**\n\n"
            f"**Repository:** {repo_name}\n"
            f"**State:** {state}\n"
        )
        
        if labels:
            summary += f"**Labels:** {', '.join(labels)}\n"
        if assignee:
            summary += f"**Assignee:** {assignee}\n"
        
        summary += f"**Results:** {issue_count} issues\n\n"
        
        if issue_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No issues found for the specified criteria."
            )]
        
        # Format results
        formatted_results = summary + "**Issues:**\n\n"
        
        for i, issue in enumerate(issues[:10], 1):  # Show first 10 issues in detail
            formatted_results += f"**{i}. #{issue['number']} - {issue['title']}**\n"
            
            if issue.get('body') and len(issue['body']) > 0:
                body = issue['body']
                if len(body) > 200:
                    body = body[:200] + "..."
                formatted_results += f"  - **Description:** {body}\n"
            
            formatted_results += f"  - **State:** {issue['state']}\n"
            
            if issue.get('user'):
                formatted_results += f"  - **Author:** {issue['user']['login']}\n"
            
            if issue.get('assignee'):
                formatted_results += f"  - **Assignee:** {issue['assignee']['login']}\n"
            elif issue.get('assignees') and len(issue['assignees']) > 0:
                assignees = [a['login'] for a in issue['assignees']]
                formatted_results += f"  - **Assignees:** {', '.join(assignees)}\n"
            
            if issue.get('labels') and len(issue['labels']) > 0:
                labels = [label['name'] for label in issue['labels']]
                formatted_results += f"  - **Labels:** {', '.join(labels)}\n"
            
            if issue.get('milestone'):
                formatted_results += f"  - **Milestone:** {issue['milestone']['title']}\n"
            
            formatted_results += f"  - **Comments:** {issue.get('comments', 0)}\n"
            
            if issue.get('created_at'):
                formatted_results += f"  - **Created:** {issue['created_at']}\n"
            
            if issue.get('html_url'):
                formatted_results += f"  - **URL:** {issue['html_url']}\n"
            
            formatted_results += "\n"
        
        # Add summary if more results available
        if issue_count > 10:
            formatted_results += f"... and {issue_count - 10} more issues.\n\n"
        
        # Add analysis suggestions
        formatted_results += self._generate_issues_analysis(issues)
        
        return [TextContent(type="text", text=formatted_results)]
    
    def _generate_issues_analysis(self, issues: List[Dict[str, Any]]) -> str:
        """Generate analysis suggestions based on issues."""
        if not issues:
            return ""
        
        suggestions = "**💡 Analysis:**\n\n"
        
        # Analyze labels
        label_counts = {}
        for issue in issues:
            if issue.get('labels'):
                for label in issue['labels']:
                    label_name = label['name']
                    label_counts[label_name] = label_counts.get(label_name, 0) + 1
        
        if label_counts:
            top_label = max(label_counts.items(), key=lambda x: x[1])
            suggestions += f"- **Most Common Label:** '{top_label[0]}' ({top_label[1]} issues)\n"
        
        # Analyze assignees
        assignee_counts = {}
        for issue in issues:
            if issue.get('assignee'):
                assignee = issue['assignee']['login']
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
        
        if assignee_counts:
            top_assignee = max(assignee_counts.items(), key=lambda x: x[1])
            suggestions += f"- **Most Active Assignee:** {top_assignee[0]} ({top_assignee[1]} issues)\n"
        
        # Count unassigned issues
        unassigned = sum(1 for issue in issues if not issue.get('assignee') and not issue.get('assignees'))
        if unassigned > 0:
            suggestions += f"- **Unassigned Issues:** {unassigned} issues need assignment\n"
        
        return suggestions


class GitHubPullRequestsTool:
    """MCP tool for getting GitHub pull requests from a repository."""
    
    def __init__(self):
        """Initialize the GitHub pull requests tool."""
        self.config = get_config()
        self._client: Optional[GitHubClient] = None
    
    def get_client(self) -> Optional[GitHubClient]:
        """Get or create GitHub client instance."""
        if self.config.github is None:
            return None
        
        if self._client is None:
            self._client = GitHubClient(self.config.github)
        return self._client
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for github_pull_requests."""
        return Tool(
            name="github_pull_requests",
            description="Get pull requests from a GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository name in format 'owner/repo' (e.g., 'octocat/Hello-World')"
                    },
                    "state": {
                        "type": "string",
                        "description": "Pull request state filter",
                        "enum": ["open", "closed", "all"],
                        "default": "open"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["repo_name"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the github_pull_requests tool."""
        try:
            client = self.get_client()
            if client is None:
                return [TextContent(
                    type="text",
                    text="❌ **GitHub Not Configured**\n\n"
                         "GitHub integration is not configured. Please set the following environment variable:\n"
                         "- GITHUB_TOKEN"
                )]
            
            # Extract arguments
            repo_name = arguments.get("repo_name")
            if not repo_name:
                raise ValueError("Repository name parameter is required")
            
            state = arguments.get("state", "open")
            max_results = arguments.get("max_results", 30)
            
            logger.info("Getting GitHub pull requests", repo_name=repo_name, state=state, max_results=max_results)
            
            # Get pull requests
            pull_requests = client.get_pull_requests(repo_name, state, max_results)
            
            # Format results for MCP response
            return self._format_pull_requests_results(pull_requests, repo_name, state)
            
        except Exception as e:
            logger.error("Error getting GitHub pull requests", repo_name=arguments.get("repo_name"), error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Error Getting Pull Requests**\n\n"
                     f"Failed to retrieve GitHub pull requests: {e}"
            )]
    
    def _format_pull_requests_results(self, pull_requests: List[Dict[str, Any]], repo_name: str, state: str) -> List[TextContent]:
        """Format pull requests results for MCP response."""
        pr_count = len(pull_requests)
        
        # Create summary
        summary = (
            f"✅ **GitHub Pull Requests Retrieved**\n\n"
            f"**Repository:** {repo_name}\n"
            f"**State:** {state}\n"
            f"**Results:** {pr_count} pull requests\n\n"
        )
        
        if pr_count == 0:
            return [TextContent(
                type="text",
                text=summary + "No pull requests found for the specified criteria."
            )]
        
        # Format results
        formatted_results = summary + "**Pull Requests:**\n\n"
        
        for i, pr in enumerate(pull_requests[:10], 1):  # Show first 10 PRs in detail
            formatted_results += f"**{i}. #{pr['number']} - {pr['title']}**\n"
            
            if pr.get('body') and len(pr['body']) > 0:
                body = pr['body']
                if len(body) > 200:
                    body = body[:200] + "..."
                formatted_results += f"  - **Description:** {body}\n"
            
            formatted_results += f"  - **State:** {pr['state']}\n"
            
            if pr.get('user'):
                formatted_results += f"  - **Author:** {pr['user']['login']}\n"
            
            if pr.get('head') and pr.get('base'):
                formatted_results += f"  - **Branch:** {pr['head']['ref']} → {pr['base']['ref']}\n"
            
            formatted_results += f"  - **Merged:** {'Yes' if pr.get('merged') else 'No'}\n"
            
            if pr.get('mergeable') is not None:
                formatted_results += f"  - **Mergeable:** {'Yes' if pr['mergeable'] else 'No'}\n"
            
            formatted_results += f"  - **Comments:** {pr.get('comments', 0)}\n"
            formatted_results += f"  - **Review Comments:** {pr.get('review_comments', 0)}\n"
            formatted_results += f"  - **Commits:** {pr.get('commits', 0)}\n"
            formatted_results += f"  - **Additions:** +{pr.get('additions', 0)}\n"
            formatted_results += f"  - **Deletions:** -{pr.get('deletions', 0)}\n"
            formatted_results += f"  - **Files Changed:** {pr.get('changed_files', 0)}\n"
            
            if pr.get('created_at'):
                formatted_results += f"  - **Created:** {pr['created_at']}\n"
            
            if pr.get('html_url'):
                formatted_results += f"  - **URL:** {pr['html_url']}\n"
            
            formatted_results += "\n"
        
        # Add summary if more results available
        if pr_count > 10:
            formatted_results += f"... and {pr_count - 10} more pull requests.\n\n"
        
        # Add analysis suggestions
        formatted_results += self._generate_pr_analysis(pull_requests)
        
        return [TextContent(type="text", text=formatted_results)]
    
    def _generate_pr_analysis(self, pull_requests: List[Dict[str, Any]]) -> str:
        """Generate analysis suggestions based on pull requests."""
        if not pull_requests:
            return ""
        
        suggestions = "**💡 Analysis:**\n\n"
        
        # Count merged vs open
        merged_count = sum(1 for pr in pull_requests if pr.get('merged'))
        open_count = sum(1 for pr in pull_requests if pr.get('state') == 'open')
        
        if merged_count > 0:
            suggestions += f"- **Merged PRs:** {merged_count} out of {len(pull_requests)}\n"
        
        if open_count > 0:
            suggestions += f"- **Open PRs:** {open_count} awaiting review/merge\n"
        
        # Analyze authors
        author_counts = {}
        for pr in pull_requests:
            if pr.get('user'):
                author = pr['user']['login']
                author_counts[author] = author_counts.get(author, 0) + 1
        
        if author_counts:
            top_author = max(author_counts.items(), key=lambda x: x[1])
            suggestions += f"- **Most Active Contributor:** {top_author[0]} ({top_author[1]} PRs)\n"
        
        # Analyze code changes
        total_additions = sum(pr.get('additions', 0) for pr in pull_requests)
        total_deletions = sum(pr.get('deletions', 0) for pr in pull_requests)
        
        if total_additions > 0 or total_deletions > 0:
            suggestions += f"- **Code Changes:** +{total_additions} additions, -{total_deletions} deletions\n"
        
        return suggestions


# Global tool instances
_repositories_tool = GitHubRepositoriesTool()
_repository_tool = GitHubRepositoryTool()
_issues_tool = GitHubIssuesTool()
_pull_requests_tool = GitHubPullRequestsTool()


def get_github_repositories_tool() -> GitHubRepositoriesTool:
    """Get the global GitHub repositories tool instance."""
    return _repositories_tool


def get_github_repository_tool() -> GitHubRepositoryTool:
    """Get the global GitHub repository tool instance."""
    return _repository_tool


def get_github_issues_tool() -> GitHubIssuesTool:
    """Get the global GitHub issues tool instance."""
    return _issues_tool


def get_github_pull_requests_tool() -> GitHubPullRequestsTool:
    """Get the global GitHub pull requests tool instance."""
    return _pull_requests_tool


def get_github_tools() -> List[Tool]:
    """Get all GitHub tool definitions."""
    config = get_config()
    if config.github is None:
        return []
    
    return [
        _repositories_tool.get_tool_definition(),
        _repository_tool.get_tool_definition(),
        _issues_tool.get_tool_definition(),
        _pull_requests_tool.get_tool_definition()
    ]


async def execute_github_repositories(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the github_repositories tool."""
    return await _repositories_tool.execute(arguments)


async def execute_github_repository(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the github_repository tool."""
    return await _repository_tool.execute(arguments)


async def execute_github_issues(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the github_issues tool."""
    return await _issues_tool.execute(arguments)


async def execute_github_pull_requests(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the github_pull_requests tool."""
    return await _pull_requests_tool.execute(arguments)
