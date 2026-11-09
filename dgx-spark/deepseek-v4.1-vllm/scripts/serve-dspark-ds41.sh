#!/usr/bin/env bash
# Serve DeepSeek-V4.1-Flash (FP8) across both DGX Sparks with DSpark vLLM recipe.
# API: http://<node1>:8888/v1
#
# Wraps ~/dspark-ds41/start-deepseek-v4.1-flash-dspark.sh with a drop_caches sidecar on
# both nodes during boot. Without it, node 1's weight load wedged for ~20 min inside
# cuMemcpyHtoDAsync (GB10 driver does not reclaim page cache fast enough; MemFree pinned at 8 GB).
#
#   ./serve-dspark-ds41.sh          start (worker first, then head; runs from node 1)
#   ~/dspark-ds41/stop-deepseek-v4.1-flash-dspark.sh    stop both ranks
set -euo pipefail
NODES=(192.168.100.10 192.168.100.11)
# Image with V4.1 support: eugr/spark-vllm-b12x:latest (2026-11-02)
# Contains DeepseekV41ForCausalLM, DSpark support, B12X kernels, deepseek_v41 tokenizer
IMG=${DSPARK_VLLM_IMAGE:-eugr/spark-vllm-b12x:latest}
REPO=/home/nielsbantilan/dspark-ds41

sidecar_up() {
  for h in "${NODES[@]}"; do
    ssh "$h" "docker rm -f dsv41-dropcaches >/dev/null 2>&1; docker run -d --rm --privileged --name dsv41-dropcaches \
      --entrypoint sh $IMG -c 'while true; do sync; echo 3 > /proc/sys/vm/drop_caches; sleep 5; done' >/dev/null"
  done
}
sidecar_down() {
  for h in "${NODES[@]}"; do ssh "$h" 'docker rm -f dsv41-dropcaches >/dev/null 2>&1' || true; done
}
trap sidecar_down EXIT

# llama.cpp RPC server on node 2 would compete for unified memory.
ssh 192.168.100.11 'pkill -x ggml-rpc-server' || true

sidecar_up
cd "$REPO"
WAIT_ATTEMPTS="${WAIT_ATTEMPTS:-160}" ./start-deepseek-v4.1-flash-dspark.sh "$@"
