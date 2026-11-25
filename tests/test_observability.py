"""Offline render/safety regressions for the additive native monitoring stack."""

# ruff: noqa: PT009, PT027, S603 -- unittest and fixed Helm commands on repository fixtures

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.observability.query import query_path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "kubernetes/observability"
HELM = shutil.which("helm")


@unittest.skipUnless(HELM, "Helm is required")
class ObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = subprocess.check_output(
            [HELM, "template", "observability", str(CHART), "--namespace", "observability"],
            text=True,
        )
        cls.objects = list(yaml.safe_load_all(cls.raw))
        cls.by_name = {(o["kind"], o["metadata"]["name"]): o for o in cls.objects}

    def test_render_is_deterministic_and_has_no_operator_or_public_routes(self):
        repeat = subprocess.check_output(
            [HELM, "template", "observability", str(CHART), "--namespace", "observability"],
            text=True,
        )
        self.assertEqual(self.raw, repeat)
        self.assertFalse({"Ingress", "IngressRoute", "CustomResourceDefinition", "Secret"} & {o["kind"] for o in self.objects})
        for obj in self.objects:
            if obj["kind"] == "Service":
                self.assertEqual(obj["spec"]["type"], "ClusterIP")

    def test_persistent_backends_and_no_privileged_or_host_network_pods(self):
        claims = [o for o in self.objects if o["kind"] == "PersistentVolumeClaim"]
        self.assertEqual(len(claims), 3)
        for claim in claims:
            self.assertEqual(claim["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")
        for obj in self.objects:
            if obj["kind"] not in {"Deployment", "DaemonSet"}:
                continue
            pod = obj["spec"]["template"]["spec"]
            self.assertFalse(pod.get("hostNetwork", False))
            self.assertFalse(pod.get("hostPID", False))
            self.assertEqual(pod["securityContext"]["seccompProfile"]["type"], "RuntimeDefault")
            for container in pod["containers"]:
                self.assertRegex(container["image"], r"@sha256:[a-f0-9]{64}$")
                self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
                self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
                self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])

    def test_loki_retention_and_state_are_on_one_persistent_mount(self):
        data = self.by_name["ConfigMap", "observability-loki"]["data"]
        config = yaml.safe_load(data["loki.yaml"])
        self.assertTrue(config["compactor"]["retention_enabled"])
        self.assertEqual(config["compactor"]["delete_request_store"], "filesystem")
        self.assertEqual(config["schema_config"]["configs"][0]["schema"], "v13")
        self.assertEqual(config["schema_config"]["configs"][0]["index"]["period"], "24h")
        self.assertEqual(config["limits_config"]["retention_period"], "720h")
        self.assertEqual(config["common"]["replication_factor"], 1)
        self.assertEqual(config["ingester"]["wal"]["dir"], "/data/wal")

    def test_collector_is_allowlisted_and_has_bounded_durable_state(self):
        data = self.by_name["ConfigMap", "observability-fluent-bit"]["data"]
        config = data["fluent-bit.conf"]
        self.assertIn("Read_from_Head Off", config)
        self.assertIn("storage.total_limit_size 256M", config)
        self.assertIn("DB /state/tail.db", config)
        self.assertIn("storage.type filesystem", config)
        self.assertIn("Skip_Long_Lines On", config)
        self.assertIn("multiline.parser cri", config)
        self.assertNotIn("Path /var/log/containers/*.log\n", config)
        self.assertIn("Keep_Log On", config)
        self.assertIn("Auto_Kubernetes_Labels Off", config)
        self.assertIn("Annotations Off", config)
        self.assertIn('record["app"] = "unknown"', data["normalize.lua"])
        pod = self.by_name["DaemonSet", "observability-fluent-bit"]["spec"]["template"]["spec"]
        self.assertEqual(
            {v["hostPath"]["path"] for v in pod["volumes"] if "hostPath" in v},
            {"/var/log/containers", "/var/log/pods", "/var/lib/infra-observability/fluent-bit"},
        )

    def test_prometheus_scrapes_kubernetes_without_insecure_tls_or_proxy_rbac(self):
        config = yaml.safe_load(self.by_name["ConfigMap", "observability-prometheus"]["data"]["prometheus.yaml"])
        jobs = {j["job_name"]: j for j in config["scrape_configs"]}
        self.assertEqual(jobs["kubelet"]["scheme"], "https")
        self.assertEqual(jobs["kubelet-cadvisor"]["metrics_path"], "/metrics/cadvisor")
        self.assertNotIn("insecure_skip_verify", json.dumps(config))
        rules = self.by_name["ClusterRole", "observability-observability-prometheus"]["rules"]
        self.assertNotIn("nodes/proxy", json.dumps(rules))
        self.assertNotIn("secrets", json.dumps(rules))
        self.assertNotIn('"*"', json.dumps(rules))

    def test_query_boundary_and_default_deny(self):
        config = self.by_name["ConfigMap", "observability-query"]["data"]["nginx.conf"]
        self.assertIn("limit_except GET", config)
        self.assertIn("return 403", config)
        self.assertNotIn("loki/api/v1/push", config)
        self.assertNotIn("loki/api/v1/delete", config)
        deny = self.by_name["NetworkPolicy", "observability-default-deny"]["spec"]
        self.assertEqual(deny["podSelector"], {})
        self.assertEqual(set(deny["policyTypes"]), {"Ingress", "Egress"})
        reader = self.by_name["Role", "observability-reader"]["rules"]
        self.assertEqual(
            reader, [{"apiGroups": [""], "resources": ["services/proxy"], "resourceNames": ["http:observability-query:8080"], "verbs": ["get"]}]
        )

    def test_grafana_has_declarative_datasources_and_no_anonymous_access(self):
        data = self.by_name["ConfigMap", "observability-grafana"]["data"]
        sources = yaml.safe_load(data["datasources.yaml"])["datasources"]
        self.assertEqual({s["uid"] for s in sources}, {"native-prometheus", "native-loki"})
        self.assertIn("enabled = false", data["grafana.ini"])
        self.assertIn("observability-query", next(s["url"] for s in sources if s["type"] == "loki"))

    def test_invalid_profiles_fail_before_render(self):
        for setting in (
            "cluster=bad/cluster",
            "loki.retention=1h",
            "collector.namespaces={kube-system}",
            "collector.statePath=/",
            "grafana.adminSecret=",
            "prometheus.storage.size=garbage",
        ):
            with self.subTest(setting=setting):
                result = subprocess.run(
                    [HELM, "template", "observability", str(CHART), "--set", setting],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)

    def test_optional_oidc_keeps_private_credentials_and_explicit_egress(self):
        raw = subprocess.check_output(
            [
                HELM,
                "template",
                "observability",
                str(CHART),
                "-n",
                "observability",
                "--set",
                "grafana.oidc.enabled=true",
                "--set",
                "grafana.oidc.secret=existing-oidc",
                "--set",
                "grafana.oidc.host=sso.example.invalid",
                "--set",
                "grafana.oidc.authBaseUrl=https://sso.example.invalid/application/o",
                "--set",
                "grafana.oidc.rootUrl=https://grafana.example.invalid",
                "--set",
                "grafana.oidc.logoutUrl=https://sso.example.invalid/application/o/grafana/end-session/",
            ],
            text=True,
        )
        objects = list(yaml.safe_load_all(raw))
        self.assertFalse(any(o["kind"] == "Secret" for o in objects))
        policy = next(o for o in objects if o["kind"] == "CiliumNetworkPolicy" and o["metadata"]["name"].endswith("-oidc"))
        self.assertEqual(policy["spec"]["egress"][1]["toFQDNs"], [{"matchName": "sso.example.invalid"}])
        config = next(o for o in objects if o["kind"] == "ConfigMap" and o["metadata"]["name"].endswith("-grafana"))
        self.assertIn("client_secret = $__file", config["data"]["grafana.ini"])


