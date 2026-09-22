Home Assistant Core - Open source home automation that puts local control and privacy first. Powered by a worldwide community of tinkerers and DIY enthusiasts. Perfect to run on a Raspberry Pi or a local server.

Home Assistant needs to set up to allow the Traefik reverse proxy (details: [HTTP - Home Assistant](https://www.home-assistant.io/integrations/http/))
For this, add to `${DOCKER_VOLUMES}/homeassistant/configuration.yaml`:
```
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12  # All Docker bridge networks
```

Links:
- [Home Assistant](https://www.home-assistant.io/)
- [linuxserver/homeassistant - Docker Image](https://hub.docker.com/r/linuxserver/homeassistant)
- [HTTP - Home Assistant](https://www.home-assistant.io/integrations/http/)
