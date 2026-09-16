# Runbook: DeepSeek-V4-Flash-0731 vLLM service (TP=2 across 2× DGX Spark)

Codification of the **currently-served** DeepSeek V4 vLLM service on this machine.
Everything here was verified against the live deployment on **2026-09-12** (service
healthy, `active (exited)`, both ranks up).

- **What it serves:** `deepseek-ai/DeepSeek-V4-Flash-0731` (FP8 e4m3 + MXFP4 routed
  experts, 155.4 GiB), with **DSpark speculative decoding (k=5)** and vLLM tensor
  parallelism `TP=2` across the two Sparks over RoCE.
- **Measured decode:** ~75 tok/s single-stream on code (73.6 / 74.6 / 76.8),
  34–37 tok/s on prose, TTFT 0.14–0.19 s.
- **API:** OpenAI-compatible at `http://192.168.100.10:8888/v1` (model
  `deepseek-v4-flash-0731`), also `http://flint-dgx:8888/v1` on Tailscale.
- **Context:** 1,048,576 tokens ceiling, shared KV pool 1,701,429 tokens, max 6
  concurrent sequences.

| | |
|---|---|
| Runtime | Docker compose project `deepseek-v4-flash` (head + worker containers) |
| Image | `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` (vLLM 0.25.2.dev0, torch/CUDA 2.11.0+cu130 / 13.0) |
| Recipe | [`MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark`](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark) @ branch `0731-ablit`, commit `0107cef1835a56d1a2bcdabf7d9e1a085b70338b` (2026-08-29, the last text-only 0731 lane) |
| Supervisor | systemd **user** unit `deepseek-v4-flash.service` on node 1 (enabled, starts on boot) |
| Checkpoint rev | `9e165c30e2704aec5d9d593cce3eebd58bbef1cb` |

---

## 1. Variable names & host facts

| | node 1 (head, rank 0) | node 2 (worker, rank 1) |
|---|---|---|
| Hostname | `spark-a7e9` (Tailscale `flint-dgx`) | `spark-17d7` |
| Fabric IP | `192.168.100.10` | `192.168.100.11` |
| netdev / RDMA | `enp1s0f1np1` / `rocep1s0f1` | same names |
| NVIDIA driver / kernel | 580.142 / 6.17.0-1014-nvidia | 580.173.02 / 7.0.0-1019-nvidia |
| Unified memory | 121 GiB | 121 GiB |

