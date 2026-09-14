# Runbook: Dual DGX Spark setup — serving an LLM across two Sparks

How to turn two fresh DGX Sparks (GB10, 121 GiB unified memory each) into a working
200 Gb RoCE cluster and serve a model across **both**, tested on this hardware
2026-09-11/12 — nodes `spark-a7e9` (node 1 / head) + `spark-17d7` (node 2 / worker).

Companion document: [`../deepseek-v4-vllm/`](../deepseek-v4-vllm/) — the production
DeepSeek-V4 vLLM service that runs on this cluster today.

Throughout, `NODE1` = `192.168.100.10`, `NODE2` = `192.168.100.11`. Use the
`192.168.100.0/24` pair for everything — on this box the interface names do **not**
match NVIDIA's playbook (`enP2p1s0f1np1` is on the `101.x` pair here, not `100.x`).
Run everything from node 1 unless a step says otherwise. Passwordless ssh is already
working in both directions.

## Topology (as built)

| | node 1 | node 2 |
|---|---|---|
| hostname | `spark-a7e9` (Tailscale `flint-dgx`) | `spark-17d7` |
| fabric IP (port 1) | `192.168.100.10` | `192.168.100.11` |
| fabric IP (port 2) | `192.168.101.10` | `192.168.101.11` |
| netdev / RDMA dev | `enp1s0f1np1` / `rocep1s0f1` | same names |
| GPU | NVIDIA GB10, compute cap **12.1**, `sm_121` | same |
| unified memory | 121 GiB | 121 GiB |
| disk free | 2.0 TB | 3.5 TB |

---

## Phase 0 — Validate the fabric (do this first, ~10 min)

### 0.1 Link is up at 200G

```bash
ip -br addr | grep -E 'enp1s0f1np1|enP2p1s0f1np1'
rdma link show | grep ACTIVE
ethtool enp1s0f1np1 | grep -E 'Speed|Link detected'
ping -c 5 192.168.100.11
```

Expect `Speed: 200000Mb/s`, two `ACTIVE` RoCE links, sub-ms ping (0.62 ms TCP-over-Ethernet
is normal; RDMA latency is ~1.7 µs).

### 0.2 Measure actual RDMA bandwidth

`ib_write_bw` needs a server on node 2. **Gotcha:** never put `pkill -f ib_write_bw`
in the same ssh command as the launch — `pkill -f` matches the ssh wrapper's own
command line and kills the session before the server starts. Use a script file:

```bash
cat > /tmp/ibsrv.sh <<'EOF'
#!/bin/bash
exec ib_write_bw -d rocep1s0f1 -x 3 --report_gbits -D 5 > /tmp/ibsrv.log 2>&1 < /dev/null
EOF
scp /tmp/ibsrv.sh 192.168.100.11:/tmp/ibsrv.sh
ssh -f 192.168.100.11 'setsid bash /tmp/ibsrv.sh'
sleep 3
ib_write_bw -d rocep1s0f1 -x 3 --report_gbits -D 5 192.168.100.11
```

`-x 3` is the RoCE v2 IPv4 GID index on these boxes (confirmed: GID 3 =
`::ffff:192.168.100.10`). Verify yours:

```bash
for i in 0 1 2 3; do echo "$i $(cat /sys/class/infiniband/rocep1s0f1/ports/1/gid_attrs/types/$i) \
$(cat /sys/class/infiniband/rocep1s0f1/ports/1/gids/$i)"; done
```

### 0.3 The ~13 Gb/s cap: ConnectX-7 power throttling

**This is a known DGX Spark firmware bug, not a misconfiguration.** Confirmed on both
nodes in `dmesg`:

```
mlx5_core 0000:01:00.0: mlx5_pcie_event:322: PCIe slot power capability was not advertised.
mlx5_core 0000:01:00.1: mlx5_pcie_event:326: Detected insufficient power on the PCIe slot (27W).
```

The ConnectX-7 firmware reads a 27 W slot-power report, decides that's not enough for a
200G NIC, and silently throttles to ~13 Gb/s (TCP and RDMA equally).

