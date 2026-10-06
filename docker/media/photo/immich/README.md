Immich is a high-performance self-hosted solution for backing up, organizing, and viewing photos and videos, with mobile clients, multi-user support, and local machine-learning search and recognition.

GPU acceleration intentionally disabled for Immich on this host.

Our host has an AMD Vega gfx90c iGPU. Immich's ROCm/MIGraphX ML image causes
GPU hangs and kernel resets that interrupt the desktop display. Immich issue
#21648 documents gfx90c APU support being removed from current ROCm images:
[rocm unsupported on gfx90c APUs · Issue #21648 · immich-app/immich](https://github.com/immich-app/immich/issues/21648)

GPU_COMPOSE_SUFFIX=amdgpu is shared by other services on this host, so retain
this no-op override to keep Immich on CPU until upstream support is verified.

Nightly database exports and B2 snapshots are configured. Independent on-site
recovery remains unfinished; confirm original-media coverage before relying on
the backup setup for full library recovery.

## References

- Home: [Immich](https://immich.app)
- Source: [GitHub - immich-app/immich: High performance self-hosted photo and video management solution.](https://github.com/immich-app/immich)
- Docs: [Docker Compose [Recommended] | Immich](https://immich.app/docs/install/docker-compose)
- Compose: [Immich Docker Compose file](https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml)

## Authentik

Immich uses native OIDC for Authentik's `media` group. OAuth settings are
persisted in Immich's database and must be configured through its web
administration interface. Keep an existing local Immich administrator and
password login for recovery.

### Host Configuration

Create `config/docker/<host>/immich/authentik-client-secret` with mode `0600`.
Set these values in ignored `config/docker/<host>/.env.immich`:

```dotenv
IMMICH_AUTHENTIK_CLIENT_ID=immich
IMMICH_AUTHENTIK_SIGNING_KEY=<asymmetric Authentik signing-key UUID>
```

Create the Authentik application:

```bash
scripts/authentik-apps.py --application immich --apply
```

### Immich Settings

Sign in as the local administrator and set **Administration > Settings > OAuth**:

| Setting                      | Value                                               |
| ---------------------------- | --------------------------------------------------- |
| Enabled                      | Enabled                                             |
| Issuer URL                   | `https://sso.<domain>/application/o/immich/`        |
| Client ID                    | `immich`                                            |
| Client secret                | Ignored host secret value                           |
| Token endpoint auth method   | `client_secret_post`                                |
| Scope                        | `openid email profile`                              |
| ID token signing algorithm   | `RS256`                                             |
| Userinfo signing algorithm   | `none`                                              |
| Storage label claim          | `preferred_username`                                |
| Auto register                | Enabled                                             |
| Auto launch                  | Disabled                                            |
| Mobile Redirect URI Override | `https://immich.<domain>/api/oauth/mobile-redirect` |

Leave role and quota claims unset so Authentik-created accounts remain ordinary
Immich users.

### Verify

Link an existing local account before making OIDC its normal login path. Test an
authorized `media` member, a non-member, local-password recovery, browser
logout, and mobile login/background uploads on every supported platform.

## Backup

`backup.yaml` defines nightly PostgreSQL exports under
`${DB_BACKUP_ROOT}/media-photo-immich/`, covering the named-volume DB
that Kopia's bind source cannot read directly. Restore using matching PostgreSQL
extensions/image, together with the photo library and external originals.
See the [backup guide](../../../../docs/backup.md) for commands, coverage,
retention and snapshot selection.

### Recovery

1. Recover `database.dump`, `globals.sql` and the manifest. Restore required
   roles and the Immich DB into a clean destination PostgreSQL named volume using
   compatible PostgreSQL/extensions and the matching application image. Keep
   Immich stopped until the database and media are ready.
2. Recover `${DOCKER_VOLUMES}/immich/library`, preserving `.immich` markers, and
   external originals from `${STORAGE_FAMILYMEDIA}` at their original mount paths.
   Check their own snapshot coverage; the DB verifier does not inventory all
   originals or external mounts. Restore original credentials/OIDC configuration.
3. Start the database and application, then validate original assets before
   regenerating missing thumbnails/encoded video.

Generated thumbs/encoded video and native `immich-db-backup-*.sql.gz` duplicates
are excluded from B2; use our checked logical exports for DB recovery. Native SQL
backups remain local. The named ML-model cache is not captured by the bind-source
snapshot and can be re-downloaded when available.

### Post-restore check

Start the matching PostgreSQL/extensions and app image with the restored library.
Sign in, open one original photo and one video, and confirm albums/asset counts
look reasonable. Verify one existing external-library path if used.
