# Feature plan: Kubernetes-native monitoring and centralized logging

**Status:** Standalone native stack installed; initial synthetic acceptance
passed; production collection and monitoring migration/cutover pending
**Audience:** Infrastructure implementation agent

## 1. Context and objectives

The environment is a small, self-hosted, family-use Kubernetes cluster: currently
one node, with multiple nodes planned later (up to three in the initial plan),
and an eventual workload of approximately 100 applications. The operator
confirmed the discovered `k3s` context is the initial deployment target.
Most applications are third-party open-source software. Their log formats cannot generally be changed beyond supported application configuration. Logs may be plain text, structured JSON, multiline messages, stdout/stderr, or files. Traffic and query concurrency are expected to be low; actual log volume is not yet measured.

The operator has Prometheus and Grafana in Docker and wants to switch to a
Kubernetes-native setup. Discovery also found an older Compose-converted
Prometheus deployment in k3s. Plan their native replacements together with
logging, preserving all existing instances until acceptance and an individually
approved cutover. This supersedes the original logging-only scope; it does not
authorize deployment or removal. Infrastructure management also involves AI
agents; centralized logs should be accessible programmatically for interactive
troubleshooting and possible scheduled health investigations.

The goal is searchable, persistent application logs across the cluster with minimal resource consumption and operational effort. Optimize for idle overhead, reliable collection, mixed formats, maintenance and reversibility, not enterprise ingestion scale.

## 2. Research summary and architecture decision

| Candidate | Relevant findings | Decision |
|---|---|---|
| Grafana Loki | Established since 2018, broad adoption and active maintenance; native Grafana integration; compact label-indexed storage; supports single-process deployment and local storage. Requires disciplined label selection and explicit retention. | **Selected log backend.** |
| VictoriaLogs | Newer dedicated logging engine, production-ready since 2024; actively maintained by the established VictoriaMetrics team. Promising resource efficiency, flexible field search, local storage and capacity-based retention. Grafana plugin and Fluent Bit ingestion are available. | Preferred future alternative; not deployed now. |
| OpenObserve | Integrated logs, metrics, dashboards and tracing; potentially useful for consolidation but requires changing more of the existing stack. | Deferred. |
| OpenSearch / Elasticsearch | Mature indexed search, but greater resource and operational overhead. | Not justified for this workload. |
| ClickStack / SigNoz / Quickwit | Useful analytical, APM or large searchable archive architectures, but solve requirements not currently present. | Deferred. |

Loki has a substantially larger standalone GitHub community and ecosystem than VictoriaLogs. The comparison is influenced by project age and VictoriaLogs' move to a separate repository in 2025. Both are actively developed; VictoriaMetrics itself is a mature project dating to 2018. GitHub popularity is not an installation count. Published high-throughput benchmarks do not establish actual idle resource usage in this cluster.

**Decision:** deploy Loki with Fluent Bit and plan Kubernetes-native Prometheus
and Grafana, retaining these products rather than changing metrics backends.
Prefer Loki for its maturity and native integration; use a backend-independent
collection pipeline to preserve the option of moving to VictoriaLogs.
VictoriaMetrics as a future Prometheus replacement is a separate decision.
The monitoring migration is staged as described in section 12.

Fluent Bit was selected over Vector, OpenTelemetry Collector and Grafana Alloy for its lightweight Kubernetes/file collection, mature parsing and buffering, and broad backend support. Do not introduce Promtail (end of life March 2026).

## 3. Target architecture

```mermaid
flowchart TD
    A[Application stdout / stderr] --> C[Node-local container logs]
    B[File-only application] --> D[Accessible file or shared-volume tail sidecar]
    D -->|stdout or explicit file input| E
    C --> E[Fluent Bit DaemonSet: collect, enrich, buffer]
    E -->|Loki output| F[Loki: monolithic, one replica]
    F --> G[Persistent storage]
    F --> H[Kubernetes-native Grafana]
    I[Kubernetes-native Prometheus] --> H
    E -. collector metrics .-> I
    F -. backend metrics .-> I
    J[AI agents] -->|Read-only query access| F
    E -. future alternate or parallel output .-> K[VictoriaLogs: not deployed]
```

- Collect on each relevant node using a Fluent Bit DaemonSet. Do not deploy one collector per application by default.
- Run a single-replica Loki monolithic (single-binary) deployment with persistent storage. No distributed Loki, additional message broker, external cache or dedicated object-store deployment is required initially.
- Provision Prometheus and Loki datasources in Kubernetes-native Grafana;
  preserve existing dashboards and needed Docker-host monitoring coverage.
- Keep application collection, normalization and output configuration logically separated. Backend-specific mapping belongs at the output boundary.
- Accept temporary backend unavailability in exchange for simplicity. This is not a highly available or compliance-grade logging system.

## 4. Repository discovery (before implementation)

