#!/usr/bin/env python3

import os
import shutil
import subprocess
from pathlib import Path
from filelock import FileLock

def get_git_root():
    return subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')

# Create subdirectories in the target directory if needed
def create_directory(target_file_path):
    target_subdir = Path(target_file_path).parent
    target_subdir.mkdir(parents=True, exist_ok=True)

def process_compose_file(source_dir, target_dir, root, file):
    # Construct the source and target file paths
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir)
    target_file_path = Path(target_dir) / relative_path.with_suffix(".md")
    service_name = source_file_path.stem.capitalize()

    create_directory(target_file_path)

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

def process_readme_md(source_dir, target_dir, root, file):
    # Construct the source and target file paths
    source_file_path = Path(root) / file
    relative_path = source_file_path.relative_to(source_dir).with_name("_index.md")
    target_file_path = Path(target_dir) / relative_path

    create_directory(target_file_path)

    # Copy the YAML file
    print(f"Copy {source_file_path} ==> {target_file_path}")
    shutil.copy2(source_file_path, target_file_path)

def process_files(source_dir, target_dir):
    # Create the target directory if it doesn't exist
    target_dir_path = Path(target_dir)
    target_dir_path.mkdir(parents=True, exist_ok=True)

    # Walk through the source directory recursively
    for root, _, files in os.walk(source_dir):
        if 'README.md' in files:
            process_readme_md(source_dir, target_dir, root, 'README.md')
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    process_compose_file(source_dir, target_dir, root, file)

# --- main ---

repo_root = Path(get_git_root())
stacks    = repo_root / 'docker' / 'stacks'
web_root  = repo_root / 'docs' / 'web' / 'src'

# Remove the complete docker directory (which only contains generated content)
shutil.rmtree(web_root / 'content')

def process_repo_readme_md(source_path, target_name):
    source_file_path = repo_root / source_path
    target_file_path = web_root / 'content' / target_name
    print(f"Copy {source_file_path} ==> {target_file_path}")
    shutil.copy2(source_file_path, target_file_path)

process_repo_readme_md("README.md", "_index.md")
process_repo_readme_md("docs/pve.md", "pve.md")
process_repo_readme_md("docs/setup.md", "setup.md")
process_repo_readme_md("docs/usage.md", "usage.md")
process_repo_readme_md("docker/README.md", "docker.md")
process_repo_readme_md("terraform/README.md", "terraform.md")
process_repo_readme_md("ansible/README.md", "ansible.md")
process_repo_readme_md("docs/web/README.md", "docs.md")

# https://discourse.gohugo.io/t/what-is-the-hugo-build-lock-file/35417/2
with FileLock(web_root / '.hugo_build.lock'):
    process_files(stacks, web_root / 'content' / 'docker')
