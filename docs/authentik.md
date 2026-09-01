# Authentik Getting Started

This guide deploys Authentik as the identity provider for a new homelab.

## What This Provides

- Local administrator accounts for break-glass recovery.
- Google login for approved people.
- OIDC/OAuth2 for applications with native SSO support.
- Traefik ForwardAuth for browser applications without native OIDC.
- TOTP, passkeys, and recovery tokens.

Authentik does not replace protocol-specific access methods. Retain SSH keys,
API keys, app passwords, database users, SMB credentials, MQTT credentials,
and WireGuard keys where those protocols require them.

## Before You Start

You need:

- A working Docker host with Traefik and HTTPS.
- A permanent HTTPS hostname for Authentik, such as `sso.example.com`.
- Local DNS that resolves that hostname to Traefik.
- A private backup location.
- At least 2 CPU cores and 2 GB RAM on the Docker host.

Choose the hostname carefully. It becomes part of OIDC issuer and callback
URLs, so changing it later breaks configured applications.

Do not expose the Authentik database or container ports on the host. Route the
web interface only through Traefik.

## Deploy the Stack

1. Ensure the Authentik service definition exists at
   `docker/security/authentik/authentik.yaml`.
2. Copy the example configuration tree to the ignored `config/` directory.
3. Create the host secret directory, for example
   `config/docker/<host>/authentik/`.
4. Generate the required secrets:

```bash
cd config/docker/<host>/authentik/
openssl rand -out postgresql-password -base64 36
openssl rand -out secret-key -hex 60
chmod 600 postgresql-password secret-key
```

5. Set the host-specific service environment variable:

```dotenv
AUTHENTIK_SECRETS_PATH=${INFRA_CONFIG_PATH}/docker/<host>/authentik
```

6. Add `authentik` under `security` in
   `config/docker/<host>/services.yaml` with `state: up`.
7. Create the isolated Docker network and connect Traefik:

```bash
docker network create security-authentik
docker network connect security-authentik traefik
```

8. Add `security-authentik` to Traefik's networks in
   `docker/security/traefik/traefik.yaml` so the connection persists after a
   Traefik recreation.
9. Start Authentik:

```bash
scripts/labctl.py service up security/authentik
```

10. Verify the three containers are healthy:

```bash
docker inspect --format '{{.Name}} {{.State.Status}} {{.State.Health.Status}}' \
  authentik-postgresql authentik-server authentik-worker
```

Expected result: each container is `running` and `healthy`.

## Create the Break-Glass Administrator

1. Open `https://sso.example.com/if/flow/initial-setup/`.
2. Set a unique, strong password for `akadmin`.
3. Store it in the password vault and keep an offline recovery record.
4. Log out, open a private browser window, and log in again.

Keep this local administrator independent of Google. Do not make the only
administrator dependent on the Google account used for daily login.

## Enroll MFA and Recovery

Sign in as `akadmin`, then open the user menu, **Settings**, and
**Credentials**.

1. Enroll **Static tokens** and store all generated one-time codes in the
   password vault plus an offline location.
2. Enroll a **TOTP device** by scanning the QR code with an authenticator app.
3. Optionally enroll a **WebAuthn device** such as a hardware security key or
   a passkey on a second device.
4. Log out and test login in a private window.

The default Authentik authentication flow normally contains MFA validation
after password validation. It requests TOTP, static tokens, or passkeys for
users that have an enrolled device, while allowing users with no device to
continue. Confirm this behavior before changing flow settings.

If all administrator login methods are lost, create a short-lived recovery link
from the Docker host. Treat the resulting URL as a password and do not paste it
into tickets or chat:

```bash
docker exec authentik-worker ak create_recovery_key 10 akadmin
```

## Back Up Before Adding Users or Applications

Back up all of these together:

- The Authentik PostgreSQL database.
- `${DOCKER_VOLUMES}/authentik/data`.
- `${DOCKER_VOLUMES}/authentik/certs`.
- `${DOCKER_VOLUMES}/authentik/templates`.
- The ignored Authentik secret files.
- The tracked Compose and Traefik configuration.

Example logical database backup:

```bash
docker exec authentik-postgresql pg_dump -U authentik -d authentik -Fc \
  -f /tmp/authentik.dump
docker cp authentik-postgresql:/tmp/authentik.dump /secure-backup/authentik.dump
docker exec authentik-postgresql rm /tmp/authentik.dump
chmod 600 /secure-backup/authentik.dump
```

