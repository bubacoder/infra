Seamless multi-primary syncing database with an intuitive HTTP/JSON API, designed for reliability

Used by [Obsidian LiveSync](https://github.com/vrtmrz/obsidian-livesync)

## References

- Home: [Apache CouchDB](https://couchdb.apache.org)
- Source: [GitHub - apache/couchdb: Seamless multi-primary syncing database with an intuitive HTTP/JSON API, designed for reliability](https://github.com/apache/couchdb)

## Backup

`backup.yaml` uses CouchDB's supported append-only live-file backup each night,
copying indexes before shards/system DBs and runtime config into
`${DB_BACKUP_ROOT}/database-couchdb/`. Every staged file is checked
in B2 before local retention. Obsidian's vault uses the separate repos source.
See the [backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Retrieve the export's staged `couchdb/data/`, `couchdb/etc/` and manifest and
   verify every recorded hash. Keep shards, indexes and system metadata together;
   restoring only visible user database files is insufficient.
2. Stop the destination CouchDB. Install the staged data/configuration at the
   configured `/opt/couchdb/data` and `/opt/couchdb/etc/local.d` mounts, retaining
   node identity, expected ownership and original credentials. Use a compatible
   image matching the backup's deployed version.
3. Start CouchDB and check `_users`, `_replicator` and the expected user database
   inventory before reconnecting [Obsidian LiveSync](../../tools/obsidian/README.md#recovery).

CouchDB's append-only live-copy method is an engine-specific exception, not a
reason to copy arbitrary running databases. DB/config/vault captures are not one
global transaction; the vault's repos restore point must be selected separately.
