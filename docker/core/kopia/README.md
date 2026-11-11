# Kopia

Encrypted, compressed and deduplicated backups with incremental snapshots and
client-side end-to-end encryption. This instance stores its repository in
**Backblaze B2** through Kopia's deprecated native `b2` provider. A directory or
container rename does not migrate that provider; see the separate
[S3-provider migration plan](../../../docs/plans/kopia-b2-s3-provider.md).

## Operations and recovery

The [backup and recovery guide](../../../docs/backup.md) is the source of truth
for coverage, export jobs, snapshot schedules, retention, manifest configuration,
restore procedures and verification. Application-specific recovery instructions
remain in each application's README.

Manage this stack as `core/kopia`:

```bash
scripts/labctl.py service logs core/kopia --tail 100
scripts/labctl.py service recreate core/kopia
docker exec kopia kopia server status --address=http://127.0.0.1:80
```

Before recreating the backup server, confirm there are no active uploads or
maintenance tasks and avoid scheduled backups. Never run two writable servers
against the same repository or create a new repository to fix a connection issue.

### Configuration and persistent identities

- Compose file: `docker/core/kopia/kopia.yaml`; container: `kopia`.
- Environment files: `config/docker/.env.kopia` and
  `config/docker/<host>/.env.kopia`, when present, after the common/host `.env`.
- Repository password variable: `KOPIA_B2_REPOSITORY_PASSWORD`; never print its
  resolved value or the credential-bearing `repository.config` file.
- Compose project/service, URL and Authentik application retain `kopia-b2` for
  compatibility. The UI remains `https://kopia-b2.${MYDOMAIN}/`.
- Data remains under `${DOCKER_VOLUMES}/kopia-b2/{config,cache,logs}`. Preserve the
  original repository connection, password and Kopia client hostname/username;
  snapshot source identities and schedules depend on them.
- [`snapshots.yaml`](snapshots.yaml) declares managed schedules and retention.
  [`backup.yaml`](backup.yaml) excludes this instance's disposable cache/logs.
  Cross-application rules remain in
  [`docker/backup/backup.yaml`](../../backup/backup.yaml).

The host backup scripts use the shared `DEFAULT_KOPIA_CONTAINER` setting in
`scripts/backup/common.py`; changing the container name must update that setting
alongside Compose.

## Authentik

Authentik ForwardAuth restricts browser access to the `admins` group. Kopia's
repository password remains separate from browser authentication. The isolated
`backup-kopia` network and Traefik are the only intended UI path.

For explicit SSO onboarding, separate from ordinary container operations:

```bash
scripts/authentik-apps.py --application kopia-b2 --apply
```

Keep the router middleware as `localaccess-authentik@file`, Traefik connected to
`backup-kopia`, and no Kopia UI host port published. This stack listens on port
`80` internally, not Kopia's upstream default `51515`. Its server flags disable
native browser authentication: never expose this API directly or add unrelated
containers to its network to bypass ForwardAuth.

Confirm an `admins` member can use the UI, a non-member is denied, group removal
applies after session refresh, recovery works, and no direct host path reaches
the UI.

## References

- Home: [Kopia](https://kopia.io/)
- Source: [kopia/kopia](https://github.com/kopia/kopia)
- Docker: [Kopia container tooling](https://github.com/kopia/kopia/tree/master/tools/docker)
