"""Integrated, create-only Cloudflare and AdGuard bootstrap DNS automation."""

import base64
import contextlib
import fcntl
import ipaddress
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .core import ROOT, BootstrapConfig, BootstrapError
from .deploy import atomic_write


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward API credentials to a redirected endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0913, PLR0917
        return None


class Api:
    """Bounded authenticated JSON transport with no raw provider errors."""

    def __init__(self, origin: str, authorization: str) -> None:
        self.origin = origin
        self.authorization = authorization
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method: str, path: str, body: dict | None = None):
        """Call a fixed-origin API without shell commands or credential logging."""
        request = urllib.request.Request(  # noqa: S310
            self.origin + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": self.authorization, "Content-Type": "application/json"},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                content = response.read(2_000_001)
            if len(content) > 2_000_000:
                raise BootstrapError("DNS API response exceeded the size limit")
            return json.loads(content) if content.strip() else None
        except (OSError, ValueError, urllib.error.URLError):
            raise BootstrapError("DNS API request failed; check private credentials, TLS trust, permissions and connectivity") from None


@dataclass(frozen=True)
class Change:
    """One create-only DNS operation containing no credentials."""

    provider: str
    path: str
    body: dict


def names_for(domain: str) -> list[str]:
    """Names checked by bootstrap's system-resolver acceptance gate."""
    return [domain, *(f"{label}.{domain}" for label in ("traefik", "home", "bootstrap-check"))]


def cloudflare_action(name: str, address: str | None, records: list[dict]) -> bool:
    """Require absent or exactly one matching DNS-only A record."""
    relevant = [record for record in records if record.get("type") in {"A", "AAAA", "CNAME", "NS"}]
    if not relevant:
        return True
    if (
        address is not None
        and len(relevant) == 1
        and relevant[0].get("type") == "A"
        and relevant[0].get("content") == address
        and relevant[0].get("proxied") is False
    ):
        return False
    raise BootstrapError(f"Cloudflare DNS conflict for {name}; existing address, alias, delegation or proxy settings will not be changed")


def adguard_action(name: str, address: str | None, records: list[dict]) -> bool:
    """Create exact rewrites without editing parent wildcards or conflicting names."""
    exact = [record for record in records if record.get("domain", "").lower().rstrip(".") == name]
    if not exact:
        return True
    if address is not None and len(exact) == 1 and exact[0].get("answer") == address and exact[0].get("enabled", True) is True:
        return False
    raise BootstrapError(f"AdGuard DNS conflict for {name}; existing or disabled rewrites will not be changed")


def cf_result(document: object) -> tuple[list[dict], int]:
    """Fail closed on API failures and unexpected pagination shapes."""
    if not isinstance(document, dict) or document.get("success") is not True or not isinstance(document.get("result"), list):
        raise BootstrapError("Cloudflare DNS API returned an invalid or unsuccessful response")
    rows = document["result"]
    info = document.get("result_info", {})
    if not isinstance(info, dict):
        raise BootstrapError("Cloudflare DNS API returned invalid pagination")
    pages = info.get("total_pages", 1)
    if any(not isinstance(row, dict) for row in rows) or type(pages) is not int or not 0 <= pages <= 100:
        raise BootstrapError("Cloudflare DNS API returned invalid records or too many pages")
    return rows, pages


def cf_list(client: Api, path: str, query: dict) -> list[dict]:
    """Read all bounded pages so conflicts cannot hide on subsequent pages."""
    rows = []
    for page in range(1, 101):
        batch, pages = cf_result(client.request("GET", f"{path}?{urllib.parse.urlencode({**query, 'page': page, 'per_page': 100})}"))
        rows.extend(batch)
        if page >= pages:
            return rows
    raise BootstrapError("Cloudflare DNS pagination exceeded the limit")


def plan_changes(config: BootstrapConfig, address: str | None) -> tuple[list[Change], dict[str, Api]]:
    """Read configured providers and validate every conflict before permitting writes."""
    settings, changes, clients = config.network.dns, [], {}
    names = names_for(config.network.domain)
    if settings.cloudflare:
        if config.target != "aws":
            raise BootstrapError("Proxmox public DNS is managed by DDNS; Cloudflare address writes are forbidden")
        client = Api("https://api.cloudflare.com/client/v4", f"Bearer {config.tls.token}")
        clients["cloudflare"] = client
        zones = cf_list(client, "/zones", {"name": settings.cloudflare.zone, "status": "active"})
        if len(zones) != 1 or zones[0].get("name") != settings.cloudflare.zone or not re.fullmatch(r"[a-f0-9]{32}", zones[0].get("id", "")):
            raise BootstrapError("Cloudflare DNS zone must resolve to exactly one active accessible zone")
        path = f"/zones/{zones[0]['id']}/dns_records"
        desired = [names[0], f"*.{names[0]}"]
        for name in [*desired, *names[1:]]:
            records = cf_list(client, path, {"name": name})
            if any(record.get("name") != name for record in records):
                raise BootstrapError("Cloudflare returned records outside the requested name")
            missing = cloudflare_action(name, address, records)
            if name in desired and missing:
                changes.append(Change("cloudflare", path, {"type": "A", "name": name, "content": address, "ttl": 1, "proxied": False}))
    if settings.adguard:
        ag = settings.adguard
        authorization = base64.b64encode(f"{ag.username}:{ag.password}".encode()).decode()
        client = Api(ag.url, f"Basic {authorization}")
        clients["adguard"] = client
        records = client.request("GET", "/control/rewrite/list")
        if not isinstance(records, list) or any(
            not isinstance(record, dict) or not isinstance(record.get("domain"), str) or not isinstance(record.get("answer"), str)
            for record in records
        ):
            raise BootstrapError("AdGuard DNS API returned an invalid rewrite list")
        for name in names:
            if adguard_action(name, address, records):
                changes.append(Change("adguard", "/control/rewrite/add", {"domain": name, "answer": address}))
    return changes, clients


def read_journal(path: Path) -> dict:
    """Never silently recover an uncertain provider write or discard evidence."""
    if not path.exists():
        return {"created": [], "pending": None}
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise BootstrapError("DNS journal must be a private regular file")
    try:
        journal = json.loads(path.read_text())
    except (ValueError, OSError):
        raise BootstrapError("Cannot read private DNS journal; inspect it without discarding it") from None
    if not isinstance(journal, dict) or not isinstance(journal.get("created"), list) or "pending" not in journal:
        raise BootstrapError("Invalid DNS journal; inspect it without discarding it")
    if journal["pending"] is not None:
        raise BootstrapError("An earlier DNS write has an uncertain result; inspect the provider and private journal before retrying")
    return journal


def execute_changes(changes: list[Change], clients: dict[str, Api], path: Path) -> None:
    """Journal before every POST; never update, delete or automatically roll back."""
    journal = read_journal(path)
    for change in changes:
        journal["pending"] = asdict(change)
        atomic_write(path, json.dumps(journal))
        result = clients[change.provider].request("POST", change.path, change.body)
        record_id = None
        if change.provider == "cloudflare":
            if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("result"), dict):
                raise BootstrapError("Cloudflare DNS write was not confirmed; inspect private journal before retrying")
            record_id = result["result"].get("id")
            if not isinstance(record_id, str) or not re.fullmatch(r"[a-f0-9]{32}", record_id):
                raise BootstrapError("Cloudflare DNS write returned no valid record ID; inspect private journal")
        journal["created"].append({**asdict(change), "record_id": record_id})
        journal["pending"] = None
        atomic_write(path, json.dumps(journal))


