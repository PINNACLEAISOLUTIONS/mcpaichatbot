FROM python:3.11-slim

# Install Node.js (required for filesystem MCP server)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build Nanobanana MCP server
RUN if [ -d "nanobanana-server/mcp-server" ]; then \
    cd nanobanana-server/mcp-server && \
    npm install && \
    npm run build && \
    echo "Checking build output" && \
    ls -la && \
    ls -la dist || true && \
    test -f dist/index.js || (echo "Missing dist/index.js. Build output path is different or build failed." && exit 1); \
    fi

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Start command
CMD gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
