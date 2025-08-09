# Splunk MCP Server Tool Parameters Guide

This document provides comprehensive descriptions of all parameters for the Splunk MCP Server tools to help Cline and other AI assistants understand how to use them effectively.

## Tool Overview

The Splunk MCP Server provides four main tools for interacting with Splunk:

1. **splunk_search** - Execute SPL queries and get formatted results
2. **splunk_indexes** - List and analyze available Splunk indexes
3. **splunk_export** - Export search results in various formats
4. **splunk_monitor** - Continuous monitoring of Splunk logs

---

## 1. splunk_search

Execute a Splunk search query using SPL (Search Processing Language) and get formatted results with analysis suggestions.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ Yes | - | SPL search query to execute. Examples: `'index=main error'`, `'search sourcetype=access_log \| stats count by host'` |
| `earliest_time` | string | No | "-24h" | Start time for search. Supports relative time (`'-24h'`, `'-1d'`, `'-7d'`) or absolute time (`'2023-01-01T00:00:00'`) |
| `latest_time` | string | No | "now" | End time for search. Use `'now'` for current time or absolute time (`'2023-01-02T00:00:00'`) |
| `max_results` | integer | No | 100 | Maximum number of results to return. Range: 1-10000 |
| `timeout` | integer | No | 300 | Search timeout in seconds. Range: 10-3600 |

### Returns
Formatted search results with analysis suggestions and metadata including:
- Search summary with query, time range, and result count
- Detailed results showing key fields (_time, _raw, host, source, sourcetype, index)
- Analysis suggestions for further investigation
- Error handling with clear messages

### Example Usage
```json
{
  "query": "index=main error | head 10",
  "earliest_time": "-1h",
  "max_results": 50
}
```

---

## 2. splunk_indexes

List and get information about Splunk indexes with filtering and sorting options.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `filter_pattern` | string | No | null | Optional pattern to filter index names (case-insensitive substring match). Example: `"web"` to find indexes containing "web" |
| `include_disabled` | boolean | No | true | Whether to include disabled indexes in the results |
| `sort_by` | string | No | "name" | Field to sort results by. Options: `'name'`, `'size'`, `'events'`, `'earliest'`, `'latest'` |
| `sort_order` | string | No | "asc" | Sort order. Options: `'asc'` (ascending) or `'desc'` (descending) |

### Returns
Comprehensive index information including:
- Total index count and summary statistics
- Individual index details (name, status, event count, size, time range)
- Usage suggestions for popular indexes
- Recommendations for index analysis

### Example Usage
```json
{
  "filter_pattern": "main",
  "sort_by": "events",
  "sort_order": "desc"
}
```

---

## 3. splunk_export

Export Splunk search results to various formats for data analysis and integration.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ Yes | - | SPL search query to execute and export results. Example: `'index=main \| stats count by host'` |
| `format` | string | No | "json" | Export format. Options: `'json'` (programmatic use), `'csv'` (spreadsheets), `'xml'` (structured data) |
| `earliest_time` | string | No | "-24h" | Start time for search. Supports relative time (`'-24h'`, `'-1d'`) or absolute time |
| `latest_time` | string | No | "now" | End time for search. Use `'now'` for current time or absolute time |
| `max_results` | integer | No | 1000 | Maximum number of results to export. Range: 1-50000 |
| `timeout` | integer | No | 300 | Search timeout in seconds. Range: 10-3600 |
| `fields` | array[string] | No | null | Specific fields to include in export. If not specified, exports all fields. Example: `["_time", "host", "message"]` |

### Returns
Exported data in the specified format with:
- Export summary (format, result count, data size)
- Preview of exported data
- Processing suggestions based on format
- Size optimization recommendations

### Example Usage
```json
{
  "query": "index=web_logs | stats count by status_code",
  "format": "csv",
  "max_results": 5000,
  "fields": ["status_code", "count"]
}
```

---

## 4. splunk_monitor

Start continuous monitoring of Splunk logs with specified intervals for real-time analysis. Only one monitoring session can be active at a time.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | ✅ Yes | - | Action to perform. Options: `'start'`, `'stop'`, `'status'`, `'get_results'` |
| `query` | string | Conditional | null | SPL search query to monitor. Required for `'start'` action. Example: `'index=main error \| head 100'` |
| `interval` | integer | No | 60 | Monitoring interval in seconds (how often to check for new data). Range: 10-3600 |
| `max_results` | integer | No | 1000 | Maximum results per monitoring check. Range: 1-10000 |
| `timeout` | integer | No | 60 | Search timeout in seconds for each monitoring check. Range: 10-300 |
| `clear_buffer` | boolean | No | true | Whether to clear results buffer after retrieving (for `get_results` action) |

### Actions Explained

#### start
- **Purpose**: Begin monitoring with a query and interval
- **Required Parameters**: `query`
- **Optional Parameters**: `interval`, `max_results`, `timeout`
- **Returns**: Confirmation of monitoring session start with parameters

#### stop
- **Purpose**: Stop the current monitoring session
- **Required Parameters**: None
- **Returns**: Confirmation of session stop

#### status
- **Purpose**: Get status of the current monitoring session
- **Required Parameters**: None
- **Returns**: Session details (query, interval, activity, buffer status)

#### get_results
- **Purpose**: Retrieve buffered results from the session
- **Optional Parameters**: `clear_buffer`
- **Returns**: Buffered monitoring results with analysis suggestions

### Returns
Depending on action:
- **start**: Session confirmation with parameters
- **stop**: Stop confirmation
- **status**: Detailed session status
- **get_results**: Buffered results grouped by check time with analysis

### Example Usage

**Start monitoring:**
```json
{
  "action": "start",
  "query": "index=security failed_login",
  "interval": 30,
  "max_results": 500
}
```

**Get results:**
```json
{
  "action": "get_results",
  "clear_buffer": true
}
```

**Check status:**
```json
{
  "action": "status"
}
```

---

## Common Parameter Patterns

### Time Specifications
- **Relative time**: `-1h`, `-24h`, `-1d`, `-7d`, `-30d`
- **Absolute time**: `2023-01-01T00:00:00`, `2023-12-31T23:59:59`
- **Special values**: `now`, `earliest`, `latest`

### SPL Query Examples
- Basic search: `index=main error`
- With stats: `index=web | stats count by status_code`
- With time chart: `index=app | timechart count`
- Complex query: `index=security sourcetype=auth | search action=failed | stats count by user`

### Best Practices
1. **Start with small time ranges** when testing queries
2. **Use specific indexes** to improve performance
3. **Limit results** with `max_results` for large datasets
4. **Include relevant fields** in export to reduce data size
5. **Monitor error patterns** with appropriate intervals
6. **Use filtering** for indexes to find relevant data sources

---

## Error Handling

All tools provide comprehensive error handling with clear messages for:
- **Connection errors**: Splunk server connectivity issues
- **Authentication errors**: Invalid credentials
- **Query syntax errors**: Invalid SPL syntax
- **Timeout errors**: Searches exceeding timeout limits
- **Parameter validation**: Invalid parameter values or ranges

Each error includes suggestions for resolution and troubleshooting steps.
