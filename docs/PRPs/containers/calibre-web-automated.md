## Base information for Calibre-Web Automated application

Application name: Calibre-Web Automated
Homepage: https://github.com/crocodilestick/Calibre-Web-Automated
GitHub page: https://github.com/crocodilestick/Calibre-Web-Automated
Install instructions URL: https://github.com/crocodilestick/Calibre-Web-Automated
Category: media/ebook
Dashboard Icon: calibre-web.png
Dashboard Group: Media
Short description: All-in-one self-hosted digital library with automated ebook ingest, conversion and management
Long description: Calibre-Web Automated (formerly Calibre-Web Automator) combines the modern lightweight Calibre-Web UI with the robust feature set of Calibre, plus a slew of extra automations. It provides automatic ingest, conversion, metadata fetch, cover/metadata enforcement, EPUB fixing, duplicate detection, KOReader syncing (KOSync), enhanced OAuth 2.0/OIDC authentication and more, making Calibre-Web a dream all-in-one self-hosted digital library solution.

> **Note about existing services:** The repository already deploys `calibre` (`docker/media/ebook/calibre`) and `calibre-web` (`docker/media/ebook/calibre-web`) as separate services. Calibre-Web Automated is a distinct project that bundles both and is explicitly designed as a drop-in replacement for stock Calibre-Web (it can reuse the existing `/config` and `/books`/library volumes). Deploying it alongside the existing `calibre-web` container on the same host will conflict on port `8083` — the implementation step must decide between replacing/migrating the existing `calibre-web` service or exposing CWA on a different port.

## Container deployment

### Overview

Calibre-Web Automated ships as a **single self-contained Docker container** built on the LinuxServer.io Ubuntu base image. It bundles Calibre (ebook-convert), Calibre-Web (web UI), kepubify, and the CWA automation services (ingest watcher, converter, EPUB fixer, auto-zipper). It is published on Docker Hub as `crocodilestick/calibre-web-automated` and supports `linux/amd64` and `linux/arm64`.

- Current latest release: **v4.0.6**
- Default container web port: **8083**
- The repo README contains the official `docker-compose.yml` template at the repository root (no separate docs page); there is **no `docker run ...` example**, only Compose.

### Docker Compose configuration

Official template (from the project README / `docker-compose.yml` in the repo):

```yaml
services:
  calibre-web-automated:
    image: crocodilestick/calibre-web-automated:latest
    container_name: calibre-web-automated
    environment:
      # Only change these if you know what you're doing
      - PUID=1000
      - PGID=1000
      # Edit to match your current timezone e.g. Europe/London, America/New_York
      - TZ=Europe/London
      # Hardcover API Key required for Hardcover as a Metadata Provider, get one here: https://docs.hardcover.app/api/getting-started/
      - HARDCOVER_TOKEN=your_hardcover_api_key_here
      # If your library is on a network share (e.g., NFS/SMB), disable WAL to reduce locking issues
      # Accepts: true/false (default: false)
      - NETWORK_SHARE_MODE=false
      # Override the default port (8083) for the web server.
      # Accepts any valid port number.
      - CWA_PORT_OVERRIDE=8083
    volumes:
      # CW users migrating should stop their existing CW instance, make a copy of the config folder, and bind that here
      - /path/to/config/folder:/config
      # This is an ingest dir, NOT a library one. Anything added here will be automatically added to your library.
      # All files placed here are REMOVED AFTER PROCESSING
      - /path/to/the/folder/you/want/to/use/for/book/ingest:/cwa-book-ingest
      # If you don't have an existing library, CWA will automatically create one at the bind provided here
      - /path/to/your/calibre/library:/calibre-library
      # If you use calibre plugins, you can bind your plugins folder here (WIP)
      # If you are starting with a fresh install, you also need to copy customize.py.json to the
      # Calibre config volume at /path/to/config/folder/.config/calibre/customize.py.json
      - /path/to/your/calibre/plugins/folder:/config/.config/calibre/plugins
    ports:
      # Change the first number to change the port you want to access the Web UI, not the second
      - 8083:8083
    # If you set CWA_PORT_OVERRIDE to a port below 1024, you may need to uncomment the following line:
    # cap_add:
    #   - NET_BIND_SERVICE
    restart: unless-stopped
```

The image declares the volumes `/config`, `/cwa-book-ingest` and `/calibre-library`, and the web port `8083`. A `HEALTHCHECK` is built in (uses `CWA_PORT_OVERRIDE` if set).

### Volume bindings

Make sure all 3 main bindings are separate directories — errors can occur when binds are made within other binds:

