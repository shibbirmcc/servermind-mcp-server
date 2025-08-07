#!/bin/bash

# Build and run the Splunk MCP Server Docker container with runtime environment variables
# This script allows you to pass environment variables at runtime instead of using .env files

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
    echo "  SPLUNK_HOST=localhost SPLUNK_TOKEN=your-token $0"
    echo ""
    echo "  # With additional options:"
    echo "  SPLUNK_HOST=splunk.company.com SPLUNK_TOKEN=your-token SPLUNK_VERIFY_SSL=false LOG_LEVEL=DEBUG $0"
    echo ""
    echo "Commands:"
    echo "  build    - Only build the Docker image"
    echo "  run      - Build and run the container (default)"
    echo "  stop     - Stop the running container"
    echo "  logs     - Show container logs"
    echo "  shell    - Open shell in running container"
    echo "  clean    - Stop and remove container and image"
}

# Parse command
COMMAND=${1:-"run"}

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

# Run container
run_container() {
    print_status "Starting container: $CONTAINER_NAME"
    
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
    
    # Run container
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p 8000:8000 \
        $ENV_ARGS \
        "$IMAGE_NAME"
    
    # Check if container started successfully
    sleep 2
    if docker ps --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_success "Container started successfully!"
        echo ""
        echo "Container Details:"
        echo "  Name: $CONTAINER_NAME"
        echo "  Image: $IMAGE_NAME"
        echo "  Status: Running"
        echo "  Splunk Host: $SPLUNK_HOST"
        echo "  Authentication: Token"
        echo ""
        echo "Useful Commands:"
        echo "  View logs: $0 logs"
        echo "  Open shell: $0 shell"
        echo "  Stop container: $0 stop"
        echo ""
        echo "To connect via MCP, use stdio transport with:"
        echo "  docker exec -i $CONTAINER_NAME python -m src.server"
    else
        print_error "Failed to start container"
        echo "Check the logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi
}

# Main command handling
case $COMMAND in
    "build")
        build_image
        ;;
    
    "run")
        validate_env
        cleanup_container
        build_image
        run_container
        ;;
    
    "stop")
        print_status "Stopping container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" 2>/dev/null || print_warning "Container not running"
        docker rm "$CONTAINER_NAME" 2>/dev/null || print_warning "Container not found"
        print_success "Container stopped and removed"
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
