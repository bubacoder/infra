#!/usr/bin/env bash
set -euo pipefail

BASE_REF="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo 'origin/main')"
STASH_NAME="Automatic-stash-before-rebasing-$(date +%s)"

if git stash push --include-untracked -m "${STASH_NAME}"; then
  STASH_SUCCEEDED=true
else
  STASH_SUCCEEDED=false
fi

# Would be possible to use "--autostash", but "--include-untracked" is not supported
git rebase --interactive --autosquash "${BASE_REF}"

if [ "$STASH_SUCCEEDED" = true ]; then
  # Not possible to reference stash by name; check if the top stash subject contains the stash name
  TOP_STASH_SUBJECT="$(git stash list --max-count=1 --format=%gs || true)"
  if [[ "$TOP_STASH_SUBJECT" == *"$STASH_NAME"* ]]; then
    git stash pop --quiet
  fi
fi
