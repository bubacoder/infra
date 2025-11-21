# Runbooks

## Reinstall a Docker host

Note: This method is a bit unconventional but simplifies the deployment (and possible rollback) procedure a lot.
A new VM is used to deploy the OS, then the new system disk is attached to the old VM, which is already configured (MAC address, start at boot, start order, protection, USB devices...)

Hosts involved:
- `OLD`: perform on the old host
- `NEW`: perform on the new host
- `PVE`: perform on the Proxmox VE host

Steps:

- OLD: Install the new host using `proxmox/create-ubuntu-server-vm.sh`
- OLD: Apply Ansible using `ansible/apply-homelab.sh`
- OLD: Transfer container images to save bandwidth (Optional, see: [Docker](../docker/README.md))

Optional: copy **Server Host Key**, an RSA, ED25519, or ECDSA private key

- NEW: Create mount point: `mkdir -p /mnt/local/storage/`
- NEW: Add `/mnt/local/storage/` to `/etc/fstab`, e.g.: `/dev/disk/by-uuid/<uuid-of-storage> /mnt/local/storage ext4 defaults 0 0`
- NEW: Shutdown the VM

- PVE-NEW: OS Disk -> Disk Action -> Reassign Owner -> select OLD
- PVE-OLD: Options -> Boot Order -> Set the NEW disk to 1st position

- OLD: Shutdown, then start the VM

- OLD: Create symlink to repos: `ln -s /mnt/local/storage/repos ~/repos`
- OLD: Start services using `task docker:apply`

- PVE: After verification, delete the temporary VM
