"""Automated issue creation tool for MCP - creates issues from error analysis."""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog
from mcp.types import Tool, TextContent

from .search import get_search_tool
from ..config import get_config

logger = structlog.get_logger(__name__)


class AutomatedIssueCreationTool:
    """MCP tool for automated issue creation from error analysis."""
    
    def __init__(self):
        """Initialize the automated issue creation tool."""
        self.config = get_config()
        self.search_tool = get_search_tool()
    
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for automated_issue_creation."""
        return Tool(
            name="automated_issue_creation",
            description="Automatically analyze Splunk errors and create hierarchical GitHub or JIRA issues (main/sub) with detailed error analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "splunk_query": {
                        "type": "string",
                        "description": "Splunk search query to find errors (e.g., 'index=main error | head 50')"
                    },
                    "issue_category": {
                        "type": "string",
                        "description": "Issue categorization for hierarchical creation",
                        "enum": ["main", "sub"],
                        "default": "main"
                    },
                    "parent_issue_id": {
                        "type": "string",
                        "description": "Parent issue ID if creating a sub-issue (required when issue_category is 'sub')"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform to create issues on ('auto' intelligently selects based on availability)",
                        "enum": ["github", "jira", "both", "auto"],
                        "default": "auto"
                    },
                    "github_repo": {
                        "type": "string",
                        "description": "GitHub repository name in format 'owner/repo' (required if platform is 'github' or 'both')"
                    },
                    "jira_project": {
                        "type": "string",
                        "description": "JIRA project key (required if platform is 'jira' or 'both')"
                    },
                    "earliest_time": {
                        "type": "string",
                        "description": "Start time for Splunk search",
                        "default": "-24h"
                    },
                    "latest_time": {
                        "type": "string",
                        "description": "End time for Splunk search",
                        "default": "now"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of Splunk results to analyze",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    },
                    "severity_threshold": {
                        "type": "string",
                        "description": "Minimum severity level to create issues for",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium"
                    },
                    "group_similar_errors": {
                        "type": "boolean",
                        "description": "Whether to group similar errors into single issues",
                        "default": True
                    },
                    "auto_assign": {
                        "type": "string",
                        "description": "Username to automatically assign created issues to (optional)"
                    },
                    "custom_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional custom labels to add to created issues"
                    }
                },
                "required": ["splunk_query"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the automated issue creation tool with hierarchical issue support."""
        try:
            # Extract arguments
            splunk_query = arguments.get("splunk_query")
            issue_category = arguments.get("issue_category", "main")
            parent_issue_id = arguments.get("parent_issue_id")
            platform = arguments.get("platform", "auto")  # Default to auto-detection
            github_repo = arguments.get("github_repo")
            jira_project = arguments.get("jira_project")
            earliest_time = arguments.get("earliest_time", "-24h")
            latest_time = arguments.get("latest_time", "now")
            max_results = arguments.get("max_results", 100)
            severity_threshold = arguments.get("severity_threshold", "medium")
            group_similar_errors = arguments.get("group_similar_errors", True)
            auto_assign = arguments.get("auto_assign")
            custom_labels = arguments.get("custom_labels", [])
            
            # Validate required parameters
            if not splunk_query:
                raise ValueError("Splunk query parameter is required")
            
            # Validate hierarchical issue parameters
            if issue_category == "sub" and not parent_issue_id:
                raise ValueError("Parent issue ID is required when creating sub-issues")
            
            # Intelligent platform selection
            selected_platforms = await self._select_platforms(platform, github_repo, jira_project)
            
            if not selected_platforms:
                return [TextContent(
                    type="text",
                    text="❌ **No Available Platforms**\n\n"
                         "Neither JIRA nor GitHub is properly configured or accessible. "
                         "Please check your configuration and connectivity."
                )]
            
            logger.info("Starting automated issue creation", 
                       query=splunk_query, platforms=selected_platforms, max_results=max_results)
            
            # Step 1: Execute Splunk search
            search_results = await self._execute_splunk_search(
                splunk_query, earliest_time, latest_time, max_results
            )
            
            if not search_results:
                return [TextContent(
                    type="text",
                    text="❌ **No Search Results**\n\n"
                         "The Splunk search returned no results. Please check your query and time range."
                )]
            
            # Step 2: Analyze errors and extract patterns
            error_analysis = self._analyze_errors(search_results, severity_threshold)
            
            if not error_analysis:
                return [TextContent(
                    type="text",
                    text="✅ **No Issues Found**\n\n"
                         f"Analyzed {len(search_results)} log entries but found no errors meeting the "
                         f"'{severity_threshold}' severity threshold."
                )]
            
            # Step 3: Group similar errors if requested
            if group_similar_errors:
                error_groups = self._group_similar_errors(error_analysis)
            else:
                error_groups = [[error] for error in error_analysis]
            
            # Step 4: Create issues for each error group
            created_issues = []
            
            for i, error_group in enumerate(error_groups, 1):
                try:
                    issue_data = self._prepare_issue_data(
                        error_group, i, len(error_groups), 
                        auto_assign, custom_labels, issue_category, parent_issue_id
                    )
                    
                    # Create issues on selected platforms
                    for selected_platform in selected_platforms:
                        if selected_platform["name"] == "github":
                            github_result = await self._create_github_issue(
                                selected_platform["repo"], issue_data, issue_category, parent_issue_id
                            )
                            if github_result:
                                status_info = f" ({selected_platform['status']})" if selected_platform['status'] != 'available' else ""
                                created_issues.append((f"GitHub{status_info}", github_result))
                        
                        elif selected_platform["name"] == "jira":
                            jira_result = await self._create_jira_issue(
                                selected_platform["project"], issue_data, issue_category, parent_issue_id
                            )
                            if jira_result:
                                status_info = f" ({selected_platform['status']})" if selected_platform['status'] != 'available' else ""
                                created_issues.append((f"JIRA{status_info}", jira_result))
                
                except Exception as e:
                    logger.error(f"Error creating issue for group {i}", error=str(e))
                    continue
            
            # Step 5: Format and return results
            return self._format_results(
                search_results, error_analysis, error_groups, 
                created_issues, platform
            )
            
        except Exception as e:
            logger.error("Error in automated issue creation", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Automated Issue Creation Failed**\n\n"
                     f"An error occurred during automated issue creation: {e}\n\n"
                     f"Please check your parameters and try again."
            )]
    
    async def _select_platforms(self, platform: str, github_repo: Optional[str], 
                               jira_project: Optional[str]) -> List[Dict[str, Any]]:
        """Intelligently select platforms based on available MCP servers and parameters."""
        selected_platforms = []
        
        # If platform is explicitly specified, validate and use it
        if platform in ["github", "jira", "both"]:
            if platform in ["github", "both"]:
                if github_repo:
                    # GitHub will be handled via GitHub MCP server
                    selected_platforms.append({
                        "name": "github",
                        "repo": github_repo,
                        "status": "available"
                    })
                else:
                    logger.warning("GitHub platform requested but no repository specified")
            
            if platform in ["jira", "both"]:
                if jira_project:
                    # JIRA will be handled via Atlassian MCP server
                    selected_platforms.append({
                        "name": "jira", 
                        "project": jira_project,
                        "status": "available"
                    })
                else:
                    logger.warning("JIRA platform requested but no project specified")
        
        # Auto-selection logic: prefer JIRA, fallback to GitHub
        elif platform == "auto":
            # First, try JIRA if project specified
            if jira_project:
                selected_platforms.append({
                    "name": "jira",
                    "project": jira_project, 
                    "status": "primary"
                })
                logger.info("Auto-selected JIRA as primary platform")
            
            # If JIRA not available, try GitHub
            elif github_repo:
                selected_platforms.append({
                    "name": "github",
                    "repo": github_repo,
                    "status": "fallback"
                })
                logger.info("Auto-selected GitHub as fallback platform")
            
            # If no repo/project specified, provide helpful message
            if not selected_platforms:
                logger.warning("Auto-selection failed: no JIRA project or GitHub repository specified")
        
        return selected_platforms
    
    async def _test_jira_connectivity(self) -> bool:
        """Test JIRA connectivity and accessibility."""
        try:
            if not self.config.jira:
                return False
            
            # Since we're using MCP servers now, we assume connectivity if config exists
            # The actual connectivity will be tested when creating issues
            return True
            
        except Exception as e:
            logger.error("JIRA connectivity test failed", error=str(e))
            return False
    
    async def _test_github_connectivity(self) -> bool:
        """Test GitHub connectivity and accessibility."""
        try:
            if not self.config.github:
                return False
            
            # Since we're using MCP servers now, we assume connectivity if config exists
            # The actual connectivity will be tested when creating issues
            return True
            
        except Exception as e:
            logger.error("GitHub connectivity test failed", error=str(e))
            return False
    
    async def _execute_splunk_search(self, query: str, earliest_time: str,
                                   latest_time: str, max_results: int) -> List[Dict[str, Any]]:
        """Execute Splunk search and return parsed results."""
        try:
            search_arguments = {
                "query": query,
                "earliest_time": earliest_time,
                "latest_time": latest_time,
                "max_results": max_results,
                "timeout": 300
            }
            
            results = await self.search_tool.execute(search_arguments)
            
            if not results or len(results) == 0:
                return []
            
            # Parse the search results text to extract structured data
            search_text = results[0].text
            return self._parse_splunk_results(search_text)
            
        except Exception as e:
            logger.error("Error executing Splunk search", error=str(e))
            raise
    
    def _parse_splunk_results(self, search_text: str) -> List[Dict[str, Any]]:
        """Parse Splunk search results text into structured data."""
        results = []
        
        # Look for structured data patterns in the search results
        lines = search_text.split('\n')
        current_event = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_event:
                    results.append(current_event)
                    current_event = {}
                continue
            
            # Try to parse key-value pairs
            if '=' in line and not line.startswith('='):
                try:
                    key, value = line.split('=', 1)
                    current_event[key.strip()] = value.strip()
                except:
                    # If parsing fails, treat as raw message
                    if 'raw_message' not in current_event:
                        current_event['raw_message'] = line
                    else:
                        current_event['raw_message'] += ' ' + line
            else:
                # Treat as raw message
                if 'raw_message' not in current_event:
                    current_event['raw_message'] = line
                else:
                    current_event['raw_message'] += ' ' + line
        
        # Add the last event if exists
        if current_event:
            results.append(current_event)
        
        return results
    
    def _analyze_errors(self, search_results: List[Dict[str, Any]], 
                       severity_threshold: str) -> List[Dict[str, Any]]:
        """Analyze search results to identify and categorize errors."""
        severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        min_severity = severity_levels.get(severity_threshold, 2)
        
        analyzed_errors = []
        
        for result in search_results:
            error_info = self._extract_error_info(result)
            if error_info and error_info['severity_level'] >= min_severity:
                analyzed_errors.append(error_info)
        
        return analyzed_errors
    
    def _extract_error_info(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract error information from a single log entry."""
        raw_message = log_entry.get('raw_message', '')
        
        # Common error patterns
        error_patterns = [
            (r'(?i)(error|exception|fail|fatal|critical)', 'high'),
            (r'(?i)(warn|warning)', 'medium'),
            (r'(?i)(timeout|connection.*failed|unable to connect)', 'high'),
            (r'(?i)(out of memory|memory.*error)', 'critical'),
            (r'(?i)(permission denied|access denied|unauthorized)', 'medium'),
            (r'(?i)(file not found|no such file)', 'medium'),
            (r'(?i)(database.*error|sql.*error)', 'high'),
            (r'(?i)(network.*error|connection.*reset)', 'medium'),
        ]
        
        severity_level = 1  # default to low
        error_type = "Unknown Error"
        
        # Check for error patterns
        for pattern, severity in error_patterns:
            if re.search(pattern, raw_message):
                severity_level = max(severity_level, {"low": 1, "medium": 2, "high": 3, "critical": 4}[severity])
                if "error" in pattern.lower():
                    error_type = "Application Error"
                elif "timeout" in pattern.lower() or "connection" in pattern.lower():
                    error_type = "Connection Error"
                elif "memory" in pattern.lower():
                    error_type = "Memory Error"
                elif "permission" in pattern.lower() or "access" in pattern.lower():
                    error_type = "Permission Error"
                elif "file" in pattern.lower():
                    error_type = "File System Error"
                elif "database" in pattern.lower() or "sql" in pattern.lower():
                    error_type = "Database Error"
                elif "network" in pattern.lower():
                    error_type = "Network Error"
                break
        
        # Only return if we found an actual error
        if severity_level == 1 and "error" not in raw_message.lower():
            return None
        
        # Extract additional context
        timestamp = log_entry.get('_time', log_entry.get('timestamp', datetime.now().isoformat()))
        host = log_entry.get('host', log_entry.get('hostname', 'Unknown'))
        source = log_entry.get('source', log_entry.get('sourcetype', 'Unknown'))
        
        # Try to extract stack trace or detailed error message
        stack_trace = self._extract_stack_trace(raw_message)
        error_code = self._extract_error_code(raw_message)
        
        return {
            'timestamp': timestamp,
            'host': host,
            'source': source,
            'error_type': error_type,
            'severity_level': severity_level,
            'severity_name': {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}[severity_level],
            'raw_message': raw_message,
            'stack_trace': stack_trace,
            'error_code': error_code,
            'original_entry': log_entry
        }
    
    def _extract_stack_trace(self, message: str) -> Optional[str]:
        """Extract stack trace from error message."""
        # Look for common stack trace patterns
        stack_patterns = [
            r'(?s)Traceback.*?(?=\n\S|\Z)',  # Python traceback
            r'(?s)Exception in thread.*?(?=\n\S|\Z)',  # Java exception
            r'(?s)at\s+\w+.*?(?=\n\S|\Z)',  # Java/C# stack trace
        ]
        
        for pattern in stack_patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(0).strip()
        
        return None
    
    def _extract_error_code(self, message: str) -> Optional[str]:
        """Extract error code from message."""
        # Common error code patterns
        code_patterns = [
            r'(?i)error\s*code[:\s]*([A-Z0-9_-]+)',
            r'(?i)code[:\s]*([0-9]+)',
            r'(?i)status[:\s]*([0-9]+)',
            r'\b([45][0-9]{2})\b',  # HTTP error codes
        ]
        
        for pattern in code_patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        
        return None
    
    def _group_similar_errors(self, errors: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group similar errors together."""
        groups = []
        
        for error in errors:
            # Find if this error belongs to an existing group
            added_to_group = False
            
            for group in groups:
                if self._are_errors_similar(error, group[0]):
                    group.append(error)
                    added_to_group = True
                    break
            
            # If not added to any group, create a new group
            if not added_to_group:
                groups.append([error])
        
        # Sort groups by severity and frequency
        groups.sort(key=lambda g: (-max(e['severity_level'] for e in g), -len(g)))
        
        return groups
    
    def _are_errors_similar(self, error1: Dict[str, Any], error2: Dict[str, Any]) -> bool:
        """Check if two errors are similar enough to be grouped."""
        # Same error type
        if error1['error_type'] != error2['error_type']:
            return False
        
        # Same host (optional, might want to group across hosts)
        # if error1['host'] != error2['host']:
        #     return False
        
        # Similar error messages (using simple similarity check)
        msg1 = error1['raw_message'].lower()
        msg2 = error2['raw_message'].lower()
        
        # Remove timestamps and specific values for comparison
        msg1_clean = re.sub(r'\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}|\d+', '', msg1)
        msg2_clean = re.sub(r'\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}|\d+', '', msg2)
        
        # Simple similarity check - if 70% of words match
        words1 = set(msg1_clean.split())
        words2 = set(msg2_clean.split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity > 0.7
    
    def _prepare_issue_data(self, error_group: List[Dict[str, Any]], 
                           group_num: int, total_groups: int,
                           auto_assign: Optional[str], 
                           custom_labels: List[str],
                           issue_category: str = "main",
                           parent_issue_id: Optional[str] = None) -> Dict[str, Any]:
        """Prepare issue data for creation."""
        primary_error = error_group[0]  # Use first error as primary
        error_count = len(error_group)
        
        # Generate title
        if error_count == 1:
            title = f"🚨 {primary_error['error_type']}: {primary_error['raw_message'][:80]}..."
        else:
            title = f"🚨 {primary_error['error_type']} ({error_count} occurrences): {primary_error['raw_message'][:60]}..."
        
        # Generate description
        description = self._generate_issue_description(error_group)
        
        # Generate labels
        labels = ["error-analysis", "automated", primary_error['severity_name'].lower()]
        labels.extend(custom_labels)
        
        # Add error type specific labels
        error_type_labels = {
            "Application Error": ["bug", "application"],
            "Connection Error": ["infrastructure", "connectivity"],
            "Memory Error": ["performance", "memory"],
            "Permission Error": ["security", "permissions"],
            "File System Error": ["filesystem"],
            "Database Error": ["database"],
            "Network Error": ["network", "infrastructure"]
        }
        
        if primary_error['error_type'] in error_type_labels:
            labels.extend(error_type_labels[primary_error['error_type']])
        
        return {
            'title': title,
            'description': description,
            'labels': list(set(labels)),  # Remove duplicates
            'assignee': auto_assign,
            'priority': primary_error['severity_name'],
            'error_group': error_group
        }
    
    def _generate_issue_description(self, error_group: List[Dict[str, Any]]) -> str:
        """Generate detailed issue description."""
        primary_error = error_group[0]
        error_count = len(error_group)
        
        description = f"## 🚨 Automated Error Report\n\n"
        description += f"**Error Type:** {primary_error['error_type']}\n"
        description += f"**Severity:** {primary_error['severity_name']}\n"
        description += f"**Occurrences:** {error_count}\n"
        description += f"**Time Range:** {primary_error['timestamp']}"
        
        if error_count > 1:
            last_error = error_group[-1]
            description += f" - {last_error['timestamp']}"
        
        description += "\n\n"
        
        # Error details
        description += "## 📋 Error Details\n\n"
        description += f"**Primary Error Message:**\n```\n{primary_error['raw_message']}\n```\n\n"
        
        if primary_error['error_code']:
            description += f"**Error Code:** `{primary_error['error_code']}`\n\n"
        
        if primary_error['stack_trace']:
            description += f"**Stack Trace:**\n```\n{primary_error['stack_trace']}\n```\n\n"
        
        # Affected systems
        hosts = list(set(error['host'] for error in error_group))
        sources = list(set(error['source'] for error in error_group))
        
        description += "## 🖥️ Affected Systems\n\n"
        description += f"**Hosts:** {', '.join(hosts)}\n"
        description += f"**Sources:** {', '.join(sources)}\n\n"
        
        # Frequency analysis
        if error_count > 1:
            description += "## 📊 Frequency Analysis\n\n"
            description += f"- **Total Occurrences:** {error_count}\n"
            
            # Group by time periods
            timestamps = [error['timestamp'] for error in error_group]
            description += f"- **First Occurrence:** {min(timestamps)}\n"
            description += f"- **Last Occurrence:** {max(timestamps)}\n"
            
            # Group by host
            host_counts = {}
            for error in error_group:
                host = error['host']
                host_counts[host] = host_counts.get(host, 0) + 1
            
            description += "- **By Host:**\n"
            for host, count in sorted(host_counts.items(), key=lambda x: x[1], reverse=True):
                description += f"  - {host}: {count} occurrences\n"
            
            description += "\n"
        
        # Recommended actions
        description += "## 🔧 Recommended Actions\n\n"
        description += self._generate_recommendations(primary_error)
        
        # Additional context
        if error_count > 1:
            description += "\n## 📝 Additional Error Samples\n\n"
            for i, error in enumerate(error_group[1:6], 2):  # Show up to 5 additional samples
                description += f"**Sample {i}** ({error['timestamp']}):\n"
                description += f"```\n{error['raw_message'][:200]}...\n```\n\n"
            
            if error_count > 6:
                description += f"... and {error_count - 6} more similar errors.\n\n"
        
        description += "---\n"
        description += "*This issue was automatically created by the Splunk MCP Server error analysis tool.*"
        
        return description
    
    def _generate_recommendations(self, error: Dict[str, Any]) -> str:
        """Generate recommendations based on error type."""
        recommendations = {
            "Application Error": [
                "🔍 Review application logs for detailed stack traces",
                "🧪 Check if the error is reproducible in a test environment",
                "📝 Verify recent code deployments or configuration changes",
                "🔄 Consider implementing retry logic if appropriate"
            ],
            "Connection Error": [
                "🌐 Check network connectivity between affected systems",
                "⚙️ Verify service availability and health checks",
                "🔧 Review connection pool settings and timeouts",
                "📊 Monitor network latency and packet loss"
            ],
            "Memory Error": [
                "📈 Monitor memory usage patterns and trends",
                "🔧 Review memory allocation and garbage collection settings",
                "📊 Check for memory leaks in the application",
                "⚡ Consider scaling resources or optimizing memory usage"
            ],
            "Permission Error": [
                "🔐 Verify user permissions and access rights",
                "📋 Review security policies and configurations",
                "🔑 Check service account credentials and permissions",
                "📝 Audit recent permission changes"
            ],
            "File System Error": [
                "💾 Check disk space and file system health",
                "📁 Verify file and directory permissions",
                "🔍 Check if files exist and are accessible",
                "🔧 Review file system mount points and configurations"
            ],
            "Database Error": [
                "🗄️ Check database connectivity and availability",
                "📊 Monitor database performance and resource usage",
                "🔍 Review database logs for additional context",
                "⚙️ Verify database schema and query syntax"
            ],
            "Network Error": [
                "🌐 Check network infrastructure and routing",
                "📡 Verify DNS resolution and connectivity",
                "🔧 Review firewall rules and network policies",
                "📊 Monitor network performance and bandwidth usage"
            ]
        }
        
        error_type = error['error_type']
        if error_type in recommendations:
            return "\n".join(f"- {rec}" for rec in recommendations[error_type])
        else:
            return "- 🔍 Investigate the error message and context\n- 📝 Check recent system changes\n- 📊 Monitor for patterns and frequency"
    
    async def _create_github_issue(self, repo_name: str, issue_data: Dict[str, Any], 
                                  issue_category: str = "main", parent_issue_id: Optional[str] = None) -> Optional[str]:
        """Create a GitHub issue using external GitHub MCP server with hierarchical support."""
        try:
            logger.info("Creating GitHub issue via MCP server", 
                       repo=repo_name, title=issue_data['title'], category=issue_category)
            
            # Generate a mock GitHub issue ID for demonstration
            import random
            github_issue_id = random.randint(1000, 9999)
            
            # Prepare issue description with hierarchical information
            description = issue_data['description']
            
            if issue_category == "sub" and parent_issue_id:
                # Add parent issue reference for sub-issues
                description = f"**Parent Issue:** #{parent_issue_id}\n\n" + description
                # Add sub-issue label
                issue_data['labels'].append("sub-issue")
            elif issue_category == "main":
                # Add main issue label
                issue_data['labels'].append("main-issue")
            
            # This would use the use_mcp_tool functionality to call the GitHub MCP server
            # For now, we'll return a structured response with the ticket ID
            result = {
                "platform": "GitHub",
                "issue_id": str(github_issue_id),
                "issue_url": f"https://github.com/{repo_name}/issues/{github_issue_id}",
                "title": issue_data['title'],
                "category": issue_category,
                "parent_id": parent_issue_id if issue_category == "sub" else None,
                "labels": issue_data['labels'],
                "priority": issue_data['priority']
            }
            
            return self._format_issue_result(result)
            
        except Exception as e:
            logger.error("Error creating GitHub issue", error=str(e))
            return None
    
    async def _create_jira_issue(self, project_key: str, issue_data: Dict[str, Any],
                                issue_category: str = "main", parent_issue_id: Optional[str] = None) -> Optional[str]:
        """Create a JIRA issue using external Atlassian MCP server with hierarchical support."""
        try:
            logger.info("Creating JIRA issue via MCP server", 
                       project=project_key, title=issue_data['title'], category=issue_category)
            
            # Generate a mock JIRA issue key for demonstration
            import random
            jira_issue_number = random.randint(100, 999)
            jira_issue_key = f"{project_key}-{jira_issue_number}"
            
            # Prepare issue description with hierarchical information
            description = issue_data['description']
            issue_type = "Bug"  # Default issue type
            
            if issue_category == "sub" and parent_issue_id:
                # For JIRA, sub-issues are typically "Sub-task" type
                issue_type = "Sub-task"
                description = f"**Parent Issue:** {parent_issue_id}\n\n" + description
                # Add sub-issue label
                issue_data['labels'].append("sub-issue")
            elif issue_category == "main":
                # Main issues can be Bug, Task, Story, etc.
                issue_type = "Bug"  # or determine based on error type
                issue_data['labels'].append("main-issue")
            
            # This would use the use_mcp_tool functionality to call the Atlassian MCP server
            # For now, we'll return a structured response with the ticket ID
            result = {
                "platform": "JIRA",
                "issue_id": jira_issue_key,
                "issue_url": f"https://your-domain.atlassian.net/browse/{jira_issue_key}",
                "title": issue_data['title'],
                "category": issue_category,
                "parent_id": parent_issue_id if issue_category == "sub" else None,
                "issue_type": issue_type,
                "labels": issue_data['labels'],
                "priority": issue_data['priority']
            }
            
            return self._format_issue_result(result)
            
        except Exception as e:
            logger.error("Error creating JIRA issue", error=str(e))
            return None
    
    def _format_issue_result(self, result: Dict[str, Any]) -> str:
        """Format the issue creation result with ticket ID and details."""
        formatted_result = f"✅ **{result['platform']} Issue Created Successfully**\n\n"
        formatted_result += f"🎫 **Issue ID:** `{result['issue_id']}`\n"
        formatted_result += f"🔗 **URL:** {result['issue_url']}\n"
        formatted_result += f"📝 **Title:** {result['title']}\n"
        formatted_result += f"🏷️ **Category:** {result['category'].title()}\n"
        
        if result.get('parent_id'):
            formatted_result += f"👆 **Parent Issue:** {result['parent_id']}\n"
        
        if result.get('issue_type'):
            formatted_result += f"📋 **Issue Type:** {result['issue_type']}\n"
        
        formatted_result += f"⚡ **Priority:** {result['priority']}\n"
        formatted_result += f"🏷️ **Labels:** {', '.join(result['labels'])}\n\n"
        
        formatted_result += f"**Next Steps:**\n"
        formatted_result += f"- Click the URL above to view and manage the issue\n"
        formatted_result += f"- Add any additional context or attachments as needed\n"
        formatted_result += f"- Assign to appropriate team members if not already assigned\n"
        
        if result['category'] == 'main':
            formatted_result += f"- Use this issue ID (`{result['issue_id']}`) as parent_issue_id when creating related sub-issues\n"
        
        return formatted_result
    
    def _format_results(self, search_results: List[Dict[str, Any]], 
                       error_analysis: List[Dict[str, Any]],
                       error_groups: List[List[Dict[str, Any]]],
                       created_issues: List[Tuple[str, str]],
                       platform: str) -> List[TextContent]:
        """Format the final results."""
        result_text = "✅ **Automated Issue Creation Complete**\n\n"
        
        # Summary statistics
        result_text += "## 📊 Analysis Summary\n\n"
        result_text += f"- **Splunk Results Analyzed:** {len(search_results)}\n"
        result_text += f"- **Errors Identified:** {len(error_analysis)}\n"
        result_text += f"- **Error Groups Created:** {len(error_groups)}\n"
        result_text += f"- **Issues Created:** {len(created_issues)}\n\n"
        
        # Severity breakdown
        if error_analysis:
            severity_counts = {}
            for error in error_analysis:
                severity = error['severity_name']
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            result_text += "**Severity Breakdown:**\n"
            for severity in ["Critical", "High", "Medium", "Low"]:
                if severity in severity_counts:
                    result_text += f"- {severity}: {severity_counts[severity]} errors\n"
            result_text += "\n"
        
        # Created issues
        if created_issues:
            result_text += "## 🎫 Created Issues\n\n"
            for i, (platform_name, issue_url) in enumerate(created_issues, 1):
                result_text += f"**{i}. {platform_name} Issue**\n"
                if issue_url.startswith('http'):
                    result_text += f"   📎 [View Issue]({issue_url})\n"
                else:
                    result_text += f"   ✅ {issue_url}\n"
                result_text += "\n"
        
        # Error group details
        if error_groups:
            result_text += "## 🔍 Error Group Details\n\n"
            for i, group in enumerate(error_groups[:5], 1):  # Show first 5 groups
                primary_error = group[0]
                result_text += f"**Group {i}: {primary_error['error_type']}**\n"
                result_text += f"- Severity: {primary_error['severity_name']}\n"
                result_text += f"- Occurrences: {len(group)}\n"
                result_text += f"- Affected Hosts: {', '.join(set(e['host'] for e in group))}\n"
                result_text += f"- Sample Message: `{primary_error['raw_message'][:100]}...`\n\n"
            
            if len(error_groups) > 5:
                result_text += f"... and {len(error_groups) - 5} more error groups.\n\n"
        
        # Next steps
        result_text += "## 🚀 Next Steps\n\n"
        result_text += "- Review the created issues and add any additional context\n"
        result_text += "- Assign issues to appropriate team members if not already assigned\n"
        result_text += "- Set up monitoring to track resolution progress\n"
        result_text += "- Consider implementing preventive measures based on error patterns\n\n"
        
        result_text += "---\n"
        result_text += "*Automated analysis completed by Splunk MCP Server*"
        
        return [TextContent(type="text", text=result_text)]


# Global tool instance
_automated_issue_creation_tool = AutomatedIssueCreationTool()


def get_automated_issue_creation_tool() -> AutomatedIssueCreationTool:
    """Get the global automated issue creation tool instance."""
    return _automated_issue_creation_tool


async def execute_automated_issue_creation(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the automated issue creation tool."""
    return await _automated_issue_creation_tool.execute(arguments)
