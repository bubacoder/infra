# Obsidian

https://obsidian.md/

> Obsidian is the private and flexible writing app that adapts to the way you think.

## Plugins

### [Self-hosted LiveSync](https://github.com/vrtmrz/obsidian-livesync)

> Self-hosted LiveSync is a community-implemented synchronization plugin, available on every obsidian-compatible platform and using CouchDB or Object Storage (e.g., MinIO, S3, R2, etc.) as the server.

Backends available in the homelab repo:
- [MinIO](https://github.com/minio/minio) - S3 compatible

### [Remotely Save](https://github.com/remotely-save/remotely-save)

> Yet another unofficial Obsidian plugin allowing users to synchronize notes between local device and the cloud service. Supports S3, Dropbox, OneDrive, webdav.

Backends available in the homelab repo:
- [MinIO](https://github.com/minio/minio) - S3 compatible
- WebDAV

### [Excalidraw](https://github.com/zsviczian/obsidian-excalidraw-plugin)

> A plugin to edit and view Excalidraw drawings in Obsidian

[The Excalidraw-Obsidian Showcase: 57 key features in just 17 minutes](https://www.youtube.com/watch?v=P_Q6avJGoWI)

---

I love Obsidian seriously anything you want someone wrote a plugin for it.

For note sync I also recommend the remotely save addon.  I use it with web dav, just spun up a little docker container just for that. To use the vault on multiple devices I set up a new vault on the device with the same name, install the remotely save addon, configure it to the same dav folder, and boom all my notes appear.

Obsidian keeps a sensible file structure. The folders you  see your side bar will be in your file system, the names you see will be the names of the files. Makes it incredibly convenient bouncing between editors, I always can get to the right file.

The sync is sturdy enough to withstand multiple users in a vault and users going between devices.

Just be sure to enable community plugins, that's where all the fun is.

Obsidian also has a nice little code editor plugin too it's been great for scratch sheets while working stuff. It's called VSCode. It does support yaml, just needs to be added to the extensions list.
