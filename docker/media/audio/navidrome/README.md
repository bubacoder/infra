Navidrome is an open source web-based music collection server and streamer.
It gives you freedom to listen to your music collection from any browser or mobile device.

In case of "unable to open database file: no such file or directory" error, chown the `data` directory to match `${PUID}:${PGID}`.

Links:
- Home: https://www.navidrome.org/
- Image: https://hub.docker.com/r/deluan/navidrome
- Installing with Docker: https://www.navidrome.org/docs/installation/docker/
- Configuration Options: https://www.navidrome.org/docs/usage/configuration-options/

Recommended desktop player:  
Feishin - A modern self-hosted music player.  
https://github.com/jeffvli/feishin  
(Fix startup issue Mac: `xattr -r -d com.apple.quarantine /Applications/Feishin.app`)
