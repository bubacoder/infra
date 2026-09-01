# Central Authentication and SSO Migration

Status: core Authentik cutover complete. Remaining work is limited to services
that are not yet migrated and general identity-platform hardening.

For Authentik deployment, backup, recovery, and Google federation, see
[`docs/authentik.md`](../authentik.md). For the Authentik-side application
onboarding workflow, see
[`docker/security/authentik/app-onboarding.md`](../../docker/security/authentik/app-onboarding.md).

## Goals

- Allow approved users to sign in with Google.
- Keep independent local Authentik accounts for break-glass access.
- Prefer native OIDC/OAuth2 over reverse-proxy authentication.
- Use Traefik ForwardAuth only for browser-oriented applications without a
  suitable native integration.
- Preserve protocol-specific access for mobile, TV, CLI, API, database, and
  device clients.
- Prevent direct routes from bypassing the intended authentication boundary.

## Target Architecture

```text
Google account --------------------+
                                    |
Local break-glass account --------> Authentik
                                    |
                       +------------+-------------+
                       |                          |
                  OIDC/OAuth2                Proxy outpost
                       |                          |
             Native application SSO       Traefik ForwardAuth
```

Use one of these patterns per service:

1. **Native OIDC:** The application owns its login session and redirects users
   to Authentik.
2. **Proxy outpost:** Traefik invokes Authentik ForwardAuth before proxying a
   browser request to an application without native OIDC.
3. **Native or machine authentication:** The application or protocol validates
   passwords, tokens, keys, or certificates directly.

Do not put ForwardAuth in front of an application that already uses native OIDC
unless a deliberate second gate is required. This creates two sessions and can
break callbacks and non-browser clients.

## Authentik Configuration

`docker/security/authentik/config/apps.yaml` is the tracked, declarative source
of Authentik application definitions. It contains non-secret provider settings,
redirect URIs, and group bindings. Host-specific client secrets and API tokens
remain in ignored `config/docker/<host>/` files.

Use `scripts/authentik-apps.py` to preview Authentik resources and add `--apply`
to create missing resources. The helper defaults to the local `localhost` host
configuration; pass `--host <name>` only for another configured host. For
existing OIDC providers, it reconciles only declared scope mappings and signing
keys. Review those settings, redirect URIs, external hosts, group bindings, and
outpost assignments before applying.

The ordinary application groups are `admins`, `family`, `users`, `developers`,
`monitoring`, and `media`. Membership in an application group is not a substitute
for application-specific authorization or protocol credentials.

## Migrated Applications

The following applications are represented in `apps.yaml`. Their first-time
setup, recovery, and verification instructions live with their Compose files.

| Application | Integration | Setup documentation |
|---|---|---|
| Open WebUI | Native OIDC | [`docker/ai/open-webui/README.md`](../../docker/ai/open-webui/README.md) |
| Gitea | Native OIDC | [`docker/dev/gitea/README.md`](../../docker/dev/gitea/README.md) |
| Calibre-Web-Automated | Native OIDC | [`docker/media/ebook/calibre-web-automated/README.md`](../../docker/media/ebook/calibre-web-automated/README.md) |
| Immich | Native OIDC | [`docker/media/photo/immich/README.md`](../../docker/media/photo/immich/README.md) |
| Grafana | Native OIDC | [`docker/monitoring/grafana/README.md`](../../docker/monitoring/grafana/README.md) |
| wg-easy | Native OIDC | [`docker/security/wg-easy/README.md`](../../docker/security/wg-easy/README.md) |
| Guacamole | Native OIDC | [`docker/tools/guacamole/README.md`](../../docker/tools/guacamole/README.md) |
| Kopia B2 | ForwardAuth | [`docker/backup/kopia-b2/README.md`](../../docker/backup/kopia-b2/README.md) |
| Adminer | ForwardAuth | [`docker/database/adminer/README.md`](../../docker/database/adminer/README.md) |
| code-server | ForwardAuth | [`docker/dev/code-server/README.md`](../../docker/dev/code-server/README.md) |
| qBittorrent | ForwardAuth | [`docker/fileshare/qbittorrent/README.md`](../../docker/fileshare/qbittorrent/README.md) |
| MeTube | ForwardAuth | [`docker/media/video/metube/README.md`](../../docker/media/video/metube/README.md) |
| Scrutiny | ForwardAuth | [`docker/monitoring/scrutiny/README.md`](../../docker/monitoring/scrutiny/README.md) |
| Uptime Kuma | ForwardAuth | [`docker/monitoring/uptime-kuma/README.md`](../../docker/monitoring/uptime-kuma/README.md) |
| Obsidian | ForwardAuth | [`docker/tools/obsidian/README.md`](../../docker/tools/obsidian/README.md) |

## Remaining Application Work

### Native OIDC Candidates

