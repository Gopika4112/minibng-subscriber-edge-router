#!/usr/bin/env bash
set -e

echo "Namespaces:"
ip netns list

echo
echo "Bridge:"
ip link show minibng-br0

echo
echo "Bridge members:"
bridge link

echo
echo "Bridge IP address:"
ip addr show minibng-br0

for namespace in user101 user102 user103; do
  echo
  echo "${namespace} IP addresses:"
  ip netns exec "${namespace}" ip addr

  echo
  echo "${namespace} routes:"
  ip netns exec "${namespace}" ip route
done
