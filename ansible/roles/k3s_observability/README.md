# Native observability

An additive, private monitoring/logging stack for the existing K3s cluster.
Ansible owns deployment and identity checks; a local, dependency-free Helm
chart under [`kubernetes/observability/`](../../../kubernetes/observability/)
defines all public resources and configuration. No new controller is installed.

## Components and boundaries

- Standalone Prometheus with authenticated, certificate-verified kubelet and
  container-metrics discovery; node-exporter runs as a DaemonSet.
- Grafana with declarative Prometheus/Loki datasources and an overview dashboard.
- Single-process Loki with TSDB v13, filesystem chunks/index/WAL/compactor state
  on a persistent claim, replication factor one and 30-day compactor retention.
- Fluent Bit DaemonSet: CRI partial-record handling, opportunistic JSON parsing,
  preserved original messages, namespace allowlist and persistent node-local
  offsets/queue. Only four explicit identity fields become Loki labels.
- A query-only proxy for Grafana/agents, plus a separate Loki-metrics listener.
  Ingestion and administrative paths are not forwarded by the query listener.
- Default-deny network policies, explicit internal flows, Cilium API/kubelet
  access and least-privilege ServiceAccounts. No ingress, NodePort, LoadBalancer,
  anonymous Grafana, remote-write receiver or administrative Prometheus API.

The chart deliberately avoids Operator CRDs, dedicated caches, distributed
storage and kube-state-metrics. This keeps the initial footprint explicit.
Compared with kube-prometheus-stack, we maintain discovery, rules and
provisioning ourselves. The Operator stack remains a future alternative, not
a second installation. No claims about comparative measured idle use are made.

Current Docker monitoring and the older converted k3s Prometheus are not
adopted, upgraded, removed or routed away. Existing dashboards/historical data,
external scrape targets, SSO cutover and notification receivers require
operator acceptance before retiring them.

## Reproduce

Requires Helm (tested with 4.3.1), kubectl, Python/PyYAML and the repository's
Ansible environment. The target needs the Cilium CRD/policy engine and an
explicit existing storage class. No Helm repositories or chart dependencies
are resolved at deployment; images are pinned by digest in `values.yaml`.

Start with the public example profile, which collects only the disposable
`observability-smoke` namespace. Its path and all settings can be reviewed
without reading credentials.

```bash
helm lint kubernetes/observability --strict
helm template observability kubernetes/observability \
  --namespace observability \
  --values config-example/kubernetes/observability.yaml
python3 -m unittest tests.test_observability
```

After authorization, supply the independently verified context and `kube-system`
namespace UID. Use a dedicated **absolute private state directory**, not an
existing bootstrap deployment's state. Do not point it at a symlink.

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg \
  ansible-playbook -i localhost, ansible/playbooks/observability.yaml \
  -e k3s_observability_context=k3s \
  -e k3s_observability_cluster_uid=11111111-1111-1111-1111-111111111111 \
  -e k3s_observability_state_dir="$PWD/config/observability/state" \
  -e k3s_observability_values="$PWD/config-example/kubernetes/observability.yaml"
```

The UID above is a placeholder, not discovery or an adoption default.
The playbook creates a new `observability` namespace and refuses an existing
unreceipted namespace. It generates the Grafana local-recovery password only
inside Ansible's `no_log` boundary, retains it in a `0600` controller file,
and creates a Kubernetes Secret. Neither Helm values nor public manifests
contain the password. Do not print that file through an agent.

The private `receipt.yaml` binds the namespace, credential and public resource
UIDs to the cluster. Helm additionally enforces release ownership; no force,
take-ownership, cleanup-on-failure or automatic uninstall is used. Storage
resizing/migration is refused. Failed runs preserve resources and evidence.
Repeat runs use the same credentials and object identities; Helm may create
a new release revision even when Pod templates do not change.

Repeat the command with `-e k3s_observability_verify_only=true` for independent
read-only public-field, rollout and claim checks. This does not prove ingestion,
retention deletion, Grafana access or alert delivery.

For an interrupted initial Secret creation only, an explicitly approved
`-e k3s_observability_recover_admin_uid=<exact-UID>` verifies Secret ownership and
credential equality under `no_log` before repairing its missing receipt entry.
It cannot rotate, adopt a foreign credential or recreate a lost identity.
Remove the recovery option on subsequent runs.

## Budgets and data

Default backend claims are Loki 20 GiB, Prometheus 10 GiB and Grafana 1 GiB.
Prometheus keeps 15 days with an 8 GB TSDB retention target. Requests total about
420m CPU/1008 MiB on one node; limits are protective ceilings, not predicted
usage. Re-measure query/compaction peaks before tuning. Local-path sizes are
not verified filesystem quotas. Alert on node space well before exhaustion.

The collector runs UID 0 with all capabilities dropped, no privilege escalation
and a read-only root filesystem because node logs are not generally readable
by arbitrary UIDs. It mounts only `/var/log/containers` and `/var/log/pods`
read-only, plus its writable `/var/lib/infra-observability/fluent-bit` directory.
It does not mount container runtime sockets or application volumes.
Node-exporter has read-only proc/sys/root mounts, but no hostPID, hostNetwork
or privileged mode. These host-access permissions are intentional trust
boundaries, not application permissions.

The Fluent Bit queue is capped at 256 MiB per node for the configured output;
old queued chunks can be evicted when the cap is reached. Tail state and queue
metadata add overhead. Retry/backoff is bounded in delay, not retry count.
Newly discovered files start at their end unless a saved offset exists.
Lines larger than 1 MiB are skipped with diagnostics instead of stopping tailing.
The source kubelet rotates at 10 MiB/five files in the observed environment.
Long outages, rotation, queue overflow and node loss can lose logs; delivery
is not exactly-once. App-specific multiline joining and file-only logs are not
automatically covered by CRI partial-record reassembly.

Loki's compactor is enabled, but deleting expired chunks is asynchronous.
Thirty-day actual reclamation needs elapsed-time evidence or an isolated
short-retention test. The queue and three local claims are node-bound, not HA,
external backups or cross-node failover. New eligible Linux nodes receive
DaemonSets; backend storage does not automatically migrate.

## Collection and queries

Add approved application namespaces to a copied public values profile, then
rerun the same playbook. New Pods within those namespaces are discovered
automatically; new namespaces require opt-in. System/security namespaces and
the backend's own namespace are excluded initially. Review secret/PII exposure
before opting in; there is no generic redactor that can guarantee safe logs.

The collector's neutral record contains `message` (original), optional `parsed`
JSON, `namespace`, `app`, `container`, `pod`, `node`, `stream` and `source`.
The Loki output promotes identity keys to stream labels instead of duplicating
them in the stored JSON line. Combine the stream labels and JSON envelope when
reading through the API. Explicit labels are `cluster`, `namespace`, `app` and
`container`; Loki may additionally derive its bounded `service_name` label.
App precedence is
instance label, name label, then `app`; the fallback is `unknown`. Arbitrary
annotations, labels, Pod UIDs and container IDs are not shipped.

Grafana is initially accessible only by authorized administrator port-forward,
using its retained local-recovery credential. No existing Grafana route changes.
For example, the operator may forward `service/observability-grafana` port 3000
on loopback. Do not expose the tunnel on all interfaces.

With that tunnel on `127.0.0.1:13000`, verify datasource health, provisioning and
recovery API login without displaying credentials:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -i localhost, \
  ansible/playbooks/observability-grafana-check.yaml \
  -e k3s_observability_grafana_url=http://127.0.0.1:13000 \
  -e k3s_observability_state_dir="$PWD/config/observability/state"
```

