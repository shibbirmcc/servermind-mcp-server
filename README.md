# Splunk MCP Server

A Model Context Protocol (MCP) server that provides seamless integration with Splunk for log access, search, and analysis capabilities within Cline and other MCP-compatible tools.

## Overview

This MCP server enables direct interaction with Splunk instances, allowing you to search logs, retrieve data, and perform analytics operations without leaving your development environment. It's designed to bridge the gap between your coding workflow and log analysis needs.

## Features

### Current Capabilities

- **Search Execution**: Run Splunk searches using SPL (Search Processing Language)
- **Real-time Search**: Execute real-time searches for live log monitoring
- **Historical Data Access**: Query historical log data with time range specifications
- **Index Listing**: Retrieve available Splunk indexes
- **Saved Search Management**: Access and execute saved searches
- **Field Extraction**: Extract and analyze specific fields from search results
- **Export Functionality**: Export search results in various formats (CSV, JSON, XML)

### Planned Features (Future Improvements)

- **Dashboard Integration**: Access and interact with Splunk dashboards
- **Alert Management**: Create, modify, and monitor Splunk alerts
- **Knowledge Object Management**: Manage lookups, macros, and data models
- **User Management**: Handle user permissions and roles
- **App Management**: Install and configure Splunk apps
- **Metrics and KPI Tracking**: Advanced analytics and performance monitoring
- **Visualization Support**: Generate charts and graphs from search results
- **Batch Operations**: Execute multiple searches in parallel
- **Custom Command Integration**: Support for custom Splunk commands
- **Advanced Authentication**: Support for SAML, LDAP, and multi-factor authentication

## Installation

### Prerequisites

- Python 3.8+
- Access to a Splunk instance (Enterprise or Cloud)
- Valid Splunk credentials with appropriate permissions

### Setup

1. Clone the repository:
```bash
git clone https://github.com/shibbirmcc/splunk-mcp-server.git
cd splunk-mcp-server
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure your Splunk connection:
```bash
cp config.example.json config.json
# Edit config.json with your Splunk details
```

4. Start the MCP server:
```bash
python src/server.py
```

## Configuration

Create a `config.json` file with your Splunk instance details:

```json
{
  "splunk": {
    "host": "your-splunk-instance.com",
    "port": 8089,
    "username": "your-username",
    "password": "your-password",
    "scheme": "https",
    "version": "8.0"
  },
  "mcp": {
    "server_name": "splunk-mcp-server",
    "version": "1.0.0"
  }
}
```

### Environment Variables

Alternatively, you can use environment variables:

```bash
export SPLUNK_HOST=your-splunk-instance.com
export SPLUNK_PORT=8089
export SPLUNK_USERNAME=your-username
export SPLUNK_PASSWORD=your-password
export SPLUNK_SCHEME=https
```

## Usage

### Available Tools

#### `splunk_search`
Execute a Splunk search query.

**Parameters:**
- `query` (string): SPL search query
- `earliest_time` (string, optional): Start time for search (default: -24h)
- `latest_time` (string, optional): End time for search (default: now)
- `max_results` (number, optional): Maximum number of results (default: 100)

**Example:**
```json
{
  "query": "index=main error | head 10",
  "earliest_time": "-1h",
  "latest_time": "now",
  "max_results": 50
}
```

#### `splunk_list_indexes`
Retrieve a list of available Splunk indexes.

**Parameters:**
- `filter` (string, optional): Filter indexes by name pattern

#### `splunk_saved_search`
Execute a saved search by name.

**Parameters:**
- `search_name` (string): Name of the saved search
- `dispatch_args` (object, optional): Additional dispatch arguments

#### `splunk_export_results`
Export search results in specified format.

**Parameters:**
- `search_id` (string): Search job ID
- `format` (string): Export format (csv, json, xml)
- `filename` (string, optional): Output filename

### Available Resources

#### `splunk://indexes`
Access to Splunk indexes information.

