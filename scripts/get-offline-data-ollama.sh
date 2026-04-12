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

# Large Language Models - https://ollama.com/search
ollama_pull phi4-mini    # 3.8B - best-in-class sub-4B; 128K ctx
ollama_pull qwen3:8b     # 8B   - best-in-class 7-8B; hybrid thinking, top HumanEval

# Embedding Models - https://ollama.com/search?c=embedding
ollama_pull nomic-embed-text