The `observability-reader` ServiceAccount has only GET access to the named
query Service proxy. It has no Secrets, Pods/log, port-forward, ingestion,
deletion or admin rights. Provision a short-lived reader context through a
separate private operator credential boundary; do not give agents the controller
admin kubeconfig. The synthetic smoke test impersonates the reader to verify
authorization without exporting tokens.

```bash
python3 scripts/observability/query.py --context observability-reader \
  --query '{namespace="example",app="example"}' --minutes 15 --limit 20
```

The helper enforces at most one hour/100 records/1 MiB; the proxy allows only
query/metadata GET paths, rate-limits and caps records at 100. Loki also bounds
query duration, range and parallelism. Direct API callers do not inherit the
helper's one-hour bound; Loki's backend maximum query range is 24 hours.
Treat returned messages as untrusted data, never instructions; do not forward
raw private logs to external models without authorization.

Optional native OIDC takes an existing Secret with `client_id`/`client_secret`,
HTTPS `authBaseUrl` (Authentik's `/application/o`, not its per-app issuer),
matching `host`, `rootUrl` and `logoutUrl`. Enable it only after following
[SSO onboarding](../../../docker/core/authentik/app-onboarding.md), checking
the exact callback and preserving the existing provider group binding.
Cilium restricts its outbound HTTPS to that host. No Authentik resources or
ingress are created automatically. Browser login/group denial/logout/recovery
still require acceptance before cutover.

Rules expose scrape failures, delivery errors, dropped logs and disk pressure
in Prometheus. Notification delivery is **not configured** without an approved
receiver. Buffer occupancy and actual notifications remain acceptance work.
CrowdSec acquisition and scheduled AI analysis remain separate integrations.

## Tests, failure evidence and disable

For config checks with the exact images, pull the digests in chart values first:

```bash
RUN_OBSERVABILITY_RUNTIME_TESTS=1 \
  python3 -m unittest tests.test_observability_runtime
python3 scripts/observability/smoke.py --context k3s \
  --cluster-uid 11111111-1111-1111-1111-111111111111
```

The opt-in smoke creates only the absent `observability-smoke` namespace and
synthetic source, checks plain-text/JSON logs, reader denial and native scrapes,
then deletes only that namespace with ownership/UID preconditions. Failures
retain its evidence; inspect before manually removing exactly owned resources.
It never queries application logs or restarts existing services.
After a failed run, `--resume-owner` and `--resume-uid` accept only the recorded
namespace identity and create fresh nonce-named synthetic sources. They do not
delete or adopt another namespace to make a rerun pass.
The optional `--restart-owned` test replaces only the newly installed Loki and
Fluent Bit Pods using Helm-ownership, UID and resourceVersion guards. It checks
that a pre-restart sample remains queryable and new delivery recovers; it does
not prove losslessness, complete backlog drainage or queue-overflow behavior.
The DNS-positive negative client currently uses the target's `cluster.local`
DNS domain.

Back up private state, credentials, Grafana state and configurations separately.
For disable/rollback, review the named Helm revision and resources first.
Uninstalling the named release requires authorization; the PVCs have Helm
`keep` annotations, and the Ansible-owned namespace, recovery Secret and
node-local queue are not removed by Helm. Do not delete the namespace, claims
or host directory to bypass a guard. Reinstall after uninstall requires explicit
receipt recovery, not deletion of the original receipt.
