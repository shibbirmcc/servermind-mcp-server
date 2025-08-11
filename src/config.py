"""Configuration management for Splunk MCP Server."""

import os
from typing import Optional
from dataclasses import dataclass
import structlog
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)


@dataclass
class SplunkConfig:
    """Splunk connection configuration."""
    host: str
    port: int
    username: str = ""
    password: str = ""
    scheme: str = "https"
    version: str = "8.0"
    verify_ssl: bool = True
    timeout: int = 30


@dataclass
class JiraConfig:
    """JIRA connection configuration."""
    base_url: str
    username: str = ""
    api_token: str = ""
    timeout: int = 30
    verify_ssl: bool = True


@dataclass
class GitHubConfig:
    """GitHub connection configuration."""
    token: str
    api_url: str = "https://api.github.com"
    timeout: int = 30
    verify_ssl: bool = True


@dataclass
class MCPConfig:
    """MCP server configuration."""
    server_name: str = "servermind-mcp-server"
    version: str = "1.0.0"
    max_results_default: int = 100
    search_timeout: int = 300


@dataclass
class Config:
    """Main configuration container."""
    splunk: SplunkConfig
    jira: Optional[JiraConfig]
    github: Optional[GitHubConfig]
    mcp: MCPConfig


class ConfigLoader:
    """Configuration loader using environment variables only."""
    
    def __init__(self):
        """Initialize configuration loader."""
        self._config: Optional[Config] = None
        # Load .env file if it exists
        load_dotenv()
    
    def load(self) -> Config:
        """Load configuration from environment variables.
        
        Returns:
            Config: Loaded configuration
            
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        if self._config is not None:
            return self._config
        
        logger.info("Loading configuration from environment variables")
        
        # Load configuration from environment variables
        self._config = self._create_config_from_env()
        
        logger.info("Configuration loaded successfully")
        return self._config
    
    def _create_config_from_env(self) -> Config:
        """Create configuration objects from environment variables."""
        # Get required Splunk configuration
        host = os.getenv('SPLUNK_HOST')
        username = os.getenv('SPLUNK_USERNAME')
        password = os.getenv('SPLUNK_PASSWORD')
        
        if not host:
            raise ValueError("Missing required environment variable: SPLUNK_HOST")
        
        if not (username and password):
            raise ValueError("Must provide both SPLUNK_USERNAME and SPLUNK_PASSWORD environment variables")
        
        # Get optional Splunk configuration with defaults
        port = self._get_int_env('SPLUNK_PORT', 8089)
        scheme = os.getenv('SPLUNK_SCHEME', 'https')
        version = os.getenv('SPLUNK_VERSION', '8.0')
        verify_ssl = self._get_bool_env('SPLUNK_VERIFY_SSL', True)
        timeout = self._get_int_env('SPLUNK_TIMEOUT', 30)
        
        # Create Splunk config
        splunk_config = SplunkConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            scheme=scheme,
            version=version,
            verify_ssl=verify_ssl,
            timeout=timeout
        )
        
        # Get optional JIRA configuration
        jira_config = None
        jira_base_url = os.getenv('JIRA_BASE_URL')
        jira_username = os.getenv('JIRA_USERNAME')
        jira_api_token = os.getenv('JIRA_API_TOKEN')
        
        if jira_base_url and jira_username and jira_api_token:
            jira_timeout = self._get_int_env('JIRA_TIMEOUT', 30)
            jira_verify_ssl = self._get_bool_env('JIRA_VERIFY_SSL', True)
            
            jira_config = JiraConfig(
                base_url=jira_base_url,
                username=jira_username,
                api_token=jira_api_token,
                timeout=jira_timeout,
                verify_ssl=jira_verify_ssl
            )
            logger.info("JIRA configuration loaded")
        else:
            logger.info("JIRA configuration not provided, JIRA tools will be disabled")
        
        # Get optional GitHub configuration
        github_config = None
        github_token = os.getenv('GITHUB_TOKEN')
        
        if github_token:
            github_api_url = os.getenv('GITHUB_API_URL', 'https://api.github.com')
            github_timeout = self._get_int_env('GITHUB_TIMEOUT', 30)
            github_verify_ssl = self._get_bool_env('GITHUB_VERIFY_SSL', True)
            
            github_config = GitHubConfig(
                token=github_token,
                api_url=github_api_url,
                timeout=github_timeout,
                verify_ssl=github_verify_ssl
            )
            logger.info("GitHub configuration loaded")
        else:
            logger.info("GitHub configuration not provided, GitHub tools will be disabled")
        
        # Get MCP configuration with defaults
        server_name = os.getenv('MCP_SERVER_NAME', 'splunk-mcp-server')
        mcp_version = os.getenv('MCP_VERSION', '1.0.0')
        max_results_default = self._get_int_env('MCP_MAX_RESULTS_DEFAULT', 100)
        search_timeout = self._get_int_env('MCP_SEARCH_TIMEOUT', 300)
        
        # Create MCP config
        mcp_config = MCPConfig(
            server_name=server_name,
            version=mcp_version,
            max_results_default=max_results_default,
            search_timeout=search_timeout
        )
        
        return Config(
            splunk=splunk_config,
            jira=jira_config,
            github=github_config,
            mcp=mcp_config
        )
    
    def _get_int_env(self, env_var: str, default: int) -> int:
        """Get integer value from environment variable with default."""
        value = os.getenv(env_var)
        if value is None:
            return default
        
        try:
            return int(value)
        except ValueError:
            logger.warning("Invalid integer value for environment variable, using default", 
                         env_var=env_var, value=value, default=default)
            return default
    
    def _get_bool_env(self, env_var: str, default: bool) -> bool:
        """Get boolean value from environment variable with default."""
        value = os.getenv(env_var)
        if value is None:
            return default
        
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def reload(self) -> Config:
        """Reload configuration from environment variables."""
        # Reload .env file
        load_dotenv(override=True)
        self._config = None
        return self.load()


# Global configuration instance
_config_loader = ConfigLoader()


def get_config() -> Config:
    """Get the global configuration instance."""
    return _config_loader.load()


def reload_config() -> Config:
    """Reload the global configuration."""
    return _config_loader.reload()
