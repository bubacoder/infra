PostgreSQL is a powerful, open source object-relational database system with over
35 years of active development that has earned it a strong reputation for
reliability, feature robustness, and performance.

## TODO

TODO: Add PgBouncer container for connection pooling
TODO: Add PostgreSQL exporter for Prometheus monitoring
TODO: Consider enabling SSL/TLS for encrypted connections
TODO: Set up streaming replication for high availability

## References

- Home: [PostgreSQL: The world's most advanced open source database](https://www.postgresql.org/)
- Source: [GitHub - docker-library/postgres: Docker Official Image packaging for Postgres](https://github.com/docker-library/postgres)
- Docs: [postgres - Official Image | Docker Hub](https://hub.docker.com/_/postgres)

## Backup

The host-side `backup.yaml` target exports **all** non-template databases and
cluster roles to `${DB_BACKUP_ROOT}/database-postgresql/`. On this
host, it currently discovers `mattermost`, `postgres` and `productsearch`.
The daily job includes this target; restore roles and required databases with a
compatible PostgreSQL version and paired application files (including Mattermost).
See the [backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Recover `globals.sql`, `database-<name>.dump` archives and the manifest's DB
   inventory. Globals contain password hashes and require private handling.
2. Use a compatible PostgreSQL destination/client (matching the deployed major
   version). Restore required roles first, recreate the selected databases with
   original ownership, then apply their matching custom archives using `pg_restore`.
3. Restore each application's paired files and original credentials before
   allowing it to connect. Follow [Mattermost recovery](../../communication/mattermost/README.md#recovery)
   for its configuration, uploads and plugins, then check database access and app health.

Separate database dumps are not one cross-database transaction. `productsearch`
has DB coverage only; its separate repository's application recovery dependencies
have not been inventoried by this backup setup.
