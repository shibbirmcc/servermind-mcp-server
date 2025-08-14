"""Issue reader tool for MCP - reads GitHub and JIRA issues using CLI or MCP servers."""

import json
import subprocess
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog
from mcp.types import Tool, TextContent

logger = structlog.get_logger(__name__)


class IssueReaderTool:
    """MCP tool for reading GitHub and JIRA issues with CLI-first approach."""
    
    def __init__(self):
        """Initialize the issue reader tool."""
        pass
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for issue_reader."""
        return Tool(
            name="issue_reader",
            description="Read GitHub or JIRA issues using CLI (preferred) or MCP servers (fallback). "
                       "Supports parsing from automated_issue_creation output or direct issue references.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_reference": {
                        "type": "string",
                        "description": "Direct issue reference (e.g., 'owner/repo#123' for GitHub, 'PROJECT-456' for JIRA)"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Explicit platform selection",
                        "enum": ["github", "jira", "auto"],
                        "default": "auto"
                    },
                    "previous_output": {
                        "type": "string",
                        "description": "JSON output from automated_issue_creation to extract issue info"
                    },
                    "github_repo": {
                        "type": "string",
                        "description": "GitHub repository in format 'owner/repo' (if not in issue_reference)"
                    },
                    "jira_project": {
                        "type": "string",
                        "description": "JIRA project key (if not in issue_reference)"
                    },
                    "issue_number": {
                        "type": "string",
                        "description": "Issue number/key (if not in issue_reference)"
                    }
                },
                "title": "issue_readerArguments"
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the issue reader tool."""
        try:
            logger.info("Starting issue reader", arguments=arguments)
            
            # Parse input arguments
            issue_info = self._parse_arguments(arguments)
            
            if not issue_info:
                return [TextContent(
                    type="text",
                    text="❌ **Invalid Input**\n\n"
                         "Could not determine which issue to read. Please provide either:\n"
                         "- `issue_reference` (e.g., 'owner/repo#123' or 'PROJECT-456')\n"
                         "- `previous_output` from automated_issue_creation\n"
                         "- `platform` + `github_repo`/`jira_project` + `issue_number`"
                )]
            
            # Handle multiple tickets
            if issue_info.get("multi_ticket"):
                return await self._process_multiple_tickets(issue_info["tickets"])
            
            # Handle single ticket (original logic)
            result = await self._process_single_ticket(issue_info)
            
            # Format and return results
            return self._format_results(result)
            
        except Exception as e:
            logger.error("Error in issue reader", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Issue Reader Failed**\n\n"
                     f"An error occurred while reading the issue: {e}\n\n"
                     f"Please check your parameters and try again."
            )]
    
    async def _process_multiple_tickets(self, tickets: List[Dict[str, Any]]) -> List[TextContent]:
        """Process multiple tickets and return structured list."""
        try:
            results = []
            successful_tickets = []
            failed_tickets = []
            
            logger.info(f"Processing {len(tickets)} tickets")
            
            for i, ticket_info in enumerate(tickets, 1):
                logger.info(f"Processing ticket {i}/{len(tickets)}", ticket=ticket_info.get("ticket_reference"))
                
                try:
                    result = await self._process_single_ticket(ticket_info)
                    
                    if result["success"]:
                        issue = result["issue"]
                        ticket_data = {
                            "ticket_number": ticket_info.get("ticket_reference", issue["id"]),
                            "platform": result["platform"],
                            "title": issue["title"],
                            "description": issue["description"],
                            "status": issue["status"],
                            "labels": issue["labels"],
                            "assignees": issue["assignees"],
                            "metadata": issue["metadata"]
                        }
                        successful_tickets.append(ticket_data)
                    else:
                        failed_tickets.append({
                            "ticket_number": ticket_info.get("ticket_reference", "unknown"),
                            "platform": result.get("platform", "unknown"),
                            "error": result.get("error", "Unknown error"),
                            "setup_instructions": result.get("setup_instructions")
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing ticket {i}", error=str(e), ticket=ticket_info)
                    failed_tickets.append({
                        "ticket_number": ticket_info.get("ticket_reference", "unknown"),
                        "platform": ticket_info.get("platform", "unknown"),
                        "error": f"Processing error: {str(e)}"
                    })
            
            # Format multi-ticket results
            return self._format_multi_ticket_results(successful_tickets, failed_tickets)
            
        except Exception as e:
            logger.error("Error processing multiple tickets", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Multi-Ticket Processing Failed**\n\n"
                     f"An error occurred while processing multiple tickets: {e}"
            )]
    
    async def _process_single_ticket(self, issue_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single ticket and return result."""
        # Try to read the issue based on platform
        if issue_info["platform"] == "github":
            return await self._read_github_issue(
                issue_info["repo"], 
                issue_info["issue_id"]
            )
        elif issue_info["platform"] == "jira":
            return await self._read_jira_issue(
                issue_info["project"], 
                issue_info["issue_id"]
            )
        else:
            # Auto-detect: try JIRA first, then GitHub
            if issue_info.get("project"):
                result = await self._read_jira_issue(
                    issue_info["project"], 
                    issue_info["issue_id"]
                )
                if not result["success"]:
                    # Try GitHub if JIRA failed and we have repo info
                    if issue_info.get("repo"):
                        result = await self._read_github_issue(
                            issue_info["repo"], 
                            issue_info["issue_id"]
                        )
                return result
            elif issue_info.get("repo"):
                return await self._read_github_issue(
                    issue_info["repo"], 
                    issue_info["issue_id"]
                )
            else:
                return {
                    "success": False,
                    "error": "Could not determine platform",
                    "platform": "unknown"
                }
    
    def _parse_arguments(self, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse and normalize input arguments."""
        issue_reference = arguments.get("issue_reference")
        platform = arguments.get("platform", "auto")
        previous_output = arguments.get("previous_output")
        github_repo = arguments.get("github_repo")
        jira_project = arguments.get("jira_project")
        issue_number = arguments.get("issue_number")
        
        # Parse from previous_output if provided
        if previous_output:
            parsed_info = self._parse_previous_output(previous_output)
            if parsed_info:
                return parsed_info
        
        # Parse from issue_reference if provided
        if issue_reference:
            parsed_info = self._parse_issue_reference(issue_reference)
            if parsed_info:
                return parsed_info
        
        # Parse from individual parameters
        if platform == "github" and github_repo and issue_number:
            return {
                "platform": "github",
                "repo": github_repo,
                "issue_id": issue_number
            }
        elif platform == "jira" and jira_project and issue_number:
            return {
                "platform": "jira",
                "project": jira_project,
                "issue_id": issue_number
            }
        elif platform == "auto":
            # Auto-detect based on available info
            info = {"platform": "auto", "issue_id": issue_number}
            if github_repo:
                info["repo"] = github_repo
            if jira_project:
                info["project"] = jira_project
            if info.get("repo") or info.get("project"):
                return info
        
        return None
    
    def _parse_previous_output(self, previous_output: str) -> Optional[Dict[str, Any]]:
        """Parse previous automated_issue_creation output to extract multiple ticket info."""
        try:
            import re
            tickets = []
            
            # Try to parse as JSON first (list of tickets)
            if previous_output.strip().startswith('[') or previous_output.strip().startswith('{'):
                try:
                    data = json.loads(previous_output)
                    if isinstance(data, list):
                        # Handle list of tickets
                        for ticket in data:
                            parsed_ticket = self._parse_ticket_object(ticket)
                            if parsed_ticket:
                                tickets.append(parsed_ticket)
                    elif isinstance(data, dict):
                        # Handle single ticket object
                        parsed_ticket = self._parse_ticket_object(data)
                        if parsed_ticket:
                            tickets.append(parsed_ticket)
                except json.JSONDecodeError:
                    pass
            
            # If no JSON tickets found, parse text output for issue URLs and references
            if not tickets:
                lines = previous_output.split('\n')
                for line in lines:
                    line = line.strip()
                    
                    # Look for GitHub issue URLs
                    if 'github.com' in line and '/issues/' in line:
                        match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', line)
                        if match:
                            tickets.append({
                                "platform": "github",
                                "repo": match.group(1),
                                "issue_id": match.group(2),
                                "ticket_reference": f"{match.group(1)}#{match.group(2)}"
                            })
                    
                    # Look for JIRA issue keys
                    elif re.search(r'[A-Z]+-\d+', line):
                        match = re.search(r'([A-Z]+-\d+)', line)
                        if match:
                            issue_key = match.group(1)
                            project = issue_key.split('-')[0]
                            tickets.append({
                                "platform": "jira",
                                "project": project,
                                "issue_id": issue_key,
                                "ticket_reference": issue_key
                            })
            
            # Return multi-ticket structure if we found multiple tickets
            if len(tickets) > 1:
                return {
                    "multi_ticket": True,
                    "tickets": tickets
                }
            elif len(tickets) == 1:
                # Single ticket - return in the original format for backward compatibility
                return tickets[0]
            
        except Exception as e:
            logger.warning("Failed to parse previous output", error=str(e))
        
        return None
    
    def _parse_ticket_object(self, ticket_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single ticket object from JSON structure."""
        try:
            # Look for common ticket fields
            ticket_number = ticket_obj.get("ticket_number") or ticket_obj.get("issue_id") or ticket_obj.get("id")
            platform = ticket_obj.get("platform", "").lower()
            
            if not ticket_number:
                return None
            
            # Parse GitHub format
            if platform == "github" or "#" in str(ticket_number):
                if "#" in str(ticket_number):
                    repo, issue_num = str(ticket_number).split("#", 1)
                    return {
                        "platform": "github",
                        "repo": repo,
                        "issue_id": issue_num,
                        "ticket_reference": ticket_number
                    }
                elif ticket_obj.get("repo"):
                    return {
                        "platform": "github",
                        "repo": ticket_obj["repo"],
                        "issue_id": str(ticket_number),
                        "ticket_reference": f"{ticket_obj['repo']}#{ticket_number}"
                    }
            
            # Parse JIRA format
            elif platform == "jira" or re.match(r'^[A-Z]+-\d+$', str(ticket_number)):
                if re.match(r'^[A-Z]+-\d+$', str(ticket_number)):
                    project = str(ticket_number).split('-')[0]
                    return {
                        "platform": "jira",
                        "project": project,
                        "issue_id": str(ticket_number),
                        "ticket_reference": str(ticket_number)
                    }
            
            return None
            
        except Exception as e:
            logger.warning("Failed to parse ticket object", error=str(e), ticket=ticket_obj)
            return None
    
    def _parse_issue_reference(self, issue_reference: str) -> Optional[Dict[str, Any]]:
        """Parse issue reference string."""
        import re
        
        # GitHub format: owner/repo#123
        github_match = re.match(r'^([^/]+/[^#]+)#(\d+)$', issue_reference)
        if github_match:
            return {
                "platform": "github",
                "repo": github_match.group(1),
                "issue_id": github_match.group(2)
            }
        
        # JIRA format: PROJECT-123
        jira_match = re.match(r'^([A-Z]+-\d+)$', issue_reference)
        if jira_match:
            issue_key = jira_match.group(1)
            project = issue_key.split('-')[0]
            return {
                "platform": "jira",
                "project": project,
                "issue_id": issue_key
            }
        
        return None
    
    async def _read_github_issue(self, repo: str, issue_number: str) -> Dict[str, Any]:
        """Read GitHub issue using CLI first, then MCP fallback."""
        logger.info("Reading GitHub issue", repo=repo, issue=issue_number)
        
        # Try GitHub CLI first
        cli_result = await self._try_github_cli(repo, issue_number)
        if cli_result["success"]:
            return cli_result
        
        # Try MCP server fallback
        mcp_result = await self._try_github_mcp(repo, issue_number)
        if mcp_result["success"]:
            return mcp_result
        
        # Both failed - return setup instructions
        return {
            "success": False,
            "platform": "github",
            "method": "failed",
            "error": "Both CLI and MCP methods failed",
            "setup_instructions": self._get_github_setup_instructions(cli_result.get("cli_error"))
        }
    
    async def _read_jira_issue(self, project: str, issue_key: str) -> Dict[str, Any]:
        """Read JIRA issue using CLI first, then MCP fallback."""
        logger.info("Reading JIRA issue", project=project, issue=issue_key)
        
        # Try JIRA CLI first
        cli_result = await self._try_jira_cli(project, issue_key)
        if cli_result["success"]:
            return cli_result
        
        # Try MCP server fallback
        mcp_result = await self._try_jira_mcp(project, issue_key)
        if mcp_result["success"]:
            return mcp_result
        
        # Both failed - return setup instructions
        return {
            "success": False,
            "platform": "jira",
            "method": "failed",
            "error": "Both CLI and MCP methods failed",
            "setup_instructions": self._get_jira_setup_instructions(cli_result.get("cli_error"))
        }
    
    async def _try_github_cli(self, repo: str, issue_number: str) -> Dict[str, Any]:
        """Try to read GitHub issue using CLI."""
        try:
            # Check if gh CLI is available and authenticated
            auth_check = await asyncio.create_subprocess_exec(
                'gh', 'auth', 'status',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await auth_check.communicate()
            
            if auth_check.returncode != 0:
                return {
                    "success": False,
                    "cli_error": "not_authenticated",
                    "error": "GitHub CLI not authenticated"
                }
            
            # Execute gh issue view command
            process = await asyncio.create_subprocess_exec(
                'gh', 'issue', 'view', issue_number,
                '--repo', repo,
                '--json', 'title,body,state,labels,assignees,comments,createdAt,updatedAt,url',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Parse JSON response
                issue_data = json.loads(stdout.decode())
                return {
                    "success": True,
                    "platform": "github",
                    "method": "cli",
                    "issue": self._format_github_issue(issue_data)
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "cli_error": "command_failed",
                    "error": f"GitHub CLI command failed: {error_msg}"
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "cli_error": "not_installed",
                "error": "GitHub CLI not installed"
            }
        except Exception as e:
            return {
                "success": False,
                "cli_error": "unknown",
                "error": f"GitHub CLI error: {str(e)}"
            }
    
    async def _try_jira_cli(self, project: str, issue_key: str) -> Dict[str, Any]:
        """Try to read JIRA issue using CLI."""
        try:
            # Try jira CLI command
            process = await asyncio.create_subprocess_exec(
                'jira', 'issue', 'view', issue_key,
                '--output', 'json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Parse JSON response
                issue_data = json.loads(stdout.decode())
                return {
                    "success": True,
                    "platform": "jira",
                    "method": "cli",
                    "issue": self._format_jira_issue(issue_data)
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "cli_error": "command_failed",
                    "error": f"JIRA CLI command failed: {error_msg}"
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "cli_error": "not_installed",
                "error": "JIRA CLI not installed"
            }
        except Exception as e:
            return {
                "success": False,
                "cli_error": "unknown",
                "error": f"JIRA CLI error: {str(e)}"
            }
    
    async def _try_github_mcp(self, repo: str, issue_number: str) -> Dict[str, Any]:
        """Try to read GitHub issue using MCP server."""
        try:
            # This would use the use_mcp_tool functionality
            # For now, return a placeholder indicating the integration point
            logger.info("Would attempt GitHub MCP server", repo=repo, issue=issue_number)
            
            # TODO: Implement actual MCP server call
            # result = await use_mcp_tool('github-server', 'get_issue', {
            #     'owner': repo.split('/')[0],
            #     'repo': repo.split('/')[1],
            #     'issue_number': int(issue_number)
            # })
            
            return {
                "success": False,
                "error": "GitHub MCP server integration not yet implemented"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"GitHub MCP server error: {str(e)}"
            }
    
    async def _try_jira_mcp(self, project: str, issue_key: str) -> Dict[str, Any]:
        """Try to read JIRA issue using MCP server."""
        try:
            # This would use the use_mcp_tool functionality
            # For now, return a placeholder indicating the integration point
            logger.info("Would attempt JIRA MCP server", project=project, issue=issue_key)
            
            # TODO: Implement actual MCP server call
            # result = await use_mcp_tool('atlassian-server', 'get_issue', {
            #     'issue_key': issue_key
            # })
            
            return {
                "success": False,
                "error": "JIRA MCP server integration not yet implemented"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"JIRA MCP server error: {str(e)}"
            }
    
    def _format_github_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format GitHub issue data into standard format."""
        return {
            "id": issue_data.get("number", "unknown"),
            "title": issue_data.get("title", ""),
            "description": issue_data.get("body", ""),
            "status": issue_data.get("state", "unknown"),
            "labels": [label.get("name", "") for label in issue_data.get("labels", [])],
            "assignees": [assignee.get("login", "") for assignee in issue_data.get("assignees", [])],
            "comments": self._format_github_comments(issue_data.get("comments", [])),
            "metadata": {
                "created": issue_data.get("createdAt", ""),
                "updated": issue_data.get("updatedAt", ""),
                "url": issue_data.get("url", "")
            }
        }
    
    def _format_jira_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format JIRA issue data into standard format."""
        fields = issue_data.get("fields", {})
        
        return {
            "id": issue_data.get("key", "unknown"),
            "title": fields.get("summary", ""),
            "description": fields.get("description", ""),
            "status": fields.get("status", {}).get("name", "unknown"),
            "labels": fields.get("labels", []),
            "assignees": [fields.get("assignee", {}).get("displayName", "")] if fields.get("assignee") else [],
            "comments": self._format_jira_comments(fields.get("comment", {}).get("comments", [])),
            "metadata": {
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
                "url": f"{issue_data.get('self', '').replace('/rest/api/2/issue/', '/browse/')}"
            }
        }
    
    def _format_github_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format GitHub comments."""
        formatted_comments = []
        for comment in comments:
            formatted_comments.append({
                "author": comment.get("user", {}).get("login", "unknown"),
                "body": comment.get("body", ""),
                "created": comment.get("createdAt", ""),
                "updated": comment.get("updatedAt", "")
            })
        return formatted_comments
    
    def _format_jira_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format JIRA comments."""
        formatted_comments = []
        for comment in comments:
            formatted_comments.append({
                "author": comment.get("author", {}).get("displayName", "unknown"),
                "body": comment.get("body", ""),
                "created": comment.get("created", ""),
                "updated": comment.get("updated", "")
            })
        return formatted_comments
    
    def _get_github_setup_instructions(self, cli_error: Optional[str]) -> str:
        """Get GitHub setup instructions based on error type."""
        if cli_error == "not_installed":
            return """## 🔧 GitHub CLI Setup Required

The GitHub CLI is not installed. Please install it:

**macOS:**
```bash
brew install gh
```

**Ubuntu/Debian:**
```bash
sudo apt install gh
```

**Windows:**
```bash
winget install GitHub.cli
```

**After installation, authenticate:**
```bash
gh auth login
```

**Alternative: Configure GitHub MCP Server**
If you prefer using an MCP server instead of CLI:
1. Install the GitHub MCP server
2. Add it to your MCP configuration
3. Provide GitHub API token

For more details: https://docs.github.com/en/github-cli/github-cli/quickstart
"""
        
        elif cli_error == "not_authenticated":
            return """## 🔐 GitHub Authentication Required

The GitHub CLI is installed but not authenticated. Please run:

```bash
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

**Alternative: Configure GitHub MCP Server**
If you prefer using an MCP server instead of CLI:
1. Install the GitHub MCP server
2. Add it to your MCP configuration  
3. Provide GitHub API token
"""
        
        else:
            return """## ⚠️ GitHub Access Issue

There was an issue accessing GitHub. Please check:

1. **GitHub CLI Setup:**
   ```bash
   gh auth status
   gh auth login  # if not authenticated
   ```

2. **Repository Access:**
   - Ensure you have access to the repository
   - Check if the issue number exists
   - Verify repository name format (owner/repo)

3. **Alternative: GitHub MCP Server**
   - Install and configure GitHub MCP server
   - Provide valid GitHub API token

For more help: https://docs.github.com/en/github-cli/github-cli/quickstart
"""
    
    def _get_jira_setup_instructions(self, cli_error: Optional[str]) -> str:
        """Get JIRA setup instructions based on error type."""
        if cli_error == "not_installed":
            return """## 🔧 JIRA CLI Setup Required

A JIRA CLI is not installed. Please install one:

**Option 1: Atlassian CLI (Recommended)**
```bash
npm install -g @atlassian/cli
```

**Option 2: jira-cli (Python)**
```bash
pip install jira-cli
```

**After installation, configure:**
```bash
# For Atlassian CLI
atlassian config

# For jira-cli
jira config set --url https://your-domain.atlassian.net --username your-email@company.com --token your-api-token
```

**Alternative: Configure Atlassian MCP Server**
If you prefer using an MCP server instead of CLI:
1. Install the Atlassian MCP server
2. Add it to your MCP configuration
3. Provide JIRA API credentials

For API token: https://id.atlassian.com/manage-profile/security/api-tokens
"""
        
        else:
            return """## ⚠️ JIRA Access Issue

There was an issue accessing JIRA. Please check:

1. **JIRA CLI Configuration:**
   ```bash
   # Check current config
   jira config list
   
   # Reconfigure if needed
   jira config set --url https://your-domain.atlassian.net --username your-email --token your-api-token
   ```

2. **Issue Access:**
   - Ensure you have access to the JIRA project
   - Check if the issue key exists and is correct format (PROJECT-123)
   - Verify your permissions

3. **Alternative: Atlassian MCP Server**
   - Install and configure Atlassian MCP server
   - Provide valid JIRA API credentials

For API token: https://id.atlassian.com/manage-profile/security/api-tokens
"""
    
    def _format_multi_ticket_results(self, successful_tickets: List[Dict[str, Any]], failed_tickets: List[Dict[str, Any]]) -> List[TextContent]:
        """Format multi-ticket results as structured list."""
        try:
            # Create the structured JSON output
            result_data = {
                "tickets": successful_tickets,
                "summary": {
                    "total_tickets": len(successful_tickets) + len(failed_tickets),
                    "successful": len(successful_tickets),
                    "failed": len(failed_tickets)
                }
            }
            
            # Add failed tickets info if any
            if failed_tickets:
                result_data["failed_tickets"] = failed_tickets
            
            # Create human-readable summary
            summary_text = f"📋 **Multi-Ticket Issue Reader Results**\n\n"
            summary_text += f"**Summary:**\n"
            summary_text += f"- Total tickets processed: {result_data['summary']['total_tickets']}\n"
            summary_text += f"- Successfully retrieved: {result_data['summary']['successful']}\n"
            summary_text += f"- Failed to retrieve: {result_data['summary']['failed']}\n\n"
            
            # Show successful tickets
            if successful_tickets:
                summary_text += f"## ✅ Successfully Retrieved Tickets ({len(successful_tickets)})\n\n"
                for i, ticket in enumerate(successful_tickets, 1):
                    summary_text += f"**{i}. {ticket['ticket_number']}** ({ticket['platform'].title()})\n"
                    summary_text += f"   - **Title:** {ticket['title']}\n"
                    summary_text += f"   - **Status:** {ticket['status']}\n"
                    if ticket['assignees']:
                        summary_text += f"   - **Assignees:** {', '.join(ticket['assignees'])}\n"
                    summary_text += f"   - **Description:** {ticket['description'][:100]}{'...' if len(ticket['description']) > 100 else ''}\n\n"
            
            # Show failed tickets
            if failed_tickets:
                summary_text += f"## ❌ Failed to Retrieve ({len(failed_tickets)})\n\n"
                for i, ticket in enumerate(failed_tickets, 1):
                    summary_text += f"**{i}. {ticket['ticket_number']}** ({ticket['platform'].title()})\n"
                    summary_text += f"   - **Error:** {ticket['error']}\n"
                    if ticket.get('setup_instructions'):
                        summary_text += f"   - Setup required (see details below)\n"
                    summary_text += "\n"
                
                # Add setup instructions for failed tickets
                setup_needed = [t for t in failed_tickets if t.get('setup_instructions')]
                if setup_needed:
                    summary_text += f"## 🔧 Setup Instructions for Failed Tickets\n\n"
                    for ticket in setup_needed:
                        summary_text += f"### {ticket['ticket_number']} ({ticket['platform'].title()})\n"
                        summary_text += f"{ticket['setup_instructions']}\n\n"
            
            # Add JSON data section
            summary_text += f"---\n\n"
            summary_text += f"## 📊 Structured Data (JSON)\n\n"
            summary_text += f"```json\n{json.dumps(result_data, indent=2)}\n```\n\n"
            summary_text += f"*Use the JSON data above for programmatic processing of ticket information.*"
            
            return [TextContent(type="text", text=summary_text)]
            
        except Exception as e:
            logger.error("Error formatting multi-ticket results", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Error Formatting Results**\n\n"
                     f"Successfully processed {len(successful_tickets)} tickets, "
                     f"but failed to format results: {e}"
            )]
    
    def _format_results(self, result: Dict[str, Any]) -> List[TextContent]:
        """Format the final results."""
        if result["success"]:
            issue = result["issue"]
            platform = result["platform"].title()
            method = result["method"].upper()
            
            result_text = f"✅ **{platform} Issue Retrieved Successfully** ({method})\n\n"
            
            # Issue details
            result_text += f"## 📋 Issue Details\n\n"
            result_text += f"**ID:** {issue['id']}\n"
            result_text += f"**Title:** {issue['title']}\n"
            result_text += f"**Status:** {issue['status']}\n"
            
            if issue['labels']:
                result_text += f"**Labels:** {', '.join(issue['labels'])}\n"
            
            if issue['assignees']:
                result_text += f"**Assignees:** {', '.join(issue['assignees'])}\n"
            
            result_text += f"**Created:** {issue['metadata']['created']}\n"
            result_text += f"**Updated:** {issue['metadata']['updated']}\n"
            
            if issue['metadata']['url']:
                result_text += f"**URL:** {issue['metadata']['url']}\n"
            
            result_text += "\n"
            
            # Description
            if issue['description']:
                result_text += f"## 📝 Description\n\n"
                # Truncate very long descriptions
                description = issue['description']
                if len(description) > 1000:
                    description = description[:1000] + "...\n\n*[Description truncated - see full issue for complete content]*"
                result_text += f"{description}\n\n"
            
            # Comments
            if issue['comments']:
                result_text += f"## 💬 Comments ({len(issue['comments'])})\n\n"
                for i, comment in enumerate(issue['comments'][:3], 1):  # Show first 3 comments
                    result_text += f"**Comment {i}** by {comment['author']} ({comment['created']}):\n"
                    comment_body = comment['body']
                    if len(comment_body) > 300:
                        comment_body = comment_body[:300] + "..."
                    result_text += f"{comment_body}\n\n"
                
                if len(issue['comments']) > 3:
                    result_text += f"... and {len(issue['comments']) - 3} more comments.\n\n"
            
            result_text += "---\n"
            result_text += f"*Issue retrieved using {platform} {method}*"
            
            return [TextContent(type="text", text=result_text)]
        
        else:
            # Failed to retrieve issue
            platform = result.get("platform", "Unknown").title()
            error_text = f"❌ **Failed to Retrieve {platform} Issue**\n\n"
            error_text += f"**Error:** {result.get('error', 'Unknown error')}\n\n"
            
            if result.get("setup_instructions"):
                error_text += result["setup_instructions"]
            
            return [TextContent(type="text", text=error_text)]


# Global tool instance
_issue_reader_tool = IssueReaderTool()


def get_issue_reader_tool() -> IssueReaderTool:
    """Get the global issue reader tool instance."""
    return _issue_reader_tool


async def execute_issue_reader(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the issue reader tool."""
    return await _issue_reader_tool.execute(arguments)
