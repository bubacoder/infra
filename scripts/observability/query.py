#!/usr/bin/env python3
"""Bounded GET-only Loki queries using a separately provisioned reader context."""

import argparse
import json
import shutil
import subprocess
import sys
import time
from urllib.parse import urlencode


def query_path(query, *, minutes=15, limit=20, now=None):
    if not 1 <= minutes <= 60 or not 1 <= limit <= 100 or not 1 <= len(query) <= 2048:
        raise ValueError("Use a 1–60 minute range, 1–100 results and a query of at most 2048 characters.")
    end = time.time_ns() if now is None else now
    parameters = urlencode({"query": query, "start": end - minutes * 60 * 10**9, "end": end, "limit": limit, "direction": "backward"})
    return "/api/v1/namespaces/observability/services/http:observability-query:8080/proxy/loki/api/v1/query_range?" + parameters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="A separately provisioned, least-privilege reader context")
    parser.add_argument("--query", required=True)
    parser.add_argument("--minutes", type=int, default=15)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        path = query_path(args.query, minutes=args.minutes, limit=args.limit)
    except ValueError as error:
        parser.error(str(error))
    kubectl = shutil.which("kubectl")
    if not kubectl:
        parser.error("kubectl is required")
    # No shell, arbitrary HTTP method, endpoint or administrative operation.
    result = subprocess.run([kubectl, "--context", args.context, "get", "--raw", path], capture_output=True, timeout=45, check=False)  # noqa: S603 -- fixed executable and GET-only API path
    if result.returncode or len(result.stdout) > 1024 * 1024:
        print("Query failed or exceeded the 1 MiB response budget; narrow its scope.", file=sys.stderr)
        return 1
    print(json.dumps(json.loads(result.stdout)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
