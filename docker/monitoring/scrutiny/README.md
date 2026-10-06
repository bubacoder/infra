Hard Drive S.M.A.R.T Monitoring, Historical Trends & Real World Failure Thresholds

## References

- Source: [GitHub - AnalogJ/scrutiny: Hard Drive S.M.A.R.T Monitoring, Historical Trends & Real World Failure Thresholds](https://github.com/AnalogJ/scrutiny)

In addition to the Omnibus image (available under the latest tag) you can deploy in Hub/Spoke mode.
Details: [scrutiny/docker/example.hubspoke.docker-compose.yml at master · AnalogJ/scrutiny](https://github.com/AnalogJ/scrutiny/blob/master/docker/example.hubspoke.docker-compose.yml)

## Authentik

Authentik ForwardAuth protects the Scrutiny web UI for the `monitoring` group.
Keep collector and InfluxDB communication internal; ForwardAuth only protects
browser requests.

### Setup

```bash
scripts/authentik-apps.py --application scrutiny --apply
scripts/labctl.py service recreate monitoring/scrutiny
```

Keep `localaccess-authentik@file` on the `scrutiny` router and do not expose the
web UI directly.

### Verify

Confirm authorized UI access, non-member denial, proxy-session group revocation,
logout, and continued internal health checks and collector operation.

## Backup

Scrutiny uses InfluxDB for history and `config/scrutiny.db` (SQLite) for
application state. Neither is included in the shared daily exporter; no dedicated
backup is configured. See the [coverage boundaries](../../../docs/backup.md#coverage-boundaries).
Any future native backup needs both SQLite application state and InfluxDB's
history/metadata, plus the original plaintext operator token for recovery;
copying raw live InfluxDB files is not a native backup.
