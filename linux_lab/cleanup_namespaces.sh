#!/usr/bin/env bash
set -e

BRIDGE="minibng-br0"
NAMESPACES=("user101" "user102" "user103")
INTERFACES=(
  "veth-user101" "edge-user101"
  "veth-user102" "edge-user102"
  "veth-user103" "edge-user103"
)

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo"
  exit 1
fi

namespace_exists() {
  ip netns list | awk '{print $1}' | grep -qx "$1"
}

interface_exists() {
  ip link show "$1" >/dev/null 2>&1
}

for namespace in "${NAMESPACES[@]}"; do
  if namespace_exists "${namespace}"; then
    ip netns delete "${namespace}"
  fi
done

for interface in "${INTERFACES[@]}"; do
  if interface_exists "${interface}"; then
    ip link delete "${interface}"
  fi
done

if interface_exists "${BRIDGE}"; then
  ip link set "${BRIDGE}" down
  ip link delete "${BRIDGE}"
fi

echo "MiniBNG namespace lab cleaned up"
