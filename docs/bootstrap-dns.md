# Bootstrap DNS

DNS is managed through Ansible modules:

- AWS: `community.general.cloudflare_dns` creates DNS-only base/wildcard A records.
- Either target: optional `community.dns.adguardhome_rewrite` manages exact local
  base and `bootstrap-check` rewrites, plus `home`/`traefik` for selected services.
- Proxmox never changes public address records; existing DDNS remains responsible.

For shared input formats, inspection and safety rules, see
[Bootstrap inputs and safety](bootstrap-configuration.md).

## Requirements by deployment

| Deployment | DNS and credential requirements |
| --- | --- |
| Selected services | Deployment names must resolve from the controller. Cloudflare token is required for TLS, even with DNS management disabled |
| Enabled AWS DNS management | Dedicated deployment subdomain, Cloudflare zone and scoped token |
| Enabled Proxmox DNS management | Deployment domain; address records stay external/DDNS, with optional existing AdGuard rewrites |
| Enabled AdGuard management | Credentials for all configured instances |
| No services and DNS disabled | No deployment domain, resolver acceptance or DNS credentials needed for installation |

Disabling DNS management leaves records to the operator, not to a fallback hosts-file
edit. Router, DHCP and hosts files are never modified by bootstrap. Keep provider
settings and credentials available for approved cleanup of any previously owned records.

## Configure providers

In the private `bootstrap.yaml`, set:

```yaml
dns:
  enabled: true
  cloudflare_zone: example.com # AWS only; omit for Proxmox.
  # adguard_urls:
  #   - https://adguard-primary.example.com
  #   - https://adguard-secondary.example.com
```

Replace the example zone and endpoints with your own addresses. List every AdGuard
instance used by clients, with the primary first. Bootstrap writes and reads back
each instance directly rather than waiting for a background sync schedule. All
endpoints share the same credentials. A single endpoint can use `adguard_url`;
do not combine it with `adguard_urls`. Endpoints must be unique HTTP or HTTPS origins with
no credentials, paths, query strings or fragments.

For services or AWS DNS management, supply `secrets.cloudflare_token` with
`Zone:Read` and `DNS:Edit` on the selected zone. Enabled AdGuard management uses
`secrets.adguard_username` and `secrets.adguard_password` for HTTP Basic authentication.

### Transport and secrets

Prefer HTTPS with a trusted
certificate; TLS verification is never disabled. HTTP AdGuard endpoints (for example,
`http://192.0.2.10:3000`) are supported only for operator-approved trusted networks:
credentials and API traffic are transmitted unencrypted. Cloudflare and application
acceptance routes still require HTTPS. Do not paste secrets into chat, args,
logs, public host settings or Terraform. Use a dedicated deployment subdomain.

### Resolver acceptance

Cloudflare alone is sufficient when no local resolver overrides the domain. If
AdGuard already overrides it, public DNS alone may not fix controller resolution;
configure that provider explicitly. Without AdGuard, required Proxmox names must
resolve through externally managed DNS to the guest's LAN address.

Provider readback is not sufficient: bootstrap checks the controller's actual
resolver for every required name with bounded retries, even when DNS is operator-managed.
For enabled AdGuard management, verification also requires the exact rewrites on
every configured instance. A successful answer from one resolver is not enough.
Caches, split DNS and filtering can still stop installation and leave partial DNS
or billable AWS resources running. There is no automatic rollback or hosts-file fallback.

## Conflict and ownership rules

Read-only provider checks reject conflicting addresses, duplicates, aliases,
delegations and proxied Cloudflare records. Exactly matching pre-existing records
are left unchanged and are **not** claimed for deletion. The small non-secret
`dns-state.yaml` receipt in the selected target's directory records only
deployment-created names, addresses, AdGuard endpoint URLs and Cloudflare IDs, not
credentials. Ownership is separate for each AdGuard endpoint: a matching record
copied by another tool is left unchanged and is not adopted.

A pending create is recorded before the native module writes. If an interrupted
request has an uncertain result, inspect the provider and receipt before a retry;
never delete the evidence or blindly repeat a request. The receipt binds the target
and provider settings. Keep those settings available for teardown even if automated
DNS is later disabled. Endpoints may be added when no write is pending. An endpoint
with owned records cannot be removed or replaced until its approved cleanup is
complete. For a single-endpoint receipt, ownership remains bound to that original
endpoint when expanding the list. Do not concurrently edit deployment names
externally. If an endpoint fails partway through an update, completed writes remain
recorded and an uncertain write retains its endpoint-specific pending evidence;
there is no automatic rollback or blind retry.

## Cleanup

Service deselection and disabling DNS management never delete records. Approved
teardown also considers receipt-owned names for services that have been deselected.

[AWS teardown](bootstrap-aws.md#teardown) removes only receipt-owned records whose
current payload and Cloudflare ID still match. Changed records stop cleanup;
pre-existing matching records, parent wildcards and unrelated rewrites remain.
Provider readback must confirm deletion before ownership evidence is removed.
For Proxmox or manual DNS, provider-side cleanup requires separate approval.
