# Immich Authentik OIDC

Immich uses native OIDC for Authentik's `media` group. OAuth settings are
persisted in Immich's database and must be configured through its web
administration interface. Keep an existing local Immich administrator and
password login for recovery.

## Host Configuration

Create `config/docker/<host>/immich/authentik-client-secret` with mode `0600`.
Set these values in ignored `config/docker/<host>/.env.immich`:

```dotenv
IMMICH_AUTHENTIK_CLIENT_ID=immich
IMMICH_AUTHENTIK_SIGNING_KEY=<asymmetric Authentik signing-key UUID>
```

Create the Authentik application:

```bash
scripts/authentik-apps.py --application immich --apply
```

## Immich Settings

Sign in as the local administrator and set **Administration > Settings > OAuth**:

| Setting | Value |
|---|---|
| Enabled | Enabled |
| Issuer URL | `https://sso.<domain>/application/o/immich/` |
| Client ID | `immich` |
| Client secret | Ignored host secret value |
| Token endpoint auth method | `client_secret_post` |
| Scope | `openid email profile` |
| ID token signing algorithm | `RS256` |
| Userinfo signing algorithm | `none` |
| Storage label claim | `preferred_username` |
| Auto register | Enabled |
| Auto launch | Disabled |
| Mobile Redirect URI Override | `https://immich.<domain>/api/oauth/mobile-redirect` |

Leave role and quota claims unset so Authentik-created accounts remain ordinary
Immich users.

## Verify

Link an existing local account before making OIDC its normal login path. Test an
authorized `media` member, a non-member, local-password recovery, browser
logout, and mobile login/background uploads on every supported platform.

Immich is a high-performance self-hosted solution for backing up, organizing, and viewing photos and videos, with mobile clients, multi-user support, and local machine-learning search and recognition.

Links:
- Home: https://immich.app
- Source: https://github.com/immich-app/immich
- Docs: https://immich.app/docs/install/docker-compose
- Compose: https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml

TODO: Configure and regularly test 3-2-1 backups for the library and PostgreSQL volume; review metrics and SSO requirements.

GPU acceleration intentionally disabled for Immich on this host.

Our host has an AMD Vega gfx90c iGPU. Immich's ROCm/MIGraphX ML image causes
GPU hangs and kernel resets that interrupt the desktop display. Immich issue
#21648 documents gfx90c APU support being removed from current ROCm images:
https://github.com/immich-app/immich/issues/21648

GPU_COMPOSE_SUFFIX=amdgpu is shared by other services on this host, so retain
this no-op override to keep Immich on CPU until upstream support is verified.
