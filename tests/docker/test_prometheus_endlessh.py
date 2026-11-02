"""Offline contracts for explicit Docker/Kubernetes Endlessh discovery."""

import copy
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROMETHEUS = ROOT / "docker/monitoring/prometheus"


class PrometheusEndlesshTests(unittest.TestCase):
    def test_prometheus_preserves_docker_default_and_allows_explicit_config_selection(self):
        compose = yaml.safe_load((PROMETHEUS / "prometheus.yaml").read_text())
        service = compose["services"]["prometheus"]
        if service["command"] != ["--config.file=/etc/prometheus/${PROMETHEUS_CONFIG_FILE:-prometheus.yaml}"]:
            self.fail("Docker must keep its default while Kubernetes selects an explicit config file")
        if (
            service["labels"].get("konverter.connect.endlessh.service") != "endlessh/endlessh"
            or service["labels"].get("konverter.connect.endlessh.ports") != "2112/tcp"
        ):
            self.fail("Retain the caller-owned metrics-only grant")

    def test_kubernetes_config_changes_only_the_endlessh_target(self):
        original = yaml.safe_load((PROMETHEUS / "config/prometheus.yaml").read_text())
        expected = copy.deepcopy(original)
        job = next(j for j in expected["scrape_configs"] if j["job_name"] == "endlessh")
        if job["static_configs"] != [{"targets": ["endlessh:2112"]}]:
            self.fail("Keep the existing Docker scrape target")
        job["static_configs"] = [{"targets": ["endlessh.endlessh.svc:2112"]}]
        actual = yaml.safe_load((PROMETHEUS / "config/prometheus.kubernetes.yaml").read_text())
        if actual != expected:
            self.fail("Kubernetes config must change only the explicitly reviewed cross-namespace target")

    def test_metrics_are_exposed_but_not_published(self):
        compose = yaml.safe_load((ROOT / "docker/security/endlessh/endlessh.yaml").read_text())
        service = compose["services"]["endlessh"]
        if service.get("expose") != ["2112"] or service["ports"] != ["2222:2222"]:
            self.fail("Keep tarpit publication and add only internal metrics exposure")
        if "-enable_prometheus" not in service["command"]:
            self.fail("Metrics must be enabled explicitly")


if __name__ == "__main__":
    unittest.main()
