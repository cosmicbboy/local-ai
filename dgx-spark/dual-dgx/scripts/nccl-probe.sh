#!/usr/bin/env bash
# Usage: ./nccl-probe.sh <rank 0|1> [size_mb]
RANK="${1:?rank}"; MB="${2:-1}"
IMG=aidendle94/sparkrun-vllm-ds4-gb10:production-v2
docker rm -f nccl-probe >/dev/null 2>&1 || true
docker run --rm --name nccl-probe \
  --gpus all --privileged --network host --ipc host --shm-size 10g \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --device /dev/infiniband:/dev/infiniband \
  -v /home/nielsbantilan/models:/models \
  -e NCCL_IB_DISABLE="${IB_DISABLE:-0}" -e NCCL_IB_HCA=rocep1s0f1 -e NCCL_IB_GID_INDEX=3 \
  -e NCCL_SOCKET_IFNAME=enp1s0f1np1 -e GLOO_SOCKET_IFNAME=enp1s0f1np1 \
  -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG="${DBG:-WARN}" \
  -e MASTER_ADDR=192.168.100.10 -e MASTER_PORT=29551 \
  -e RANK="$RANK" -e WORLD_SIZE=2 -e LOCAL_RANK=0 -e TEST_MB="$MB" -e PREALLOC_GB="${PREALLOC_GB:-0}" \
  --entrypoint /opt/env/bin/python "$IMG" /models/nccl_test.py
