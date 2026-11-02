"""Exercise resolver configuration and notifications against temporary files only."""

# ruff: noqa: PT009, PT027

import configparser
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class DNSStubListenerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.config = self.directory / "resolved.conf"
        self.restart = self.directory / "restarted"
        tasks = yaml.safe_load((ROOT / "ansible/roles/debian_base/tasks/40-network.yaml").read_text())
        probe = next(task for task in tasks if task.get("register") == "debian_base_systemd_resolved_conf")
        setting = next(task for task in tasks if "community.general.ini_file" in task)
        probe["ansible.builtin.stat"]["path"] = str(self.config)
        setting["community.general.ini_file"]["path"] = str(self.config)
        play = [
            {
                "hosts": "all",
                "gather_facts": False,
                "tasks": [probe, setting],
                "handlers": [
                    {
                        "name": "Restart service systemd-resolved",
                        "ansible.builtin.copy": {
                            "dest": str(self.restart),
                            "content": "restart requested",
                            "mode": "0600",
                        },
                    }
                ],
            }
        ]
        self.playbook = self.directory / "test.yaml"
        self.playbook.write_text(yaml.safe_dump(play, sort_keys=False))
        self.ansible_config = self.directory / "ansible.cfg"
        self.ansible_config.write_text("[defaults]\nretry_files_enabled=False\n")

    def run_tasks(self):
        result = subprocess.run(  # noqa: S603 -- local Ansible, temporary configuration and inert handler
            [shutil.which("ansible-playbook"), "-i", "localhost,", "-c", "local", str(self.playbook)],
            cwd=self.directory,
            env={**os.environ, "ANSIBLE_CONFIG": str(self.ansible_config), "ANSIBLE_NOCOLOR": "1"},
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_inserts_or_updates_setting_and_restarts_only_on_change(self):
        for initial in ("[Resolve]\nDNS=192.0.2.53\n", "[Resolve]\nDNS=192.0.2.53\n#DNSStubListener=yes\n"):
            with self.subTest(initial=initial):
                self.config.write_text(initial)
                self.run_tasks()
                parsed = configparser.ConfigParser()
                parsed.read(self.config)
                self.assertEqual(parsed["Resolve"]["DNSStubListener"], "no")
                self.assertEqual(parsed["Resolve"]["DNS"], "192.0.2.53")
                self.assertTrue(self.restart.exists())
                self.restart.unlink()
                before = self.config.read_bytes()
                self.run_tasks()
                self.assertEqual(self.config.read_bytes(), before)
                self.assertFalse(self.restart.exists())

    def test_absent_configuration_is_not_created_or_restarted(self):
        self.run_tasks()
        self.assertFalse(self.config.exists())
        self.assertFalse(self.restart.exists())


if __name__ == "__main__":
    unittest.main()
