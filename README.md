# ServerMind MCP Server

A comprehensive Model Context Protocol (MCP) server which provides seamless integration with Splunk, JIRA, and GitHub for unified log analysis, issue tracking, and repository management. This server enables AI assistants and other MCP clients to interact with multiple enterprise systems through a single interface.

## Overview

ServerMind MCP Server is a Splunk-focused MCP server that provides advanced log analysis and automated issue creation capabilities:

- **Splunk Integration**: Execute SPL queries, analyze logs, and monitor systems
- **Automated Issue Creation**: Analyze Splunk errors and automatically create issues via external MCP servers
- **External MCP Integration**: Leverages Atlassian and GitHub MCP servers for issue creation

## Features

### Current Capabilities

#### Splunk Integration
- **Advanced Search**: Execute SPL (Search Processing Language) queries with intelligent validation
- **Index Management**: List and analyze available Splunk indexes
- **Data Export**: Export search results in JSON, CSV, and XML formats
- **Real-time Monitoring**: Continuous log monitoring with configurable intervals
- **Cost Estimation**: Query complexity analysis and optimization suggestions
- **Rich Formatting**: Well-formatted results with analysis suggestions

#### JIRA Integration
- **Issue Search**: Execute JQL (JIRA Query Language) queries with advanced filtering
- **Project Management**: List available projects with metadata
- **Issue Details**: Get comprehensive information about specific issues
- **Smart Analysis**: Automatic pattern detection and workload analysis

#### GitHub Integration
- **Repository Management**: List and explore repositories with detailed statistics
- **Issue Tracking**: Access repository issues with filtering and analysis
- **Pull Request Management**: Monitor pull requests with merge status and code changes
- **Multi-scope Access**: Support for user, organization, and authenticated user repositories

### Planned Features

- **Cross-platform Analytics**: Correlate data across Splunk, JIRA, and GitHub
- **Advanced Dashboards**: Unified monitoring and reporting capabilities
- **Workflow Automation**: Automated actions based on cross-platform triggers
- **Enhanced Security**: Advanced authentication and authorization features

## Installation

### Prerequisites

- Python 3.8+ or higher
- Access to configured systems (Splunk, JIRA, and/or GitHub)
- Appropriate credentials and permissions

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/shibbirmcc/servermind-mcp-server.git
cd servermind-mcp-server
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure your connections**
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. **Run the server**
```bash
python src/server.py
```

## Configuration

The server uses environment variables for configuration. You can set these directly or use a `.env` file.

### Using .env File (Recommended)

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit the `.env` file with your credentials:

```bash
# MCP Server Configuration
MCP_SERVER_NAME=servermind-mcp-server
MCP_VERSION=1.0.0
LOG_LEVEL=INFO

# Splunk Configuration (Required)
SPLUNK_HOST=your-splunk-host.com
SPLUNK_PORT=8089
SPLUNK_USERNAME=your-username
SPLUNK_PASSWORD=your-password
SPLUNK_SCHEME=https
SPLUNK_VERIFY_SSL=true
SPLUNK_TIMEOUT=30

# GitHub Configuration (Optional - for direct GitHub integration)
GITHUB_TOKEN=your-github-token
GITHUB_API_URL=https://api.github.com
GITHUB_VERIFY_SSL=true
GITHUB_TIMEOUT=30

# Note: JIRA integration is now handled by external Atlassian MCP server
# Configure the Atlassian MCP server separately in your MCP client configuration
```

### Configuration Options

#### MCP Server Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `MCP_SERVER_NAME` | servermind-mcp-server | MCP server identifier |
| `MCP_VERSION` | 1.0.0 | Server version |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

#### Splunk Configuration (Required)

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `SPLUNK_HOST` | Yes | - | Splunk server hostname or IP |
| `SPLUNK_PORT` | No | 8089 | Splunk management port |
| `SPLUNK_USERNAME` | Yes | - | Splunk username |
| `SPLUNK_PASSWORD` | Yes | - | Splunk password |
| `SPLUNK_SCHEME` | No | https | Connection scheme (http/https) |
| `SPLUNK_VERIFY_SSL` | No | true | Verify SSL certificates |
| `SPLUNK_TIMEOUT` | No | 30 | Connection timeout in seconds |

#### JIRA Configuration (Optional)

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `JIRA_BASE_URL` | Yes* | - | JIRA instance URL |
| `JIRA_USERNAME` | Yes* | - | JIRA username/email |
| `JIRA_API_TOKEN` | Yes* | - | JIRA API token |
| `JIRA_VERIFY_SSL` | No | true | Verify SSL certificates |
| `JIRA_TIMEOUT` | No | 30 | Connection timeout in seconds |

*Required only if you want JIRA integration

#### GitHub Configuration (Optional)

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes* | - | GitHub personal access token |
| `GITHUB_API_URL` | No | https://api.github.com | GitHub API URL |
| `GITHUB_VERIFY_SSL` | No | true | Verify SSL certificates |
| `GITHUB_TIMEOUT` | No | 30 | Connection timeout in seconds |