```bash
sudo dmesg | grep -iE "insufficient power|slot power"
ssh 192.168.100.11 'sudo dmesg | grep -iE "insufficient power|slot power"'
```

**Trigger:** hot-plugging the QSFP cable into a running system — exactly what NVIDIA's
stacked-sparks guide has you do.

**Fix — reboot both nodes with the cable already connected:**

```bash
# 1. Leave the QSFP topology exactly as you want it. Do not unplug or move the cable.
# 2. Reboot both nodes.
ssh 192.168.100.11 'sudo reboot'
sudo reboot
# 3. After both return, do not touch the cable. Re-measure 0.2.
```

**Verified:** 13.42 Gb/s → **109.18 Gb/s average**. If one reboot doesn't clear it,
fully power-drain both units (shut down, pull power cords 30 s, boot with the cable in).

### 0.3b What to actually expect

The 200 Gb/s headline is **aggregate across both QSFP ports**, not per port. `dmesg`
states the per-port ceiling directly:

```
mlx5_core 0002:01:00.1: 126.028 Gb/s available PCIe bandwidth (32.0 GT/s PCIe x4 link)
```

| Measurement | Realistic target |
|---|---|
| Single port (`ib_write_bw` on `rocep1s0f1`) | **95–115 Gb/s** |
| Both ports driven in parallel | ~190–200 Gb/s |
| NCCL all-reduce bus bandwidth | ~10 GB/s (GDR is off; tensors transit system memory) |

A single `ib_write_bw` run will never show 200 on this hardware. **~100 Gb/s on one
port is healthy.**

### 0.3c MTU 9000 — keep it, but it is not the bandwidth fix

Raising the netdev MTU to 9000 lifts RoCE `active_mtu` 1024 → 4096. Measured
throughput change on this cluster: 13.50 → 13.42 Gb/s (zero — the power throttle was
the real cause). Keep the setting (helps TCP); don't expect it to fix bandwidth.

```yaml
# /etc/netplan/40-cx7.yaml — on both nodes
network:
  version: 2
  ethernets:
    enp1s0f1np1:
      addresses: [192.168.100.10/24]   # .11 on node 2
      mtu: 9000
    enP2p1s0f1np1:
      addresses: [192.168.101.10/24]   # .11 on node 2
      mtu: 9000
```

```bash
sudo netplan apply
ibv_devinfo -d rocep1s0f1 | grep active_mtu   # expect 4096
```

### 0.3d Ruled out on this hardware (don't re-tread)

| Suspect | Finding |
|---|---|
| MTU | `active_mtu: 4096` both nodes, no throughput change |
| Bad cable / one bad port | Both ports measure identically (13.45 / 13.33 pre-fix) |
| Link negotiation | `active_width: 2X`, `active_speed: 100.0 Gbps` = 200G at the wire |
| RDMA tuning | Flat across 1/4/8 QPs, 64 KB–4 MB messages, tx_depth 128/256 |
| Latency / path | `ib_write_lat` t_avg **1.68 µs** — healthy |
| Congestion / retransmits | Zero change in RoCE `hw_counters` during a run |
| PCIe link | Gen5 x4 at full rate, 126 Gb/s available |
| CPU governor | `performance` |

### 0.4 NCCL sanity check

The real gate: NCCL must pick RoCE, not WiFi.

```bash
docker run --rm --gpus all --network host --ipc host \
  --device /dev/infiniband --ulimit memlock=-1 \
  -e NCCL_DEBUG=INFO -e NCCL_SOCKET_IFNAME=enp1s0f1np1 \
  -e NCCL_IB_HCA=rocep1s0f1 -e NCCL_IB_GID_INDEX=3 \
  nvcr.io/nvidia/vllm:25.11-py3 \
  python -c "import torch;print(torch.__version__, torch.cuda.get_device_name(0))"
```

The full two-node all-reduce happens implicitly in Phase 3; look for **`NET/IB`**
(good) rather than **`NET/Socket`** (bad — fell back to TCP, usually an `NCCL_IB_HCA`
or `/dev/infiniband` passthrough problem).

