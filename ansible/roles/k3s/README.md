# K3s

Installs a single K3s server on an amd64/arm64 Debian-family systemd host using
the [official installer](https://docs.k3s.io/quick-start). The role uses upstream
defaults: the stable channel on first installation, containerd, SQLite, Flannel,
CoreDNS, Traefik, ServiceLB, metrics-server and local-path storage. No Docker
installation, external datastore or cluster joining is required. Cilium can
optionally replace Flannel on a fresh VM; it is not installed by default. Optional direct
controller access adds one `tls-san` to the K3s configuration. Allow at least 2 CPU
cores and 2 GB RAM; 4 GB RAM is preferable for workloads.

## Bootstrap (Proxmox or AWS)

Initialize either target with the K3s profile:

```bash
task bootstrap:init TARGET=proxmox PROFILE=k3s BOOTSTRAP_CONFIG_DIR=config/my-k3s
# Or use TARGET=aws with a separate deployment directory.
```

For opt-in direct controller access, add `K3S_API_HOST=k3s.example.com` and an
optional `K3S_CONTEXT=my-k3s` during initialization. The API name must resolve
externally unless you privately enable the AdGuard DNS settings described below.
This creates no VM, changes no existing deployment and keeps provider settings
from the target template for review.

Alternatively, initialize normally and replace these sections in its private
`bootstrap.yaml` before planning:

```yaml
roles:
  - debian_base
  - k3s
services: []
host: {}
dns:
  enabled: false
secrets: {}
```

Retain the template's `version`, `target`, `vm` and provider section. Use a dedicated
VM name such as `k3s-proxmox` or `k3s-aws`. Existing Docker deployments are not
migrated or uninstalled by changing role selection. Use a fresh VM: K3s's bundled
Traefik/ServiceLB need ports 80/443 and must not compete with an existing proxy.
Bootstrap rejects selecting Docker applications alongside this default K3s role.

Follow the usual [Proxmox](../../../docs/setup.md) or
[AWS](../../../docs/bootstrap-aws.md) plan/apply procedure, passing the same target
and deployment directory throughout. `configure` applies this local role without
requiring a published guest repository ref. `verify` independently checks the
enabled/running service, root-only kubeconfig, API readiness, Ready nodes and
availability of the default packaged deployments. Verification never installs,
restarts, upgrades or changes Kubernetes resources.

While apply is still running, `task bootstrap:status TARGET=proxmox` or
`TARGET=aws` reports the current VM/EC2 state and, once trust has been established,
K3s service and node readiness. This read-only snapshot does not check all
packaged deployments; run `bootstrap:verify` after apply for acceptance.

AWS still provisions/verifies its standard `/storage` data disk. **K3s defaults
store cluster state and local-path volumes on the OS disk** under
`/var/lib/rancher/k3s`, not on `/storage`. Size the OS disk for workloads and back
up cluster state, the server token and application data separately; retaining only
the AWS data disk does not preserve this cluster. Default AWS bootstrap security
groups do not expose TCP 6443 unless K3s controller access is selected. When enabled,
Terraform allows it only from `aws.admin_source_address` (never from everyone).
Existing HTTP/HTTPS rules still apply to applications later exposed through ingress.

## Optional Cilium networking

To install Cilium instead of Flannel, add this to the private `bootstrap.yaml`
**before the first apply**, retaining the VM/provider settings and any `k3s.access`
settings:

```yaml
roles: [debian_base, k3s]
services: []
k3s:
  cilium:
    enabled: true
```

Omitting `k3s.cilium` or setting `enabled: false` keeps upstream networking defaults
and installs nothing extra. This works on both Proxmox and AWS, independently of
controller access. Inspect the selection with `bootstrap:show-config`.

The role disables Flannel and K3s's network-policy controller before first startup,
then uses the built-in K3s Helm controller to install Cilium **1.20.4** from
`https://helm.cilium.io/`. The bootstrap Helm job can run before pod networking is
ready; no Helm or Cilium CLI is required on the controller. Cilium retains
kube-proxy, uses K3s's default pod CIDR `10.42.0.0/16` and a single operator replica.
Traefik, ServiceLB and local-path storage remain enabled; Hubble is disabled.
The guest needs outbound HTTPS access to the chart and container registries and a
[Cilium-compatible kernel](https://docs.cilium.io/en/stable/operations/system_requirements/).
This profile supports the default single-server network, not custom CIDRs or
multi-node networking/security-group configuration.

The role writes `/etc/rancher/k3s/config.yaml.d/20-bootstrap-cilium.yaml` and
`/var/lib/rancher/k3s/server/manifests/bootstrap-cilium.yaml`. Repeat configuration
requires their contents to match; it does not silently upgrade the pinned chart or
overwrite operator edits. Existing installations without these files are rejected
when opting into Cilium: automatic Flannel migration and adoption of externally
managed Cilium are not supported. Disabling Cilium after installation also fails
without deleting files or uninstalling the CNI. Review any migration or upgrade
separately with backups; never remove these files to bypass a guard.

`bootstrap:verify` additionally waits for the Cilium agent DaemonSet and operator
Deployment rollouts, then verifies node and bundled-workload readiness. These are
read-only checks, not a full network-policy/connectivity test. The upstream
`cilium connectivity test` creates test resources and is a separate, explicitly
approved operation. `bootstrap:status` retains its lightweight service/node checks.

See [Cilium on K3s](https://docs.cilium.io/en/stable/installation/k3s/) and
[K3s Helm automation](https://docs.k3s.io/add-ons/helm) for the upstream integration.

## Access and lifecycle

On the guest:

```bash
sudo k3s kubectl get nodes
sudo k3s kubectl get pods -A
```

Admin kubeconfig remains root-owned mode `0600` at
`/etc/rancher/k3s/k3s.yaml`. By default it stays on the guest. To opt into direct
`kubectl`/K9s access **from the Linux bootstrap controller**, add to the same
private `bootstrap.yaml` (retaining the provider/VM settings):

```yaml
roles: [debian_base, k3s]
services: []
host:
  domain: k3s.example.com
dns:
  enabled: true
  # adguard_urls: [https://adguard.example.com] # Proxmox local DNS, if managed here
k3s:
  access:
    enabled: true
    context: k3s-proxmox
    install_context: true
    # host: k3s.example.com # Defaults to host.domain.
secrets: {} # Supply private AdGuard credentials if its URLs are configured.
```

AWS DNS management also needs `dns.cloudflare_zone` and a scoped private
`secrets.cloudflare_token`. For DNS maintained outside bootstrap, use
`dns: {enabled: false}` with `k3s.access.host` set to an externally resolvable
name or a fixed IPv4 instead of `host.domain`. Proxmox public records, DHCP and
router DNS remain outside bootstrap; reserve a stable address. Clients must reach
TCP 6443, and the API TLS certificate must match the configured host. Do not expose
the API publicly without appropriate network restrictions.

Bootstrap-managed DNS requires a fully qualified `host.domain` such as
`k3s.example.com`, not a short name like `k3s`; `bootstrap:show-config` checks this
offline. List every local AdGuard endpoint so bootstrap verifies and tracks
record ownership independently on each instance. It never edits the controller's
hosts file as a fallback.

The controller needs `kubectl`, Python 3/PyYAML and a private `~/.kube` (mode `0700`;
an existing `~/.kube/config` must be a regular `0600` file). Configure retrieves the
admin credential through pinned SSH, validates DNS/TLS and the Ready node **before**
writing `~/.kube/k3s-proxmox.yaml` and registering unique cluster/user/context names
in `~/.kube/config`. Existing context selection and unrelated entries are preserved;
conflicting names or operator edits fail closed. A private ownership receipt and
private backups of changed existing config stay in the deployment directory.
No credentials are printed or passed as command arguments. Run:

```bash
kubectl config use-context k3s-proxmox
kubectl get nodes
k9s
```

`bootstrap:configure` refreshes a deployment-owned copy when K3s rotates the
admin certificate. `bootstrap:verify` checks the installed client without
reinstalling or changing it; `bootstrap:status` shows controller access readiness.
After a reviewed `bootstrap:destroy`, cleanup removes only deployment-owned
controller credentials and contexts (no cluster connection is required), while
preserving unrelated kubeconfig entries and private recovery records. If an
operator changed owned credentials, cleanup stops rather than overwriting edits.
Only explicitly enabled profiles export cluster-admin credentials to the
controller. Workstation access from another machine requires its own approved
credential distribution; the bootstrap controller is not automatically your laptop.

Adding a new hostname to an **existing** K3s installation updates `config.yaml`
and restarts the service once. If the existing API certificate does not acquire
the new SAN, the controller's TLS check fails before any client kubeconfig is
installed. Inspect the K3s certificate and plan a separately approved
[certificate rotation](https://docs.k3s.io/cli/certificate#rotating-client-and-server-certificates)
with backups, then rerun `bootstrap:configure`. Never disable TLS verification
or delete the existing cluster state to bypass this check.

The installer is downloaded over verified HTTPS and verifies the downloaded K3s
binary against the upstream release checksum. The installer script itself follows
the upstream URL; it is not pinned. Repeat runs skip installation when the default
systemd unit exists and ensure the service is enabled/started. They do **not**
follow stable-channel changes or automatically upgrade an existing cluster.
Review [manual upgrades](https://docs.k3s.io/upgrades/manual) separately. A partial
installation or externally customized cluster requires investigation rather than
deleting the unit or state to force reinstall.

Removing `k3s` from `roles` does not uninstall it. There is no automatic role-level
teardown: upstream `/usr/local/bin/k3s-uninstall.sh` deletes local cluster data and
requires explicit approval and backups. VM teardown remains provider-specific.