#### `splunk://saved-searches`
Access to saved searches catalog.

#### `splunk://search-jobs`
Access to active and completed search jobs.

## Examples

### Basic Log Search
```javascript
// Search for errors in the last hour
const result = await mcpClient.callTool('splunk_search', {
  query: 'index=main level=error | stats count by source',
  earliest_time: '-1h',
  max_results: 100
});
```

### Real-time Monitoring
```javascript
// Monitor live logs for specific patterns
const result = await mcpClient.callTool('splunk_search', {
  query: 'index=main | search "authentication failed"',
  earliest_time: 'rt-5m',
  latest_time: 'rt'
});
```

### Data Analysis
```javascript
// Analyze user activity patterns
const result = await mcpClient.callTool('splunk_search', {
  query: 'index=web_logs | stats count by user, action | sort -count',
  earliest_time: '-7d',
  max_results: 500
});
```

## Security Considerations

- **Credential Management**: Store credentials securely using environment variables or encrypted configuration files
- **Network Security**: Use HTTPS connections to Splunk instances
- **Access Control**: Implement proper user permissions and role-based access
- **Audit Logging**: Log all search activities for compliance and monitoring
- **Rate Limiting**: Implement request throttling to prevent API abuse

## Development

### Project Structure
```
splunk-mcp-server/
├── src/
│   ├── server.py          # Main MCP server implementation
│   ├── splunk/
│   │   ├── __init__.py
│   │   ├── client.py      # Splunk API client
│   │   ├── search.py      # Search functionality
│   │   └── utils.py       # Utility functions
│   └── tools/
│       ├── __init__.py
│       ├── search.py      # Search tool implementation
│       ├── indexes.py     # Index management tools
│       └── export.py      # Export functionality
├── tests/
│   ├── __init__.py
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── docs/                  # Documentation
├── config.example.json    # Example configuration
├── requirements.txt       # Python dependencies
└── pyproject.toml         # Python project configuration
```

### Running Tests
```bash
python -m pytest tests/
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## API Reference

### Splunk REST API Integration

This server integrates with the following Splunk REST API endpoints:

- `/services/search/jobs` - Search job management
- `/services/data/indexes` - Index information
- `/services/saved/searches` - Saved search management
- `/services/search/jobs/{sid}/results` - Search results retrieval
- `/services/search/jobs/{sid}/events` - Event data access

### Error Handling

The server implements comprehensive error handling for:

- Connection failures
- Authentication errors
- Invalid search syntax
- Timeout scenarios
- Rate limiting
- Permission issues

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Verify Splunk instance is accessible
   - Check firewall settings
   - Confirm port configuration

2. **Authentication Failed**
   - Verify username and password
   - Check user permissions in Splunk
   - Ensure account is not locked

3. **Search Timeout**
   - Reduce search time range
   - Optimize search query
   - Increase timeout settings

4. **No Results Returned**
   - Verify index exists and contains data
   - Check time range parameters
   - Review search syntax

### Debug Mode

Enable debug logging by setting:
```bash
export DEBUG=splunk-mcp-server:*
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs and feature requests on [GitHub Issues](https://github.com/shibbirmcc/splunk-mcp-server/issues)
- **Documentation**: Visit our [Wiki](https://github.com/shibbirmcc/splunk-mcp-server/wiki)
- **Community**: Join discussions in [GitHub Discussions](https://github.com/shibbirmcc/splunk-mcp-server/discussions)

## Changelog

### v1.0.0 (Planned)
- Initial release with basic search functionality
- Index listing and management
- Saved search execution
- Export capabilities
- Basic authentication support

### Future Releases
- Dashboard integration
- Advanced analytics
- Real-time streaming
- Enhanced security features
- Performance optimizations

---

**Note**: This project is under active development. Features and APIs may change before the stable release. Please check the [roadmap](https://github.com/shibbirmcc/splunk-mcp-server/projects) for current development status.
