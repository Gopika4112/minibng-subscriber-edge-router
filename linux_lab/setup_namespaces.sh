#!/usr/bin/env bash
set -e

BRIDGE="minibng-br0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACES=("user101" "user102" "user103")
IPS=("10.10.0.101" "10.10.0.102" "10.10.0.103")

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo"
  exit 1
fi

# Start from a clean state so the lab can be safely re-run.
bash "${SCRIPT_DIR}/cleanup_namespaces.sh"

# The bridge acts as the MiniBNG edge/gateway for all subscriber namespaces.
ip link add name "${BRIDGE}" type bridge
ip addr add 10.10.0.1/24 dev "${BRIDGE}"
ip link set "${BRIDGE}" up

# Enable IPv4 forwarding for lab extensions that route beyond the bridge.
sysctl -w net.ipv4.ip_forward=1

create_subscriber_namespace() {
  local namespace="$1"
  local ip_address="$2"
  local subscriber_iface="veth-${namespace}"
  local edge_iface="edge-${namespace}"

  # Create the namespace that represents a broadband subscriber.
  ip netns add "${namespace}"

  # Create a veth pair: one end goes into the subscriber namespace, and the
  # edge end stays on the host and attaches to the MiniBNG bridge.
  ip link add "${subscriber_iface}" type veth peer name "${edge_iface}"
  ip link set "${subscriber_iface}" netns "${namespace}"

  # Attach the host-side edge interface to the bridge.
  ip link set "${edge_iface}" master "${BRIDGE}"
  ip link set "${edge_iface}" up

  # Configure the subscriber-side interface and default route.
  ip netns exec "${namespace}" ip addr add "${ip_address}/24" dev "${subscriber_iface}"
  ip netns exec "${namespace}" ip link set lo up
  ip netns exec "${namespace}" ip link set "${subscriber_iface}" up
  ip netns exec "${namespace}" ip route add default via 10.10.0.1
}

for index in "${!NAMESPACES[@]}"; do
  create_subscriber_namespace "${NAMESPACES[$index]}" "${IPS[$index]}"
done

echo "MiniBNG namespace lab is ready"
echo
echo "Namespaces:"
ip netns list
echo
echo "Bridge:"
ip link show "${BRIDGE}"
echo
echo "Bridge members:"
bridge link
echo
echo "IP addresses:"
ip addr show "${BRIDGE}"
for namespace in "${NAMESPACES[@]}"; do
  echo
  echo "${namespace}:"
  ip netns exec "${namespace}" ip addr
done
