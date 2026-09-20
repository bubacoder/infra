"""Tests for update-example-env.py."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parent.parent / "scripts/update-example-env.py"
SPEC = importlib.util.spec_from_file_location("update_example_env", MODULE_PATH)
update_example_env = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError("Cannot load update-example-env.py")
SPEC.loader.exec_module(update_example_env)


class UpdateExampleEnvironmentTests(unittest.TestCase):
    def test_preserves_secret_path_values(self) -> None:
        line = "GRAFANA_AUTHENTIK_CLIENT_SECRET_PATH=/home/admin/secret"
        if update_example_env.mask_line(line) != line:
            self.fail("SECRET_PATH value was masked")

    def test_preserves_secret_path_before_other_matching_rules(self) -> None:
        line = "service_ip_secret_path=/home/admin/secret"
        if update_example_env.mask_line(line) != line:
            self.fail("SECRET_PATH did not take precedence")

    def test_masks_sensitive_values(self) -> None:
        for name in ("API_KEY", "USERNAME", "PASSWORD", "TOKEN", "AUTHENTIK_SECRET"):
            with self.subTest(name=name):
                if update_example_env.mask_line(f"{name}=value") != f'{name}="use-some-very-secure-value-here"':
                    self.fail(f"{name} was not masked")

    def test_generalizes_known_values(self) -> None:
        expected = {
            "TIMEZONE=Europe/Budapest": "TIMEZONE=Etc/UTC",
            "MYDOMAIN=home.example": "MYDOMAIN=example.com",
            "ADMIN_EMAIL=admin@example.com": "ADMIN_EMAIL=root@localhost",
        }
        for source, result in expected.items():
            with self.subTest(source=source):
                if update_example_env.mask_line(source) != result:
                    self.fail(f"{source} was not generalized")

    def test_preserves_comments_blank_lines_and_regular_values(self) -> None:
        for line in ("", "# A comment", "COMPOSE_PROJECT_NAME=infra"):
            with self.subTest(line=line):
                if update_example_env.mask_line(line) != line:
                    self.fail(f"{line!r} was changed")

    def test_masks_an_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / ".env"
            source.write_text("API_TOKEN=secret\nGRAFANA_AUTHENTIK_CLIENT_SECRET_PATH=/home/admin/secret\nMYDOMAIN=home.example\n")

            expected = 'API_TOKEN="use-some-very-secure-value-here"\nGRAFANA_AUTHENTIK_CLIENT_SECRET_PATH=/home/admin/secret\nMYDOMAIN=example.com\n'
            if update_example_env.mask_sensitive_variables(source) != expected:
                self.fail("Environment file was not masked as expected")


if __name__ == "__main__":
    unittest.main()
