#!/usr/bin/env bash
# Serve DeepSeek-V4-Flash-0731 (FP8 + MXFP4 experts) across both DGX Sparks with the
# MiaAI DSpark vLLM recipe (Anemll 0.1.1 image, TP=2, DSpark k=5). API: http://<node1>:8888/v1
#
# Wraps ~/dspark-ds4-0731/start-deepseek-v4-flash-dspark.sh with a drop_caches sidecar on
# both nodes during boot. Without it, node 1's weight load wedged for ~20 min inside
# cuMemcpyHtoDAsync (GB10 driver does not reclaim page cache fast enough; MemFree pinned at 8 GB).
#
#   ./serve-dspark-ds4.sh          start (worker first, then head; runs from node 1)
#   ~/dspark-ds4-0731/stop-deepseek-v4-flash-dspark.sh    stop both ranks
set -euo pipefail
NODES=(192.168.100.10 192.168.100.11)
IMG=ghcr.io/anemll/dspark-vllm-gx10:0.1.1
REPO=/home/nielsbantilan/dspark-ds4-0731

sidecar_up() {
  for h in "${NODES[@]}"; do
    ssh "$h" "docker rm -f dsv4-dropcaches >/dev/null 2>&1; docker run -d --rm --privileged --name dsv4-dropcaches \
      --entrypoint sh $IMG -c 'while true; do sync; echo 3 > /proc/sys/vm/drop_caches; sleep 5; done' >/dev/null"
  done
}
sidecar_down() {
  for h in "${NODES[@]}"; do ssh "$h" 'docker rm -f dsv4-dropcaches >/dev/null 2>&1' || true; done
}
trap sidecar_down EXIT

# llama.cpp RPC server on node 2 would compete for unified memory.
ssh 192.168.100.11 'pkill -x ggml-rpc-server' || true

sidecar_up
cd "$REPO"
WAIT_ATTEMPTS="${WAIT_ATTEMPTS:-160}" ./start-deepseek-v4-flash-dspark.sh "$@"
