# Postman Testing Guide for Splunk MCP Server

This guide explains how to use the provided Postman collection to test the Splunk MCP Server with SSE transport.

## Prerequisites

1. **Server Running**: Ensure the MCP server is running on port 8756:
   ```bash
   python -m src.server
   ```

2. **Splunk Instance**: Have a local Splunk instance running with proper credentials configured in `.env`

3. **Postman**: Install Postman desktop application or use the web version

## Import Collection

1. Open Postman
2. Click "Import" button
3. Select the `postman-collection.json` file
4. The collection "Splunk MCP Server API" will be imported

## Collection Structure

### 1. Health Check
- **Root Endpoint**: Tests basic server connectivity (`GET /`)
- **SSE Endpoint**: Tests Server-Sent Events endpoint (`GET /sse`)

### 2. MCP Protocol
- **Initialize Connection**: Establishes MCP protocol connection
- **List Tools**: Retrieves available tools (should show `splunk_search`)
- **List Resources**: Lists available resources

### 3. Splunk Search Tool
- **Basic Search - Index Main**: Simple search in main index
- **Search Kubernetes Index**: Search in kubernetes index (if available)
- **Stats Query - Count by Host**: Statistical analysis by host
- **Timechart Query**: Time-based analysis
- **Metadata Query - Sources**: Get data source metadata
- **Search with Custom Timeout**: Custom timeout example

### 4. Error Testing
- **Invalid Query**: Tests error handling with malformed SPL
- **Empty Query**: Tests validation with empty query
- **Invalid Tool Name**: Tests error handling with wrong tool name

### 5. Advanced Queries
- **Complex Analytics Query**: Multi-function statistical analysis
- **Search with Eval and Where**: Advanced SPL with eval/where clauses
- **Top Command Query**: Find top values using SPL top command

## Variables

The collection uses these variables:
- `baseUrl`: Server URL (default: `http://localhost:8756`)
- `sessionId`: Unique session identifier (auto-generated)

## Usage Instructions

### Step 1: Health Check
1. Run "Root Endpoint" - should return 200 OK
2. Run "SSE Endpoint" - should return 200 OK (may timeout in Postman, this is normal)

### Step 2: MCP Protocol Setup
1. Run "Initialize Connection" - establishes MCP session
2. Run "List Tools" - should show `splunk_search` tool
3. Run "List Resources" - shows available resources

### Step 3: Test Splunk Searches
1. Start with "Basic Search - Index Main"
2. Try "Search Kubernetes Index" if you have kubernetes data
3. Test statistical queries like "Stats Query - Count by Host"

### Step 4: Error Testing
1. Run error test cases to verify proper error handling
2. Check that errors are returned in proper JSON-RPC format

## Expected Responses

### Successful Tool Call
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "✅ **Splunk Search Completed**\n\nQuery: index=main\nResults: X events\n..."
      }
    ]
  }
}
```

### Error Response
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "❌ **Splunk Search Error**\n\nSearch execution failed: ..."
      }
    ]
  }
}
```

## Troubleshooting

### Server Not Responding
- Check if server is running: `ps aux | grep "python -m src.server"`
- Verify port 8756 is not blocked
- Check server logs for errors

### SSL Certificate Errors
- Ensure `SPLUNK_VERIFY_SSL=false` in `.env` file
- Check Splunk connection with: `python test_local_splunk.py`

### No Data in Searches
- Verify Splunk has data in the specified indexes
- Try searching different indexes (main, _internal, etc.)
- Check time ranges in queries

### JSON-RPC Errors
- Ensure Content-Type is `application/json`
- Verify JSON syntax in request body
- Check that session_id parameter is included

## Advanced Testing

### Custom Queries
Modify the query field in any search request:
```json
{
  "query": "index=_internal | stats count by component | sort -count"
}
```

### Time Range Testing
Adjust time ranges:
```json
{
  "earliest_time": "-7d",
  "latest_time": "-1d"
}
```

### Result Limits
Control result count:
```json
{
  "max_results": 50
}
```

## Automated Testing

The collection includes test scripts that automatically:
- Validate response status codes
- Check JSON-RPC format
- Log responses for debugging

View test results in the Postman "Test Results" tab after running requests.

## Integration with CI/CD

You can run this collection in automated tests using Newman:
```bash
npm install -g newman
newman run postman-collection.json --environment your-env.json
```

## Support

If you encounter issues:
1. Check server logs for detailed error messages
2. Verify Splunk connectivity with integration tests
3. Ensure all environment variables are properly set
4. Review the MCP protocol documentation for advanced usage
