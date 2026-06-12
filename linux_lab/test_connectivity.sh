#!/usr/bin/env bash
set -e

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo"
  exit 1
fi

FAILED=0

run_ping_test() {
  local label="$1"
  local namespace="$2"
  local target="$3"

  if ip netns exec "${namespace}" ping -c 2 -W 2 "${target}" >/dev/null; then
    echo "PASS: ${label}"
  else
    echo "FAIL: ${label}"
    FAILED=1
  fi
}

echo "Testing subscriber to bridge gateway connectivity..."
run_ping_test "user101 -> gateway 10.10.0.1" "user101" "10.10.0.1"
run_ping_test "user102 -> gateway 10.10.0.1" "user102" "10.10.0.1"
run_ping_test "user103 -> gateway 10.10.0.1" "user103" "10.10.0.1"

echo
echo "Testing subscriber to subscriber connectivity..."
run_ping_test "user101 -> user102 10.10.0.102" "user101" "10.10.0.102"
run_ping_test "user102 -> user103 10.10.0.103" "user102" "10.10.0.103"
run_ping_test "user103 -> user101 10.10.0.101" "user103" "10.10.0.101"

if [[ "${FAILED}" -ne 0 ]]; then
  exit 1
fi

echo
echo "All MiniBNG namespace lab connectivity tests passed"
