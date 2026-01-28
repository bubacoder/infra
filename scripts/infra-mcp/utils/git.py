"""
Git utility functions for infra-mcp tools.
"""

import shutil
import subprocess
from pathlib import Path


def get_git_root(reference_path: Path | str | None = None) -> Path:
    """Get the git repository root directory.

    Args:
        reference_path: Optional path to resolve git root from. If provided,
            the git command runs from this path's directory. If None, uses CWD.

    Returns:
        Path: The absolute path to the git repository root directory.

    Raises:
        RuntimeError: If git executable is not found or not in a git repository.
    """
    git_cmd = shutil.which("git")
    if git_cmd is None:
        raise RuntimeError("Git not found on PATH") from None

    cwd = None
    if reference_path:
        cwd = Path(reference_path).resolve().parent

    try:
        result = subprocess.run(  # noqa: S603
            [git_cmd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            check=True,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise RuntimeError("Git executable not found. Please install Git and ensure it is on your PATH.") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("Unable to locate git repository. Are you running this inside a Git repo?") from None
    return Path(result.stdout.strip())
