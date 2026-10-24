Crowdsec - An open-source, lightweight agent to detect and respond to bad behaviours.

Register to dashboard, subscribe to blocklists: [Safer Together - CrowdSec Console](https://app.crowdsec.net/)  
Configure the host firewall bouncer with
`ansible/roles/debian_base/tasks/50-crowdsec.yaml`. The detection engine runs in
Docker; the firewall bouncer runs as a host systemd service.
The published LAPI port binds only to `127.0.0.1:7080` for the host bouncer;
Traefik connects directly to `crowdsec:8080` over the Docker network.

## Enforcement

- Set `CROWDSEC_ENABLED=true` in the host's ignored Traefik environment file and
  recreate only `security/traefik` to enable the `publicaccess` middleware bouncer.
  Keep its API key private. Private-only routes retain their IP allowlist policy.
- Enable `debian_base_install_crowdsec_bouncer` in the target host's inventory.
  Use a dedicated registered bouncer key, not the Traefik key. Supply it using
  `debian_base_crowdsec_local_api_key_file` (a controller-side `0600` file) or the
  existing secret variable `debian_base_crowdsec_local_api_key`.
- On Docker hosts, set `debian_base_crowdsec_iptables_chains` to `INPUT` and
  `DOCKER-USER`. The managed `.yaml.local` override enables both IPv4 and IPv6;
  systemd ordering starts Docker before the firewall bouncer.

Docker-host enforcement is deliberately separate from base host provisioning:
the base role runs before Docker installation and before application containers
are deployed. It leaves existing enforcement unchanged and prints a reminder to
run the targeted playbook. Hosts using only `INPUT` retain base-role configuration.

After provisioning Docker, deploying CrowdSec, and registering the dedicated
bouncer key, apply only this component, without other host-role changes:

```bash
ANSIBLE_ROLES_PATH=ansible/roles ansible-playbook ansible/playbooks/crowdsec.yaml \
  -i ansible/inventory/inventory.yaml \
  -i config/ansible/inventory/inventory.yaml --limit colony
```

Activation checks that Docker is running and its IPv4 `DOCKER-USER` chain exists
when requested, then waits for the configured LAPI's `/health` endpoint before
installing or changing the bouncer. The first service start reloads systemd so
the Docker ordering drop-in is effective immediately. These checks do not replace
the post-activation enforcement tests below.

Before activation, verify management IPs are not banned and arrange a timed
rollback. After activation, check bouncer API pulls, populated IPv4/IPv6 sets,
`INPUT`/`DOCKER-USER` hooks, and an isolated temporary-ban test. A running engine
and a list of decisions alone do not prove enforcement. Do not test by banning
the administrative source IP.

## Bouncer credential maintenance

Use separate parent credentials for Traefik (`colony-traefik`) and the host
firewall (`colony-firewall`). Traefik's key is stored privately in the host's
Traefik environment file; keep the controller copy under ignored
`config/docker/colony/traefik/crowdsec-bouncer-api-key` with mode `0600`.

CrowdSec automatically creates `parent@IP` identities when a shared key is used
from another address. These are not independent keys. In CrowdSec 1.8.1,
`cscli bouncers delete` refuses to delete an auto-created identity individually;
deleting the parent removes its key and all child identities. Do not use a
blanket age-based prune: an active shared key's parent can have an old last-pull
timestamp while its current child is active.

For supported cleanup, back up the database, register a new dedicated parent
key, update only the intended consumer, and verify fresh API pulls plus a
controlled ban/unban test. Only then delete the old parent. Preserve other
consumers' credentials and private recovery backups. Never delete database rows
directly to bypass the CLI's parent/child safety checks.

## Reliability and detection checks

`USE_WAL=true` enables SQLite write-ahead logging for the local database. Keep
the data volume on local storage that supports SQLite shared-memory locking;
do not move a WAL database to NFS/SMB. Take a consistent database backup before
changing database settings.

The Traefik bouncer uses stream mode with a 60-second sync interval. Initial
sync is synchronous (`StreamStartupBlock=true`), and a failed sync marks the
stream unhealthy immediately (`UpdateMaxFailure=0`), blocking public requests
until sync recovers. This deliberately favors security over availability.
The host firewall bouncer independently syncs its kernel sets.

Application parsers recognize selected security events, not every log line.
Unparsed routine Authentik/Jellyfin/SSH messages are not by themselves failures.
Vaultwarden logs at `warn`, so an unchanged log can be normal when no warnings
or authentication failures occur. Verify log paths and open file descriptors
before changing logging verbosity or parsers.

Use `cscli explain --log '<synthetic event>' --type <source-type>` inside the
CrowdSec container to validate parser and scenario selection without producing
real failed logins or injecting events into the running acquisition pipeline.
Use documentation-only addresses and fake usernames; never paste real tokens
or authentication logs into the command line or chat.

Useful commands - execute within the container like `docker exec crowdsec <command>`:
- `cscli collections list`
- `cscli bouncers list`
- `cscli decisions list`
- `cscli alerts list`
- `cscli metrics`

## References

- Home: [Curated Threat Intelligence Powered by the Crowd | CrowdSec](https://www.crowdsec.net/)
- Image: [crowdsecurity/crowdsec - Docker Image](https://hub.docker.com/r/crowdsecurity/crowdsec)
- Source: [GitHub - crowdsecurity/example-docker-compose: Example integration of crowdsec in docker-compose](https://github.com/crowdsecurity/example-docker-compose)
- Tutorial: https://docs.ibracorp.io/crowdsec/
