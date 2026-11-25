#!/usr/bin/env python3
"""Synthetic acceptance; optional replacements affect only the owned new stack."""

import argparse
import json
import shutil
import subprocess
import time
import uuid
from urllib.parse import urlencode

from query import query_path

IMAGE = "alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a"
NAMESPACE = "observability-smoke"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_records(kubectl, query, *, now=None):
    result = json.loads(kubectl("get", "--raw", query_path(query, minutes=5, limit=100, now=now), reader=True).stdout)
    return [
        {**json.loads(v[1]), "namespace": stream["stream"]["namespace"], "app": stream["stream"]["app"], "timestamp": int(v[0])}
        for stream in result.get("data", {}).get("result", [])
        for v in stream.get("values", [])
    ]


def restart_owned_stack(kubectl, query, sample):
    """Verify old data and new delivery across a bounded, owned-stack outage."""
    start = time.time_ns()
    for kind, name in [("deployment", "observability-loki"), ("daemonset", "observability-fluent-bit")]:
        resource = json.loads(kubectl("-n", "observability", "get", kind, name, "-o=json").stdout)
        metadata = resource["metadata"]
        require(metadata.get("annotations", {}).get("meta.helm.sh/release-name") == "observability", "Refusing to restart a non-owned resource")
        annotations = resource["spec"]["template"]["metadata"].get("annotations", {})
        patch = [
            {"op": "test", "path": "/metadata/uid", "value": metadata["uid"]},
            {"op": "test", "path": "/metadata/resourceVersion", "value": metadata["resourceVersion"]},
            {
                "op": "add",
                "path": "/spec/template/metadata/annotations",
                "value": {**annotations, "infra.observability/synthetic-restart": uuid.uuid4().hex},
            },
        ]
        kubectl("-n", "observability", "patch", kind, name, "--type=json", "-p", json.dumps(patch))
        kubectl("-n", "observability", "rollout", "status", kind + "/" + name, "--timeout=120s")
    historical = read_records(kubectl, query, now=sample["timestamp"] + 1)
    require(
        any(r["timestamp"] == sample["timestamp"] and r["message"] == sample["message"] for r in historical), "Pre-restart sample was not preserved"
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if any(r["timestamp"] > start for r in read_records(kubectl, query)):
            print("Stored sample and new delivery survived Loki/collector Pod replacement", flush=True)
            return
        time.sleep(3)
    raise RuntimeError("New synthetic delivery did not recover; evidence retained")


def main():  # noqa: PLR0915 -- one bounded ownership-guarded acceptance sequence
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--cluster-uid", required=True)
    parser.add_argument("--resume-owner")
    parser.add_argument("--resume-uid")
    parser.add_argument("--restart-owned", action="store_true", help="Also replace only the new owned Loki/collector Pods")
    args = parser.parse_args()
    executable = shutil.which("kubectl")
    if not executable:
        parser.error("kubectl is required")

    def kubectl(*command, body=None, check=True, reader=False):
        argv = [executable, "--context", args.context]
        if reader:
            argv += ["--as=system:serviceaccount:observability:observability-reader"]
        result = subprocess.run(  # noqa: S603 -- fixed kubectl, explicit context, synthetic bodies only
            [*argv, *command],
            input=json.dumps(body) if body is not None else None,
            capture_output=True,
            text=True,
            timeout=150,
            check=False,
        )
        if check and result.returncode:
            raise RuntimeError(f"Synthetic check failed: {command[:3]}: {result.stderr[:500]}")
        return result

    identity = kubectl("get", "namespace", "kube-system", "-o=jsonpath={.metadata.uid}").stdout
    if identity != args.cluster_uid:
        parser.error("Cluster identity differs; no test resources created")
    if bool(args.resume_owner) != bool(args.resume_uid):
        parser.error("Resume requires both the recorded owner and namespace UID")

    owner = args.resume_owner or "observability-smoke-" + uuid.uuid4().hex
    created = (
        json.loads(kubectl("get", "namespace", NAMESPACE, "-o=json").stdout)
        if args.resume_uid
        else json.loads(
            kubectl(
                "create",
                "-f=-",
                "-o=json",
                body={
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {"name": NAMESPACE, "labels": {"infra.observability/test-owner": owner}},
                },
            ).stdout
        )
    )
    uid = created["metadata"]["uid"]
    if args.resume_uid:
        require(
            uid == args.resume_uid and created["metadata"]["labels"].get("infra.observability/test-owner") == owner,
            "Resume identity differs; retained namespace is untouched",
        )
    nonce = uuid.uuid4().hex[:8]
    source_name, client_name = "source-" + nonce, "client-" + nonce
    marker = owner + "-" + nonce
    print("Created synthetic namespace; owner:", owner, "UID:", uid, flush=True)
    # Failure evidence remains on any exception. Never delete an unknown namespace.
    security = {"runAsNonRoot": True, "runAsUser": 65532, "seccompProfile": {"type": "RuntimeDefault"}}
    kubectl(
        "-n",
        NAMESPACE,
        "create",
        "-f=-",
        body={
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "bounded-test-egress-" + nonce, "labels": {"infra.observability/test-owner": owner}},
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [
                    {
                        "to": [
                            {
                                "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
                                "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                            }
                        ],
                        "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                    },
                    {
                        "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "observability"}}}],
                        "ports": [{"protocol": "TCP", "port": port} for port in (3100, 8080, 9090)],
                    },
                ],
            },
        },
    )
    kubectl(
        "-n",
        NAMESPACE,
        "create",
        "-f=-",
        body={
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": source_name, "labels": {"app": "observability-smoke", "infra.observability/test-owner": owner}},
            "spec": {
                "automountServiceAccountToken": False,
                "restartPolicy": "Never",
                "securityContext": security,
                "containers": [
                    {
                        "name": "source",
                        "image": IMAGE,
                        "command": [
                            "/bin/sh",
                            "-c",
                            'i=0; while [ "$i" -lt 300 ]; do echo "'
                            + marker
                            + ' plain-$i"; echo \'{"message":"'
                            + marker
                            + '","severity":"info","kind":"json"}\'; echo "'
                            + marker
                            + ' stderr-$i" >&2; i=$((i+1)); sleep 2; done',
                        ],
                        "resources": {"requests": {"cpu": "5m", "memory": "8Mi"}, "limits": {"cpu": "50m", "memory": "32Mi"}},
                        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                    }
                ],
            },
        },
    )
    kubectl("-n", NAMESPACE, "wait", "--for=condition=Ready", "pod/" + source_name, "--timeout=90s")
    query = '{namespace="observability-smoke",app="observability-smoke"} |= "' + marker + '"'
    deadline = time.monotonic() + 90
    records = []
    while time.monotonic() < deadline:
        records = read_records(kubectl, query)
        if (
            any("plain-" in r["message"] for r in records)
            and any(r.get("parsed", {}).get("kind") == "json" for r in records)
            and any(r.get("stream") == "stderr" for r in records)
        ):
            break
        time.sleep(3)
    else:
        raise RuntimeError("Plain-text and JSON records were not queryable; test evidence retained")
    require(all(r["namespace"] == NAMESPACE and r["app"] == "observability-smoke" for r in records), "Synthetic identity mapping differs")
    require(all(abs(time.time_ns() - r["timestamp"]) < 300 * 10**9 for r in records), "Synthetic timestamps differ")
    print("Plain-text/JSON/stdout/stderr and timestamps verified through the reader identity;", len(records), "synthetic records", flush=True)

    # The reader must be unable to use ingestion or admin paths.
    for path in ["/loki/api/v1/push", "/loki/api/v1/delete", "/config"]:
        endpoint = "/api/v1/namespaces/observability/services/http:observability-query:8080/proxy" + path
        denied = kubectl("get", "--raw", endpoint, reader=True, check=False)
        require(denied.returncode != 0, "Query boundary accepted a forbidden endpoint")
    denied = kubectl("auth", "can-i", "create", "services/proxy", "-n", "observability", reader=True, check=False)
    require(denied.stdout.strip() == "no", "Reader unexpectedly has write access")
    print("Reader denied write methods and ingestion/admin endpoints", flush=True)

    kubectl(
        "-n",
        NAMESPACE,
        "create",
        "-f=-",
        body={
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": client_name, "labels": {"app": "untrusted-client", "infra.observability/test-owner": owner}},
            "spec": {
                "automountServiceAccountToken": False,
                "restartPolicy": "Never",
                "securityContext": security,
                "containers": [
                    {
                        "name": "client",
                        "image": IMAGE,
                        "command": [
                            "/bin/sh",
                            "-c",
                            "nslookup observability-loki.observability.svc.cluster.local || exit 2; "
                            "for url in observability-loki.observability.svc.cluster.local:3100/ready "
                            "observability-query.observability.svc.cluster.local:8080/ready "
                            "observability-prometheus.observability.svc.cluster.local:9090/-/ready; do "
                            'if wget -q -T 3 -O /dev/null "http://$url"; then exit 1; fi; done; exit 0',
                        ],
                        "resources": {"requests": {"cpu": "5m", "memory": "8Mi"}, "limits": {"cpu": "50m", "memory": "32Mi"}},
                        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                    }
                ],
            },
        },
    )
    kubectl("-n", NAMESPACE, "wait", "--for=jsonpath={.status.containerStatuses[0].state.terminated}", "pod/" + client_name, "--timeout=90s")
    exit_code = kubectl("-n", NAMESPACE, "get", "pod", client_name, "-o=jsonpath={.status.containerStatuses[0].state.terminated.exitCode}").stdout
    require(exit_code == "0", "DNS-positive network denial check failed; retain synthetic client evidence")
    print("DNS-positive untrusted client denied backend/query/Prometheus access", flush=True)

    # Only report aggregate health, never unrelated metric series or log records.
    for job in ["kubelet", "kubelet-cadvisor", "observability"]:
        parameters = urlencode({"query": 'count(up{job="' + job + '"} == 1)'})
        endpoint = "/api/v1/namespaces/observability/services/http:observability-prometheus:9090/proxy/api/v1/query?" + parameters
        values = json.loads(kubectl("get", "--raw", endpoint).stdout)["data"]["result"]
        require(values and float(values[0]["value"][1]) >= 1, "No healthy native scrape for " + job)
        print("Healthy native scrape:", job, flush=True)

    if args.restart_owned:
        restart_owned_stack(kubectl, query, records[0])

    current = json.loads(kubectl("get", "namespace", NAMESPACE, "-o=json").stdout)
    require(
        current["metadata"]["uid"] == uid and current["metadata"]["labels"]["infra.observability/test-owner"] == owner,
        "Cleanup identity differs; no namespace is deleted",
    )
    kubectl(
        "delete",
        "--raw",
        "/api/v1/namespaces/" + NAMESPACE,
        "-f=-",
        body={
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {"uid": uid},
        },
    )
    print("Removed exact test-owned namespace; logging backends and claims retained")


if __name__ == "__main__":
    main()
