"""Local validation tests for authentik-apps.py."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("authentik-apps.py")
SPEC = importlib.util.spec_from_file_location("authentik_apps", MODULE_PATH)
authentik_apps = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError("Cannot load authentik-apps.py")
SPEC.loader.exec_module(authentik_apps)


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.host = Path(self.tempdir.name)
        self.manifest = self.host / "apps.yaml"
        self.manifest.write_text("""version: 1
authentik:
  url: "${AUTHENTIK_URL}"
  token_file: authentik/api-token
  outpost: authentik Embedded Outpost
applications:
  - name: Grafana
    slug: grafana
    launch_url: "https://grafana.${MYDOMAIN}/"
    group: monitoring
    provider:
      type: oidc
      name: Grafana
      client_id: "${CLIENT_ID}"
      client_secret_file: grafana/secret
      redirect_uris: ["https://grafana.${MYDOMAIN}/login/generic_oauth"]
""")
        self.env = {"AUTHENTIK_URL": "https://sso.example.test", "MYDOMAIN": "example.test", "CLIENT_ID": "grafana"}

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_valid_manifest_needs_no_network(self) -> None:
        loaded = authentik_apps.load_manifest(self.manifest, self.env, self.host)
        if loaded["authentik"]["url"] != "https://sso.example.test":
            self.fail("Auth URL was not expanded")
        if loaded["applications"][0]["provider"]["scope_mappings"] != list(authentik_apps.OIDC_MAPPINGS):
            self.fail("Default OIDC scope mappings were not applied")

    def test_rejects_duplicate_oidc_scope_mappings(self) -> None:
        self.manifest.write_text(
            self.manifest.read_text().replace(
                'redirect_uris: ["https://grafana.${MYDOMAIN}/login/generic_oauth"]',
                'redirect_uris: ["https://grafana.${MYDOMAIN}/login/generic_oauth"]\n      scope_mappings: [duplicate, duplicate]',
            )
        )
        try:
            authentik_apps.load_manifest(self.manifest, self.env, self.host)
        except authentik_apps.ConfigError:
            return
        self.fail("Duplicate OIDC scope mappings were accepted")

    def test_loads_oidc_signing_key(self) -> None:
        self.manifest.write_text(
            self.manifest.read_text().replace(
                'redirect_uris: ["https://grafana.${MYDOMAIN}/login/generic_oauth"]',
                'redirect_uris: ["https://grafana.${MYDOMAIN}/login/generic_oauth"]\n      signing_key: "${SIGNING_KEY}"',
            )
        )
        loaded = authentik_apps.load_manifest(self.manifest, dict(self.env, SIGNING_KEY="signing-key-id"), self.host)
        if loaded["applications"][0]["provider"].get("signing_key") != "signing-key-id":
            self.fail("OIDC signing key was not loaded")

    def test_loads_public_implicit_client_without_secret(self) -> None:
        self.manifest.write_text(
            self.manifest.read_text().replace(
                "      client_secret_file: grafana/secret\n",
                "      client_type: public\n      grant_types: [implicit]\n",
            )
        )
        loaded = authentik_apps.load_manifest(self.manifest, self.env, self.host)
        provider = loaded["applications"][0]["provider"]
        if provider["client_type"] != "public" or provider["grant_types"] != ["implicit"]:
            self.fail("Public implicit client was not loaded")

    def test_expands_nested_environment_values(self) -> None:
        env = dict(self.env, AUTHENTIK_URL="https://sso.${MYDOMAIN}")
        loaded = authentik_apps.load_manifest(self.manifest, env, self.host)
        if loaded["authentik"]["url"] != "https://sso.example.test":
            self.fail("Nested Authentik URL was not expanded")

    def test_loads_manifest_service_environment_with_host_precedence(self) -> None:
        docker_config = self.host / "config" / "docker"
        host_dir = docker_config / "colony"
        host_dir.mkdir(parents=True)
        (docker_config / ".env.grafana").write_text("CLIENT_ID=common-client\n")
        (host_dir / ".env.grafana").write_text("CLIENT_ID=host-client\n")
        _, env = authentik_apps.host_environment("colony", self.manifest, docker_config)
        if env.get("CLIENT_ID") != "host-client":
            self.fail("Host service environment did not override common service environment")

    def test_rejects_non_https_authentik_url(self) -> None:
        env = dict(self.env, AUTHENTIK_URL="http://sso.example.test")
        try:
            authentik_apps.load_manifest(self.manifest, env, self.host)
        except authentik_apps.ConfigError:
            return
        self.fail("Non-HTTPS Authentik URL was accepted")

    def test_rejects_missing_expansion(self) -> None:
        try:
            authentik_apps.load_manifest(self.manifest, {"AUTHENTIK_URL": "https://sso.example.test"}, self.host)
        except authentik_apps.ConfigError:
            return
        self.fail("Missing manifest variable was accepted")

    def test_rejects_unsafe_secret_path(self) -> None:
        self.manifest.write_text(self.manifest.read_text().replace("grafana/secret", "../secret"))
        try:
            authentik_apps.load_manifest(self.manifest, self.env, self.host)
        except authentik_apps.ConfigError:
            return
        self.fail("Unsafe secret path was accepted")

    def test_application_lookup_uses_slug_endpoint(self) -> None:
        class Client:
            def request(self, method: str, path: str) -> dict:
                if (method, path) != ("GET", "core/applications/grafana/"):
                    raise RuntimeError("Unexpected request")
                return {"slug": "grafana"}

        application = authentik_apps.application_by_slug(Client(), "grafana")
        if application != {"slug": "grafana"}:
            self.fail("Application was not resolved by slug")

    def test_lists_all_api_pages(self) -> None:
        client = object.__new__(authentik_apps.AuthentikClient)
        requests: list[tuple[str, str, dict[str, int]]] = []

        def request(method: str, path: str, **kwargs: object) -> dict:
            params = kwargs.get("params", {})
            requests.append((method, path, params))
            return (
                {"pagination": {"next": 2}, "results": [{"name": "first"}]}
                if not params
                else {"pagination": {"next": 0}, "results": [{"name": "second"}]}
            )

        client.request = request
        if client.list("core/groups/") != [{"name": "first"}, {"name": "second"}]:
            self.fail("Later API page was not returned")
        if requests != [("GET", "core/groups/", {}), ("GET", "core/groups/", {"page": 2})]:
            self.fail("API pages were not requested in order")

    def test_selects_one_declared_application(self) -> None:
        loaded = authentik_apps.load_manifest(self.manifest, self.env, self.host)
        selected = authentik_apps.select_application(loaded, "grafana")
        if [app["slug"] for app in selected["applications"]] != ["grafana"]:
            self.fail("Requested application was not selected")

    def test_rejects_undeclared_selected_application(self) -> None:
        loaded = authentik_apps.load_manifest(self.manifest, self.env, self.host)
        try:
            authentik_apps.select_application(loaded, "immich")
        except authentik_apps.ConfigError:
            return
        self.fail("Undeclared application selection was accepted")

    def test_validates_all_client_secrets_before_mutation(self) -> None:
        manifest = authentik_apps.load_manifest(self.manifest, self.env, self.host)
        with patch.object(authentik_apps, "ensure_group", side_effect=self.fail):
            try:
                authentik_apps.apply(manifest, object(), self.host / "routes.yml", self.host / "apply.lock")
            except authentik_apps.ConfigError:
                return
        self.fail("Missing OIDC client secret did not stop mutations")

    def test_adds_missing_outpost_route(self) -> None:
        routes = self.host / "authentik-outposts.yml"
        routes.write_text("http:\n  routers:\n    existing: {}\n  services:\n    authentik-outpost: {}\n")
        os.chmod(routes, 0o640)
        app = {"slug": "adminer", "provider": {"external_host": "https://adminer.example.test/"}}
        if not authentik_apps.add_outpost_route(routes, app, "example.test"):
            self.fail("Missing callback route was not added")
        if authentik_apps.add_outpost_route(routes, app, "example.test"):
            self.fail("Existing callback route was added again")
        content = routes.read_text()
        if 'Host(`adminer.{{env "MYDOMAIN"}}`)' not in content:
            self.fail("Callback host did not preserve the domain template")
        if routes.stat().st_mode & 0o777 != 0o640:
            self.fail("Callback route replacement did not preserve file permissions")


if __name__ == "__main__":
    unittest.main()
