"""Constants for the infra-mcp server.

This module centralizes magic numbers and configuration values used throughout the codebase.
"""

import platform as _platform

# HTTP Request Timeouts (in seconds)
DEFAULT_REQUEST_TIMEOUT = 10
REGISTRY_REQUEST_TIMEOUT = 30

# Container Tag Limits
MAX_TAGS_FETCH_LIMIT = 1000
DEFAULT_TAG_LIMIT = 10
DEFAULT_SAME_HASH_LIMIT = 100

# Container Architecture

_arch_map = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "arm"}
DEFAULT_CONTAINER_ARCHITECTURE = f"linux/{_arch_map.get(_platform.machine(), _platform.machine())}"

# Task Execution
TASK_COMMAND_TIMEOUT = 600  # 10 minutes in seconds
