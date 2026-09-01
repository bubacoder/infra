# Scrutiny Authentik ForwardAuth

Authentik ForwardAuth protects the Scrutiny web UI for the `monitoring` group.
Keep collector and InfluxDB communication internal; ForwardAuth only protects
browser requests.

## Setup

```bash
scripts/authentik-apps.py --application scrutiny --apply
scripts/labctl.py service recreate monitoring/scrutiny
```

Keep `localaccess-authentik@file` on the `scrutiny` router and do not expose the
web UI directly.

## Verify

Confirm authorized UI access, non-member denial, proxy-session group revocation,
logout, and continued internal health checks and collector operation.
