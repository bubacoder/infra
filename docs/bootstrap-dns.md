# Bootstrap DNS

DNS is managed through Ansible modules:

- AWS: `community.general.cloudflare_dns` creates DNS-only base/wildcard A records.
- Either target: optional `community.dns.adguardhome_rewrite` manages exact local
  base, `home`, `traefik` and `bootstrap-check` rewrites.
- Proxmox never changes public address records; existing DDNS remains responsible.

For shared input formats, inspection and safety rules, see
[Bootstrap inputs and safety](bootstrap-configuration.md).

In the non-secret `host.yaml`, set:

```yaml
dns:
  enabled: true
  cloudflare_zone: example.com # AWS only; omit for Proxmox.
  # adguard_url: https://adguardhome.example.com
```

Replace the example zone and endpoint with your own addresses. If AdGuard syncs
configuration to replicas, use the primary instance's API endpoint.

In private mode-`0600` `secrets.yaml`, supply `cloudflare_token` with `Zone:Read` and
`DNS:Edit` on that zone. Optional AdGuard uses `adguard_username` and
`adguard_password` for HTTP Basic authentication. Provider endpoints must use trusted
HTTPS. TLS verification is never disabled. Do not paste secrets into chat, args,
logs, public host settings or Terraform. Use a dedicated deployment subdomain.

`dns.enabled: false` leaves DNS to the operator while retaining resolver acceptance.
TLS DNS challenges still need the token. Cloudflare alone is sufficient when no
local resolver overrides the domain. If AdGuard already overrides it, public DNS
alone may not fix the controller's answers; configure that provider explicitly.
Without AdGuard, Proxmox names must resolve externally to the guest's LAN address.
Router, DHCP and hosts files are never edited by bootstrap.

## Conflict and ownership rules

Read-only provider checks reject conflicting addresses, duplicates, aliases,
delegations and proxied Cloudflare records. Exactly matching pre-existing records
are left unchanged and are **not** claimed for deletion. The small non-secret
`dns-state.yaml` receipt in the selected target's directory records only
deployment-created names, addresses and Cloudflare IDs, not credentials.

A pending create is recorded before the native module writes. If an interrupted
request has an uncertain result, inspect the provider and receipt before a retry;
never delete the evidence or blindly repeat a request. The receipt binds the target
and provider settings. Keep those settings available for teardown even if automated
DNS is later disabled. An AdGuard endpoint can be added or corrected while no
AdGuard records are owned and no write is pending. Once records are owned, changing
that endpoint is blocked. Do not concurrently edit deployment names externally.

Provider readback is necessary but not sufficient: Ansible checks the controller's
actual resolver for all required names with bounded retries. Caches, split DNS and
filtering can still stop installation. Failures can leave partial DNS and billable
AWS resources running. There is no automatic rollback or hosts-file fallback.

## Cleanup

[AWS teardown](bootstrap-aws.md#teardown) removes only receipt-owned records whose
current payload and Cloudflare ID still match. Changed records stop cleanup;
pre-existing matching records, parent wildcards and unrelated rewrites remain.
Provider readback must confirm deletion before ownership evidence is removed.
For Proxmox or manual DNS, provider-side cleanup requires separate approval.
