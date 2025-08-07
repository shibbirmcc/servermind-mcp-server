#!/bin/bash

# Build and run the Splunk MCP Server Docker container in persistent mode for Cline integration
# This version keeps the container running so Cline can connect to it

set -e

# Configuration
IMAGE_NAME="splunk-mcp-server"
CONTAINER_NAME="splunk-mcp-server"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Environment Variables (required):"
    echo "  SPLUNK_HOST        - Splunk server hostname/IP"
    echo "  SPLUNK_TOKEN       - Splunk API token"
    echo ""
    echo "Optional Environment Variables:"
    echo "  SPLUNK_PORT        - Splunk management port (default: 8089)"
    echo "  SPLUNK_SCHEME      - http or https (default: https)"
    echo "  SPLUNK_VERIFY_SSL  - true or false (default: true)"
    echo "  SPLUNK_TIMEOUT     - Connection timeout (default: 30)"
    echo "  LOG_LEVEL          - DEBUG, INFO, WARNING, ERROR (default: INFO)"
    echo ""
    echo "Examples:"
    echo "  # Basic usage with API token:"
    echo "  SPLUNK_HOST=127.0.0.1 SPLUNK_TOKEN=your-token $0"
    echo ""
    echo "Commands:"
    echo "  start    - Build and start the persistent container (default)"
    echo "  stop     - Stop the running container"
    echo "  restart  - Restart the container"
    echo "  logs     - Show container logs"
    echo "  status   - Show container status"
    echo "  shell    - Open shell in running container"
    echo "  clean    - Stop and remove container and image"
}

# Parse command
COMMAND=${1:-"start"}

# Validate required environment variables
validate_env() {
    if [ -z "$SPLUNK_HOST" ]; then
        print_error "SPLUNK_HOST environment variable is required"
        show_usage
        exit 1
    fi

    if [ -z "$SPLUNK_TOKEN" ]; then
        print_error "SPLUNK_TOKEN environment variable is required"
        show_usage
        exit 1
    fi

    print_success "Environment variables validated"
}

# Build Docker image
build_image() {
    print_status "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME" .
    print_success "Docker image built successfully"
}

# Stop and remove existing container
cleanup_container() {
    if docker ps -a --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_status "Stopping and removing existing container..."
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
}

# Run container in persistent mode
run_persistent_container() {
    print_status "Starting persistent container: $CONTAINER_NAME"
    
    # Build environment variable arguments
    ENV_ARGS=""
    ENV_ARGS="$ENV_ARGS -e SPLUNK_HOST=$SPLUNK_HOST"
    ENV_ARGS="$ENV_ARGS -e SPLUNK_PORT=${SPLUNK_PORT:-8089}"
    ENV_ARGS="$ENV_ARGS -e SPLUNK_SCHEME=${SPLUNK_SCHEME:-https}"
    ENV_ARGS="$ENV_ARGS -e SPLUNK_VERIFY_SSL=${SPLUNK_VERIFY_SSL:-true}"
    ENV_ARGS="$ENV_ARGS -e SPLUNK_TIMEOUT=${SPLUNK_TIMEOUT:-30}"
    ENV_ARGS="$ENV_ARGS -e LOG_LEVEL=${LOG_LEVEL:-INFO}"
    
    # Add authentication variables
    ENV_ARGS="$ENV_ARGS -e SPLUNK_TOKEN=$SPLUNK_TOKEN"
    print_status "Using token authentication"
    
    # Add MCP configuration
    ENV_ARGS="$ENV_ARGS -e MCP_SERVER_NAME=${MCP_SERVER_NAME:-splunk-mcp-server}"
    ENV_ARGS="$ENV_ARGS -e MCP_VERSION=${MCP_VERSION:-1.0.0}"
    ENV_ARGS="$ENV_ARGS -e MCP_MAX_RESULTS_DEFAULT=${MCP_MAX_RESULTS_DEFAULT:-100}"
    ENV_ARGS="$ENV_ARGS -e MCP_SEARCH_TIMEOUT=${MCP_SEARCH_TIMEOUT:-300}"
    
    # Run container in persistent mode (keeps running)
    docker run -d \
        --name "$CONTAINER_NAME" \
        --network host \
        $ENV_ARGS \
        "$IMAGE_NAME" \
        tail -f /dev/null
    
    # Check if container started successfully
    sleep 2
    if docker ps --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_success "Persistent container started successfully!"
        echo ""
        echo "Container Details:"
        echo "  Name: $CONTAINER_NAME"
        echo "  Image: $IMAGE_NAME"
        echo "  Status: Running (persistent mode)"
        echo "  Splunk Host: $SPLUNK_HOST"
        echo "  Authentication: Token"
        echo ""
        echo "Cline Integration:"
        echo "  The container is now running and ready for Cline to connect"
        echo "  Cline will execute: docker exec -i $CONTAINER_NAME python -m src.server"
        echo ""
        echo "Useful Commands:"
        echo "  View logs: $0 logs"
        echo "  Check status: $0 status"
        echo "  Open shell: $0 shell"
        echo "  Stop container: $0 stop"
    else
        print_error "Failed to start persistent container"
        echo "Check the logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi
}

# Main command handling
case $COMMAND in
    "start")
        validate_env
        cleanup_container
        build_image
        run_persistent_container
        ;;
    
    "stop")
        print_status "Stopping container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" 2>/dev/null || print_warning "Container not running"
        docker rm "$CONTAINER_NAME" 2>/dev/null || print_warning "Container not found"
        print_success "Container stopped and removed"
        ;;
    
    "restart")
        validate_env
        print_status "Restarting container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        run_persistent_container
        ;;
    
    "status")
        print_status "Container status:"
        docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|$CONTAINER_NAME)" || echo "Container not found"
        ;;
    
    "logs")
        print_status "Showing logs for: $CONTAINER_NAME"
        docker logs -f "$CONTAINER_NAME"
        ;;
    
    "shell")
        print_status "Opening shell in: $CONTAINER_NAME"
        docker exec -it "$CONTAINER_NAME" /bin/bash
        ;;
    
    "clean")
        print_status "Cleaning up Docker resources..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        docker rmi "$IMAGE_NAME" 2>/dev/null || true
        print_success "Cleanup completed"
        ;;
    
    "help"|"-h"|"--help")
        show_usage
        ;;
    
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
