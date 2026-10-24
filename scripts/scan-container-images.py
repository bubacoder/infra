"""CLI entry point for combined container-image vulnerability scanning."""

import sys

from container_scan.runner import main

if __name__ == "__main__":
    sys.exit(main())
