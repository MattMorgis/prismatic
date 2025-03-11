#!/bin/bash

# Check required environment variables
if [ -z "$ANTHROPIC_API_KEY" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: Required environment variables are not set"
    echo "Please set:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - GITHUB_TOKEN"
    exit 1
fi

# Create secrets file from environment variables
cat > mcp_agent.secrets.yaml << EOL
anthropic:
  api_key: "${ANTHROPIC_API_KEY}"
mcp:
  servers:
    github:
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
EOL

# Execute the main program with arguments
exec uv run main.py "$@"
