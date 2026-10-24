"""Snapshot allowlisted Docker metadata only; never read environment or labels."""

import json
import os
import subprocess


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=60).stdout.strip()  # noqa: S603


def target():
    context = run(["docker", "context", "show"])
    endpoint = os.environ.get("DOCKER_HOST") if not os.environ.get("DOCKER_CONTEXT") else None
    endpoint = endpoint or run(["docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"])
    if not endpoint.startswith("unix://"):
        raise ValueError("Only Unix-socket Docker targets are supported; run the task on the Docker host")
    daemon_id = run(["docker", "info", "--format", "{{.ID}}"])
    if not daemon_id:
        raise ValueError("Docker daemon identity is unavailable")
    return {"context": context, "endpoint": endpoint, "daemon_id": daemon_id}


def inventory(container=None):
    snapshot = {"target": target(), "images": [], "issues": []}
    rows = [
        json.loads(line)
        for line in run(
            [
                "docker",
                "ps",
                "--no-trunc",
                "--format",
                '{"id":{{json .ID}},"name":{{json .Names}},"reference":{{json .Image}}}',
            ]
        ).splitlines()
        if line.strip()
    ]
    if container:
        exact = [r for r in rows if r["name"] == container or r["id"] == container]
        rows = exact or [r for r in rows if r["id"].startswith(container)]
        if len(rows) != 1:
            raise ValueError("Select exactly one running container by name or ID")
    images = {}
    for row in rows:
        try:
            image_id = run(["docker", "inspect", "--type", "container", "--format", "{{.Image}}", row["id"]])
        except subprocess.SubprocessError:
            snapshot["issues"].append(f"{row['name']}: container disappeared or could not be inspected")
            continue
        if image_id not in images:
            image = images[image_id] = {"id": image_id, "containers": [], "stages": {}, "coverage": []}
            try:
                image.update(
                    json.loads(
                        run(
                            [
                                "docker",
                                "image",
                                "inspect",
                                "--format",
                                '{"platform":{{json .Architecture}},"digests":{{json .RepoDigests}}}',
                                image_id,
                            ]
                        )
                    )
                )
            except (subprocess.SubprocessError, ValueError):
                image["inventory_error"] = "Original image metadata missing from local Docker image store"
        images[image_id]["containers"].append(row)
    snapshot["images"] = list(images.values())
    return snapshot
