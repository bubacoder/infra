## Base information for MongoDB application

Application name: MongoDB
Homepage: https://www.mongodb.com
GitHub page: https://github.com/docker-library/mongo
Install instructions URL: https://hub.docker.com/_/mongo
Category: database
Dashboard Icon: mongodb.png
Dashboard Group: Storage
Short description: Popular NoSQL document database
Long description: MongoDB is a source-available, document-oriented NoSQL database designed for scalability and developer agility, storing data as flexible, JSON-like documents rather than rows and columns.

## Container deployment

### Compose example (from Docker Hub `_/mongo`)

```yaml
services:
  mongo:
    image: mongo
    restart: always
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: example
    volumes:
      - /my/own/datadir:/data/db
    ports:
      - 27017:27017
```

(`mongo-express` admin UI is offered in the official example too, but is not required — skip it
unless a web admin UI is wanted later.)

### Environment variables

- `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD` — creates the root user on first
  boot. Must be treated as secrets (host `.env`, not example `.env`).
- `MONGO_INITDB_DATABASE` — optional, names the database that init scripts in
  `/docker-entrypoint-initdb.d/` operate against.

### Volumes

- `/data/db` — database data storage (persistent).
- `/data/configdb` — only relevant with `--configsvr` (sharding), not needed here.

### Init scripts (`/docker-entrypoint-initdb.d`)

Any `.sh`/`.js` files mounted here run **once**, only on first startup when `/data/db` is empty.
This instance is intended to be a **shared** Mongo server (same pattern as
`docker/database/postgresql` and `docker/database/couchdb` in this repo) — the first consuming
application is `unifi-network-application`, which needs its own non-root user + `unifi`/`unifi_stat`
databases created via RBAC. Since this is a brand-new instance, it's fine to mount that app's
init script (creating the `unifi` user with `dbOwner` on `unifi`/`unifi_stat`, per LinuxServer's
`docker-unifi-network-application` README) as part of this initial deployment. **Any future
service** that wants to reuse this same Mongo instance will need its db/user created manually via
`mongosh` after the fact, since init scripts won't re-run against existing data — call this out in
the compose file's header comment as a TODO/note for future maintainers.

### Security considerations

- By default Mongo requires no authentication — root credentials **must** be set via
  `MONGO_INITDB_ROOT_USERNAME`/`_PASSWORD` env vars (real secrets, host-specific `.env`).
  Enable RBAC/auth from the start rather than relaxing it later.
- Do not expose port 27017 to the internet/reverse proxy; if published, keep it local-network-only
  (no Traefik router — same as `postgresql.yaml`'s `traefik.enable: false`). Other containers reach
  it over the shared `proxy` docker network by container name (`mongodb`), not via the published
  port.

### AMD GPU acceleration

None — MongoDB has no GPU acceleration support (not applicable to a database engine).

### Possible further improvements

- Add a `mongo-express` or similar admin UI service later if a web GUI is wanted (mirrors the
  `adminer` service already present for SQL databases in `docker/database/`).
- Add an automated backup solution (`mongodump` cron) similar to the TODOs already present in
  `docker/database/postgresql/postgresql.yaml`.
