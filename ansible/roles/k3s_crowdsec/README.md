# Bootstrap-managed CrowdSec

Opt-in native Kubernetes LAPI and Traefik bouncer integration. Docker CrowdSec
and its credentials are not moved, adopted or changed. No application route is
changed by this role, and no Konverter change is required.

## Explicit profile

Add `k3s_crowdsec` after `k3s` and before `k3s_traefik` in the existing private
bootstrap source. Keep all existing Traefik settings and add `publicaccess` to
its selected middleware list. Supply every field below:

```yaml
roles: [debian_base, k3s, k3s_crowdsec, k3s_traefik]
services: []
k3s:
  crowdsec:
    enabled: true
    namespace: security-crowdsec
    storage_class: local-path
    storage_size: 1Gi
    plugin_image: registry.example.com/crowdsec-plugin@sha256:<image-digest>
    transport: http-cluster
    online_api: false
    resources:
      requests: {cpu: 100m, memory: 128Mi}
      limits: {cpu: "1", memory: 512Mi}
  # Retain the complete existing traefik profile, including its storage/TLS.
```

These are illustrative budgets, not a choice of live storage or sizing.
Select existing storage and adequate resources explicitly. The image placeholder
is deliberately invalid: build and make the reviewed image available before
using its actual digest.

The native single-replica Deployment uses Recreate and a new persistent claim.
Database, local machine credentials and the generated bouncer key live on that
claim. Non-root UID/GID 65532 and `fsGroupChangePolicy: OnRootMismatch` avoid a
privileged ownership initializer and preserve private files on later mounts.
No host filesystem, Docker socket or Kubernetes API token is mounted.
This is not HA, distributed storage or a tested backup.

LAPI has an internal ClusterIP Service and an ingress NetworkPolicy permitting
TCP 8080 only from Pods named by `app.kubernetes.io/name: traefik` in
`kube-system`. Writers in that namespace remain a trust boundary. Policies are
additive: other policies may also grant access. Actual enforcement requires
an enabled policy engine and separate live negative tests.

`transport: http-cluster` explicitly selects unencrypted in-cluster transport.
It is not suitable if node/network observers are outside the trust boundary;
there is no automatic TLS downgrade or public LAPI ingress. Egress is not
restricted by this role. Community API use needs DNS and outbound HTTPS.

`online_api: false` disables community registration and feed access. With log
acquisition deferred, this mode enforces manually supplied decisions only.
`online_api: true` enables CAPI registration with signal sharing disabled, but
does not guarantee community feed updates. CrowdSec 1.8.2 waits for an agent to
report at least one scenario before pulling; this LAPI-only profile does not
provide one. Do not rely on community decisions without independently verifying
feed operation and providing an appropriately configured agent. Generated
credentials persist on the claim. Console enrollment is not configured.
Log collection and a scenario-reporting agent are deferred. Until that
integration and community-feed enforcement are verified, keep K3s ingress
inaccessible from the internet; do not forward HTTP or HTTPS ports to it.

This acquisition-free profile declares an empty Hub catalog. No parsers,
scenarios or collections are installed. This also lets non-root `cscli`
management commands load a valid catalog without reading the upstream image's
root-only registry index. Adding acquisition later must supply actual Hub items
and their compatible catalog rather than reuse this empty profile unchanged.

### Ingress-only update on an existing Proxmox guest

After normal bootstrap has established pinned guest trust and role ownership,
`ansible/playbooks/bootstrap-ingress.yaml` applies only CrowdSec and Traefik.
It does not rerun DNS, VM, base OS, Cilium or application configuration. Supply
the independently verified guest address and existing cluster UID; it refuses
different guest/cluster identities and does not learn SSH trust.

Prepare the existing private source through the normal compiler boundary:

```bash
export BOOTSTRAP_DIR="$PWD/config/my-existing-k3s"
export BOOTSTRAP_TARGET=proxmox
python3 scripts/bootstrap/config.py prepare
export BOOTSTRAP_STATE_DIR="$BOOTSTRAP_DIR/state"
export BOOTSTRAP_INPUT_DIR="$BOOTSTRAP_STATE_DIR/generated"
ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" \
  ansible-playbook -i localhost, -c local \
  ansible/playbooks/bootstrap-ingress.yaml \
  -e bootstrap_ingress_address=192.0.2.10 \
  -e bootstrap_ingress_cluster_uid=11111111-1111-1111-1111-111111111111
```

