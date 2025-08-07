FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY pyproject.toml .
COPY README.md .

# Install the package
RUN pip install -e .

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Set environment variables with defaults
ENV SPLUNK_HOST=""
ENV SPLUNK_PORT=8089
ENV SPLUNK_TOKEN=""
ENV SPLUNK_SCHEME=https
ENV SPLUNK_VERIFY_SSL=true
ENV SPLUNK_TIMEOUT=30
ENV MCP_SERVER_NAME=splunk-mcp-server
ENV MCP_VERSION=1.0.0
ENV MCP_MAX_RESULTS_DEFAULT=100
ENV MCP_SEARCH_TIMEOUT=300
ENV LOG_LEVEL=INFO

# Expose port (though MCP uses stdio, this is for potential future HTTP support)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, 'src'); from src.config import get_config; get_config()" || exit 1

# Default command
CMD ["python", "-m", "src.server"]
