"""Private artifacts, bounded subprocesses, and advisory freshness checks."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime


def now():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text())


@contextmanager
def scan_lock(root):
    """One lock also protects shared tool databases and SBOM cache publication."""
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / ".scan.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another scan is running; no second scan was started") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def stop_process(process):
    """Stop only the new process group created for this scanner command."""
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def execute(args, directory, label, *, env=None, timeout=600):
    """Keep potentially sensitive output in private files, never on the console."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {"status": "failed", "started": now(), "command": args}
    started = time.monotonic()
    process = None
    try:
        with (directory / f"{label}.stdout.log").open("w") as out, (directory / f"{label}.stderr.log").open("w") as err:
            process = subprocess.Popen(  # noqa: S603 -- fixed tools and argument arrays; never a shell
                args, stdout=out, stderr=err, env=env, start_new_session=True
            )
            record["returncode"] = process.wait(timeout=timeout)
            if record["returncode"] == 0:
                record["status"] = "complete"
            else:
                record["error"] = f"{args[0]} exited {record['returncode']}; see private logs"
    except subprocess.TimeoutExpired:
        stop_process(process)
        record["error"] = "Command timed out"
    except KeyboardInterrupt:
        if process is not None:
            stop_process(process)
        record["error"] = "Interrupted"
        raise
    except OSError:
        record["error"] = f"Could not execute {args[0]}; check installation and private logs"
    finally:
        record["seconds"] = time.monotonic() - started
        write_json(directory / f"{label}.stage.json", record)
    return record


def validate_json_stage(stage, path, predicate):
    if stage["status"] != "complete":
        return None
    try:
        value = read_json(path)
        if predicate(value):
            return value
    except (ValueError, OSError, TypeError, AttributeError):
        pass
    stage.update(status="failed", error=f"Invalid or missing {path.name}")
    return None


def database_issue(metadata, maximum_hours, label):
    stamp = metadata.get("UpdatedAt") or metadata.get("built")
    if not stamp or metadata.get("valid") is False:
        return f"{label}: advisory database metadata unavailable or invalid"
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).total_seconds() / 3600
    except (ValueError, TypeError):
        return f"{label}: advisory database timestamp is invalid"
    if age > maximum_hours or age < -1:
        return f"{label}: advisory database outside freshness limit ({maximum_hours} hours)"
    return None


def scanner_environment(endpoint):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TRIVY_", "SYFT_", "GRYPE_")) and k != "DOCKER_CONTEXT"}
    env.update(
        DOCKER_HOST=endpoint,
        SYFT_CHECK_FOR_APP_UPDATE="false",
        SYFT_GOLANG_CAPTURE_SYMBOLS="all",
        GRYPE_CHECK_FOR_APP_UPDATE="false",
        GRYPE_DB_AUTO_UPDATE="false",
    )
    return env


def target_key(target):
    return digest({k: target[k] for k in ("daemon_id", "endpoint")})[:20]
