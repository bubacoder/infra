SearXNG is a free internet metasearch engine which aggregates results from various search services and databases.
Users are neither tracked nor profiled.

## Configuration

The container uses Granian's default worker and thread settings. Legacy uWSGI
environment variables do not apply to this image.

The Valkey connection is configured by `SEARXNG_VALKEY_URL` and the mounted
settings file's `valkey` section. The backend retains its `searxng-redis` service
name so existing network addressing and storage paths stay unchanged.

## References

- Home: [SearXNG Documentation (2026.9.23+3cd69d30e)](https://docs.searxng.org)
- Source: [GitHub - searxng/searxng: SearXNG is a free internet metasearch engine which aggregates results from various search services and databases. Users are neither tracked nor profiled.](https://github.com/searxng/searxng)
- Compose: [GitHub - searxng/searxng-docker](https://github.com/searxng/searxng-docker)
