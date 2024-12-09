#!/usr/bin/env python3

import os
import shutil
import subprocess
import yaml
import argparse
from pathlib import Path

# Markdown files to be included in the website
# Fields: source ("filename" or "directory/"), target, weight
MARKDOWN_LOCATIONS = [
    ("README.md", "_index.md", 0),
    ("docs/setup.md", "setup.md", 10),
    ("docs/usage.md", "usage.md", 20),
    ("docs/learning.md", "learning.md", 30),
    ("docs/ai/", "ai/", 40),
    ("ansible/README.md", "tools/ansible.md", 0),
    ("terraform/README.md", "tools/terraform.md", 0),
    ("proxmox/", "proxmox/", 60),
    ("docker/README.md", "docker/_index.md", 70),
    ("docs/tools/", "tools/", 75),
    ("docs/web/README.md", "docs.md", 80),
]

VERBOSE = False


def get_git_root() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        check=True,
        universal_newlines=True,
    ).stdout.strip()


def log_copy(source_file_path: str, target_file_path: str) -> None:
    if VERBOSE:
        print(f"  {source_file_path} ==> {target_file_path}")


def create_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def delete_directory_content(content_path: Path) -> None:
    if content_path.exists() and content_path.is_dir():
        shutil.rmtree(content_path)
        create_directory(content_path)


def copy_markdown_file(source_file_path: Path, target_file_path: Path, weight: int = 0) -> None:
    with open(source_file_path, "r") as readme_file:
        lines = readme_file.readlines()

    title_found = False
    processed_lines = []

    # First line starting with "# " will be the title
    for line in lines:
        if not title_found and line.startswith("# "):
            title = line[2:].replace("<!-- omit in toc -->", "").strip()
            processed_lines.append("---\n")
            processed_lines.append(f"title: \"{title}\"\n")
            if weight != 0:
                processed_lines.append(f"weight: {weight}\n")
            processed_lines.append("---\n")
            title_found = True
        else:
            processed_lines.append(line)

    with open(target_file_path, "w") as readme_file:
        readme_file.writelines(processed_lines)


def process_location(repository_path: Path, source_path: str, target_name: str, weight: int = 0) -> None:
    if source_path.endswith("/"):
        process_directory(repository_path, source_path, target_name, weight)
    else:
        process_markdown_file(repository_path, source_path, target_name, weight)


def process_directory(repository_path: Path, source_path: str, target_name: str, weight: int = 0) -> None:
    source_dir = repository_path / source_path
    for file in os.listdir(source_dir):
        if file.endswith(".md"):
            target_filename = "_index.md" if file == "README.md" else file
            process_markdown_file(repository_path, source_path + "/" + file, target_name + "/" + target_filename, weight)


def process_markdown_file(repository_path: Path, source_path: str, target_name: str, weight: int = 0) -> None:
    source_file_path = repository_path / source_path
    target_file_path = output_content_path / target_name

    create_directory(target_file_path.parent)
    log_copy(source_file_path, target_file_path)
    copy_markdown_file(source_file_path, target_file_path, weight)


def process_docker_stack_index(source_dir: Path, target_dir: Path, root: str, file: str) -> None:
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir).with_name("_index.md")
    target_file_path = Path(target_dir) / relative_path

    create_directory(target_file_path.parent)
    log_copy(source_file_path, target_file_path)
    copy_markdown_file(source_file_path, target_file_path)


def process_docker_compose_file(source_dir: Path, target_dir: Path, root: str, file: str) -> None:
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir)
    target_file_path = Path(target_dir) / relative_path.with_suffix(".md")

    create_directory(target_file_path.parent)
    log_copy(source_file_path, target_file_path)

    metadata = get_compose_metadata(source_file_path)

    metadata.setdefault("name", source_file_path.stem.capitalize())

    with open(source_file_path, "r") as compose_file:
        lines = compose_file.readlines()

    yaml_started = False
    processed_lines = ["---\n", f"title: \"{metadata['name']}\"\n"]
    if 'description' in metadata:
        processed_lines += f"description: \"{metadata['description']}\"\n"
    if 'icon' in metadata:
        processed_lines += "params:\n"
        processed_lines += f"  icon: \"{get_icon_url(metadata['icon'])}\"\n"
    processed_lines += "---\n"

    for line in lines:
        if yaml_started:
            processed_lines.append(line)
        elif line.startswith("# "):
            processed_lines.append(line[2:])
        elif line.startswith("#"):
            processed_lines.append(line[1:])
        elif line.strip() == "---":
            yaml_started = True
            processed_lines.append("```yaml\n")

    if yaml_started:
        processed_lines.append("```\n")
        with open(target_file_path, "w") as doc_file:
            doc_file.writelines(processed_lines)


def get_icon_url(icon: str) -> str:
    return f"https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/{icon}" if icon else ""


def get_compose_metadata(file_path: Path) -> dict:
    try:
        with open(file_path, "r") as stream:
            compose_dict = yaml.safe_load(stream)
            if compose_dict is None:
                return {}

        services = compose_dict.get("services", {})

        for service in services.values():
            labels = service.get("labels", {})
            homepage_name = labels.get("homepage.name", "")
            homepage_description = labels.get("homepage.description", "")
            homepage_icon = labels.get("homepage.icon", "")

            if homepage_icon or homepage_description or homepage_name:
                return {
                    "name": homepage_name,
                    "description": homepage_description,
                    "icon": homepage_icon,
                }

        return {}

    except yaml.YAMLError as ex:
        print(ex)
        return {}


def process_docker_directory(source_dir: Path, target_dir: str) -> None:
    create_directory(Path(target_dir))

    # Walk through the source directory recursively
    for root, _, files in os.walk(source_dir):
        if "README.md" in files:
            process_docker_stack_index(source_dir, target_dir, root, "README.md")
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    process_docker_compose_file(source_dir, target_dir, root, file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process documentation files.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--repository-path", type=str, help="Specify the path to the repository root")
    parser.add_argument("--output-content-path", type=str, help="Specify the path of the generated content")
    args = parser.parse_args()

    VERBOSE = args.verbose

    if args.repository_path:
        repository_path = Path(args.repository_path)
    else:
        repository_path = Path(get_git_root())

    if args.output_content_path:
        output_content_path = Path(args.output_content_path)
    else:
        output_content_path = repository_path / "docs" / "web" / "src" / "content"

    # Remove the content directory (which only contains generated content)
    delete_directory_content(output_content_path)

    print("Processing Docker Compose stacks")
    process_docker_directory(repository_path / "docker", output_content_path / "docker")

    for source, target, weight in MARKDOWN_LOCATIONS:
        print(f"Processing {source} ==> {target}")
        process_location(repository_path, source, target, weight)