---

## Phase 1 — Bootstrap node 2

### 1.1 Docker group

```bash
ssh 192.168.100.11 'sudo usermod -aG docker $USER'
ssh 192.168.100.11 'sudo systemctl restart docker'
# log out / back in, then:
ssh 192.168.100.11 'docker ps'
```

### 1.2 Container image — ship, don't re-pull

```bash
docker save nvcr.io/nvidia/vllm:25.11-py3 | ssh 192.168.100.11 'docker load'
ssh 192.168.100.11 'docker images | grep vllm'
```

### 1.3 Verify GPU access on node 2

```bash
ssh 192.168.100.11 'docker run --rm --gpus all nvcr.io/nvidia/vllm:25.11-py3 nvidia-smi -L'
# Expect GPU 0: NVIDIA GB10 (UUID: ...)
```

---

## Phase 2 — Shared model storage

With Ray + vLLM, **every worker reads the full checkpoint directory** and loads its own
shard. Node 2 has no models, so export node 1's HF cache over the fast link.

```bash
# --- node 1 ---
sudo apt-get install -y nfs-kernel-server
echo '/home/nielsbantilan/.cache/huggingface 192.168.100.0/24(ro,sync,no_subtree_check,no_root_squash)' \
  | sudo tee -a /etc/exports
sudo exportfs -ra
sudo systemctl enable --now nfs-server

# --- node 2 ---
ssh 192.168.100.11 'sudo apt-get install -y nfs-common && \
  sudo mkdir -p /home/nielsbantilan/.cache/huggingface && \
  sudo mount -t nfs -o ro,vers=4.2 192.168.100.10:/home/nielsbantilan/.cache/huggingface \
    /home/nielsbantilan/.cache/huggingface && \
  ls /home/nielsbantilan/.cache/huggingface/hub | head'
```

Persist on node 2 in `/etc/fstab`:
```
192.168.100.10:/home/nielsbantilan/.cache/huggingface /home/nielsbantilan/.cache/huggingface nfs ro,vers=4.2,_netdev 0 0
```

> **No-sudo alternative (used on this box):** `rsync` one model at a time, ~290–300
> MB/s over a single stream (ssh-encryption bound). Parallel streams or
> `rsync --rsh='ssh -c aes128-gcm@openssh.com'` do better:
> ```bash
> ssh 192.168.100.11 'mkdir -p ~/.cache/huggingface/hub'
> rsync -a --info=progress2 \
>   ~/.cache/huggingface/hub/models--unsloth--Qwen3.8-27B-NVFP4 \
>   192.168.100.11:.cache/huggingface/hub/
> ```

---

## Phase 3 — The actual test: vLLM + Ray, TP=2

### 3.1 Pick the model

| Tier | Model | Size | Purpose |
|---|---|---|---|
| **Smoke test** | `unsloth/Qwen3.8-27B-NVFP4` | 22 GB (already local) | proves the plumbing; you'll see half the weights land on each node |
| **Capacity proof** | `RedHatAI/Qwen3-VL-235B-A22B-Instruct-NVFP4` | ~130 GB (needs download) | genuinely cannot fit on one Spark |

Start with the smoke test — you're testing the *mechanism*, not the model.

### 3.2 Shared environment block

Put this in `~/spark-cluster.env` **on both nodes** (same content, `VLLM_HOST_IP` differs):

```bash
export FABRIC_IF=enp1s0f1np1
export NCCL_SOCKET_IFNAME=$FABRIC_IF
export GLOO_SOCKET_IFNAME=$FABRIC_IF
export TP_SOCKET_IFNAME=$FABRIC_IF
export UCX_NET_DEVICES=$FABRIC_IF
export OMPI_MCA_btl_tcp_if_include=$FABRIC_IF
export NCCL_IB_DISABLE=0
export NCCL_IB_HCA=rocep1s0f1
export NCCL_IB_GID_INDEX=3
export NCCL_DEBUG=INFO            # drop to WARN once it works
export MASTER_ADDR=192.168.100.10
export RAY_memory_monitor_refresh_ms=0
```

