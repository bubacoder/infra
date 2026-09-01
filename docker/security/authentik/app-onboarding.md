# Authentik Application Onboarding

This is the canonical procedure for adding an application to Authentik SSO in
this repository. Prefer native OIDC/OAuth2. Use Traefik ForwardAuth only for a
browser-oriented application without a suitable native integration.

## Before Starting

1. Read the application's current official authentication documentation. Do
   not infer support from an old image, issue, or blog post.
2. Record its deployed version and determine whether it supports native OIDC,
   OAuth2, SAML, trusted headers, or no external authentication.
3. Identify exact callback and logout URLs, scopes, client authentication
   method, PKCE requirements, group/role claim mapping, and local recovery.
4. Identify non-browser clients such as APIs, mobile apps, webhooks, and CLI
   tools that cannot follow interactive redirects.
5. Bind access to the smallest appropriate ordinary Authentik group.

Keep the service on `localaccess@file` while researching and preparing SSO.
Do not disable its local administrator until login, logout, access revocation,
and recovery have been tested.

## Automation Boundary

`docker/security/authentik/config/apps.yaml` is the tracked application
manifest. `scripts/authentik-apps.py` partially automates onboarding:

- Creates missing Authentik providers and applications.
- Creates missing groups and application group bindings.
- Assigns proxy providers to the embedded outpost.
- Adds missing Traefik callback routers for ForwardAuth applications.
- Defaults to a read-only plan and never deletes resources.

It updates existing OIDC providers only when declared scope mappings or signing
keys differ. It does not otherwise update existing Authentik resources,
configure the downstream application, change its Traefik middleware, create
application-local users, or test application behavior. Existing Authentik
resources are otherwise authoritative; review drift manually.

The dedicated API token and OIDC client secrets stay under ignored
`config/docker/<host>/` paths. Never put them in the manifest, command line,
Compose labels, logs, or chat.

The helper defaults to `config/docker/localhost`, which is a symlink to the
local Docker host configuration. Pass `--host <name>` only when operating on a
different configured host.

## Native OIDC/OAuth2

Use this for applications that can manage an OIDC login and their own session.
The Grafana entry is the working example:

```yaml
- name: Grafana
  slug: grafana
  launch_url: "https://grafana.${MYDOMAIN}/"
  group: monitoring
  provider:
    type: oidc
    name: Provider for Grafana
    client_id: "${GRAFANA_AUTHENTIK_CLIENT_ID}"
    client_secret_file: grafana/authentik-client-secret
    redirect_uris:
      - "https://grafana.${MYDOMAIN}/login/generic_oauth"
```

Onboarding sequence:

1. Add the OIDC entry to `config/apps.yaml` using the exact callback URL from
   the application's official documentation.
2. Put the non-secret client ID in ignored
   `config/docker/<host>/.env.<application-slug>` configuration and the matching
   client secret in the manifest's ignored host-relative secret file. The
   helper automatically loads common and host service environment files for
   every manifest slug. Restrict secret files to mode `0600` and parent
   directories to `0700`.
3. Run the plan and review every proposed resource:

   ```bash
    scripts/authentik-apps.py --application <slug>
    ```

    Use `--application <slug>` to avoid applying unrelated declared changes.

4. Back up Authentik, then apply only the reviewed create and update actions:

   ```bash
    scripts/authentik-apps.py --application <slug> --apply
    scripts/authentik-apps.py --application <slug>
   ```

   The second command must report `NO-CHANGE` for the new resources.
5. Configure the application from its official documentation. Authentik's
   standard endpoints are:

   | Purpose | URL |
   |---|---|
   | Issuer/discovery base | `https://sso.<domain>/application/o/<slug>/` |
   | Authorization | `https://sso.<domain>/application/o/authorize/` |
   | Token | `https://sso.<domain>/application/o/token/` |
   | User info | `https://sso.<domain>/application/o/userinfo/` |
   | End session | `https://sso.<domain>/application/o/<slug>/end-session/` |

6. Mount the client secret as a Docker secret when the application supports a
   secret-file setting. Otherwise keep it only in ignored host configuration.
7. Recreate only the application and verify the acceptance checklist below.

The helper defaults to confidential Authorization Code providers with strict
redirect URI matching and the managed `openid`, `profile`, and `email` scope
mappings. A manifest may explicitly select another client type or grant type
when an application's official documentation requires it. Confirm these choices
before applying.

## Traefik ForwardAuth

Use this as an outer browser access gate when native OIDC is unavailable. It
does not replace database passwords, API keys, or other non-browser credentials.
Adminer is the working example:

```yaml
- name: Adminer
  slug: adminer
  launch_url: "https://adminer.${MYDOMAIN}/"
  group: developers
  provider:
    type: proxy_forward_auth
    name: Provider for Adminer
    external_host: "https://adminer.${MYDOMAIN}/"
    mode: forward_single
    outpost: authentik Embedded Outpost
```

Onboarding sequence:

1. Confirm the service has no direct host port or alternate hostname that
   bypasses Traefik. Preserve native authentication when it protects APIs or
   non-browser clients.
2. Add the proxy entry to `config/apps.yaml` and run plan, apply, then plan as
   shown above. Apply also adds a create-only callback router to
   `docker/security/traefik/config/dynamic/authentik-outposts.yml`; Traefik
   reloads this watched file without restarting Authentik.
3. After the second plan reports `NO-CHANGE`, switch only the application's
   router middleware:

   ```yaml
   traefik.http.routers.<service>.middlewares: localaccess-authentik@file
   ```

4. Validate and recreate only the application:

   ```bash
   pre-commit run --files docker/<category>/<service>/<service>.yaml
   scripts/labctl.py service config <category>/<service>
   scripts/labctl.py service recreate <category>/<service>
   ```

5. An unauthenticated request should redirect through Authentik and return to
   `https://<service>.<domain>/outpost.goauthentik.io/callback` before reaching
   the application.

## Acceptance Checklist

- An authorized group member can log in from a fresh private browser session.
- A user outside the bound group is denied in a fresh private session.
- Removing group membership denies a new session; restoring it restores access.
- Logout removes the usable application/proxy session.
- Session expiry forces reauthentication.
- The local application administrator or other recovery path still works.
- APIs, mobile clients, webhooks, WebSockets, and CLI clients still work where
  applicable.
- Direct ports and alternate hostnames cannot bypass Traefik authentication.
- The final helper plan reports `NO-CHANGE`.

If any test fails, restore `localaccess@file` or the previous middleware first,
then investigate.
