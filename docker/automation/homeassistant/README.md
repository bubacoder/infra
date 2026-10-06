Home Assistant Core - Open source home automation that puts local control and privacy first. Powered by a worldwide community of tinkerers and DIY enthusiasts. Perfect to run on a Raspberry Pi or a local server.

Home Assistant needs to set up to allow the Traefik reverse proxy (details: [HTTP - Home Assistant](https://www.home-assistant.io/integrations/http/))
For this, add to `${DOCKER_VOLUMES}/homeassistant/configuration.yaml`:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12  # All Docker bridge networks
```

## References

- [Home Assistant](https://www.home-assistant.io/)
- [linuxserver/homeassistant - Docker Image](https://hub.docker.com/r/linuxserver/homeassistant)
- [HTTP - Home Assistant](https://www.home-assistant.io/integrations/http/)

## Backup

`backup.yaml` creates native `backup.create` backups of this Container
installation's full configuration, `.storage`, automations/secrets/custom
components and recorder state, plus a standalone SQLite export under
`${DB_BACKUP_ROOT}/automation-homeassistant/`. Provision an
administrator token in the ignored `homeassistant/backup-token` file (mode
`0600`) before running the backup.
See the [backup guide](../../../docs/backup.md) for scheduling, retention and snapshot selection.

### Obtain and save the administrator token

1. Sign in to Home Assistant with an **administrator** account.
2. Open your user profile (bottom of the sidebar), then the **Security** tab.
3. Under **Long-lived access tokens**, select **Create token** and name it
   `Homelab native backups`.
4. Copy the generated token immediately: it is shown only once. Save it on the
   Docker host, never in chat, tracked files or a shell command argument.

Run as the non-root backup user (`buba` on this host), without `sudo`. The private
parent directory must already exist and be owned by that user with mode `0700`.
This hidden prompt saves mode `0600` and refuses to overwrite an existing token:

```bash
python3 - <<'PY'
import getpass
import os
from pathlib import Path

path = Path("/home/buba/repos/infra/config/docker/localhost/homeassistant/backup-token")
token = getpass.getpass("Paste Home Assistant token (hidden): ").strip()
if not token or any(character.isspace() for character in token):
    raise SystemExit("Token is empty or contains whitespace.")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    output.write(token + "\n")
print("Token saved privately.")
PY
```

Saving the file automatically includes Home Assistant in both existing cron
jobs; no cron reinstall is needed. For token rotation, provision and validate
the replacement privately before revoking the old token in the same profile page.
References: [token creation](https://developers.home-assistant.io/docs/auth_api/#long-lived-access-token),
[native backup action](https://www.home-assistant.io/actions/backup.create/).

Validate activation or a rotated token with:

```bash
python3 scripts/backup/run.py automation/homeassistant
python3 scripts/backup/run.py automation/homeassistant --verify-latest
```

Once an export directory exists, missing credentials report failure instead of
silently disabling the target. Only the exporter-created native duplicate is
removed after publication; pre-existing UI backups remain.

### Recovery

Recover `homeassistant.tar`, `database.sqlite3` and their checksum manifest. The
native archive includes `.storage` accounts/credentials/device/entity state,
YAML/secrets/automations, custom components and recorder DB/WAL. It is unencrypted
locally, protected by private staging and Kopia repository encryption; this
adapter's archive does not require a separate HA backup emergency key.

Use onboarding **Upload backup** with a compatible image. For manual Container
recovery, stop the destination, unpack the native archive's
`homeassistant.tar.gz`, and restore its `data/` contents into `/config`. Preserve
ownership and the matching recorder DB/WAL. If installing the separate standalone
SQLite export as `home-assistant_v2.db`, discard stale destination WAL/SHM instead.
Recover original host/Compose settings and keep restored automations isolated from
production devices until ready.

### Post-restore check

After an actual restore, sign in with the existing account, confirm expected
devices/entities and automations, inspect recorder history, and test one harmless
local action.
