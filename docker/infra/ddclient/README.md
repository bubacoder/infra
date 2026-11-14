ddclient is a Perl client used to update dynamic DNS entries for accounts on Dynamic DNS Network Service Provider. It was originally written by Paul Burry and is now mostly by wimpunk.
It has the capability to update more than just dyndns and it can fetch your WAN-ipaddress in a few different ways.

## References

- Home: [Home | ddclient docs](https://ddclient.net/)
- Source: [GitHub - ddclient/ddclient: ddclient updates dynamic DNS entries for accounts on a wide range of dynamic DNS services.](https://github.com/ddclient/ddclient)
- Image: [ddclient - LinuxServer.io](https://docs.linuxserver.io/images/docker-ddclient/)

## Native environment-backed configuration

The tracked `ddclient.conf` uses ddclient's native `password_env`, `zone_env`
and `host_env` settings. The Cloudflare token is supplied at runtime through the
service-specific environment file; it is not rendered into a config file or
image. `MYDOMAIN` supplies the zone and the Compose service constructs the two
host names.

The config file is mounted read-only. Before starting the service, create its
state directory and ensure ddclient's configured user can write its cache:

```bash
sudo mkdir -p "${DOCKER_VOLUMES}/ddclient"
sudo chown -R "${PUID}:${PGID}" "${DOCKER_VOLUMES}/ddclient"
```

Run these commands with the service's environment variables loaded. The image
defaults to UID/GID `1000:1000` when run without the Compose user override.
