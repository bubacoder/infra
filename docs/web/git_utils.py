import shutil
import subprocess


class GitNotOnPathError(RuntimeError):
    """Raised when Git executable is not found on PATH."""
    def __init__(self):
        super().__init__("Git not found on PATH")

class GitExecutableNotFoundError(RuntimeError):
    """Raised when Git executable cannot be found."""
    def __init__(self):
        super().__init__("Git executable not found. Please install Git and ensure it is on your PATH.")

class NotInGitRepositoryError(RuntimeError):
    """Raised when not running inside a Git repository."""
    def __init__(self):
        super().__init__("Unable to locate git repository. Are you running this inside a Git repo?")

def get_git_root() -> str:
    """Get the git repository root directory.

    Returns:
        str: The absolute path to the git repository root directory.

    Raises:
        GitNotOnPathError: If git executable is not found on PATH.
        GitExecutableNotFoundError: If git executable cannot be found.
        NotInGitRepositoryError: If not running inside a Git repository.
    """
    git_cmd = shutil.which("git")
    if git_cmd is None:
        raise GitNotOnPathError() from None
    try:
        result = subprocess.run(  # noqa: S603
            [git_cmd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        )
    except FileNotFoundError:
        raise GitExecutableNotFoundError() from None
    except subprocess.CalledProcessError:
        raise NotInGitRepositoryError() from None
    return result.stdout.strip()
