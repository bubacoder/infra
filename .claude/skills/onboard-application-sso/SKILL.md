---
name: onboard-application-sso
description: >
  Onboard or migrate an application to Authentik SSO in this homelab repository using native
  OIDC/OAuth2 or Traefik ForwardAuth. Use when asked to add SSO, Authentik, OIDC, OAuth login,
   proxy authentication, or ForwardAuth.
---

# Onboard Application SSO

Canonical reference: `docker/security/authentik/app-onboarding.md`.

1. Read the canonical reference before editing anything.
2. Inspect the deployed Compose definition and current access path.
3. Retrieve current official documentation for the application's deployed
   version. Confirm native OIDC/OAuth2 support, exact callbacks, client impacts,
   and recovery; do not rely on memory.
4. Prefer native OIDC. Use ForwardAuth only when native integration is unsuitable.
5. Add the application to `docker/security/authentik/config/apps.yaml`; run the
   helper's read-only plan and show high-impact changes before `--apply`.
6. Configure the application side exactly as documented in the canonical
   reference and official application docs.
7. Run repository validation, deploy only affected services, and complete the
   acceptance checklist. Stop and restore the previous middleware if access or
   recovery fails.

Never expose, print, or commit API tokens or client secrets. Never delete
Authentik resources or disable local recovery as part of onboarding.
