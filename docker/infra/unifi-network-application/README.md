UniFi Network Application is a powerful, enterprise wireless software engine ideal for high-density client deployments requiring low latency and high uptime performance.

For Unifi to adopt other devices, e.g. an Access Point, it is required to change the *inform* IP address.
Because Unifi runs inside Docker by default it uses an IP address not accessible by other devices.
To change this go to Settings > System Settings > Controller Configuration and set the Controller Hostname/IP to a hostname or IP address accessible by your devices.

For the Homepage widget use a local account that has read privileges.
Local account can be created on the Legacy Interface:
- To temporally switch to the old interface: Settings -> System -> Legacy Interface -> Enable
- Create the user on Settings -> Admins
- Set the `${UNIFI_LOCAL_VIEWONLY_USERNAME}` and `${UNIFI_LOCAL_VIEWONLY_PASSWORD}` variables

This service no longer bundles its own database — it connects to the shared `mongodb` service
in `docker/database/mongodb`. That stack must be running before this one starts.

MIGRATION: Migrated from the deprecated linuxserver/unifi-controller image (8.0.24). In-place upgrade
is not supported — this must be a fresh install restored from a backup of the old instance.
Before first start, create the Mongo user on the shared instance (per LinuxServer's documented
init script):
  docker exec -it mongodb mongosh -u root -p "$MONGO_ROOT_PASSWORD" --eval '
    db.getSiblingDB("admin").createUser({
      user: "<UNIFI_MONGO_USERNAME value>", pwd: "<UNIFI_MONGO_PASSWORD value>",
      roles: [
        "clusterMonitor",
        {role:"dbOwner", db:"<UNIFI_MONGO_DBNAME value>"},
        {role:"dbOwner", db:"<UNIFI_MONGO_DBNAME value>_stat"},
        {role:"dbOwner", db:"<UNIFI_MONGO_DBNAME value>_audit"},
        {role:"dbOwner", db:"<UNIFI_MONGO_DBNAME value>_restore"}
     ]
    })'
Must be created against `admin` (not `unifi`) to match MONGO_AUTHSOURCE=admin below, and needs
more than just the main db (`_stat`, `_audit`, `_restore`, `clusterMonitor` too)
The databases themselves don't need to pre-exist — Mongo creates them lazily on first write.

## References

- Home: [Software Downloads - Ubiquiti](https://ui.com/download/releases/network-server)
- Image: [GitHub - linuxserver/docker-unifi-network-application](https://github.com/linuxserver/docker-unifi-network-application)

## Backup

The shared MongoDB backup job briefly stops and restarts UniFi to get a
consistent standalone database export. Restore it with this application's
`/config` data from the paired B2 application-volume snapshot and the original MongoDB
credentials/controller settings. See the [backup guide](../../../docs/backup.md)
for commands, retention and snapshot selection.

### Recovery

1. Keep the destination controller stopped and follow
   [MongoDB recovery](../../database/mongodb/README.md#recovery) for the full-instance
   `database.archive.gz`, including original databases/users/roles and credentials.
2. Restore `${DOCKER_VOLUMES}/unifi-network-application/data` and other required
   `/config` state from the paired application snapshot, preserving controller
   identity, keystore/certificates, ownership and original host configuration.
3. Start MongoDB before the matching controller image. Preserve the controller
   hostname/inform path; a test restore must not take over production adoption.

The exporter assumes UniFi is MongoDB's only writer. It normally restarts the
paused controller on failure; after a killed job/host interruption, check whether
UniFi needs to be started manually.

### Post-restore check

Restore shared MongoDB and paired UniFi config first. Sign in with the existing
local administrator and confirm sites, networks and adopted devices. Keep a
test restore off the production controller/inform path; after actual recovery,
verify one device reconnects without re-adoption.