### 3.3 Start the Ray head (node 1)

```bash
docker run -d --name vllm-head \
  --gpus all --network host --ipc host --shm-size 16g \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --device /dev/infiniband \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -e VLLM_HOST_IP=192.168.100.10 \
  -e NCCL_SOCKET_IFNAME=enp1s0f1np1 \
  -e GLOO_SOCKET_IFNAME=enp1s0f1np1 \
  -e TP_SOCKET_IFNAME=enp1s0f1np1 \
  -e NCCL_IB_DISABLE=0 -e NCCL_IB_HCA=rocep1s0f1 -e NCCL_IB_GID_INDEX=3 \
  -e NCCL_DEBUG=INFO -e RAY_memory_monitor_refresh_ms=0 \
  nvcr.io/nvidia/vllm:25.11-py3 \
  ray start --head --port=6379 --dashboard-host=0.0.0.0 --block
```

### 3.4 Join the worker (node 2)

```bash
ssh 192.168.100.11 'docker run -d --name vllm-worker \
  --gpus all --network host --ipc host --shm-size 16g \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --device /dev/infiniband \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -e VLLM_HOST_IP=192.168.100.11 \
  -e NCCL_SOCKET_IFNAME=enp1s0f1np1 \
  -e GLOO_SOCKET_IFNAME=enp1s0f1np1 \
  -e TP_SOCKET_IFNAME=enp1s0f1np1 \
  -e NCCL_IB_DISABLE=0 -e NCCL_IB_HCA=rocep1s0f1 -e NCCL_IB_GID_INDEX=3 \
  -e NCCL_DEBUG=INFO -e RAY_memory_monitor_refresh_ms=0 \
  nvcr.io/nvidia/vllm:25.11-py3 \
  ray start --address=192.168.100.10:6379 --block'
```

### 3.5 Confirm the cluster formed — **checkpoint**

```bash
docker exec vllm-head ray status
```

You must see **2 nodes** and **2.0 GPU** total. If you see 1 node, stop and fix it;
nothing downstream will work.

### 3.6 Serve

```bash
docker exec -d vllm-head \
  vllm serve unsloth/Qwen3.8-27B-NVFP4 \
    --served-model-name qwen-27b \
    --tensor-parallel-size 2 \
    --distributed-executor-backend ray \
    --gpu-memory-utilization 0.80 \
    --max-model-len 8192 \
    --host 0.0.0.0 --port 8000

docker logs -f vllm-head
```

Watch for, in order: `NCCL INFO ... NET/IB ...` (RDMA, not `NET/Socket`); both
hostnames in the NCCL init lines; `Loading safetensors checkpoint shards` progressing
on **both nodes**; `Application startup complete`. First startup takes minutes (CUDA
graph compile for `sm_121`).

---

## Phase 4 — Prove both nodes' memory is in use

**`nvidia-smi` reports `[N/A]` on GB10** — GPU memory comes out of the same LPDDR5X
pool as the CPU. **Use `free -g`.**

### 4.1 Baseline, then compare

```bash
for h in 192.168.100.10 192.168.100.11; do \
  echo -n "$h  "; ssh $h "free -g | awk '/Mem:/{print \$3\" GiB used\"}'"; done
```

Before vLLM both read ~4 GiB. After load, the 22 GB smoke test should show **+11 GiB on
each node** (weights halved by TP) + KV cache. The signature is *both numbers moving
together* — that's tensor parallelism splitting the model. If only node 1 climbs, TP
didn't span the cluster.

### 4.2 Ray's own view

```bash
docker exec vllm-head ray status
docker exec vllm-head python -c "import ray; ray.init(address='auto'); print(ray.nodes())"
# each node: Resources: {'GPU': 1.0, ...}, Alive: True
```

### 4.3 Generate + 4.4 baseline, then tear down

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-27b","messages":[{"role":"user","content":"In one sentence: what is tensor parallelism?"}],"max_tokens":100}' \
  | python3 -m json.tool

