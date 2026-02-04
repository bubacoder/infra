# Ubuntu VM

https://ubuntu.com/server

## Installation

There are multiple methods to install the OS.

### Cloud Image with Cloud-init (Recommended)

This is the recommended method for fully automated VM creation with zero manual interaction.

**How it works:**
- Downloads pre-installed Ubuntu cloud image (~700MB vs ~2.5GB ISO)
- Imports the image directly as a VM disk (no installer needed)
- Cloud-init configures hostname, users, SSH keys, and packages on first boot
- VM boots directly to a configured state in ~30-60 seconds

**Quickstart:**

- Setup SSH access to the PVE host
- Edit `create-ubuntu-cloud-vm.sh` to match the desired configuration
- Execute to deploy an Ubuntu Server VM:
```bash
ssh root@proxmox "bash -s" -- < create-ubuntu-cloud-vm.sh
```
- Start the VM - it will boot directly to a ready-to-use system

**Verify cloud-init status:**
```bash
ssh buba@<vm-ip> "cloud-init status --wait"
```

**Limitations:**
- Uses default disk layout (cannot customize partitions/LVM like autoinstall)
- If you need custom storage layout, use the autoinstall method below

**References:**
- [Proxmox - Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)
- [Cloud-init Documentation](https://cloudinit.readthedocs.io/)

### Automatic install - "autoinstall"

Use this method when you need custom storage layouts (LVM, partitions, RAID).

**Note:** This method still requires a manual confirmation at the VM console ("Continue with autoinstall?" prompt) unless you modify the installation ISO to include the `autoinstall` kernel parameter.

**Quickstart:**

- Setup SSH access to the PVE host
- Edit `create-ubuntu-server-vm.sh` to match the desired configuration
- Execute to deploy an Ubuntu Server VM:
```bash
ssh root@proxmox "bash -s" -- < create-ubuntu-server-vm.sh
```
- Start the VM and confirm the installation ("Continue with autoinstall?" prompt)

**Details:**

[Introduction to autoinstall](https://canonical-subiquity.readthedocs-hosted.com/en/latest/intro-to-autoinstall.html)

> Automatic Ubuntu installation is performed with the autoinstall format. You might also know this feature as "unattended", "hands-off" or "preseeded" installation.
> Automatic installation lets you answer all configuration questions ahead of time with an autoinstall configuration and lets the installation process run without any interaction.

Good guides describing autoinstall's possibilities:
- [How to write and perform Ubuntu unattended installations with autoinstall](https://linuxconfig.org/how-to-write-and-perform-ubuntu-unattended-installations-with-autoinstall)
- [How to automate a bare metal Ubuntu 22.04 LTS installation](https://www.jimangel.io/posts/automate-ubuntu-22-04-lts-bare-metal/)

**Notes:**
> When any Ubuntu system is installed (manual or automated) an autoinstall file for repeating the installation is created at `/var/log/installer/autoinstall-user-data`.

> Even if a fully non-interactive autoinstall config is found, the server installer will ask for confirmation before writing to the disks unless "autoinstall" is present on the kernel command line. This is to make it harder to accidentally create a USB stick that will reformat a machine it is plugged into at boot. ([source](https://ubuntu.com/server/docs/install/autoinstall))

To achieve fully unattended autoinstall, you would need to modify the installation ISO's GRUB configuration to include the `autoinstall` kernel parameter.

### Manual install

This method creates a VM, downloads the installation media and attaches it for manual installation.

- Setup SSH access to the PVE host
- Edit `create-ubuntu-server-vm.sh` to match the desired configuration and set: `AUTOINSTALL=false`
- Execute to deploy an Ubuntu Server VM:
```bash
ssh root@proxmox "bash -s" -- < create-ubuntu-server-vm.sh
```
- Start the VM and use the installer

## Method Comparison

| Method      | Manual Interaction | Install Time | Storage Customization |
| ----------- | ------------------ | ------------ | --------------------- |
| Cloud Image | None               | ~1 min       | Default layout only   |
| Autoinstall | One confirmation   | ~10-15 min   | Full control          |
| Manual      | Full installation  | ~15-30 min   | Full control          |
