# Bootstrap-managed Traefik

Opt-in platform configuration for Traefik already bundled with the local `k3s`
role. It installs no second controller and does not convert the Docker-provider
configuration. Application Compose files and Konverter remain responsible for
application Deployments, Services, routes and backend policies.

## Explicit profile

Use the existing private `bootstrap.yaml` workflow. Retain provider/VM and
optional K3s access/Cilium settings, then select:

```yaml
roles: [debian_base, k3s, k3s_traefik]
services: []
host:
  acme_email: admin@example.com
k3s:
  traefik:
    enabled: true
    domain: apps.example.com
    admin_cidr: 192.0.2.10/32
    middlewares: [localaccess, https-only, security-headers]
    acme_environment: staging
    storage_class: local-path
    storage_size: 1Gi
secrets:
  cloudflare_token: REPLACE_PRIVATELY
```

The sample values are placeholders. Use a domain in an operator-controlled
Cloudflare zone, a real ACME contact and an explicit admin CIDR. No ingress IP
is detected automatically. The application `domain` is separate from the API
hostname in `k3s.access.host`. All feature fields are required when enabled;
omitting both feature and role preserves default K3s behavior.

Use `bootstrap:show-config` for safe inspection, then the existing target-specific
plan/apply or configure/verify workflow. Follow
[bootstrap input safety](../../../docs/bootstrap-configuration.md); never share
private inputs, inspect them with raw tools or use Ansible `--diff`. No additional
`.env` source or Terraform credential variable is introduced.

Supported bundled chart: `traefik-40.1.5+up40.1.0.tgz`. A changed packaged version
requires an explicitly reviewed adapter update. K3s itself is neither upgraded
nor restarted by this role. Cilium is independent and is not reconfigured here.

## One shared dynamic policy

The existing files remain canonical:

- `docker/security/traefik/config/dynamic/middlewares.yml`: explicitly selected
  middleware, complete transitive chain dependencies and shared TLS options.
- `docker/security/traefik/config/dynamic/tls.yml`: copied verbatim, including
  the default generated certificate policy. Currently this requests the apex,
  `*.<domain>` and `*.dev.<domain>`; the adapter does not reduce its SAN list.

The offline compiler projects a ConfigMap, PVC and HelmChartConfig into the
private generated directory. Ansible copies files verbatim, without Jinja
re-rendering. Traefik evaluates preserved Go `env` templates using explicit
`MYDOMAIN` and `LOCAL_ACCESS_ADMIN_CIDR` environment values. The whole watched
ConfigMap directory is mounted read-only, without `subPath`.

Compose references such as `localaccess@file` stay unchanged. File middleware is
controller-wide, so configuration writers are a trust boundary. Cross-namespace
Middleware CRD references remain disabled. Application ports, Cilium grants and
public routes are not inferred.

The supported initial subset is `chain`, `ipAllowList`, `headers` and
`redirectScheme`. Missing dependencies, cycles, unknown templates and selected
unsupported types fail before provisioning. `localaccess-authentik` and
`publicaccess` therefore fail until authentication/plugin integration is added;
they never become weakened substitutes. Docker external services and insecure
server transports are not imported.

The canonical allowlist preserves its private-network/loopback rules plus the
supplied admin CIDR. A narrow admin CIDR does **not** make this policy admin-only.
Actual client-IP/SNAT behavior still needs an approved live client test.

## Credentials and certificates

Private `secrets.cloudflare_token` becomes a namespaced Secret on the guest.
Traefik uses `valueFrom`; ConfigMaps and Helm values contain no actual token.
Cloudflare requires zone-read/DNS-edit permissions limited to the authoritative
zone. DNS-01 uses temporary public TXT records; application addresses may remain
private and inbound public TCP 80 is not required for certificate validation.

Traefik directly owns the `letsencrypt` resolver; cert-manager is not needed.
Staging uses `/data/acme-staging.json`, production `/data/acme.json`, avoiding
reuse of staging accounts as production state. Staging is not browser-trusted.

ACME private keys persist on a new, explicitly sized ReadWriteOnce claim. One
replica and Recreate rollouts avoid overlapping replacement writers, at the cost
of ingress downtime during controller updates. This is not HA or protection
from external writers. UID/GID 65532 and `fsGroup: 65532` support the newly owned
storage without a privileged chown container. Adoption, resizing and storage
class changes are refused.

Local-path storage remains on the node/OS disk, including AWS; this role does not
move K3s data to the separate AWS data disk. Back up the datastore, server token,
ownership receipt and ACME volume securely. VM destruction can destroy them.
Kubernetes Secrets are not encryption by themselves: protect RBAC, datastore,
guest files and backups.

Root-only staged manifests and receipt live in
`/var/lib/rancher/k3s/bootstrap-traefik/` (directory 0700, files 0600). Credentials
use native Ansible `no_log`, never arguments, logs or Terraform. Rotation
refreshes the controller and records an acknowledged private checksum, so a
retry does not lose a pending rotation or restart every successful repeat.

## Ownership and lifecycle

All resources receive server-side dry-run validation before the first apply;
dependencies precede the HelmChartConfig. The Helm controller reconciles the
existing packaged release. Conflicting base list/secret inputs or higher-priority
overrides are refused rather than discarded.

A private receipt binds object UIDs to cluster UID/deployment. Existing objects
without receipts are refused even with matching labels. New objects use create,
not apply/adoption. Updates carry UID/resourceVersion preconditions, use
server-side ownership and never force conflicts. Unsafe/symlinked management
files and deleted/replaced objects fail closed. Each mutation immediately records
its returned UID. An interruption before receipt persistence needs explicit
recovery: never delete recovery files to force retry.

The current manually configured example cluster's `traefik` HelmChartConfig is
deliberately not adopted. Its real middleware, trial keys, credentials and
certificate data need a separately reviewed handover. Removing role/feature does
not uninstall objects, delete certificates or reclaim storage. Teardown and
migration are separately authorized operations; preserve data and remove mounts
before deleting their ConfigMaps.

## Verification

`bootstrap:verify` uses separate read-only tasks. It never installs packages,
applies objects, restarts Pods or repairs drift. Checks cover:

- Receipt/UID ownership and live ConfigMap/HelmChartConfig against compiled
  public projections, without displaying private operator edits.
- Helm's intended template, one replica, Recreate strategy, owned claim and
  rollout. An old Ready Deployment is not sufficient.
- Bound storage and a nonempty ACME file at mode 0600, without reading keys.
- Mounted dynamic-file hashes against the intended ConfigMap data, allowing for
  asynchronous Kubernetes projection rather than accepting API submission alone.
- Certificate hostname and at least one day's validity, directly against node
  ingress with SNI, independent of application DNS.
- Production system-CA and TLS-handshake hostname trust. Staging checks requested
  hostname/validity only and does not claim public trust.

The probe keeps a public certificate in process memory and reads no private key.
OpenSSL is installed only during configure. Middleware request/deny behavior,
apps, reload, renewal and persistence after replacement remain separate live
acceptance tests. Verify creates no synthetic apps and changes no DNS.

Offline tests cover validation, secret separation, canonical policy, complete
chains, actual Ansible schema/ownership guards and Go-template-safe atomic
updates. They do not establish successful live ACME issuance.
