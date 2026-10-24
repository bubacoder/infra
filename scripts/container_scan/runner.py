"""Sequential scan orchestration and CLI; scheduling is deliberately external."""

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .common import now, read_json, scan_lock, target_key, write_json
from .findings import combine, inventory_counts
from .inventory import inventory, target
from .policy import load_policy
from .reporting import finish
from .scanners import Scanners

REPOSITORY = Path(__file__).resolve().parents[2]


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def scan_image(engine, image, directory, policy):
    image.update(status="running", findings=[])
    if image.get("inventory_error"):
        image["coverage"].append(image["inventory_error"])
        image["status"] = "unscannable"
        return
    directory.mkdir(parents=True, mode=0o700)
    trivy = engine.trivy(image, directory)
    syft = engine.syft(image, directory)
    grype = engine.grype(image, directory) if syft is not None else None
    if syft is None:
        image["stages"]["grype"] = {"status": "not_run", "error": "Syft inventory unavailable"}
    image["findings"] = combine(trivy, grype)
    image["packages"], names = inventory_counts(trivy, syft)
    for tool, result in [("trivy", trivy), ("syft", syft)]:
        if result is not None and not image["packages"][tool]:
            image["coverage"].append(f"{tool}: no packages detected; safety cannot be assessed")
    for container in image["containers"]:
        expected = policy.get("expected_components", {}).get(container["name"])
        if expected and not names.intersection(expected):
            image["coverage"].append(f"{container['name']}: expected runtime absent from Syft inventory ({', '.join(expected)})")
    required = ("trivy", "trivy-cyclonedx", "syft", "grype")
    image["status"] = "complete" if all(image["stages"].get(k, {}).get("status") == "complete" for k in required) else "failed"
    image["coverage"] = sorted(set(image["coverage"]))


def scan(args):
    started = time.monotonic()
    policy = load_policy(args.policy)
    with scan_lock(args.output):
        report = inventory(args.container)
        target_dir = args.output / target_key(report["target"])
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        directory = target_dir / "runs" / run_id
        directory.mkdir(parents=True, mode=0o700)
        report.update(schema=1, run=run_id, started=now(), status="running", selection=args.container, changes=[])
        for image in report["images"]:
            image.update(status="not_run", findings=[])
        write_json(directory / "inventory.json", report)
        engine = Scanners(args.output, directory, report["target"], args.timeout)
        try:
            report["databases_before"] = engine.prepare(policy["database_max_age_hours"])
            report["issues"].extend(engine.issues)
            report["versions"] = engine.versions
            report["setup"] = engine.setup
            for index, image in enumerate(report["images"], 1):
                names = ", ".join(c["name"] for c in image["containers"])
                print(f"[{index}/{len(report['images'])}] {names}", flush=True)
                image_dir = directory / "images" / image["id"].replace(":", "-")
                try:
                    scan_image(engine, image, image_dir, policy)
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    image["status"] = "failed"
                    image["coverage"].append("Could not process scanner artifacts; inspect private reports/logs")
                write_json(directory / "inventory.json", report)
            report["databases_after"] = engine.metadata("after")
            if report["databases_before"] != report["databases_after"]:
                report["issues"].append("Advisory database metadata changed during scan; results are not a fixed snapshot")
            report["issues"].extend(issue for issue in engine.issues if issue not in report["issues"])
        except KeyboardInterrupt:
            report["issues"].append("Scan interrupted; partial results only; no findings may be assumed resolved")
        report["finished"] = now()
        report["seconds"] = time.monotonic() - started
        code = finish(report, directory, target_dir, policy, args.fail_on)
        cached = sum(bool(i["stages"].get("syft", {}).get("cached")) for i in report["images"])
        print(f"Scan {report['status']}; {report['seconds']:.1f}s; Syft inventories reused: {cached}/{len(report['images'])}")
        print(f"Report: {directory / 'summary.md'}")
        return code


def show_report(root):
    target_dir = root / target_key(target())
    pointer = read_json(target_dir / "latest.json")
    if not re.fullmatch(r"[0-9TZ.]+", pointer["run"]):
        raise ValueError("Invalid latest report pointer")
    path = target_dir / "runs" / pointer["run"] / "summary.md"
    print(path.read_text())
    print(f"Report: {path}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Scan running images with Trivy and cached Syft inventories + Grype")
    parser.add_argument("--container", default=os.environ.get("SCAN_CONTAINER") or None)
    parser.add_argument("--fail-on", choices=("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"), default=os.environ.get("SCAN_FAIL_ON") or None)
    parser.add_argument("--output", type=Path, default=REPOSITORY / "reports/trivy")
    parser.add_argument("--policy", type=Path, default=REPOSITORY / "docker/scan-policy.json")
    parser.add_argument("--timeout", type=int, default=1200, help="Per scanner stage timeout in seconds")
    parser.add_argument("--report", action="store_true", help="Show latest combined summary for the current Docker target")
    args = parser.parse_args()
    if args.timeout <= 0 or args.fail_on not in (None, "UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
        parser.error("Invalid timeout or FAIL_ON severity")
    args.output = args.output.resolve()
    os.umask(0o077)
    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        return show_report(args.output) if args.report else scan(args)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        print("Scan unavailable: check Docker access, policy, report history or an overlapping scan. No containers were changed.", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
