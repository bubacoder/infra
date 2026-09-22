Synchronize AdGuard Home config to replicas

Prerequisites: Both the origin instance and replica(s) must be initially set up with AdguardHome via the AdguardHome installation wizard.

Note:
> While Windows will prioritize the first DNS provider, systemd-based Linux distributions will enact a "parallel probe" of all servers and pick the fastest responder.
> The same goes for Android, macOS, and iOS, where all servers are questioned at once, and the fastest to answer is considered correct.
See more: https://www.xda-developers.com/two-pi-holes-spare-resources-recommend/

Links:
- Source: https://github.com/bakito/adguardhome-sync
