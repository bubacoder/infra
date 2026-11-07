"""Regression checks for build-cache isolation and Homebrew package types."""

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


def load_tasks(role, filename="20-homebrew.yaml"):
    return yaml.safe_load((ROOT / f"ansible/roles/{role}/tasks/{filename}").read_text())


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class NativeHomebrewTrustTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir="/tmp/opencode")  # noqa: S108 -- approved harness directory
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.binary_dir = self.directory / "bin"
        self.binary_dir.mkdir()
        brew = self.binary_dir / "brew"
        brew.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "path = Path(os.environ['HOMEBREW_TEST_STATE'])\n"
            "entries = json.loads(path.read_text()) if path.exists() else []\n"
            "assert sys.argv[1] == 'trust' and sys.argv[2] in ('--formula', '--cask')\n"
            "entry = sys.argv[2:]\n"
            "action = 'Already trusted' if entry in entries else 'Trusted'\n"
            "if entry not in entries: entries.append(entry)\n"
            "path.write_text(json.dumps(entries))\n"
            "print(f'{action} {entry[0][2:]}: {entry[1]}')\n"
        )
        brew.chmod(0o700)
        tasks = load_tasks("common", "homebrew-trust.yaml")
        # No real Homebrew operations: record tap selection, execute trust via fake brew.
        tap = tasks[0].pop("community.general.homebrew_tap")
        tasks[0]["ansible.builtin.set_fact"] = {"homebrew_test_taps": tap["name"]}
        self.trust_tasks = self.directory / "trust.yaml"
        self.trust_tasks.write_text(yaml.safe_dump(tasks, sort_keys=False))

    def run_trust(self, terraform_enabled):
        result_file = self.directory / "result.json"
        state_file = self.directory / "trust.json"
        build_casks = next(
            task for task in load_tasks("debian_tools") if "debian_tools_brew_effective_cask_packages" in task.get("ansible.builtin.set_fact", {})
        )
        playbook = [
            {
                "hosts": "all",
                "gather_facts": False,
                "vars": {
                    "ansible_facts": {"env": {"PATH": os.environ["PATH"]}},
                    "debian_tools_brew_install_groups": {"terraform": terraform_enabled},
                    "debian_tools_brew_cask_packages_terraform": ["terraform-linters/tap/tflint"],
                    "common_homebrew_formulae": ["jq", "vendor/tap/tool", "vendor/tap/tool"],
                    "common_homebrew_casks": "{{ debian_tools_brew_effective_cask_packages }}",
                    "common_homebrew_path": str(self.binary_dir),
                },
                "tasks": [
                    build_casks,
                    {"name": "Exercise real trust tasks", "ansible.builtin.include_tasks": str(self.trust_tasks)},
                    {
                        "name": "Save results",
                        "ansible.builtin.copy": {
                            "dest": str(result_file),
                            "mode": "0600",
                            "content": "{{ {'formula_changed': common_homebrew_formula_trust.changed, "
                            "'cask_changed': common_homebrew_cask_trust.changed, 'taps': homebrew_test_taps, "
                            "'casks': debian_tools_brew_effective_cask_packages} | to_json }}",
                        },
                    },
                ],
            }
        ]
        play = self.directory / "play.yaml"
        play.write_text(yaml.safe_dump(playbook, sort_keys=False))
        config = self.directory / "ansible.cfg"
        config.write_text("[defaults]\nretry_files_enabled=False\n")
        result = subprocess.run(  # noqa: S603 -- local temp-only playbook and fake brew
            [shutil.which("ansible-playbook"), "-i", "localhost,", "-c", "local", str(play)],
            cwd=self.directory,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
            env={**os.environ, "ANSIBLE_CONFIG": str(config), "HOMEBREW_TEST_STATE": str(state_file)},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result_file.read_text()), json.loads(state_file.read_text())

    def test_typed_trust_is_deduplicated_and_idempotent(self):
        first, entries = self.run_trust(terraform_enabled=True)
        self.assertEqual(entries, [["--formula", "vendor/tap/tool"], ["--cask", "terraform-linters/tap/tflint"]])
        self.assertEqual(first["taps"], ["vendor/tap", "terraform-linters/tap"])
        self.assertTrue(first["formula_changed"])
        self.assertTrue(first["cask_changed"])
        second, _ = self.run_trust(terraform_enabled=True)
        self.assertFalse(second["formula_changed"])
        self.assertFalse(second["cask_changed"])

    def test_disabled_terraform_group_does_not_trust_or_install_tflint(self):
        result, entries = self.run_trust(terraform_enabled=False)
        self.assertEqual(result["casks"], [])
        self.assertEqual(entries, [["--formula", "vendor/tap/tool"]])


if __name__ == "__main__":
    unittest.main()
