# Bootstrap DNS automation

Bootstrap manages deployment DNS by default as part of normal plan/apply:

| Target | Local AdGuard Home | Public Cloudflare address records |
| --- | --- | --- |
| AWS | If configured, base and service names point to the Elastic IP | Base and wildcard point to the Elastic IP, DNS-only |
| Proxmox | If configured, base and service names point to the VM's LAN IP | Never changed; existing DDNS owns public addressing |

Both targets still use `tls.token` for Cloudflare TLS DNS challenges. That is
separate from managing public A records. Existing parent domains/wildcards,
router settings, DHCP and `/etc/hosts` are never changed.

## Configure privately

Choose a dedicated deployment subdomain, such as `aws-test.example.com`. Do not
reuse your homelab's base domain or redirect its existing wildcard to AWS.

For AWS, configure Cloudflare in your ignored, mode-`0600` bootstrap file.
Add AdGuard only if it already exists and you want to manage its local overrides:

```yaml
network:
  expected_ipv4: auto
  domain: aws-test.example.com
  dns:
    enabled: true
    verify: true
    cloudflare:
      zone: example.com
    adguard:
      url: https://dns-admin.example.com
      username: <adguard-web-username>
      password: <adguard-web-password>
```

For Proxmox, use the same structure but **omit `cloudflare`**; it is rejected
to protect DDNS-managed public records. **AdGuard is optional on both targets**:
omit its entire section if it does not exist yet. `enabled` defaults to `true`
and `verify` defaults to `true` when omitted. AWS requires `cloudflare.zone`;
Proxmox permits no configured DNS provider and then performs no DNS writes.
Provider credentials are never discovered by searching other private files.

A first AWS deployment can use Cloudflare alone. A Proxmox deployment without
AdGuard must have DNS supplied externally: all required names must resolve from
the admin host to the VM's LAN IPv4 address. Existing DDNS does not necessarily
provide that LAN answer. If resolution is unavailable, bootstrap stops at its
resolver checkpoint; optional AdGuard does not mean optional working DNS.
If AdGuard does exist and overrides the domain, omitting it leaves those overrides
untouched, so public Cloudflare changes may still not fix local resolution.

These are placeholders, not usable credentials. Edit the file privately; do not
paste passwords into chat, command arguments, or environment variables. AdGuard
credentials remain on the administrative host and are never rendered on the VM.

- Cloudflare reuses `tls.token`, scoped to the selected zone with `Zone:Read` and
  `DNS:Edit`. The zone must be active and contain `network.domain`.
- AdGuard Home uses its web API credentials (HTTP Basic authentication), not a
  Cloudflare token or an assumed AdGuard API key. The origin URL must use trusted
  HTTPS with no path or embedded credentials. Plain HTTP is permitted only on
  numeric loopback addresses (`127.0.0.1` or `[::1]`), for example through a
  separately arranged SSH tunnel. TLS verification cannot be disabled. HTTP
  redirects and environment proxy settings are not followed.
- Set `network.dns.enabled: false` to disable DNS automation: no DNS provider
  calls or record changes are made, but required names must still resolve
  correctly. Manage records externally in that case. This does not disable
  Cloudflare TLS certificate challenges, which still use `tls.token`.
- Legacy `mode: external` and `mode: managed` remain aliases for `enabled: false`
  and `enabled: true`. Prefer `enabled` in new files; remove `mode` when migrating.
  If both fields are supplied they must agree. Verification cannot be disabled.
  There is no hosts-file fallback;
  the former hosts-file helper commands have been removed. Existing host-file
  entries are left alone and may need separately approved operator cleanup.

## Normal installation

Use the ordinary commands; no separate DNS invocation is required:

```bash
task bootstrap:plan CONFIG=config/bootstrap-aws.yaml
task bootstrap:apply CONFIG=config/bootstrap-aws.yaml
```

Plan reads enabled provider APIs and previews missing records without DNS writes.
It checks conflicts even when the AWS Elastic IP or Proxmox DHCP address is not
yet known; pre-existing exact entries cannot be accepted as matching an unknown
future address. Apply asks approval for the displayed infrastructure/DNS plan,
obtains the address, and rechecks configured providers before creating anything in DNS.
Proxmox `auto` uses guest-agent discovery; AWS uses the allocated Elastic IP.

Provider readback must confirm the requested entries, then the administrative
host's actual resolver must return only the deployment address for all four
required names. Managed apply waits up to 60 seconds for resolver convergence
before failing safely; it does not repeatedly write DNS while waiting. Check
resolver selection, custom filtering, caches and upstream policy if it stops.
After correcting the cause, explicitly resume the same apply within the approved
scope. DNS changes and billable AWS resources can remain after a failure.

## Record behavior and recovery

DNS is an internal installation stage, not a separate command. Preview it with
`bootstrap:plan`; reconcile and recover with the normal `bootstrap:apply`.
Inspect plan output privately before sharing. The ordinary apply confirmation
covers the displayed infrastructure and DNS changes. `YES=1` skips that
confirmation only for an already reviewed unattended run, not any safety checks.

On AWS, Cloudflare receives DNS-only A records for the base name and its wildcard. Any
explicit `home`, `traefik`, or `bootstrap-check` address/alias/delegation records
are also checked so that they cannot silently defeat the wildcard. AdGuard
receives exact rewrites for the base name and those three service names, leaving
broader local wildcard rewrites untouched. Exact rewrites take precedence over
broader AdGuard rewrites; custom filtering, upstream policy, and other local DNS
servers may still override the effective answer.

Missing records are created. Exactly matching records are left unchanged and are
not claimed as owned. Conflicting addresses, aliases, delegations, disabled
rewrites, duplicate address records, or Cloudflare proxy settings stop the entire
preview before writes. The tool never updates or deletes existing records and
does not edit AdGuard filtering rules or enable globally disabled DNS rewrites.
Do not concurrently edit these names through another operator or tool.

API requests have a 20-second timeout and bounded response sizes/pagination. After
writes, provider readback must show all requested records. This is **not proof of
effective DNS resolution**: allow caches to expire and verify the administrative
host's resolver. When ready, explicitly resume the original deployment:

```bash
task bootstrap:apply CONFIG=config/bootstrap-aws.yaml
```

Bootstrap's existing resolver check must still pass; DNS automation does not
bypass it or any repository revision checks. Normal plan/apply require a clean,
published revision. For offline AI inspection use `bootstrap:show-config`, not
a live plan or a raw private-file read.

## Failures, ownership and cleanup

Private evidence is stored under `config/bootstrap-dns/<hostname>/journal.json`
with mode `0600`. It records the target, provider endpoints, created record
payloads, and Cloudflare record IDs, but no credentials. Preserve it alongside
the deployment state. It is evidence for review, not automatic deletion authority.

Every attempted write is journaled **before** the request. A failed request can
have succeeded remotely; an uncertain pending entry stops subsequent DNS runs.
Inspect the provider and journal manually before deciding how to reconcile it.
Do not discard the journal or blindly retry a POST. Changing the journal's target
or provider endpoints also requires manual review. After a successful run, a
repeat bootstrap plan should report zero DNS creates; run it only within the approved test
scope.

Provider changes are not transactional across Cloudflare and AdGuard. A later
failure may leave some records created and AWS resources running and billable.
No automatic rollback or teardown occurs. Cleanup requires separate approval:
review the journal, verify each recorded entry is still exactly the test-created
record, and remove only those entries through the respective provider. Never
delete pre-existing matching records, parent wildcards, or unrelated rewrites.
