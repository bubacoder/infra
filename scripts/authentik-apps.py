#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "PyYAML==6.0.3",
#   "requests==2.34.2",
# ]
# ///
"""Safely plan or create Authentik applications from a YAML manifest."""

import argparse
import fcntl
import os
import re
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "docker/security/authentik/config/apps.yaml"
DEFAULT_OUTPOST_ROUTES = ROOT / "docker/security/traefik/config/dynamic/authentik-outposts.yml"
ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
OIDC_MAPPINGS = (
    "goauthentik.io/providers/oauth2/scope-openid",
    "goauthentik.io/providers/oauth2/scope-profile",
    "goauthentik.io/providers/oauth2/scope-email",
)


class ConfigError(ValueError):
    """Raised before any network operation for invalid local configuration."""


class AuthentikApiError(RuntimeError):
    """An Authentik API request failed."""

    def __init__(self, status: int | str, message: str):
        super().__init__(message)
        self.status = status


def load_env_file(path: Path, values: dict[str, str]) -> None:
    """Read simple dotenv assignments without executing configuration."""
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            values[key] = value.strip().strip("\"'")


def manifest_slugs(path: Path) -> list[str]:
    """Read and validate application slugs before using them as env filenames."""
    try:
        manifest = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"Cannot load manifest {path}: {error}") from error
    apps = manifest.get("applications") if isinstance(manifest, dict) else None
    if not isinstance(apps, list) or not apps:
        raise ConfigError("Manifest requires a non-empty applications list")
    slugs: list[str] = []
    for app in apps:
        slug = app.get("slug") if isinstance(app, dict) else None
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug) or slug in slugs:
            raise ConfigError(f"Application slug is invalid or duplicated: {slug}")
        slugs.append(slug)
    return slugs


def host_environment(host: str, manifest_path: Path, docker_config: Path | None = None) -> tuple[Path, dict[str, str]]:
    """Load Docker environment files using the same common-to-host precedence."""
    docker_config = docker_config or ROOT / "config/docker"
    host_dir = docker_config / host
    if not host_dir.is_dir():
        raise ConfigError(f"Host configuration directory does not exist: {host_dir}")
    values = dict(os.environ)
    paths = [docker_config / ".env", host_dir / ".env", docker_config / ".env.authentik", host_dir / ".env.authentik"]
    for slug in manifest_slugs(manifest_path):
        paths.extend((docker_config / f".env.{slug}", host_dir / f".env.{slug}"))
    for path in paths:
        load_env_file(path, values)
    return host_dir, values


def expand(value: object, env: dict[str, str]) -> object:
    if isinstance(value, str):
        expanded = value
        seen: set[str] = set()
        while ENV_PATTERN.search(expanded):
            if expanded in seen:
                raise ConfigError(f"Circular environment variable expansion: {value}")
            seen.add(expanded)

            def replacement(match: re.Match[str]) -> str:
                key = match.group(1)
                if not env.get(key):
                    raise ConfigError(f"Required environment variable is unset: {key}")
                return env[key]

            expanded = ENV_PATTERN.sub(replacement, expanded)
        return expanded
    if isinstance(value, list):
        return [expand(item, env) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, env) for key, item in value.items()}
    return value


def https_url(value: object, field: str) -> str:
    if not isinstance(value, str) or not (parsed := urlparse(value)).scheme == "https" or not parsed.netloc:
        raise ConfigError(f"{field} must be an absolute HTTPS URL")
    return value.rstrip("/")


