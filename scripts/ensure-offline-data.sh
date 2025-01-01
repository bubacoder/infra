#!/usr/bin/env bash
set -euo pipefail

error() {
  echo "Error: $1" >&2
  exit 1
}

ollama_pull() {
  if [ -z "$1" ]; then
    error "Model name is required"
  fi

  # Check if ollama container is running
  if ! docker ps --format '{{.Names}}' | grep -q '^ollama$'; then
    error "Ollama container is not running"
  fi

  docker exec ollama ollama pull "$1"
}


ollama_pull llama3.2:latest
ollama_pull qwen2.5-coder:7b

# Embedding models - https://ollama.com/search?c=embedding
ollama_pull nomic-embed-text
