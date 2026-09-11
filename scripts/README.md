# Scripts

## System Cleanup

`system-cleanup.sh` reports and optionally clears regenerable Debian/Ubuntu caches. It never removes Docker images, containers, volumes, VM disks, or user files. Run `task system-cleanup` to inspect cleanup candidates, or `task system-cleanup-apply` to clear APT, Docker build, and Snap download caches while retaining 1 GB of journal logs. Use `scripts/system-cleanup.sh --help` to select an individual component, including disabled Snap revisions.

## Third-party scripts

- git-filter-repo.py
    - Quickly rewrite git repository history (filter-branch replacement)
    - Source: https://github.com/newren/git-filter-repo
- test-colors.py
    - Source: https://gist.github.com/lilydjwg/fdeaf79e921c2f413f44b6f613f6ad53
    - More Info: https://github.com/termstandard/colors
