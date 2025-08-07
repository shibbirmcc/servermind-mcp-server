"""Unit tests for configuration module."""

import os
import json
import tempfile
import pytest
from unittest.mock import patch
from src.config import ConfigLoader, SplunkConfig, MCPConfig, Config


class TestConfigLoader:
    """Test configuration loader functionality."""
    
    def test_load_from_file(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "splunk": {
                "host": "test-host",
                "port": 8089,
                "username": "test-user",
                "password": "test-pass"
            },
            "mcp": {
                "server_name": "test-server"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            config = loader.load()
            
            assert config.splunk.host == "test-host"
            assert config.splunk.port == 8089
            assert config.splunk.username == "test-user"
            assert config.splunk.password == "test-pass"
            assert config.mcp.server_name == "test-server"
            
        finally:
            os.unlink(temp_path)
    
    def test_load_with_env_override(self):
        """Test configuration override with environment variables."""
        config_data = {
            "splunk": {
                "host": "file-host",
                "port": 8089,
                "username": "file-user",
                "password": "file-pass"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            with patch.dict(os.environ, {
                'SPLUNK_HOST': 'env-host',
                'SPLUNK_USERNAME': 'env-user'
            }):
                loader = ConfigLoader(temp_path)
                config = loader.load()
                
                # Environment variables should override file values
                assert config.splunk.host == "env-host"
                assert config.splunk.username == "env-user"
                # File values should remain for non-overridden fields
                assert config.splunk.password == "file-pass"
                
        finally:
            os.unlink(temp_path)
    
    def test_missing_required_fields(self):
        """Test error handling for missing required fields."""
        config_data = {
            "splunk": {
                "host": "test-host"
                # Missing username and password
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Missing required Splunk configuration fields"):
                loader.load()
                
        finally:
            os.unlink(temp_path)
    
    def test_invalid_json(self):
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ValueError, match="Invalid JSON"):
                loader.load()
                
        finally:
            os.unlink(temp_path)
    
    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        loader = ConfigLoader("nonexistent.json")
        
        # Should not raise error, but use environment variables only
        with patch.dict(os.environ, {
            'SPLUNK_HOST': 'env-host',
            'SPLUNK_USERNAME': 'env-user',
            'SPLUNK_PASSWORD': 'env-pass'
        }):
            config = loader.load()
            assert config.splunk.host == "env-host"
            assert config.splunk.username == "env-user"
            assert config.splunk.password == "env-pass"
    
    def test_default_values(self):
        """Test default configuration values."""
        config_data = {
            "splunk": {
                "host": "test-host",
                "username": "test-user",
                "password": "test-pass"
                # Missing optional fields
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            config = loader.load()
            
            # Check default values
            assert config.splunk.port == 8089
            assert config.splunk.scheme == "https"
            assert config.splunk.version == "8.0"
            assert config.splunk.verify_ssl == True
            assert config.splunk.timeout == 30
            
            assert config.mcp.server_name == "splunk-mcp-server"
            assert config.mcp.version == "1.0.0"
            assert config.mcp.max_results_default == 100
            assert config.mcp.search_timeout == 300
            
        finally:
            os.unlink(temp_path)
    
    def test_type_conversion(self):
        """Test type conversion for environment variables."""
        with patch.dict(os.environ, {
            'SPLUNK_HOST': 'test-host',
            'SPLUNK_PORT': '9999',
            'SPLUNK_USERNAME': 'test-user',
            'SPLUNK_PASSWORD': 'test-pass',
            'SPLUNK_VERIFY_SSL': 'false',
            'SPLUNK_TIMEOUT': '60',
            'MCP_MAX_RESULTS_DEFAULT': '200'
        }):
            loader = ConfigLoader("nonexistent.json")
            config = loader.load()
            
            assert isinstance(config.splunk.port, int)
            assert config.splunk.port == 9999
            assert isinstance(config.splunk.verify_ssl, bool)
            assert config.splunk.verify_ssl == False
            assert isinstance(config.splunk.timeout, int)
            assert config.splunk.timeout == 60
            assert isinstance(config.mcp.max_results_default, int)
            assert config.mcp.max_results_default == 200


class TestConfigDataClasses:
    """Test configuration data classes."""
    
    def test_splunk_config_creation(self):
        """Test SplunkConfig creation."""
        config = SplunkConfig(
            host="test-host",
            port=8089,
            username="test-user",
            password="test-pass"
        )
        
        assert config.host == "test-host"
        assert config.port == 8089
        assert config.username == "test-user"
        assert config.password == "test-pass"
        assert config.scheme == "https"  # default
        assert config.version == "8.0"  # default
        assert config.verify_ssl == True  # default
        assert config.timeout == 30  # default
    
    def test_mcp_config_creation(self):
        """Test MCPConfig creation."""
        config = MCPConfig()
        
        assert config.server_name == "splunk-mcp-server"
        assert config.version == "1.0.0"
        assert config.max_results_default == 100
        assert config.search_timeout == 300
    
    def test_config_creation(self):
        """Test Config creation."""
        splunk_config = SplunkConfig(
            host="test-host",
            port=8089,
            username="test-user",
            password="test-pass"
        )
        mcp_config = MCPConfig()
        
        config = Config(splunk=splunk_config, mcp=mcp_config)
        
        assert config.splunk == splunk_config
        assert config.mcp == mcp_config
