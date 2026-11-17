# Labctl design

## Purpose

Labctl is the operator-facing command for selecting and managing application
stacks. Its current Compose backend preserves the established stack layout,
host-specific configuration, and Docker Compose operations. A later Kubernetes
backend will convert selected Compose stacks with Konverter and manage only the
resulting, explicitly owned Kubernetes resources.

This document defines the boundary between the two tools before Kubernetes
implementation begins.

## Existing Compose contract

A stack identifier has the form `category/name` or
`category/subcategory/name`. Its base Compose file is:

```text
docker/<category>/<name>/<name>.yaml
```

The host configuration directory is `config/docker/<hostname>`. Labctl passes
each existing environment file to Docker Compose in this order, with later
files overriding earlier values:

1. `config/docker/.env`
2. `config/docker/<hostname>/.env`
3. `config/docker/.env.<name>`
4. `config/docker/<hostname>/.env.<name>`

When the host `.env` supplies `GPU_COMPOSE_SUFFIX`, labctl also supplies the
existing `<name>-<suffix>.yaml` Compose override. Before `up` or `recreate`,
labctl creates missing external bridge networks declared by the stack.

Host-wide desired state remains a YAML file such as:

```yaml
services:
  - security:
      - name: traefik
        state: up
  - dashboard:
      - name: homepage
```

The supported Compose operations are `pull`, `up`, `down`, `restart`,
`recreate`, `config`, and `logs`. `config` uses
`docker compose config --no-interpolate --no-env-resolution` to avoid
interpolating variables or resolving service environment files. The output
can still contain values written directly in Compose files; treat it as sensitive.

## Phase one: Go Compose implementation

The isolated Go module is `tools/labctl`, with `scripts/labctl` as the
repository-root launcher. The launcher builds the binary when it is missing or
older than its Go sources, so Go is required on the host. It can also be built
explicitly:

```sh
task labctl:build
scripts/labctl config apply
scripts/labctl service recreate ai/ollama
```

The launcher anchors stack and configuration paths to its repository, regardless
of the caller's working directory.
When `config apply --config FILE` selects an alternate manifest, its parent
directory also selects the host-specific environment files and GPU override,
as in the previous Python CLI.

The command has a backend-neutral controller for stack identifiers and
configuration iteration, and a Compose backend that invokes Docker explicitly.
It neither reads Kubernetes configuration nor makes Kubernetes API calls.

The phase-one implementation must preserve the Compose config-file format,
environment precedence, GPU override behavior, external-network creation,
operations, and log options. Tests use temporary Compose/config fixtures and a
fake Docker executor; they never contact a Docker daemon.

## Sharing Go code with Konverter

Go shares code through imported packages in modules. Konverter's current
conversion packages are under `konverter/internal/`. Go intentionally prevents
this separate infra repository from importing those packages, because they are
not a public API.

The initial Kubernetes backend will therefore invoke the versioned Konverter
binary with explicit inputs and a temporary output location. It must not copy
or fork conversion logic. A future public Konverter Go package is an option
only if subprocess use becomes a measured limitation and a stable API can be
designed. A Go workspace or local `replace` directive resolves local modules;
it does not bypass Go's `internal` visibility rule.

## Future Kubernetes backend

The intended flow is:

```text
labctl selects a stack
  -> Konverter converts its Compose input
  -> labctl validates and applies the generated Kubernetes resource set
```

Responsibilities are intentionally separate:

- **labctl** chooses stacks, loads desired-state configuration, selects an
  explicit target, records ownership, and performs lifecycle operations.
- **Konverter** translates explicitly supplied Compose and environment inputs
  into typed Kubernetes manifests, preserving its fail-closed diagnostics.
- **Kubernetes** reconciles the declared resources.

No Kubernetes context, namespace, environment file, converter configuration,
or security setting may be inferred from the shell environment.

### Operation semantics requiring approval

Kubernetes is declarative, so Docker operation names are not automatically
equivalent:

| Compose operation | Candidate Kubernetes behavior | Decision needed |
| --- | --- | --- |
| `up` | Convert, validate, and apply | Apply/preflight contract |
| `down` | Delete only verified labctl-owned resources | Retention and deletion scope |
| `restart` | Trigger a Deployment rollout | Workload/container selection |
| `recreate` | Apply and force a rollout | Exact disruption policy |
| `config` | Convert without applying; optionally server dry-run | Review output location |
| `logs` | Select workload, Pod, and container for `kubectl logs` | Selection rules |
| `pull` | No implicit equivalent | Whether pre-pull is ever allowed |

`down` is particularly sensitive. It must never delete a namespace merely
because a stack used it, and it must not silently delete PVCs, externally
referenced Secrets, or platform-owned resources. Scaling to zero, deletion of
selected resources, and stopped-state overlays are distinct choices.

### Ownership and namespace decisions

Before any apply/delete feature, every generated object needs a stable
labctl-specific ownership label and stack identity. Destructive selection must
require that identity and the labctl manager label; namespace-only deletion is
prohibited.

The project must choose whether namespaces are per stack, per category, or
otherwise mapped. This must align with Konverter's Compose-project-derived
namespace names and prevent collisions between path-based labctl identifiers.
Per-stack namespaces simplify isolation and lifecycle ownership; shared
namespaces complicate network and deletion safety.

### Conversion boundaries

Konverter intentionally does not claim full Docker Compose equivalence.
Examples relevant to this repository include Compose build directives,
multi-file overrides, Docker external networks, volumes/PVCs, Cilium policy,
Traefik trust, and unsupported security settings. A Kubernetes backend must
report conversion diagnostics and fail each unsuitable stack clearly. It must
not globally enable partial conversion, silently fall back to Docker, build
images, infer registry credentials, or weaken security settings.

## Adoption sequence

1. Inventory current stacks as convertible now, convertible with explicit
   configuration, requiring image/storage/network decisions, or Docker-only.
2. Complete and validate the Go Compose backend without changing live service
   behavior.
3. Add a non-mutating Kubernetes conversion preview for sanitized,
   representative stacks.
4. Define and test explicit context selection, server-side preflight,
   namespaces, ownership labels, and apply behavior.
5. Add Kubernetes lifecycle operations one at a time, including persistent-data
   and networking validation.
6. Reassess whether a public Konverter Go API is justified.
