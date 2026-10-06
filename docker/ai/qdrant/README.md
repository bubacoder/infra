Qdrant - High-performance, massive-scale Vector Database and Vector Search Engine for the next generation of AI.

Some Dashboard Quickstart examples use incorrect endpoint URLs. Remove the
`dashboard/` path prefix when following the tutorial. See the
[reported issue](https://github.com/qdrant/qdrant-web-ui/issues/252).

## Collections

Qdrant calls its independent vector stores **collections**, rather than databases.
Collection configurations and aliases are discovered at backup time rather than
maintained as a fixed inventory in this README.

Clients can access this instance through `qdrant:6333`. Open WebUI uses Chroma,
not these collections.

## Storage

- Compose definition: [`qdrant.yaml`](qdrant.yaml).
- Declared bind: `${DOCKER_VOLUMES}/qdrant/storage:/qdrant/storage`.
- Collections are stored under `storage/collections/<collection-name>/`.

## References

- Home: https://qdrant.tech/
- Source: [GitHub - qdrant/qdrant: Qdrant - High-performance, massive-scale Vector Database and Vector Search Engine for the next generation of AI. Also available in the cloud https://cloud.qdrant.io/](https://github.com/qdrant/qdrant)

## Backup

### Backup coverage

`backup.yaml` enables native full-storage snapshots of the single-node instance,
including **all collections and aliases**. `scripts/backup/db/qdrant.py`
discovers the inventory dynamically, with no collection allowlist; newly created
collections are included automatically in the next successful export. It
publishes private `full.snapshot`,
`inventory.json` and checksum manifest under
`${DB_BACKUP_ROOT}/ai-qdrant/<UTC run>/`. The existing 00:05 export
and 03:00 B2-gated seven-local-export retention jobs automatically include it.
Kopia snapshots the database-export source at 01:15 and application volumes at 01:20.
See the [backup guide](../../../docs/backup.md) for shared scheduling, retention
and snapshot-selection procedures.

```bash
python3 scripts/backup/run.py ai/qdrant --dry-run
python3 scripts/backup/run.py ai/qdrant
python3 scripts/backup/run.py ai/qdrant --verify-latest
```

The adapter gets the API key from the running container without logging it or
placing it in command arguments. It requires cluster-disabled mode, records
version/collection configurations/counts/aliases, checks native size/SHA-256,
reads every nested tar payload without extraction, and rejects inventory drift
during capture. It does not stop Qdrant or its clients. Full snapshots are not a
transaction with external source documents; matching before/after counts do not
prove that no same-count payload updates occurred.

Only the newly returned full snapshot and confirmed exporter-owned intermediates
are removed; operator snapshots are preserved. v1.19.1 removes collection
intermediates automatically. If a request is interrupted before returning an
owned snapshot name, inspect server snapshot inventory before deleting anything;
the adapter does not guess ownership of unrelated artifacts.

### Recovery and post-restore check

Retrieve the native artifact, inventory and manifest from the same B2 root;
verify hashes/structure before use. Restore into empty **destination** storage
using the matching `qdrant/qdrant:v1.19.1` image and startup command:

```text
./qdrant --storage-snapshot /restore/full.snapshot
```

Mount the snapshot read-only at `/restore/full.snapshot` and empty destination
storage at `/qdrant/storage`. Restore the original ignored API key and Compose
settings separately; the native snapshot is not a copy of container credentials.
Preserve client applications' source documents, embedding/chunking settings and model
assets separately if regeneration is required. Before switching clients, compare
collections/configurations/counts/aliases with `inventory.json`, confirm each alias
points to its expected collection, and test a representative retrieval.
Use an isolated destination for a drill, never production storage.
