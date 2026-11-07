"""Offline checks for repository/package selection and native Ansible rendering."""

# ruff: noqa: PT009, PT027

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/apt_repositories"
TEST_TEMP_ROOT = Path("/tmp/opencode")  # noqa: S108 -- approved harness directory


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class NativeRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        role = self.directory / "roles/apt_repositories"
        shutil.copytree(ROLE, role)
        # Execute real control flow and expressions, but never mutate host APT.
        path = role / "tasks/repository.yaml"
        tasks = yaml.safe_load(path.read_text())
        for task in tasks[-1]["block"]:
            module = next(key for key in task if key.startswith("ansible.builtin."))
            parameters = task.pop(module)
            # Put nested templates in vars, not inside another Jinja expression.
            task["vars"] = {"repository_test_parameters": parameters}
            task["ansible.builtin.set_fact"] = {
                "repository_test_calls": ("{{ repository_test_calls + [{'module': '" + module + "', 'parameters': repository_test_parameters}] }}")
            }
            task["changed_when"] = "repository_test_source_changed" if "register" in task else False
        path.write_text(yaml.safe_dump(tasks, sort_keys=False))
        (self.directory / "ansible.cfg").write_text("[defaults]\nroles_path=roles\nretry_files_enabled=False\n")

    def run_entries(self, entries, *, source_changed=False, facts=None, extra_vars=None, expect_success=True):
        result_path = self.directory / "result.json"
        play = [
            {
                "hosts": "all",
                "gather_facts": False,
                "vars": {
                    "ansible_facts": facts or {"os_family": "Debian"},
                    "apt_repositories_items": entries,
                    "repository_test_calls": [],
                    "repository_test_source_changed": source_changed,
                    **(extra_vars or {}),
                },
                "roles": ["apt_repositories"],
                "tasks": [
                    {
                        "name": "Save calls",
                        "ansible.builtin.copy": {"dest": str(result_path), "content": "{{ repository_test_calls | to_json }}", "mode": "0600"},
                    }
                ],
            }
        ]
        playbook = self.directory / "test.yaml"
        playbook.write_text(yaml.safe_dump(play, sort_keys=False))
        result = subprocess.run(  # noqa: S603 -- fixed local executable, temp-only playbook with mocked APT
            [shutil.which("ansible-playbook"), "-i", "localhost,", "-c", "local", str(playbook)],
            cwd=self.directory,
            env={**os.environ, "ANSIBLE_CONFIG": str(self.directory / "ansible.cfg"), "ANSIBLE_NOCOLOR": "1"},
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
        if not expect_success:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result_path.read_text())

    @staticmethod
    def entry(**overrides):
        return {
            "name": "vendor",
            "uri": "https://example.com/apt",
            "suites": "stable",
            "components": ["main"],
            "signing_key_url": "https://example.com/key.asc",
            "packages": ["tool=1.2.3"],
            **overrides,
        }

    def test_empty_and_disabled_entries_do_nothing(self):
        self.assertEqual(self.run_entries([]), [])
        self.assertEqual(self.run_entries([{"name": "disabled", "enabled": False}]), [])

    def test_scoped_key_and_package_options(self):
        calls = self.run_entries([self.entry(architectures=["amd64"], allow_downgrade=True)], source_changed=True)
        self.assertEqual([call["module"] for call in calls], ["ansible.builtin.apt", "ansible.builtin.deb822_repository", "ansible.builtin.apt"])
        self.assertIn("python3-debian", calls[0]["parameters"]["name"])
        self.assertEqual(calls[1]["parameters"]["signed_by"], "https://example.com/key.asc")
        self.assertEqual(calls[1]["parameters"]["architectures"], ["amd64"])
        self.assertEqual(calls[2]["parameters"]["name"], ["tool=1.2.3"])
        self.assertTrue(calls[2]["parameters"]["allow_downgrade"])

    def test_invalid_definitions_fail_before_apt_operations(self):
        for overrides in [
            {"uri": "http://example.com/apt"},
            {"signing_key_url": "http://example.com/key.asc"},
            {"name": "../unsafe"},
            {"packages": []},
            {"packages": "tool"},
            {"package_state": "absent"},
        ]:
            with self.subTest(overrides=overrides):
                self.run_entries([self.entry(**overrides)], expect_success=False)

    def test_azure_catalog_uses_correct_distribution_suite(self):
        variables = yaml.safe_load((ROOT / "ansible/inventory/group_vars/debian/vars.yaml").read_text())
        catalog = variables["debian_tools_apt_repository_catalog"]
        for distribution, version, release, expected in [
            ("Debian", "13", "trixie", "bookworm"),
            ("Ubuntu", "26", "resolute", "resolute"),
        ]:
            with self.subTest(distribution=distribution, version=version):
                calls = self.run_entries(
                    ["{{ debian_tools_apt_repository_catalog.azure_cli }}"],
                    facts={
                        "os_family": "Debian",
                        "distribution": distribution,
                        "distribution_major_version": version,
                        "distribution_release": release,
                    },
                    extra_vars={"debian_tools_apt_repository_catalog": catalog},
                )
                self.assertEqual(calls[1]["parameters"]["suites"], expected)
                self.assertEqual(calls[-1]["parameters"]["name"], ["azure-cli"])

    def test_docker_pinned_and_default_package_names_render(self):
        defaults = yaml.safe_load((ROOT / "ansible/roles/debian_docker_host/defaults/main.yaml").read_text())
        inventory = yaml.safe_load((ROOT / "ansible/inventory/inventory.yaml").read_text())
        for distribution, overrides, expected in [
            (
                "Debian",
                inventory["debian"]["hosts"]["nas"],
                ["docker-ce=5:20.10.24~3-0~debian-bullseye", "docker-ce-cli=5:20.10.24~3-0~debian-bullseye", "containerd.io=1.6.33-1"],
            ),
            ("Ubuntu", {}, ["docker-ce", "docker-ce-cli", "containerd.io"]),
        ]:
            with self.subTest(distribution=distribution):
                tasks = yaml.safe_load((ROOT / f"ansible/roles/debian_docker_host/tasks/10-docker-{distribution}.yaml").read_text())
                install = next(task for task in tasks if "ansible.builtin.include_role" in task)
                calls = self.run_entries(
                    install["vars"]["apt_repositories_items"],
                    facts={"os_family": "Debian", "distribution_release": "bullseye" if distribution == "Debian" else "resolute"},
                    extra_vars={**defaults, **overrides},
                )
                self.assertEqual(calls[-1]["parameters"]["name"], expected)
                self.assertTrue(calls[-1]["parameters"]["allow_downgrade"])


if __name__ == "__main__":
    unittest.main()