Test a restore in a temporary database before relying on the backup. Never
restore over the live `authentik` database as a test.

## Create Groups

Create groups before adding applications. Initial groups for this repository:

| Group | Intended access |
|---|---|
| `admins` | Authentik administration, Traefik, backups, databases, VPN, remote access, and security tools |
| `family` | Family media, photos, books, and approved household services |
| `users` | Low-risk general authenticated services |
| `developers` | Gitea, code-server, development tools, and selected AI interfaces |
| `monitoring` | Grafana, Prometheus UI, Uptime Kuma, and Scrutiny |
| `media` | Media-management tools beyond normal media consumption |

To create a group, open the Authentik Admin interface and go to **Directory**
then **Groups**. Click **Create**, enter the group name, leave **Is superuser**
disabled, and save. Repeat for each group.

Add the break-glass administrator to the ordinary `admins` group through
**Directory** then **Users**, selecting `akadmin`, and editing its group
membership.

Do not change the existing built-in superuser group. The ordinary `admins`
group is for future application access; it does not itself make someone an
Authentik administrator. Do not grant `admins` based on a Google email address
or automatic group creation.

## Add Google Login

1. In Google Cloud Console, create an OAuth client for a web application.
2. Set its authorized redirect URI to the exact, case-sensitive URL:

   ```text
   https://sso.example.com/source/oauth/callback/google/
   ```

   Replace `sso.example.com` with the permanent Authentik hostname. Do not use
   a wildcard URI.
3. In Authentik Admin, create a **Google OAuth Source** with a stable slug such
   as `google`, the Google client ID, and the Google client secret.
4. Set **User matching mode** and **Group matching mode** to **Use the
   source-specific identifier**. This prevents automatic linking to a local
   Authentik user or group solely because its email address or name matches.
5. Leave **Scopes** empty. Authentik's Google source already requests the
   required `email` and `profile` scopes; do not request additional Google data
   without a concrete need.
6. Add the source to the **Selected Sources** setting on the
   `default-authentication-identification` stage of the
   `default-authentication-flow`. The login screen should then offer both local
   login and Google.
7. Configure the single-source-of-truth email allowlist below before granting
   any application access.
8. Test an approved account, an unapproved account, local administrator login,
   logout, and a Google-outage recovery path.

If a Google client secret is ever copied into a chat, ticket, source-control
file, or other untrusted location, rotate it in Google Cloud Console and
replace the source's **Consumer secret** before testing.

### Require Verified, Allowlisted Google Email

Authentik's built-in Google source reads Google's OAuth userinfo response, which
includes a `verified_email` boolean. Require that current value alongside the
approved-email list for both first enrollment and repeat authentication. The
checks fail closed when the value is absent or is not the boolean `true`.

`docker/security/authentik/config/blueprints/google-email-verification.yaml`
manages the non-secret implementation:

- Expression policy `google-email-verified`.
- The existing `default-source-enrollment-if-sso` and
  `default-source-authentication-if-sso` expressions that require both verified
  email and the private allowlist policy.

Authentik automatically applies this mounted blueprint. Keep only the private
address list manual:

1. In **Customization** > **Policies**, create or update the **Expression
   Policy** named
   `google-email-allowlist` with this expression. Replace the example addresses
   with the approved accounts.

   ```python
   allowed_emails = {
       "person1@example.com",
       "person2@example.com",
   }

   email = request.context.get("allowlist_email", "").strip().casefold()

   if email not in allowed_emails:
       ak_message("This Google account is not permitted.")
       return False

   return True
   ```

2. Keep the Google OAuth app in **Testing** and add the same approved accounts
   under Google Cloud Console > **Google Auth Platform** > **Audience** >
   **Test users**. This provides a second admission check until the app is
   published.

The source enrollment policy prevents an unverified or unlisted account from
creating an Authentik user. The source authentication policy checks the current
Google claim on every source login and blocks an account that becomes
unverified or is removed from the allowlist. Source-specific identifiers remain
enabled, so Authentik does not link accounts merely because their email
addresses match. These shared default policies apply to every source using the
default source flows. If a second external identity source is added, give it
dedicated flows and policies rather than sharing this Google-specific check.

## Pilot Native OIDC with Grafana

Use Grafana as a low-risk first native OIDC application. Keep Grafana's local
administrator enabled until OAuth login, access removal, and local recovery
have all been tested.

1. In Authentik Admin, open **Applications** > **Applications** > **New
   Application**.
