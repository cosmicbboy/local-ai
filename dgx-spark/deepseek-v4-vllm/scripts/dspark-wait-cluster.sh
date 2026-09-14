#!/usr/bin/env bash
# Pre-start gate for deepseek-v4-flash.service: block until both DGX Sparks are ready to
# form the TP=2 group (local docker, RoCE link up with its IPv4, node 2 reachable with
# docker + image). Gives up after TIMEOUT seconds so a missing node 2 fails the unit visibly.
set -uo pipefail
NODE2=192.168.100.11
IFACE=enp1s0f1np1
HCA=rocep1s0f1
IMG=ghcr.io/anemll/dspark-vllm-gx10:0.1.1
TIMEOUT="${TIMEOUT:-1800}"

local_ready() {
  docker info >/dev/null 2>&1 &&
  docker image inspect "$IMG" >/dev/null 2>&1 &&
  grep -q ACTIVE "/sys/class/infiniband/$HCA/ports/1/state" 2>/dev/null &&
  ip -4 addr show "$IFACE" 2>/dev/null | grep -q 'inet '
}
remote_ready() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$NODE2" \
    "docker info >/dev/null 2>&1 && docker image inspect $IMG >/dev/null 2>&1 &&
     grep -q ACTIVE /sys/class/infiniband/$HCA/ports/1/state &&
     ip -4 addr show $IFACE | grep -q 'inet '" >/dev/null 2>&1
}

start=$(date +%s)
until local_ready && remote_ready; do
  if (( $(date +%s) - start > TIMEOUT )); then
    echo "cluster not ready after ${TIMEOUT}s (local_ready=$(local_ready && echo y || echo n), node2_ready=$(remote_ready && echo y || echo n))" >&2
    exit 1
  fi
  sleep 10
done
# RoCE GIDs can populate a few seconds after the link comes up; the launcher resolves them.
sleep 15
echo "cluster ready after $(( $(date +%s) - start ))s"
