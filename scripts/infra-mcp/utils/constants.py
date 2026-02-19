"""Constants for the infra-mcp server.

This module centralizes magic numbers and configuration values used throughout the codebase.
"""

# HTTP Request Timeouts (in seconds)
DEFAULT_REQUEST_TIMEOUT = 10
REGISTRY_REQUEST_TIMEOUT = 30

# Container Tag Limits
MAX_TAGS_FETCH_LIMIT = 1000
DEFAULT_TAG_LIMIT = 10
DEFAULT_SAME_HASH_LIMIT = 100

# Container Architecture
DEFAULT_CONTAINER_ARCHITECTURE = "linux/amd64"

# Task Execution
TASK_COMMAND_TIMEOUT = 600  # 10 minutes in seconds