docker exec vllm-head vllm bench serve \
  --model unsloth/Qwen3.8-27B-NVFP4 --served-model-name qwen-27b \
  --base-url http://localhost:8000 \
  --dataset-name random --num-prompts 50 \
  --random-input-len 512 --random-output-len 128

# teardown
docker rm -f vllm-head
ssh 192.168.100.11 'docker rm -f vllm-worker'
```

Two-node TP being *slower* than single-node on a 22 GB model is the **correct and
expected** result — cross-node TP is for models that don't fit on one Spark, not for
speed.

---

## Phase 5 — Capacity proof (the reason the pair was bought)

Once Phase 4 passes, pull a model that cannot fit in 121 GiB:
`hf download RedHatAI/Qwen3-VL-235B-A22B-Instruct-NVFP4`, repeat 3.3–3.6 with
`--tensor-parallel-size 2 --gpu-memory-utilization 0.85 --max-model-len 8192` and the
new model path. `free -g` will show ~65+ GiB used on **each** node; the same command
with `--tensor-parallel-size 1` on a single node OOMs.

> **If TP=2 is too slow at your link bandwidth,** swap to
> `--pipeline-parallel-size 2 --tensor-parallel-size 1`: PP only passes activations
> between nodes at layer boundaries instead of all-reducing every layer — far less
> traffic, but no single-stream latency benefit.

---

## Alternative A — llama.cpp RPC (no-sudo, proven end-to-end, uses your GGUFs)

Lower ceremony than vLLM, works directly on LM Studio GGUFs, and is the fastest way to
a "yes, both nodes are holding the model" answer. Directly runs on the RoCE fabric on
this build (RDMA, not just TCP). Running script:
[`scripts/spark-rpc-test.sh`](scripts/spark-rpc-test.sh).

### A.1 Build on both nodes

```bash
cd ~ && git clone --depth 1 https://github.com/ggml-org/llama.cpp
cd llama.cpp
export PATH=/usr/local/cuda/bin:$PATH
cmake -B build -DGGML_CUDA=ON -DGGML_RPC=ON -DCMAKE_CUDA_ARCHITECTURES=121 \
      -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j "$(nproc)" \
      --target llama-server llama-cli ggml-rpc-server
```

**Gotchas:**
- `CMAKE_CUDA_ARCHITECTURES=121` — GB10 reports compute capability **12.1**.
- The RPC target is **`ggml-rpc-server`**, not `rpc-server` (`gmake: No rule to make
  target 'rpc-server'` otherwise). List with
  `cmake --build build --target help | grep -i rpc`.
- CC template instantiations dominate: budget **~15–25 min**.
- LM Studio's bundled runtime is a dead end: no `rpc-server`, and its `llama-server`
  is a 19 KB loader stub. Build from source.

### A.2 RDMA support

`GGML_RPC_RDMA=ON` is set in the cache and the binary links `libibverbs.so.1` — this
build's cross-node traffic runs over RoCE (verified on the wire: ~8.6 MB RDMA vs ~194
bytes TCP per request). Corrects the common claim that llama.cpp RPC is TCP-only.

### A.3 Ship + start

`ggml` is statically linked into `ggml-rpc-server`, so no `.so` files must travel.

```bash
ssh 192.168.100.11 'mkdir -p ~/llama-rpc'
rsync -a ~/llama.cpp/build/bin/ggml-rpc-server 192.168.100.11:llama-rpc/

cat > ~/llama-rpc/start_rpc.sh <<'SH'
#!/usr/bin/env bash
cd /home/nielsbantilan/llama-rpc
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
exec ./ggml-rpc-server -H 0.0.0.0 -p 50052
SH
ssh 192.168.100.11 'chmod +x ~/llama-rpc/start_rpc.sh; \
  setsid nohup ~/llama-rpc/start_rpc.sh > ~/llama-rpc/rpc.log 2>&1 < /dev/null & echo launched'
