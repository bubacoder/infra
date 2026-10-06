ddclient is a Perl client used to update dynamic DNS entries for accounts on Dynamic DNS Network Service Provider. It was originally written by Paul Burry and is now mostly by wimpunk.
It has the capability to update more than just dyndns and it can fetch your WAN-ipaddress in a few different ways.

Links:
- Home: [Home | ddclient docs](https://ddclient.net/)
- Source: [GitHub - ddclient/ddclient: ddclient updates dynamic DNS entries for accounts on a wide range of dynamic DNS services.](https://github.com/ddclient/ddclient)
- Image: [ddclient - LinuxServer.io](https://docs.linuxserver.io/images/docker-ddclient/)

## Config rendering permissions

The config renderer runs as `${PUID}:${PGID}` to match ddclient's configured user.
Before starting the service, create its output directory and ensure that this
user can write the directory and any existing generated config files:

```bash
sudo mkdir -p "${DOCKER_VOLUMES}/ddclient"
sudo chown -R "${PUID}:${PGID}" "${DOCKER_VOLUMES}/ddclient"
```

Run these commands with the service's environment variables loaded. The image
defaults to UID/GID `1000:1000` when run without the Compose user override.
