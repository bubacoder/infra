#!/usr/bin/env python3
"""
FastMCP server implementation for task runner integration, container operations, and infrastructure management.
Dynamically creates tools from the output of 'task --list-all'.
"""

import contextlib
import io
import logging
import os
import signal
import sys

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from tools.collections.container_tools import add_container_operation_tools
from tools.collections.task_tools import add_task_tools
from tools.get_app_icon import AppIconFinder
from tools.get_container_categories import ContainerCategoryFinder
from tools.get_container_tags import ContainerTagFinder
from tools.get_dashboard_groups import DashboardGroupFinder
from utils.constants import DEFAULT_CONTAINER_ARCHITECTURE, DEFAULT_SAME_HASH_LIMIT, DEFAULT_TAG_LIMIT
from utils.git import get_git_root
from utils.models import ContainerTagFinderArgs
from utils.security import validate_url_for_ssrf

# Configure logging from environment
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("infra-mcp")
logger.info("Starting Infra MCP server")

mcp = FastMCP(
    name="infra-mcp",
    instructions="Use these tools to configure the homelab infrastructure and interact with the services.",
)


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(_request: Request) -> PlainTextResponse:
    """Health check endpoint for monitoring server status."""
    return PlainTextResponse("OK")


@mcp.tool(name="get-app-icon")
def get_app_icon(app_name: str, homepage_url: str) -> str:
    """
    Find an application icon from either the dashboard-icons repository or by extracting favicon from the app's homepage.

    Args:
        app_name (str): The name of the application.
        homepage_url (str): The URL of the application's homepage.

    Returns:
        str: Either the name of the application icon or a favicon URL.
    """
    if not validate_url_for_ssrf(homepage_url):
        return "default"

    try:
        icon_finder = AppIconFinder()
        return icon_finder.get_app_icon(app_name, homepage_url)
    except Exception:
        logger.exception("find-app-icon failed for app_name=%r homepage_url=%r", app_name, homepage_url)
        return "default"


@mcp.tool(name="get-dashboard-groups")
def get_dashboard_groups() -> list[str]:
    """
    Get a list of dashboard groups from the homepage settings.

    Returns:
        list[str]: A list of dashboard group names.
    """
    group_finder = DashboardGroupFinder()
    try:
        return group_finder.get_dashboard_groups()
    except Exception:
        logger.exception("get-dashboard-groups failed")
        return []


@mcp.tool(name="get-container-categories")
def get_container_categories() -> list[str]:
    """
    Get a list of container categories from the docker directory.
    Recursively looks for directories that contain both a README.md file and at least one *.yaml file.

    Returns:
        list[str]: A list of directory paths relative to the docker directory.
    """
    category_finder = ContainerCategoryFinder()
    try:
        return category_finder.get_container_categories()
    except Exception:
        logger.exception("get-container-categories failed")
        return []


@mcp.tool(name="list-container-tags")
def list_container_tags(image: str, limit: int = DEFAULT_TAG_LIMIT) -> list[str]:
    """
    List recent tags for a container image.

    Args:
        image: Image name (e.g., nginx or registry.example.com/nginx)
        limit: Maximum number of tags to display (default: 10)

    Returns:
        list[str]: A list of tag names sorted by recency
    """
    tag_finder = ContainerTagFinder()
    try:
        args = ContainerTagFinderArgs(
            image=image,
            architecture=DEFAULT_CONTAINER_ARCHITECTURE,
            limit=limit,
            quiet=True,
            registry=None,
        )

        tags, _, _, _ = tag_finder.get_image_tags(args)
        return [tag["name"] for tag in tags[:limit]] if tags else []
    except Exception:
        logger.exception(f"list-container-tags failed for image={image!r}")
        return []


