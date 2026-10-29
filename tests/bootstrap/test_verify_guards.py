"""Structural checks for independent, non-mutating bootstrap verification."""

# ruff: noqa: PT009 -- match bootstrap unittest fixtures

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class BootstrapVerifyGuardTests(unittest.TestCase):
    def test_verify_only_checks_deselected_cilium_before_k3s_verification(self):
        play = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap.yaml").read_text())[1]
        tasks = play["tasks"]
        guards = [task for task in tasks if task.get("ansible.builtin.include_role") == {"name": "k3s_cilium", "tasks_from": "check-absent"}]
        self.assertEqual(len(guards), 1)
        guard = guards[0]
        self.assertEqual(guard["when"], "bootstrap_verify_only and 'k3s' in bootstrap.roles and 'k3s_cilium' not in bootstrap.roles")
        verify = next(task for task in tasks if task.get("ansible.builtin.include_role") == {"name": "k3s", "tasks_from": "verify"})
        self.assertLess(tasks.index(guard), tasks.index(verify))

    def test_verify_only_does_not_run_role_installation_to_check_deselection(self):
        play = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap.yaml").read_text())[1]
        role_installation = next(task for task in play["tasks"] if task.get("ansible.builtin.include_tasks") == "bootstrap/roles.yaml")
        self.assertEqual(role_installation["when"], "not bootstrap_verify_only")


if __name__ == "__main__":
    unittest.main()
