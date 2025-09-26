"""
Git utility functions for infra-mcp tools.
"""

import shutil
import subprocess


def get_git_root() -> str:
    """Get the git repository root directory.

    Returns:
        str: The absolute path to the git repository root directory.

    Raises:
        RuntimeError: If git executable is not found or not in a git repository.
    """
    git_cmd = shutil.which("git")
    if git_cmd is None:
        raise RuntimeError("Git not found on PATH") from None
    try:
        result = subprocess.run(  # noqa: S603
            [git_cmd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("Git executable not found. Please install Git and ensure it is on your PATH.") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("Unable to locate git repository. Are you running this inside a Git repo?") from None
    return result.stdout.strip()
