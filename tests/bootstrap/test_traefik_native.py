"""Execute real Ansible ownership/update guards against offline synthetic fixtures."""

# ruff: noqa: PT009, PT027 -- unittest assertions

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.bootstrap.config import outputs
from tests.bootstrap.test_traefik import profile

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/k3s_traefik"


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class NativeTraefikTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None)  # noqa: S108
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.resources = yaml.safe_load((ROLE / "vars/main.yaml").read_text())["k3s_traefik_resources"]
        self.variables = {
            "bootstrap": {"name": "synthetic-vm"},
            "k3s_traefik_directory": str(self.directory),
            "k3s_traefik_manager": "infra-bootstrap-traefik",
            "k3s_traefik_resources": self.resources,
        }

    def run_tasks(self, tasks, variables=None, env=None):
        play = self.directory / "play.yaml"
        play.write_text(
            yaml.safe_dump(
                [
                    {
                        "name": "Offline Traefik safety checks",
                        "hosts": "localhost",
                        "gather_facts": False,
                        "vars": {**self.variables, **(variables or {})},
                        "tasks": tasks,
                    }
                ],
                sort_keys=False,
            )
        )
        return subprocess.run(  # noqa: S603 -- local generated fixture play, probes are mocked
            [shutil.which("ansible-playbook"), "-i", "localhost,", "-c", "local", str(play)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={**os.environ, "ANSIBLE_NOCOLOR": "1", **(env or {})},
        )

    def inspect(self, *, owned=False, manual=False, replaced=False, cluster_changed=False, missing=False):
        receipt = {
            "cluster_uid": "synthetic-cluster",
            "deployment": "synthetic-vm",
            "uids": {item["kind"]: "owned-" + item["kind"] for item in self.resources},
        }
        (self.directory / "receipt.yaml").write_text(yaml.safe_dump(receipt))
        paths = [
            {"item": str(self.directory), "stat": {"exists": owned, "isdir": True, "islnk": False, "mode": "0700", "uid": 0}},
            {"item": str(self.directory / "receipt.yaml"), "stat": {"exists": owned, "isreg": True, "islnk": False, "mode": "0600", "uid": 0}},
        ]
        identities = []
        for item in self.resources:
            uid = "owned-" + item["kind"]
            if replaced and item["kind"] == "helmchartconfig":
                uid = "replacement"
            output = uid + "|infra-bootstrap-traefik|synthetic-vm" if owned or manual else ""
            if missing and item["kind"] == "persistentvolumeclaim":
                output = ""
            identities.append({"item": item, "stdout": output})
            paths.append({"item": str(self.directory / item["file"]), "stat": {"exists": False}})
        fixtures = {
            "k3s_traefik_paths": {"results": paths},
            "k3s_traefik_cluster": {"stdout": "different-cluster" if cluster_changed else "synthetic-cluster"},
            "k3s_traefik_live_identities": {"results": identities},
        }
        tasks = yaml.safe_load((ROLE / "tasks/inspect.yaml").read_text())
        for task in tasks:
            if "ansible.builtin.stat" in task or "ansible.builtin.command" in task:
                register = task["register"]
                task.clear()
                task.update({"name": "Mock metadata probe " + register, "ansible.builtin.set_fact": {register: fixtures[register]}})
        return self.run_tasks(tasks)

    def test_absent_resources_are_accepted_without_adoption(self):
        result = self.inspect()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_existing_matching_labels_without_receipt_are_not_adopted(self):
        result = self.inspect(manual=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not owned by this receipt", result.stdout)

    def test_valid_receipt_is_accepted(self):
        result = self.inspect(owned=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_replaced_missing_and_wrong_cluster_resources_fail_closed(self):
        for option in ("replaced", "missing", "cluster_changed"):
            with self.subTest(option=option):
                result = self.inspect(owned=True, **{option: True})
                self.assertNotEqual(result.returncode, 0)

    def test_update_serialization_preserves_go_templates_and_sets_api_preconditions(self):
        desired = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "bootstrap-traefik-dynamic", "namespace": "kube-system"},
            "data": {"test.yaml": "source: '{{env \"LOCAL_ACCESS_ADMIN_CIDR\"}}'\n"},
        }
        (self.directory / "configmap.yaml").write_text(yaml.safe_dump(desired))
        captured = self.directory / "captured.json"
        tasks = yaml.safe_load((ROLE / "tasks/resource.yaml").read_text())
        for task in tasks:
            if task.get("ansible.builtin.include_tasks") == "ownership.yaml":
                task.clear()
                task.update({"name": "Ownership handover is exercised separately", "ansible.builtin.set_fact": {"test_handover_included": True}})
            if "ansible.builtin.copy" in task:
                task["ansible.builtin.copy"].pop("owner", None)
                task["ansible.builtin.copy"].pop("group", None)
            command = task.pop("ansible.builtin.command", None)
            if command is None:
                continue
            task.pop("changed_when", None)
            register = task.pop("register", None)
            if register == "k3s_traefik_current_cluster":
                task["ansible.builtin.set_fact"] = {register: {"stdout": "synthetic-cluster"}}
            elif command["argv"][2] == "--namespace=kube-system":
                task["ansible.builtin.set_fact"] = {register: {"stdout": "owned-configmap|42|infra-bootstrap-traefik|synthetic-vm"}}
            elif "apply" in command["argv"]:
                task["block"] = [
                    {
                        "name": "Capture the actual templated stdin instead of sending it to Kubernetes",
                        "ansible.builtin.copy": {"content": command["stdin"], "dest": str(captured), "mode": "0600"},
                    },
                    {"name": "Mock apply metadata", "ansible.builtin.set_fact": {register: {"stdout": "owned-configmap|42"}}},
                ]
            else:
                task["ansible.builtin.fail"] = {"msg": "A live create must not run in this offline update fixture"}
        receipt = {"cluster_uid": "synthetic-cluster", "deployment": "synthetic-vm", "uids": {"configmap": "owned-configmap"}}
        result = self.run_tasks(tasks, {"k3s_traefik_resource": self.resources[1], "k3s_traefik_receipt": receipt})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actual = json.loads(captured.read_text())
        self.assertEqual(actual["data"], desired["data"])
        self.assertEqual(actual["metadata"]["uid"], "owned-configmap")
        self.assertEqual(actual["metadata"]["resourceVersion"], "42")

    def test_verification_tasks_have_no_apply_or_installer_actions(self):
        for filename in ("verify.yaml", "verify-resource.yaml", "inspect.yaml"):
            tasks = (ROLE / "tasks" / filename).read_text()
            for forbidden in ("kubectl, apply", "kubectl, create", "rollout, restart", "ansible.builtin.apt:", "ansible.builtin.copy:"):
                self.assertNotIn(forbidden, tasks)
        resource = (ROLE / "tasks/resource.yaml").read_text()
        self.assertNotIn("--force-conflicts", resource)
        self.assertIn("resourceVersion", resource)

    def test_create_ownership_is_migrated_without_reset_or_force(self):
        source = yaml.safe_load((ROLE / "tasks/ownership.yaml").read_text())
        text = yaml.safe_dump(source)
        self.assertIn("/operation", text)
        self.assertIn("/metadata/uid", text)
        self.assertIn("/metadata/resourceVersion", text)
        self.assertIn("--dry-run=server", text)
        self.assertNotIn("--force-conflicts", text)
        self.assertNotIn("op: remove", text)
        configure = (ROLE / "tasks/configure.yaml").read_text()
        self.assertLess(configure.index("ownership.yaml"), configure.index("Validate every resource"))
        resource = (ROLE / "tasks/resource.yaml").read_text()
        self.assertLess(resource.index("Atomically persist"), resource.index("ownership.yaml"))

    def handover_fixture(self, *, operation="Update", uid="owned-configmap", cluster="synthetic-cluster", ambiguous=False, conflict=False):
        own = {
            "manager": "infra-bootstrap-traefik",
            "operation": operation,
            "apiVersion": "v1",
            "fieldsType": "FieldsV1",
            "fieldsV1": {"f:data": {"f:test.yaml": {}}},
        }
        foreign = {
            "manager": "synthetic-controller",
            "operation": "Update",
            "apiVersion": "v1",
            "fieldsType": "FieldsV1",
            "fieldsV1": {"f:metadata": {"f:annotations": {"f:controller-owned": {}}}},
        }
        metadata = {
            "uid": uid,
            "resourceVersion": "42",
            "labels": {"app.kubernetes.io/managed-by": "infra-bootstrap-traefik", "infra.bootstrap/deployment": "synthetic-vm"},
            "managedFields": [foreign, own],
        }
        if ambiguous:
            duplicate = copy.deepcopy(own)
            duplicate["operation"] = "Apply"
            metadata["managedFields"].append(duplicate)
        after = copy.deepcopy(metadata)
        after["managedFields"][1]["operation"] = "Apply"
        after["resourceVersion"] = "43"
        captured = self.directory / "ownership-patch.json"
        tasks = yaml.safe_load((ROLE / "tasks/ownership.yaml").read_text())

        def mock_probes(steps):
            for task in steps:
                if "block" in task:
                    mock_probes(task["block"])
                if "ansible.builtin.copy" in task:
                    task["ansible.builtin.copy"].pop("owner", None)
                    task["ansible.builtin.copy"].pop("group", None)
                command = task.pop("ansible.builtin.command", None)
                if command is None:
                    continue
                register = task.pop("register", None)
                task.pop("changed_when", None)
                if register == "k3s_traefik_handover_cluster":
                    task["ansible.builtin.set_fact"] = {register: {"stdout": cluster}}
                elif register in ("k3s_traefik_handover_metadata", "k3s_traefik_handover_readback"):
                    task["ansible.builtin.set_fact"] = {register: {"stdout": json.dumps(metadata if register.endswith("metadata") else after)}}
                elif "--dry-run=server" in command["argv"]:
                    if conflict:
                        task["ansible.builtin.fail"] = {"msg": "Synthetic API conflict; no ownership mutation is allowed"}
                    else:
                        task["ansible.builtin.set_fact"] = {"test_handover_validated": True}
                else:
                    task["ansible.builtin.copy"] = {"content": command["stdin"], "dest": str(captured), "mode": "0600"}

        mock_probes(tasks)
        receipt = {"cluster_uid": "synthetic-cluster", "deployment": "synthetic-vm", "uids": {"configmap": "owned-configmap"}}
        result = self.run_tasks(tasks, {"k3s_traefik_resource": self.resources[1], "k3s_traefik_receipt": receipt})
        return result, captured, metadata

    def test_handover_preserves_foreign_ownership_and_original_metadata_for_recovery(self):
        result, captured, before = self.handover_fixture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        patch = json.loads(captured.read_text())
        self.assertEqual(
            patch[:2],
            [{"op": "test", "path": "/metadata/uid", "value": "owned-configmap"}, {"op": "test", "path": "/metadata/resourceVersion", "value": "42"}],
        )
        self.assertEqual(patch[2], {"op": "test", "path": "/metadata/managedFields/1", "value": before["managedFields"][1]})
        self.assertEqual(patch[3:], [{"op": "replace", "path": "/metadata/managedFields/1/operation", "value": "Apply"}])
        backups = list(self.directory.glob("ownership-configmap-*/metadata.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), before)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_handover_is_a_noop_after_success(self):
        result, captured, _ = self.handover_fixture(operation="Apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(captured.exists())
        self.assertEqual(list(self.directory.glob("ownership-configmap-*")), [])

    def test_handover_refuses_replaced_objects_wrong_clusters_ambiguity_and_api_conflicts(self):
        for setting in ({"uid": "replacement"}, {"cluster": "other-cluster"}, {"ambiguous": True}, {"conflict": True}):
            with self.subTest(setting=setting):
                result, captured, _ = self.handover_fixture(**setting)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(captured.exists())

    def test_real_native_profile_validation_matches_compiler_inputs(self):
        public = yaml.safe_load(outputs(profile())["host.yaml"])
        validation = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/inputs.yaml").read_text())[-1]
        tasks = [
            {
                "name": "Validate the real public argument schema",
                "ansible.builtin.validate_argument_spec": {
                    "argument_spec": yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/spec.yaml").read_text()),
                    "provided_arguments": "{{ bootstrap }}",
                },
            },
            validation,
        ]
        result = self.run_tasks(tasks, {"bootstrap": public})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        public["k3s"]["traefik"]["admin_cidr"] = "0.0.0.0/0"
        result = self.run_tasks(tasks, {"bootstrap": public})
        self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is not installed")
    def test_staging_probe_rejects_a_certificate_for_the_wrong_hostname(self):
        openssl = shutil.which("openssl")
        cert = self.directory / "synthetic.pem"
        subprocess.run(  # noqa: S603 -- generated synthetic credentials, no live TLS server
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-subj",
                "/CN=bootstrap-check.example.invalid",
                "-days",
                "2",
                "-keyout",
                str(self.directory / "synthetic.key"),
                "-out",
                str(cert),
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )  # noqa: S603 -- generated synthetic credentials only
        binaries = self.directory / "bin"
        binaries.mkdir()
        stub = binaries / "openssl"
        stub.write_text('#!/bin/sh\nif [ "$1" = s_client ]; then cat "$SYNTHETIC_CERT"; else exec "$REAL_OPENSSL" "$@"; fi\n')
        stub.chmod(0o700)
        task = next(task for task in yaml.safe_load((ROLE / "tasks/verify.yaml").read_text())[0]["block"] if "ansible.builtin.shell" in task)
        task["retries"] = 0
        task["delay"] = 0
        env = {"PATH": str(binaries) + os.pathsep + os.environ["PATH"], "SYNTHETIC_CERT": str(cert), "REAL_OPENSSL": openssl}
        for domain, expected in (("example.invalid", 0), ("different.example.invalid", 1)):
            result = self.run_tasks(
                [task],
                {"ansible_facts": {"default_ipv4": {"address": "192.0.2.1"}}, "k3s_traefik": {"domain": domain, "acme_environment": "staging"}},
                env=env,
            )
            if expected:
                self.assertNotEqual(result.returncode, 0)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
