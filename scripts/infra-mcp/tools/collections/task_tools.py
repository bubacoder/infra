"""
Task tools for FastMCP server.
Provides functions to interact with taskfile.dev tasks.
"""

import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.tools import Tool

# Import constants from the shared constants module
try:
    from ...utils.constants import TASK_COMMAND_TIMEOUT
except ImportError:
    # Fallback for standalone execution
    TASK_COMMAND_TIMEOUT = 600

# Configure logging
logger = logging.getLogger("infra-mcp")


def get_task_list(repository_root_path: str | Path) -> list[dict[str, str]]:
    """
    Get the list of available tasks by running 'task --list-all'.

    Args:
        repository_root_path: The root path of the repository

    Returns:
        A list of dictionaries with 'name' and 'description' keys
    """
    logger.debug("Getting task list")
    task_bin = shutil.which("task")
    if task_bin is None:
        logger.error("The 'task' binary was not found on PATH.")
        return []
    try:
        result = subprocess.run(  # noqa: S603
            [task_bin, "--list-all", "--dir", str(repository_root_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=TASK_COMMAND_TIMEOUT,
        )
    except subprocess.CalledProcessError:
        logger.exception("Error getting task list")
        return []
    else:
        tasks = []
        # Parse output lines
        for line in result.stdout.splitlines():
            # Match lines like "* task_name:   task description"
            match = re.match(r"^\*\s+(.+?):\s+(.+)$", line.strip())
            if match:
                task_name = match.group(1).strip()
                description = match.group(2).strip()
                tasks.append(
                    {"name": task_name, "description": description},
                )

        logger.debug(f"Found {len(tasks)} tasks")
        return tasks


def execute_task(task_name: str, repository_root_path: str | Path) -> str:
    """
    Execute a task command and return the output.

    Args:
        task_name: The name of the task to execute
        repository_root_path: The root path of the repository

    Returns:
        The command output as a string
    """
    logger.info(f"Executing task: {task_name}")
    task_bin = shutil.which("task")
    if task_bin is None:
        logger.error("The 'task' binary was not found on PATH.")
        return f"Error executing task {task_name}: 'task' binary not found"
    try:
        return subprocess.run(  # noqa: S603
            [task_bin, task_name, "--dir", str(repository_root_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=TASK_COMMAND_TIMEOUT,
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.exception(f"Error executing task {task_name}")
        return f"Error executing task {task_name}: {e.stderr}"


def create_task_function(task_name: str, repository_root_path: str | Path) -> Callable[[], str]:
    """
    Create a function that executes a specific task.

    Args:
        task_name: The name of the task
        repository_root_path: The root path of the repository

    Returns:
        A callable function that executes the task
    """

    def task_fn() -> str:
        return execute_task(task_name, repository_root_path)

    return task_fn


def add_task_tools(mcp_server: FastMCP, repository_root_path: str | Path) -> None:
    """
    Get list of tasks, then create and add tools to MCP server for each task.

    Args:
        mcp_server: The FastMCP server instance
        repository_root_path: The root path of the repository
    """
    tasks = get_task_list(repository_root_path)

    for task_info in tasks:
        task_name = task_info["name"]
        tool_name = task_name.replace(":", "-")
        description = task_info["description"]
        task_fn = create_task_function(task_name, repository_root_path)

        tool = Tool.from_function(
            fn=task_fn,
            name=tool_name,
            title=tool_name,
            description=description,
        )
        mcp_server.add_tool(tool)

    logger.info(f"Added {len(tasks)} 'task' tools to MCP server")
