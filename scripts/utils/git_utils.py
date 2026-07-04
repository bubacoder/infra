"""Utility functions for Git repository operations."""

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

UNCOMMITTED_SHA = "0000000000000000000000000000000000000000"


class GitExecutableNotFoundError(RuntimeError):
    """Raised when Git executable cannot be found."""


class NotInGitRepositoryError(RuntimeError):
    """Raised when not running inside a Git repository."""


def _get_git_executable() -> str:
    """Locate the git executable on PATH.

    Returns:
        Path to the git executable.

    Raises:
        GitExecutableNotFoundError: If git executable is not found on PATH.
    """
    git_cmd = shutil.which("git")
    if git_cmd is None:
        raise GitExecutableNotFoundError("Git executable not found. Please install Git and ensure it is on your PATH.")
    return git_cmd


def get_line_last_changed(repository_path: str | Path, file_path: str, line_number: int) -> datetime | None:
    """Get the date a specific line was last changed, via `git blame`.

    Args:
        repository_path: Path to the repository root (used as the git working directory)
        file_path: Path to the file, relative to repository_path
        line_number: 1-indexed line number to blame

    Returns:
        Timezone-aware datetime of the commit that last changed the line, or None if the
        line is uncommitted or blame information could not be determined.
    """
    git_cmd = _get_git_executable()

    try:
        result = subprocess.run(  # noqa: S603
            [git_cmd, "blame", "--porcelain", "-L", f"{line_number},{line_number}", "--", file_path],
            cwd=repository_path,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    lines = result.stdout.splitlines()
    if not lines or lines[0].split(" ")[0] == UNCOMMITTED_SHA:
        return None

    for line in lines:
        if line.startswith("author-time "):
            timestamp = int(line.split(" ", 1)[1])
            return datetime.fromtimestamp(timestamp, tz=UTC)

    return None


def get_git_root() -> str:
    """Get the git repository root directory.

    Returns:
        The absolute path to the git repository root directory.

    Raises:
        GitExecutableNotFoundError: If git executable is not found on PATH.
        NotInGitRepositoryError: If not running inside a Git repository.
    """
    git_cmd = _get_git_executable()

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
