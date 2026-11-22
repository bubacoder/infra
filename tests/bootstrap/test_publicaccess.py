"""Synthetic regressions for the opt-in CrowdSec platform integration."""

# ruff: noqa: PT009, PT027 -- unittest assertions

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap.config import ConfigError, outputs
from tests.bootstrap import test_traefik_native as native
from tests.bootstrap.test_traefik import profile

ROOT = Path(__file__).resolve().parents[2]
STAGER = ROOT / "kubernetes/traefik/crowdsec-plugin/stage.sh"
TEMP_DIRECTORY = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None  # noqa: S108 -- private randomized TemporaryDirectory below


def public_profile():
    value = profile()
    value["roles"].insert(-1, "k3s_crowdsec")
    value["k3s"]["traefik"]["middlewares"].append("publicaccess")
    value["k3s"]["crowdsec"] = {
        "enabled": True,
        "namespace": "security-crowdsec",
        "storage_class": "local-path",
        "storage_size": "1Gi",
        "plugin_image": "registry.example.invalid/crowdsec-plugin@sha256:" + "a" * 64,
        "transport": "http-cluster",
        "online_api": False,
        "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}},
    }
    return value


class PublicAccessTests(unittest.TestCase):
    def render(self, value=None):
        with patch(
            "scripts.bootstrap.config.load_secret_files",
            return_value={"cloudflare_token": "SYNTHETIC_TOKEN_NOT_REAL", "crowdsec_bouncer_key": "SYNTHETIC_BOUNCER_NOT_REAL"},
        ):
            return outputs(value or public_profile())

    def test_complete_chain_is_enabled_and_secret_is_not_in_public_projections(self):
        rendered = self.render()
        for name, text in rendered.items():
            if name != "secrets.yaml":
                self.assertNotIn("SYNTHETIC_BOUNCER_NOT_REAL", text)
                self.assertNotIn("/synthetic/crowdsec-key", text)
        cm = yaml.safe_load(rendered["k3s-traefik-configmap.yaml"])
        policy = yaml.safe_load(cm["data"]["middlewares.yaml"])["http"]["middlewares"]
        self.assertEqual(policy["publicaccess"]["chain"]["middlewares"], ["crowdsec-bouncer", "security-headers"])
        plugin = policy["crowdsec-bouncer"]["plugin"]["crowdsec-bouncer-traefik-plugin"]
        self.assertTrue(plugin["Enabled"])
        self.assertEqual(plugin["UpdateMaxFailure"], 0)
        self.assertTrue(plugin["StreamStartupBlock"])
        self.assertNotIn("CrowdsecLapiKey", plugin)
        self.assertEqual(plugin["CrowdsecLapiKeyFile"], "/etc/traefik/crowdsec/bouncer-key")
        self.assertEqual(plugin["CrowdsecLapiHost"], "bootstrap-crowdsec.security-crowdsec.svc:8080")

    def test_plugin_staging_is_local_bounded_nonprivileged_and_not_controller_fatal(self):
        rendered = self.render()
        values = yaml.safe_load(yaml.safe_load(rendered["k3s-traefik-helmchartconfig.yaml"])["spec"]["valuesContent"])
        init = values["deployment"]["initContainers"][0]
        self.assertEqual(init["image"], public_profile()["k3s"]["crowdsec"]["plugin_image"])
        self.assertEqual(init["imagePullPolicy"], "IfNotPresent")
        self.assertEqual(init["securityContext"]["runAsUser"], 65532)
        self.assertFalse(init["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(init["command"], ["/bin/sh", "/stage.sh"])
        self.assertIn("--experimental.abortonpluginfailure=false", values["additionalArguments"])
        self.assertNotIn("plugins", values.get("experimental", {}))
        secret_volume = next(v for v in values["deployment"]["additionalVolumes"] if "secret" in v)
        self.assertTrue(secret_volume["secret"]["optional"])

    def test_native_lapi_is_internal_persistent_single_writer_without_log_host_mounts(self):
        rendered = self.render()
        deployment = yaml.safe_load(rendered["k3s-crowdsec-deployment.yaml"])
        pod = deployment["spec"]["template"]["spec"]
        self.assertEqual(deployment["spec"]["strategy"], {"type": "Recreate"})
        self.assertEqual(deployment["spec"]["replicas"], 1)
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertFalse(any("hostPath" in v for v in pod["volumes"]))
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        service = yaml.safe_load(rendered["k3s-crowdsec-service.yaml"])
        self.assertEqual(service["spec"]["type"], "ClusterIP")
        policy = yaml.safe_load(rendered["k3s-crowdsec-networkpolicy.yaml"])
        self.assertEqual(policy["spec"]["ingress"][0]["ports"], [{"port": 8080, "protocol": "TCP"}])
        engine = yaml.safe_load(yaml.safe_load(rendered["k3s-crowdsec-configmap.yaml"])["data"]["config.yaml"])
        self.assertEqual(engine["db_config"]["flush"], {"max_items": 5000, "max_age": "7d"})

    def test_resource_quantities_are_canonicalized(self):
        value = public_profile()
        value["k3s"]["crowdsec"]["resources"]["limits"] = {"cpu": "1000m", "memory": "1024Mi"}
        deployment = yaml.safe_load(self.render(value)["k3s-crowdsec-deployment.yaml"])
        resources = deployment["spec"]["template"]["spec"]["containers"][0]["resources"]
        self.assertEqual(resources["limits"], {"cpu": "1", "memory": "1Gi"})

    def test_invalid_or_incomplete_profiles_fail_without_leaking_values(self):
        for field, setting in (
            ("plugin_image", "unpinned:latest"),
            ("transport", "public"),
            ("online_api", "true"),
            ("namespace", "kube-system"),
        ):
            with self.subTest(field=field):
                value = public_profile()
                value["k3s"]["crowdsec"][field] = setting
                with self.assertRaises(ConfigError) as error:
                    self.render(value)
                self.assertNotIn("SENTINEL_PRIVATE", str(error.exception))
        value = public_profile()
        value["roles"].reverse()
        with self.assertRaises(ConfigError):
            self.render(value)

    def test_community_api_is_explicit_and_does_not_enable_signal_sharing(self):
        value = public_profile()
        value["k3s"]["crowdsec"]["online_api"] = True
        rendered = self.render(value)
        cm = yaml.safe_load(rendered["k3s-crowdsec-configmap.yaml"])
        engine = yaml.safe_load(cm["data"]["config.yaml"])
        self.assertFalse(engine["api"]["server"]["online_client"]["sharing"])
        self.assertEqual(engine["api"]["server"]["online_client"]["credentials_path"], "/data/online_api_credentials.yaml")

    @unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
    def test_actual_native_schema_and_secret_template_with_optional_crowdsec(self):
        helper = native.NativeTraefikTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        public = yaml.safe_load(self.render()["host.yaml"])
        source = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/inputs.yaml").read_text())
        validation = [task for task in source if task["name"].startswith(("Validate opt-in Traefik", "Validate opt-in CrowdSec"))]
        tasks = [
            {
                "name": "Validate the real native schema",
                "ansible.builtin.validate_argument_spec": {
                    "argument_spec": yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/spec.yaml").read_text()),
                    "provided_arguments": "{{ bootstrap }}",
                },
            },
            *validation,
            {
                "name": "Render the real Secret without exposing synthetic values",
                "ansible.builtin.template": {
                    "src": str(ROOT / "ansible/roles/k3s_traefik/templates/secret.yaml.j2"),
                    "dest": str(helper.directory / "secret.yaml"),
                    "mode": "0600",
                },
                "no_log": True,
            },
        ]
        result = helper.run_tasks(
            tasks,
            {
                "bootstrap": public,
                "k3s_traefik_token": "SYNTHETIC_TOKEN_NOT_REAL",
                "k3s_crowdsec_bouncer_key": "SYNTHETIC_BOUNCER_KEY_NOT_REAL",
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        secret = yaml.safe_load((helper.directory / "secret.yaml").read_text())
        self.assertEqual(set(secret["data"]), {"token", "bouncer-key"})
        self.assertNotIn("SYNTHETIC_BOUNCER_KEY_NOT_REAL", result.stdout + result.stderr)

        # Exercise the role's filter with Ansible-tagged values, not just Python.
        result = helper.run_tasks(
            [
                {
                    "name": "Compare desired fields with API-defaulted public data",
                    "ansible.builtin.assert": {
                        "that": [
                            "expected | bootstrap_resource_subset(actual)",
                            "not (expected | bootstrap_resource_subset(changed))",
                        ],
                    },
                }
            ],
            {
                "expected": {"spec": {"containers": [{"image": "pinned"}]}},
                "actual": {"spec": {"containers": [{"image": "pinned", "terminationMessagePolicy": "File"}]}},
                "changed": {"spec": {"containers": [{"image": "other"}]}},
            },
            env={"ANSIBLE_FILTER_PLUGINS": str(ROOT / "ansible/roles/k3s_crowdsec/filter_plugins")},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result, captured, _ = helper.handover_fixture(resource_kind="deployment", api_version="apps/v1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(captured.exists())

    def test_public_resource_verification_accepts_defaults_but_not_changed_owned_fields(self):
        spec = importlib.util.spec_from_file_location(
            "bootstrap_resource_filters",
            ROOT / "ansible/roles/k3s_crowdsec/filter_plugins/bootstrap_resources.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        check = module.resource_subset
        desired = {"spec": {"containers": [{"image": "pinned", "securityContext": {"runAsNonRoot": True}}]}}
        actual = {"spec": {"containers": [{"image": "pinned", "securityContext": {"runAsNonRoot": True}, "terminationMessagePolicy": "File"}]}}
        self.assertTrue(check(desired, actual))
        actual["spec"]["containers"][0]["securityContext"]["runAsNonRoot"] = False
        self.assertFalse(check(desired, actual))
        self.assertFalse(check({"enabled": True}, {"enabled": 1}))

    @unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
    def test_ingress_only_update_refuses_a_different_guest_or_cluster(self):
        helper = native.NativeTraefikTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        plays = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap-ingress.yaml").read_text())
        guard = next(task for task in plays[1]["tasks"] if "ansible.builtin.assert" in task)
        variables = {
            "bootstrap_ingress_live_cluster": {"stdout": "synthetic-cluster"},
            "bootstrap_ingress_expected_cluster": "synthetic-cluster",
            "ansible_facts": {"hostname": "synthetic-vm"},
        }
        result = helper.run_tasks([guard], variables)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for change in (
            {"bootstrap_ingress_live_cluster": {"stdout": "different-cluster"}},
            {"ansible_facts": {"hostname": "different-guest"}},
        ):
            with self.subTest(change=change):
                result = helper.run_tasks([guard], {**variables, **change})
                self.assertNotEqual(result.returncode, 0)


class PluginStagingTests(unittest.TestCase):
    def run_stager(self, source, target, *, path=None):
        return subprocess.run(  # noqa: S603 -- repository stager and generated synthetic paths only
            ["/bin/sh", str(STAGER), str(source), str(target)],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env={"PATH": path or "/usr/bin:/bin"},
        )

    def test_absent_source_and_failed_copy_exit_success_without_published_plugin(self):
        with tempfile.TemporaryDirectory(dir=TEMP_DIRECTORY) as tmp:
            root = Path(tmp)
            source, target = root / "absent", root / "output"
            result = self.run_stager(source, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((target / "src").exists())
            self.assertIn("unavailable", result.stderr)
            source.mkdir()
            (source / "go.mod").write_text("module github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin\n")
            (source / ".traefik.yml").write_text("displayName: Synthetic\n")
            (source / "bouncer.go").write_text("package synthetic\n")
            (source / "vendor").mkdir()
            tools = root / "tools"
            tools.mkdir()
            # Exercise a real copy failure without requiring root or chmod tricks.
            (tools / "cp").write_text("#!/bin/sh\nexit 1\n")
            (tools / "cp").chmod(0o755)
            result = self.run_stager(source, target, path=str(tools) + ":/usr/bin:/bin")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((target / "src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin").exists())

    def test_success_publishes_complete_source_and_repeat_uses_same_pod_artifact(self):
        with tempfile.TemporaryDirectory(dir=TEMP_DIRECTORY) as tmp:
            root = Path(tmp)
            source, target = root / "source", root / "output"
            source.mkdir()
            for name, content in {
                "go.mod": "module github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin\n",
                ".traefik.yml": "displayName: Synthetic\n",
                "bouncer.go": "package synthetic\n",
            }.items():
                (source / name).write_text(content)
            (source / "vendor").mkdir()
            result = self.run_stager(source, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            destination = target / "src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin"
            self.assertEqual((destination / "bouncer.go").read_text(), "package synthetic\n")
            self.assertEqual(self.run_stager(source, target).returncode, 0)
            self.assertTrue((destination / ".traefik.yml").exists())