Inspect the repository and, if permitted, the live cluster using existing tooling. Follow repository instructions and established conventions. Do not infer the following from this plan:

- Deployment mechanism (Helm, GitOps, Kustomize, manifests or other tooling), repository layout, ownership, release pinning and upgrade process.
- Kubernetes distribution, version, container runtime, OS, node roles/taints, runtime log paths and rotation settings.
- Storage classes, available capacity, volume access modes, node affinity, persistence/backup conventions and whether shared storage is available.
- Current Grafana/Prometheus deployment and datasource provisioning, discovery of scrape targets, alerting and dashboards.
- Existing logging agents, log shipping, overlapping inputs, namespaces, networking, security policies, ingress, authentication and secrets management.
- Workload identities and labels, application log destinations, file paths, file permissions and volume mounts. Actual log rates and resource headroom.
- Existing infrastructure-agent access conventions, MCP/tooling, network access and scheduled-job practices.

Reuse existing mechanisms rather than adding parallel infrastructure. If a consequential choice cannot be resolved from the repository or permitted discovery, document it and request input; do not invent values, secrets, paths or configuration. Report evidence, assumptions and blockers. Do not mutate a live cluster merely to discover its configuration.

## 5. Implementation requirements

### 5.1 Loki

- Use a maintained stable version, pinned according to repository conventions. Use monolithic mode, one replica and replication factor 1. Select chart values for the actual pinned version: recent community chart versions renamed `SingleBinary` to `Monolithic`, while some values still use `singleBinary`.
- Prefer TSDB indexing with the supported current schema (v13 where applicable), filesystem-backed storage on a persistent volume, and persistence of required index, chunk, WAL and compactor state. Adapt to existing storage conventions; do not assume a particular storage class or host path.
- Enable compactor-based time retention, including version-appropriate deletion configuration. Verify actual retention and reclamation; setting a retention period alone is insufficient. Filesystem Loki does not automatically prune logs based on free disk space.
- Disable unused deployment modes, dedicated caches and optional components unless needed for the selected configuration. Inspect rendered manifests for unintended pods, services or dependencies. Keep necessary internal components and existing authentication/network controls.
- Configure sensible resource requests and limits based on available headroom, observed usage and existing policy. Avoid aggressive memory limits that cause OOM during queries or compaction.
- Keep the endpoint private. Restrict ingestion to authorized collectors and query access to authorized consumers. Loki does not provide its own authentication layer; use existing network isolation/authentication or an appropriate proxy if necessary. A Kubernetes Service alone is not access control.

### 5.2 Fluent Bit: standard container logs

- Deploy one collector per relevant node, including any additional workload-hosting nodes as the cluster grows. Discover appropriate runtime log paths and mount only required paths read-only.
- Automatically discover and tail workload stdout/stderr. Handle runtime CRI/Docker framing and partial records as applicable, and preserve event timestamps. Use Kubernetes metadata enrichment with least-privilege RBAC.
- Support plain text, JSON and mixed formats. Preserve the original message; parse structured content opportunistically without dropping text when parsing fails. Do not require application changes or maintain a parser for every application. Support application multiline/stack traces selectively when beneficial; avoid merging unrelated messages.
- Persist tail offsets across collector restarts on each node. Enable bounded filesystem buffering with retry/backoff; use persistent node-local storage for state and queues where supported. Bound queue and memory usage; document what happens when capacity is exceeded or files rotate while shipping is unavailable.
- Configure line-size handling, rotation, startup/backfill behavior and failure visibility explicitly. Prefer collecting new logs on rollout unless historical backfill is deliberately requested. Avoid duplicate collection and ingestion of sensitive or irrelevant sources; avoid feedback loops from collector/backend diagnostic logs.
- Use the built-in Loki output plugin and stable, explicit label mapping. No separate collector or forwarding gateway is needed unless the repository/network setup requires one.

### 5.3 Application file logs

A node-level DaemonSet cannot automatically read arbitrary files inside containers. Discover actual file-only applications before making application-specific changes.

| Source | Preferred handling |
|---|---|
| Standard stdout/stderr | Automatic DaemonSet collection. |
| Application can be configured to log to stdout | Prefer supported application configuration if it does not disrupt existing behavior. |
| File in an approved node-accessible directory | Explicit Fluent Bit Tail input, with correct permissions, rotation, metadata and offset tracking. |
| File in a pod-private path or mounted PVC | Share the relevant log directory with a lightweight tail-to-stdout sidecar or appropriate collector, only for affected workloads. |
| Application supports remote log shipping | Consider only when simpler than file access; reuse existing supported mechanisms. |

Do not broadly mount container runtime internals or all application volumes just to access logs. Do not alter unrelated files, permissions, log retention or application behavior. Ensure sidecar-based records can be attributed to the originating application, even when their container identity is the sidecar. Record unsupported/unreachable sources explicitly; do not claim full coverage until verified.

