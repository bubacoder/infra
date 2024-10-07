# Obsidian

https://obsidian.md/

> Obsidian is the private and flexible writing app that adapts to the way you think.

[Download clients](https://obsidian.md/download) for iOS, Android, Windows, Mac, Linux

## Community Plugins

- For note sync, the "Remotely Save" plugin is recommended
- To use it with WebDAV, configure the `storage/webdav` container
- To use the vault on multiple devices:
  - Set up a new vault with the same name on the other device
  - Enable the community plugins
  - Install the "Remotely Save" plugin
  - Configure it to the same WebDAV folder
  - All notes will sync across devices instantly
- Obsidian maintains a sensible file structure:
  - The folders in your sidebar correspond directly to your file system
  - File names in Obsidian match the actual file names, making it easy to switch between editors and locate files

### [Remotely Save](https://github.com/remotely-save/remotely-save)

> Yet another unofficial Obsidian plugin allowing users to synchronize notes between local device and the cloud service. Supports S3, Dropbox, OneDrive, webdav.

Backends available in the homelab repo:
- [MinIO](https://github.com/minio/minio) - S3 compatible
- WebDAV

Configuration:
- Vault name: Infra
- Remote service type: Webdav
- Server address: `https://webdav.<MYDOMAIN>.li`
- Username
- Password

### Alternative: [Self-hosted LiveSync](https://github.com/vrtmrz/obsidian-livesync)

> Self-hosted LiveSync is a community-implemented synchronization plugin, available on every obsidian-compatible platform and using CouchDB or Object Storage (e.g., MinIO, S3, R2, etc.) as the server.

Backends available in the homelab repo:
- [MinIO](https://github.com/minio/minio) - S3 compatible

### [Excalidraw](https://github.com/zsviczian/obsidian-excalidraw-plugin)

> A plugin to edit and view Excalidraw drawings in Obsidian

[The Excalidraw-Obsidian Showcase: 57 key features in just 17 minutes](https://www.youtube.com/watch?v=P_Q6avJGoWI)

### [VSCode Editor](https://github.com/sunxvming/obsidian-vscode-editor)

> A third-party plug-in of Obsidian that provides viewing and editing functions for files in various code formats

Configuration:
- Add file extensions: `yaml,yml,json,sh,txt`