def load_manifest(path: Path, env: dict[str, str], host_dir: Path) -> dict:  # noqa: PLR0912
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"Cannot load manifest {path}: {error}") from error
    manifest = expand(raw, env)
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ConfigError("Manifest must be a mapping with version: 1")
    auth = manifest.get("authentik")
    apps = manifest.get("applications")
    if not isinstance(auth, dict) or not isinstance(apps, list) or not apps:
        raise ConfigError("Manifest requires authentik and a non-empty applications list")
    auth["url"] = https_url(auth.get("url"), "authentik.url")
    auth["domain"] = env.get("MYDOMAIN", "")
    token_file = auth.get("token_file")
    if not isinstance(token_file, str) or Path(token_file).is_absolute() or ".." in Path(token_file).parts:
        raise ConfigError("authentik.token_file must be a relative ignored-host-config path")
    auth["token_file"] = host_dir / token_file
    if not isinstance(auth.get("outpost"), str) or not auth["outpost"]:
        raise ConfigError("authentik.outpost is required")

    slugs: set[str] = set()
    for app in apps:
        if not isinstance(app, dict):
            raise ConfigError("Each application must be a mapping")
        for key in ("name", "slug", "launch_url", "group", "provider"):
            if not app.get(key):
                raise ConfigError(f"Application is missing {key}")
        if not isinstance(app["slug"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", app["slug"]) or app["slug"] in slugs:
            raise ConfigError(f"Application slug is invalid or duplicated: {app['slug']}")
        slugs.add(app["slug"])
        app["launch_url"] = https_url(app["launch_url"], f"application {app['slug']} launch_url") + "/"
        provider = app["provider"]
        if not isinstance(provider, dict) or provider.get("type") not in {"oidc", "proxy_forward_auth"} or not provider.get("name"):
            raise ConfigError(f"Application {app['slug']} has an invalid provider")
        if provider["type"] == "oidc":
            if not isinstance(provider.get("client_id"), str) or not provider["client_id"]:
                raise ConfigError(f"OIDC application {app['slug']} requires provider.client_id")
            client_type = provider.get("client_type", "confidential")
            if client_type not in {"confidential", "public"}:
                raise ConfigError(f"OIDC application {app['slug']} has an invalid client_type")
            provider["client_type"] = client_type
            grant_types = provider.get("grant_types", ["authorization_code"])
            if not isinstance(grant_types, list) or not grant_types or any(not isinstance(grant, str) or not grant for grant in grant_types):
                raise ConfigError(f"OIDC application {app['slug']} has invalid grant_types")
            provider["grant_types"] = grant_types
            secret_file = provider.get("client_secret_file")
            if client_type == "confidential" and not isinstance(secret_file, str):
                raise ConfigError(f"OIDC application {app['slug']} requires a relative client_secret_file")
            if secret_file is not None:
                if not isinstance(secret_file, str) or Path(secret_file).is_absolute() or ".." in Path(secret_file).parts:
                    raise ConfigError(f"OIDC application {app['slug']} has an invalid client_secret_file")
                provider["client_secret_file"] = host_dir / secret_file
            uris = provider.get("redirect_uris")
            if not isinstance(uris, list) or not uris:
                raise ConfigError(f"OIDC application {app['slug']} requires redirect_uris")
            provider["redirect_uris"] = [https_url(uri, f"OIDC redirect URI for {app['slug']}") for uri in uris]
            provider["reconcile_scope_mappings"] = "scope_mappings" in provider
            mappings = provider.get("scope_mappings", list(OIDC_MAPPINGS))
            if not isinstance(mappings, list) or not mappings or any(not isinstance(mapping, str) or not mapping for mapping in mappings):
                raise ConfigError(f"OIDC application {app['slug']} has invalid scope_mappings")
            if len(set(mappings)) != len(mappings):
                raise ConfigError(f"OIDC application {app['slug']} has duplicate scope_mappings")
            provider["scope_mappings"] = mappings
            signing_key = provider.get("signing_key")
            if signing_key is not None and (not isinstance(signing_key, str) or not signing_key):
                raise ConfigError(f"OIDC application {app['slug']} has an invalid signing_key")
        else:
            provider["external_host"] = https_url(provider.get("external_host"), f"Proxy external_host for {app['slug']}") + "/"
            if provider.get("mode") != "forward_single":
                raise ConfigError(f"Proxy application {app['slug']} only supports mode: forward_single")
    return manifest


def select_application(manifest: dict, slug: str | None) -> dict:
    """Restrict reconciliation to one declared application when requested."""
    if slug is None:
        return manifest
    applications = [app for app in manifest["applications"] if app["slug"] == slug]
    if not applications:
        raise ConfigError(f"Application slug is not declared in the manifest: {slug}")
    return {**manifest, "applications": applications}


class AuthentikClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    def request(self, method: str, path: str, **kwargs: object) -> object:
        try:
            response = self.session.request(method, f"{self.base_url}/api/v3/{path.lstrip('/')}", timeout=20, **kwargs)
            response.raise_for_status()
        except requests.RequestException as error:
            status = getattr(error.response, "status_code", "unavailable")
            detail = "" if error.response is not None else f": {type(error).__name__}"
            raise AuthentikApiError(status, f"Authentik API {method} {path} failed ({status}){detail}") from error
        return response.json() if response.content else None

    def list(self, path: str) -> list[dict]:
        data = self.request("GET", path)
        if not isinstance(data, dict) or "results" not in data:
            return data
        results = list(data["results"])
        while next_page := data.get("pagination", {}).get("next"):
            data = self.request("GET", path, params={"page": next_page})
            if not isinstance(data, dict) or "results" not in data:
                raise AuthentikApiError("invalid response", f"Authentik API GET {path} returned an invalid paginated response")
            results.extend(data["results"])
        return results


def named(items: list[dict], name: str, field: str = "name") -> dict | None:
    return next((item for item in items if item.get(field) == name), None)


def application_by_slug(client: AuthentikClient, slug: str) -> dict | None:
    """Look up an application without using Authentik's access-filtered collection."""
    try:
        application = client.request("GET", f"core/applications/{slug}/")
    except AuthentikApiError as error:
        if error.status == 404:
            return None
        raise
    return application if isinstance(application, dict) else None


def outpost_router_name(app: dict) -> str:
    return f"authentik-{app['slug']}-outpost"


def callback_host(app: dict, domain: str) -> str:
    host = urlparse(app["provider"]["external_host"]).hostname
    if not host:
        raise ConfigError(f"Proxy external_host for {app['slug']} is invalid")
    if domain and host.endswith(f".{domain}"):
        return f'{host[: -len(domain)]}{{{{env "MYDOMAIN"}}}}'
    return host


def load_outpost_routes(path: Path) -> dict:
    try:
        config = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"Cannot load outpost routes {path}: {error}") from error
    routers = config.get("http", {}).get("routers") if isinstance(config, dict) else None
    if not isinstance(routers, dict):
        raise ConfigError(f"Outpost routes {path} must define http.routers")
    return routers


def add_outpost_route(path: Path, app: dict, domain: str) -> bool:
    """Append a missing callback router with an atomic file replacement."""
    router = outpost_router_name(app)
    if router in load_outpost_routes(path):
        return False
    marker = "\n  services:\n"
    content = path.read_text()
    if marker not in content:
        raise ConfigError(f"Outpost routes {path} must contain an http.services block")
    route = (
        f"\n    {router}:\n"
        f"      rule: Host(`{callback_host(app, domain)}`) && PathPrefix(`/outpost.goauthentik.io/`)\n"
        "      priority: 100\n"
        "      middlewares:\n"
        "        - localaccess@file\n"
        "      service: authentik-outpost\n"
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            os.chmod(temporary_path, path.stat().st_mode & 0o777)
            temporary.write(content.replace(marker, f"{route}{marker}", 1))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return True


def plan(manifest: dict, client: AuthentikClient, routes: dict) -> list[str]:
    """Return the create/no-change actions using read-only API discovery."""
    actions: list[str] = []
    groups = client.list("core/groups/")
    bindings = client.list("policies/bindings/")
    oidc_providers = client.list("providers/oauth2/")
    proxy_providers = client.list("providers/proxy/")
    outposts = client.list("outposts/instances/")
    mappings = {item.get("managed"): item["pk"] for item in client.list("propertymappings/provider/scope/")}
    for app in manifest["applications"]:
        group = named(groups, app["group"])
        provider_type = app["provider"]["type"]
        providers = oidc_providers if provider_type == "oidc" else proxy_providers
        provider = named(providers, app["provider"]["name"])
        application = application_by_slug(client, app["slug"])
        actions.append(("NO-CHANGE" if group else "CREATE") + f" group {app['group']}")
        if provider_type == "oidc":
            missing = [mapping for mapping in app["provider"]["scope_mappings"] if mapping not in mappings]
            if missing:
                raise RuntimeError(f"Required managed OIDC scope mappings are missing: {', '.join(missing)}")
            expected = [mappings[mapping] for mapping in app["provider"]["scope_mappings"]]
            provider_update = provider and (
                (app["provider"]["reconcile_scope_mappings"] and provider.get("property_mappings", []) != expected)
                or ("signing_key" in app["provider"] and provider.get("signing_key") != app["provider"]["signing_key"])
            )
            provider_action = "UPDATE OIDC settings for" if provider_update else "NO-CHANGE"
        else:
            provider_action = "NO-CHANGE"
        actions.append((provider_action if provider else "CREATE") + f" {provider_type} provider {app['provider']['name']}")
        actions.append(("NO-CHANGE" if application else "CREATE") + f" application {app['slug']}")
        binding_exists = (
            group is not None
            and application is not None
            and any(str(item.get("group")) == str(group["pk"]) and str(item.get("target")) == str(application["pk"]) for item in bindings)
        )
        actions.append(("NO-CHANGE" if binding_exists else "CREATE") + f" group binding {app['group']} -> {app['slug']}")
        if provider_type == "proxy_forward_auth":
            outpost_name = app["provider"].get("outpost", manifest["authentik"]["outpost"])
            outpost = named(outposts, outpost_name)
            assigned = outpost is not None and provider is not None and provider["pk"] in outpost.get("providers", [])
            actions.append(("NO-CHANGE" if assigned else "ADD") + f" provider {app['provider']['name']} to outpost {outpost_name}")
            router = outpost_router_name(app)
            actions.append(("NO-CHANGE" if router in routes else "ADD") + f" Traefik callback route {router}")
    return actions


def required_flow(client: AuthentikClient, slug: str) -> object:
    flow = named(client.list("flows/instances/"), slug, "slug")
    if not flow:
        raise RuntimeError(f"Required Authentik flow is missing: {slug}")
    return flow["pk"]


def ensure_group(client: AuthentikClient, name: str) -> dict:
    return named(client.list("core/groups/"), name) or client.request("POST", "core/groups/", json={"name": name})


def oidc_client_secret(provider: dict) -> str:
    secret_path = provider["client_secret_file"]
    if not secret_path.is_file() or not (secret := secret_path.read_text().strip()):
        raise ConfigError(f"OIDC client secret file is missing or empty: {secret_path}")
    return secret


def validate_client_secrets(manifest: dict) -> None:
    """Fail before mutations when a selected confidential OIDC secret is invalid."""
    for app in manifest["applications"]:
        provider = app["provider"]
        if provider["type"] == "oidc" and provider["client_type"] == "confidential":
            oidc_client_secret(provider)


def ensure_provider(client: AuthentikClient, app: dict) -> dict:
    provider = app["provider"]
    endpoint = "providers/oauth2/" if provider["type"] == "oidc" else "providers/proxy/"
    existing = named(client.list(endpoint), provider["name"])
    if existing:
        if provider["type"] == "oidc":
            updates = {}
            mappings = {item.get("managed"): item["pk"] for item in client.list("propertymappings/provider/scope/")}
            missing = [mapping for mapping in provider["scope_mappings"] if mapping not in mappings]
            if missing:
                raise RuntimeError(f"Required managed OIDC scope mappings are missing: {', '.join(missing)}")
            expected = [mappings[mapping] for mapping in provider["scope_mappings"]]
            if provider["reconcile_scope_mappings"] and existing.get("property_mappings", []) != expected:
                updates["property_mappings"] = expected
            if "signing_key" in provider and existing.get("signing_key") != provider["signing_key"]:
                updates["signing_key"] = provider["signing_key"]
            if updates:
                return client.request("PATCH", f"providers/oauth2/{existing['pk']}/", json=updates)
        return existing
    authorization_flow = required_flow(client, "default-provider-authorization-implicit-consent")
    invalidation_flow = required_flow(client, "default-invalidation-flow")
    if provider["type"] == "oidc":
        mappings = {item.get("managed"): item["pk"] for item in client.list("propertymappings/provider/scope/")}
        missing = [mapping for mapping in provider["scope_mappings"] if mapping not in mappings]
        if missing:
            raise RuntimeError("Required managed OIDC scope mappings are missing")
        payload = {
            "name": provider["name"],
            "client_type": provider["client_type"],
            "client_id": provider["client_id"],
            "authorization_flow": authorization_flow,
            "invalidation_flow": invalidation_flow,
            "grant_types": provider["grant_types"],
            "redirect_uris": [{"matching_mode": "strict", "url": uri, "redirect_uri_type": "authorization"} for uri in provider["redirect_uris"]],
            "property_mappings": [mappings[mapping] for mapping in provider["scope_mappings"]],
        }
        if provider["client_type"] == "confidential":
            payload["client_secret"] = oidc_client_secret(provider)
        if "signing_key" in provider:
            payload["signing_key"] = provider["signing_key"]
    else:
        payload = {
            "name": provider["name"],
            "authorization_flow": authorization_flow,
            "invalidation_flow": invalidation_flow,
            "external_host": provider["external_host"],
            "mode": "forward_single",
        }
    return client.request("POST", endpoint, json=payload)


def ensure_application(client: AuthentikClient, app: dict, provider: dict) -> dict:
    existing = application_by_slug(client, app["slug"])
    if existing:
        return existing
    return client.request(
        "POST",
        "core/applications/",
        json={"name": app["name"], "slug": app["slug"], "provider": provider["pk"], "meta_launch_url": app["launch_url"]},
    )


def ensure_binding(client: AuthentikClient, group: dict, application: dict) -> None:
    bindings = client.list("policies/bindings/")
    if any(str(item.get("group")) == str(group["pk"]) and str(item.get("target")) == str(application["pk"]) for item in bindings):
        return
    client.request("POST", "policies/bindings/", json={"group": group["pk"], "target": application["pk"], "order": 0})


def ensure_outpost_provider(client: AuthentikClient, outpost_name: str, provider: dict) -> None:
    outpost = named(client.list("outposts/instances/"), outpost_name)
    if not outpost:
        raise RuntimeError(f"Proxy outpost is missing: {outpost_name}")
    providers = list(outpost.get("providers", []))
    if provider["pk"] not in providers:
        client.request("PATCH", f"outposts/instances/{outpost['pk']}/", json={"providers": [*providers, provider["pk"]]})


@contextmanager
def apply_lock(path: Path) -> Iterator[TextIO]:
    """Serialize apply operations that mutate one host's Authentik resources."""
    with path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield lock_file
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def apply(manifest: dict, client: AuthentikClient, routes_path: Path, lock_path: Path) -> list[str]:
    actions: list[str] = []
    with apply_lock(lock_path):
        validate_client_secrets(manifest)
        for app in manifest["applications"]:
            group = ensure_group(client, app["group"])
            provider = ensure_provider(client, app)
            application = ensure_application(client, app, provider)
            ensure_binding(client, group, application)
            if app["provider"]["type"] == "proxy_forward_auth":
                ensure_outpost_provider(client, app["provider"].get("outpost", manifest["authentik"]["outpost"]), provider)
                add_outpost_route(routes_path, app, manifest["authentik"]["domain"])
            actions.append(f"APPLIED {app['slug']}")
    return actions


def run(args: argparse.Namespace) -> int:
    """Run a validated plan or apply operation."""
    host_dir, env = host_environment(args.host, args.manifest)
    manifest = load_manifest(args.manifest, env, host_dir)
    manifest = select_application(manifest, args.application)
    routes = load_outpost_routes(args.outpost_routes)
    token_path = manifest["authentik"]["token_file"]
    if not token_path.is_file() or not (token := token_path.read_text().strip()):
        raise ConfigError(f"API token file is missing or empty: {token_path}")
    client = AuthentikClient(manifest["authentik"]["url"], token)
    actions = apply(manifest, client, args.outpost_routes, host_dir / ".authentik-apps.lock") if args.apply else plan(manifest, client, routes)
    for action in actions:
        print(action)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely reconcile Authentik applications; it never deletes resources.")
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host directory name beneath config/docker (default: localhost)",
    )
    parser.add_argument("--application", help="Reconcile only this declared application slug")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Application manifest path")
    parser.add_argument("--outpost-routes", type=Path, default=DEFAULT_OUTPOST_ROUTES, help="Traefik callback routes file")
    parser.add_argument("--apply", action="store_true", help="Create missing resources and reconcile declared OIDC scope mappings")
    args = parser.parse_args()
    try:
        return run(args)
    except (ConfigError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