sleep 4
ssh 192.168.100.11 'tail -5 ~/llama-rpc/rpc.log; ss -ltn | grep 50052'
```

Healthy output: `ggml_cuda_init: found 1 CUDA devices (Total VRAM: 124608 MiB)` and
`LISTEN 0 1 0.0.0.0:50052`. **Skip `-c`** (keeps node 2 from caching tensors; the
cache cost 28–50 GB of writes during first load).

### A.4 Serve, split across both nodes

```bash
export LD_LIBRARY_PATH=~/llama.cpp/build/bin:/usr/local/cuda/lib64:$LD_LIBRARY_PATH
setsid nohup ~/llama.cpp/build/bin/llama-server \
  -m <path-to-first-gguf-shard> \
  --rpc 192.168.100.11:50052 \
  -ngl 999 --host 0.0.0.0 --port 8080 -c 4096 \
  > ~/llama-server.log 2>&1 < /dev/null &
```

llama.cpp assigns layers across local CUDA0 + the RPC device automatically (override
`-ts 1,1` for a specific ratio). **Readiness wording matters:** grep for
`model loaded|listening on http://0.0.0.0:8080` — `server is listening` never appears
and would hang a wait-loop.

### A.5 Verified results (llama.cpp path)

**Qwen3.6-35B-A3B-UD-Q4_K_XL (21 GB):** load 44 s; node memory 6→17 (+11) / 4→16
(+12) GiB; 48 tok/s generation. Both nodes moved together → spanning works.

**Qwen3.8-Flash-Next-UD-Q4_K_XL (111.3 GB, cannot fit one Spark):** load 3 m 02 s;
6→73 (+67) / 5→45 (+40) GiB, ~107 GiB resident across the pair; **23.6 tok/s**; prompt
eval 96 tok/s. Pass only the `-00001-of-00004.gguf` shard to `-m`; llama.cpp finds the
rest.

Reasoning models (Qwen3.x) consume `max_tokens` in `reasoning_content`; pass
`"chat_template_kwargs":{"enable_thinking":false}` or raise `max_tokens`.

---

## Alternative B — SGLang

No Ray; SGLang handles rendezvous itself.

```bash
# node 1 (rank 0)
docker run --rm --gpus all --network host --ipc host --shm-size 16g \
  --ulimit memlock=-1 --device /dev/infiniband \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -e NCCL_SOCKET_IFNAME=enp1s0f1np1 -e NCCL_IB_HCA=rocep1s0f1 -e NCCL_IB_GID_INDEX=3 \
  lmsysorg/sglang:latest \
  python3 -m sglang.launch_server \
    --model-path unsloth/Qwen3.8-27B-NVFP4 \
    --tp 2 --nnodes 2 --node-rank 0 \
    --dist-init-addr 192.168.100.10:5000 \
    --host 0.0.0.0 --port 30000

# node 2 (rank 1) — identical except --node-rank 1
```

Verify `lmsysorg/sglang` has an `arm64`/`sm_121` build before committing time; if not,
build from source in the NGC PyTorch container. (Not pursued on this box — vLLM path
won.)

---

## Findings worth remembering

1. **~13 Gb/s = ConnectX-7 slot-power bug, fixed by rebooting with the cable in.** (§0.3)
2. **~100 Gb/s per port is healthy**, not 200. (§0.3b)
3. **MTU 9000 is correct, not a bandwidth fix.** (§0.3c)
4. **`nvidia-smi` lies on GB10; `free -g` is the proof.** (§Phase 4)
5. **`sudo` needs a password on both nodes** — the docker group fix is one command
   (`/usr/local` → `sudo usermod -aG docker $USER`), and rsync replaces NFS when root
   isn't available.
6. **`pkill -f <name>` over ssh kills your own session** (it matches the ssh wrapper's
   command line). Use a script file on the remote host or kill by recorded PID. Ka-ching
   — this trap is responsible for the most confusing failures in all three runbooks.
7. **LM Studio's bundled llama.cpp cannot do multi-node** (no `rpc-server`, loader-stub
   binary). It still works great as a *client* of any OpenAI-compatible endpoint.
8. **llama.cpp RPC over RoCE is real** on this build (RDMA ~8.6 MB / TCP ~194 B).

