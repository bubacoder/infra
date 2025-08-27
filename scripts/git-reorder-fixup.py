#!/usr/bin/env python3

# This Python script reorders git commits containing the "[FIXUP]" text to be right after their counterpart commit in a given file, modifies the command to "fixup" for these lines, and then opens the modified file in the nano text editor for review or further changes.

# GIT_SEQUENCE_EDITOR=~/repos/infra/scripts/git-reorder-fixup.py git rebase -i abcdef1234
# alias rebase-fixup="GIT_SEQUENCE_EDITOR=~/repos/infra/scripts/git-reorder-fixup.py git rebase -i"
# git config --global sequence.editor "code --wait"

import os
import shlex
import subprocess
import sys


def reorder_commits(file_path: str) -> None:
    git_sequence_editor = os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'nano'

    with open(file_path) as file:
        lines = file.readlines()

    reordered_lines = []
    fixup_lines = []

    for line in lines:
        if line.startswith('#'):
            reordered_lines.append(line)
        elif '[FIXUP]' in line or '[F]' in line:
            fixup_lines.append(line)
        else:
            reordered_lines.append(line)

    for fixup_line in fixup_lines:
        line_to_add = fixup_line
        original_commit_message = get_original_commit_message(line_to_add)
        original_commit_found = False
        for i, reordered_line in enumerate(reordered_lines):
            if original_commit_message in reordered_line:
                line_to_add = line_to_add.replace('pick', 'fixup', 1)
                reordered_lines.insert(i + 1, line_to_add)
                original_commit_found = True
                break
        if not original_commit_found:
            reordered_lines.insert(0, line_to_add)

    with open(file_path, 'w') as file:
        file.writelines(reordered_lines)

    res = subprocess.call(shlex.split(git_sequence_editor) + [file_path])
    sys.exit(res)


def get_original_commit_message(fixup_line: str) -> str:
    message = ' '.join(fixup_line.split()[2:])
    return message.replace('[FIXUP]', '').replace('[F]', '').strip()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: No file path provided.")
        sys.exit(1)
    reorder_commits(sys.argv[1])
