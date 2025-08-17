#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
BASE_REF="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo 'origin/main')"
STASH_NAME="Automatic-stash-before-rebasing-$(date +%s)"

if git stash push --include-untracked -m "${STASH_NAME}"; then
    STASH_SUCCEEDED=true
else
    STASH_SUCCEEDED=false
fi

# Would be possible to use "--autostash", but "--include-untracked" is not supported
GIT_SEQUENCE_EDITOR="${SCRIPT_DIR}/git-reorder-fixup.py" git rebase --interactive "${BASE_REF}"

# Not possible to reference stash by name, so the first stash will be popped if the name matches
if [ "$STASH_SUCCEEDED" = true ] && git stash list --format=%gs | head -1 | grep -q "${STASH_NAME}"; then
    git stash pop --quiet
fi
