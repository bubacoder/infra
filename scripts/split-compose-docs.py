#!/usr/bin/env python3
"""Move leading Compose documentation comments into service README files."""

from pathlib import Path

from utils.git_utils import get_git_root


def split_compose_docs(compose_file: Path) -> bool:
    """Move the comment block before the YAML separator into README.md."""
    lines = compose_file.read_text(encoding="utf-8").splitlines(keepends=True)
    separator_index = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)

    if separator_index is None:
        return False

    documentation = "".join(line[2:] if line.startswith("# ") else line[1:] if line.startswith("#") else line for line in lines[:separator_index])
    if not documentation:
        return False

    readme_file = compose_file.parent / "README.md"
    existing_readme = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""
    separator = "\n" if existing_readme.endswith("\n") else "\n\n" if existing_readme else ""
    readme_file.write_text(f"{existing_readme}{separator}{documentation}", encoding="utf-8")
    compose_file.write_text("".join(lines[separator_index + 1 :]), encoding="utf-8")
    return True


def compose_files(docker_dir: Path) -> list[Path]:
    """Find Compose files with a leading comment section and a name document."""
    files = []
    for path in docker_dir.rglob("*"):
        if path.suffix not in {".yaml", ".yml"}:
            continue
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        separator_index = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
        if separator_index is not None and any(line.startswith("name:") for line in lines[separator_index + 1 :]):
            files.append(path)
    return files


def main() -> None:
    """Split documentation from every Docker Compose file with a comment header."""
    repository_path = Path(get_git_root())
    updated = sum(split_compose_docs(path) for path in compose_files(repository_path / "docker"))
    print(f"Split documentation from {updated} Compose files.")


if __name__ == "__main__":
    main()
