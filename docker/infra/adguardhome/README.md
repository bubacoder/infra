AdGuard Home is a network-wide software for blocking ads and tracking. After you set it up, it'll cover all your home devices, and you won't need any client-side software for that

To fix "listen tcp4 0.0.0.0:53: bind: address already in use" error on Ubuntu: disable `DNSStubListener` (see Ansible).  
Follow the AdguardHome installation wizard for first-time configuration. (Note: Firefox may not allow access to the admin interface)

Best practice:
 1. Configure two instances of AdGuard Home on two separate hardware
 2. Setup adguardhome-sync to sync the settings
 3. Specify both DNS servers in the router's DHCP settings

Links:
- Home: https://adguard.com/en/adguard-home/overview.html
- Image: https://hub.docker.com/r/adguard/adguardhome
