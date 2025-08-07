# Splunk MCP Server

A Model Context Protocol (MCP) server that provides seamless integration with Splunk for log access, search, and analysis capabilities. This server enables AI assistants and other MCP clients to interact with Splunk instances, execute searches, and analyze log data.

## Features

- **Splunk Search Integration**: Execute SPL (Search Processing Language) queries directly from MCP clients
- **Intelligent Query Validation**: Built-in SPL query validation and safety checks
- **Cost Estimation**: Analyze query complexity and provide optimization suggestions
- **Rich Result Formatting**: Well-formatted search results with analysis suggestions
- **Resource Access**: Access Splunk connection info and index metadata
- **Comprehensive Error Handling**: Detailed error messages and troubleshooting guidance
- **Flexible Configuration**: Support for JSON files and environment variables

## Installation

### Prerequisites

- Python 3.8 or higher
- Access to a Splunk instance
- Splunk credentials with search permissions

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Development Installation

```bash
pip install -e .
```

## Configuration

### Option 1: Configuration File

Create a `config.json` file in the project root:

```json
{
  "splunk": {
    "host": "your-splunk-host.com",
    "port": 8089,
    "username": "your-username",
    "password": "your-password",
    "scheme": "https",
    "verify_ssl": true,
    "timeout": 30
  },
  "mcp": {
    "server_name": "splunk-mcp-server",
    "version": "1.0.0",
    "max_results_default": 100,
    "search_timeout": 300
  }
}
```

### Option 2: Environment Variables

Set the following environment variables:

```bash
export SPLUNK_HOST=your-splunk-host.com
export SPLUNK_PORT=8089
export SPLUNK_USERNAME=your-username
export SPLUNK_PASSWORD=your-password
export SPLUNK_SCHEME=https
export SPLUNK_VERIFY_SSL=true
export SPLUNK_TIMEOUT=30
```

### Configuration Options

#### Splunk Configuration

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `host` | Yes | - | Splunk server hostname or IP |
| `port` | No | 8089 | Splunk management port |
| `username` | Yes | - | Splunk username |
| `password` | Yes | - | Splunk password |
| `scheme` | No | https | Connection scheme (http/https) |
| `verify_ssl` | No | true | Verify SSL certificates |
| `timeout` | No | 30 | Connection timeout in seconds |

#### MCP Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `server_name` | splunk-mcp-server | MCP server name |
| `version` | 1.0.0 | Server version |
| `max_results_default` | 100 | Default maximum search results |
| `search_timeout` | 300 | Default search timeout in seconds |

## Usage

### Docker Deployment (Recommended)

The easiest way to run the MCP server is using Docker:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your Splunk credentials
nano .env  # or use your preferred editor

# 3. Build and run the container
./docker-run.sh run

# Or using docker-compose directly
docker-compose up -d
```

#### Docker Commands

```bash
# Build the image
./docker-run.sh build

# Start the server
./docker-run.sh run

# Run tests
./docker-run.sh test

# View logs
./docker-run.sh logs

# Stop the server
./docker-run.sh stop

# Check health
./docker-run.sh health

# Open shell in container
./docker-run.sh shell

# Clean up resources
./docker-run.sh clean
```

### Local Development

For local development without Docker:

```bash
# Using the installed script
splunk-mcp-server

# Or using Python module
python -m src.server

