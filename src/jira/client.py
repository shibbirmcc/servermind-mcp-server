"""JIRA API client module."""

from jira import JIRA
from typing import Dict, Any, List, Optional
import structlog
from ..config import JiraConfig

logger = structlog.get_logger(__name__)


class JiraConnectionError(Exception):
    """Exception raised when connection to JIRA fails."""
    pass


class JiraAuthenticationError(Exception):
    """Exception raised when authentication to JIRA fails."""
    pass


class JiraOperationError(Exception):
    """Exception raised when JIRA operation fails."""
    pass


class JiraClient:
    """JIRA API client for connecting to JIRA instances."""
    
    def __init__(self, config: JiraConfig):
        """Initialize JIRA client.
        
        Args:
            config: JIRA configuration
        """
        self.config = config
        self._client: Optional[JIRA] = None
        self._connected = False
    
    def connect(self) -> None:
        """Connect to JIRA instance.
        
        Raises:
            JiraConnectionError: If connection fails
            JiraAuthenticationError: If authentication fails
        """
        if self._connected and self._client is not None:
            return
        
        logger.info("Connecting to JIRA", base_url=self.config.base_url)
        
        try:
            # Create JIRA client with basic authentication
            self._client = JIRA(
                server=self.config.base_url,
                basic_auth=(self.config.username, self.config.api_token),
                options={
                    'verify': self.config.verify_ssl,
                    'timeout': self.config.timeout
                }
            )
            
            # Test connection by getting server info
            server_info = self._client.server_info()
            logger.info("Connected to JIRA successfully", 
                       version=server_info.get('version'),
                       server_title=server_info.get('serverTitle'))
            
            self._connected = True
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'authentication' in error_msg or 'unauthorized' in error_msg or '401' in error_msg:
                raise JiraAuthenticationError(f"Authentication failed: {e}")
            else:
                raise JiraConnectionError(f"Connection failed: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from JIRA instance."""
        if self._client is not None:
            try:
                # JIRA client doesn't have explicit disconnect
                logger.info("Disconnected from JIRA")
            except Exception as e:
                logger.warning("Error during disconnect", error=str(e))
            finally:
                self._client = None
                self._connected = False
    
    def is_connected(self) -> bool:
        """Check if client is connected to JIRA.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected and self._client is not None
    
    def get_client(self) -> JIRA:
        """Get the JIRA client instance.
        
        Returns:
            JIRA: JIRA client instance
            
        Raises:
            JiraConnectionError: If not connected
        """
        if not self.is_connected():
            self.connect()
        
        if self._client is None:
            raise JiraConnectionError("Not connected to JIRA")
        
        return self._client
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to JIRA and return server info.
        
        Returns:
            Dict[str, Any]: Server information
            
        Raises:
            JiraConnectionError: If connection test fails
        """
        try:
            client = self.get_client()
            server_info = client.server_info()
            
            return {
                'connected': True,
                'version': server_info.get('version'),
                'server_title': server_info.get('serverTitle'),
                'base_url': server_info.get('baseUrl'),
                'build_number': server_info.get('buildNumber')
            }
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            raise JiraConnectionError(f"Connection test failed: {e}")
    
    def search_issues(self, jql: str, max_results: int = 50, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for issues using JQL.
        
        Args:
            jql: JQL query string
            max_results: Maximum number of results
            fields: List of fields to include
            
        Returns:
            List[Dict[str, Any]]: List of issues
            
        Raises:
            JiraOperationError: If search fails
        """
        try:
            client = self.get_client()
            
            # Default fields if none specified
            if fields is None:
                fields = ['key', 'summary', 'status', 'assignee', 'reporter', 'created', 'updated', 'priority', 'issuetype']
            
            issues = client.search_issues(jql, maxResults=max_results, fields=fields)
            
            result = []
            for issue in issues:
                issue_dict = {
                    'key': issue.key,
                    'id': issue.id,
                    'self': issue.self,
                    'fields': {}
                }
                
                # Extract fields safely
                for field in fields:
                    try:
                        if hasattr(issue.fields, field):
                            value = getattr(issue.fields, field)
                            if hasattr(value, 'name'):
                                issue_dict['fields'][field] = value.name
                            elif hasattr(value, 'displayName'):
                                issue_dict['fields'][field] = value.displayName
                            else:
                                issue_dict['fields'][field] = str(value) if value is not None else None
                        else:
                            issue_dict['fields'][field] = None
                    except Exception as e:
                        logger.warning(f"Error extracting field {field}", error=str(e))
                        issue_dict['fields'][field] = None
                
                result.append(issue_dict)
            
            logger.info("Issues searched successfully", count=len(result))
            return result
            
        except Exception as e:
            logger.error("Failed to search issues", jql=jql, error=str(e))
            raise JiraOperationError(f"Failed to search issues: {e}")
    
    def get_issue(self, issue_key: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific issue by key.
        
        Args:
            issue_key: Issue key (e.g., 'PROJ-123')
            fields: List of fields to include
            
        Returns:
            Dict[str, Any]: Issue details
            
        Raises:
            JiraOperationError: If getting issue fails
        """
        try:
            client = self.get_client()
            
            if fields is None:
                fields = ['key', 'summary', 'description', 'status', 'assignee', 'reporter', 'created', 'updated', 'priority', 'issuetype', 'components', 'labels']
            
            issue = client.issue(issue_key, fields=fields)
            
            issue_dict = {
                'key': issue.key,
                'id': issue.id,
                'self': issue.self,
                'fields': {}
            }
            
            # Extract fields safely
            for field in fields:
                try:
                    if hasattr(issue.fields, field):
                        value = getattr(issue.fields, field)
                        if hasattr(value, 'name'):
                            issue_dict['fields'][field] = value.name
                        elif hasattr(value, 'displayName'):
                            issue_dict['fields'][field] = value.displayName
                        elif isinstance(value, list):
                            issue_dict['fields'][field] = [str(item) for item in value]
                        else:
                            issue_dict['fields'][field] = str(value) if value is not None else None
                    else:
                        issue_dict['fields'][field] = None
                except Exception as e:
                    logger.warning(f"Error extracting field {field}", error=str(e))
                    issue_dict['fields'][field] = None
            
            logger.info("Issue retrieved successfully", key=issue_key)
            return issue_dict
            
        except Exception as e:
            logger.error("Failed to get issue", key=issue_key, error=str(e))
            raise JiraOperationError(f"Failed to get issue {issue_key}: {e}")
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """Get list of available projects.
        
        Returns:
            List[Dict[str, Any]]: List of projects
            
        Raises:
            JiraOperationError: If getting projects fails
        """
        try:
            client = self.get_client()
            projects = client.projects()
            
            result = []
            for project in projects:
                project_dict = {
                    'key': project.key,
                    'id': project.id,
                    'name': project.name,
                    'description': getattr(project, 'description', None),
                    'lead': getattr(project.lead, 'displayName', None) if hasattr(project, 'lead') and project.lead else None,
                    'project_type': getattr(project, 'projectTypeKey', None),
                    'url': getattr(project, 'self', None)
                }
                result.append(project_dict)
            
            logger.info("Projects retrieved successfully", count=len(result))
            return result
            
        except Exception as e:
            logger.error("Failed to get projects", error=str(e))
            raise JiraOperationError(f"Failed to get projects: {e}")
    
    def create_issue(self, project_key: str, summary: str, description: str = "", 
                    issue_type: str = "Task", **kwargs) -> Dict[str, Any]:
        """Create a new issue.
        
        Args:
            project_key: Project key
            summary: Issue summary
            description: Issue description
            issue_type: Issue type (Task, Bug, Story, etc.)
            **kwargs: Additional issue fields
            
        Returns:
            Dict[str, Any]: Created issue details
            
        Raises:
            JiraOperationError: If creating issue fails
        """
        try:
            client = self.get_client()
            
            issue_dict = {
                'project': {'key': project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type}
            }
            
            # Add additional fields
            issue_dict.update(kwargs)
            
            new_issue = client.create_issue(fields=issue_dict)
            
            result = {
                'key': new_issue.key,
                'id': new_issue.id,
                'self': new_issue.self,
                'url': f"{self.config.base_url}/browse/{new_issue.key}"
            }
            
            logger.info("Issue created successfully", key=new_issue.key)
            return result
            
        except Exception as e:
            logger.error("Failed to create issue", project=project_key, summary=summary, error=str(e))
            raise JiraOperationError(f"Failed to create issue: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
