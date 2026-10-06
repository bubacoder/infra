
A powerful knowledge base that works on top of a local folder of plain text Markdown files.
Obsidian is a free and flexible app for your private thoughts that stores notes locally
with extensive plugin support and open file formats.

TODO: Consider GPU acceleration configuration if needed for advanced use cases

## References

- Home: [Obsidian - Sharpen your thinking](https://obsidian.md)
- Source: [Obsidian.md](https://github.com/obsidianmd)
- Docs: [obsidian - LinuxServer.io](https://docs.linuxserver.io/images/docker-obsidian/)

## Authentik

Authentik ForwardAuth limits access to the browser-hosted Obsidian desktop to
the `admins` group. All admitted users share the same desktop, vault, terminal,
and container privileges; it is not a multi-user authorization boundary.

### Setup

```bash
scripts/authentik-apps.py --application obsidian --apply
scripts/labctl.py service recreate tools/obsidian
```

Keep `localaccess-authentik@file` on the router and the UI port private to
Traefik. `OBSIDIAN_CUSTOM_USER` and `OBSIDIAN_PASSWORD` provide a temporary
native recovery path when configured through ignored host values.

### Verify

Confirm authorized access, non-member denial, logout, session-refresh group
revocation, local recovery, and absence of a direct browser route.

## Backup

The vault bind mount lives under `${ADMIN_HOME}/repos/today/vault`, not
`${DOCKER_VOLUMES}`. Kopia B2's **repos** source contains `today/vault`; CouchDB
LiveSync is protected by the separate CouchDB export and Docker-volumes
snapshot on a different schedule. Preserve the original sync/encryption settings.
See the [backup guide](../../../docs/backup.md) for coverage, retention and snapshot selection.

### Recovery

1. Restore the primary `today/vault` tree from the repos snapshot, including notes,
   attachments and `.obsidian` settings; synchronization is not its backup.
2. Follow [CouchDB recovery](../../database/couchdb/README.md#recovery) for LiveSync's
   databases. Select nearby vault/DB restore points and record both timestamps;
   the two sources are not captured as one transaction.
3. Recover original LiveSync credentials, encryption settings and container/desktop
   configuration. Open the recovered vault before enabling sync; keep a test client
   disconnected from the production database to avoid propagating empty state.

### Post-restore check

Open the restored vault and one known note/attachment before enabling LiveSync.
Verify the restored CouchDB databases and original sync/encryption settings;
avoid synchronizing an empty test vault into the working database.
