#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$(dirname "$SCRIPT_DIR")"
TARGET="$(dirname "$SCRIPT_DIR")/../../repo-template"

# List of files to copy
files_to_copy=(
  # Git
  ".gitattributes"
  ".gitignore"

  # Linting
  ".pre-commit-config.yaml"
  ".editorconfig"
  ".shellcheckrc"
  ".terraform-docs.yml"
  ".yamllint.yml"
  "ruff.toml"

  # VS Code
  ".vscode/extensions.json"
  ".devcontainer/minimal/devcontainer.json"

  # Claude Code
  ".claude/settings.json"
  ".mcp.json"
)

# Copy each file, preserving directory structure
for file in "${files_to_copy[@]}"; do
  echo "$file"
  src="$SOURCE/$file"
  dst="$TARGET/$file"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
done
