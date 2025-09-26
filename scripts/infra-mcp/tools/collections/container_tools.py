"""
Container service tools for FastMCP server.
Provides functions to interact with Docker container services via labctl.py.
"""

import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool

# Configure logging
logger = logging.getLogger("infra-mcp")


def get_container_operations():
    """
    Get the list of valid container operations

    Returns:
        A list of dictionaries with operation name and description
    """
    return [
        {'name': 'pull', 'description': "Pull the latest container image for the specified service"},
        {'name': 'up', 'description': "Start the specified service containers"},
        {'name': 'down', 'description': "Stop the specified service containers"},
        {'name': 'restart', 'description': "Restart the specified service containers"},
        {'name': 'recreate', 'description': "Recreate the specified service containers"},
        {'name': 'config', 'description': "Show the docker-compose configuration for the specified service"},
    ]


def execute_container_operation(operation: str, service_name: str, repository_root_path: str) -> str:
    """
    Execute one operation on the specified service and return the output

    Args:
        operation: One of 'pull', 'up', 'down', 'restart', 'recreate', 'config'
        service_name: Service name in format category/name or category/subcategory/name
        repository_root_path: The root path of the repository

    Returns:
        The command output as a string
    """
    # Validate operation
    valid_operations = {op['name'] for op in get_container_operations()}
    if operation not in valid_operations:
        return f"Invalid operation: {operation}"

    # Validate service_name format
    if not re.match(r'^[a-zA-Z0-9_/-]+$', service_name):
        return f"Invalid service name format: {service_name}"

    cmd = [
        sys.executable,  # Use the current Python interpreter
        os.path.join(repository_root_path, "scripts", "labctl.py"),
        "service",
        operation,
        service_name
    ]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        return f"Error running operation: {e.stderr or str(e)}"
    else:
        return result.stdout or "(No output)"


def create_operation_function(op: str, repository_root_path: str) -> Callable[[str], str]:
    """
    Create a function that executes a specific container service operation.

    Args:
        op: The operation to execute ('pull', 'up', 'down', etc.)
        repository_root_path: The root path of the repository

    Returns:
        A callable function that executes the operation on a given service
    """
    def operation_fn(service_name: str) -> str:
        """
        Execute one operation on the specified service and return the output

        Args:
            service_name: Service name in format category/name or category/subcategory/name

        Returns:
            The command output as a string
        """
        return execute_container_operation(op, service_name, repository_root_path)

    return operation_fn


def add_container_operation_tools(mcp_server: FastMCP, repository_root_path: str) -> None:
    """
    Create and add tools to MCP server for container service operations.

    Args:
        mcp_server: The FastMCP server instance
        repository_root_path: The root path of the repository
    """
    operations = get_container_operations()

    for op in operations:
        operation_fn = create_operation_function(op['name'], repository_root_path)
        tool_name = f"container-service-{op['name']}"
        description = op['description']

        tool = Tool.from_function(
            fn=operation_fn,
            name=tool_name,
            title=tool_name,
            description=description
        )
        mcp_server.add_tool(tool)

    logger.info(f"Added {len(operations)} container service operation tools to MCP server")