class QueryBoundaryTests(unittest.TestCase):
    def test_query_is_get_only_with_explicit_bounded_range_and_limit(self):
        from urllib.parse import parse_qs, urlsplit  # noqa: PLC0415 -- local test helper

        path = query_path('{namespace="synthetic"}', now=10**15, minutes=5, limit=10)
        url = urlsplit(path)
        self.assertEqual(url.path, "/api/v1/namespaces/observability/services/http:observability-query:8080/proxy/loki/api/v1/query_range")
        values = parse_qs(url.query)
        self.assertEqual(int(values["end"][0]) - int(values["start"][0]), 300 * 10**9)
        for options in ({"minutes": 0}, {"minutes": 61}, {"limit": 101}, {"limit": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                query_path("{}", **options)


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is required")
class ObservabilityGuardTests(unittest.TestCase):
    def test_credential_identity_is_durable_before_block_condition_changes(self):
        tasks = yaml.safe_load((ROOT / "ansible/roles/k3s_observability/tasks/install.yaml").read_text())
        block = next(
            t for t in tasks if any("k3s_observability_admin_password" in child.get("ansible.builtin.set_fact", {}) for child in t.get("block", []))
        )
        with tempfile.TemporaryDirectory(
            dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None  # noqa: S108 -- optional approved parent
        ) as directory:
            root = Path(directory)
            binary = root / "kubectl"
            binary.write_text("#!/bin/sh\ncat >/dev/null\nprintf synthetic-created-uid\n")
            binary.chmod(0o755)
            play = root / "play.yaml"
            play.write_text(
                yaml.safe_dump(
                    [
                        {
                            "hosts": "localhost",
                            "connection": "local",
                            "gather_facts": False,
                            "vars": {
                                "k3s_observability_state_dir": str(root),
                                "k3s_observability_context": "synthetic",
                                "k3s_observability_namespace": "synthetic",
                                "k3s_observability_receipt": {"admin_uid": ""},
                                "k3s_observability_settings": {"grafana": {"adminSecret": "synthetic"}},
                            },
                            "tasks": [block],
                        }
                    ]
                )
            )
            result = subprocess.run(
                [shutil.which("ansible-playbook"), "-i", "localhost,", str(play)],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"]},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(yaml.safe_load((root / "receipt.yaml").read_text())["admin_uid"], "synthetic-created-uid")

    def test_actual_role_refuses_wrong_cluster_or_unowned_namespace_without_mutation(self):
        for mode, expected in [("wrong-cluster", "Cluster identity differs"), ("existing-namespace", "Namespace is unowned")]:
            with (
                self.subTest(mode=mode),
                tempfile.TemporaryDirectory(
                    dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None  # noqa: S108 -- optional approved harness directory
                ) as directory,
            ):
                root = Path(directory)
                binary = root / "kubectl"
                marker = root / "mutations"
                binary.write_text(
                    "#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n"
                    "a=sys.argv[1:]\n"
                    f"if 'get' not in a: Path({str(marker)!r}).write_text('mutation'); sys.exit(1)\n"
                    f"print({'22222222-2222-2222-2222-222222222222' if mode == 'wrong-cluster' else '11111111-1111-1111-1111-111111111111'!r}"
                    " if 'kube-system' in a else 'foreign-uid|external-owner', end='')\n"
                )
                binary.chmod(0o755)
                play = root / "play.yaml"
                play.write_text(
                    yaml.safe_dump(
                        [
                            {
                                "hosts": "localhost",
                                "connection": "local",
                                "gather_facts": True,
                                "vars": {
                                    "k3s_observability_context": "synthetic",
                                    "k3s_observability_cluster_uid": "11111111-1111-1111-1111-111111111111",
                                    "k3s_observability_state_dir": str(root / "state"),
                                    "k3s_observability_values": str(ROOT / "config-example/kubernetes/observability.yaml"),
                                },
                                "roles": ["k3s_observability"],
                            }
                        ]
                    )
                )
                result = subprocess.run(
                    [shutil.which("ansible-playbook"), "-i", "localhost,", str(play)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                    env={
                        **os.environ,
                        "PATH": str(root) + os.pathsep + os.environ["PATH"],
                        "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg"),
                        "ANSIBLE_ROLES_PATH": str(ROOT / "ansible/roles"),
                    },
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stdout)
                self.assertFalse(marker.exists())
                self.assertFalse((root / "state").exists())
