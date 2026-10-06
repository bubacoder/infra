
Gitea is a lightweight, open-source self-hosted Git service.
It's a community-managed fork of Gogs with enhanced features focused on Git management and CI/CD integration.

Installation:
The following commands will output a new SECRET_KEY and INTERNAL_TOKEN to stdout, which you can then place in your environment variables.

```sh
docker run -it --rm docker.gitea.com/gitea:1 gitea generate secret SECRET_KEY
docker run -it --rm docker.gitea.com/gitea:1 gitea generate secret INTERNAL_TOKEN
```

Do not lose/change your SECRET_KEY after the installation, otherwise the encrypted data can not be decrypted anymore.

## TODO

TODO: Generate SECRET_KEY and INTERNAL_TOKEN for enhanced security
TODO: Consider switching to PostgreSQL for improved performance with large repositories

## References

- Home: [Gitea Official Website](https://about.gitea.com/)
- Source: [GitHub - go-gitea/gitea: Git with a cup of tea! Painless self-hosted all-in-one software development service, including Git hosting, code review, team collaboration, package registry and CI/CD](https://github.com/go-gitea/gitea)
- Docs: [Installation with Docker | Gitea Documentation](https://docs.gitea.com/installation/install-with-docker)

## Authentik

Gitea uses native OIDC for Authentik's `developers` group. Browser SSO does not
replace Git-over-SSH keys, Git HTTPS personal access tokens, or runner tokens.
Keep a local Gitea administrator for recovery.

### Setup

Create the ignored secret file at
`config/docker/<host>/gitea/authentik-client-secret` with mode `0600`. Set
`GITEA_AUTHENTIK_CLIENT_ID`, `GITEA_AUTHENTIK_CLIENT_SECRET`, and
`GITEA_AUTHENTIK_SIGNING_KEY` in the ignored host `.env` file. The signing key
is an asymmetric Authentik certificate/key UUID.

Create the Authentik resources, recreate Gitea, then configure its persisted
authentication source:

```bash
scripts/authentik-apps.py --application gitea --apply
scripts/labctl.py service recreate dev/gitea
docker/dev/gitea/gitea-auth.py --host <host> --apply
```

Run the last command again after changing OIDC client settings. Keep the
registered callback URI exact:
`https://gitea.<domain>/user/oauth2/authentik/callback`.

### Verify

Confirm a `developers` member can sign in, a non-member is denied by Authentik,
an existing account links only through the intended flow, and local
administrator, Git SSH, and PAT workflows remain usable.

## Backup

`backup.yaml` exports SQLite online each night under
`${DB_BACKUP_ROOT}/dev-gitea/`. Pair the DB with `/data/git`,
`/data/gitea` and `/data/ssh` from the verified application B2 snapshot, including repositories,
LFS, attachments, SSH keys and the original app.ini/secret key.
See the [backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Retrieve `database.sqlite3` and its manifest plus the paired repositories, LFS,
   attachments, action artifacts, avatars, packages, JWT/SSH state and `app.ini`.
   The database alone is not a repository backup.
2. Stop the destination and install the standalone export as
   `/data/gitea/gitea.db`, removing stale destination WAL/SHM. Restore paired
   `/data/git`, `/data/gitea` and `/data/ssh` files with the expected ownership.
3. Recover original `GITEA_SECRET_KEY`, `GITEA_INTERNAL_TOKEN`, OIDC secret and
   persisted configuration; do not generate fresh installation secrets. Start
   the matching image before testing access.

DB/repository capture is not atomic; check refs, LFS and attachment references.
Keep runners, webhooks and outbound notifications disconnected on a test restore.

### Post-restore check

Restore the original config/secret key and paired repositories with the DB. Sign
in, browse a known commit, and clone one repository using an existing SSH key or
PAT. Check one LFS object if used.
