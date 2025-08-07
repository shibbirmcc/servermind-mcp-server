#!/bin/bash

# Docker deployment script for Splunk MCP Server
# This script builds and runs the MCP server in a Docker container

set -e

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

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
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

if [ -z "$SPLUNK_USERNAME" ] || [ "$SPLUNK_USERNAME" = "admin" ]; then
    print_warning "SPLUNK_USERNAME is not set or using default 'admin'. Please verify this is correct."
fi

if [ -z "$SPLUNK_PASSWORD" ] || [ "$SPLUNK_PASSWORD" = "changeme" ]; then
    print_error "SPLUNK_PASSWORD is not set or still has default value. Please update .env file."
    exit 1
fi

print_success "Environment variables validated."

# Parse command line arguments
COMMAND=${1:-"run"}
PROFILE=${2:-""}

case $COMMAND in
    "build")
        print_status "Building Docker image..."
        docker-compose build
        print_success "Docker image built successfully."
        ;;
    
    "run")
        print_status "Starting Splunk MCP Server..."
        docker-compose up -d
        print_success "Splunk MCP Server started."
        print_status "Container logs:"
        docker-compose logs -f
        ;;
    
    "test")
        print_status "Running tests..."
        docker-compose --profile test up --build splunk-mcp-test
        ;;
    
    "stop")
        print_status "Stopping Splunk MCP Server..."
        docker-compose down
        print_success "Splunk MCP Server stopped."
        ;;
    
    "restart")
        print_status "Restarting Splunk MCP Server..."
        docker-compose down
        docker-compose up -d
        print_success "Splunk MCP Server restarted."
        ;;
    
    "logs")
        print_status "Showing container logs..."
        docker-compose logs -f
        ;;
    
    "shell")
        print_status "Opening shell in container..."
        docker-compose exec splunk-mcp-server /bin/bash
        ;;
    
    "clean")
        print_status "Cleaning up Docker resources..."
        docker-compose down -v --remove-orphans
        docker system prune -f
        print_success "Docker resources cleaned up."
        ;;
    
    "health")
        print_status "Checking container health..."
        docker-compose ps
        docker-compose exec splunk-mcp-server python -c "
import sys
sys.path.insert(0, 'src')
from src.config import get_config
try:
    config = get_config()
    print('✓ Configuration loaded successfully')
    print(f'✓ Splunk host: {config.splunk.host}')
    print(f'✓ Splunk port: {config.splunk.port}')
    print(f'✓ MCP server: {config.mcp.server_name}')
except Exception as e:
    print(f'✗ Health check failed: {e}')
    sys.exit(1)
"
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
        exit 1
        ;;
esac
