# K3s

Installs a single K3s server on an amd64/arm64 Debian-family systemd host using
the [official installer](https://docs.k3s.io/quick-start). The role uses upstream
defaults: the stable channel on first installation, containerd, SQLite, Flannel,
CoreDNS, Traefik, ServiceLB, metrics-server and local-path storage. No Docker
installation, external datastore, cluster joining or custom K3s configuration is
required. Allow at least 2 CPU cores and 2 GB RAM; 4 GB RAM is preferable for workloads.

## Bootstrap (Proxmox or AWS)

Initialize the desired target normally, then replace these sections in its private
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

AWS still provisions/verifies its standard `/storage` data disk. **K3s defaults
store cluster state and local-path volumes on the OS disk** under
`/var/lib/rancher/k3s`, not on `/storage`. Size the OS disk for workloads and back
up cluster state, the server token and application data separately; retaining only
the AWS data disk does not preserve this cluster. Default AWS bootstrap security
groups do not expose TCP 6443. No additional firewall rules are opened by the role.
Existing HTTP/HTTPS rules still apply to applications later exposed through ingress.

## Access and lifecycle

On the guest:

```bash
sudo k3s kubectl get nodes
sudo k3s kubectl get pods -A
```

Admin kubeconfig remains root-owned mode `0600` at
`/etc/rancher/k3s/k3s.yaml`. The role never prints it, fetches it to the controller,
or grants unprivileged users cluster-admin access. For workstation access, transfer
it privately and use a trusted network or SSH tunnel. For example, forward local
port 16443 to guest `127.0.0.1:6443` and set the copied kubeconfig server to
`https://127.0.0.1:16443`. Do not publish the Kubernetes API to the internet.

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
