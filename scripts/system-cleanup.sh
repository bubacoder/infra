#!/usr/bin/env bash
# Safely clear regenerable Debian/Ubuntu caches. Destructive actions require --apply.
set -euo pipefail

JOURNAL_SIZE="1G"
APPLY=false
COMPONENTS=(apt journal docker-build-cache snap-cache)

usage() {
  cat <<'EOF'
Usage: system-cleanup.sh [--apply] [--journal-size SIZE] [--only COMPONENT]

Report or remove regenerable system caches on Debian and Ubuntu hosts.
Without --apply, no files are removed.

Components:
  apt                 Downloaded APT packages
  journal             systemd journal logs, retaining JOURNAL_SIZE (default: 1G)
  docker-build-cache  Unused Docker build cache only
  snap-cache          Downloaded Snap packages
  snap-disabled       Disabled Snap revisions

Examples:
  system-cleanup.sh
  system-cleanup.sh --apply --only docker-build-cache
  system-cleanup.sh --apply --journal-size 500M --only journal
EOF
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

has_component() {
  local component="$1"
  local selected
  for selected in "${COMPONENTS[@]}"; do
    [[ "$selected" == "$component" ]] && return 0
  done
  return 1
}

require_sudo() {
  if ! sudo -v; then
    fail "Administrator privileges are required for the selected cleanup."
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=true
      ;;
    --journal-size)
      [[ $# -ge 2 ]] || fail "--journal-size requires a value."
      JOURNAL_SIZE="$2"
      shift
      ;;
    --only)
      [[ $# -ge 2 ]] || fail "--only requires a component."
      case "$2" in
        apt|journal|docker-build-cache|snap-cache|snap-disabled)
          COMPONENTS=("$2")
          ;;
        *)
          fail "Unknown component: $2"
          ;;
      esac
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
  shift
done

if [[ "$APPLY" == false ]]; then
  printf 'Dry run: add --apply to remove cache data.\n\n'
fi

if has_component apt; then
  if command -v apt-get >/dev/null 2>&1; then
    printf 'APT package cache: '
    du -sh /var/cache/apt/archives 2>/dev/null || true
    if [[ "$APPLY" == true ]]; then
      require_sudo
      sudo apt-get clean
    fi
  else
    printf 'APT: skipped (apt-get is not installed).\n'
  fi
fi

if has_component journal; then
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --disk-usage
    printf 'Journal retention target: %s\n' "$JOURNAL_SIZE"
    if [[ "$APPLY" == true ]]; then
      require_sudo
      sudo journalctl --vacuum-size="$JOURNAL_SIZE"
    fi
  else
    printf 'Journal: skipped (journalctl is not installed).\n'
  fi
fi

if has_component docker-build-cache; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker system df | awk 'NR == 1 || /^Build Cache/'
    if [[ "$APPLY" == true ]]; then
      docker builder prune --all --force
    fi
  else
    printf 'Docker build cache: skipped (Docker is unavailable or inaccessible).\n'
  fi
fi

if has_component snap-cache; then
  if command -v snap >/dev/null 2>&1; then
    printf 'Snap download cache: '
    du -sh /var/lib/snapd/cache 2>/dev/null || true
    if [[ "$APPLY" == true ]]; then
      require_sudo
      sudo rm -f /var/lib/snapd/cache/*
    fi
  else
    printf 'Snap download cache: skipped (snap is not installed).\n'
  fi
fi

if has_component snap-disabled; then
  if command -v snap >/dev/null 2>&1; then
    if ! disabled_revisions=$(snap list --all | awk '$NF ~ /disabled/ { print $1 " " $3 }'); then
      printf 'Disabled Snap revisions: skipped (Snap is unavailable or inaccessible).\n'
    elif [[ -z "$disabled_revisions" ]]; then
      printf 'Disabled Snap revisions: none.\n'
    else
      printf 'Disabled Snap revisions:\n%s\n' "$disabled_revisions"
      if [[ "$APPLY" == true ]]; then
        require_sudo
        while read -r name revision; do
          sudo snap remove "$name" --revision="$revision"
        done <<< "$disabled_revisions"
      fi
    fi
  else
    printf 'Disabled Snap revisions: skipped (snap is not installed).\n'
  fi
fi
