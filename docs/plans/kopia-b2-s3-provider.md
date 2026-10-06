# Kopia B2 provider migration

Status: **read-only reconnection and restore verified; live migration not applied**. The current
`kopia-b2` container still uses Kopia's deprecated native `b2` storage
provider. Its scheduled backups continue to work with the pinned Kopia
image. This change addresses a future provider-removal/upgrade problem;
it does **not** provide backups during an Internet outage. Restoring the
independent on-site backup destination is the higher offline-resilience
priority.

## Findings

- Kopia's current guidance recommends its **S3-compatible** provider for
  Backblaze B2. Backblaze accepts the existing B2 application key ID and key
  as S3 access key ID and secret key. The bucket's S3 endpoint was discovered
  through Backblaze's account-authorization API:
  `s3.eu-central-003.backblazeb2.com` (region `eu-central-003`).
- The active native-B2 repository uses the bucket root, **without an object
  prefix**. A disposable Kopia 0.23.1 container connected through the S3
  provider to the **same bucket** with `--readonly`. Kopia reported the
  **same repository unique ID** as the active native-B2 connection. The
  disposable config/cache and credentials file were on ephemeral storage;
  nothing was changed in the active Kopia config or remote repository.
- The read-only S3 connection listed **152 snapshots**, including all 15
  then-present snapshots for the existing Docker-volumes source, with the
  same latest timestamp as the native connection. A small manifest restored
  through S3 matched the original local and native-B2 checksum. A first
  path-filtered snapshot query appeared empty because the disposable
  container had a different default hostname; an unfiltered `--all` query
  showed the snapshots. This confirms why preserving the existing Kopia
  `hostname` and `username` settings matters at cutover.
- This supports an **in-place reconnection**. No repository sync or second
  bucket is needed for the tested configuration. Do not run
  `repository create s3` against this existing bucket, or sync a repository
  into the same prefix. If the bucket/key/region is changed later, recheck
  compatibility before any cutover.

## Suggested cutover and rollback

1. First verify a recent B2 snapshot can restore a real artifact. Preserve
   the current root-owned `repository.config` and repository password in
   ignored/offline recovery storage (mode 0600); preserve the **original
   Kopia hostname and username** from that config. A throwaway container's
   hostname is not a safe replacement: snapshot identity and schedules are
   keyed by source user/host/path.
2. The separate **read-only** S3 trial has already confirmed repository ID,
   snapshot listing and a small restore. Before cutting over, additionally
   confirm both active policies in [the backup guide](../backup.md):
   `root@nest:/sources/local/db-backups` and
   `root@nest:/sources/local/docker-volumes`, including retention and ignores.
   Store B2 credentials only in restricted environment/secret files, never
   command arguments or tracked Compose files. Use the bucket root, exact
   regional endpoint, TLS and the existing repository password. Keep the
   running native-B2 server and its 01:15/01:20 schedules untouched until cutover.
3. During a maintenance window **outside** the scheduled backup, stop the
   Kopia server, create a writable S3-provider connection in a **new**
   configuration file, and carry forward the original source identity and
   operational settings. Switch the config only after checks pass; restart
   Kopia, verify the repository ID, source paths, scheduling policy and
   fresh snapshot/restore. Avoid running two writable Kopia servers against
   the same repository during the switch.
4. On any failure, stop the new connection and restore the saved native-B2
   config; restart the original container and confirm the previous schedule.
   Keep that rollback file until multiple S3-provider backups and restores
   succeed. Then remove the deprecated-provider dependency from operational
   notes and document the active endpoint/credential rotation method without
   committing secret values.

References: [Kopia's storage-provider guidance](https://kopia.io/docs/repositories/),
[Kopia S3 connection flags](https://kopia.io/docs/reference/command-line/common/repository-connect-s3/),
and [Backblaze's S3 endpoint and key mapping](https://www.backblaze.com/docs/cloud-storage-call-the-s3-compatible-api).
