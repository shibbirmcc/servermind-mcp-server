"""Test suite for README.md validation."""

import os
import pytest


class TestReadme:
    """Test class for README.md content validation."""
    
    @pytest.fixture(scope="class")
    def readme_content(self):
        """Load README.md content."""
        readme_path = os.path.join(os.path.dirname(__file__), '..', 'README.md')
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_readme_exists(self, readme_content):
        """Test that README.md exists and has content."""
        assert readme_content is not None
        assert len(readme_content) > 0
    
    def test_has_proper_title(self, readme_content):
        """Test that README has proper title."""
        assert '# Splunk MCP Server' in readme_content
    
    def test_contains_overview_section(self, readme_content):
        """Test that README contains overview section."""
        assert '## Overview' in readme_content
    
    def test_contains_features_section(self, readme_content):
        """Test that README contains features section."""
        assert '## Features' in readme_content
        assert '### Current Capabilities' in readme_content
        assert '### Planned Features' in readme_content
    
    def test_contains_installation_instructions(self, readme_content):
        """Test that README contains installation instructions."""
        assert '## Installation' in readme_content
        assert '### Prerequisites' in readme_content
        assert '### Setup' in readme_content
    
    def test_contains_configuration_section(self, readme_content):
        """Test that README contains configuration section."""
        assert '## Configuration' in readme_content
        assert 'config.json' in readme_content
    
    def test_contains_usage_examples(self, readme_content):
        """Test that README contains usage examples."""
        assert '## Usage' in readme_content
        assert '### Available Tools' in readme_content
        assert 'splunk_search' in readme_content
    
    def test_contains_security_considerations(self, readme_content):
        """Test that README contains security considerations."""
        assert '## Security Considerations' in readme_content
    
    def test_contains_development_section(self, readme_content):
        """Test that README contains development section."""
        assert '## Development' in readme_content
        assert '### Project Structure' in readme_content
    
    def test_contains_troubleshooting_section(self, readme_content):
        """Test that README contains troubleshooting section."""
        assert '## Troubleshooting' in readme_content
        assert '### Common Issues' in readme_content
    
    def test_contains_proper_github_repository_references(self, readme_content):
        """Test that README contains proper GitHub repository references."""
        assert 'shibbirmcc/splunk-mcp-server' in readme_content
    
    def test_contains_license_information(self, readme_content):
        """Test that README contains license information."""
        assert '## License' in readme_content
        assert 'MIT License' in readme_content
    
    def test_contains_changelog(self, readme_content):
        """Test that README contains changelog."""
        assert '## Changelog' in readme_content
        assert 'v1.0.0' in readme_content
    
    def test_references_python_as_primary_language(self, readme_content):
        """Test that README references Python as primary language."""
        assert 'Python 3.8+' in readme_content
        assert 'python src/server.py' in readme_content
        assert 'requirements.txt' in readme_content
        assert 'pyproject.toml' in readme_content
    
    def test_contains_python_project_structure(self, readme_content):
        """Test that README contains Python project structure."""
        assert 'server.py' in readme_content
        assert 'client.py' in readme_content
        assert '__init__.py' in readme_content
        assert 'python -m pytest tests/' in readme_content