Conventions used throughout (matching this repo's scripts):
- `HOME=/home/nielsbantilan` on both nodes (adjust for your user).
- Passwordless `ssh` from node 1 → node 2 (no agent required).
- The serving user is in the `docker` group on **both** nodes.
- `sudo` requires a password on both nodes (the design avoids needing it).
- `Linger=yes` for the user on node 1 (so systemd user units run at boot without a login).

> The two nodes have **different driver/kernel** versions. The NVIDIA forum thread
> (370309) measured +37% decode after aligning them; alignment needs sudo + reboot
> and is still an open item. Keep the fabric healthy (§ Rehydration step 0) regardless.

---

## 2. Architecture

- vLLM runs `TP=2` (one GB10 per rank), `pipeline-parallel 1`, `nnodes 2`.
- Worker (node 2, rank 1) starts **first**, head (node 1, rank 0) second; the head
  owns the `:8888` OpenAI API.
- Rank rendezvous (ZMQ/TCPStore) and NCCL all-reduce travel over the **RoCE fabric**
  (`rocep1s0f1` / `enp1s0f1np1`, GID index 3). Verified: no TCP fallback, ~664 MiB
  RDMA traffic per short request, 0 MiB TCP.
- **DSpark** is the speculative head: `{"method":"dspark","num_speculative_tokens":5,
  "draft_sample_method":"probabilistic"}`. Acceptance on code ≈ 0.90 / 0.86 / 0.80 /
  0.59 / 0.55 per position (mean accept length ~4.7). Prose accepts far less, hence
  ~35 tok/s.
- Default reasoning is **on, `reasoning_effort: low`** (override with
  `chat_template_kwargs` per request). Clients passing a small `max_tokens` will see
  it consumed by `reasoning_content` with empty `content`.

---

## 3. Rehydration checklist (fresh DGX pair)

> Before you start, both Sparks must be a working 200 Gb RoCE pair. Do **not** skip
> this — every symptom below assumes a healthy fabric. See the
> [`dual-dgx/`](../dual-dgx/) runbook for the fabric bring-up, the ConnectX-7 power
> throttle fix (reboot with the cable connected!) and NCCL validation.

### Step 0 — Fabric prerequisites (one time)

- QSFP cable connected **before boot** (hot-plug triggers the ~13 Gb/s power-throttle
  bug), MTU 9000 on both interfaces, and proof that NCCL takes `NET/IB` not `NET/Socket`.
  Details: [`dual-dgx/`](../dual-dgx/), Phase 0.
- `ssh` from node 1 → node 2 with no password, user in `docker` group on both nodes.
- On node 1: `loginctl enable-linger <user>`.

### Step 1 — Clone + pin the recipe

On node 1 (and mirrored to node 2 by the launcher at start time):

```bash
git clone https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark.git dspark-ds4-0731
cd dspark-ds4-0731
git checkout 0107cef1835a56d1a2bcdabf7d9e1a085b70338b     # branch 0731-ablit, last text-only lane
```

Keep the checkout at this commit. `main` has since moved to Vision-Exp, which this
service is not. The recipe provides: `docker-compose.dspark.yml`, the
`start/stop/status/logs/smoke-*` launchers, `patches/` (startup hotfixes), and
`recipe/` (the DSpark vLLM overlay). **Edit only node 1's copy** — the launcher
scp's `.env.dspark`, compose and patches to the same path on node 2 on each start.

### Step 2 — Configure `.env.dspark` (the 8 deltas)

Copy the recipe's `.env.dspark.example` → `.env.dspark` on node 1 and apply exactly
the deltas documented in [`config/env-deltas.md`](config/env-deltas.md). The deployed
file is vendored verbatim at [`config/DEPLOYED.env.dspark`](config/DEPLOYED.env.dspark)
— you can diff yours against it. In one line: node IPs, the f1 interface names,
`DSPARK_RESTART_POLICY=no`, `GPU_MEMORY_UTILIZATION_TEXT=0.80` (was 0.835),
`DEFAULT_THINKING=low` (was max), and tag- vs digest-pinned image.

Key values that matter (the rest are upstream defaults):

```bash
WORKER_HOST=192.168.100.11
MASTER_ADDR=192.168.100.10               # MASTER_PORT=25000
VLLM_HOST_IP=192.168.100.10
WORKER_VLLM_HOST_IP=192.168.100.11
NCCL_IB_HCA=rocep1s0f1                   # f1 is the cabled port on this pair (f0 is DOWN)
NCCL_SOCKET_IFNAME=enp1s0f1np1           # also TP_SOCKET_IFNAME, GLOO_SOCKET_IFNAME
DSPARK_RESTART_POLICY=no                 # systemd owns lifecycle; dockerd must not restore ranks at boot
GPU_UTILITY... GPU_MEMORY_UTILIZATION_TEXT=0.80   # 0.85 hit ibv_reg_mr ENOMEM on the old image
DEFAULT_THINKING=low
MAX_MODEL_LEN=1048576                    # 1M context ceiling
MAX_NUM_SEQS=6
MAX_NUM_BATCHED_TOKENS=8192
MTP_NUM_TOKENS=5                         # DSpark k
NCCL_CUMEM_ENABLE=0                      # required (ibv_reg_mr memory class)
VLLM_USE_BREAKABLE_CUDAGRAPH=0
```

### Step 3 — Checkpoint + JIT caches on both nodes

1. Get the 155.4 GiB FP8 checkpoint (`config.json` + 48 safetensors) + the small
   repo files into `~/models/deepseek-v4-flash-0731-fp8/` on **both** nodes.
2. Run the cache builder on each node so vLLM's offline/HF-cache path finds it:

```bash
# on each node:  scripts/dspark-ds4-0731-mkcache.sh
# builds ~/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4-Flash-0731/snapshots/<rev>/
# as HARD LINKS to ~/models/... (zero extra disk), fetches the small files the flat
# download flattens away — encoding/encoding_dsv4.py is REQUIRED (installed as the
# DeepSeek-V4 message encoder by the container entrypoint).
```

Do **not** delete `~/models/deepseek-v4-flash-0731-fp8` — the hub snapshot shares
inodes with it; editing a file in place changes both.

### Step 4 — Get the image on both nodes

- **Node 1:** `docker pull ghcr.io/anemll/dspark-vllm-gx10:0.1.1`
- **Node 2 (over the fabric):**
  `docker save ghcr.io/anemll/dspark-vllm-gx10:0.1.1 | ssh -c aes128-gcm@openssh.com 192.168.100.11 docker load`
  (18.8 GB, ~2 min). `docker load` drops the registry digest, so `.env.dspark` uses the
  **tag** (`:0.1.1`), not `@sha256:`. **Verify image IDs match** on both nodes:
  `docker image inspect --format '{{.Id}}' ghcr.io/anemll/dspark-vllm-gx10:0.1.1`
  → expect `sha256:3430d6614a8e2925f34d059af6caf05aff42387326db4d05639a60f10f2654d8`.

### Step 5 — Install the wrapper scripts + systemd unit

From this repo, copy onto node 1:

| Source | Destination | Role |
|---|---|---|
| `systemd/deepseek-v4-flash.service` | `~/.config/systemd/user/deepseek-v4-flash.service` | systemd unit (adjust any paths/user) |
| `scripts/serve-dspark-ds4.sh` | `~/serve-dspark-ds4.sh` | start wrapper: drop-caches sidecars + launcher |
| `scripts/dspark-wait-cluster.sh` | `~/dspark-wait-cluster.sh` | pre-start gate (docker, fabric, node 2) |
| `scripts/dspark-ds4-0731-mkcache.sh` | `~/dspark-ds4-0731-mkcache.sh` | HF-cache builder (Step 3) |
| `scripts/bench-dspark.py` | `~/bench-dspark.py` | streaming decode benchmark |
| `scripts/bench-ds4.sh` | `~/bench-ds4.sh` | simple throughput one-shot |

```bash
chmod +x ~/serve-dspark-ds4.sh ~/dspark-wait-cluster.sh
systemctl --user daemon-reload
systemctl --user enable deepseek-v4-flash
```

### Step 6 — Start + verify

```bash
systemctl --user start deepseek-v4-flash
# or, first bring-up without systemd:
~/serve-dspark-ds4.sh
```

Expected cold-boot timeline with the drop-caches sidecar (persist JIT caches across
boots for a cached ~2 min FlashInfer autotune):

- ~3 min weight load
- ~1 min compile/profile
- ~2 min FlashInfer autotune (cached after first boot)
- ~20 s CUDA graph capture

```bash
curl -s localhost:8888/v1/models | python3 -m json.tool     # served model + max_model_len
curl -s -o /dev/null -w '%{http_code}\n' localhost:8888/health   # 200
scripts/bench-dspark.py --runs 3 --think off --prompt code   # expect ~73–77 tok/s
```

---

## 4. What the deployed service looks like

### 4.1 Effective `vllm serve` command (captured from the live head container)

```text
vllm serve deepseek-ai/DeepSeek-V4-Flash-0731
  --revision 9e165c30e2704aec5d9d593cce3eebd58bbef1cb
  --served-model-name deepseek-v4-flash-0731
  --host 0.0.0.0 --port 8888 --trust-remote-code
  --tensor-parallel-size 2 --pipeline-parallel-size 1
  --kv-cache-dtype nvfp4_ds_mla --block-size 256
  --max-model-len 1048576 --max-num-seqs 6 --max-num-batched-tokens 8192
  --long-prefill-token-threshold 1024 --max-cudagraph-capture-size 36
  --gpu-memory-utilization 0.80
  --enable-prefix-caching --enable-prompt-tokens-details --async-scheduling --enable-chunked-prefill
  --speculative-config {"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic"}
  --tokenizer-mode deepseek_v4 --distributed-executor-backend mp --moe-backend flashinfer_b12x
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice --reasoning-parser deepseek_v4
  --reasoning-config {"reasoning_parser":"deepseek_v4","reasoning_start_str":" thinking","reasoning_end_str":" response"}
  --default-chat-template-kwargs {"thinking":true,"reasoning_effort":"low"}
  --generation-config vllm --enable-flashinfer-autotune
  --nnodes 2 --node-rank 0 --master-addr 192.168.100.10 --master-port 25000
```

Node 2 runs the identical command with `--node-rank 1 --headless` and
`VLLM_HOST_IP=192.168.100.11`. Daemonized by the recipe's launcher + compose; the
container is `deepseek-v4-flash-vllm-dspark-1` on each node.

### 4.2 Container runtime

- `--network host`, `--ipc host`, `shm_size 64g`, `--gpus all`, `/dev/infiniband`
  passed through, `memlock -1`, `stack 67108864`, restart `no`.
- Key mounts: `~/.cache/huggingface → /cache/huggingface` (HF + vllm/triton/tilelang/
  flashinfer JIT caches persist across restarts), `~/.cache/dspark-tmp → /tmp`, plus
  the `patches/` hotfix bind-mounts.

### 4.3 Key environment (select; full matrix in `config/DEPLOYED.env.dspark`)

```text
# NCCL — must stay NET/IB on the fabric
NCCL_NET=IB  NCCL_IB_DISABLE=0  NCCL_IB_HCA=rocep1s0f1  NCCL_IB_GID_INDEX=3
NCCL_IB_ADDR_FAMILY=AF_INET  NCCL_IB_ROCE_VERSION_NUM=2  NCCL_SOCKET_IFNAME=enp1s0f1np1
NCCL_CROSS_NIC=1  NCCL_CUMEM_ENABLE=0  NCCL_NVLS_ENABLE=0  NCCL_IGNORE_CPU_AFFINITY=1  NCCL_DEBUG=WARN

# vLLM
VLLM_USE_B12X_MOE=1  VLLM_USE_FLASHINFER_SAMPLER=1  VLLM_USE_BREAKABLE_CUDAGRAPH=0
VLLM_ALLOW_LONG_MAX_MODEL_LEN=1  VLLM_SPARSE_INDEXER_MAX_LOGITS_MB=256
VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=0  VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800
VLLM_PREFIX_CACHE_RETENTION_INTERVAL=4096  VLLM_CACHE_ROOT=/cache/huggingface/vllm-cache

# arch / JIT
TORCH_CUDA_ARCH_LIST=12.1a  FLASHINFER_CUDA_ARCH_LIST=12.1a  CUTE_DSL_ARCH=sm_121a
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True  HF_HUB_OFFLINE=1  TRANSFORMERS_OFFLINE=1
```

**Startup hotfixes** are applied by the compose entrypoint before `exec vllm`
(DSv4 encoder + #21, #55, #22 nvfp4-ds-mla long-context, #79 shm spin-wait,
backports #50312/#49486/#48407/#48957/#50298/grammar-advance, #27/#43/#26/#133,
suppress-stops-in-reasoning, empty-encoder-output). All fail closed. Details: the
recipe's `docs/PATCHES.md`.

---

## 5. The systemd unit

See [`systemd/deepseek-v4-flash.service`](systemd/deepseek-v4-flash.service).
Modeled: `Type=oneshot RemainAfterExit=yes`, `ExecStartPre=dspark-wait-cluster.sh`
(≤30 min gate), `ExecStart=serve-dspark-ds4.sh`, `ExecStop=stop-…sh`,
`SuccessExitStatus=3`, `TimeoutStartSec=90min`.

### Boot sequence

1. `Linger=yes` starts the user manager at boot without a login → `default.target`.
2. `dspark-wait-cluster.sh` polls every 10 s (≤30 min): local docker + image,
   `rocep1s0f1` `ACTIVE` with an IPv4, node 2 reachable over ssh with docker + image.
   If node 2 never appears the unit **fails** (no half cluster). Then sleeps 15 s for
   RoCE GIDs to populate.
3. `serve-dspark-ds4.sh` kills any `ggml-rpc-server` on node 2 (memory competition),
   starts a `dsv4-dropcaches` privileged sidecar on **both** nodes (`drop_caches`
   every 5 s), runs the recipe launcher (worker first, then head), waits for
   `/v1/models` (≤160×15 s = 40 min), runs the boot-shape warmup, and always removes
   the sidecars on exit.
4. Unit goes `active (exited)`. Launcher exit 3 ("both already up") counts as success.

> Cold boot through systemd was only *adopted* an already-running cluster (exit 3) in
> the verified deployment. Run one `systemctl --user restart deepseek-v4-flash` in a
> quiet window to prove the full path before relying on it after a power cycle.

---

## 6. Operating the service

### 6.1 Start / stop / restart

```bash
systemctl --user start   deepseek-v4-flash      # no-op (exit 3 → success) if already serving
systemctl --user stop    deepseek-v4-flash      # stops head + worker containers
systemctl --user restart deepseek-v4-flash      # full cold restart, ~6–10 min API downtime
systemctl --user enable  deepseek-v4-flash      # start on boot (current state)
systemctl --user disable deepseek-v4-flash      # don't start on boot
```

**Without systemd:** `~/serve-dspark-ds4.sh` / `dspark-ds4-0731/stop-deepseek-v4-flash-dspark.sh`.

**After power-cycling both boxes:** run this from your Mac —
[`scripts/restart-after-reboot.sh`](scripts/restart-after-reboot.sh). It waits for both
nodes to be reachable on Tailscale, waits for the head node to see the worker over the
RoCE fabric, then restarts the service and polls `/health` until the API is actually
serving (not just "active (exited)").

**Config change:** edit `~/dspark-ds4-0731/.env.dspark` on node 1, then
`systemctl --user restart deepseek-v4-flash`. **`docker compose restart` does not
pick up env changes** — always stop then start.

### 6.2 Visibility

```bash
systemctl --user status deepseek-v4-flash
journalctl --user -u deepseek-v4-flash -f            # gate, launcher, exit codes
curl -s localhost:8888/v1/models | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' localhost:8888/health   # 200 = engine healthy
~/dspark-ds4-0731/status-deepseek-v4-flash-dspark.sh             # both ranks, image IDs, API

~/dspark-ds4-0731/logs-deepseek-v4-flash-dspark.sh               # TAIL=160 default
docker logs -f deepseek-v4-flash-vllm-dspark-1                   # head (API + TP0)
ssh 192.168.100.11 'docker logs -f deepseek-v4-flash-vllm-dspark-1'   # worker (TP1)
docker logs --since 5m deepseek-v4-flash-vllm-dspark-1 2>&1 \
  | grep -E 'SpecDecoding metrics|Avg generation throughput' | tail
curl -s localhost:8888/metrics | grep -E '^vllm:(num_requests_running|num_requests_waiting|kv_cache_usage_perc|spec_decode)'
```

`active (exited)` only means startup succeeded — it does **not** notice a later vLLM
crash; use the health checks.

### 6.3 Memory (both nodes)

```bash
for h in 192.168.100.10 192.168.100.11; do ssh $h "free -g | awk '/Mem:/{print \"$h used=\"\$3\" avail=\"\$7}'"; done
# steady state: ~110 GiB used / ~11 GiB avail on node 1, ~106 / ~14 on node 2
```

### 6.4 Confirm TP traffic is on RDMA, not TCP

```bash
C=/sys/class/infiniband/rocep1s0f1/ports/1/counters; N=/sys/class/net/enp1s0f1np1/statistics
R1=$(cat $C/port_xmit_data); T1=$(cat $N/tx_bytes)
scripts/bench-dspark.py --runs 1 --max-tokens 256
R2=$(cat $C/port_xmit_data); T2=$(cat $N/tx_bytes)
echo "RDMA $(( (R2-R1)*4/1048576 )) MiB, TCP $(( (T2-T1)/1048576 )) MiB"   # verified: RDMA 664 MiB, TCP 0 MiB
# port_xmit_data counts 4-byte words
```

### 6.5 Smoke tests

```bash
curl -s http://192.168.100.10:8888/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model":"deepseek-v4-flash-0731",
  "messages":[{"role":"user","content":"Write a haiku about two computers sharing memory."}],
  "max_tokens":200, "chat_template_kwargs":{"thinking":false}}' | python3 -m json.tool

scripts/bench-dspark.py --runs 3 --think off --prompt code     # expect ~72–77 tok/s decode
~/dspark-ds4-0731/smoke-deepseek-v4-flash-dspark.sh            # recipe's own smoke test
```

---

## 7. Troubleshooting

### 7.1 Weight load hangs at "Loading safetensors checkpoint shards: N/48"

Seen on node 1. Progress freezes (e.g. 10/48 for 20 min) while node 2 finishes; no
errors; `py-spy` shows 100% CPU in `cuMemcpyHtoDAsync_v2`. **Fix:** drop page caches
— the `serve-dspark-ds4.sh` sidecar does this automatically now. Manual check:
`docker ps | grep dsv4-dropcaches` on both nodes.

### 7.2 Launcher "Timed out waiting for DSpark API" (exit 1)

Almost always §7.1 or a crashed rank. Containers are **not** torn down on timeout, so
`curl localhost:8888/v1/models` may still work — systemd will mark the unit failed
anyway; clean it with a restart.

### 7.3 Launcher exit 3

"Head container already exists" = both ranks already up → success
(`SuccessExitStatus=3`).

### 7.4 Unit fails in `ExecStartPre` ("cluster not ready after 1800s")

Check, in order: node 2 powered on → `ssh 192.168.100.11 docker info` →
`ibv_devinfo -d rocep1s0f1 | grep state` both nodes → `ip -4 addr show enp1s0f1np1`.
Then restart.

### 7.5 `ibv_reg_mr_iova2 ... Cannot allocate memory` / NCCL init errors

Seen on the (abandoned) aidendle94 image attempts, not on this deployment. If it
recurs: confirm `NCCL_CUMEM_ENABLE=0`, lower
`GPU_MEMORY_UTILIZATION_TEXT` (0.78 floor), free unified memory held by other GPU
workloads (LM Studio, Ollama, the llama.cpp RPC server on node 2), and re-check GIDs
after a reboot.

### 7.6 Mid-serve stall: "No available shared memory broadcast block"

Recipe issue #141 — stochastic TP=2 sparse-MLA stall under high
`max_num_seqs × (k+1)`. Mitigation: `DSPARK_ENABLE_ISSUE141_SPARSE_MLA_CHUNK=1`
in `.env.dspark` and/or lower `MAX_NUM_SEQS`, then restart. Unit stays `active
(exited)` through a stall — use the health checks.

### 7.7 OOM / host wedge under long, concurrent load

Node 1 keeps ~11 GiB free at steady state. Keep ≥6 GiB `MemAvailable`; if available
memory creeps down over hours add `UCX_MEM_MMAP_HOOK_MODE=none` and
`UCX_RCACHE_MAX_UNRELEASED=1024` to `.env.dspark` (per-request UCX leak). Don't run
other GPU workloads on either node while this is up. Each 0.01 of
`GPU_MEMORY_UTILIZATION_TEXT` ≈ 1.2 GiB ≈ 165K KV tokens.

### 7.8 Other devices can't reach :8888

vLLM binds `0.0.0.0:8888` (verify `ss -ltn | grep 8888`). `ufw` is active on node 1;
for tailnet-only access: `sudo ufw allow in on tailscale0 to any port 8888 proto tcp`.

---

## 8. Performance baseline (2026-09-12, single stream, 768 output tokens, streaming)

| Workload | Decode tok/s | TTFT |
|---|---|---|
| Code, thinking off | 73.6 / 74.6 / 76.8 | 0.17–0.19 s |
| Code, thinking low | 61.6 / 62.0 | 0.14–0.19 s |
| Prose, thinking off | 34.4 / 36.6 | 0.17–0.18 s |

Boot stats: model 79.17 GiB per rank; KV 11.46 GiB → 1,701,429 tokens (1.62× a full
1M request); graph capture 21 s, 1.25 GiB (head) / 2.59 GiB (worker).

---

## 9. Known risks / open items

1. **Cold boot via systemd untested** — prove with one quiet restart.
2. **`lmstudio.service` also enabled at boot** loads `qwen3-coder-next` +
   `qwen3.6-35b-a3b` on node 1, competing for unified memory. Consider
   `systemctl --user disable lmstudio` (its `ExecStart` already fails with 203/EXEC,
   but its model-loading `ExecStartPre`s still run).
3. **Node driver/kernel mismatch** (§1) — aligning may improve speed and remove the
   §7.1 wedge trigger.
4. **No API key** — anyone on LAN/tailnet can use the model. Set `VLLM_API_KEY=` in
   `.env.dspark` to require one.
5. **Upstream moves on** — stay pinned on `0731-ablit` unless deliberately changing
   checkpoints.
6. **Old containers/images** — the exited `vllm-head`/`vllm-worker` from the
   aidendle94 attempts (and that 22.7 GB image) can be removed if no longer wanted.

---

## 10. File manifest (this directory)

| Path | What it is |
|---|---|
| `README.md` | this runbook |
| `systemd/deepseek-v4-flash.service` | systemd user unit (node 1) |
| `config/DEPLOYED.env.dspark` | the exact live `.env.dspark` (ground truth, node 1) |
| `config/env-deltas.md` | the 8 deltas vs the recipe example, with a merge procedure |
| `scripts/serve-dspark-ds4.sh` | start wrapper (drop-caches sidecar) |
| `scripts/dspark-wait-cluster.sh` | pre-start readiness gate |
| `scripts/dspark-ds4-0731-mkcache.sh` | HF-hub-cache builder (hardlinks) |
| `scripts/bench-dspark.py` | streaming single-stream decode bench |
| `scripts/bench-ds4.sh` | simple one-shot throughput |
| `scripts/serve-deepseek-v4-flash-llamacpp.sh` | **reference only**: the older llama.cpp RPC DS4 config (~25 tok/s), superseded by this vLLM service |

The recipe checkout itself (compose file, launchers, patches, DSpark overlay) is an
upstream repo — reference/pin it per §Step 1 rather than vendoring it here.
