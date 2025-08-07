# Connecting Splunk MCP Server to Cline

This guide explains how to connect your Splunk MCP Server to Cline for AI-powered log analysis.

## Prerequisites

1. **Splunk Instance Running**: Ensure your Splunk instance is running on `localhost:8089`
2. **API Token Created**: You should have created a Splunk API token (see `SETUP_TOKEN_AUTH.md`)
3. **Docker Container Running**: The Splunk MCP server container should be running

## Step 1: Start the Splunk MCP Server Container (Persistent Mode)

Start the MCP server container in persistent mode so Cline can connect to it:

```bash
# Replace with your actual Splunk API token
SPLUNK_HOST=127.0.0.1 \
SPLUNK_TOKEN="eyJraWQiOiJzcGx1bmsuc2VjcmV0IiwiYWxnIjoiSFM1MTIiLCJ2ZXIiOiJ2MiIsInR0eXAiOiJzdGF0aWMifQ..." \
SPLUNK_VERIFY_SSL=false \
./docker-run-persistent.sh start
```

Verify the container is running:
```bash
docker ps | grep splunk-mcp-server
# Should show: Status "Up X seconds (healthy)"
```

**Important**: Use `docker-run-persistent.sh` instead of `docker-run-env.sh` for Cline integration!

## Step 2: Configure Cline MCP Settings

### Option A: Using Cline Settings UI (Recommended)

1. **Open Cline Settings**:
   - In VS Code, open the Command Palette (`Cmd/Ctrl + Shift + P`)
   - Type "Cline: Open Settings" and select it
   - Or click the gear icon in the Cline chat interface

2. **Navigate to MCP Settings**:
   - Look for "MCP Servers" or "Model Context Protocol" section
   - Click "Add Server" or "Configure MCP Servers"

3. **Add Splunk MCP Server**:
   - **Server Name**: `splunk-mcp-server`
   - **Command**: `docker`
   - **Arguments**: 
     ```json
     ["exec", "-i", "splunk-mcp-server", "python", "-m", "src.server"]
     ```
   - **Environment Variables**:
     ```json
     {
       "SPLUNK_HOST": "localhost",
       "SPLUNK_TOKEN": "your-actual-splunk-api-token-here",
       "SPLUNK_PORT": "8089",
       "SPLUNK_SCHEME": "https",
       "SPLUNK_VERIFY_SSL": "false",
       "SPLUNK_TIMEOUT": "30",
       "LOG_LEVEL": "INFO"
     }
     ```

### Option B: Manual Configuration File

1. **Locate Cline Configuration Directory**:
   - **macOS**: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/`
   - **Linux**: `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/`
   - **Windows**: `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\`

2. **Create or Edit MCP Configuration**:
   Create/edit the file `settings.json` in the Cline configuration directory:

   ```json
   {
     "mcpServers": {
       "splunk-mcp-server": {
         "command": "docker",
         "args": [
           "exec",
           "-i",
           "splunk-mcp-server",
           "python",
           "-m",
           "src.server"
         ],
         "env": {
           "SPLUNK_HOST": "localhost",
           "SPLUNK_TOKEN": "your-actual-splunk-api-token-here",
           "SPLUNK_PORT": "8089",
           "SPLUNK_SCHEME": "https",
           "SPLUNK_VERIFY_SSL": "false",
           "SPLUNK_TIMEOUT": "30",
           "LOG_LEVEL": "INFO"
         }
       }
     }
   }
   ```

## Step 3: Restart Cline

After configuring the MCP server:

1. **Restart VS Code** or **Reload Window**:
   - Command Palette → "Developer: Reload Window"
   - Or restart VS Code completely

2. **Verify Connection**:
   - Open a new Cline chat
   - The Splunk MCP server should appear in the available tools/resources
   - You should see tools like `splunk_search` available

## Step 4: Test the Connection

In a Cline chat, try asking:

```
Can you show me the available Splunk tools and check the connection status?
```

Cline should be able to:
- List the `splunk_search` tool
- Access the `splunk://connection-info` resource
- Show Splunk server information

## Available Tools and Resources

Once connected, Cline will have access to:

### Tools:
- **`splunk_search`**: Execute Splunk searches and retrieve logs
  - Parameters: `query`, `earliest_time`, `latest_time`, `max_results`
  - Example: Search for errors in the last hour

### Resources:
- **`splunk://connection-info`**: Splunk connection status and server info
- **`splunk://indexes`**: List of available Splunk indexes

## Example Usage

Ask Cline to help with log analysis:

```
"Search for all ERROR level logs in the last 24 hours and analyze the most common error patterns"

"Find all failed login attempts in the security index and show me the top source IPs"

"Look for any unusual network traffic patterns in the last hour"
```

## Troubleshooting

### Container Not Running
```bash
# Check if container is running
docker ps | grep splunk-mcp-server

# If not running, start it
SPLUNK_HOST=localhost SPLUNK_TOKEN="your-token" SPLUNK_VERIFY_SSL=false ./docker-run-env.sh
```

### Connection Issues
```bash
# Check container logs
docker logs splunk-mcp-server

# Test MCP server manually
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' | docker exec -i splunk-mcp-server python -m src.server
```

### Token Issues
- Verify your Splunk API token is valid
- Check token permissions in Splunk Web UI
- Ensure token hasn't expired

### Cline Not Detecting MCP Server
- Restart VS Code completely
- Check Cline logs in VS Code Developer Tools
- Verify the configuration file syntax is correct

## Security Notes

- **Never commit your actual Splunk API token to version control**
- **Use environment variables or secure configuration management**
- **Regularly rotate your API tokens**
- **Limit token permissions to only what's needed**

## Advanced Configuration

### Custom Search Timeouts
```json
{
  "env": {
    "MCP_SEARCH_TIMEOUT": "600",
    "MCP_MAX_RESULTS_DEFAULT": "500"
  }
}
```

### Debug Logging
```json
{
  "env": {
    "LOG_LEVEL": "DEBUG"
  }
}
```

### SSL Configuration
```json
{
  "env": {
    "SPLUNK_VERIFY_SSL": "true",
    "SPLUNK_SCHEME": "https"
  }
}
```

---

Once configured, you'll have powerful AI-assisted log analysis capabilities directly in Cline! 🚀
