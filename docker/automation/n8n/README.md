The world's most popular workflow automation platform for technical teams

## References

- Home: [AI Workflow Automation Platform - n8n](https://n8n.io/)
- Instal: https://docs.n8n.io/hosting/installation/docker/
- Compose based on: [n8n-hosting/docker-compose/withPostgres/docker-compose.yml at main · n8n-io/n8n-hosting](https://github.com/n8n-io/n8n-hosting/blob/main/docker-compose/withPostgres/docker-compose.yml)
- Migration to v2: https://docs.n8n.io/2-0-breaking-changes/

## Backup

`backup.yaml` defines nightly exports of n8n's dedicated PostgreSQL database
under `${DB_BACKUP_ROOT}/automation-n8n/`. Restore with the paired
`.n8n` user folder/binary data and **original `N8N_ENCRYPTION_KEY`** or saved
credentials cannot be decrypted. See the [backup guide](../../../docs/backup.md)
for commands, retention and snapshot selection.

### Recovery

1. Recover `database.dump`, `globals.sql` and the manifest. Restore the required
   roles and database `n8n` with owner `root` into the compatible dedicated
   PostgreSQL instance before starting n8n. A lingering `database.sqlite` is
   legacy data, not the deployed PostgreSQL backend.
2. Restore `/home/node/.n8n`, including `config`, `binaryData`, `git`, `ssh` and
   `nodes`, with expected ownership. Recover original encryption/JWT secrets,
   PostgreSQL credentials and host configuration.
3. Start the matching app/DB images and check `/healthz`, saved credential
   decryption and binary-file access. Keep production schedules/webhooks inactive
   on a test restore.

The DB, user files and separate secret-config copy can have different capture
times; choose nearby restore points and record the recovery pair.

### Post-restore check

Use the original encryption key, restore the DB and paired user folder, then
sign in and open a saved workflow/credential. Test a harmless workflow manually;
keep production schedules/webhooks inactive on an isolated restore.
