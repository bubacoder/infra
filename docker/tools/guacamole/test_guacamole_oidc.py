"""Local validation tests for guacamole-oidc.py."""

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("guacamole-oidc.py")
SPEC = importlib.util.spec_from_file_location("guacamole_oidc", MODULE_PATH)
guacamole_oidc = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError("Cannot load guacamole-oidc.py")
SPEC.loader.exec_module(guacamole_oidc)


class PropertiesTests(unittest.TestCase):
    def test_preserves_unmanaged_properties(self) -> None:
        content = "postgresql-hostname: localhost\nopenid-client-id: old\n"
        updated = guacamole_oidc.update_properties(content, {"openid-client-id": "guacamole"})
        if updated != "postgresql-hostname: localhost\nopenid-client-id: guacamole\n":
            self.fail("Unmanaged properties were not preserved")

    def test_builds_authentik_endpoints(self) -> None:
        properties = guacamole_oidc.desired_properties({"MYDOMAIN": "example.test", "GUACAMOLE_AUTHENTIK_CLIENT_ID": "guacamole"})
        if properties["openid-jwks-endpoint"] != "https://sso.example.test/application/o/guacamole/jwks/":
            self.fail("Unexpected JWKS endpoint")
        if properties["openid-redirect-uri"] != "https://guacamole.example.test":
            self.fail("Unexpected redirect URI")
        if properties["postgresql-auto-create-accounts"] != "true":
            self.fail("External JDBC account creation was not enabled")


if __name__ == "__main__":
    unittest.main()
