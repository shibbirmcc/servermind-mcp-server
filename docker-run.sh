#!/bin/bash

# Docker deployment script for Splunk MCP Server
# This script builds and runs the MCP server in a Docker container using direct Docker commands

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

# Function to print colored output
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

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_warning "Please edit .env file with your Splunk credentials before running the container."
        print_warning "Required variables: SPLUNK_HOST, SPLUNK_USERNAME, SPLUNK_PASSWORD"
        exit 1
    else
        print_error ".env.example file not found. Cannot create .env file."
        exit 1
    fi
fi

# Validate required environment variables
print_status "Validating environment variables..."
source .env

if [ -z "$SPLUNK_HOST" ] || [ "$SPLUNK_HOST" = "your-splunk-host.com" ]; then
    print_error "SPLUNK_HOST is not set or still has default value. Please update .env file."
    exit 1
fi

if [ -z "$SPLUNK_USERNAME" ] || [ "$SPLUNK_USERNAME" = "your-username-here" ]; then
    print_error "SPLUNK_USERNAME is not set or still has default value. Please update .env file."
    exit 1
fi

if [ -z "$SPLUNK_PASSWORD" ] || [ "$SPLUNK_PASSWORD" = "your-password-here" ]; then
    print_error "SPLUNK_PASSWORD is not set or still has default value. Please update .env file."
    exit 1
fi

print_success "Environment variables validated."

# Build Docker image
build_image() {
    print_status "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME" .
    print_success "Docker image built successfully."
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
    print_status "Starting Splunk MCP Server container..."
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        --network host \
        -p 9090:9090 \
        --env-file .env \
        "$IMAGE_NAME"
    
    # Check if container started successfully
    sleep 2
    if docker ps --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_success "Splunk MCP Server started successfully!"
        echo ""
        echo "Container Details:"
        echo "  Name: $CONTAINER_NAME"
        echo "  Image: $IMAGE_NAME"
        echo "  Status: Running"
        echo "  SSE Transport: http://localhost:9090"
        echo ""
        print_status "Container logs:"
        docker logs -f "$CONTAINER_NAME"
    else
        print_error "Failed to start container"
        echo "Check the logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi
}

# Parse command line arguments
COMMAND=${1:-"run"}

case $COMMAND in
    "build")
        build_image
        ;;
    
    "run")
        cleanup_container
        build_image
        run_container
        ;;
    
    "test")
        print_status "Running tests in container..."
        cleanup_container
        build_image
        docker run --rm \
            --network host \
            --env-file .env \
            "$IMAGE_NAME" \
            python -m pytest tests/ -v
        ;;
    
    "stop")
        print_status "Stopping Splunk MCP Server..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || print_warning "Container not running"
        docker rm "$CONTAINER_NAME" 2>/dev/null || print_warning "Container not found"
        print_success "Splunk MCP Server stopped."
        ;;
    
    "restart")
        print_status "Restarting Splunk MCP Server..."
        cleanup_container
        build_image
        run_container
        ;;
    
    "logs")
        print_status "Showing container logs..."
        docker logs -f "$CONTAINER_NAME"
        ;;
    
    "shell")
        print_status "Opening shell in container..."
        docker exec -it "$CONTAINER_NAME" /bin/bash
        ;;
    
    "clean")
        print_status "Cleaning up Docker resources..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        docker rmi "$IMAGE_NAME" 2>/dev/null || true
        docker system prune -f
        print_success "Docker resources cleaned up."
        ;;
    
    "health")
        print_status "Checking container health..."
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|$CONTAINER_NAME)" || echo "Container not found"
        if docker ps --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            docker exec "$CONTAINER_NAME" python -c "
import sys
sys.path.insert(0, 'src')
from src.config import get_config
try:
    config = get_config()
    print('✓ Configuration loaded successfully')
    print(f'✓ Splunk host: {config.splunk.host}')
    print(f'✓ Splunk port: {config.splunk.port}')
    print(f'✓ MCP server: {config.mcp.server_name}')
    print('✓ SSE transport: http://localhost:9090')
except Exception as e:
    print(f'✗ Health check failed: {e}')
    sys.exit(1)
"
        else
            print_warning "Container is not running"
        fi
        ;;
    
    *)
        echo "Usage: $0 {build|run|test|stop|restart|logs|shell|clean|health}"
        echo ""
        echo "Commands:"
        echo "  build    - Build the Docker image"
        echo "  run      - Start the MCP server (default)"
        echo "  test     - Run the test suite"
        echo "  stop     - Stop the MCP server"
        echo "  restart  - Restart the MCP server"
        echo "  logs     - Show container logs"
        echo "  shell    - Open shell in container"
        echo "  clean    - Clean up Docker resources"
        echo "  health   - Check container health"
        echo ""
        echo "Examples:"
        echo "  $0 run          # Start the server"
        echo "  $0 test         # Run tests"
        echo "  $0 logs         # View logs"
        echo ""
        echo "SSE Transport will be available at: http://localhost:9090"
        exit 1
        ;;
esac
