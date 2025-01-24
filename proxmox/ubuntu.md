# Ubuntu VM

https://ubuntu.com/server

## Installation

There are multiple methods to install the OS.

### Manual install

This method creates a VM, downloads the installation media and attaches it.

- Setup SSH access to the PVE host
- Edit `create-ubuntu-server-vm.sh` to match the desired configuration and set: `AUTOINSTALL=false`
- Execute to deploy an Ubuntu Server VM:
```
ssh root@proxmox "bash -s" -- < create-ubuntu-server-vm.sh
```
- Start the VM and use the installer

### Automatic install - "autoinstall"

**Quickstart:**

In addition to the previous, this script also configures the installer for unattended install.

- Setup SSH access to the PVE host
- Edit `create-ubuntu-server-vm.sh` to match the desired configuration
- Execute to deploy an Ubuntu Server VM:
```
ssh root@proxmox "bash -s" -- < create-ubuntu-server-vm.sh
```
- Start the VM and confirm the installation ("Continue with autoinstall?" prompt)

**Details:**

[Introduction to autoinstall](https://canonical-subiquity.readthedocs-hosted.com/en/latest/intro-to-autoinstall.html)

> Automatic Ubuntu installation is performed with the autoinstall format. You might also know this feature as “unattended”, “hands-off” or “preseeded” installation.
> Automatic installation lets you answer all configuration questions ahead of time with an autoinstall configuration and lets the installation process run without any interaction.

Good guides describing autoinstall's possibilities:
- [How to write and perform Ubuntu unattended installations with autoinstall](https://linuxconfig.org/how-to-write-and-perform-ubuntu-unattended-installations-with-autoinstall)
- [How to automate a bare metal Ubuntu 22.04 LTS installation](https://www.jimangel.io/posts/automate-ubuntu-22-04-lts-bare-metal/)

**Notes:**
> When any Ubuntu system is installed (manual or automated) an autoinstall file for repeating the installation is created at `/var/log/installer/autoinstall-user-data`.

> Even if a fully non-interactive autoinstall config is found, the server installer will ask for confirmation before writing to the disks unless “autoinstall” is present on the kernel command line. This is to make it harder to accidentally create a USB stick that will reformat a machine it is plugged into at boot. ([source](https://ubuntu.com/server/docs/install/autoinstall))

The above article describes how to modify the install media for completely automatic installation.

### Import disk and use Cloud-init

Not yet implemented in the repo. See:
- [Proxmox - Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [Making a Ubuntu 24.04 VM Template for Proxmox and CloudInit](https://github.com/UntouchedWagons/Ubuntu-CloudInit-Docs)
