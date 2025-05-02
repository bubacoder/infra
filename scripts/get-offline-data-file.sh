#!/usr/bin/env bash
set -euo pipefail

# Validate that target directory, URL, and pattern are provided
if [[ $# -ne 3 ]]; then
  echo >&2 "Error: You must provide a target directory, a URL, and a pattern."
  echo "Usage: $0 <directory-path> <url> <pattern>"
  exit 1
fi

# Assign parameters
TARGET_DIR="$1"
URL="$2"
PATTERN="$3"

# Check if the target directory exists
if [[ ! -d "$TARGET_DIR" ]]; then
  echo >&2 "Error: The specified directory '$TARGET_DIR' does not exist."
  exit 1
fi

cd "$TARGET_DIR"

# Function to download the latest file matching the pattern
download_latest_file() {
  local url="$1"
  local pattern="$2"
  local HTML FILES LATEST_FILE

  echo -e "\n==> Fetching webpage content from $url..."
  if ! HTML=$(wget -qO- "$url"); then
    echo "Failed to fetch the webpage content from $url. Exiting."
    return 1
  fi

  echo "Finding files matching the pattern '$pattern'..."
  # Extract files matching the pattern
  FILES=$(echo "$HTML" | grep -oP "(?<=href=\")${pattern}" | sort -r)

  if [[ -z "$FILES" ]]; then
    echo "No files found matching the pattern '$pattern'. Exiting."
    return 1
  fi

  # Get the latest file from the sorted list
  LATEST_FILE=$(echo "$FILES" | head -n 1)

  if [[ -z "$LATEST_FILE" ]]; then
    echo "Could not determine the latest file. Exiting."
    return 1
  fi

  echo "Latest file found: $LATEST_FILE"

  # Check if the file already exists locally
  if [[ -f "$LATEST_FILE" ]]; then
    echo "File '$LATEST_FILE' already exists locally. No download needed."
    return 0
  fi

  # Download the latest file
  echo "Downloading the latest file: $LATEST_FILE..."
  if wget -q --show-progress "${url}${LATEST_FILE}"; then
    echo "File '$LATEST_FILE' successfully downloaded to $(pwd)."
  else
    echo "Failed to download the file '$LATEST_FILE'. Exiting."
    return 1
  fi
}

# Call the function with the provided URL and pattern
download_latest_file "$URL" "$PATTERN"
