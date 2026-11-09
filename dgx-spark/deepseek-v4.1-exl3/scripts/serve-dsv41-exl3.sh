#!/usr/bin/env bash
# Serve 0xSero/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw across both DGX Sparks (TP=2) with sudoingX's recipe
# (vLLM 6e517b15 + patch series + vllm_exl3_moe plugin, CI-built image pinned by digest).
# API: http://<node1>:8888/v1, model name deepseek-v4-flash-0731 (same as the V4 service, so clients don't change).
#
# Wraps ~/dsv41-0xsero/recipe/scripts/launch/dsv41_tp2.sh (recipe @ cc59c360, unmodified) with our site values:
#   - the fabric port that is up on our nodes (enp1s0f1np1 / rocep1s0f1); the recipe defaults to the f0 port, which is
#     down here. The recipe derives the RoCE v2 GID index from the port's IPv4 (index 3 on ours).
#   - NCCL_MAX_NCHANNELS=8 for node 2's memory-region ceiling (../../deepseek-v4-vllm/README.md §7.5).
#   - a drop_caches sidecar on both nodes during boot only. The recipe drops page cache with `sudo -n`, which our nodes
#     don't allow; and dropping caches while serving evicts Engram's hot rows (recipe README), so it stops at exit.
#
#   ./serve-dsv41-exl3.sh up                 start both ranks, wait for /v1/models (stop V4 first: same GPUs, same port)
#   ./serve-dsv41-exl3.sh down | status | logs [head|worker]
set -euo pipefail
NODES=(192.168.100.10 192.168.100.11)
RECIPE=${RECIPE:-$HOME/dsv41-0xsero/recipe}
SIDECAR_IMG=ghcr.io/anemll/dspark-vllm-gx10:0.1.1   # any image on both nodes with sh; this is V4's
export IMAGE=${IMAGE:-ghcr.io/sybil-solutions/deepseek-v4.1-flash-exl3-spark@sha256:5817414f92e9bec0406dfc4575e16b282209f0cb1ead16fe53d51bac7ac9e9e4}
export HEAD=${NODES[0]} WORKER=${NODES[1]}
export FAB_IF=${FAB_IF:-enp1s0f1np1} FAB_HCA=${FAB_HCA:-rocep1s0f1}
export MODEL_DIR=${MODEL_DIR:-$HOME/models/dsv41-1017-exl3}
export SERVED=${SERVED:-deepseek-v4-flash-0731} PORT=${PORT:-8888}
export DOCKER_ENV="NCCL_MAX_NCHANNELS=8${DOCKER_ENV:+ $DOCKER_ENV}"

sidecar_up() {
  for h in "${NODES[@]}"; do
    ssh "$h" "docker rm -f dsv41-dropcaches >/dev/null 2>&1; docker run -d --rm --privileged --name dsv41-dropcaches \
      --entrypoint sh $SIDECAR_IMG -c 'while true; do sync; echo 3 > /proc/sys/vm/drop_caches; sleep 5; done' >/dev/null"
  done
}
sidecar_down() {
  for h in "${NODES[@]}"; do ssh "$h" 'docker rm -f dsv41-dropcaches >/dev/null 2>&1' || true; done
}

if [ "${1:-status}" = up ]; then
  if curl -sf -m 5 "http://${NODES[0]}:$PORT/v1/models" >/dev/null 2>&1; then
    echo "something already serves :$PORT (stop deepseek-v4-flash.service first)" >&2; exit 1
  fi
  ssh "${NODES[1]}" 'pkill -x ggml-rpc-server' || true   # llama.cpp RPC on node 2 competes for unified memory
  trap sidecar_down EXIT
  sidecar_up
fi
"$RECIPE/scripts/launch/dsv41_tp2.sh" "$@"
