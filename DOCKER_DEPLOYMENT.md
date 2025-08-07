# Docker Deployment Guide for Splunk MCP Server

This guide provides comprehensive instructions for deploying the Splunk MCP Server using Docker, specifically configured for use with Cline and other MCP clients.

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd splunk-mcp-server
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Splunk credentials
   nano .env
   ```

3. **Deploy with Docker**
   ```bash
   ./docker-run.sh run
   ```

## Environment Configuration

### Required Environment Variables

Edit the `.env` file with your Splunk connection details:

```bash
# Required: Splunk server connection
SPLUNK_HOST=your-splunk-host.com
SPLUNK_USERNAME=your-username
SPLUNK_PASSWORD=your-password

# Optional: Connection settings
SPLUNK_PORT=8089
SPLUNK_SCHEME=https
SPLUNK_VERIFY_SSL=false  # Set to false for self-signed certificates
SPLUNK_TIMEOUT=30

# Optional: MCP server settings
MCP_SERVER_NAME=splunk-mcp-server
MCP_MAX_RESULTS_DEFAULT=100
MCP_SEARCH_TIMEOUT=300
LOG_LEVEL=INFO
```

### Security Notes

- The `.env` file is automatically excluded from Git via `.gitignore`
- Never commit sensitive credentials to version control
- Use strong passwords and consider using service accounts for Splunk access
- Set `SPLUNK_VERIFY_SSL=false` only for development environments with self-signed certificates

## Docker Commands

### Using the Deployment Script

The `docker-run.sh` script provides convenient commands:

```bash
# Build the Docker image
./docker-run.sh build

# Start the MCP server
./docker-run.sh run

# Run tests
./docker-run.sh test

# View logs
./docker-run.sh logs

# Stop the server
./docker-run.sh stop

# Restart the server
./docker-run.sh restart

# Check health status
./docker-run.sh health

# Open shell in container
./docker-run.sh shell

# Clean up Docker resources
./docker-run.sh clean
```

### Using Docker Compose Directly

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Run tests
docker-compose --profile test up --build splunk-mcp-test
```

### Using Docker Directly

```bash
# Build image
docker build -t splunk-mcp-server .

# Run with environment file
docker run --rm -i --env-file .env splunk-mcp-server

# Run with individual environment variables
docker run --rm -i \
  -e SPLUNK_HOST=your-host \
  -e SPLUNK_USERNAME=your-user \
  -e SPLUNK_PASSWORD=your-pass \
  splunk-mcp-server
```

## Cline Integration

### Configuration for Cline

To use the Dockerized MCP server with Cline, add this configuration to your MCP client settings:

#### Option 1: Using Docker Run

```json
{
  "mcpServers": {
    "splunk": {
      "command": "docker",
      "args": [
        "run", 
        "--rm", 
        "-i",
        "--env-file", "/absolute/path/to/splunk-mcp-server/.env",
        "splunk-mcp-server"
      ]
    }
  }
}
```

#### Option 2: Using Docker Compose

```json
{
  "mcpServers": {
    "splunk": {
      "command": "docker-compose",
      "args": [
        "-f", "/absolute/path/to/splunk-mcp-server/docker-compose.yml",
        "run", "--rm", "splunk-mcp-server"
      ],
      "cwd": "/absolute/path/to/splunk-mcp-server"
    }
  }
}
```

#### Option 3: Using the Deployment Script

```json
{
  "mcpServers": {
    "splunk": {
      "command": "/absolute/path/to/splunk-mcp-server/docker-run.sh",
      "args": ["run"],
      "cwd": "/absolute/path/to/splunk-mcp-server"
    }
  }
}
```

**Important**: Replace `/absolute/path/to/splunk-mcp-server` with the actual absolute path to your project directory.

## Container Features

### Security
- Runs as non-root user (`mcpuser`)
- Minimal base image (Python 3.10 slim)
- No unnecessary packages installed
- Environment variables for sensitive data

### Resource Management
- Memory limit: 512MB
- CPU limit: 0.5 cores
- Automatic restart policy
- Health checks included

### Monitoring
- Built-in health checks
- Structured logging with configurable levels
- Container status monitoring
- Resource usage tracking

## Troubleshooting

### Common Issues

1. **Container fails to start**
   ```bash
   # Check logs
   ./docker-run.sh logs
   
   # Verify environment variables
   ./docker-run.sh health
   ```

2. **Splunk connection errors**
   ```bash
   # Test connectivity from container
   ./docker-run.sh shell
   # Inside container:
   ping your-splunk-host.com
   curl -k https://your-splunk-host.com:8089
   ```

3. **Permission errors**
   ```bash
   # Ensure .env file is readable
   chmod 644 .env
   
   # Check Docker permissions
   docker ps
   ```

4. **MCP client connection issues**
   - Verify absolute paths in MCP client configuration
   - Ensure Docker is accessible from the MCP client environment
   - Check that the container starts successfully with `docker run`

### Debug Mode

Enable debug logging:

```bash
# In .env file
LOG_LEVEL=DEBUG

# Restart container
./docker-run.sh restart
```

### Health Checks

The container includes built-in health checks:

```bash
# Check container health
docker ps
# Look for "healthy" status

# Manual health check
./docker-run.sh health
```

## Performance Optimization

### Resource Tuning

Adjust resource limits in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 1G        # Increase for large result sets
      cpus: '1.0'       # Increase for complex queries
    reservations:
      memory: 512M
      cpus: '0.5'
```

### Query Optimization

The server includes built-in query cost estimation and optimization suggestions:

- Use specific index and sourcetype filters
- Limit time ranges for better performance
- Use `head` or `tail` commands to limit results
- Avoid expensive operations like joins when possible

## Production Deployment

### Recommendations

1. **Use specific image tags**
   ```bash
   docker build -t splunk-mcp-server:1.0.0 .
   ```

2. **Set up log rotation**
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

3. **Use secrets management**
   ```yaml
   secrets:
     splunk_password:
       external: true
   ```

4. **Monitor resource usage**
   ```bash
   docker stats splunk-mcp-server
   ```

5. **Regular updates**
   ```bash
   # Rebuild with latest dependencies
   ./docker-run.sh build --no-cache
   ```

## Support

For issues with Docker deployment:

1. Check the container logs: `./docker-run.sh logs`
2. Verify environment configuration: `./docker-run.sh health`
3. Test Splunk connectivity from the container
4. Review the main README.md for general troubleshooting
5. Create an issue with logs and configuration details (excluding sensitive data)

## Version Information

- Docker Image: `splunk-mcp-server:latest`
- Base Image: `python:3.10-slim`
- MCP Server Version: 1.0.0
- Supported Architectures: linux/amd64, linux/arm64
