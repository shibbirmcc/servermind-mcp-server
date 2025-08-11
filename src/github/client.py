"""GitHub API client module."""

from github import Github
from github.GithubException import GithubException
from typing import Dict, Any, List, Optional
import structlog
from ..config import GitHubConfig

logger = structlog.get_logger(__name__)


class GitHubConnectionError(Exception):
    """Exception raised when connection to GitHub fails."""
    pass


class GitHubAuthenticationError(Exception):
    """Exception raised when authentication to GitHub fails."""
    pass


class GitHubOperationError(Exception):
    """Exception raised when GitHub operation fails."""
    pass


class GitHubClient:
    """GitHub API client for connecting to GitHub instances."""
    
    def __init__(self, config: GitHubConfig):
        """Initialize GitHub client.
        
        Args:
            config: GitHub configuration
        """
        self.config = config
        self._client: Optional[Github] = None
        self._connected = False
    
    def connect(self) -> None:
        """Connect to GitHub instance.
        
        Raises:
            GitHubConnectionError: If connection fails
            GitHubAuthenticationError: If authentication fails
        """
        if self._connected and self._client is not None:
            return
        
        logger.info("Connecting to GitHub", api_url=self.config.api_url)
        
        try:
            # Create GitHub client with token authentication
            self._client = Github(
                auth=self.config.token,
                base_url=self.config.api_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            
            # Test connection by getting user info
            user = self._client.get_user()
            logger.info("Connected to GitHub successfully", 
                       login=user.login,
                       name=user.name)
            
            self._connected = True
            
        except GithubException as e:
            if e.status == 401:
                raise GitHubAuthenticationError(f"Authentication failed: {e}")
            else:
                raise GitHubConnectionError(f"Connection failed: {e}")
        except Exception as e:
            raise GitHubConnectionError(f"Connection failed: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from GitHub instance."""
        if self._client is not None:
            try:
                # GitHub client doesn't have explicit disconnect
                logger.info("Disconnected from GitHub")
            except Exception as e:
                logger.warning("Error during disconnect", error=str(e))
            finally:
                self._client = None
                self._connected = False
    
    def is_connected(self) -> bool:
        """Check if client is connected to GitHub.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected and self._client is not None
    
    def get_client(self) -> Github:
        """Get the GitHub client instance.
        
        Returns:
            Github: GitHub client instance
            
        Raises:
            GitHubConnectionError: If not connected
        """
        if not self.is_connected():
            self.connect()
        
        if self._client is None:
            raise GitHubConnectionError("Not connected to GitHub")
        
        return self._client
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to GitHub and return user info.
        
        Returns:
            Dict[str, Any]: User information
            
        Raises:
            GitHubConnectionError: If connection test fails
        """
        try:
            client = self.get_client()
            user = client.get_user()
            
            return {
                'connected': True,
                'login': user.login,
                'name': user.name,
                'email': user.email,
                'company': user.company,
                'location': user.location,
                'public_repos': user.public_repos,
                'followers': user.followers,
                'following': user.following
            }
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            raise GitHubConnectionError(f"Connection test failed: {e}")
    
    def get_repositories(self, user_or_org: Optional[str] = None, repo_type: str = "all", 
                        max_results: int = 30) -> List[Dict[str, Any]]:
        """Get list of repositories.
        
        Args:
            user_or_org: Username or organization name (None for authenticated user)
            repo_type: Repository type ('all', 'owner', 'public', 'private', 'member')
            max_results: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of repositories
            
        Raises:
            GitHubOperationError: If getting repositories fails
        """
        try:
            client = self.get_client()
            
            if user_or_org:
                try:
                    # Try as user first
                    user = client.get_user(user_or_org)
                    repos = user.get_repos(type=repo_type)
                except GithubException:
                    # Try as organization
                    org = client.get_organization(user_or_org)
                    repos = org.get_repos(type=repo_type)
            else:
                # Get authenticated user's repositories
                user = client.get_user()
                repos = user.get_repos(type=repo_type)
            
            result = []
            count = 0
            for repo in repos:
                if count >= max_results:
                    break
                
                repo_dict = {
                    'name': repo.name,
                    'full_name': repo.full_name,
                    'description': repo.description,
                    'private': repo.private,
                    'html_url': repo.html_url,
                    'clone_url': repo.clone_url,
                    'ssh_url': repo.ssh_url,
                    'language': repo.language,
                    'stargazers_count': repo.stargazers_count,
                    'watchers_count': repo.watchers_count,
                    'forks_count': repo.forks_count,
                    'open_issues_count': repo.open_issues_count,
                    'created_at': repo.created_at.isoformat() if repo.created_at else None,
                    'updated_at': repo.updated_at.isoformat() if repo.updated_at else None,
                    'pushed_at': repo.pushed_at.isoformat() if repo.pushed_at else None,
                    'default_branch': repo.default_branch
                }
                result.append(repo_dict)
                count += 1
            
            logger.info("Repositories retrieved successfully", count=len(result))
            return result
            
        except Exception as e:
            logger.error("Failed to get repositories", user_or_org=user_or_org, error=str(e))
            raise GitHubOperationError(f"Failed to get repositories: {e}")
    
    def get_repository(self, repo_name: str) -> Dict[str, Any]:
        """Get a specific repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo'
            
        Returns:
            Dict[str, Any]: Repository details
            
        Raises:
            GitHubOperationError: If getting repository fails
        """
        try:
            client = self.get_client()
            repo = client.get_repo(repo_name)
            
            repo_dict = {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description,
                'private': repo.private,
                'html_url': repo.html_url,
                'clone_url': repo.clone_url,
                'ssh_url': repo.ssh_url,
                'language': repo.language,
                'stargazers_count': repo.stargazers_count,
                'watchers_count': repo.watchers_count,
                'forks_count': repo.forks_count,
                'open_issues_count': repo.open_issues_count,
                'created_at': repo.created_at.isoformat() if repo.created_at else None,
                'updated_at': repo.updated_at.isoformat() if repo.updated_at else None,
                'pushed_at': repo.pushed_at.isoformat() if repo.pushed_at else None,
                'default_branch': repo.default_branch,
                'topics': repo.get_topics(),
                'license': repo.license.name if repo.license else None,
                'owner': {
                    'login': repo.owner.login,
                    'type': repo.owner.type,
                    'html_url': repo.owner.html_url
                }
            }
            
            logger.info("Repository retrieved successfully", repo=repo_name)
            return repo_dict
            
        except Exception as e:
            logger.error("Failed to get repository", repo=repo_name, error=str(e))
            raise GitHubOperationError(f"Failed to get repository {repo_name}: {e}")
    
    def get_issues(self, repo_name: str, state: str = "open", labels: Optional[List[str]] = None,
                  assignee: Optional[str] = None, max_results: int = 30) -> List[Dict[str, Any]]:
        """Get issues from a repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo'
            state: Issue state ('open', 'closed', 'all')
            labels: List of label names to filter by
            assignee: Username to filter by assignee
            max_results: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of issues
            
        Raises:
            GitHubOperationError: If getting issues fails
        """
        try:
            client = self.get_client()
            repo = client.get_repo(repo_name)
            
            # Build filter parameters
            kwargs = {'state': state}
            if labels:
                kwargs['labels'] = labels
            if assignee:
                kwargs['assignee'] = assignee
            
            issues = repo.get_issues(**kwargs)
            
            result = []
            count = 0
            for issue in issues:
                if count >= max_results:
                    break
                
                # Skip pull requests (they appear as issues in GitHub API)
                if issue.pull_request:
                    continue
                
                issue_dict = {
                    'number': issue.number,
                    'title': issue.title,
                    'body': issue.body,
                    'state': issue.state,
                    'html_url': issue.html_url,
                    'user': {
                        'login': issue.user.login,
                        'html_url': issue.user.html_url
                    } if issue.user else None,
                    'assignee': {
                        'login': issue.assignee.login,
                        'html_url': issue.assignee.html_url
                    } if issue.assignee else None,
                    'assignees': [{'login': a.login, 'html_url': a.html_url} for a in issue.assignees],
                    'labels': [{'name': label.name, 'color': label.color} for label in issue.labels],
                    'milestone': {
                        'title': issue.milestone.title,
                        'number': issue.milestone.number
                    } if issue.milestone else None,
                    'comments': issue.comments,
                    'created_at': issue.created_at.isoformat() if issue.created_at else None,
                    'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
                    'closed_at': issue.closed_at.isoformat() if issue.closed_at else None
                }
                result.append(issue_dict)
                count += 1
            
            logger.info("Issues retrieved successfully", repo=repo_name, count=len(result))
            return result
            
        except Exception as e:
            logger.error("Failed to get issues", repo=repo_name, error=str(e))
            raise GitHubOperationError(f"Failed to get issues from {repo_name}: {e}")
    
    def get_pull_requests(self, repo_name: str, state: str = "open", 
                         max_results: int = 30) -> List[Dict[str, Any]]:
        """Get pull requests from a repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo'
            state: PR state ('open', 'closed', 'all')
            max_results: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of pull requests
            
        Raises:
            GitHubOperationError: If getting pull requests fails
        """
        try:
            client = self.get_client()
            repo = client.get_repo(repo_name)
            
            pulls = repo.get_pulls(state=state)
            
            result = []
            count = 0
            for pr in pulls:
                if count >= max_results:
                    break
                
                pr_dict = {
                    'number': pr.number,
                    'title': pr.title,
                    'body': pr.body,
                    'state': pr.state,
                    'html_url': pr.html_url,
                    'user': {
                        'login': pr.user.login,
                        'html_url': pr.user.html_url
                    } if pr.user else None,
                    'head': {
                        'ref': pr.head.ref,
                        'sha': pr.head.sha,
                        'repo': pr.head.repo.full_name if pr.head.repo else None
                    },
                    'base': {
                        'ref': pr.base.ref,
                        'sha': pr.base.sha,
                        'repo': pr.base.repo.full_name if pr.base.repo else None
                    },
                    'merged': pr.merged,
                    'mergeable': pr.mergeable,
                    'comments': pr.comments,
                    'review_comments': pr.review_comments,
                    'commits': pr.commits,
                    'additions': pr.additions,
                    'deletions': pr.deletions,
                    'changed_files': pr.changed_files,
                    'created_at': pr.created_at.isoformat() if pr.created_at else None,
                    'updated_at': pr.updated_at.isoformat() if pr.updated_at else None,
                    'closed_at': pr.closed_at.isoformat() if pr.closed_at else None,
                    'merged_at': pr.merged_at.isoformat() if pr.merged_at else None
                }
                result.append(pr_dict)
                count += 1
            
            logger.info("Pull requests retrieved successfully", repo=repo_name, count=len(result))
            return result
            
        except Exception as e:
            logger.error("Failed to get pull requests", repo=repo_name, error=str(e))
            raise GitHubOperationError(f"Failed to get pull requests from {repo_name}: {e}")
    
    def create_issue(self, repo_name: str, title: str, body: str = "", 
                    labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new issue.
        
        Args:
            repo_name: Repository name in format 'owner/repo'
            title: Issue title
            body: Issue body
            labels: List of label names
            assignees: List of usernames to assign
            
        Returns:
            Dict[str, Any]: Created issue details
            
        Raises:
            GitHubOperationError: If creating issue fails
        """
        try:
            client = self.get_client()
            repo = client.get_repo(repo_name)
            
            kwargs = {'title': title, 'body': body}
            if labels:
                kwargs['labels'] = labels
            if assignees:
                kwargs['assignees'] = assignees
            
            issue = repo.create_issue(**kwargs)
            
            result = {
                'number': issue.number,
                'title': issue.title,
                'body': issue.body,
                'state': issue.state,
                'html_url': issue.html_url,
                'user': {
                    'login': issue.user.login,
                    'html_url': issue.user.html_url
                } if issue.user else None,
                'created_at': issue.created_at.isoformat() if issue.created_at else None
            }
            
            logger.info("Issue created successfully", repo=repo_name, number=issue.number)
            return result
            
        except Exception as e:
            logger.error("Failed to create issue", repo=repo_name, title=title, error=str(e))
            raise GitHubOperationError(f"Failed to create issue in {repo_name}: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
