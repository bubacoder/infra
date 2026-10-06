MongoDB is a source-available, document-oriented NoSQL database designed for scalability and
developer agility, storing data as flexible, JSON-like documents rather than rows and columns.

This is a shared instance, following the same pattern as postgresql/couchdb in this category.
Mongo's /docker-entrypoint-initdb.d scripts only run once, on first startup with an empty data
directory — each consuming service should add its own init script under ./config/initdb when it
first starts using this instance. A service added *after* this instance already has data must
create its user/db manually via `mongosh` instead, since init scripts won't re-run.

TODO: Add a mongo-express (or similar) admin UI service if a web GUI is wanted

## References

- Home: [MongoDB: The World’s Leading Modern Data Platform | MongoDB](https://www.mongodb.com)
- Source: [GitHub - docker-library/mongo: Docker Official Image packaging for MongoDB](https://github.com/docker-library/mongo)
- Docs: [mongo - Official Image | Docker Hub](https://hub.docker.com/_/mongo)

## Backup

`backup.yaml` creates nightly full-instance `mongodump --archive --gzip` exports
under `${DB_BACKUP_ROOT}/database-mongodb/`. The standalone server's
known writer, UniFi, is briefly stopped and restarted even on failure. Restore
all databases/users with paired UniFi config and original credentials.
See the [backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Recover `database.archive.gz` and its manifest; verify the hash and compressed
   payload before restoring into a compatible MongoDB destination.
2. Keep application writers stopped and use `mongorestore` with `--archive` and
   `--gzip` to recover the full-instance databases/users/roles with original
   credentials. Start MongoDB before the controller.
3. Restore [UniFi's paired configuration](../../infra/unifi-network-application/README.md#recovery)
   and controller settings before reconnecting devices.

Standalone MongoDB has no `--oplog` capture. Consistency assumes UniFi is the only
writer; reassess that assumption when adding consumers. Normal cleanup restarts
UniFi, but a killed job or host interruption can bypass it: check/start UniFi
manually if it remains stopped.
