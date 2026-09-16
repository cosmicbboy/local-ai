#!/usr/bin/env bash
# Run this from your Mac right after power-cycling both DGX Spark boxes.
#
# Waits for flint-dgx (head) and agate-dgx (worker) to come back up on
# Tailscale, waits for the head node to see the worker over the private RoCE
# fabric, then restarts the deepseek-v4-flash service and polls /health until
# the API is actually serving (systemd reporting "active (exited)" does NOT
# mean the engine is ready -- see dgx-spark/deepseek-v4-vllm/README.md §6.2).
#
# Usage: dgx-spark/deepseek-v4-vllm/scripts/restart-after-reboot.sh

set -euo pipefail

HEAD_TS_HOST="100.70.69.103"      # flint-dgx, Tailscale IP
WORKER_TS_HOST="100.119.213.60"   # agate-dgx, Tailscale IP
WORKER_FABRIC_IP="192.168.100.11" # agate-dgx, RoCE fabric IP (as seen from the head node)
SERVICE="deepseek-v4-flash"

SSH="ssh -o ConnectTimeout=5 -o BatchMode=yes"

wait_for() {
  local desc="$1"; shift
  until "$@" >/dev/null 2>&1; do
    echo "  $desc not ready yet, retrying in 10s..."
    sleep 10
  done
  echo "  $desc: up"
}

echo "Waiting for both nodes to be reachable over Tailscale..."
wait_for "flint-dgx (head)"   $SSH "$HEAD_TS_HOST" true
wait_for "agate-dgx (worker)" $SSH "$WORKER_TS_HOST" true

echo "Waiting for head -> worker fabric (ssh + docker)..."
wait_for "fabric" $SSH "$HEAD_TS_HOST" "$SSH $WORKER_FABRIC_IP 'docker info'"

echo "Restarting $SERVICE (full cold restart, ~6-10 min typical)..."
$SSH "$HEAD_TS_HOST" "systemctl --user restart $SERVICE"

echo "Polling /health..."
for i in $(seq 1 120); do
  code=$($SSH "$HEAD_TS_HOST" "curl -s -o /dev/null -w '%{http_code}' localhost:8888/health" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo "Healthy after $((i * 15))s."
    exit 0
  fi
  echo "  not ready yet (http $code), $((i * 15))s elapsed..."
  sleep 15
done

echo "Timed out after 30min waiting for /health to return 200." >&2
echo "Check: ssh $HEAD_TS_HOST \"journalctl --user -u $SERVICE -f\"" >&2
exit 1
