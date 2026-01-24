"""Utility functions for Git repository operations."""

import shutil
import subprocess


class GitExecutableNotFoundError(RuntimeError):
    """Raised when Git executable cannot be found."""


class NotInGitRepositoryError(RuntimeError):
    """Raised when not running inside a Git repository."""


def get_git_root() -> str:
    """Get the git repository root directory.

    Returns:
        The absolute path to the git repository root directory.

    Raises:
        GitExecutableNotFoundError: If git executable is not found on PATH.
        NotInGitRepositoryError: If not running inside a Git repository.
    """
    git_cmd = shutil.which("git")
    if git_cmd is None:
        raise GitExecutableNotFoundError("Git executable not found. Please install Git and ensure it is on your PATH.")

    try:
        result = subprocess.run(  # noqa: S603
            [git_cmd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GitExecutableNotFoundError("Git executable not found. Please install Git and ensure it is on your PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise NotInGitRepositoryError("Unable to locate git repository. Are you running this inside a Git repo?") from exc

    return result.stdout.strip()
