#!/usr/bin/env bash
# Two-rank NCCL repro for the TP=2 fabric, in ~1 min instead of a 13-min vLLM boot.
#
# Why this exists: when rank 1 dies in ncclCommInitRank the only feedback loop used to be
# a full service start, which made bisecting NCCL env knobs impractical. This drives the
# same NCCL path with the same env as the serving container, but nothing else.
#
#   ./nccl-repro.sh baseline                            # reproduce the current failure
#   ./nccl-repro.sh cap NCCL_MAX_NCHANNELS=8            # test a candidate fix
#   ./nccl-repro.sh deep NCCL_MAX_NCHANNELS=8 PROBE_NGROUPS=20   # headroom check
#
# It stages nccl_probe.py (next to this script) to both nodes and runs it in the serving
# image. Any KEY=VAL argument is passed to both ranks, overriding the baseline env below.
# Logs land in $LOGDIR (default ~/vllm-debugging/logs).
#
# See README 7.5 for what this was built to chase: node 2's ~200-memory-region ceiling.
set -uo pipefail
LABEL="${1:?usage: nccl-repro.sh <label> [KEY=VAL ...]}"; shift || true

NODE1="${NODE1:-192.168.100.10}"
NODE2="${NODE2:-192.168.100.11}"
HCA="${HCA:-rocep1s0f1}"
IFACE="${IFACE:-enp1s0f1np1}"
IMG="${IMG:-ghcr.io/anemll/dspark-vllm-gx10:0.1.1}"
LOGDIR="${LOGDIR:-$HOME/vllm-debugging/logs}"
STAGE="${STAGE:-$HOME/.cache/nccl-probe}"
WAIT="${WAIT:-150}"          # seconds before declaring a rank hung
PROBE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/nccl_probe.py"

[ -f "$PROBE" ] || { echo "missing $PROBE" >&2; exit 1; }
mkdir -p "$LOGDIR"

# Baseline env mirrors .env.dspark's NCCL block, so a PASS here means the fabric is good.
BASE=(
  MASTER_ADDR="$NODE1" MASTER_PORT=25000
  NCCL_IB_HCA="$HCA" NCCL_SOCKET_IFNAME="$IFACE"
  NCCL_NET=IB NCCL_IB_DISABLE=0 NCCL_CUMEM_ENABLE=0
  NCCL_IGNORE_CPU_AFFINITY=1 NCCL_NVLS_ENABLE=0 NCCL_CROSS_NIC=1
  NCCL_IB_ADDR_FAMILY=AF_INET NCCL_IB_ROCE_VERSION_NUM=2
  NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=INIT,NET
  PROBE_NGROUPS=3
)
EXTRA=("$@")

# Stage the probe to both nodes (node 1 is local).
mkdir -p "$STAGE" && cp "$PROBE" "$STAGE/nccl_probe.py"
ssh -o BatchMode=yes "$NODE2" "mkdir -p $STAGE" </dev/null >/dev/null 2>&1
scp -q -o BatchMode=yes "$PROBE" "$NODE2:$STAGE/nccl_probe.py" || { echo "cannot stage probe to $NODE2" >&2; exit 1; }

cleanup() {
  docker rm -f nccl-probe-0 >/dev/null 2>&1
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$NODE2" 'docker rm -f nccl-probe-1 >/dev/null 2>&1' </dev/null >/dev/null 2>&1
}
trap cleanup EXIT

run_cmd() {  # $1 = rank
  local r=$1 out=() kv
  for kv in "${BASE[@]}" "${EXTRA[@]}"; do out+=(-e "$kv"); done
  out+=(-e "PROBE_RANK=$r")
  printf 'docker rm -f nccl-probe-%s >/dev/null 2>&1; docker run -d --name nccl-probe-%s --gpus all --privileged --network host --ipc host --shm-size 10g --ulimit memlock=-1 --ulimit stack=67108864 --device /dev/infiniband:/dev/infiniband -v %s:/probe %s --entrypoint python3 %s -u /probe/nccl_probe.py' \
    "$r" "$r" "$STAGE" "$(printf '%q ' "${out[@]}")" "$IMG"
}

cleanup
echo "[repro:$LABEL] extra env: ${EXTRA[*]:-<none>}"
# Rank 0 hosts the rendezvous store and MUST start first; the reverse order fails with a
# misleading "Connection refused" that looks like a fabric problem.
bash -c "$(run_cmd 0)" >/dev/null 2>&1 || { echo "rank0 launch FAILED"; exit 1; }
sleep 5
ssh -o BatchMode=yes "$NODE2" "$(run_cmd 1)" </dev/null >/dev/null 2>&1 || { echo "rank1 launch FAILED"; exit 1; }

for ((i=0; i<WAIT; i+=5)); do
  s0=$(docker inspect -f '{{.State.Status}}' nccl-probe-0 2>/dev/null)
  s1=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$NODE2" 'docker inspect -f "{{.State.Status}}" nccl-probe-1 2>/dev/null' </dev/null 2>/dev/null)
  [[ "$s0" != running && "$s1" != running ]] && break
  sleep 5
done

docker logs nccl-probe-0 > "$LOGDIR/$LABEL-rank0.log" 2>&1
ssh -o BatchMode=yes "$NODE2" 'docker logs nccl-probe-1' </dev/null > "$LOGDIR/$LABEL-rank1.log" 2>&1

echo "[repro:$LABEL] rank0=$s0 rank1=$s1 (elapsed ~${i}s)  logs: $LOGDIR/$LABEL-rank{0,1}.log"
rc=0
for r in 0 1; do
  log="$LOGDIR/$LABEL-rank$r.log"
  if grep -q PROBE_PASS "$log" 2>/dev/null; then
    echo "  rank$r: PASS  $(grep -o 'PROBE_PASS total=[0-9.]*' "$log" | head -1)"
  else
    rc=1
    echo "  rank$r: FAIL/HUNG  comms_ok=$(grep -c 'subgroup .* ok' "$log") regmr_fails=$(grep -c wrap_ibv_reg_mr_iova2 "$log")"
    grep -oE 'Call to ibv_reg_mr_iova2 failed with error .*|Connection refused.*' "$log" | head -1 | sed 's/^/    /'
  fi
done
# A hung rank 0 is the normal shape of this failure: rank 1 dies, rank 0 waits forever.
exit $rc