# Or directly
python src/server.py
```

### Testing the Installation

Run the test script to verify everything is working:

```bash
python test_server.py
```

### MCP Client Configuration

Configure your MCP client to connect to this server. The server communicates via stdio.

#### Docker Configuration for Cline

To use the Dockerized MCP server with Cline, configure it to run the container:

```json
{
  "mcpServers": {
    "splunk": {
      "command": "docker",
      "args": [
        "run", 
        "--rm", 
        "-i",
        "--env-file", "/path/to/splunk-mcp-server/.env",
        "splunk-mcp-server"
      ]
    }
  }
}
```

Or using docker-compose:

```json
{
  "mcpServers": {
    "splunk": {
      "command": "docker-compose",
      "args": [
        "-f", "/path/to/splunk-mcp-server/docker-compose.yml",
        "run", "--rm", "splunk-mcp-server"
      ],
      "cwd": "/path/to/splunk-mcp-server"
    }
  }
}
```

#### Local Configuration for Claude Desktop

```json
{
  "mcpServers": {
    "splunk": {
      "command": "python",
      "args": ["/path/to/splunk-mcp-server/src/server.py"]
    }
  }
}
```

## Available Tools

### splunk_search

Execute Splunk search queries using SPL (Search Processing Language).

**Parameters:**
- `query` (required): SPL search query to execute
- `earliest_time` (optional): Start time for search (default: "-24h")
- `latest_time` (optional): End time for search (default: "now")
- `max_results` (optional): Maximum number of results (default: 100)
- `timeout` (optional): Search timeout in seconds (default: 300)

**Example Usage:**
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

## Available Resources

### splunk://connection-info

Provides information about the current Splunk connection including server version, build, and connection status.

### splunk://indexes

Lists all available Splunk indexes with metadata including event counts, size information, and time ranges.

## Query Examples

### Basic Search
```spl
index=main error
```

### Time-based Analysis
```spl
index=web_logs status=500 | timechart count by host
```

### Statistical Analysis
```spl
index=security failed_login | stats count by src_ip | sort -count
```

### Field Extraction
```spl
index=app_logs | rex field=_raw "user=(?<username>\w+)" | stats count by username
```

## Query Validation and Safety

The server includes built-in query validation that:

- Checks for dangerous commands (delete, drop, truncate, alter)
- Validates quote balancing
- Limits pipe operations to prevent overly complex queries
- Provides syntax suggestions and corrections

## Cost Estimation

The server analyzes query complexity and provides cost estimates:

- **Low Cost**: Simple queries with short time ranges
- **Medium Cost**: Moderate complexity with reasonable scope
- **High Cost**: Complex queries with expensive operations
- **Very High Cost**: Resource-intensive queries requiring optimization

Cost factors include:
- Time range scope
- Query complexity (joins, transactions, clustering)
- Number of pipe operations
- Use of expensive commands

## Error Handling

The server provides detailed error messages for common issues:

- **Connection Errors**: Splunk server connectivity issues
- **Authentication Errors**: Invalid credentials or permissions
- **Search Errors**: SPL syntax errors or search failures
- **Timeout Errors**: Long-running searches that exceed limits

## Development

### Running Tests

```bash
# Run unit tests
python -m pytest tests/unit/ -v

# Run with coverage
python -m pytest tests/unit/ --cov=src --cov-report=html

# Run integration tests (requires Splunk connection)
python -m pytest tests/integration/ -v
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
splunk-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py              # Main MCP server
│   ├── config.py              # Configuration management
│   ├── splunk/
│   │   ├── __init__.py
│   │   ├── client.py          # Splunk API client
│   │   ├── search.py          # Search utilities
│   │   └── utils.py           # Utility functions
│   └── tools/
│       ├── __init__.py
│       ├── search.py          # Search tool implementation
│       ├── indexes.py         # Index management tools
│       └── export.py          # Data export tools
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── __init__.py
├── config.example.json        # Example configuration
├── config.test.json          # Test configuration
├── test_server.py            # Server test script
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project configuration
└── README.md               # This file
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify Splunk host and port are correct
   - Check network connectivity to Splunk server
   - Ensure Splunk is running and accessible

2. **Authentication Failed**
   - Verify username and password are correct
   - Check user permissions in Splunk
   - Ensure account is not locked

3. **Search Timeout**
   - Reduce search time range
   - Simplify complex queries
   - Increase timeout value in configuration

4. **SSL Certificate Errors**
   - Set `verify_ssl: false` for self-signed certificates
   - Install proper SSL certificates on Splunk server

### Debug Mode

Enable debug logging by setting the log level:

```bash
export LOG_LEVEL=DEBUG
python -m src.server
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review existing GitHub issues
3. Create a new issue with detailed information
4. Include logs and configuration (without sensitive data)

## Changelog

### Version 1.0.0
- Initial release
- Basic Splunk search functionality
- Configuration management
- Query validation and safety checks
- Cost estimation and optimization suggestions
- Comprehensive error handling
- Resource access for connection info and indexes
