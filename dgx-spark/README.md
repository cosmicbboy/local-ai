# dgx-spark

Operational configuration for the **2× NVIDIA DGX Spark (GB10)** cluster at
`spark-a7e9` (node 1 / head) + `spark-17d7` (node 2 / worker), connected with a
Direct QSFP 200 Gb RoCE fabric. Everything here is what is (or was) actually
deployed on the pair, captured so the box can be re-hydrated from scratch.

| Path | What it is |
|------|-----------|
| [`deepseek-v4-vllm/`](deepseek-v4-vllm/) | **The currently-served service** — DeepSeek-V4-Flash-0731, vLLM + DSpark speculative decoding, TP=2 across both Sparks, OpenAI API on `:8888`. Full rehydration + ops runbook, systemd unit, wrapper scripts, and the exact deployed `.env.dspark`. |
| [`dual-dgx/`](dual-dgx/) | **Dual-node bring-up runbook** — fabric validation, the ConnectX-7 power-throttle bug, node bootstrap, shared storage, and the three ways to serve a model across both Sparks (vLLM+Ray TP=2, llama.cpp RPC, SGLang), with the helper scripts. |

## The cluster at a glance

| | node 1 (head, rank 0) | node 2 (worker, rank 1) |
|---|---|---|
| Hostname | `spark-a7e9` (Tailscale `flint-dgx`) | `spark-17d7` |
| Fabric IP / netdev / RDMA | `192.168.100.10` / `enp1s0f1np1` / `rocep1s0f1` | `192.168.100.11` / same names |
| GPU | GB10, compute cap `sm_121`, 124 GiB unified VRAM | same |
| NVIDIA driver | 580.142 | 580.173.02 |
| Kernel | 6.17.0-1014-nvidia | 7.0.0-1019-nvidia |
| OS | Ubuntu 24.04 (LTS) | Ubuntu 24.04 (LTS) |
| CUDA (driver) | 13.0 | 13.0 |

> `nvidia-smi` reports `[N/A]` for memory on GB10 — the GPU allocates from the same
> LPDDR5X pool as the CPU. **Always use `free -g`, never `nvidia-smi`, to reason
> about GB10 memory.**

## What is (and isn't) captured here

- **`deepseek-v4-vllm/`** is the production service on node 1 (systemd user unit
  `deepseek-v4-flash.service`, currently ~75 tok/s decode). This is the artifact to
  rebuild on a new pair.
- **`dual-dgx/`** is the how-to for turning two fresh Sparks into a cluster and
  proving the model actually spans both. It also records the hard-won fabric
  findings (the ~13 Gb/s power-throttle bug, PB-level expectations, etc.).
- Deprecated singles like the `aidendle94/sparkrun-vllm-ds4-gb10` attempt (~24
  tok/s, `ibv_reg_mr` failures → abandoned) are *described* in the runbooks for
  history but not vendored as living config.
