Web GUI for youtube-dl (using the yt-dlp fork) with playlist support. Allows you to download videos from YouTube and dozens of other sites

Links:
- Source: [GitHub - alexta69/metube: Self-hosted video downloader for YouTube and other sites (web UI for yt-dlp)](https://github.com/alexta69/metube)
- Supported sites: [yt-dlp/supportedsites.md at master · yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- Browser plugin for Chrome/Chromium based browsers: [MeTube Downloader](https://chromewebstore.google.com/detail/metube-downloader/fbmkmdnlhacefjljljlbhkodfmfkijdh)
- Browser plugin for Firefox: [MeTube Downloader – Get this Extension for 🦊 Firefox (en-US)](https://addons.mozilla.org/en-US/firefox/addon/metube-downloader/)

# Authentik ForwardAuth

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
