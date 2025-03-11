# Use Python 3.11 as the base image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Install git and Node.js
RUN apt-get update && \
    apt-get install -y git curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command (can be overridden)
CMD ["--help"]
