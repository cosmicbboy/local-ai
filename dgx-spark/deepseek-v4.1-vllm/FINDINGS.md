# DeepSeek-V4.1-Flash on 2× DGX Spark: findings (2026-11-08 → 2026-11-09)

> **Outcome: not deployed. V4 (`deepseek-v4-flash-0731`) stays the live service on `:8888`.**
>
> The full-precision V4.1-Flash-1017 checkpoint does not fit in two GB10s. The only builds that do are
> community ~2.5–2.8 bpw EXL3 quants served by community engines (not stock vLLM), with a measurable
> tool-call quality loss. Revisit when one of the "What would change this" items lands.

## 1. Full precision does not fit

Measured from the safetensors headers of `deepseek-ai/DeepSeek-V4.1-Flash-1017` at revision
`1bae0e1088993b9b82de08f59de5be5a34e42170` (48 shards, 510.3 GB):

| Component | Size |
|-----------|------|
| Routed experts (384 × 40 layers, already MXFP4) | 268.9 GiB |
| Engram tables (`layers.1`, `layers.14`; shards 47–48, ~95 GiB each) | 189.1 GiB |
| Attention / dense / shared experts | 9.0 GiB |
| MTP + DSpark drafter | 7.4 GiB |
| Vision encoder | 0.8 GiB |
| **Total** | **475.2 GiB** |

Each GB10 has ~121 GiB of unified memory, shared by CPU and GPU: ~242 GiB across the pair. V4-Flash-0731
is ~155 GiB, which is why it fits. V4.1's routed experts alone exceed the pair's memory. The V4.1 config is
also a bigger backbone than V4 (hidden 5120 vs 4096, 384 vs 256 routed experts) plus the new Engram
conditional memory.

## 2. No 1–2 bit path on stock vLLM

