# K3s Cilium networking

Prepares Cilium instead of Flannel on a fresh single-server K3s VM. This role
must run **before `k3s`**, because the network configuration and bootstrap chart
must exist before the server's first start. It does not install or start K3s.

In the private `bootstrap.yaml`, retain VM/provider settings and select:

```yaml
roles: [debian_base, k3s_cilium, k3s]
services: []
```

Role selection is the only switch; there is no separate enable flag. Bootstrap
rejects missing or misordered server roles before provider access. Existing Cilium
profiles must add `k3s_cilium` before `k3s` and remove the obsolete `k3s.cilium`
settings block (the schema rejects it). This role
retains the same on-host paths and byte-identical files, so matching existing
bootstrap installations require no network migration. Default K3s profiles omit
the role to retain Flannel.
The feature works on Proxmox and AWS independently of API access and Traefik.
See [bootstrap input safety](../../../docs/bootstrap-configuration.md) for private
editing and `bootstrap:show-config`; never inspect private inputs with raw tools.

## Installation and ownership

The role disables Flannel and K3s's network-policy controller, then stages Cilium
**1.20.4** from `https://helm.cilium.io/` for the built-in K3s Helm controller.
The bootstrap Helm job runs before pod networking is ready; no controller-side
Helm/Cilium CLI is required. Cilium retains kube-proxy, uses the default pod CIDR
`10.42.0.0/16` and one operator replica. Traefik, ServiceLB and local-path remain
enabled; Hubble is disabled. Outbound chart/image access and a
[compatible kernel](https://docs.cilium.io/en/stable/operations/system_requirements/)
are required. Custom CIDRs and multi-node networking/security groups are outside
this profile.

Owned files remain:

- `/etc/rancher/k3s/config.yaml.d/20-bootstrap-cilium.yaml`
- `/var/lib/rancher/k3s/server/manifests/bootstrap-cilium.yaml`

Repeat configuration requires exact matching contents; operator edits and implicit
chart upgrades are refused. Existing servers missing these files are rejected;
automatic Flannel migration or adoption of external Cilium is unsupported.
Bootstrap checks these paths even when the Cilium role is deselected while K3s
remains selected, refusing silent disabling without deleting files or the CNI.
The omitted-role guard performs inspection only. Review upgrades/migrations separately
with backups; never remove files to bypass a guard. Removing roles does not
uninstall networking.

## Verification

After the `k3s` role starts and verifies the server, bootstrap independently runs
`k3s_cilium`'s `verify` tasks for both configure and verify-only workflows. These
read-only checks wait for the Cilium agent DaemonSet and operator Deployment
rollouts; they never stage files or install resources. The role's main entry point
only prepares networking and cannot verify rollouts before K3s is installed.
Standalone playbooks should likewise run `k3s_cilium`, then `k3s`, then include
`k3s_cilium` with `tasks_from: verify`.

Server checks cover node and bundled-workload readiness. These are not full
network-policy/connectivity acceptance. `cilium connectivity test` creates resources
and requires separate approval. `bootstrap:status` remains a lightweight
service/node check.

Upstream: [Cilium on K3s](https://docs.cilium.io/en/stable/installation/k3s/),
[K3s Helm automation](https://docs.k3s.io/add-ons/helm).