2. Configure the application:

   | Field | Value |
   |---|---|
   | Name | `Grafana` |
   | Slug | `grafana` |
   | Launch URL | `https://grafana.example.com/` |

3. Select **OAuth2/OIDC** as the provider type and configure:

   | Field | Value |
   |---|---|
   | Client type | Confidential |
   | Redirect URI | `https://grafana.example.com/login/generic_oauth` |
   | Authentication flow | `default-authentication-flow` |
   | Authorization flow | `default-provider-authorization-implicit-consent` |
   | Grant types | Authorization Code only |
   | Scope mappings | Keep `openid`, `profile`, and `email` |

   Replace `grafana.example.com` with Grafana's permanent HTTPS hostname. The
   implicit-consent flow suppresses a redundant consent page for a trusted
   first-party app. It does not enable the insecure OAuth implicit grant.
4. Create the application and store its generated client ID and client secret
   only in the password vault and ignored host configuration. Do not paste them
   into chat or tracked files.
5. On the Grafana application's **Policy / Group / User Bindings** tab, bind
   the ordinary `monitoring` group. This controls who can authorize Grafana.
6. Add each approved test user to `monitoring` under **Directory** > **Users**.
   Do not add external users to `admins` merely to grant Grafana access.

Do not set Grafana as the Authentik default application. This setup keeps
Homepage available without login on the LAN and VPN, and users open protected
applications through their direct URLs.

### Configure Grafana

The Grafana Compose definition reads the OIDC client ID from ignored host
configuration and mounts the client secret as a Docker secret file. On the
Grafana host:

1. Add these values to `config/docker/<host>/.env.grafana`:

   ```dotenv
   GRAFANA_AUTHENTIK_CLIENT_ID=<Authentik Grafana client ID>
   GRAFANA_AUTHENTIK_CLIENT_SECRET_PATH=${INFRA_CONFIG_PATH}/docker/<host>/grafana/authentik-client-secret
   ```

2. Create `config/docker/<host>/grafana/authentik-client-secret`, paste only
   the Authentik Grafana client secret into it, and set its mode to `0600`. Set
   its parent directory mode to `0700`.
3. Recreate only Grafana:

   ```bash
   scripts/labctl.py service recreate monitoring/grafana
   ```

Grafana uses the Authorization Code flow with PKCE, keeps its local login form
available, and does not grant Grafana administrator privileges from any OAuth
claim. The Authentik application's `monitoring` group binding remains the
access gate.

Use these endpoint values when troubleshooting the Generic OAuth configuration:

| Setting | Value |
|---|---|
| Authorization URL | `https://sso.example.com/application/o/authorize/` |
| Token URL | `https://sso.example.com/application/o/token/` |
| User info URL | `https://sso.example.com/application/o/userinfo/` |
| Sign-out redirect URL | `https://sso.example.com/application/o/grafana/end-session/` |

Do not remove local administrator login after Google works. Google is a normal
login path, not the emergency recovery path.

## Add Applications Safely

The canonical end-to-end onboarding procedure is
`docker/security/authentik/app-onboarding.md`. This section provides deployment
history and additional Authentik-specific context; keep operational steps
aligned with the canonical application onboarding guide.

### Managed Application Manifest

`docker/security/authentik/config/apps.yaml` declares Grafana OIDC and the
Uptime Kuma and Adminer Traefik ForwardAuth applications. Use
`scripts/authentik-apps.py` to create only missing resources. It is a
self-contained `uv` script, so no manually activated Python environment is
needed. Its default is a read-only plan; `--apply` is required before it makes
any change.
It never deletes resources or overwrites an existing application, group binding,
or outpost assignment. For existing OIDC providers, `--apply` reconciles only
declared scope mappings and signing keys.

On the Authentik Docker host, create these ignored files under
`config/docker/<host>/`:

```dotenv
# .env.authentik
AUTHENTIK_URL=https://sso.example.com
```

### Create the Application Helper API Token

Use a dedicated service account instead of an administrator's personal token.
`docker/security/authentik/config/blueprints/authentik-apps-operator.yaml`
declaratively maintains the `authentik-apps-operator` role, its least-privilege
permissions, and membership for the `authentik-apps` service account. Do not
edit those permissions manually; deploy the Authentik stack after changing the
blueprint. Authentik discovers mounted blueprints and reapplies them when they
change.

Create the service account and its token in the Authentik admin interface:

1. Go to **Directory > Users** and create a service account named
   `authentik-apps` with an expiry appropriate for the environment. Do not make
   it a superuser.
