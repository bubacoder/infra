#!/usr/bin/env bash
set -euo pipefail

# Check if the startup parameter (the path) has been provided
if [[ $# -lt 1 ]]; then
  echo "Error: You must provide a target directory path as a parameter."
  echo "Usage: $0 <directory-path>"
  exit 1
fi

# Validate the provided path and change to it
TARGET_DIR=$1
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Error: The specified path '$TARGET_DIR' does not exist or is not a directory."
  exit 1
fi

cd "$TARGET_DIR"
echo "Changed directory to: $TARGET_DIR"

# Parameters:
# - URL of the website containing the zim files
# - The pattern to search for (e.g., wikipedia_hu_top_maxi)
kiwix_pull() {
  URL=$1
  PATTERN=$2

  # Step 1: Download the HTML from the URL
  echo -e "\n==> Fetching index from $URL..."
  HTML=$(wget -qO- "$URL")
  if [[ -z "$HTML" ]]; then
    echo "Failed to fetch the webpage content from $URL. Skipping this entry."
    return 1
  fi

  # Step 2: Extract the list of files matching the pattern
  echo "Finding files matching the pattern '$PATTERN'..."
  FILES=$(echo "$HTML" | grep -oP "${PATTERN}_[0-9]{4}-[0-9]{2}\.zim")
  if [[ -z "$FILES" ]]; then
    echo "No files found matching the pattern '$PATTERN'. Skipping this entry."
    return 1
  fi

  # Step 3: Find the latest file based on the date embedded in the name
  LATEST_FILE=$(echo "$FILES" | sort -r | head -n 1)
  if [[ -z "$LATEST_FILE" ]]; then
    echo "Could not determine the latest file for pattern '$PATTERN'. Skipping this entry."
    return 1
  fi

  echo "Latest file found: $LATEST_FILE"

  # Step 4: Check if the file already exists locally
  if [[ -f "$LATEST_FILE" ]]; then
    echo "File '$LATEST_FILE' already exists locally. No download needed."
    return 0
  fi

  # Step 5: Download the latest zim file
  echo "Downloading the file..."
  if wget -q --show-progress "$URL$LATEST_FILE"; then
    echo "File '$LATEST_FILE' successfully downloaded."
  else
    echo "Failed to download the file '$LATEST_FILE'. Skipping this entry."
    return 1
  fi
}

kiwix_pull "https://download.kiwix.org/zim/wikipedia/" "wikipedia_hu_top_maxi"
kiwix_pull "https://download.kiwix.org/zim/wikipedia/" "wikipedia_en_top_maxi"
kiwix_pull "https://download.kiwix.org/zim/other/" "zimgit-post-disaster_en"
kiwix_pull "https://download.kiwix.org/zim/zimit/" "www.ready.gov_en"