- `/config` - Stores logs and other miscellaneous files that keep CWA running
  - **New Users** - Use any empty folder (make sure its ownership isn't `root:root`)
  - **Existing Calibre-Web Users** - Map to the existing `/config` directory containing `app.db` to carry over settings and users
- `/cwa-book-ingest` - **ATTENTION** - All files within this folder are **DELETED** after being processed. Only dump new books here for import/automatic conversion
- `/calibre-library` - Bind to the Calibre library folder where `metadata.db` and book files reside
  - **New Users** - Use any empty folder (CWA auto-creates and auto-registers a new library)
  - **Existing Users** - If multiple libraries exist in the mount, CWA mounts the largest one (check logs for which `metadata.db` was used)

**Local library requirement (this repo):** the CWA `/calibre-library` bind must use the same library volume as the existing `calibre` service in `docker/media/ebook/calibre/calibre.yaml`, i.e. `- ${STORAGE_CALIBRE_LIBRARY}:/calibre-library`. That service mounts `${STORAGE_CALIBRE_LIBRARY}:/books` and `${STORAGE_CALIBRE_LIBRARY_HUN}:/books-hun` (Hungarian library). Note that CWA currently supports **only one library per instance**, so the Hungarian library (`STORAGE_CALIBRE_LIBRARY_HUN`) cannot be served by the same CWA container — either bind the main `STORAGE_CALIBRE_LIBRARY` (which CWA will auto-detect and mount) and keep serving the Hungarian library from the existing `calibre` service, or run a second parallel CWA instance for it.
- `/config/.config/calibre/plugins` *(optional)* - Bind a directory containing your existing Calibre plugins; also copy `customize.py.json` (typically at `~/.config/calibre/customize.py.json` on Linux) to `/config/.config/calibre/customize.py.json`. Can be skipped if no Calibre plugins are used
- `/app/calibre-web-automated/gmail.json` *(optional)* - For sending books via a Gmail account (see the Calibre-Web mailserver wiki); a simple SMTP server is recommended instead

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `PUID` / `PGID` | User/group ID the container runs as | `1000` |
| `TZ` | Container timezone (e.g. `Europe/London`) | — |
| `HARDCOVER_TOKEN` | API key for Hardcover metadata provider (optional; from https://docs.hardcover.app/api/getting-started/) | — |
| `NETWORK_SHARE_MODE` | Set `true` when library/config are on NFS/SMB: disables SQLite WAL on `metadata.db`/`app.db`, skips recursive `chown`, switches to polling file watcher | `false` |
| `CWA_WATCH_MODE` | Force `poll` watcher regardless of share mode (auto-used on Docker Desktop and network shares) | `inotify` |
| `CWA_PORT_OVERRIDE` | Override web server port | `8083` |
| `TRUSTED_PROXY_COUNT` | Number of proxies in front of the app for Werkzeug ProxyFix (e.g. Cloudflare Tunnel → nginx → CWA = `2`) | `1` |

### Security considerations

- **Default credentials:** Username `admin`, password `admin123` — must be changed on first login.
- **Reverse proxy:** Intended to run behind a reverse proxy (e.g. Traefik). CWA uses Werkzeug's ProxyFix; behind multiple proxies set `TRUSTED_PROXY_COUNT` to the total proxy chain depth to avoid session-protection re-login issues.
- **Authentication:** Supports LDAP and enhanced OAuth 2.0/OIDC (Keycloak, Authentik, Google, Azure AD) with auto-discovery, group-based admin roles and manual endpoint overrides. In this repo it would sit behind the existing Traefik + Authelia (`localaccess@file` middleware) setup, like the current `calibre-web` service.
- **File permissions:** Books dropped into `/cwa-book-ingest` must be owned by the container user (`PUID`/`PGID`), otherwise permission errors / incomplete imports occur.
- **Ingest dir is destructive:** files placed in `/cwa-book-ingest` are removed after processing; originals are kept (by default) in `/config/processed_books`.
- **Ports:** Only the web port (8083) needs to be exposed; expose it only to the proxy network, not the public internet.

### AMD GPU acceleration

**None.** Calibre-Web Automated performs CPU-based ebook conversion (Calibre `ebook-convert`, kepubify) and has no video decode/transcode or compute workload. The Dockerfile and README contain no VAAPI, ROCm, NVENC, or any GPU-related packages/tags — the image is architecture-specific only (`linux/amd64`, `linux/arm64`). No GPU device, GPU image tag, or in-app GPU configuration is required or supported.

### Post-install tasks

1. Browse to `http://<host>:8083` (or `:8083/opds` for the OPDS catalog)
2. Log in with the default admin credentials (`admin` / `admin123`) and change them
3. Configure the Calibre-Web settings via the Admin Page — make sure **Enable Uploads** is enabled under `Settings -> Basic Configuration -> Feature Configuration`
4. Configure CWA-specific behaviour in the **CWA Settings** panel (enable/disable features, set the target format — EPUB/MOBI/AZW3/KEPUB/PDF —, ignored vs auto-converted formats)
5. Drop a book into the ingest folder to verify the automated pipeline works

### Possible improvements / integration notes

- **Version pinning:** Follow the repo convention of pinning a specific tag (currently `v4.0.6`) instead of `latest` for reproducible deploys.
- **Traefik integration:** Add `traefik.enable` / router / `localaccess@file` middleware labels and the Homepage dashboard labels (`homepage.group: Media`, `homepage.icon: calibre-web.png`, `homepage.href`) in the same style as the existing `docker/media/ebook/calibre-web/calibre-web.yaml`.
- **Reuse existing volumes:** The existing `calibre-web` container's `/config` and the calibre library path (`STORAGE_CALIBRE_LIBRARY`) can be reused to migrate; the implementation step must resolve the port-8083 conflict with the currently deployed `calibre-web` service.
- **Metadata providers:** An `HARDCOVER_TOKEN` can be added later for the Hardcover provider; isbndb, Kobo and LitRes providers are also supported.
- **Backups:** `/config` (including `app.db`, `metadata.db` and the auto-backup `processed_books` folder) plus the library are the data to protect.
- **Monitoring:** The image includes a built-in `HEALTHCHECK` (curl on the web port) usable by Docker; CWA also exposes a `/kosync` endpoint for KOReader sync (RFC 7617 Basic Auth with CWA accounts).
