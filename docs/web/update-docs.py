#!/usr/bin/env python3

import os
import shutil
import subprocess
import yaml
from pathlib import Path
from filelock import FileLock

# Markdown files to be included in the website
# Fields: source, target, weight
markdown_files = [
    ("README.md", "_index.md", 0),

    ("docs/setup.md", "setup.md", 1),
    ("docs/pve.md", "pve.md", 2),
    ("ansible/README.md", "ansible.md", 3),
    ("terraform/README.md", "terraform.md", 4),
    ("docs/usage.md", "usage.md", 5),
    ("docs/web/README.md", "docs.md", 6),

    ("docker/README.md", "docker/_index.md", 7),
]


def get_git_root() -> str:
    return subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')


def create_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def remove_content(content_path: Path) -> None:
    if content_path.exists() and content_path.is_dir():
        shutil.rmtree(content_path)
        create_directory(content_path)


def copy_readme_md(source_file_path: Path, target_file_path: Path, weight: int = 0) -> None:
    with open(source_file_path, 'r') as readme_file:
        lines = readme_file.readlines()

    title_found = False
    processed_lines = []

    # First line starting with "# " will be the title
    for line in lines:
        if not title_found and line.startswith("# "):
            title = line[2:].strip()
            processed_lines.append("+++\n")
            processed_lines.append(f"title = \"{title}\"\n")
            if weight != 0:
                processed_lines.append(f"weight = {weight}\n")
            processed_lines.append("+++\n")
            title_found = True
        else:
            processed_lines.append(line)

    with open(target_file_path, 'w') as readme_file:
        readme_file.writelines(processed_lines)


def process_readme_md(repo_root: Path, source_path: str, target_name: str, weight: int = 0) -> None:
    source_file_path = repo_root / source_path
    target_file_path = web_root / 'content' / target_name

    print(f"Copy {source_file_path} ==> {target_file_path}")
    copy_readme_md(source_file_path, target_file_path, weight)


def process_docker_category_readme_md(source_dir: Path, target_dir: Path, root: str, file: str) -> None:
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir).with_name("_index.md")
    target_file_path = Path(target_dir) / relative_path

    create_directory(target_file_path.parent)
    print(f"Copy {source_file_path} ==> {target_file_path}")
    copy_readme_md(source_file_path, target_file_path)


def get_icon_url(icon: str) -> str:
    if icon:
        return f"https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/{icon}"
    else:
        return ""


def process_docker_compose_file(source_dir: Path, target_dir: Path, root: str, file: str) -> None:
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir)
    target_file_path = Path(target_dir) / relative_path.with_suffix(".md")

    create_directory(target_file_path.parent)
    print(f"Copy {source_file_path} ==> {target_file_path}")

    metadata = read_compose_metadata(source_file_path)

    if 'name' not in metadata:
        metadata['name'] = source_file_path.stem.capitalize()

    with open(source_file_path, 'r') as compose_file:
        lines = compose_file.readlines()

    yaml_started = False
    processed_lines = ["+++\n", f"title = \"{metadata['name']}\"\n"]
    if 'description' in metadata:
        processed_lines += f"description = \"{metadata['description']}\"\n"
    if 'icon' in metadata:
        processed_lines += "[params]\n"
        processed_lines += f"  icon = \"{get_icon_url(metadata['icon'])}\"\n"
    processed_lines += "+++\n"

    for line in lines:
        if yaml_started:
            processed_lines.append(line)
        elif line.startswith("# "):
            line = line[2:]
            processed_lines.append(line)
        elif line.startswith("#"):
            line = line[1:]
            processed_lines.append(line)
        elif line.strip() == '---':
            yaml_started = True
            processed_lines.append("```yaml\n")

    if yaml_started:
        processed_lines.append("```\n")
        with open(target_file_path, 'w') as doc_file:
            doc_file.writelines(processed_lines)


def read_compose_metadata(file_path: Path):
    with open(file_path, 'r') as stream:
        try:
            compose_dict = yaml.safe_load(stream)
            if compose_dict is None:
                return {}

            services = compose_dict.get('services', {})

            for service in services.values():
                labels = service.get('labels', {})
                homepage_name = labels.get('homepage.name', '')
                homepage_description = labels.get('homepage.description', '')
                homepage_icon = labels.get('homepage.icon', '')

                if homepage_icon or homepage_description or homepage_name:
                    return {
                        'name': homepage_name,
                        'description': homepage_description,
                        'icon': homepage_icon
                    }

            # if not found in any service
            return {}

        except yaml.YAMLError as exc:
            print(exc)
            return {}


def process_docker_directory(source_dir: Path, target_dir: str) -> None:
    create_directory(Path(target_dir))

    # Walk through the source directory recursively
    for root, _, files in os.walk(source_dir):
        if 'README.md' in files:
            process_docker_category_readme_md(source_dir, target_dir, root, 'README.md')
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    process_docker_compose_file(source_dir, target_dir, root, file)


if __name__ == '__main__':
    repo_root = Path(get_git_root())
    stacks = repo_root / 'docker' / 'stacks'
    web_root = repo_root / 'docs' / 'web' / 'src'

    # https://discourse.gohugo.io/t/what-is-the-hugo-build-lock-file/35417/2
    with FileLock(web_root / '.hugo_build.lock'):
        # Remove the content directory (which only contains generated content)
        remove_content(web_root / 'content')

        process_docker_directory(stacks, web_root / 'content' / 'docker')

        for source, target, weight in markdown_files:
            process_readme_md(repo_root, source, target, weight)
