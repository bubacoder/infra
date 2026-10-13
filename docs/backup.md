# Backup and recovery

Kopia B2 snapshots checked database/native exports separately from application
files. Application-specific recovery steps live in the service READMEs below.

## Coverage and storage

Set the host paths in `config/docker/<host>/.env`:

```dotenv
DOCKER_VOLUMES=/mnt/docker-volumes
DB_BACKUP_ROOT=/path/to/backup-disk/db-backups
```

The export root must exist outside Docker volumes. **It is recommended to store it
on a second physical disk, separate from the disk holding application volumes.**
Replace the example path with your own disk location. The directory must
belong to the non-root backup user and have mode `0700`. Export files are private
(`0600`). Kopia mounts both sources read-only; applications do not receive access
to the export directory.

| Data/job | Location or Kopia source | Daily time, host local |
|---|---|---|
| Export generation | `${DB_BACKUP_ROOT}/<category>-<service>/<UTC timestamp>/` | 00:05 |
| Prepare latest view and database/native snapshot | Host job → `/sources/local/db-backups` | 01:15 |
| Application-file snapshot | `/sources/local/docker-volumes` | 01:20 |
| Coverage verification and local pruning | Host job | 03:00 |

Both snapshot policies retain latest 10, hourly 48, daily 7, weekly 4, monthly 6
and annual 0 snapshots. These categories overlap. Local retention keeps seven
completed exports per service after remote coverage passes. New database snapshots
contain only the latest usable verified export per service, not all seven local exports.

### Latest-only database snapshot view

`${DB_BACKUP_ROOT}/latest/` is a real directory containing real service/timestamp
directories and hard-linked artifact files, including `manifest.json`. Kopia mounts
this view read-only at `/sources/local/db-backups`; the local timestamped history
remains outside that mount. For example:

```text
${DB_BACKUP_ROOT}/
├── tools-vaultwarden/<timestamp>/database.sqlite3  # local history
└── latest/tools-vaultwarden/<timestamp>/database.sqlite3  # same inode
```

Hard links add directory entries without another copy of the file contents. They
require the same filesystem, which placing the view under the export root provides.
Published exports must remain immutable: writing through either pathname changes
the same file. Directory symlinks are not used; backing up a link alone does not
back up its target's contents.

The host `latest.py` job holds a view lock through preparation and the foreground
Kopia upload. It locks each service while selecting and verifying its exports,
checks hashes/native format, and builds the replacement view before installing its
contents. **One service failure does not block the others or the Kopia DB upload.**

- Each service uses its newest valid export. If the newest is invalid, older local
  exports are tried and revalidated; the failure remains explicitly reported.
- A valid export older than 24 hours is still included as that service's latest
  available recovery point, with a stale-export warning. Future/invalid publication
  times are rejected.
- If local selection fails (including a busy service lock), the previous frozen
  export is revalidated and reused when available. If no usable export exists,
  only that service is omitted, with an explicit error.
- Kopia snapshots all available verified exports. After a successful upload, the
  command exits **1** and logs **DEGRADED** if any service was stale, failed validation,
  used a fallback or was omitted. Exit **0** means all configured services were
  included with valid recent exports; an export-job failure is also recorded by
  the independent `run.py --run-all` job.

Global failures such as a wrong mount, view-lock contention, inability to install
the view or a Kopia upload error still fail the job. If no service has a usable
export, the previous view is preserved and no empty snapshot is uploaded. Abandoned
staging is removed on the next run. Service exports can continue after the hard
links have been created without modifying the frozen selection.

The `latest/` root itself stays in place so Docker's bind mount remains valid. Each
successful refresh removes superseded links. Deleting a local history pathname does
not invalidate a linked file still in the view. Snapshot paths retain their timestamp
component, so remote coverage still identifies the exact local export.

The DB policy is **manual-only in Kopia**; the host cron job provides its daily
schedule. Use `latest.py` for ad-hoc DB snapshots too, so preparation and uploading
share the lock. The Kopia UI or a direct snapshot command bypasses that coordination.
`--prepare-only` is for migration/maintenance when DB uploads are stopped.

### Applications and recovery instructions

