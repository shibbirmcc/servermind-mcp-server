#!/bin/bash

# Script to create an API token in your Splunk Docker container
# This script will help you set up token-based authentication

set -e

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

# Configuration
SPLUNK_CONTAINER=${1:-"splunk-local"}
TOKEN_NAME=${2:-"mcp-server-token"}

print_status "Creating Splunk API Token"
echo "=================================="
echo "Container: $SPLUNK_CONTAINER"
echo "Token Name: $TOKEN_NAME"
echo ""

# Check if container exists and is running
if ! docker ps --format 'table {{.Names}}' | grep -q "^${SPLUNK_CONTAINER}$"; then
    print_error "Splunk container '$SPLUNK_CONTAINER' is not running"
    echo ""
    echo "Available containers:"
    docker ps --format 'table {{.Names}}\t{{.Status}}'
    echo ""
    echo "Usage: $0 [container_name] [token_name]"
    echo "Example: $0 splunk-local mcp-server-token"
    exit 1
fi

print_status "Container found and running"

# Method 1: Create token via REST API
print_status "Creating API token via REST API..."

# Get the current admin credentials (you'll need to modify these)
SPLUNK_USERNAME="admin"
SPLUNK_PASSWORD="changeme123"
SPLUNK_HOST="localhost"
SPLUNK_PORT="8089"

echo ""
print_warning "This script will create an API token using your current admin credentials."
print_warning "Make sure the following credentials are correct:"
echo "  Username: $SPLUNK_USERNAME"
echo "  Password: $SPLUNK_PASSWORD"
echo "  Host: $SPLUNK_HOST"
echo "  Port: $SPLUNK_PORT"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Aborted by user"
    exit 0
fi

# Create the token
print_status "Creating token '$TOKEN_NAME'..."

TOKEN_RESPONSE=$(curl -k -s -u "$SPLUNK_USERNAME:$SPLUNK_PASSWORD" \
    -X POST \
    "https://$SPLUNK_HOST:$SPLUNK_PORT/services/authorization/tokens" \
    -d "name=$TOKEN_NAME" \
    -d "audience=Users" \
    -d "expires_on=+30d" 2>/dev/null || echo "FAILED")

if [[ "$TOKEN_RESPONSE" == "FAILED" ]] || [[ -z "$TOKEN_RESPONSE" ]]; then
    print_error "Failed to create token via REST API"
    print_status "Trying alternative method using docker exec..."
    
    # Method 2: Create token via CLI inside container
    print_status "Creating token using Splunk CLI inside container..."
    
    TOKEN_OUTPUT=$(docker exec -u splunk "$SPLUNK_CONTAINER" /opt/splunk/bin/splunk \
        auth-tokens create \
        -name "$TOKEN_NAME" \
        -description "MCP Server Authentication Token" \
        -audience "Users" \
        -expires-on "+30d" \
        -auth "admin:changeme123" 2>/dev/null || echo "FAILED")
    
    if [[ "$TOKEN_OUTPUT" == "FAILED" ]]; then
        print_error "Failed to create token using CLI method"
        echo ""
        print_status "Manual token creation steps:"
        echo "1. Access Splunk Web UI at http://localhost:8000"
        echo "2. Go to Settings > Tokens"
        echo "3. Click 'New Token'"
        echo "4. Set name: $TOKEN_NAME"
        echo "5. Set audience: Users"
        echo "6. Set expiration: 30 days"
        echo "7. Click 'Create'"
        echo "8. Copy the generated token"
        exit 1
    fi
    
    # Extract token from CLI output
    TOKEN=$(echo "$TOKEN_OUTPUT" | grep -o 'token=[^[:space:]]*' | cut -d'=' -f2 || echo "")
    
else
    # Extract token from REST API response
    TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '<s:key name="token">[^<]*</s:key>' | sed 's/<s:key name="token">\(.*\)<\/s:key>/\1/' || echo "")
fi

if [[ -z "$TOKEN" ]]; then
    print_error "Could not extract token from response"
    print_status "Raw response:"
    echo "$TOKEN_RESPONSE"
    echo ""
    print_status "Please create the token manually:"
    echo "1. Access Splunk Web UI at http://localhost:8000"
    echo "2. Go to Settings > Tokens"
    echo "3. Click 'New Token'"
    echo "4. Set name: $TOKEN_NAME"
    echo "5. Copy the generated token"
    exit 1
fi

print_success "API Token created successfully!"
echo ""
echo "=================================="
echo "🔑 Your Splunk API Token:"
echo "=================================="
echo "$TOKEN"
echo "=================================="
echo ""
print_warning "IMPORTANT: Save this token securely! It won't be shown again."
echo ""
print_status "You can now use this token with the MCP server:"
echo ""
echo "# Using the new docker script with token:"
echo "SPLUNK_HOST=localhost SPLUNK_TOKEN=$TOKEN ./docker-run-env.sh"
echo ""
echo "# Or export as environment variable:"
echo "export SPLUNK_HOST=localhost"
echo "export SPLUNK_TOKEN=$TOKEN"
echo "export SPLUNK_VERIFY_SSL=false"
echo "./docker-run-env.sh"
echo ""
print_status "Token details:"
echo "  Name: $TOKEN_NAME"
echo "  Audience: Users"
echo "  Expires: 30 days from now"
echo "  Container: $SPLUNK_CONTAINER"
