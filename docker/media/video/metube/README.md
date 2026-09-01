# MeTube Authentik ForwardAuth

Authentik ForwardAuth protects MeTube's browser UI for the `media` group. Its
cookie file is a host credential and must remain in ignored host configuration.

## Setup

```bash
scripts/authentik-apps.py --application metube --apply
scripts/labctl.py service recreate media/video/metube
```

Keep `localaccess-authentik@file` on the router and do not publish MeTube's UI
port. Browser extensions and shortcuts that cannot follow interactive redirects
need a deliberate alternative, not a broadly unauthenticated route.

## Verify

Confirm a `media` member can use the UI, a non-member is denied, downloads work,
group removal applies after session refresh, and no direct UI route exists.
