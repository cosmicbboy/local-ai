# `.env.dspark` — deployed deltas vs upstream example

The serving config for the DeepSeek-V4-Flash vLLM service lives in
`~/dspark-ds4-0731/.env.dspark` on node 1 (synced by the launcher to node 2 at every
start). It is copied verbatim from the recipe's `.env.dspark.example` and edited in
**8 places**. The deployed file is vendored here as
[`DEPLOYED.env.dspark`](DEPLOYED.env.dspark) — the ground truth.

## The complete diff (`diff .env.dspark.example .env.dspark`)

```diff
--- .env.dspark.example
+++ .env.dspark            (== config/DEPLOYED.env.dspark)

 9  :  -WORKER_HOST=worker-host-or-roce-ip
     :  +WORKER_HOST=192.168.100.11

 16 :  -MASTER_ADDR=head-roce-ip
     :  +MASTER_ADDR=192.168.100.10

 25 : +# systemd user unit deepseek-v4-flash.service owns start order + drop-caches
     : +# sidecar; do not let dockerd restore ranks.
     : +DSPARK_RESTART_POLICY=no

 34 :  -NCCL_IB_HCA=rocepXsYfZ
 35 :  -NCCL_SOCKET_IFNAME=enpXsYfZnpN
     :  +NCCL_IB_HCA=rocep1s0f1
     :  +NCCL_SOCKET_IFNAME=enp1s0f1np1

 161 : -VLLM_HOST_IP=head-roce-ip
 162 : -WORKER_VLLM_HOST_IP=worker-roce-ip
     : +VLLM_HOST_IP=192.168.100.10
     : +WORKER_VLLM_HOST_IP=192.168.100.11

 170 : -DSPARK_VLLM_IMAGE=ghcr.io/anemll/dspark-vllm-gx10:0.1.1@sha256:a83948492cf13df455170fb42885f5ef4db54fefe0feff0f841ecbff464ac9d8
     : +DSPARK_VLLM_IMAGE=ghcr.io/anemll/dspark-vllm-gx10:0.1.1
     :   (plus two explanatory comments; `docker load` on node 2 drops the registry
     :    digest, so we pin the tag and verify the image ID equals
     :    sha256:3430d6614a8e2925f34d059af6caf05aff42387326db4d05639a60f10f2654d8
     :    on both nodes instead.)

 291 : -GPU_MEMORY_UTILIZATION_TEXT=0.835
     : +GPU_MEMORY_UTILIZATION_TEXT=0.80

 303 : -DEFAULT_THINKING=max
     : +DEFAULT_THINKING=low
```

Everything else is the upstream default (including `MAX_MODEL_LEN=1048576`,
`MAX_NUM_SEQS=6`, `MAX_NUM_BATCHED_TOKENS=8192`, `MTP_NUM_TOKENS=5`,
`VLLM_USE_BREAKABLE_CUDAGRAPH=0`, `NCCL_CUMEM_ENABLE=0`).

## Why each change

| Key | Old | Deployed | Why |
|---|---|---|---|
| `WORKER_HOST` | placeholder | `192.168.100.11` | fabric IP of node 2 |
| `MASTER_ADDR` | placeholder | `192.168.100.10` | fabric IP of node 1 |
| `DSPARK_RESTART_POLICY` | (unset → `unless-stopped`) | `no` | systemd owns the lifecycle; dockerd must not restore ranks at boot |
| `NCCL_IB_HCA` | placeholder | `rocep1s0f1` | **f1 is the cabled port on this pair** (f0 is DOWN) |
| `NCCL_SOCKET_IFNAME` (+ `TP_`, `GLOO_`) | placeholder | `enp1s0f1np1` | matches the HCA |
| `VLLM_HOST_IP` / `WORKER_VLLM_HOST_IP` | placeholder | `.10` / `.11` | keeps ZMQ/rendezvous on the fabric, not WiFi |
| `DSPARK_VLLM_IMAGE` | `…:0.1.1@sha256:a839…` | `…:0.1.1` | digest lost on node 2 after `docker load`; image IDs verified equal |
| `GPU_MEMORY_UTILIZATION_TEXT` | 0.835 | **0.80** | extra headroom; the old image hit `ibv_reg_mr` ENOMEM at 0.85 |
| `DEFAULT_THINKING` | max | **low** | faster default; clients can raise it per request |

## Merge procedure on a fresh checkout

```bash
cd dspark-ds4-0731
cp .env.dspark.example .env.dspark
# edit .env.dspark and apply the 8 hunks above, or just crib from
# config/DEPLOYED.env.dspark in this repo.
```

Then sanity-check with the recipe's validator (if available):
`./validate-dspark-config.sh`. Editing only node 1's copy is sufficient — the
launcher scp's it to node 2 on each start.