The path, address and UID above are placeholders, not discovery defaults.
Back up existing private inputs and Traefik staging/receipts before applying.
The controller's Recreate update briefly interrupts all ingress.

## Plugin delivery and failure isolation

Build the plugin-only image using the directory as its build context:

```bash
docker build -t registry.example.com/crowdsec-plugin:reviewed \
  kubernetes/traefik/crowdsec-plugin
```

Publication to your chosen registry and node preloading are separate operator
actions. Builds verify the pinned plugin commit. Runtime init containers only
copy bundled source; they never fetch it from Git or a plugin registry.

The init container uses the same non-root identity as Traefik, a read-only root
filesystem and a Pod-local emptyDir. Copy/chmod operations have bounded
timeouts.
Source validation or copy failure exits successfully without publishing partial
source on the module path. A failed plugin registration disables the protected
routers, not Traefik: `abortOnPluginFailure` is explicitly false. The shared
chain is never replaced with an empty or headers-only substitute.

Missing keys also must not block Pod startup: the Secret projection is optional,
but an unavailable key makes bouncer middleware creation fail. Traefik's own
ping probes remain independent of LAPI. Public-access failure is not a reason
to mark the whole controller unready or restart it.

An init container that cannot start, image pull errors and volume mount failure
still prevent Pod startup; these are explicitly outside the soft-failure
contract. Make images available on replacement nodes for offline recovery.

LAPI outages fail closed in stream mode at the first failed synchronization:
60-second interval plus a five-second HTTP timeout, not instantaneous detection.
Cold initialization synchronizes before serving protected requests. Unrelated
local routes remain usable, though synchronous initialization can delay a
configuration rebuild by the bounded request timeout.

## Credentials, ownership and recovery

CrowdSec generates the dedicated `bootstrap-traefik` bouncer credential. Ansible
transfers it under `no_log` directly to the existing Traefik-owned Secret as
`bouncer-key`; it is never a CLI argument, ConfigMap value, Helm value or public
compiler artifact. The existing Secret name remains unchanged for compatibility.
Traefik reads a mounted key file; changed Secret contents cause its existing
controlled credential-refresh path to restart the consumer.

The role reuses the Traefik adapter's private receipt, UID/resourceVersion and
server-side ownership guards under a separate namespace, manager and directory.
It creates the namespace before server dry-running namespaced objects and
records that UID immediately. A later failure retains the namespace and recovery
evidence. Existing objects are never adopted, overwritten by forced conflicts or
deleted to permit retry. Storage resize, namespace changes, uninstall and
ownership handover require separate approval.

Back up the persistent claim and private receipts securely. A registration
interrupted between database creation and key-file publication stops for private
recovery; do not delete pending files or recreate identities to bypass it.
Automatic key rotation is not implemented. Rotation/revocation requires a
separately reviewed operation preserving database/key consistency.

`bootstrap:verify` is read-only: it checks receipt ownership, desired public
fields, bound storage, rollout and private-key file metadata. It does not read
keys or prove request enforcement. Application acquisition, Loki, AppSec/WAF,
CAPTCHA, Redis, host firewall bouncers and application exposure are not
installed.

## Validation

Offline tests run through `task bootstrap:test`. For disposable local Docker
runtime checks, first build the test image, then run:

```bash
docker build -t konverter-crowdsec-plugin-test:20261122 \
  kubernetes/traefik/crowdsec-plugin
RUN_CROWDSEC_RUNTIME_TESTS=1 python3 -m unittest \
  tests.bootstrap.test_publicaccess_runtime
```

These tests use no kubeconfig, publish no ports and use network-isolated
containers. They verify missing-plugin isolation, cold LAPI failure, decisions,
outage/recovery and persistent identity. Cleanup checks test ownership before
removing containers and repairing ownership of disposable test files.
These Docker tests do not establish Kubernetes deployment, Secret projection
or rotation, real client IPs, policy denial, public exposure or backup
restoration. Those require authorized live acceptance.

See [deployment validation](../../../docs/crowdsec-ingress-validation.md) for
the bounded live checks and remaining acceptance limits.