| Export target | Artifacts | Application recovery |
|---|---|---|
| `tools/vaultwarden` | `database.sqlite3` | [Vaultwarden](../docker/tools/vaultwarden/README.md#recovery) |
| `tools/guacamole` | `database.dump`, `globals.sql` | [Guacamole](../docker/tools/guacamole/README.md#recovery) |
| `dev/gitea` | `database.sqlite3` | [Gitea](../docker/dev/gitea/README.md#recovery) |
| `ai/open-webui` | `database.sqlite3`, `database-chroma.sqlite3` | [Open WebUI](../docker/ai/open-webui/README.md#recovery) |
| `automation/n8n` | `database.dump`, `globals.sql` | [n8n](../docker/automation/n8n/README.md#recovery) |
| `database/postgresql` | `database-<name>.dump`, `globals.sql` | [PostgreSQL](../docker/database/postgresql/README.md#recovery), [Mattermost](../docker/communication/mattermost/README.md#recovery) |
| `database/mongodb` | `database.archive.gz` | [MongoDB](../docker/database/mongodb/README.md#recovery), [UniFi](../docker/infra/unifi-network-application/README.md#recovery) |
| `database/couchdb` | Staged `couchdb/data/` and `couchdb/etc/` | [CouchDB](../docker/database/couchdb/README.md#recovery), [Obsidian](../docker/tools/obsidian/README.md#recovery) |
| `security/authentik` | `database.dump`, `globals.sql` | [Authentik](../docker/security/authentik/README.md#recovery) |
| `media/photo/immich` | `database.dump`, `globals.sql` | [Immich](../docker/media/photo/immich/README.md#recovery) |
| `security/wg-easy` | `database.sqlite3` | [wg-easy](../docker/security/wg-easy/README.md#recovery) |
| `automation/homeassistant` | `homeassistant.tar`, `database.sqlite3` | [Home Assistant](../docker/automation/homeassistant/README.md#recovery) |
| `ai/qdrant` | `full.snapshot`, `inventory.json` | [Qdrant](../docker/ai/qdrant/README.md#recovery-and-post-restore-check) |

Every export includes `manifest.json` with artifact sizes and SHA-256 hashes.
Home Assistant is enabled by its administrator token or an existing export
directory; missing credentials then report failure rather than silently dropping it.

### Coverage boundaries

- Scrutiny, Grafana and Uptime Kuma are intentionally excluded from dedicated
  database exports. Other services' files may be in the application snapshot, but
  raw live databases do not have the exporter's consistency guarantees.
- Shared PostgreSQL discovers every non-template database. `productsearch` has
  database coverage; its external-repository application recovery dependencies
  have not been inventoried here.
- Obsidian's primary vault uses the separate **repos** source. Immich's original
  library and external photos must be recovered separately from its DB; confirm
  the relevant media-source coverage rather than assuming all external mounts
  are included in the application-volume source.
- Docker named volumes are not automatically captured by the bind-source
  snapshot. Immich's PostgreSQL named volume is covered by its logical export;
  its downloaded model cache is rebuildable. Original ignored secrets and image
  versions still need recoverable copies.
- B2 is the off-host repository. Local staging is not an independent backup.
  The NAS destination is unavailable after disk failure; independent on-site,
  WAN-free recovery remains unfinished. Verify the separate off-host `config/`
  copy and access to repository passwords, application secrets and unlock methods.
  Independent on-site recovery is a separate offline-resilience work item.

## Everyday operations

Run from the repository root on the Docker host. Replace the example target with
an entry from the table. `--host <name>` selects another host configuration;
the default is `config/docker/localhost`.

```bash
python3 scripts/backup/run.py tools/vaultwarden --dry-run
python3 scripts/backup/run.py tools/vaultwarden
python3 scripts/backup/run.py tools/vaultwarden --verify-latest
python3 scripts/backup/run.py --run-all
python3 scripts/backup/latest.py
python3 scripts/backup/run.py --prune-all --keep-local 7
```

`--verify-latest` validates the current local export's hashes and native format;
it does not prove remote coverage or a full application restore. `--prune-all`
verifies remote coverage even when fewer than seven exports exist. Only successful
coverage permits deletion, including Open WebUI model-revision pruning.

Preview/install the three managed cron entries as the backup user with Docker access:

```bash
python3 scripts/backup/schedule.py --time 00:05 --snapshot-time 01:15 --prune-time 03:00 --keep-local 7
python3 scripts/backup/schedule.py --time 00:05 --snapshot-time 01:15 --prune-time 03:00 --keep-local 7 --apply
```

Changing these values updates only this project's export/snapshot/prune entries; other jobs
are preserved. `--remove --apply` removes those entries. The prune job records
`--kopia-source /sources/local/db-backups` and
`--kopia-volumes-source /sources/local/docker-volumes`. Ensure exports finish
before the DB snapshot, and pruning starts after both snapshots complete.

### Migrate the existing whole-history DB source

Run as the non-root backup user on the Docker host, outside an active DB upload.
The commands below use the default host configuration; add `--host <name>` to the
host backup commands when needed.

1. Disable Kopia's automatic DB schedule and refresh the server:
   `python3 scripts/backup/kopia_schedule.py --apply`. Application scheduling and
   DB retention/ignores are still managed by `snapshots.yaml`.
2. Ensure fresh exports exist (`python3 scripts/backup/run.py --run-all`), then
   populate the private view: `python3 scripts/backup/latest.py --prepare-only`.
   Do this before recreating Kopia so Docker does not create a root-owned directory.
3. Recreate Kopia with the updated bind mount:
   `python3 scripts/labctl.py service recreate backup/kopia-b2`.
4. Run `python3 scripts/backup/latest.py`. The command checks that the running
   container actually mounts `DB_BACKUP_ROOT/latest` read-only at the DB source,
   refusing an old whole-history mount. Inspect the new snapshot: it should contain
   one timestamp directory per service. Restore a sample to a separate directory
   and verify its manifest hashes/native format.
5. Install the three host jobs with `python3 scripts/backup/schedule.py --apply`.
   Check coverage with the normal prune job after the application snapshot completes.

The source path and its existing snapshot history are preserved. Old snapshots
continue to contain multiple generations until their retention expires; exclusions
or the new mount do not rewrite them. Kopia still deduplicates shared content, but
new snapshots no longer repeatedly include the entire local history. During a
service outage, its last verified export can remain in new snapshots until a
valid replacement becomes available; its original timestamp and stale warnings
make that reduced freshness explicit.

### Snapshot policies and exclusions

Kopia-managed schedules and retention are declared in
[`snapshots.yaml`](../docker/backup/kopia-b2/snapshots.yaml):

```bash
python3 scripts/backup/kopia_schedule.py
python3 scripts/backup/kopia_schedule.py --apply
python3 scripts/backup/kopia_policy.py
python3 scripts/backup/kopia_policy.py --apply
```

Commands preview by default. The schedule command manages both active sources and
manual-only legacy sources, applies their source-specific ignores and refreshes
the running server. Its control address defaults to `http://127.0.0.1:80` inside
the container; override with `--server-address` when needed. The ignore-only command
targets `root@nest:/sources/local/docker-volumes`; use the schedule command's apply
afterward to refresh the running server immediately.

The active DB source is also manual-only, with managed retention and ignores. Its
01:15 host schedule is managed by `schedule.py --snapshot-time`, not Kopia's server.

The application policy combines all service `files.ignore` lists, including
disabled services with remaining volumes. YAML is authoritative: removing a
pattern removes its explicit policy rule on the next apply. Shared/legacy rules
live in [`docker/backup/backup.yaml`](../docker/backup/backup.yaml).

Live database files replaced by exports, disposable logs/caches and generated
media are excluded. Immich's native SQL archives stay local but are excluded from
B2 in favor of the checked exports. Open WebUI vector files and its pinned offline
model stay included. Overpass application data stays included; the legacy `/overpass`
rule is root-anchored. The DB source excludes incomplete staging and lock files,
and the volume source excludes `/db-backups`.

Kopia also reads `.kopiaignore` files and detects valid `CACHEDIR.TAG` markers.
Application policy rules do not apply to the separate DB source. Exclusions do
not delete local files or immediately remove data from retained snapshots.

### Troubleshooting coverage failures

Inspect `~/infra-db-backup.log`, source-host free space and both Kopia source
statuses. A failed export does not prevent attempts for the remaining services.
The latest-view job isolates service failures: healthy services are snapshotted,
stale or fallback exports are explicitly reported, and only services with no
verified recovery candidate are omitted. A **DEGRADED** exit after a completed
snapshot means a service needs attention, not that all backups stopped. Fix that
service's export problem and rerun `latest.py`; a busy service can retry after the
exporter finishes. Application-file snapshots run independently. Check that `latest/` is owned by the backup
user with mode `0700`, and that the container has been recreated with its new mount.
If snapshots are unavailable, stale or missing required paths, pruning fails and
older exports remain local. Check the configured paths, snapshot errors, export
timestamps and paired-file inventory before changing retention. An interrupted
MongoDB job can leave UniFi stopped; check its running state.

## General recovery

1. Select a completed export in `/sources/local/db-backups` and its required
   application state in `/sources/local/docker-volumes`. The verifier reports
   both snapshot IDs and end times. All declared paired paths must be present in
   one application snapshot; the eligible snapshots start after export publication.
2. Restore to a separate destination, verify artifact sizes/hashes against
   `manifest.json`, and check the native format. Use the appropriate application
   README above for destination paths, compatible images, ownership and secrets.
3. Recover the original host/Compose configuration, repository password and
   application keys. Database backups do not replace master passwords, recovery
   codes or independent unlock material. Restore identity before dependent SSO apps.
4. Stop the destination app while installing its DB and paired state. Use matching
   engine tools/images, restore required roles before databases, and follow the
   app's post-restore check before switching clients or enabling automation/sync.

Database exports and later file snapshots are **not a transactionally simultaneous
capture**. Missing attachment references, repository state or vector files can
require application-specific reconciliation. Authentik and Immich recovery needs
more than their DB exports; their manifests do not declare an exhaustive paired-file
inventory. A coverage check or native artifact restore is not proof of full app recovery.

Historical `/sources/nest/docker-volumes` and nested `db-backups` sources are
manual-only, with older snapshots still available. A historical whole-volume
snapshot stores exports beneath `db-backups/`; the new DB snapshot starts directly
with `<category>-<service>/`. Inspect the selected root when recovering old data.

## Application backup manifests

The first-release `version: 1` schema separates export settings from file coverage:

```yaml
version: 1
databases:
  engine: postgresql
  container: n8n-postgres
  database: n8n
  user: root
files:
  root: n8n
  required:
    - config
    - binaryData
  ignore:
    # Live storage is covered by the logical database export.
    - /n8n/postgres-data
```

- `databases` is one database/native exporter mapping, including engine-specific
  options such as `additional_databases`, `all_databases` and archive validation.
- `files.root` is relative to `DOCKER_VOLUMES`; `files.required` is relative to that
  root. Both keys must be specified together. Requirements verify paired coverage;
  they are not a whitelist of what Kopia snapshots.
- `files.offline_model` configures Open WebUI's pinned archive; its exact archive
  and manifest paths must also appear in `files.required`.
- `files.ignore` patterns are relative to the **whole application snapshot source**,
  not `files.root`. Quote globs and anchor specific roots with `/`. Kopia sorts
  policy patterns, so avoid order-dependent negation exceptions in these lists.

Files-only manifests omit `databases`; database-only exports may omit `files`.
Unknown fields, unsupported versions and the old flat layout are rejected.

## Implementation appendix

All code lives in [`scripts/backup/`](../scripts/backup/). Host paths/secrets stay in
ignored host configuration; service manifests contain non-secret export contracts.
The loader normalizes the sectioned schema without changing stored artifact formats.

| Module | Responsibility |
|---|---|
| `run.py`, `schedule.py` | Export/verify/prune CLI and three marked cron entries |
| `latest.py` | Checked hard-link view, mount verification and locked foreground DB snapshot |
| `config.py`, `common.py` | Definitions, safe host-path parsing, private staging, locks, hashes and atomic publication |
| `runner.py` | Adapter dispatch and latest-export validation |
| `kopia.py` | Complete/recent DB snapshot plus required application snapshot; coverage before any pruning |
| `kopia_policy.py`, `kopia_schedule.py` | Ignore reconciliation and source schedules/retention |
| `db/`, `apps/` | Engine-native exports and application-specific preparation |

Per-service `.incomplete-*` directories are published by atomic rename only after
validation. Failed staging is removed, and abandoned staging is cleaned under the
service lock on the next run. Nightly coverage requires complete snapshots with no
errors, started after publication and within the last 24 hours. Verification proves
remote **path presence**, not remote checksum equality; local checks and recovered
artifact validation remain separate.

SQLite uses its online backup API and produces standalone files without sidecars.
PostgreSQL uses matching clients, custom archives and roles; the shared instance
discovers every non-template DB, without a cross-database transaction. MongoDB
pauses/restarts its known standalone writer in cleanup. CouchDB is the supported
append-only live-copy exception, capturing indexes before shards/system files and
configuration with before/after inventory checks. Qdrant validates single-node
topology, collections/aliases, nested native payloads and inventory stability, and
removes only exporter-owned snapshots.

Open WebUI creates a deterministic, validated inference archive once per pinned
revision outside tagged caches, including model/license metadata. Model pruning
follows successful remote coverage and keeps three recent revisions plus every
revision referenced by a retained local DB export.

Unfinished work includes offline resilience and the
[B2 provider migration](plans/kopia-b2-s3-provider.md). Additional native
exporters, coverage/capacity alerts and broader RPO choices need separate decisions;
they are not implied by file-snapshot coverage or this documentation cleanup.