### 5.4 Metadata and log representation

Define a small, backend-neutral field contract, using existing naming conventions where possible. Proposed semantic fields:

| Field | Purpose | Loki indexed label? |
|---|---|---|
| `cluster` | Stable cluster identity | Yes |
| `namespace` | Kubernetes namespace | Yes |
| `app` | Stable workload/application identity | Yes, when reliably derived |
| `container` | Originating container name | Consider if bounded and useful |
| `pod`, `node`, `stream`, `source` | Investigation context | Prefer non-indexed fields initially |
| `message` | Original application log content | No |
| timestamp | Event time, UTC | Native timestamp |
| severity, request/trace ID | Optional parsed attributes | No, initially |

Map existing workload labels to stable application identity; define and document fallback behavior for unlabeled workloads. Avoid indexing pod UIDs, changing pod names, request IDs, timestamps, filenames with unbounded values or arbitrary Kubernetes labels/annotations. Do not enable indiscriminate auto-labeling. Keep other useful metadata in the record or supported structured metadata; avoid storing excessive Kubernetes annotations or duplicated data. Establish an explicit JSON-envelope versus raw-message policy that keeps logs human-readable in Grafana and machine-queryable. Verify timestamp and metadata mapping end to end.

### 5.5 Kubernetes-native Grafana and monitoring

- Provision the Prometheus and Loki datasources declaratively in the native
  Grafana deployment. Reuse Ansible ownership and private credential boundaries.
  Preserve existing datasource/dashboard UIDs where required for compatibility.
  Verify Grafana Explore and available Logs Drilldown functionality against the
  selected version.
- Provide a simple documented way to browse by namespace/application, recent logs, possible error patterns and log volume. Reuse built-in views; avoid unnecessary custom dashboards.
- Expose and scrape Loki and Fluent Bit operational metrics with native
  Prometheus. Monitor backend readiness, ingestion failures, retries/dropped
  records, queue utilization, resource usage and volume free space. Add minimal
  actionable alerts for sustained ingestion failure, growing queues and disk
  pressure using the selected alert-delivery mechanism.
- Retain needed scrape targets and dashboards, including Docker hosts while
  they remain in service. No Prometheus-to-VictoriaMetrics migration or unrelated
  observability refactor. Packaging must account for the one-node resource
  budget rather than enabling every chart component by default.
- Preserve Grafana's Authentik OIDC restrictions and independent local recovery
  login. Do not expose Prometheus/Loki directly as an unauthenticated public API.
  See section 12 for storage, migration and cutover boundaries.

## 6. Initial sizing and retention proposals

These are starting proposals, not measured requirements or fixed commitments. Adjust after discovery; document chosen settings and rationale. Existing cluster policies take precedence.

| Setting | Starting proposal |
|---|---|
| Loki replicas | 1 |
| Retention | 30 days |
| Loki persistent storage | 20 GiB, subject to capacity and measured ingest |
| Loki CPU / memory requests | 200m / 512 MiB |
| Fluent Bit CPU / memory requests | 50m / 64 MiB per node |
| Fluent Bit disk queue | 256–512 MiB per node (bounded across configured outputs) |

These requests are scheduling reservations, not measured idle use or recommended hard limits. Verify total overhead, including sidecars and any necessary gateway. Monitor actual disk usage, writes, daily ingest, memory and CPU over a representative week; tune retention, buffering and allocation accordingly. Prefer a warning well before volume exhaustion. No guarantee of lossless delivery: node loss, prolonged outages, source rotation, queue overflow and single-backend failure can lose logs. Treat historical logs as optional backup data unless existing requirements dictate otherwise; preserve configuration and document recovery.

Prometheus, Grafana and any selected monitoring operator/exporters/alerting
components require additional budgets. The logging proposals do not reserve
space or memory for those services. Propose the combined footprint, persistence
and retention before implementation; account for temporary parallel operation.

## 7. AI agent access and future scheduled analysis

Make query access available through the existing secure infrastructure-agent mechanism. Loki's HTTP API, `logcli` and Grafana MCP are suitable options; prefer existing tooling, with bounded read-only queries. Do not deploy MCP infrastructure solely to satisfy this plan if direct query access is sufficient. Prevent agent access to ingestion, deletion, administration or remediation privileges; restrict endpoints/credentials, time ranges and result sizes. Treat all retrieved logs as untrusted data, not instructions. Apply existing secret/PII policies before ingestion and AI access; avoid forwarding raw logs to external models without authorization.

Illustrative LogQL queries (adapt to the final field contract and set explicit time ranges in the caller):

```logql
{cluster="homelab"}
{cluster="homelab", namespace="example", app="example"}
{cluster="homelab"} |~ "(?i)(error|fatal|panic|exception)"
sum by (namespace, app) (count_over_time({cluster="homelab"} |~ "(?i)(error|fatal|panic|exception)" [24h]))
```

