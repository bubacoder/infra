#!/usr/bin/env bash
# Sets up a uv virtual environment, installs dependencies, and starts the Infra MCP server.
set -e

# Change to script directory
cd "$(dirname "$0")"

# Check if virtual environment exists, create if it doesn't
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install or update dependencies
echo "Installing dependencies..."
uv sync

# Start the MCP server
echo "Starting Infra MCP server..."
fastmcp run server.py --transport http --host 127.0.0.1 --port 9876