| Application | Recommended approach | Constraints before implementation |
|---|---|---|
| Vaultwarden | Native OIDC after a client matrix | Test browser extension, desktop, mobile, CLI, WebSocket sync, account linking, and emergency local access. Do not enable `SSO_ONLY` until all clients pass. |
| LiteLLM | Native JWT/OIDC plus API keys | Interactive redirects break OpenAI-compatible API consumers. Configure audience validation, role mapping, and API/master or virtual keys first. |
| Portainer | Native OAuth2 where Authentik topology is available | Keep an initial local administrator and separately restrict direct port `9000` and agent access. |

For a native OIDC application, create a distinct client, use exact redirect URIs,
request only required scopes, retain one local administrator until recovery is
tested, and validate all supported browser and non-browser clients.

### Browser-Gate Candidates

1. Traefik dashboard and ScanservJS.
2. Calibre desktop GUI, excluding Content Server and OPDS routes.
3. Prometheus human UI after separating machine routes for scraping, federation,
   alerting, Grafana, and API automation.
4. Optional protection for SearXNG, Kiwix, CyberChef, and HTTPBin when their
   content or request data warrants interactive authentication.

Do not attach interactive ForwardAuth globally to API-heavy applications. Keep
machine endpoints internal or protect them with explicit non-interactive
authentication.

### Header-Aware Applications

- Frigate: configure trusted-proxy authentication and role mapping only after
  direct access is blocked. Preserve Home Assistant and API access deliberately.
- Navidrome: use external authentication only for the web UI; retain native
  credentials or a separate route for `/rest/*` Subsonic clients.
- CouchDB: consider native JWT or signed proxy authentication only for a real
  client requirement; ordinary Authentik headers are not sufficient.

For every trusted-header integration, Traefik must strip or overwrite incoming
identity headers, and only trusted proxy networks may reach the application.

### Keep Application or Machine Authentication

| Service | Required approach |
|---|---|
| Jellyfin | Retain native users because TV and native clients cannot reliably use browser SSO. |
| Home Assistant | Retain native accounts; outer ForwardAuth can break companion apps, webhooks, callbacks, and integrations. |
| AdGuard Home and UniFi | Retain native accounts because API, device, and mobile endpoints need direct authentication. |
| Mosquitto | Configure native users, ACLs, and TLS/mTLS; ForwardAuth cannot authenticate MQTT traffic. |
| MongoDB and PostgreSQL | Retain database users and restrict network exposure; enable TLS where remote access is required. |
| Ollama, Qdrant, and Portainer Agent | Restrict networks and use API tokens, keys, or agent secrets where supported. |

## Security Prerequisites

Before disabling a service's own browser login or trusting proxy identity
headers:

- Remove unnecessary published HTTP ports.
- Bind unavoidable ports to trusted interfaces or firewall them appropriately.
- Ensure only Traefik and approved internal clients can reach a protected
  application container.
- Strip or overwrite client-provided Authentik and forwarded identity headers.
- Keep non-browser protocols on their own credentials, keys, tokens, or network
  boundaries.
- Review Cloudflare Tunnel ingress and external access policies separately.

Known categories requiring independent review include host-networked services,
database ports, broker ports, node-exporter, Portainer Agent, and device
protocols. A listening port alone does not establish Internet exposure, but it
can bypass Traefik from reachable networks.

## Identity and Recovery Design

- Permit only explicitly approved Google accounts and require a verified email.
- Maintain at least one local Authentik break-glass administrator with an
  independent password and MFA/recovery mechanism.
- Keep a local administrator in each critical downstream service until its
  service-specific recovery procedure has been tested.
- Use shorter sessions and stronger reauthentication for administrative services
  than for ordinary media services.
- Do not use interactive SSO for Git over SSH, MQTT, SMB, database connections,
  WireGuard, API clients, or other non-browser protocols.

## Validation Matrix

Apply relevant checks before declaring a new application migration complete:

| Test | Expected result |
|---|---|
| Authorized user | Login succeeds with the intended application role. |
| Unauthorized user | Access is denied before application access. |
| Group removal | Access or elevated role is removed at the designed refresh boundary. |
| Local recovery | A retained administrator can recover without Google. |
| Direct access | Direct container or host paths are blocked or retain native authentication. |
| Logout and expiry | Sessions end and reauthenticate without redirect loops. |
| Client compatibility | WebSockets, mobile, desktop, API, and CLI clients use the appropriate protocol. |
| Identity outage | The application failure mode and local recovery path are understood. |

## Operational Requirements

- Pin Authentik and PostgreSQL image versions.
- Back up the Authentik database, data, certificates, templates, secret key, and
  OIDC client secrets; test restoration regularly.
- Monitor Authentik and database health, login failures, and proxy errors.
- Review Authentik release notes before upgrades because identity schemas and
  outpost behavior are security-sensitive.
- Keep time synchronized across Authentik, Traefik, and relying-party hosts.

## Decision Record

Authentik runs on `colony` with an embedded proxy outpost. Normal users are
admitted through an explicit Google-email allowlist, while local Authentik
accounts remain reserved for administrator recovery. Initial access is limited
Authentik default application.