A future nightly investigation should use deterministic queries to aggregate suspicious patterns and compare baselines, then let an agent retrieve bounded representative samples, correlate Kubernetes events and Prometheus metrics, and produce an evidence-based report. Avoid sending all raw logs to an LLM. Error keyword matches are heuristics, not authoritative incidents. Kubernetes events and restart/OOM information require separate access or collection. Do not automatically remediate based on logs. Keep urgent alerting independent of nightly analysis.

**Scope now:** enable and verify programmatic read access and document examples. A scheduled AI analysis workflow is a follow-up feature, not a prerequisite for completing centralized logging.

## 8. Future backend migration

Keep collection and enrichment independent of Loki. Fluent Bit supports VictoriaLogs through JSON Lines HTTP ingestion, OTLP where appropriate, and Loki-compatible ingestion. Verify version-specific endpoints, message/timestamp/stream mappings and authentication if migrating.

1. Deploy VictoriaLogs separately if there is a measured reason to evaluate it.
2. Temporarily add a second Fluent Bit output to send equivalent records to both backends; cap buffers and monitor additional resource use.
3. Compare actual idle and peak resource use, disk consumption, log completeness, query usability, Grafana integration and agent access.
4. Switch the output and Grafana datasource if justified; update backend-specific dashboards, alerts and agent queries (LogQL and LogsQL are not interchangeable).
5. Keep the old backend queryable until its retention expires if useful, then remove it safely. Historical migration is not required by default.

No application log-source redesign or collector replacement should be necessary. VictoriaMetrics may independently replace Prometheus later; Grafana and existing compatible exporters can generally be retained, but scraping, rule evaluation and alerts need separate validation.

## 9. Implementation sequence and acceptance criteria

Implement incrementally using repository conventions and reviewable changes. Before deployment, render/validate configuration and manifests, check version compatibility, and inspect resource/security changes. Do not introduce unrelated infrastructure changes. Apply to a live environment only if authorized by the repository workflow and user.

- [x] Initial discovery documented in section 11; existing mechanisms and
  unresolved blockers recorded. This does not complete host/Grafana inspection
  or multi-node verification.
- [x] Loki and Fluent Bit definitions added with pinned versions, persistence,
  resource settings, retention and bounded buffering; configuration validates
  against the exact images. No unused distributed components are rendered.
- [x] The current node has a healthy collector; synthetic stdout/stderr logs are
  queryable with correct application metadata and timestamps. Recheck each new
  node when added; multi-node runtime validation is future work, not a
  prerequisite requiring an invented second node.
- [ ] Plain text, JSON, runtime partial/multiline logs and representative file-only sources verified without losing message content; inventory of file-only applications and outstanding exceptions recorded.
- [ ] New workloads are discovered automatically; rotation and collector restart tested using safe synthetic logs; offsets/buffers persist as designed and duplicates/loss are characterized.
- [ ] Controlled short backend interruption tested (prefer non-disruptive test environment); backlog drains when restored and overflow behavior is documented. No unsupported claim of exactly-once delivery.
- [ ] Backend restart preserves previously stored sample logs; retention configuration and compactor activity verified; actual deletion verified when practical (or with isolated short-retention test).
- [ ] Grafana datasource works; namespace/application filters and error-search examples are documented; existing metrics/dashboarding remain functional.
- [ ] Native Prometheus/Grafana pass section 12 acceptance before any route
  cutover; old instances, data and credentials remain available for rollback.
- [ ] Operational metrics and actionable failure/disk-pressure visibility are available; baseline resource usage captured or a follow-up measurement explicitly recorded.
- [ ] Authorized read-only API/agent query works; no unnecessary public endpoint or unrestricted write/admin access.
- [ ] Rollback/disable procedure documented (retain PVCs unless explicit data deletion is approved); collector output replacement and optional dual shipping documented.

Deliver repository-native configuration, concise operator documentation, validation evidence, chosen settings and their rationale, and any outstanding coverage/measurement limitations. Do not mark unexecuted runtime tests as passed.

## 10. References

Use documentation for the selected versions; do not copy latest chart values into older versions blindly.