@mcp.tool(name="list-same-hash-container-tags")
def list_same_hash_container_tags(image: str, tag: str | None = None, limit: int = DEFAULT_SAME_HASH_LIMIT) -> list[str]:
    """
    List tags that have the same hash as a specified container tag.

    Args:
        image: Image name (e.g., nginx or registry.example.com/nginx)
        tag: Tag to use as reference (default: latest or first tag found)
        limit: Maximum number of tags to search through (default: 100)

    Returns:
        list[str]: A list of tag names that share the same content hash
    """
    tag_finder = ContainerTagFinder()
    try:
        args = ContainerTagFinderArgs(
            image=image,
            tag=tag,
            architecture=DEFAULT_CONTAINER_ARCHITECTURE,
            limit=limit,
            quiet=True,
            registry=None,
        )

        # Get same hash tags but don't output to stdout
        same_hash_tags = tag_finder.list_same_hash_tags(args, suppress_output=True)
        return [tag["name"] for tag in same_hash_tags] if same_hash_tags else []
    except Exception:
        logger.exception(f"list-same-hash-container-tags failed for image={image!r} tag={tag!r}")
        return []


@mcp.tool(name="get-most-specific-container-tag")
def get_most_specific_container_tag(image: str, tag: str | None = None, limit: int = DEFAULT_SAME_HASH_LIMIT) -> str:
    """
    Find the most specific container version tag from tags with the same hash.

    Args:
        image: Image name (e.g., nginx or registry.example.com/nginx)
        tag: Tag to use as reference (default: latest or first tag found)
        limit: Maximum number of tags to search through (default: 100)

    Returns:
        str: The most specific version tag name (e.g., a semver tag like '1.2.3' instead of 'latest')
    """
    tag_finder = ContainerTagFinder()
    try:
        args = ContainerTagFinderArgs(
            image=image,
            tag=tag,
            architecture=DEFAULT_CONTAINER_ARCHITECTURE,
            limit=limit,
            quiet=True,
            registry=None,
        )

        # Suppress any prints from the finder
        with contextlib.redirect_stdout(io.StringIO()):
            most_specific = tag_finder.get_most_specific_tag(args)
            same_hash = tag_finder.list_same_hash_tags(args, suppress_output=True)
    except Exception:
        logger.exception(f"get-most-specific-container-tag failed for image={image!r} tag={tag!r}")
        return tag or "latest"
    else:
        if most_specific:
            return most_specific["name"]
        if same_hash:
            return same_hash[0]["name"]
        return tag or "latest"


# --- Configure the FastMCP server ---


def handle_shutdown(signum: int, _frame: object) -> None:
    """Handle shutdown signals gracefully.

    Args:
        signum: Signal number received
        _frame: Current stack frame (unused)
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name}, shutting down gracefully...")
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

try:
    # Get the repository root path
    repository_root_path = get_git_root()
    logger.info(f"Repository root path: {repository_root_path}")

    # Check environment variables to enable/disable tools
    enable_task_tools = os.environ.get("ENABLE_TASK_TOOLS", "true").lower() != "false"
    enable_container_tools = os.environ.get("ENABLE_CONTAINER_TOOLS", "true").lower() != "false"

    # Add tools based on environment variable settings
    if enable_task_tools:
        logger.info("Adding task tools")
        add_task_tools(mcp, repository_root_path)
    else:
        logger.info("Task tools disabled by environment variable")

    if enable_container_tools:
        logger.info("Adding container operation tools")
        add_container_operation_tools(mcp, repository_root_path)
    else:
        logger.info("Container operation tools disabled by environment variable")
except FileNotFoundError:
    logger.exception("Repository not found")
    sys.exit(1)
except RuntimeError:
    logger.exception("Git operation failed")
    sys.exit(1)
except ImportError:
    logger.exception("Failed to import required module")
    sys.exit(1)
except Exception:
    logger.exception("Unexpected error during server initialization")
    sys.exit(1)


def main() -> None:
    """Start the MCP server."""
    # Start the server
    mcp.run()
    # Or start with parameters:
    # mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")


if __name__ == "__main__":
    main()
