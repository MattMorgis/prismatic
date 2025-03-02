#!/bin/bash

# Docker permissions
sudo chown root:docker /var/run/docker.sock

# Update PATH first so we use the right pip consistently
export PATH="/home/vscode/.local/bin:$PATH"

python -m pip install --user --upgrade pip
# python -m pip install --user hatch

# Create hatch environment
# echo "Creating hatch environment..."
# hatch env create

# Copy starship config
if [ -f ".devcontainer/starship.toml" ]; then
    mkdir -p ~/.config
    cp .devcontainer/starship.toml ~/.config/starship.toml
fi

# Copy mcp_agent.secrets.yaml.example file if it doesn't exist
if [ ! -f "mcp_agent.secrets.yaml" ] && [ -f "mcp_agent.secrets.yaml.example" ]; then
    echo "Creating mcp_agent.secrets.yaml file from mcp_agent.secrets.yaml.example"
    cp mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml
fi

# Install Claude Code
npm install -g @anthropic-ai/claude-code

echo "✅ Setup complete. Please open a new terminal to apply changes."
