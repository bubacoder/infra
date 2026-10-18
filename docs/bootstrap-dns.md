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

In private mode-`0600` `secrets.yaml`, supply `cloudflare_token` with `Zone:Read` and
`DNS:Edit` on that zone. Optional AdGuard uses `adguard_username` and
`adguard_password` for HTTP Basic authentication. Prefer HTTPS with a trusted
certificate; TLS verification is never disabled. HTTP AdGuard endpoints (for example,
`http://192.0.2.10:3000`) are supported only for operator-approved trusted networks:
credentials and API traffic are transmitted unencrypted. Cloudflare and application
acceptance routes still require HTTPS. Do not paste secrets into chat, args,
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

Provider readback is necessary but not sufficient: Ansible checks the controller's
actual resolver for all required names with bounded retries. Caches, split DNS and
filtering can still stop installation. Failures can leave partial DNS and billable
AWS resources running. There is no automatic rollback or hosts-file fallback.
`bootstrap:verify` also requires every configured AdGuard endpoint to contain each
exact deployment rewrite; a successful answer from just one resolver is not enough.

## Cleanup

[AWS teardown](bootstrap-aws.md#teardown) removes only receipt-owned records whose
current payload and Cloudflare ID still match. Changed records stop cleanup;
pre-existing matching records, parent wildcards and unrelated rewrites remain.
Provider readback must confirm deletion before ownership evidence is removed.
For Proxmox or manual DNS, provider-side cleanup requires separate approval.
