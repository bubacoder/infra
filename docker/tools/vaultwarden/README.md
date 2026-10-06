Unofficial Bitwarden compatible server written in Rust

## References

- Source: [GitHub - dani-garcia/vaultwarden: Unofficial Bitwarden compatible server written in Rust, formerly known as bitwarden_rs](https://github.com/dani-garcia/vaultwarden)
- Wiki: [Home · dani-garcia/vaultwarden Wiki](https://github.com/dani-garcia/vaultwarden/wiki)
- Keepass import: [Importing data from Keepass or KeepassX · dani-garcia/vaultwarden Wiki](https://github.com/dani-garcia/vaultwarden/wiki/Importing-data-from-Keepass-or-KeepassX)
- Bitwarden: https://bitwarden.com/, https://bitwarden.com/browser-start/

## Backup

`backup.yaml` defines nightly online SQLite exports under
`${DB_BACKUP_ROOT}/tools-vaultwarden/`. Restore the standalone DB
with attachments, Sends, signing keys and any `config.json` from the paired application B2
snapshot. Signing-key inventory is checked before publication. See the
[backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Retrieve `database.sqlite3` and its checksum manifest from the DB snapshot,
   and `attachments/`, `sends/`, `rsa_key.*` and any `config.json` from the paired
   application snapshot. Restore the original ignored host configuration too.
2. Stop the destination Vaultwarden and preserve its old `/data`. Install the
   standalone export as `/data/db.sqlite3`; remove stale destination DB WAL/SHM
   files rather than copying live sidecars alongside the export.
3. Restore the paired files with ownership required by the matching image, then
   start Vaultwarden. The DB/file capture gap is accepted for this online backup;
   verify restored attachment/Send references rather than assuming atomic capture.

A restored database does not replace the user's master password, recovery code
or offline unlock material.

### Post-restore check

Restore the standalone DB, attachments/Sends and original signing keys. Unlock
the vault with an existing account, open one saved item and download one
attachment; check an organization vault if used.
