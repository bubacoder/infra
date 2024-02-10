+++
title = "Proxmox VE"
weight = 3
+++

https://www.proxmox.com/en/downloads/proxmox-virtual-environment

VM config: `/etc/pve/qemu-server/100.conf`

https://tteck.github.io/Proxmox/

Post-install configuration:
- https://pve.proxmox.com/wiki/Package_Repositories#sysadmin_no_subscription_repo
- TODO


## Kernel Samepage Merging

https://docs.kernel.org/admin-guide/mm/ksm.html

`watch cat /sys/kernel/mm/ksm/pages_sharing`
Note: a page is 4096 bytes

## Windows VM

▶️ [How to Virtualise an Existing Windows Install using Proxmox](https://www.youtube.com/watch?v=eFDcCxRS5Xk)
https://pve.proxmox.com/wiki/Windows_VirtIO_Drivers
https://pve.proxmox.com/wiki/Dynamic_Memory_Management

## LXC Containers

`pct enter <CTID>`

### Create a container

proxmox_lxc_pct_provisioner.sh
https://gist.github.com/tinoji/7e066d61a84d98374b08d2414d9524f2
`pct create <id> /var/lib/vz/template/cache/centos-7-default_20170504_amd64.tar.xz ...`

```
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

```
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




### Cannot mount a SMB share

```
mount error(1): Operation not permitted
Refer to the mount.cifs(8) manual page (e.g. man mount.cifs) and kernel log messages (dmesg)
```

> You can't mount any SMB/NFS share inside a unprivileged LXC. Thats only possible with the unsecure privileged LXCs after enabling the CIFS or NFS features under your LXC -> Options -> Features. If you want to use shares with a unprivileged LXC you need to mount the shares on your host and then use bind-mounts to bring the mounted share from your host into your LXC.