*Required only if you want GitHub integration

## Usage

### Starting the Server

```bash
# Default port (8756)
python src/server.py

# Custom port
python src/server.py 8080
```

The server will display available tools based on your configuration:

```
ServerMind MCP Server running on http://localhost:8756
Endpoints:
  SSE: http://localhost:8756/sse
  Messages: http://localhost:8756/messages/
Tools:
  Splunk Tools:
    - splunk_search: Execute Splunk search queries
    - splunk_indexes: List available Splunk indexes
    - splunk_export: Export Splunk search results to various formats
    - splunk_monitor: Start continuous monitoring of Splunk logs
  JIRA Tools:
    - jira_search: Search JIRA issues using JQL
    - jira_projects: List available JIRA projects
    - jira_issue: Get detailed JIRA issue information
  GitHub Tools:
    - github_repositories: List GitHub repositories
    - github_repository: Get detailed repository information
    - github_issues: Get repository issues
    - github_pull_requests: Get repository pull requests
```

### MCP Client Configuration

#### For Cline (SSE Transport)

Add to your `cline-mcp-config.json`:

```json
{
  "mcpServers": {
    "servermind-mcp-server": {
      "disabled": false,
      "timeout": 60,
      "type": "sse",
      "url": "http://127.0.0.1:8756/"
    }
  }
}
```

#### For Claude Desktop (stdio)

```json
{
  "mcpServers": {
    "servermind": {
      "command": "python",
      "args": ["/path/to/servermind-mcp-server/src/server.py"]
    }
  }
}
```

## Available Tools

### Splunk Tools

#### splunk_search
Execute Splunk search queries using SPL (Search Processing Language).

**Parameters:**
- `query` (required): SPL search query to execute
- `earliest_time` (optional): Start time for search (default: "-24h")
- `latest_time` (optional): End time for search (default: "now")
- `max_results` (optional): Maximum number of results (default: 100)
- `timeout` (optional): Search timeout in seconds (default: 300)

**Example:**
```json
{
  "name": "splunk_search",
  "arguments": {
    "query": "index=main error | stats count by host",
    "earliest_time": "-1h",
    "max_results": 50
  }
}
```

#### splunk_indexes
List and get information about Splunk indexes.

**Parameters:**
- `filter_pattern` (optional): Pattern to filter index names
- `include_disabled` (optional): Include disabled indexes (default: true)
- `sort_by` (optional): Sort field - 'name', 'size', 'events', 'earliest', 'latest' (default: 'name')
- `sort_order` (optional): Sort order - 'asc' or 'desc' (default: 'asc')

#### splunk_export
Export Splunk search results to various formats.

**Parameters:**
- `query` (required): SPL search query to execute and export
- `format` (optional): Export format - 'json', 'csv', or 'xml' (default: 'json')
- `earliest_time` (optional): Start time for search (default: "-24h")
- `latest_time` (optional): End time for search (default: "now")
- `max_results` (optional): Maximum number of results (default: 1000)
- `timeout` (optional): Search timeout in seconds (default: 300)
- `fields` (optional): Specific fields to include in export

#### splunk_monitor
Start continuous monitoring of Splunk logs.

**Parameters:**
- `action` (required): Action to perform - 'start', 'stop', 'status', 'get_results'
- `query` (required for 'start'): SPL search query to monitor
- `interval` (optional): Monitoring interval in seconds (default: 60)
- `max_results` (optional): Maximum results per check (default: 1000)
- `timeout` (optional): Search timeout per check (default: 60)
- `clear_buffer` (optional): Clear results buffer after retrieving (default: true)

### JIRA Tools

#### jira_search
Search for JIRA issues using JQL (JIRA Query Language).

**Parameters:**
- `jql` (required): JQL query string
- `max_results` (optional): Maximum number of results (default: 50)
- `fields` (optional): List of fields to include

**Example:**
```json
{
  "name": "jira_search",
  "arguments": {
    "jql": "project = PROJ AND status = Open",
    "max_results": 25
  }
}
```

#### jira_projects
Get list of available JIRA projects.

**Parameters:** None

#### jira_issue
Get detailed information about a specific JIRA issue.

**Parameters:**
- `issue_key` (required): JIRA issue key (e.g., 'PROJ-123')
- `fields` (optional): List of fields to include

### GitHub Tools

#### github_repositories
Get list of GitHub repositories.

**Parameters:**
- `user_or_org` (optional): Username or organization name
- `repo_type` (optional): Repository type - 'all', 'owner', 'public', 'private', 'member' (default: 'all')
- `max_results` (optional): Maximum number of results (default: 30)

**Example:**
```json
{
  "name": "github_repositories",
  "arguments": {
    "user_or_org": "octocat",
    "repo_type": "public",
    "max_results": 10
  }
}
```

