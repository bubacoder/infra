# Jellyseerr to Seerr configuration migration

## Scope

Replace `arr/jellyseerr` with `arr/seerr`. This is a **configuration-only
migration with a fresh Seerr instance**: no existing application data, databases,
users, requests or settings need importing. Do not copy or rename the old
Jellyseerr data directory, run database conversion tools, or delete old data.

Seerr is the maintained successor to Jellyseerr and Overseerr. Use the official
image, existing external `proxy` network and local-only Traefik access pattern.
Implementation and deployment are separate: this plan does not authorize live
container changes.

## Implementation

1. Replace `docker/arr/jellyseerr/` with `docker/arr/seerr/`, including the base
   Compose file, service README and backup declaration. Update the Arr index and
   tracked service examples. Keep the old deployment definition available in
   version control for recovery.
2. Select a reviewed stable `seerr/seerr:<version>@sha256:<digest>` from the
   upstream-published Docker Hub image. Resolve and verify the digest and target
   architecture before writing the Compose file; do not use `latest`, a floating
   major tag or an unverified placeholder digest. Follow the repository's
   [image review policy](../../docker/README.md#container-update-safety).
3. Configure the service as follows:

   | Setting | Value |
   | --- | --- |
   | Compose project / service / container | `seerr` |
   | Process init | `init: true` (required by the official image) |
   | Restart policy | `unless-stopped` |
   | Timezone | `TZ: ${TIMEZONE}` |
   | Log level | `LOG_LEVEL: info` |
   | Config mount | `${DOCKER_VOLUMES}/seerr:/app/config` |
   | Network | Existing external `proxy` |
   | Container HTTP port | `5055`, without a published host port |
   | Traefik hostname | `seerr.${MYDOMAIN}` |
   | Middleware | `localaccess@file` |
   | Homepage | Group `Arr`, name `Seerr`, URL `https://seerr.${MYDOMAIN}/` |

   Use an explicit Traefik host rule and service port label. Add the upstream
   healthcheck for `http://localhost:5055/api/v1/settings/public`, with a startup
   grace period. Keep the image's default non-root `node` user; do not add
   unsupported `PUID`/`PGID` settings or run it as root. Apply upstream-compatible
   `no-new-privileges` and dropped-capability settings.
4. Give UID/GID `1000:1000` write access to the **new, exact** Seerr config
   directory before starting. Inspect ownership first; do not recursively change
   ownership of `${DOCKER_VOLUMES}` or the old Jellyseerr directory.
5. Rename only the intended host registration from `arr/jellyseerr` to
   `arr/seerr`, preserving its existing `down` state unless deployment is
   separately approved. Inspect any service-specific environment overrides
   privately and carry over only settings still needed under `.env.seerr`.
   Do not print secrets or invent credentials for this fresh installation.
6. Update the backup log exclusion from `/jellyseerr/logs` to `/seerr/logs`.
   Keep the new config/database covered by the existing file-backup system;
   review/regenerate backup policy through the [backup guide](../backup.md).
   Do not prune retained Jellyseerr snapshots.

## Validation and deployment

- Validate YAML, the host service schema, and Compose with interpolation/env-file
  resolution disabled, without reading private environment values into output.
- Confirm old tracked service identifiers are removed except explanatory docs,
  and check updated Compose labels, backup paths and environment references.
- Before deployment, select the host and Docker context, confirm the original
  service state, verify DNS/TLS routing for the new hostname, and obtain approval.
- If an old Jellyseerr container exists, stop it using the existing definition
  before removing that definition from the deployed checkout. Do not use
  `down --volumes`, delete data, or assume that renaming a Compose project removes
  its old container.
- Start only `arr/seerr` through the documented service workflow. Verify health,
  local-only access, Homepage navigation, login/onboarding and restart persistence.
- Set up the fresh instance's media server, libraries and any Radarr/Sonarr
  connections through its onboarding/admin UI. This is new configuration, not
  an import of old Jellyseerr state. Verify a test request if those integrations
  are configured. Do not add Authentik SSO as part of this rename.

## Recovery

If validation fails, stop only the new Seerr service and preserve its config for
diagnosis. Restore the prior deployment definitions and original registration
state from the reviewed change if needed. The old Jellyseerr data and retained
backups remain untouched; never point an older image at a database modified by
a newer application.

## References

- [Seerr release announcement](https://docs.seerr.dev/blog/seerr-release)
- [Upstream migration guide](https://docs.seerr.dev/migration-guide)
- [Official Docker configuration](https://docs.seerr.dev/getting-started/docker)
- [Official Docker Hub image](https://hub.docker.com/r/seerr/seerr)
- [Releases](https://github.com/seerr-team/seerr/releases)
