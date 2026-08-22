## Base information for Immich application

Application name: Immich
Homepage: https://immich.app
GitHub page: https://github.com/immich-app/immich
Install instructions URL: https://immich.app/docs/install/docker-compose
Category: tools
Dashboard Icon: immich.png
Dashboard Group: Media
Short description: Self-hosted photo and video backup and management platform
Long description: Immich is a high-performance self-hosted solution for backing up, organizing, and viewing photos and videos, with mobile clients, multi-user support, and local machine-learning search and recognition.

## Container deployment

### Overview and requirements

Docker Compose is Immich's recommended production deployment method. Use the current release assets rather than Compose files from the repository's `main` branch, which may be incompatible with the latest release.

- Supported platforms are `amd64` and `arm64`. Since v3, the `amd64` machine-learning image requires an x86-64-v2 CPU; use a suitable virtual CPU type when deploying in a VM.
- Use Docker Engine with the Compose plugin and the `docker compose` command. The deprecated `docker-compose` v1 command is unsupported.
- Minimum resources are 2 CPU cores and 6 GB RAM; 4 cores and 8 GB RAM are recommended. Machine learning can be disabled on 4 GB hosts.
- Store the Postgres database on local, Unix-compatible SSD storage. It must never be on NFS, SMB, or another network share. When using Docker resource limits, allocate Postgres at least 2 GB RAM.
- Plan library capacity for original assets plus roughly 10-20% additional space for thumbnails and transcoded videos. Back up both the upload library and database using a 3-2-1 strategy.

### Required files

Create an Immich directory containing these release assets:

```bash
wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O .env https://github.com/immich-app/immich/releases/latest/download/example.env
```

For optional hardware acceleration, download the matching file into the same directory:

```bash
wget -O hwaccel.transcoding.yml https://github.com/immich-app/immich/releases/latest/download/hwaccel.transcoding.yml
wget -O hwaccel.ml.yml https://github.com/immich-app/immich/releases/latest/download/hwaccel.ml.yml
```

Start or recreate the stack with:

```bash
docker compose up -d
```

### Official Docker Compose configuration

The official release Compose stack is:

```yaml
name: immich

services:
  immich-server:
    container_name: immich_server
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-release}
    # extends:
    #   file: hwaccel.transcoding.yml
    #   service: cpu # Use nvenc, quicksync, rkmpp, vaapi, or vaapi-wsl when enabled.
    volumes:
      - ${UPLOAD_LOCATION}:/data
      - /etc/localtime:/etc/localtime:ro
    env_file:
      - .env
    ports:
      - '2283:2283'
    depends_on:
      - redis
      - database
    restart: always
    healthcheck:
      disable: false

  immich-machine-learning:
    container_name: immich_machine_learning
    image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-release}
    # Add -armnn, -cuda, -rocm, -openvino, or -rknn to the image tag when enabled.
    # extends:
    #   file: hwaccel.ml.yml
    #   service: cpu
    volumes:
      - model-cache:/cache
    env_file:
      - .env
    restart: always
    healthcheck:
      disable: false

  redis:
    container_name: immich_redis
    image: docker.io/valkey/valkey:9@sha256:8e8d64b405ce18f41b8e5ee20aa4687a8ed0022d1298f2ce31cdcf3a76e09411
    healthcheck:
      test: redis-cli ping || exit 1
    restart: always

  database:
    container_name: immich_postgres
    image: ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:bcf63357191b76a916ae5eb93464d65c07511da41e3bf7a8416db519b40b1c23
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${DB_USERNAME}
      POSTGRES_DB: ${DB_DATABASE_NAME}
      POSTGRES_INITDB_ARGS: '--data-checksums'
      # Set DB_STORAGE_TYPE: 'HDD' if this database is not on SSD storage.
    volumes:
      - ${DB_DATA_LOCATION}:/var/lib/postgresql/data
    shm_size: 128mb
    restart: always
    healthcheck:
      disable: false

volumes:
  model-cache:
```

Only port `2283` is published. Valkey and Postgres are internal to the Compose network. The implementation should follow repository conventions for routing this port through Traefik instead of exposing it publicly.

### Environment variables and storage

Set these values in `.env` before deployment:

| Variable | Description | Default / guidance |
|---|---|---|
| `UPLOAD_LOCATION` | Absolute host path for uploaded originals, thumbnails, encoded videos, and derived files, mounted at `/data`. | `./library`; choose a sufficiently large persistent filesystem. |
| `DB_DATA_LOCATION` | Absolute local host path for Postgres data. | `./postgres`; local SSD only, never a network share. |
| `TZ` | IANA timezone used as EXIF fallback, log timestamps, and cron scheduling. | Uncomment and set, for example `Etc/UTC`. |
| `IMMICH_VERSION` | Server and machine-learning image version. | `v3`; pin an exact compatible release for reproducibility. |
| `DB_PASSWORD` | Postgres password used only on the internal network. | Replace `postgres` with a random value using only `A-Za-z0-9` characters. |
| `DB_USERNAME` | Postgres user. | `postgres`; normally unchanged. |
| `DB_DATABASE_NAME` | Postgres database name. | `immich`; normally unchanged. |