---

## Helper scripts (this directory)

| Path | What it is |
|---|---|
| [`scripts/spark-rpc-test.sh`](scripts/spark-rpc-test.sh) | End-to-end llama.cpp RPC test: ships binaries to node 2, starts `rpc-server`, serves across both nodes with memory baseline/comparison |
| [`scripts/nccl-probe.sh`](scripts/nccl-probe.sh) | Two-rank NCCL all-reduce probe in containers (`rank 0|1`, optional size/PREALLOC) — quick RDMA transport check |
| [`scripts/nccl_test.py`](scripts/nccl_test.py) | The torch NCCL payload used by `nccl-probe.sh` (all_reduce + optional unified-memory preallocation) |
| [`scripts/discover-sparks`](scripts/discover-sparks) | NVIDIA's utility to auto-discover Spark neighbors via `avahi-browse` and emit an MPI hosts file (Apache-2.0, license header retained) |

## Model inventory on node 1 (at time of capture)

| model | size |
|---|---|
| `deepseek-ai/DeepSeek-V4-Flash-0731` (FP8, the vLLM service) | 155 GB |
| `unsloth/Qwen3.8-Flash-Next-GGUF` | 104 GB (111.3 GB GGUF) |
| `Qwen/Qwen3-Next-80B-A3B-Thinking-FP8` | 76 GB |
| `Qwen/Qwen3.6-35B-A3B` | 66 GB |
| `unsloth/gpt-oss-120b` | 60 GB |
| `unsloth/Qwen3-Next-80B-A3B-Instruct-bnb-4bit` | 39 GB |
| `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` | 22 GB |
| `unsloth/Qwen3.8-27B-NVFP4` | 21 GB (also synced to node 2) |
| `stabilityai/stable-diffusion-xl-base-1.0` | 6 GB |

---

## Quick reference

```bash
# fabric health
ibv_devinfo -d rocep1s0f1 | grep -E 'state|active_mtu|active_width|active_speed'
#           expect: PORT_ACTIVE, active_mtu 4096, active_width 2X, active_speed 100.0 Gbps
ssh -f 192.168.100.11 'setsid bash /tmp/ibsrv.sh'; sleep 3
ib_write_bw -d rocep1s0f1 -x 3 --report_gbits -D 5 192.168.100.11   # expect ~100 Gb/s

# memory on both nodes (nvidia-smi will NOT show this on GB10)
for h in 192.168.100.10 192.168.100.11; do \
  echo -n "$h  "; ssh $h "free -g | awk '/Mem:/{print \$3\" GiB\"}'"; done

# RDMA vs TCP on the wire
C=/sys/class/infiniband/rocep1s0f1/ports/1/counters; N=/sys/class/net/enp1s0f1np1/statistics
R1=$(cat $C/port_xmit_data); T1=$(cat $N/tx_bytes)
# ... one request ...
R2=$(cat $C/port_xmit_data); T2=$(cat $N/tx_bytes)
echo "RDMA: $(( (R2-R1)*4 )) B  TCP: $(( T2-T1 )) B"   # port_xmit_data counts 4-byte words

# node 2 RPC server state
ssh 192.168.100.11 'tail -5 ~/llama-rpc/rpc.log; ss -ltn | grep 50052'

# teardown (llama.cpp)
kill <llama-server-pid>
ssh 192.168.100.11 'pkill ggml-rpc-server'   # bare name, NOT pkill -f
```

---

## DeepSeek-V4-Flash-0731: the jump to the production vLLM service

The llama.cpp config above (~25 tok/s) was superseded on 2026-09-12 by the **vLLM +
DSpark** deployment at **~75 tok/s** — the service codified in
[`../deepseek-v4-vllm/`](../deepseek-v4-vllm/). That document covers the recipe
(MiaAI `0731-ablit`), the exact image/checkpoint pins, the `.env.dspark` deltas, the
NCCL environment, the drop-caches wedge fix, and the systemd unit. This setup runbook
is the fabric + plumbing layer underneath it.