- [Loki project and releases](https://github.com/grafana/loki)
- [Loki monolithic Helm deployment](https://grafana.com/docs/loki/latest/setup/install/helm/install-monolithic/) and [community Helm charts](https://github.com/grafana-community/helm-charts)
- [Loki retention](https://grafana.com/docs/loki/latest/operations/storage/retention/) and [filesystem storage](https://grafana.com/docs/loki/latest/operations/storage/filesystem/)
- [Loki label guidance](https://grafana.com/docs/loki/latest/get-started/labels/) and [HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/)
- [Fluent Bit Kubernetes deployment](https://docs.fluentbit.io/manual/installation/downloads/kubernetes), [Tail input](https://docs.fluentbit.io/manual/data-pipeline/inputs/tail), [buffering](https://docs.fluentbit.io/manual/data-pipeline/buffering), [Loki output](https://docs.fluentbit.io/manual/data-pipeline/outputs/loki)
- [Kubernetes logging architecture](https://kubernetes.io/docs/concepts/cluster-administration/logging/)
- [Grafana MCP](https://github.com/grafana/mcp-grafana)
- [VictoriaLogs](https://github.com/VictoriaMetrics/VictoriaLogs), [Fluent Bit integration](https://docs.victoriametrics.com/victorialogs/data-ingestion/fluentbit/), [ingestion protocols](https://docs.victoriametrics.com/victorialogs/data-ingestion/) and [Grafana datasource](https://grafana.com/grafana/plugins/victoriametrics-logs-datasource/)
- [VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics)

## 11. Initial repository and cluster discovery

### Scope and evidence, 2026-11-24

Read-only discovery used the current infra checkout and the existing `k3s`
context. Cluster identity matched the previously used deployment. No workload
was deployed, restarted or reconfigured. No Secret values, kubeconfig contents,
private bootstrap inputs or application log messages were inspected. Other
hosts and Docker's running Grafana instance were not inspected.

This is a snapshot of the accessible cluster, not proof of future topology.
The operator confirmed that this one-node cluster is the target; additional
nodes are planned, not currently missing from discovery.

### Environment and deployment ownership

| Area | Observed evidence | Implementation consequence |
| --- | --- | --- |
| Nodes | One untainted node; K3s v1.36.5+k3s1 | Confirmed initial target; more nodes later |
| Runtime | Ubuntu 26.04.1 LTS; containerd 2.3.4-k3s1.36 | Use CRI framing |
| Capacity | Four allocatable CPUs; about 8.1 GiB allocatable RAM | Size for this node first |
| Current usage | About 170m CPU and 1867 MiB RAM in one metrics snapshot | Not a peak or idle benchmark |
| Networking | Cilium 1.20.4, Cilium policies and Kubernetes NetworkPolicy | Reuse existing policy engine |
| Logging agents | No Loki, Fluent Bit, Alloy, Vector or OTel workload found | No observed collector to replace |
| Deployment | Ansible-owned native platform roles and K3s Helm controller | Do not add GitOps/controller tooling |
| Applications | Konverter-managed Deployments, including older namespaces | Do not delete or migrate them here |

Repository integration points:

- `kubernetes/README.md`: public runtime/platform assets belong under
  `kubernetes/`; Ansible retains installation, ownership and verification.
- `ansible/roles/k3s_crowdsec/` and `ansible/roles/k3s_traefik/`: existing
  namespace/UID receipts, strict server-side validation, conflict refusal and
  independent verification. Reuse established safeguards; extraction into a
  new shared framework is not required for logging.
- `scripts/bootstrap/`: explicit profile validation and public projections,
  separated from private credential resolution.
- `ansible/Taskfile.bootstrap.yaml` and `tests/bootstrap/`: native/offline
  validation entry points and synthetic regression patterns.
- `kubernetes/cilium/cilium-chart.yaml`: an existing pinned K3s HelmChart
  example. Helm is available through K3s, but Loki/Fluent Bit chart versus native
  manifest packaging and exact release pins still need selection and render
  inspection. No version compatibility claim has been made yet.

### Runtime logs, rotation and collector state

The live kubelet configuration reports:

- `podLogsDir: /var/log/pods`.
- `containerLogMaxSize: 10Mi` and `containerLogMaxFiles: 5`.
- One rotation worker and a ten-second rotation monitor interval.
- Anonymous kubelet authentication disabled; webhook authorization enabled.

These are source-retention settings, not a guaranteed outage-recovery window.
The kubelet stats endpoint exposes current container-log byte counts, but those
counts do not measure daily ingestion or logs written elsewhere.

Host permissions, `/var/log/containers` symlink targets, log-file ownership and
an approved persistent node-local collector state directory remain unverified.
Do not mount runtime internals, request privileged mode, or assume a writable
host path merely to bypass that discovery. No host-shell or Pod exec inspection
was performed. Future inspection should return paths/permissions and sizes only,
not actual application logs.

### Storage and initial sizing

The only observed dynamic StorageClass is `local-path`, using
`rancher.io/local-path`, `WaitForFirstConsumer`, and reclaim policy `Delete`.
Volume expansion is not advertised. The provisioner configuration places data
under `/var/lib/rancher/k3s/storage` by default. Existing NFS PVs are retained,
read-only media mappings, not an approved writable Loki backend.

The node filesystem snapshot reported approximately 247 GiB capacity and
215 GiB available. This is node-wide space, not a reserved Loki allocation.
Local-path claim requests must not be treated as enforced filesystem quotas
without separate verification. Loki and collector queues would compete with
cluster state, images and existing claims on that node.

The section 6 proposals remain proposals: a 20 GiB local claim, 30-day retention
and 200m/512 MiB Loki requests appear feasible for an initial experiment, but
daily ingest, compaction/query peaks and hard limits are not measured. Choose
storage explicitly before implementation. Keep PVCs during disable/rollback;
deleting a local-path PVC may delete the data.

### Existing monitoring and Grafana integration

- Prometheus is deployed in namespace `prometheus`; its observed image is
  `prom/prometheus:v3.9.1`, older than the current Compose source pin.
  Preserve it during native replacement rather than upgrading it in place.
- Its live `prometheus-config` ConfigMap has static jobs for Prometheus,
  node-exporter, cAdvisor and Endlessh. There is no Kubernetes service discovery,
  no `rule_files` and no alerting section in that configuration.
- No Prometheus Operator, ServiceMonitor or PodMonitor CRD was found.
  Packaging selection must explicitly choose standalone native Prometheus or
  an Operator-managed setup; do not assume those CRDs already exist.
- The Prometheus namespace has Cilium ingress policies. Review actual
  collector/backend metric paths and policies before claiming scrape access.
- There is no Grafana Deployment or StatefulSet in this cluster. The public
  `docker/monitoring/grafana/grafana.yaml` defines Grafana with Authentik OIDC,
  LAN middleware and a persistent data mount. It has no datasource provisioning
  mount; the repository contains no Grafana datasource provisioning definition.
  This does not establish how the running Grafana instance is configured.

The operator subsequently requested native Prometheus/Grafana in this cluster.
Confirm the existing Docker hosts, versions, scrape targets and Grafana assets
needed for migration without overwriting existing instances. Alerts also need
an explicit existing delivery mechanism or an approved minimal addition; none
was established by this discovery. The native setup no longer depends on
granting Docker Grafana direct access to Loki.

### Source coverage and identity

Container stdout/stderr is available in kubelet log accounting for the current
application Pods. That does not prove it contains every application event or
that file logging is redundant.

| Source | Evidence | Remaining work |
| --- | --- | --- |
| Jellyfin | `/config` PVC mount; Docker acquisition expects Jellyfin files | Verify live file destinations and duplication |
| Navidrome | `/data` and read-only media mounts; container logs accounted | Verify stdout completeness without changing settings |
| Kiwix, CyberChef, OpenSpeedTest | Container logs accounted | Synthetic collection and identity checks |
| k3s Traefik | Runtime arguments show info logging, no access-log flag | Access logs are not established; separate explicit change |
| Docker Traefik | Source writes diagnostics/access logs to `/logs` | Outside initial k3s collection; preserve Docker ingestion |
| Future file sources | Vaultwarden, WebDAV and Mosquitto definitions reference files | Inventory when those applications enter scope |

The workload label `app.kubernetes.io/name` sometimes names an entire converted
stack; for example, the Prometheus/exporter Pods share it. The instance label
distinguishes those components. Propose an explicit precedence for `app`:
`app.kubernetes.io/instance`, then `app.kubernetes.io/name`, then `app`.
Define a bounded fallback for unlabeled workloads before implementation; do not
silently use changing Pod names or arbitrary labels.

Decide whether to include system/security namespaces and retired-but-running
application namespaces. Automatically tailing every Pod can ingest sensitive
data and duplicate old application instances. Exclude the collector/backend
diagnostics initially unless an explicit non-recursive path is selected.

### Query access and CrowdSec boundary

`scripts/infra-mcp/` exposes Task commands, including operational commands; it is
not a least-privilege log-query boundary. The existing controller kubeconfig is
administrative access and must not become the logging-agent credential.

Recommend a bounded query-only interface, with ingestion and administrative
paths inaccessible to agent consumers. NetworkPolicy alone cannot distinguish
read and write HTTP endpoints on Loki's shared port. If external Grafana/agents
need a routed endpoint, select the existing authentication mechanism and an
explicit query-path/method boundary before implementation. `publicaccess@file`
is CrowdSec plus headers, not user authentication or read-only authorization.
No public Loki ingress or new MCP service is selected.

Centralizing logs in Loki does not enable CrowdSec detection. Its current
LAPI-only profile has no acquisition/scenario items. Application acquisition,
parser/catalog installation and any Loki-to-CrowdSec connection remain a
separately designed integration, not an implied output of this feature.

### Discovery decisions and subsequent resolution

1. Target confirmed: the current one-node `k3s` context, with multi-node growth
   later. Do not provision or join another node as part of this feature.
2. Identify existing Docker monitoring assets needed for migration; authorize
   bounded read-only inspection there if needed. Plan the native monitoring
   deployment using section 12 rather than only attaching Docker Grafana.
3. The initial additive installation uses separate fresh local-path backend
   claims and a fixed node-local collector state path, with budgets in the
   role guide. Collection is synthetic-only until application privacy/scope
   review. Grafana and agent queries use a private GET-only proxy boundary.
4. Packaging is selected in section 12. Notification receivers, old monitoring
   asset migration and actual SSO/route cutover remain unresolved.

Next: complete application-source/privacy and monitoring-migration decisions,
then expand collection and test real browser acceptance before route cutover.
Multi-node, rotation/overflow, actual retention deletion, real reader credential
issuance and representative resource baselines remain outstanding.

## 12. Kubernetes-native Prometheus and Grafana migration

### Scope approved for planning

The operator confirmed the one-node target and requested a Kubernetes-native
Prometheus/Grafana setup instead of keeping monitoring in Docker indefinitely.
Use platform-managed Kubernetes resources, not another conversion of the
monitoring Compose stack. Preserve Docker monitoring and the existing converted
k3s Prometheus until replacement acceptance and separate cutover approval.

No historical metrics/database migration, distributed storage, HA replicas,
new cluster nodes, production secret changes or teardown are implicitly
selected. Historical metrics may remain queryable in the old Prometheus
instance during transition; confirm whether that is sufficient. Do not copy a
live TSDB or Grafana database into a new version without a tested, supported
migration and private backup procedure.

### Selected packaging

Compare two repository-native options before selecting one:

| Option | Benefit | Cost or boundary |
| --- | --- | --- |
| Standalone Prometheus and Grafana, Ansible-managed | Small explicit footprint; no new Operator | Own service discovery, RBAC, rules and provisioning |
| Pinned kube-prometheus-stack, Ansible-managed | Integrated Operator, discovery and rule lifecycle | Additional CRDs/controllers and chart defaults to review |

The implementation selects a dependency-free local chart, installed and
verified by Ansible, with standalone Prometheus/Grafana, single-process Loki,
Fluent Bit and node-exporter DaemonSets, and a query-only proxy. The inspected
kube-prometheus-stack 93.10.0 metadata includes Operator CRDs and optional
Grafana/exporter/state-metrics dependencies. Those integrations are useful, but
the standalone design avoids a new controller/CRD lifecycle for this small
cluster. No rendered Operator benchmark or measured efficiency comparison was
performed; resource-efficiency claims remain hypotheses to measure.

Do not install two monitoring stacks or add ServiceMonitor/PodMonitor resources
unless the chosen setup supports them. If using an Operator, pin CRD versions,
define upgrade/ownership handling and disable unsuitable defaults, including
K3s-inapplicable control-plane scrapes. Ansible remains deployment ownership;
no additional GitOps controller is required.

### Native collection and persistence requirements

- Scrape native Kubernetes kubelet/container metrics over authenticated TLS
  using least-privilege identities. Do not treat a Docker-oriented cAdvisor
  Pod as Kubernetes container coverage or enable the insecure kubelet port.
- Plan node-exporter as a DaemonSet for relevant current/future nodes, with
  explicit read-only host access. Retain Docker-host exporters where required.
  Evaluate kube-state-metrics for workload/restart/state visibility explicitly;
  it is not installed or approved merely by naming it here.
- Discover and retain application/external targets such as Endlessh and
  Docker/NAS exporters. Document any target intentionally deferred; avoid
  silently losing coverage when moving to native service discovery.
- Allocate separate persistent storage for Prometheus TSDB and Grafana state.
  Propose metric retention by time and size, Grafana persistence, resources and
  alerting overhead alongside Loki/Fluent Bit. Do not reuse application claims
  or claim that local-path storage supports failover across nodes.
- Future nodes should receive collectors/exporters through DaemonSets and
  appropriate discovery/RBAC. A local-path backend stays node-bound; adding a
  node does not make stored metrics/logs HA or automatically relocate them.
- Provision datasources, selected dashboards and rules declaratively. Preserve
  needed UIDs and document which Grafana state remains database-managed.
- Reuse Authentik OIDC and approved LAN ingress for Grafana, with credentials
  delivered privately. Keep an independently usable local recovery account.
  Machine-query identities must be read-only; browser SSO is not sufficient.
- Select one alert evaluation/delivery arrangement and approved receiver.
  Alertmanager or Grafana alerting are options, not simultaneous defaults.
  Avoid duplicate notifications during parallel operation. Keep an external
  cluster-health observer because in-cluster monitoring fails with the cluster.

### Staged implementation and acceptance

1. Inventory only the required existing monitoring configuration/assets through
   safe read-only inspection. Record external scrape targets, dashboards,
   datasource UIDs, OIDC requirements, alert receivers and historical-data needs;
   never copy private databases, credentials or raw application data into tests
   or this plan.
2. Select packaging and approve the combined storage/resource/security profile.
   Render pinned definitions offline, inspect RBAC/network/host access and test
   ownership, provisioning and disabled behavior. Use separate resource
   identities for the native stack to avoid adopting the converted deployment.
3. With separate live authorization, deploy native monitoring in parallel.
   Verify target discovery, authenticated scrapes, actual series and timestamps,
   dashboards, Grafana SSO/group restrictions and local recovery login. Test
   backend restart and state persistence using safe data. No route cutover yet.
4. Add Loki/Fluent Bit, provision the native Grafana Loki datasource and scrape
   their operational metrics. Complete the logging acceptance tests and verify
   read-only agent queries without granting ingest/delete/admin access.
5. Obtain operator acceptance and route-cutover approval individually. Verify
   existing dashboards/targets remain usable and alerts reach the selected
   receiver without duplicate delivery. Retain old data and a documented route
   rollback until the operator approves retirement.
6. Retire Docker monitoring and the old converted k3s Prometheus only under
   explicit teardown authorization. Exporter removal requires checking remaining
   consumers. Preserve old claims/data unless deletion is separately approved.

### Implementation and acceptance boundary

The public implementation is under `kubernetes/observability/`,
`ansible/roles/k3s_observability/`, `ansible/playbooks/observability.yaml`,
`scripts/observability/` and `tests/test_observability*.py`. See the
[role guide](../../ansible/roles/k3s_observability/README.md) for exact commands,
budgets, security boundaries, recovery and known limitations.

The new stack is installed in its own `observability` namespace. Initial log
collection is limited to the disposable `observability-smoke` namespace.
Ansible validates cluster identity, namespace/credential ownership and public
object UIDs; independent desired-field, readiness and claim checks passed.
No existing monitoring instance or application route was changed.

Exact-image Docker checks passed for Loki, Prometheus/promtool, Fluent Bit and
the query proxy. Native wrong-cluster/unowned-namespace guards are covered by
synthetic tests. The combined observability and existing ingress regression run
passed all 49 tests; focused pre-commit checks passed. The repository-wide KICS
hook was excluded in favor of the scoped scan documented below. A live test
exposed an Ansible block-condition ordering issue
in the initial credential receipt; the ordering was fixed and regression-tested.
The operator approved a bounded recovery that verified ownership and retained
credential equality privately before recording the missing UID. No credential
was rotated or deleted.

A scoped KICS 2.2.0 scan of public rendered manifests reported zero critical
and 12 high findings: two host-mount rules flag each of the six intentional
node log/state and exporter mounts. These were not suppressed or reported as
a passing scan. Read-only mounts, capability removal, no hostPID/hostNetwork,
private state and restricted identities constrain but do not eliminate the
host-access risk. The collector's root identity is limited to reading node logs
and its own queue; it has no runtime socket or application-volume mounts.

Grafana has a privately generated local recovery credential and declarative
datasources/dashboard. It remains private, with no existing hostname cutover.
Optional OIDC takes explicit endpoints and an existing Secret, but real browser
login/group denial/logout/recovery have not been tested. No raw application
logs, Docker monitoring databases or private dashboard exports were read.

#### Initial live acceptance results

| Check | Observed result |
| --- | --- |
| Independent Ansible verification | Desired public fields, ownership, rollouts and claims passed |
| Repeat configuration | Passed; Pod identities/restart counts unchanged |
| Synthetic ingestion | Plain text, JSON, stdout/stderr and timestamps queryable |
| Reader identity | Query GET succeeded; write and ingestion/admin access denied |
| Network isolation | DNS-positive untrusted Pod denied backend, proxy and Prometheus |
| Native metrics | Kubelet, container metrics and four stack targets healthy |
| Pod replacement | Old sample and new delivery survived Loki/collector replacement |
| Grafana API acceptance | Recovery login, both datasource health checks and overview passed |
| Existing services | Prior Deployment/DaemonSet/IngressRoute UIDs and generations unchanged |
| Test cleanup | Exact test-owned namespace deleted with UID precondition |

The smoke harness initially froze query time before messages arrived and used
a BusyBox DNS lookup without the cluster domain. Those test errors were
diagnosed separately from the working collection path and corrected before
the successful acceptance run. Failed synthetic sources were retained until
identity-checked resume and final cleanup.

A single post-smoke metrics snapshot reported approximately 32m total CPU and
330 MiB memory for the six new Pods. This is not a representative week, peak
query load, capacity guarantee or comparative idle benchmark. Storage requests
and memory limits must not be inferred from this point measurement.

Short Pod-replacement recovery is not complete outage/overflow/rotation testing.
No actual 30-day retention deletion, external backup restoration or
production-source completeness claim follows from these checks.

Application namespace opt-in/privacy review, file-only sources, real OIDC and
existing dashboards/external targets, notification receivers, actual retention
deletion, prolonged backlog/overflow behavior, external backup/restore and
multi-node acceptance remain incomplete. No old monitoring teardown is
authorized or required by the successful additive installation.