Useful optional settings include `IMMICH_TRUSTED_PROXIES` for the reverse-proxy IP range, `IMMICH_LOG_LEVEL`, `IMMICH_LOG_FORMAT=json`, `CPU_CORES`, and `DB_STORAGE_TYPE=HDD` when the database must use rotational local storage. Do not set `IMMICH_MEDIA_LOCATION`; change the host library path through `UPLOAD_LOCATION` only. Configure variables before the first launch or recreate affected containers after changes with `docker compose up -d --force-recreate`.

### Security considerations

- Treat the library as private user data. Do not publish port `2283` directly to the Internet; use the existing TLS reverse proxy and authentication controls.
- Set a unique database password and keep it out of version control. Immich supports `DB_PASSWORD_FILE` and related `_FILE` variables with Docker secrets or systemd credentials if secret-file handling is desired.
- Set `IMMICH_TRUSTED_PROXIES` to the proxy addresses so forwarded client headers are trusted only from the proxy.
- Complete initial administrator setup promptly. Consider setting `IMMICH_ALLOW_SETUP=false` after the first administrator is created to disable the public administrator-sign-up endpoint.
- Preserve and back up both `${UPLOAD_LOCATION}` and `${DB_DATA_LOCATION}`. Postgres data checksums are enabled by the official image initialization settings.
- Keep the release-provided Postgres image, including its pinned digest and supported VectorChord/pgvector extensions. Do not substitute a stock Postgres image.

### AMD GPU acceleration

Immich supports AMD GPU acceleration in two independent areas. It ships no AMD-specific server image for transcoding; server hardware selection is supplied by the `hwaccel.transcoding.yml` Compose extension. It does ship a ROCm-specific machine-learning image tag.

#### VAAPI video transcoding

- **Type:** VAAPI can use AMD GPUs for hardware video encoding. By default, only encoding is accelerated; enable hardware decoding in Immich for end-to-end acceleration. AMD and NVIDIA GPUs do not encode VP9. Hardware encodes can be larger and lower quality than software encodes at comparable settings.
- **Compose setup:** Download `hwaccel.transcoding.yml`, uncomment `immich-server.extends`, set `file: hwaccel.transcoding.yml` and `service: vaapi`. The extension maps `/dev/dri:/dev/dri`; no GPU-specific server image tag is required.
- **Manual in-app setup:** Redeploy `immich-server`, then open **Admin > Video transcoding settings**, select **VAAPI** as hardware acceleration, save, and optionally enable hardware decoding. Existing jobs do not need to be redone; future transcodes use the device.

#### ROCm machine-learning inference

- **Type:** ROCm accelerates Smart Search and facial-recognition inference on supported AMD GPUs. This backend is experimental and requires Linux or WSL2.
- **Image tag:** Change the machine-learning image to `ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-release}-rocm`.
- **Compose setup:** Download `hwaccel.ml.yml`, uncomment `immich-machine-learning.extends`, set `file: hwaccel.ml.yml` and `service: rocm`. The extension adds the container to the `video` group and maps `/dev/dri` and `/dev/kfd`.
- **Host prerequisites:** Install the AMDGPU driver. With Secure Boot, enroll the DKMS signing key in UEFI. The GPU must be ROCm-supported; unsupported devices may sometimes work with `HSA_OVERRIDE_GFX_VERSION` and, if needed, `HSA_USE_SVM=0`.
- **Operational notes:** The ROCm image needs at least 35 GiB of free disk for its initial pull. Initial MIGraphX inference compiles models and is slow. GPU power use can stay elevated until the machine-learning container has been idle for five minutes; tune `MACHINE_LEARNING_MODEL_TTL` if appropriate.
- **Manual in-app setup:** No in-app GPU selector is required for ROCm. Redeploy `immich-machine-learning`; new jobs use ROCm automatically. Confirm the AMD device is used with `radeontop` and the machine-learning container logs.

### Possible improvements

- Integrate with the repository's Traefik and Homepage label conventions, using dashboard group `Media` and icon `immich.png`.
- Pin `IMMICH_VERSION` to an exact release and follow Immich's upgrade instructions for every version change; the application changes quickly and its server, ML, and database components must remain compatible.
- Enable the internal metrics ports only if monitoring is configured: `IMMICH_API_METRICS_PORT` defaults to `8081` and `IMMICH_MICROSERVICES_METRICS_PORT` to `8082`.
- Place the database on SSD and, if it must be on a local HDD, enable `DB_STORAGE_TYPE=HDD` for appropriate I/O tuning.
- Size and back up the named `model-cache` volume if avoiding repeated model downloads matters; it is not the irreplaceable user-data backup target.
- Review post-installation settings for storage templates, job concurrency, external libraries, and an authentication strategy compatible with the existing reverse-proxy setup.

### Sources

- https://immich.app/docs/install/docker-compose
- https://immich.app/docs/install/requirements
- https://immich.app/docs/install/environment-variables
- https://immich.app/docs/features/hardware-transcoding
- https://immich.app/docs/features/ml-hardware-acceleration
