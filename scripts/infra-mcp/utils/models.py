"""Data models for the infra-mcp server.

This module contains dataclass definitions for shared data structures used throughout the codebase.
"""

from dataclasses import dataclass


@dataclass
class ContainerTagFinderArgs:
    """Arguments for ContainerTagFinder operations.

    Attributes:
        image: Container image name (e.g., nginx or registry.example.com/nginx)
        architecture: Container architecture (e.g., linux/amd64, linux/arm64)
        limit: Maximum number of tags to process
        quiet: Whether to suppress output
        registry: Optional registry URL for private registries
        tag: Optional tag to use as reference (for same-hash operations)
    """

    image: str
    architecture: str = "linux/amd64"
    limit: int = 10
    quiet: bool = True
    registry: str | None = None
    tag: str | None = None
