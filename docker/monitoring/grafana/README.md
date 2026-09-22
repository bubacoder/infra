# Grafana Authentik OIDC

Grafana uses native OIDC for Authentik's `monitoring` group. Keep a local
Grafana administrator enabled for recovery. API tokens and service accounts are
independent of browser SSO.

## Setup

Create the ignored client-secret file:

```text
config/docker/<host>/grafana/authentik-client-secret
```

Set its mode to `0600`, then set `GRAFANA_AUTHENTIK_CLIENT_ID` and
`GRAFANA_AUTHENTIK_CLIENT_SECRET_PATH` in the ignored
`config/docker/<host>/.env.grafana` file. Create the Authentik resources and
recreate Grafana:

```bash
scripts/authentik-apps.py --application grafana --apply
scripts/labctl.py service recreate monitoring/grafana
```

The Compose configuration supplies the issuer endpoints, PKCE, refresh-token
scope, and sign-out endpoint. Keep the registered callback URI exact:
`https://grafana.<domain>/login/generic_oauth`.

## Verify

Confirm a `monitoring` member can sign in, a non-member is denied, and the
retained local administrator can still sign in. Access changes are re-evaluated
when Grafana refreshes its Authentik token.

Grafana open source software enables you to query, visualize, alert on, and explore your metrics, logs, and traces wherever they are stored.
Grafana OSS provides you with tools to turn your time-series database (TSDB) data into insightful graphs and visualizations.
The Grafana OSS plugin framework also enables you to connect other data sources like NoSQL/SQL databases, ticketing tools like Jira or ServiceNow, and CI/CD tooling like GitLab.
([source](https://grafana.com/docs/grafana/latest/introduction/))

Default admin user credentials: `admin` / `admin`

Links:
- Home: https://grafana.com/grafana/
- Image: https://hub.docker.com/r/grafana/grafana-oss
- Getting Started: https://grafana.com/docs/grafana/latest/fundamentals/getting-started/
- New in v12: https://grafana.com/docs/grafana/latest/whatsnew/whats-new-in-v12-0/

Recommended dashboards to import:
- https://grafana.com/grafana/dashboards/1860-node-exporter-full/
- https://grafana.com/grafana/dashboards/14282-cadvisor-exporter/
