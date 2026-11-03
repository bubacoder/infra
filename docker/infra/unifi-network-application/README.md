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

## Kubernetes preparation

Docker keeps `MONGO_HOST=mongodb` by default. For separate Konverter projects,
explicitly supply `UNIFI_MONGO_HOST=mongodb.mongodb.svc` at the conversion input
boundary. MongoDB declares internal `expose: ["27017"]`; its `mongodb` ClusterIP
Service remains distinct from `mongodb-published`, which retains the existing
published port. The caller-owned labels grant only this controller's exact
namespace/app/workload identity TCP 27017 access in namespace `mongodb`.

`UNIFI_TRAEFIK_SERVERS_TRANSPORT` selects an existing reviewed transport reference;
its Docker default remains `insecureTransport@file`. Konverter preserves either
`name@file` or a same-namespace ServersTransport CRD name, but never creates the
definition or disables certificate verification. K3s Traefik bootstrap currently
excludes insecure file transports. Prefer a reviewed trusted-CA/certificate
configuration; providing an insecure compatibility transport requires a separate
bootstrap/security decision. Selecting a name alone does not make it available.

The published TCP/UDP ports remain unchanged alongside the HTTPS Traefik route
in LoadBalancer mode. Direct port 8443 access bypasses Traefik middleware. A
single-node Local traffic policy with an explicit LAN CIDR was tested with
synthetic traffic, not UniFi devices. UDP publication does not reproduce Docker
L2/broadcast discovery. Preserve the device-accessible inform address and port
8080; do not point real access points at an isolated test controller.

LinuxServer documents the Mongo connection variables as **first-run-only**.
Changing the input hostname does not safely rewrite an existing `/config` state
or migrate its database. Existing data/identity/credentials require a separate
backup/restore and configuration review. The shared MongoDB init directory has
only a placeholder, so the required UniFi account/roles are not provisioned by
the tracked source; use the existing reviewed provisioning procedure above.
Root credentials and ping readiness do not prove the UniFi account is usable.
Real secrets must be managed privately, never copied into regression fixtures.

No production stack, controller transport, Mongo user or adoption setting is
changed by these source preparations. Fresh synthetic startup/authentication and
database-backed readiness remain separate live checks before migration.

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
