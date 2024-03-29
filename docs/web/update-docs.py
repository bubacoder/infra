#!/usr/bin/env python3

import os
import shutil
import subprocess
from pathlib import Path
# TODO from filelock import FileLock

# Markdown files to be included in the website
# Fields: source, target, weight
markdown_files = [
    ("README.md", "_index.md", 5),

    ("docs/pve.md", "pve.md", 3),
    ("docs/setup.md", "setup.md", 0),
    ("docs/usage.md", "usage.md", 0),

    ("docker/README.md", "docker.md", 0),
    ("terraform/README.md", "terraform.md", 0),
    ("ansible/README.md", "ansible.md", 0),
    ("docs/web/README.md", "docs.md", 0),
]


def get_git_root():
    return subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')


def create_directory(directory):
    directory.mkdir(parents=True, exist_ok=True)


def remove_content(content_path):
    if content_path.exists() and content_path.is_dir():
        shutil.rmtree(content_path)
        create_directory(content_path)


def copy_readme_md(source_file_path, target_file_path, weight=0):
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


def process_readme_md(repo_root, source_path, target_name, weight=0):
    source_file_path = repo_root / source_path
    target_file_path = web_root / 'content' / target_name

    print(f"Copy {source_file_path} ==> {target_file_path}")
    copy_readme_md(source_file_path, target_file_path, weight)


def process_docker_category_readme_md(source_dir, target_dir, root, file):
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir).with_name("_index.md")
    target_file_path = Path(target_dir) / relative_path

    create_directory(target_file_path.parent)
    print(f"Copy {source_file_path} ==> {target_file_path}")
    copy_readme_md(source_file_path, target_file_path)


def process_docker_compose_file(source_dir, target_dir, root, file):
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir)
    target_file_path = Path(target_dir) / relative_path.with_suffix(".md")
    service_name = source_file_path.stem.capitalize()

    create_directory(target_file_path.parent)

    print(f"Copy {source_file_path} ==> {target_file_path}")

    # Read the content of the file
    with open(source_file_path, 'r') as compose_file:
        lines = compose_file.readlines()

    yaml_started = False
    processed_lines = [
        "+++\n",
        f"title = \"{service_name}\"\n",
        "+++\n"
    ]

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


def process_docker_directory(source_dir, target_dir):
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

    # # https://discourse.gohugo.io/t/what-is-the-hugo-build-lock-file/35417/2
    # with FileLock(web_root / '.hugo_build.lock'):

    # Remove the content directory (which only contains generated content)
    remove_content(web_root / 'content')

    for source, target, weight in markdown_files:
        process_readme_md(repo_root, source, target, weight)

    process_docker_directory(stacks, web_root / 'content' / 'docker')


# TODO Extract homepage.icon
# https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/grafana.png
