#!/usr/bin/env bash
set -euo pipefail

# Note: More functions https://bgstack15.ddns.net/cgit/jellystack/tree/jellystack_lib.py

#TODO define
readonly JELLYFIN_URL="https://jellyfin.example.com"
readonly JELLYFIN_API_KEY="SomeSecureValueGoesHere"

# Function to trigger the media library rescan
trigger_rescan() {
  local library_id="$1"
  local endpoint="${JELLYFIN_URL}/Items/${library_id}/Refresh?Recursive=true&ImageRefreshMode=Default&MetadataRefreshMode=Default&ReplaceAllImages=false&ReplaceAllMetadata=false"
  local response=$(curl -X POST -H "X-Emby-Token: ${JELLYFIN_API_KEY}" "${endpoint}")
  echo "${response}"
}

# Replace 'your_library_id' with the actual ID of the library you want to rescan.
# The library ID can be found in the Jellyfin web interface when you navigate to
# the library settings page.
library_id_to_rescan="your_library_id"

response=$(trigger_rescan "${library_id_to_rescan}")

if [[ $response == *"200 OK"* ]]; then
  echo "Media library rescan triggered successfully for Library ID: ${library_id_to_rescan}"
else
  echo "Failed to trigger media library rescan. Response: ${response}"
fi
