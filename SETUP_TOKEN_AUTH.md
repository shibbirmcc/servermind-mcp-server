# Splunk API Token Authentication Setup Guide

This guide will help you set up API token authentication for your Splunk MCP Server instead of using username/password authentication.

## Why Use API Tokens?

- **Security**: Tokens can be scoped and have expiration dates
- **Auditing**: Better tracking of API usage
- **Rotation**: Easier to rotate without changing passwords
- **Best Practice**: Recommended by Splunk for API access

## Prerequisites

- Splunk container running (e.g., `splunk-local`)
- Admin access to Splunk
- Docker installed and running

## Step 1: Create API Token

### Option A: Automated Script (Recommended)

Use the provided script to create a token automatically:

```bash
# Create token for your Splunk container
./create-splunk-token.sh splunk-local mcp-server-token
```

The script will:
1. Verify your Splunk container is running
2. Create an API token using REST API or CLI
3. Display the token for you to copy

### Option B: Manual Creation via Web UI

1. Open Splunk Web UI: http://localhost:8000
2. Login with admin credentials (admin/changeme123)
3. Go to **Settings** > **Tokens**
4. Click **New Token**
5. Fill in the details:
   - **Token Name**: `mcp-server-token`
   - **Audience**: `Users`
   - **Expires On**: `+30d` (30 days from now)
6. Click **Create**
7. **Copy the token immediately** (it won't be shown again)

### Option C: Manual Creation via CLI

```bash
# Execute inside your Splunk container
docker exec -it splunk-local /opt/splunk/bin/splunk auth-tokens create \
  -name "mcp-server-token" \
  -description "MCP Server Authentication Token" \
  -audience "Users" \
  -expires-on "+30d" \
  -auth "admin:changeme123"
```

## Step 2: Test Token Authentication

Test your token with a simple curl command:

```bash
# Replace YOUR_TOKEN with the actual token
curl -k -H "Authorization: Bearer YOUR_TOKEN" \
  https://localhost:8089/services/server/info
```

If successful, you'll see XML response with server information.

## Step 3: Run MCP Server with Token

### Using the New Docker Script

```bash
# Set environment variables and run
SPLUNK_HOST=localhost \
SPLUNK_TOKEN=YOUR_TOKEN \
SPLUNK_VERIFY_SSL=false \
./docker-run-env.sh
```

### Using Environment Variables

```bash
# Export variables
export SPLUNK_HOST=localhost
export SPLUNK_TOKEN=YOUR_TOKEN
export SPLUNK_VERIFY_SSL=false
export LOG_LEVEL=DEBUG

# Run the container
./docker-run-env.sh
```

### Using Docker Run Directly

```bash
docker run -d \
  --name splunk-mcp-server \
  -e SPLUNK_HOST=localhost \
  -e SPLUNK_TOKEN=YOUR_TOKEN \
  -e SPLUNK_VERIFY_SSL=false \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  splunk-mcp-server
```

## Step 4: Verify MCP Server

Check the container logs to ensure it's working:

```bash
# View logs
./docker-run-env.sh logs

# Or directly
docker logs splunk-mcp-server
```

You should see successful connection messages like:
```
Connected to Splunk successfully version=10.0.0 build=e8eb0c4654f8
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SPLUNK_HOST` | Splunk server hostname/IP | `localhost` |
| `SPLUNK_TOKEN` | API token for authentication | `eyJraWQiOiJzcGx1bms...` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPLUNK_PORT` | `8089` | Splunk management port |
| `SPLUNK_SCHEME` | `https` | Connection scheme |
| `SPLUNK_VERIFY_SSL` | `true` | SSL certificate verification |
| `SPLUNK_TIMEOUT` | `30` | Connection timeout (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Token Management

### List Existing Tokens

```bash
# Via Web UI: Settings > Tokens
# Via CLI:
docker exec -it splunk-local /opt/splunk/bin/splunk auth-tokens list -auth "admin:changeme123"
```

### Revoke Token

```bash
# Via Web UI: Settings > Tokens > Delete
# Via CLI:
docker exec -it splunk-local /opt/splunk/bin/splunk auth-tokens delete \
  -name "mcp-server-token" -auth "admin:changeme123"
```

### Rotate Token

1. Create a new token with a different name
2. Update your MCP server configuration
3. Test the new token
4. Revoke the old token

## Troubleshooting

### Token Not Working

1. **Check token format**: Should start with `eyJ`
2. **Verify expiration**: Tokens expire after set time
3. **Check permissions**: Token user needs search permissions
4. **SSL issues**: Set `SPLUNK_VERIFY_SSL=false` for self-signed certs

### Connection Issues

```bash
# Test direct connection
curl -k -H "Authorization: Bearer YOUR_TOKEN" \
  https://localhost:8089/services/server/info

# Check container connectivity
docker exec -it splunk-mcp-server ping splunk-local
```

### Container Issues

```bash
# Check container status
docker ps -a

# View detailed logs
docker logs splunk-mcp-server --tail 50

# Open shell in container
./docker-run-env.sh shell
```

## Security Best Practices

1. **Use tokens instead of passwords** for API access
2. **Set appropriate expiration dates** (30-90 days)
3. **Store tokens securely** (environment variables, secrets management)
4. **Rotate tokens regularly**
5. **Monitor token usage** in Splunk audit logs
6. **Revoke unused tokens**

## Example Complete Setup

```bash
# 1. Create token
./create-splunk-token.sh splunk-local mcp-server-token

# 2. Copy the token output, then run:
export SPLUNK_HOST=localhost
export SPLUNK_TOKEN="eyJraWQiOiJzcGx1bms..."  # Your actual token
export SPLUNK_VERIFY_SSL=false

# 3. Run MCP server
./docker-run-env.sh

# 4. Verify it's working
./docker-run-env.sh logs
```

## Migration from Username/Password

If you're currently using username/password authentication:

1. Create an API token (steps above)
2. Test the token works
3. Update your environment variables:
   - Remove: `SPLUNK_USERNAME`, `SPLUNK_PASSWORD`
   - Add: `SPLUNK_TOKEN`
4. Restart your MCP server container
5. Verify the connection works

The MCP server will automatically detect and use token authentication when `SPLUNK_TOKEN` is provided.
