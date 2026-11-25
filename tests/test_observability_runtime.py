"""Opt-in container config checks using pinned images and synthetic files only."""

# ruff: noqa: PT009, PT027, S603 -- fixed local Docker commands

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.test_observability import CHART, HELM


@unittest.skipUnless(os.environ.get("RUN_OBSERVABILITY_RUNTIME_TESTS") == "1" and shutil.which("docker"), "opt-in Docker config checks")
class ObservabilityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None)  # noqa: S108 -- optional approved harness parent
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.directory.chmod(0o755)
        rendered = subprocess.check_output([HELM, "template", "observability", str(CHART), "-n", "observability"], text=True)
        self.images = yaml.safe_load((CHART / "values.yaml").read_text())["images"]
        for obj in yaml.safe_load_all(rendered):
            if obj["kind"] != "ConfigMap":
                continue
            folder = self.directory / obj["metadata"]["name"].removeprefix("observability-")
            folder.mkdir()
            for name, text in obj["data"].items():
                (folder / name).write_text(text)

    def run_image(self, name, *arguments, entrypoint=None, hosts=()):
        component = "fluent-bit" if name == "fluentBit" else name
        command = [
            shutil.which("docker"),
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=32m,mode=1777",  # noqa: S108 -- private container tmpfs, not a controller path
            "-v",
            str(self.directory / component) + ":/config:ro",
        ]
        for host in hosts:
            command += ["--add-host", host + ":127.0.0.1"]
        if entrypoint:
            command += ["--entrypoint", entrypoint]
        result = subprocess.run([*command, self.images[name], *arguments], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_loki_config_with_exact_pinned_binary(self):
        self.run_image("loki", "-config.file=/config/loki.yaml", "-verify-config=true")

    def test_prometheus_config_with_exact_pinned_binary(self):
        self.run_image("prometheus", "check", "config", "--syntax-only", "/config/prometheus.yaml", entrypoint="/bin/promtool")
        self.run_image("prometheus", "check", "rules", "/config/rules.yaml", entrypoint="/bin/promtool")

    def test_fluent_bit_config_with_exact_pinned_binary(self):
        self.run_image("fluentBit", "--dry-run", "-c", "/config/fluent-bit.conf", hosts=("observability-loki",))

    def test_query_proxy_config_with_exact_pinned_binary(self):
        self.run_image("query", "-t", "-c", "/config/nginx.conf", entrypoint="nginx", hosts=("observability-loki",))
