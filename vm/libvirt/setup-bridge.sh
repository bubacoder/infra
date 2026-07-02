#!/usr/bin/env bash
set -euo pipefail

# Creates a NetworkManager bridge over a physical NIC so libvirt VMs can get
# IPs directly from the LAN router. Idempotent: safe to run multiple times.
#
# Usage: sudo ./setup-bridge.sh [BRIDGE_NAME [PHYSICAL_IF]]
# Defaults: bridge=br0, physical interface=eno1
#
# Note: after running this, the desktop network manager applet (taskbar "Networks"
# popup) will show "No available connections". This is cosmetic — the physical NIC
# becomes a bridge slave which NM applets don't display. The network works normally.

BRIDGE_NAME="${1:-br0}"
PHYSICAL_IF="${2:-eno1}"
SLAVE_CON="${BRIDGE_NAME}-slave-${PHYSICAL_IF}"

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (use sudo)" >&2
    exit 1
fi

command -v nmcli >/dev/null || { echo "Missing required tool: nmcli" >&2; exit 1; }

conn_exists() { nmcli connection show "$1" &>/dev/null; }

# If the bridge interface is already up and owns the physical NIC, nothing to do
if ip link show "${BRIDGE_NAME}" &>/dev/null && \
   ip link show "${PHYSICAL_IF}" 2>/dev/null | grep -q "master ${BRIDGE_NAME}"; then
    echo "Bridge ${BRIDGE_NAME} is already active with ${PHYSICAL_IF} enslaved. Nothing to do."
    exit 0
fi

echo "Setting up bridge ${BRIDGE_NAME} over ${PHYSICAL_IF}..."

if ! conn_exists "${BRIDGE_NAME}"; then
    echo "Creating bridge connection ${BRIDGE_NAME}..."
    # Clone the physical NIC's MAC so the router assigns the same IP as before
    phys_mac=$(cat "/sys/class/net/${PHYSICAL_IF}/address")
    nmcli connection add type bridge ifname "${BRIDGE_NAME}" con-name "${BRIDGE_NAME}" \
        802-3-ethernet.cloned-mac-address "${phys_mac}"
fi

if ! conn_exists "${SLAVE_CON}"; then
    echo "Creating slave connection ${SLAVE_CON}..."
    nmcli connection add type bridge-slave ifname "${PHYSICAL_IF}" master "${BRIDGE_NAME}" con-name "${SLAVE_CON}"
fi

# Find the active connection on the physical NIC (if any) and bring it down
ACTIVE_CON=$(nmcli -g NAME,DEVICE connection show --active | grep ":${PHYSICAL_IF}$" | cut -d: -f1 || true)
if [[ -n "${ACTIVE_CON}" && "${ACTIVE_CON}" != "${SLAVE_CON}" ]]; then
    echo "Bringing down existing connection '${ACTIVE_CON}' on ${PHYSICAL_IF}..."
    nmcli connection down "${ACTIVE_CON}"
fi

echo "Activating bridge (brief connectivity drop expected)..."
nmcli connection up "${SLAVE_CON}"
nmcli connection up "${BRIDGE_NAME}"

echo ""
echo "Bridge ${BRIDGE_NAME} is up:"
ip addr show "${BRIDGE_NAME}" | grep -E "inet |state"
