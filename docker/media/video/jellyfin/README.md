Jellyfin is a Free Software Media System that puts you in control of managing and streaming your media. It is an alternative to the proprietary Emby and Plex, to provide media from a dedicated server to end-user devices via multiple apps.
Jellyfin is descended from Emby's 3.5.2 release and ported to the .NET Core framework to enable full cross-platform support. There are no strings attached, no premium licenses or features, and no hidden agendas: just a team who want to build something better and work together to achieve it.

Links:
- Home: https://jellyfin.org/
- Image: https://hub.docker.com/r/linuxserver/jellyfin

Desktop client: https://github.com/jellyfin/jellyfin-media-player

GPU override for Jellyfin — AMD VAAPI hardware transcoding.
Enable by setting GPU_COMPOSE_SUFFIX=amdgpu in config/docker/<hostname>/.env
After deploying, configure VA-API in Jellyfin UI: Dashboard → Playback → Transcoding → VA-API
