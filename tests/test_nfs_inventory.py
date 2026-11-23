"""Offline tests for the shared NFS inventory validator."""

import importlib.util
import unittest
from pathlib import Path

try:
    import jinja2
except ImportError:
    jinja2 = None

FILE = Path(__file__).resolve().parents[1] / "ansible/roles/nfs_server/files/validate_inventory.py"
SPEC = importlib.util.spec_from_file_location("nfs_inventory_validator", FILE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

VERIFY_FILE = FILE.with_name("verify_active.py")
VERIFY_SPEC = importlib.util.spec_from_file_location("nfs_active_validator", VERIFY_FILE)
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


def valid():
    return {
        "version": 1,
        "server": "192.0.2.10",
        "clients": ["192.0.2.20"],
        "dataRoots": ["/srv/media"],
        "backingMounts": ["/srv"],
        "exports": {
            "books": {
                "source": "/srv/media/books",
                "serverPath": "/srv/books",
                "access": "read-only",
                "capacity": "1Gi",
            }
        },
    }


class TestInventory(unittest.TestCase):
    def test_valid_read_only_and_writable(self):
        for access in ("read-only", "read-write"):
            data = valid()
            data["exports"]["books"]["access"] = access
            self.assertEqual(MODULE.validate(data), data)  # noqa: PT009

    def test_reject_unsafe_inputs(self):
        changes = [
            ("clients", ["*"]),
            ("clients", ["192.0.2.0/0.0.0.255"]),
            ("backingMounts", ["/elsewhere"]),
            ("dataRoots", ["/"]),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                data = valid()
                data[field] = value
                with self.assertRaises(ValueError):  # noqa: PT027
                    MODULE.validate(data)
        data = valid()
        data["exports"]["books"]["serverPath"] = "/srv/books\n*(rw)"
        with self.assertRaises(ValueError):  # noqa: PT027
            MODULE.validate(data)

    def test_duplicate_yaml_keys_fail(self):
        with self.assertRaises(ValueError):  # noqa: PT027
            MODULE.yaml.load("version: 1\nversion: 1\n", Loader=MODULE.UniqueLoader)

    def test_active_exports_must_match(self):
        data = valid()
        data["exports"]["music"] = {
            "source": "/srv/media/music",
            "serverPath": "/srv/music",
            "access": "read-write",
            "capacity": "1Gi",
        }
        good = "/srv/books 192.0.2.20(sync,ro,root_squash,no_subtree_check)\n/srv/music 192.0.2.20(sync,rw,root_squash,no_subtree_check)\n"
        VERIFY.verify(data, good)
        for bad in (
            good.replace("\n", "", 1),
            good.splitlines()[0],
            good.replace("(sync,ro,", "(sync,rw,", 1),
            good.replace("root_squash", "no_root_squash", 1),
            good.replace("root_squash", "root_squash,crossmnt", 1),
            good.replace("root_squash", "root_squash,anonuid=0", 1),
            good.replace("root_squash", "root_squash,anongid=0", 1),
            good.replace("root_squash", "root_squash,anonuid=1234", 1),
        ):
            with self.assertRaises(ValueError):  # noqa: PT027
                VERIFY.verify(data, bad)
        VERIFY.verify(data, good.replace("root_squash", "root_squash,anonuid=65534,anongid=65534"))

    @unittest.skipIf(jinja2 is None, "Jinja2 is required for template rendering")
    def test_multiple_exports_render_as_separate_lines(self):
        data = valid()
        data["exports"]["music"] = {
            "source": "/srv/media/music",
            "serverPath": "/srv/music",
            "access": "read-write",
            "capacity": "1Gi",
        }
        env = jinja2.Environment(trim_blocks=True, keep_trailing_newline=True, autoescape=False)  # noqa: S701
        env.filters["dict2items"] = lambda value: [{"key": key, "value": item} for key, item in value.items()]
        template = FILE.parent.parent / "templates" / "exports.j2"
        output = env.from_string(template.read_text()).render(nfs_server_inventory=data)
        lines = output.splitlines()
        self.assertEqual(len(lines), 3)  # noqa: PT009
        VERIFY.verify(data, "\n".join(lines[1:]))
        VERIFY.verify_configuration(data, output)
        with self.assertRaises(ValueError):  # noqa: PT027
            VERIFY.verify_configuration(data, output.replace("\n", "", 1))

    def test_multiple_clients_on_one_export_line(self):
        data = valid()
        data["clients"].append("192.0.2.21")
        VERIFY.verify(
            data,
            "/srv/books 192.0.2.20(ro,sync,root_squash,no_subtree_check) 192.0.2.21(ro,sync,root_squash,no_subtree_check)",
        )

    def test_export_change_notifies_both_server_handlers(self):
        role = FILE.parent.parent
        handlers = MODULE.yaml.safe_load((role / "handlers/main.yaml").read_text())
        matching = [entry for entry in handlers if entry.get("listen") == "Restart managed NFS server"]
        self.assertEqual(len(matching), 2)  # noqa: PT009
        self.assertIn("ansible.builtin.systemd_service", matching[0])  # noqa: PT009
        self.assertIn("ansible.builtin.command", matching[1])  # noqa: PT009