def preview(config: BootstrapConfig, address: str | None, root: Path = ROOT) -> None:
    """Read providers before provisioning, even when the future IP is unknown."""
    if not config.network.dns.enabled:
        return
    read_journal(root / "config/bootstrap-dns" / config.vm.name / "journal.json")
    changes, _ = plan_changes(config, address)
    print(f"DNS target: {config.network.domain} -> {address or 'address allocated/discovered during apply'}")
    for change in changes:
        print(f"  {change.provider}: create {change.body.get('name', change.body.get('domain'))}")
    print(f"DNS plan: {len(changes)} creates; no updates or deletions. No DNS records changed.")


def reconcile(config: BootstrapConfig, address: str, *, root: Path = ROOT) -> None:
    """Reconcile DNS inside the already approved deployment apply."""
    if not config.network.dns.enabled:
        return
    try:
        address = str(ipaddress.IPv4Address(address))
    except (ValueError, TypeError):
        raise BootstrapError("DNS reconciliation requires the verified deployment IPv4 address") from None
    directory = root / "config/bootstrap-dns" / config.vm.name
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    with contextlib.ExitStack() as stack:
        descriptor = os.open(directory / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        stack.callback(os.close, descriptor)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BootstrapError("Another DNS operation holds this deployment lock") from None
        path = directory / "journal.json"
        journal = read_journal(path)
        identity = {
            "target": config.target,
            "domain": config.network.domain,
            "address": address,
            "cloudflare_zone": config.network.dns.cloudflare.zone if config.network.dns.cloudflare else None,
            "adguard_url": config.network.dns.adguard.url if config.network.dns.adguard else None,
        }
        if "identity" in journal and journal["identity"] != identity:
            raise BootstrapError("DNS target or providers changed; inspect the existing journal rather than discarding it")
        changes, clients = plan_changes(config, address)
        print(f"DNS target: {config.network.domain} -> {address}")
        for change in changes:
            print(f"  {change.provider}: create {change.body.get('name', change.body.get('domain'))} -> {address}")
        print(f"DNS plan: {len(changes)} creates; no updates or deletions. Matching existing records are not owned.")
        if not clients:
            print("No DNS providers configured; no DNS changes made. Supply working DNS externally; bootstrap still verifies resolution.")
            return
        journal["identity"] = identity
        atomic_write(path, json.dumps(journal))
        execute_changes(changes, clients, path)
        remaining, _ = plan_changes(config, address)
        if remaining:
            raise BootstrapError("DNS API readback did not confirm all records; no retry or rollback was attempted")
        print(f"DNS API readback passed. Journal: {path}. No cleanup was performed.")
        print("Bootstrap will now verify resolution through the administrative host resolver; cached or overridden DNS may still block it.")