#### github_repository
Get detailed information about a specific GitHub repository.

**Parameters:**
- `repo_name` (required): Repository name in format 'owner/repo'

#### github_issues
Get issues from a GitHub repository.

**Parameters:**
- `repo_name` (required): Repository name in format 'owner/repo'
- `state` (optional): Issue state - 'open', 'closed', 'all' (default: 'open')
- `labels` (optional): List of label names to filter by
- `assignee` (optional): Username to filter by assignee
- `max_results` (optional): Maximum number of results (default: 30)

#### github_pull_requests
Get pull requests from a GitHub repository.

**Parameters:**
- `repo_name` (required): Repository name in format 'owner/repo'
- `state` (optional): PR state - 'open', 'closed', 'all' (default: 'open')
- `max_results` (optional): Maximum number of results (default: 30)

## Query Examples

### Splunk Examples

#### Basic Search
```spl
index=main error
```

#### Time-based Analysis
```spl
index=web_logs status=500 | timechart count by host
```

#### Statistical Analysis
```spl
index=security failed_login | stats count by src_ip | sort -count
```

### JIRA Examples

#### Find Open Issues
```jql
project = MYPROJ AND status = Open
```

#### Issues by Assignee
```jql
assignee = currentUser() AND status != Done
```

#### Recent High Priority Issues
```jql
priority in (High, Critical) AND created >= -7d
```

### GitHub Examples

#### Repository Search
- List all repositories for a user: `user_or_org: "username"`
- Find public repositories: `repo_type: "public"`
- Get organization repositories: `user_or_org: "organization"`

#### Issue Analysis
- Open bugs: `state: "open", labels: ["bug"]`
- Assigned issues: `assignee: "username"`
- Recent issues: Filter by creation date in results

## Security Considerations

### Credential Management
- Store all credentials securely using environment variables
- Use API tokens instead of passwords where possible
- Rotate credentials regularly
- Never commit credentials to version control

### Network Security
- Use HTTPS connections for all integrations
- Consider network segmentation for production deployments
- Implement proper firewall rules

### Access Control
- Run the MCP server with minimal required permissions
- Use dedicated service accounts with limited access
- Regularly audit access permissions

### Query Validation
- Built-in query validation prevents dangerous operations
- SPL queries are checked for harmful commands
- JQL queries are validated for syntax

## Development

### Running Tests

```bash
# Run unit tests
python -m pytest tests/unit/ -v

# Run integration tests (requires configured connections)
python -m pytest tests/integration/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Project Structure

```
servermind-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py              # Main MCP server
│   ├── config.py              # Configuration management
│   ├── splunk/                # Splunk integration
│   │   ├── __init__.py
│   │   ├── client.py          # Splunk API client
│   │   ├── search.py          # Search utilities
│   │   └── utils.py           # Utility functions
│   ├── jira/                  # JIRA integration
│   │   ├── __init__.py
│   │   └── client.py          # JIRA API client
│   ├── github/                # GitHub integration
│   │   ├── __init__.py
│   │   └── client.py          # GitHub API client
│   └── tools/                 # MCP tool implementations
│       ├── __init__.py
│       ├── search.py          # Splunk search tools
│       ├── indexes.py         # Splunk index tools
│       ├── export.py          # Splunk export tools
│       ├── monitor.py         # Splunk monitoring tools
│       ├── jira.py            # JIRA tools
│       └── github.py          # GitHub tools
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── __init__.py
├── .env.example              # Example environment configuration
├── cline-mcp-config.json     # Cline MCP configuration
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project configuration
└── README.md               # This file
```

## Troubleshooting

### Common Issues

#### Connection Problems
1. **Splunk Connection Failed**
   - Verify host, port, and credentials
   - Check network connectivity
   - Ensure Splunk is running

2. **JIRA Authentication Failed**
   - Verify base URL and API token
   - Check user permissions
   - Ensure API token is not expired

3. **GitHub API Errors**
   - Verify personal access token
   - Check token permissions
   - Ensure rate limits are not exceeded

#### Configuration Issues
1. **Tools Not Available**
   - Check environment variables are set
   - Verify .env file is loaded correctly
   - Restart server after configuration changes

2. **SSL Certificate Errors**
   - Set `verify_ssl: false` for self-signed certificates
   - Install proper SSL certificates
   - Check certificate validity

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python src/server.py
```

### Testing Connections

Test individual connections:

```bash
# Test Splunk connection
python test_splunk_connection.py

# Test MCP server
python test_mcp_server.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review existing GitHub issues
3. Create a new issue with detailed information
4. Include logs and configuration (without sensitive data)

## Changelog

### v1.0.0
- Initial release with Splunk, JIRA, and GitHub integration
- Comprehensive search and analysis capabilities
- Advanced query validation and safety checks
- Cost estimation and optimization suggestions
- Cross-platform data correlation
- Flexible configuration system
- Comprehensive error handling and logging
