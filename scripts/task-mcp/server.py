#!/usr/bin/env python3
"""
FastMCP server implementation for task runner integration.
Dynamically creates tools from the output of 'task --list-all'.
"""

import logging
import re
import subprocess
import sys
import os
from typing import Callable, Dict, List
from fastmcp import FastMCP
from fastmcp.tools import Tool
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("task-mcp")
logger.info("Starting Task MCP server")

mcp = FastMCP(
    name="task-mcp",
    instructions="Use these tools to configure the homelab infrastructure and interact with the services."
)


def get_git_root() -> str:
    """Get the git repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            check=True,
            universal_newlines=True,
        )
    except FileNotFoundError:
        raise RuntimeError("Git executable not found. Please install Git and ensure it is on your PATH.") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("Unable to locate git repository. Are you running this inside a Git repo?") from None
    return result.stdout.strip()


def get_task_list() -> List[Dict[str, str]]:
    """
    Get the list of available tasks by running 'task --list-all'.

    Returns:
        A list of dictionaries with 'name' and 'description' keys
    """
    logger.debug("Getting task list")
    try:
        result = subprocess.run(
            ["task", "--list-all", "--dir", repository_root_path],
            capture_output=True,
            text=True,
            check=True
        )

        tasks = []
        # Parse output lines
        for line in result.stdout.splitlines():
            # Match lines like "* task_name:   task description"
            match = re.match(r'^\*\s+(.+?):\s+(.+)$', line.strip())
            if match:
                task_name = match.group(1).strip()
                description = match.group(2).strip()
                tasks.append({
                    "name": task_name,
                    "description": description
                })

        logger.debug(f"Found {len(tasks)} tasks")
        return tasks
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting task list: {e}")
        return []


def execute_task(task_name: str) -> str:
    """
    Execute a task command and return the output.

    Args:
        task_name: The name of the task to execute

    Returns:
        The command output as a string
    """
    logger.info(f"Executing task: {task_name}")
    try:
        return subprocess.run(
            ["task", task_name, "--dir", repository_root_path],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing task {task_name}: {e}")
        return f"Error executing task {task_name}: {e.stderr}"


def create_task_function(task_name: str) -> Callable[[], str]:
    """
    Create a function that executes a specific task.

    Args:
        task_name: The name of the task

    Returns:
        A callable function that executes the task
    """
    def task_fn() -> str:
        return execute_task(task_name)

    return task_fn


@mcp.tool(name="control-container-service")
def control_container_service(operation: str, service_name: str) -> str:
    """
    Execute one operation ('up', 'down', 'restart', 'recreate', 'update' or 'pull') on the specified service and return the output

    Args:
        operation: One of 'up', 'down', 'restart', 'recreate', 'update', 'pull'
        service_name: Service name in format category/name or category/subcategory/name

    Returns:
        The command output as a string
    """
    allowed_operations = ['up', 'down', 'restart', 'recreate', 'update', 'pull']

    if operation not in allowed_operations:
        return f"Invalid operation: {operation}. Allowed: {', '.join(allowed_operations)}"

    # Validate service_name format
    if not re.match(r'^[a-zA-Z0-9_/-]+$', service_name):
        return f"Invalid service name format: {service_name}"

    cmd = [
        sys.executable,
        os.path.join(repository_root_path, "docker", "labctl.py"),
        "service",
        operation,
        service_name
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout or "(No output)"
    except subprocess.CalledProcessError as e:
        return f"Error running operation: {e.stderr or str(e)}"


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


# --- Configure the FastMCP server ---

try:
    # Get the repository root path
    repository_root_path = get_git_root()
    logger.info(f"Repository root path: {repository_root_path}")

    # Get the list of available tasks
    tasks = get_task_list()
except Exception as e:
    logger.error(f"Failed to initialize server: {e}")
    sys.exit(1)

# Create and add tools for each task
for task_info in tasks:
    task_name = task_info["name"]
    description = task_info["description"]
    task_fn = create_task_function(task_name)
    tool = Tool.from_function(fn=task_fn, name=task_name, title=task_name, description=description)
    mcp.add_tool(tool)

logger.info(f"Added {len(tasks)} tools to MCP server")


if __name__ == "__main__":
    # Start the server
    mcp.run()

    # Or start with parameters:
    # mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
