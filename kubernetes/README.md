# Kubernetes assets

Canonical public assets for Kubernetes platform services. Ansible roles own
installation, updates, resource ownership and verification; this directory
does not introduce a separate deployment mechanism.

## Layout

```text
kubernetes/
├── cilium/
│   ├── cilium-chart.yaml
│   └── cilium-network.yaml
├── crowdsec/
│   ├── profiles.yaml
│   └── start.sh
└── traefik/
    └── crowdsec-plugin/
        ├── Dockerfile
        └── stage.sh
```

- **`cilium/`**: the pinned K3s HelmChart and server network configuration,
  installed and guarded by the
  [Cilium role](../ansible/roles/k3s_cilium/README.md).
- **`crowdsec/`**: LAPI startup and remediation configuration used by the
  bootstrap compiler and
  [CrowdSec role](../ansible/roles/k3s_crowdsec/README.md).
  Application-log acquisition remains separate.
- **`traefik/crowdsec-plugin/`**: the plugin-only image build context and
  non-fatal source-staging initializer used by the
  [Traefik role](../ansible/roles/k3s_traefik/README.md).

These files are not a recursive `kubectl apply` bundle. For example,
`cilium-network.yaml` is host-side K3s configuration, `cilium-chart.yaml`
requires the K3s Helm controller, and CrowdSec's files are runtime fragments.
Use the owning role's documented workflow.

## Related locations

- `ansible/`: deployment, ownership, safety guards and verification.
- `scripts/bootstrap/`: input validation and public manifest generation.
- `tests/`: offline/native regressions and opt-in runtime checks.
- `docs/`: operating guides and validation evidence.
- `config-example/kubernetes/`: placeholder operator configuration examples.
- `config/`: ignored private inputs, credentials and generated manifests.

Do not put real credentials or private generated configuration here. Shared
Docker/Kubernetes Traefik policy currently remains under
`docker/core/traefik/config/dynamic/`; it is not Kubernetes-only configuration
and must not be duplicated here.
