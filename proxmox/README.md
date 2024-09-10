# Proxmox VE

> Proxmox Virtual Environment is a complete, open-source server management platform for enterprise virtualization. It tightly integrates the KVM hypervisor and Linux Containers (LXC), software-defined storage and networking functionality, on a single platform. With the integrated web-based user interface you can manage VMs and containers, high availability for clusters, or the integrated disaster recovery tools with ease.

See more: https://www.proxmox.com/en/proxmox-virtual-environment/overview

Download: https://www.proxmox.com/en/downloads/proxmox-virtual-environment

- [Mobile Application](https://play.google.com/store/apps/details?id=com.proxmox.app.pve_flutter_frontend)
- [Scripts for Streamlining Your Homelab with Proxmox VE](https://tteck.github.io/Proxmox/)
- [Collection of tools for Proxmox](https://github.com/DerDanilo/proxmox-stuff)

Post-install configuration:
- https://pve.proxmox.com/wiki/Package_Repositories#sysadmin_no_subscription_repo
- TODO

## Virtual machines

VM config location: `/etc/pve/qemu-server/<ID>.conf`

## Create a VM via CLI

[Proxmox VE `qm` command manual](https://pve.proxmox.com/pve-docs/qm.1.html)

See example: `create-ubuntu-server-vm.sh`

### Kernel Samepage Merging (KSM)

KSM is a memory-saving de-duplication feature.
See more: https://docs.kernel.org/admin-guide/mm/ksm.html

Check KSM statistics: `watch cat /sys/kernel/mm/ksm/pages_sharing`  
Note: a page is 4096 bytes.

### Proxmox VM Watchdogs

[Proxmox VM Watchdogs](https://tompaw.net/proxmox-vm-watchdogs/)

### Force stop a VM

If Proxmox is stuck terminating a VM, as last resort, the `kvm` process can be forcefully terminated.

```sh
# Get the PID of the `kvm` process of the VM:
ps -auwx | grep <VMID>

# Force kill the `kvm` process:
kill -9 <KVM_PID>
```

## LXC Containers

Connect to terminal: `pct enter <CTID>`

### Create a container

proxmox_lxc_pct_provisioner.sh
https://gist.github.com/tinoji/7e066d61a84d98374b08d2414d9524f2
`pct create <id> /var/lib/vz/template/cache/centos-7-default_20170504_amd64.tar.xz ...`

CLI examples (TODO cleanup):

```sh
pct create <id> /data/template/cache/debian-11-standard_11.3-1_amd64.tar.zst \
 -ostype <debian|centos|etc> \ \
 -hostname <hostname> \
 -cores <cores>  \
 -memory <memory(MB)> \
 -swap <swap(MB)> \
 -rootfs volume=main:<sizeInGB> \
 -net0 name=eth0,bridge=<bridge>,ip=dhcp,hwaddr=<macaddr format 00:00:00:00:00:00> \
 -ssh-public-keys ~/.ssh/authorized_keys

pct start <id>
```

```sh
pct create <id> /var/lib/vz/template/cache/centos-7-default_20170504_amd64.tar.xz \
    -arch amd64 \
    -ostype <centos|ubuntu|etc> \
    -hostname <hostname> \
    -cores <cores> \
    -memory <memory(MB)> \
    -swap <swap(MB)> \
    -storage local-lvm \
    -password \
    -net0 name=eth0,bridge=<bridge>,gw=<gateway>,ip=<cidr>,type=veth  &&\
pct start <id> &&\
sleep 10 &&\
pct resize <id> rootfs <storage(ex: +4G)> &&\
pct exec <id> -- bash -c "yum update -y &&\
    yum install -y openssh-server &&\
    systemctl start sshd &&\
    useradd -mU hogeuser &&\
    echo "password" | passwd --stdin hogeuser"
```

### Issue: Cannot mount a SMB share

```
mount error(1): Operation not permitted
Refer to the mount.cifs(8) manual page (e.g. man mount.cifs) and kernel log messages (dmesg)
```

> You can't mount any SMB/NFS share inside a unprivileged LXC. Thats only possible with the unsecure privileged LXCs after enabling the CIFS or NFS features under your LXC -> Options -> Features. If you want to use shares with a unprivileged LXC you need to mount the shares on your host and then use bind-mounts to bring the mounted share from your host into your LXC.
