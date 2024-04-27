#!/bin/bash

JELLYFIN_URL="https://jellyfin.example.com"
JELLYFIN_API_KEY="SomeSecureValueGoesHere"

# Function to trigger the media library rescan
trigger_rescan() {
  local library_id=$1
  #local endpoint="${JELLYFIN_URL}/Library/Refresh/${library_id}/"
  local endpoint="${JELLYFIN_URL}/Library/Refresh"
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
