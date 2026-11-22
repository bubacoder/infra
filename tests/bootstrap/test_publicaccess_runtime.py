"""Opt-in disposable Docker tests; never use kubeconfig or existing containers."""

# ruff: noqa: PT009, PT027, S603 -- fixed Docker commands and synthetic fixtures

import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import yaml

from scripts.bootstrap import crowdsec
from tests.bootstrap.test_publicaccess import public_profile

ROOT = Path(__file__).resolve().parents[2]
TRAEFIK = "traefik:v3.7.17@sha256:f4bb143d1135a579b630ed491e17ec50f6f7c9c6a30585ff3d385471d2a86f5a"
PLUGIN_IMAGE = os.environ.get("CROWDSEC_PLUGIN_TEST_IMAGE", "konverter-crowdsec-plugin-test:20261122")
TEMP_DIRECTORY = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None  # noqa: S108 -- private randomized TemporaryDirectory below


@unittest.skipUnless(os.environ.get("RUN_CROWDSEC_RUNTIME_TESTS") == "1" and shutil.which("docker"), "opt-in disposable Docker runtime tests")
class PublicAccessRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP_DIRECTORY)
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o755)
        self.containers = []
        self.owner = "publicaccess-test-" + uuid.uuid4().hex
        (self.directory / ".test-owner").write_text(self.owner)
        self.addCleanup(self.cleanup)

    def docker(self, *args, check=True):
        return subprocess.run([shutil.which("docker"), *args], check=check, capture_output=True, text=True, timeout=60)

    def cleanup(self):
        for name in reversed(self.containers):
            current = self.docker("inspect", "--format", '{{index .Config.Labels "infra.publicaccess-test"}}', name, check=False)
            if current.returncode == 0 and current.stdout.strip() == self.owner:
                self.docker("unpause", name, check=False)
                self.docker("rm", "-f", name)
        # UID 65532 owns files created by the non-root production commands.
        # Restore controller ownership only inside this verified test sandbox.
        if (self.directory / ".test-owner").read_text() != self.owner:
            raise RuntimeError("Refusing cleanup of unowned artifacts")
        self.docker(
            "run",
            "--rm",
            "--network=none",
            "--user=0:0",
            "--entrypoint=/bin/sh",
            "-v",
            str(self.directory) + ":/artifacts",
            PLUGIN_IMAGE,
            "-c",
            'chown -R "$1" /artifacts',
            "cleanup",
            f"{os.getuid()}:{os.getgid()}",
        )
        self.temp.cleanup()

    def run_container(self, image, *options):
        name = self.owner + "-" + str(len(self.containers))
        self.containers.append(name)
        self.docker("run", "-d", "--name", name, "--label", "infra.publicaccess-test=" + self.owner, *options, image)
        return name

    def prepare_plugin(self, *, missing=False):
        output = self.directory / ("missing-plugin" if missing else "plugin")
        output.mkdir(mode=0o777)
        output.chmod(0o777)
        options = ["--network=none", "--read-only", "-v", str(output) + ":/output"]
        if missing:
            options += ["--entrypoint=/bin/sh"]
        args = ["/stage.sh", "/absent", "/output"] if missing else []
        result = self.docker("run", "--rm", *options, PLUGIN_IMAGE, *args)
        self.assertEqual(result.returncode, 0)
        if missing:
            self.assertIn("plugin unavailable", result.stderr)
        return output

    def traefik(self, output, *, lapi="127.0.0.1:1", network="none"):
        configdir = self.directory / ("dynamic-" + str(len(self.containers)))
        configdir.mkdir(mode=0o755)
        plugin = {
            "Enabled": True,
            "CrowdsecMode": "stream",
            "CrowdsecLapiHost": lapi,
            "CrowdsecLapiKeyFile": "/key/bouncer-key",
            "StreamStartupBlock": True,
            "UpdateMaxFailure": 0,
            "UpdateIntervalSeconds": 1,
            "HTTPTimeoutSeconds": 1,
            "MetricsUpdateIntervalSeconds": 0,
        }
        config = {
            "http": {
                "routers": {
                    "local": {"rule": "Path(`/local`)", "service": "ping@internal", "entryPoints": ["web"], "middlewares": ["localaccess"]},
                    "public": {"rule": "Path(`/public`)", "service": "ping@internal", "entryPoints": ["web"], "middlewares": ["publicaccess"]},
                },
                "middlewares": {
                    "localaccess": {"ipAllowList": {"sourceRange": ["127.0.0.1/32"]}},
                    "publicaccess": {"chain": {"middlewares": ["crowdsec-bouncer", "security-headers"]}},
                    "crowdsec-bouncer": {"plugin": {crowdsec.PLUGIN: plugin}},
                    "security-headers": {"headers": {"contentTypeNosniff": True}},
                },
            }
        }
        (configdir / "dynamic.yaml").write_text(yaml.safe_dump(config))
        keydir = self.directory / "keys"
        if not keydir.exists():
            keydir.mkdir(mode=0o755)
            (keydir / "bouncer-key").write_text("SYNTHETIC_TEST_KEY_NOT_REAL")
        name = self.owner + "-" + str(len(self.containers))
        self.containers.append(name)
        self.docker(
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "infra.publicaccess-test=" + self.owner,
            "--network=" + network,
            "--read-only",
            "--tmpfs=/tmp",
            "--user=65532:65532",
            "-v",
            str(output) + ":/plugins-local:ro",
            "-v",
            str(configdir) + ":/dynamic:ro",
            "-v",
            str(keydir) + ":/key:ro",
            TRAEFIK,
            "--global.checknewversion=false",
            "--global.sendanonymoususage=false",
            "--entrypoints.web.address=:8000",
            "--entrypoints.traefik.address=:9000",
            "--ping=true",
            "--providers.file.directory=/dynamic",
            "--providers.file.watch=true",
            f"--experimental.localplugins.{crowdsec.PLUGIN}.modulename={crowdsec.MODULE}",
            "--experimental.abortonpluginfailure=false",
        )
        return name

    def status(self, container, path):
        result = self.docker("exec", container, "wget", "-S", "-O", "/dev/null", "-T", "2", "http://127.0.0.1:8000/" + path, check=False)
        match = re.search(r"HTTP/\S+\s+(\d+)", result.stderr)
        return int(match[1]) if match else None

    def expect(self, container, path, status, timeout=30):
        deadline = time.monotonic() + timeout
        actual = None
        while time.monotonic() < deadline:
            actual = self.status(container, path)
            if actual == status:
                return
            time.sleep(0.2)
        self.fail(f"{path}: expected HTTP {status}, received {actual}; container {container}")

    def test_missing_plugin_is_not_an_ingress_outage_or_public_bypass(self):
        controller = self.traefik(self.prepare_plugin(missing=True))
        self.expect(controller, "local", 200)
        self.expect(controller, "public", 404)

    def test_lapi_unavailable_at_cold_start_preserves_local_access_and_blocks_public(self):
        controller = self.traefik(self.prepare_plugin())
        self.expect(controller, "local", 200)
        self.expect(controller, "public", 403)

    def test_invalid_plugin_source_and_missing_key_do_not_disable_local_routes(self):
        output = self.prepare_plugin()
        module = output / "src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin"
        # A source tree that cannot be interpreted is handled at controller
        # plugin registration, independently of init-container copy validation.
        broken = self.directory / "broken"
        broken.mkdir(mode=0o755)
        destination = broken / "src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin"
        destination.mkdir(parents=True)
        (destination / ".traefik.yml").write_text("displayName: Broken\ntype: middleware\nimport: " + crowdsec.MODULE + "\n")
        (destination / "bouncer.go").write_text("not valid Go\n")
        self.assertTrue((module / "bouncer.go").exists())
        controller = self.traefik(broken)
        self.expect(controller, "local", 200)
        self.expect(controller, "public", 404)
        (self.directory / "keys/bouncer-key").unlink()
        controller = self.traefik(output)
        self.expect(controller, "local", 200)
        self.expect(controller, "public", 404)

    def test_native_lapi_bans_outage_recovery_and_persistent_identity(self):
        value = public_profile()
        rendered = crowdsec.manifests(value, ROOT)
        configdir = self.directory / "engine-config"
        configdir.mkdir(mode=0o755)
        for name, text in yaml.safe_load(rendered["k3s-crowdsec-configmap.yaml"])["data"].items():
            (configdir / name).write_text(text)
        data = self.directory / "data"
        data.mkdir(mode=0o777)
        data.chmod(0o777)
        engine = self.owner + "-engine"
        self.containers.append(engine)
        self.docker(
            "run",
            "-d",
            "--name",
            engine,
            "--label",
            "infra.publicaccess-test=" + self.owner,
            "--network=none",
            "--user=65532:65532",
            "--read-only",
            "--tmpfs=/tmp:uid=65532,gid=65532",
            "-v",
            str(configdir) + ":/etc/crowdsec:ro",
            "-v",
            str(data) + ":/data",
            "--entrypoint=/bin/sh",
            crowdsec.IMAGE,
            "/etc/crowdsec/start.sh",
        )
        # Only synthetic generated credentials are handled; never print them.
        deadline = time.monotonic() + 30
        keydir = self.directory / "keys"
        keydir.mkdir(mode=0o755)
        while time.monotonic() < deadline:
            result = self.docker("exec", engine, "cat", "/data/bouncer-key", check=False)
            if result.returncode == 0 and result.stdout.strip():
                (keydir / "bouncer-key").write_text(result.stdout)
                break
            time.sleep(0.2)
        else:
            # No credentials are emitted by start.sh or its failing commands.
            self.fail("Synthetic LAPI did not generate a bouncer key: " + self.docker("logs", engine).stderr)
        # CAPI status also loads the Hub catalog. It must be usable by the
        # non-root LAPI profile even though acquisition/scenarios are deferred.
        self.docker("exec", engine, "cscli", "-c", "/etc/crowdsec/config.yaml", "hub", "list", "-o", "json")
        controller = self.traefik(self.prepare_plugin(), lapi="127.0.0.1:8080", network="container:" + engine)
        self.expect(controller, "local", 200)
        self.expect(controller, "public", 200)
        self.docker("exec", engine, "cscli", "-c", "/etc/crowdsec/config.yaml", "decisions", "add", "--ip", "127.0.0.1", "--duration", "1m")
        self.expect(controller, "public", 403)
        self.expect(controller, "local", 200)
        self.docker("exec", engine, "cscli", "-c", "/etc/crowdsec/config.yaml", "decisions", "delete", "--ip", "127.0.0.1")
        self.expect(controller, "public", 200)
        self.docker("pause", engine)
        self.expect(controller, "public", 403)
        self.expect(controller, "local", 200)
        self.docker("unpause", engine)
        self.expect(controller, "public", 200)
        # The replacement shares the isolated LAPI network namespace and ports.
        # Stop its predecessor rather than mistaking a bind failure for denial.
        self.docker("stop", controller)
        synthetic_key_path = keydir / "bouncer-key"
        saved = synthetic_key_path.read_text()
        synthetic_key_path.write_text("INVALID_SYNTHETIC_BOUNCER_KEY_NOT_REAL")
        invalid_controller = self.traefik(self.directory / "plugin", lapi="127.0.0.1:8080", network="container:" + engine)
        self.expect(invalid_controller, "local", 200)
        self.expect(invalid_controller, "public", 403)
        synthetic_key_path.write_text(saved)
        self.docker("stop", invalid_controller)
        before = self.docker("exec", engine, "sha256sum", "/data/bouncer-key").stdout
        self.docker("restart", engine)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            after = self.docker("exec", engine, "sha256sum", "/data/bouncer-key", check=False)
            if after.returncode == 0:
                self.assertEqual(after.stdout, before)
                break
            time.sleep(0.2)
        else:
            self.fail("Persistent synthetic bouncer identity was not restored")
        controller = self.traefik(self.directory / "plugin", lapi="127.0.0.1:8080", network="container:" + engine)
        self.expect(controller, "public", 200)