| Variant | Size | Why it doesn't help |
|---------|------|---------------------|
| `nvidia/DeepSeek-V4.1-Flash-1017-NVFP4` | ~400 GiB | Experts are already FP4 (MXFP4→NVFP4 is lossless, same size); only Engram shrinks. Its `--engram-config '{"cpu_offload":true}'` moves ~97 GiB/node to host RAM, which on GB10 is the same memory pool. Needs vllm#61530. Validated on 4× GB300. |
| `intel-ai/...-MXFP4-Mixed-CT-AutoRound`, `...-W4A16-Engram-AutoRound` | 4-bit | Same problem: 4-bit experts are what we already have. |
| `unsloth/DeepSeek-V4.1-Flash-1017-GGUF` UD-IQ1_S / IQ1_M / IQ2_XXS | 217 / 233 / 280 GiB | llama.cpp only (unsloth's PR), not vLLM. |

Stock vLLM has no 1–2 bit format for `deepseek_v41`.

## 3. Community builds that do fit (all EXL3, all non-stock engines)

The trick that makes them fit: keep the 189 GiB of Engram tables **on NVMe** and read the rows each token
needs at lookup time (Linux AIO / O_DIRECT), and quantize the routed experts to ~2.5–2.8 bpw. All of them
read the Engram tables from DeepSeek's official 1017 shards 47–48.

| Build | Size excl. Engram | Engine | Reported (authors' numbers, not reproduced here) |
|-------|-------------------|--------|-----------------------------------------|
| `bertholomus/DeepSeek-V4.1-Flash-1017-EXL3-2.5bpw` @ `fdae35e8` | ~172 GiB | bertholomus's TensorFold fork (native Zig engine), recipe `bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10` v0.7.5 | 1M context, 32 streams; decode ~106 code / ~61 prose / ~119 structured tok/s; 10.3 / 13.0 GiB free at the lowest during a 1M prompt |
| `sudoingx/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw` (and 2.8bpw v2.0) | ~183 GiB | vLLM `6e517b15` + patch series + `vllm_exl3_moe` plugin, `sudoingX/dgx-spark-deepseek-v41` | IFEval 89.1 vs 90.4 native; ~100 / 59 / 141 tok/s; 8–9 GiB free per node after load |
| `0xSero/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw` | ~185 GiB | sudoingX's stack, CI-built image `ghcr.io/sybil-solutions/deepseek-v4.1-flash-exl3-spark` (pinned digest) | KLD 0.0304 / top-1 94.95 % vs native |

For comparison, V4 on this pair decodes at ~75 tok/s (`../README.md`).

**Quality cost for agent use.** The bertholomus card measures KL / top-1 agreement against the original
1017 weights. At 2.5 bpw: overall short-row top-1 92.0 %, code 95.2 %, but **tool-call turns 79.4 %
(KL 0.59)**. The authors say so directly: "for agent work that needs the closest match, the 4.0 bpw quant
(four nodes) is the better pick". Our main consumers are agent harnesses, so this is the biggest reason
not to push the 2-node path now.

## 4. What the TensorFold (bertholomus 2.5 bpw) attempt found on our pair

Taken up to just before the build; stopped by choice on 2026-11-09. Site-specific issues found:

1. **RDMA GID index.** The engine's RDMA ring hardcodes GID index 5 (`zig/src/families/dsv41/model.zig`,
   two call sites) and this engine line ignores `TF_RDMA_GID_INDEX`. On both of our nodes index 5 is
   empty on every RoCE device. Our RoCE v2 IPv4 entries are at **index 3** (index 0/1 link-local v1/v2,
   2/3 IPv4 v1/v2), the same index V4's NCCL uses:

   | Device | Node 1 | Node 2 |
   |--------|--------|--------|
   | `rocep1s0f1` (`enp1s0f1np1`) | 192.168.100.10 @ GID 3 | 192.168.100.11 @ GID 3 |
   | `roceP2p1s0f1` (`enP2p1s0f1np1`) | 192.168.101.10 @ GID 3 | 192.168.101.11 @ GID 3 |

   Fix written, not built or tested: [`patches/tensorfold-0001-rdma-gid-index-from-env.patch`](patches/tensorfold-0001-rdma-gid-index-from-env.patch)
   (reads `TF_RDMA_GID_INDEX`, default 5), plus a recipe `serve.sh` change so its preflight and
   `NCCL_IB_GID_INDEX` use the same index. Alternative without patching: add an address to each link
   interface so a RoCE v2 IPv4 entry lands at index 5 (root, host network change).
2. **Node 2's memory-region ceiling still applies.** Node 2 is still on the drifted `7.0.0-1019-nvidia`
   kernel (node 1: `6.17.0-1014-nvidia`). The engine uses NCCL for prompt chunks, so it needs
   `NCCL_MAX_NCHANNELS=8` like V4 does (see `../deepseek-v4-vllm/README.md`). The recipe's `node_run.sh`
   passes `NCCL_*` variables through to the container.
3. **Build.** The engine must be built from source: Zig exactly 0.17.0 (`.zig-version`; the official
   aarch64 tarball sha256 is `9e8d1166…4ff8`) and the CUDA toolchain of `nvcr.io/nvidia/pytorch:26.07-py3`,
   which is also the runtime image. Then per node: `tools/serving_1017.py` on the weights, a ~93 GB rank
   weight file (`node_inputs.sh`), and `kit/verify_kit.sh`. The kit ships prebuilt cubins and a prebuilt
   `libtfgrammar.so`. The ranks' rendezvous port is unauthenticated (fine on the private link only).
4. **Serving shape.** `SERVED_NAME` and `PORT` are config values, so it could take over `:8888` as
   `deepseek-v4-flash-0731` without changing harness configs. The API is TensorFold's OpenAI-compatible
   server, not vLLM's. Clients would need regression testing (reasoning fields, tool-call format).

## 5. The 2026-11-08 cutover attempt (pi session `01a1b3cc`)

What happened, from the session log and `journalctl --user -u deepseek-v4.1-flash.service`:

- It marked all blockers "resolved" after finding `eugr/spark-vllm-b12x:latest` knows the
  `DeepseekV41ForCausalLM` architecture, then downloaded the full 476 GiB checkpoint to both nodes. The
  ~155 GiB size estimate in this directory was copied from V4, so nobody checked it would fit.
- It replaced the planned launcher with an improvised `~/dspark-ds41/start-deepseek-v4.1-flash.sh`:
  `--tensor-parallel-size 1 --pipeline-parallel-size 2`, none of V4's RoCE/NCCL env, no drop-caches
  sidecar, and a 10 s `sleep` before declaring failure. It stopped V4 and ran it; the unit failed.
- It reported the node-2 `WorkerProc initialization failed` as the root cause. It wasn't: the checkpoint
  cannot be loaded on this hardware by any launcher.
- It rolled V4 back but **left `deepseek-v4-flash-watchdog.timer` stopped**, so V4 had no automatic
  recovery from 22:48 until it was restarted on 2026-11-08 at 23:40. Any future swap's rollback must
  restart the watchdog timer as well as the service.

## 6. State left on the machines

| What | Where | Size | Status |
|------|-------|------|--------|
| V4 service + watchdog | `deepseek-v4-flash.service`, `deepseek-v4-flash-watchdog.timer` | | active, enabled, serving `deepseek-v4-flash-0731` |
| V4.1 vLLM unit (pi session) | `~/.config/systemd/user/deepseek-v4.1-flash.service` | | disabled, failed state cleared; points at the improvised `~/dspark-ds41/*.sh` |
| Full V4.1 checkpoint | `~/models/deepseek-v4.1-flash-1017-fp8/`, both nodes | 476 GiB each | shards 47–48 verified against HF sha256 on both nodes |
| HF cache copy | `~/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash-1017`, node 1 | | from the pi session |
| Engram hardlinks | `~/dsv41-tp2/engram/` (shards 47–48), both nodes | 0 extra | hardlinks into the checkpoint above |
| Partial 2.5 bpw download | `~/models/dsv41-1017-exl3-2.5bpw/`, node 1 | ~56 GB of ~185 | stopped |
| TensorFold source + Zig 0.17.0 | `~/dsv41-tp2/engine-src` (patched), `~/dsv41-tp2/toolchain`, node 1 | small | not built |
| Images | `eugr/spark-vllm-b12x:latest`, `nvcr.io/nvidia/pytorch:26.07-py3`, both nodes | 17.8 GB / 24.3 GB each | unused |

To reclaim space while keeping a future EXL3 attempt cheap: delete shards 1–46 of the full checkpoint
(~286 GiB per node) but keep shards 47–48, since every 2-node EXL3 build needs exactly those. Nothing has
been deleted.

## 7. What would change this

- **A third and fourth Spark.** bertholomus's 4.0 bpw quant on the 4-node recipe has much closer tool-call
  quality (top-1 87.8 % vs 79.4 %), and `nvidia/...-NVFP4` style builds get closer to fitting.
- **Upstream vLLM support** for EXL3 MoE experts plus Engram on NVMe (today it is the sudoingX patch series
  plus a plugin).
- **Tool-call quality** at ~2.5–2.8 bpw measured on our own agent workloads, not only the authors' panels.
- **Node 2 back on `6.17.0-1014-nvidia`** (needs root), which removes the `NCCL_MAX_NCHANNELS` workaround
  from any engine we pick.
