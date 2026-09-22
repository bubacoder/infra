Samba via crazy-max/docker-samba image.
Users and shares are configured in config/config.yml (mounted at /data/config.yml).
${ADMIN_USER} and ${ADMIN_PASSWORD} are passed as container env vars so that
config.yml can reference them via envsubst at container startup.

Links:
- Source: https://github.com/crazy-max/docker-samba
- Image: https://hub.docker.com/r/crazymax/samba