2. Create an API token for the service account. Give it a descriptive name,
   make it expiring, and copy its value when Authentik displays it. Authentik
   shows the plaintext token only once.

The helper's default plan needs the `view` permissions. `--apply` additionally
needs the listed `add` permissions. It needs Outpost `change` only for a
ForwardAuth application; an OIDC-only manifest does not need it. It never needs
delete permissions. Remove that permission from the blueprint if its manifest
will only manage OIDC applications.

```bash
# Restrict both files to the Docker-host administrator.
mkdir -p config/docker/<host>/authentik
chmod 700 config/docker/<host>/authentik
chmod 600 config/docker/<host>/authentik/api-token
chmod 600 config/docker/<host>/grafana/authentik-client-secret
```

Create the API token in the Authentik admin interface and store only its value
in `authentik/api-token` with a local editor; do not set it in a shell
environment, Compose label, tracked file, or command line. The host
`authentik/` directory is ignored by the repository's example configuration.
The Grafana client ID remains in the ignored `.env.grafana` file described
above and its secret remains in the existing ignored secret file.

Validate the resolved configuration first:

```bash
scripts/authentik-apps.py
```

Review the output, back up Authentik, then create the missing resources:

```bash
scripts/authentik-apps.py --apply
```

The helper defaults to the `config/docker/localhost` symlink. It loads
`config/docker/.env`, the selected host `.env`, common and host `.env.authentik`,
then common and host `.env.<application-slug>` files for every manifest entry.
Pass `--host <name>` only to select a different configured host. It rejects
unsafe slugs, non-HTTPS Authentik URLs, and unresolved manifest variables before
it reads the token or makes an API request. Plan mode then uses read-only API
requests to report the actual create/no-change actions.

For each ForwardAuth application, the helper plans and, with `--apply`, adds its
callback hostname to `docker/security/traefik/config/dynamic/authentik-outposts.yml`.
Traefik watches that file-provider directory and applies the route without
restarting Authentik. The helper never deletes or rewrites existing callback
routes.

For OIDC it creates the provider with Authorization Code, exact redirect URIs,
and Authentik's managed `openid`, `profile`, and `email` mappings. For
ForwardAuth it creates a `forward_single` proxy provider, creates the
application, binds the declared group, and adds that provider to the named
embedded proxy outpost. Existing objects are treated as authoritative: the
helper reports no error for a compatible repeated run but does not reconcile
drift. Change existing objects through the Authentik admin UI (or after
reviewing a future, schema-tested update implementation).

Use one of these patterns per application:

| Application capability | Use |
|---|---|
| Native OIDC/OAuth2 | Create a dedicated Authentik OAuth2/OIDC provider and application |
| Browser-only app without OIDC | Use an Authentik proxy provider and Traefik ForwardAuth |
| Trusted header support | Use a proxy provider only after direct access and spoofed headers are blocked |
| API, CLI, device, or non-HTTP protocol | Use the application's API key, app password, mTLS, SSH key, or native credentials |

Prefer native OIDC. Do not place interactive ForwardAuth in front of an API
that needs machine clients, mobile clients, or WebSocket callbacks unless those
clients have been tested.

For every new application:

1. Use exact redirect URIs.
2. Bind access to the smallest necessary group.
3. Keep a local application administrator initially.
4. Test private-browser login, logout, access removal, and direct-port bypass.
5. Test mobile, desktop, CLI, API, and device clients where applicable.
6. Back up the application before changing identity linking or disabling local
   login.

## Ongoing Operations

- Pin Authentik and PostgreSQL image versions.
- Review Authentik release notes before upgrades.
- Back up and restore-test the database regularly.
- Rotate leaked or Docker-label-exposed credentials.
- Check that direct host ports do not bypass Traefik protection.
- Keep at least one tested local administrator and MFA recovery method.
- Update application and group documentation whenever access changes.

## References

- [Authentik Docker Compose installation](https://docs.goauthentik.io/install-config/install/docker-compose/)
- [Authentik user credentials and MFA devices](https://docs.goauthentik.io/users-sources/user/user-interface/#credentials)
- [Authentik Google social source](https://docs.goauthentik.io/docs/users-sources/sources/social-logins/google/)
- [Authentik OAuth2/OIDC provider](https://docs.goauthentik.io/docs/add-secure-apps/providers/oauth2/)
- [Authentik Traefik ForwardAuth](https://docs.goauthentik.io/docs/add-secure-apps/providers/proxy/server_traefik)
