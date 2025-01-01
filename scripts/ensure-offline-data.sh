#!/usr/bin/env bash
set -euo pipefail

ollama_pull() {
  docker exec ollama ollama pull "$1"
}

ollama_pull llama3.2:latest
ollama_pull qwen2.5-coder:7b

# Embedding models - https://ollama.com/search?c=embedding
ollama_pull nomic-embed-text
