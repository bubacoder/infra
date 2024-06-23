# OpenWrt VM

## OpenWrt on x86 hardware

https://openwrt.org/docs/guide-user/installation/openwrt_x86

Target, disk image selection:
- `64`: for modern PC hardware (anything from around 2007 onward), it is built for 64-bit capable computers and has support for modern CPU features. Choose this unless you have good reasons not to.
- `ext4-combined.img.gz`: This disk image uses a single read-write ext4 partition without a read-only squashfs root filesystem. As a result, the root partition can be expanded to fill a large drive (e.g. SSD/SATA/mSATA/SATA DOM/NVMe/etc). Features like Failsafe Mode or Factory Reset will not be available as they need a read-only squashfs partition in order to function. It has both the boot and root partitions and Master Boot Record (MBR) area with updated GRUB2.

## Setup

Based on [Run an OpenWRT VM on Proxmox VE](https://i12bretro.github.io/tutorials/0405.html) - [Video](https://www.youtube.com/watch?v=_fh7tnQW034)

1. Create VM containing ready-to-use OpenWRT with a script:
   - Option A: `ssh root@proxmox "bash -s" -- < create-openwrt-vm.sh`
   - Option B: Login to Proxmox Shell, copy `create-openwrt-vm.sh` and execute there.
   - Reference: [Proxmox VE `qm` command manual](https://pve.proxmox.com/pve-docs/qm.1.html)
2. Start the VM - `qm start ${VMID}`
3. Open the VM console
4. Wait for the text to stop scrolling and press Enter
5. Change root password with the command `passwd`
6. Configure the network and update packages:
```sh
# set the lan ip address, use something in the same subnet as your LAN
uci set network.lan.ipaddr='192.168.1.60'
# restart network services
service network restart
# check network status
ip addr
# update openwrt packages
opkg update
# install the luci web ui
opkg install luci
```

Open a new browser tab and navigate to http://IP-of-VM, http://192.168.1.60 in the example
At the login screen, enter the username `root` and the password set above > Click the Login button

## Use Serial Console:

TODO Test

```sh
ssh root@proxmox "qm terminal 200"
```

## Setup USB Wifi stick

TODO Describe steps

```
$ lsusb

MediaTek WiFi
https://linux-hardware.org/?id=usb:148f-
Device 'Ralink Technology MT7610U ("Archer T2U" 2.4G+5G WLAN Adapter')

Install kmod-mt76
```

## Configure as an Access Point

TODO Describe steps

Change LAN interface CIDR

Install packages:

```sh
opkg update
opkg install usbutils
```

