Nginx webserver with WebDAV enabled.
Aims to enable a no-nonsense WebDAV docker system on the latest available nginx mainline.

Source: https://github.com/dgraziotin/docker-nginx-webdav-nononsense  
Based on [Making Native WebDAV Actually Work on nginx with Finder and Explorer](https://www.rebeccapeck.org/2020/06/making-webdav-actually-work-on-nginx/)

Note: this container is a bit heavy (Ubuntu-based). The ideal solution would be to use the official
Alpine-based [nginx image](https://hub.docker.com/_/nginx) and add the `nginx-mod-http-dav-ext` module.
But the module in the Alpine repo is not compatible with the recent nginx versions and gives this error:
`nginx: [emerg] module "/usr/lib/nginx/modules/ngx_http_dav_ext_module.so" version 1024000 instead of 1026001 in /etc/nginx/nginx.conf:5`
