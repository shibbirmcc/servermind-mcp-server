"""Configuration management for Splunk MCP Server."""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import structlog

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
class MCPConfig:
    """MCP server configuration."""
    server_name: str = "splunk-mcp-server"
    version: str = "1.0.0"
    max_results_default: int = 100
    search_timeout: int = 300


@dataclass
class Config:
    """Main configuration container."""
    splunk: SplunkConfig
    mcp: MCPConfig


class ConfigLoader:
    """Configuration loader with support for JSON files and environment variables."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration loader.
        
        Args:
            config_path: Path to configuration file. If None, looks for config.json
        """
        self.config_path = config_path or "config.json"
        self._config: Optional[Config] = None
    
    def load(self) -> Config:
        """Load configuration from file and environment variables.
        
        Returns:
            Config: Loaded configuration
            
        Raises:
            FileNotFoundError: If config file is not found
            ValueError: If configuration is invalid
        """
        if self._config is not None:
            return self._config
        
        logger.info("Loading configuration", config_path=self.config_path)
        
        # Load from JSON file
        config_data = self._load_from_file()
        
        # Override with environment variables
        config_data = self._override_with_env(config_data)
        
        # Validate and create config objects
        self._config = self._create_config(config_data)
        
        logger.info("Configuration loaded successfully")
        return self._config
    
    def _load_from_file(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        config_path = Path(self.config_path)
        
        if not config_path.exists():
            logger.warning("Config file not found, using environment variables only", 
                         path=str(config_path))
            return {"splunk": {}, "mcp": {}}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            logger.debug("Configuration loaded from file", path=str(config_path))
            return config_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading config file {config_path}: {e}")
    
    def _override_with_env(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Override configuration with environment variables."""
        env_mappings = {
            'SPLUNK_HOST': ('splunk', 'host'),
            'SPLUNK_PORT': ('splunk', 'port'),
            'SPLUNK_USERNAME': ('splunk', 'username'),
            'SPLUNK_PASSWORD': ('splunk', 'password'),
            'SPLUNK_SCHEME': ('splunk', 'scheme'),
            'SPLUNK_VERSION': ('splunk', 'version'),
            'SPLUNK_VERIFY_SSL': ('splunk', 'verify_ssl'),
            'SPLUNK_TIMEOUT': ('splunk', 'timeout'),
            'MCP_SERVER_NAME': ('mcp', 'server_name'),
            'MCP_VERSION': ('mcp', 'version'),
            'MCP_MAX_RESULTS_DEFAULT': ('mcp', 'max_results_default'),
            'MCP_SEARCH_TIMEOUT': ('mcp', 'search_timeout'),
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if section not in config_data:
                    config_data[section] = {}
                
                # Convert types for specific fields
                if key in ['port', 'timeout', 'max_results_default', 'search_timeout']:
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning("Invalid integer value for environment variable", 
                                     env_var=env_var, value=value)
                        continue
                elif key == 'verify_ssl':
                    value = value.lower() in ('true', '1', 'yes', 'on')
                
                config_data[section][key] = value
                logger.debug("Configuration overridden from environment", 
                           env_var=env_var, section=section, key=key)
        
        return config_data
    
    def _create_config(self, config_data: Dict[str, Any]) -> Config:
        """Create configuration objects from loaded data."""
        splunk_data = config_data.get('splunk', {})
        mcp_data = config_data.get('mcp', {})
        
        # Validate required Splunk fields - username and password required
        host = splunk_data.get('host')
        username = splunk_data.get('username')
        password = splunk_data.get('password')
        
        if not host:
            raise ValueError("Missing required Splunk configuration field: host")
        
        if not (username and password):
            raise ValueError("Must provide both SPLUNK_USERNAME and SPLUNK_PASSWORD")
        
        # Create Splunk config
        splunk_config = SplunkConfig(
            host=host,
            port=splunk_data.get('port', 8089),
            username=username,
            password=password,
            scheme=splunk_data.get('scheme', 'https'),
            version=splunk_data.get('version', '8.0'),
            verify_ssl=splunk_data.get('verify_ssl', True),
            timeout=splunk_data.get('timeout', 30)
        )
        
        # Create MCP config
        mcp_config = MCPConfig(
            server_name=mcp_data.get('server_name', 'splunk-mcp-server'),
            version=mcp_data.get('version', '1.0.0'),
            max_results_default=mcp_data.get('max_results_default', 100),
            search_timeout=mcp_data.get('search_timeout', 300)
        )
        
        return Config(splunk=splunk_config, mcp=mcp_config)
    
    def reload(self) -> Config:
        """Reload configuration from file and environment."""
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
