# DeepSeek-V4.1-Flash vLLM service (TP=2 across 2× DGX Spark)

> **Status: ON HOLD — V4 stays live.** Full findings: [`FINDINGS.md`](FINDINGS.md).
>
> DeepSeek-V4.1-Flash-1017 is ~475 GiB of weights (269 GiB FP4 routed experts + 189 GiB
> Engram tables + 17 GiB rest). The pair has ~242 GiB of unified memory in total, so the
> full checkpoint cannot be served here. Only community ~2.5–2.8 bpw EXL3 builds on
> non-stock engines fit, and they lose the most quality on tool calls. A vLLM cutover was
> attempted on 2026-11-08 and rolled back.
>
> This directory contains the **draft** configuration for swapping the currently-served
> DeepSeek-V4-Flash-0731 service to DeepSeek-V4.1-Flash on the same 2× DGX Spark pair.
> The swap has **not** been executed. See [`SWAP-RUNBOOK.md`](SWAP-RUNBOOK.md) for the
> step-by-step cutover procedure.

## Current state (what is live today)

- **Model:** `deepseek-ai/DeepSeek-V4-Flash-0731` (V4)
- **Architecture:** `DeepseekV4ForCausalLM` / `deepseek_v4`
- **Image:** `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` (vLLM 0.25.2.dev0, custom Anemll build)
- **Speculative decoding:** DSpark k=5 (probabilistic)
- **Service:** systemd user unit `deepseek-v4-flash.service`
- **Runbook:** [`../deepseek-v4-vllm/README.md`](../deepseek-v4-vllm/README.md)

## Target state (what this directory prepares)

- **Model:** `deepseek-ai/DeepSeek-V4.1-Flash-1017` (V4.1, Oct 2026 release) or
  `deepseek-ai/DeepSeek-V4.1-Flash` (Sept 2026 release)
- **Architecture:** `DeepseekV41ForCausalLM` / `deepseek_v41` — **new architecture**
- **Capabilities:** Text + Vision (`image-text-to-text`), built-in Jinja chat template
- **Speculative decoding:** MTP (`method: mtp`) — DSpark support for V4.1 is **unconfirmed**

## Memory blocker (2026-11-08)

Measured from the safetensors headers of `~/models/deepseek-v4.1-flash-1017-fp8`
(revision `1bae0e1088993b9b82de08f59de5be5a34e42170`, 48 shards, 510.3 GB):

| Component | Size |
|-----------|------|
| Routed experts (384 × 40 layers, MXFP4) | 268.9 GiB |
| Engram tables (`layers.1`, `layers.14`; shards 47–48) | 189.1 GiB |
| Attention / dense / shared experts | 9.0 GiB |
| MTP + DSpark head | 7.4 GiB |
| Vision encoder | 0.8 GiB |
| **Total** | **475.2 GiB** |

Each GB10 has ~121 GiB of unified memory shared by CPU and GPU, so ~242 GiB across the
pair. V4-Flash-0731 is ~155 GiB, which is why it fits. None of the published V4.1 variants
fits with room for KV cache:

| Variant | Size | Why it doesn't help on Spark |
|---------|------|------------------------------|
| `nvidia/DeepSeek-V4.1-Flash-1017-NVFP4` | ~400 GiB | Experts are already FP4 (lossless MXFP4→NVFP4); only Engram shrinks. Its `engram-config cpu_offload` moves ~97 GiB/node to host RAM, which on GB10 is the same memory pool. Also needs vllm#61530. |
| `unsloth/DeepSeek-V4.1-Flash-1017-GGUF` UD-IQ1_S / IQ1_M / IQ2_XXS | 217 / 233 / 280 GiB | llama.cpp only (unsloth PR), not vLLM. |

Paths that could work, each a different project rather than a swap: a 3rd/4th Spark, or a
community ~2.5–2.8 bpw EXL3 build on a patched vLLM that reads Engram from NVMe at lookup
time (see below). Stock vLLM has no 1–2 bit format for `deepseek_v41`.

### Community EXL3 builds for 2× DGX Spark (checked 2026-11-09)

All keep the Engram tables out of memory and read them from DeepSeek's official 1017 shards
47–48. Those are already on both nodes at revision `1bae0e10`, which matches. Each needs its
own patched vLLM image; none run on stock vLLM or `eugr/spark-vllm-b12x`.

| Build | Size (excl. Engram) | Stack | Reported |
|-------|---------------------|-------|----------|
| `sudoingx/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw` (also 2.8bpw v2.0) | 183 GiB | vLLM `6e517b15` + patches + `vllm_exl3_moe`, github.com/sudoingX/dgx-spark-deepseek-v41 | IFEval 89.1 vs 90.4 native; ~100/59/141 tok/s code/prose/structured; 8–9 GiB free per node after load |
| `bertholomus/DeepSeek-V4.1-Flash-1017-EXL3-2.5bpw` | 172 GiB | TensorFold TP2 over RDMA, github.com/bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10 | 1M context, 32 streams, ~106/61/119 tok/s |
| `0xSero/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw` | 185 GiB | sudoingX stack, attested image `ghcr.io/sybil-solutions/deepseek-v4.1-flash-exl3-spark` | KLD 0.0304 / top-1 94.95% vs native |

### What went wrong in the 2026-11-08 attempt

- The improvised `~/dspark-ds41/start-deepseek-v4.1-flash.sh` launched `--tensor-parallel-size 1
  --pipeline-parallel-size 2`, without the RoCE/NCCL env, drop-caches sidecar or recipe used by
  V4, and declared failure after a 10 s `sleep`. The node-2 `WorkerProc initialization failed`
  error it reported is not the root cause; the model cannot be loaded on this hardware at all.
- `deepseek-v4-flash-watchdog.timer` was stopped for the swap and not restarted on rollback
  (restarted 2026-11-08 23:40). Any future attempt must restart it in the rollback path.

## Blocking items (must be resolved before swap)

| # | Blocker | Status | Notes |
|---|---------|--------|-------|
| 0 | **Memory** | 🔴 Blocker | ~475 GiB checkpoint vs ~242 GiB across both Sparks. See "Memory blocker". |
| 1 | **No vLLM recipe** | 🔴 Blocker | `recipes.vllm.ai` has no V4.1 entry. `eugr/spark-vllm-b12x:latest` (2026-11-02) knows the architecture, but no serving parameters are validated for GB10. |
| 2 | **No DSpark/GB10 image** | 🟡 Candidate | `eugr/spark-vllm-b12x:latest` contains `DeepseekV41ForCausalLM` with B12X/SM12x kernels and is pulled on both nodes. It has never loaded the model. |
| 3 | **DSpark support unknown** | 🟡 Candidate | The checkpoint ships `dspark_*` config keys and the eugr image has `vllm/models/deepseek_v41/nvidia/dspark.py`. Not exercised. |
| 4 | **Checkpoint download** | ✅ Done | `~/models/deepseek-v4.1-flash-1017-fp8/` on both nodes, 476 GiB each. |
| 5 | **New tokenizer mode** | ✅ Resolved | `--tokenizer-mode deepseek_v41` confirmed in `eugr/spark-vllm-b12x:latest`. |
| 6 | **Vision weights** | 🟡 Optional | V4.1 is `image-text-to-text`. Vision encoder weights add to the checkpoint size. Can be served text-only initially if the vision encoder is a separate download. |
| 7 | **Reasoning effort format** | 🟡 Verify | V4 used `reasoning_effort: low/high/max`. V4.1 accepts `low/medium/high/max` **or** integer 1–100 (mapped to budget). Default is `high` (budget 75). Client code may need updating. |

## V4 vs V4.1 — key architectural differences

| Aspect | V4 (current) | V4.1 (target) |
|--------|-------------|---------------|
| Architecture | `DeepseekV4ForCausalLM` | `DeepseekV41ForCausalLM` |
| Model type | `deepseek_v4` | `deepseek_v41` |
| Tokenizer mode | `--tokenizer-mode deepseek_v4` | `--tokenizer-mode deepseek_v41` |
| Chat template | Custom `encoding/` folder (no Jinja) | **Built-in Jinja template** |
| Vision | Text only | `image-text-to-text` |
| Reasoning effort | `low` / `high` / `max` | `low` / `medium` / `high` / `max` or int 1–100 |
| Spec decoding | DSpark (`dspark_*` in config.json) | MTP (or DSpark if community module emerges) |
| Parameters | 284B total / 13B active | ~284B total / ~13B active (same family) |
| Checkpoint size | ~155.4 GiB (FP8+MXFP4) | ~475.2 GiB (FP8+MXFP4, incl. 189 GiB Engram) |
| vLLM version | 0.25.2.dev0 (Anemll fork) | ≥ 0.28.0 (stock vLLM has `deepseek_v41`) |
| License | MIT | MIT |

## File manifest (this directory)

| Path | What it is |
|------|------------|
| `README.md` | This file — overview and blocker tracking |
| `FINDINGS.md` | **What we learned 2026-11-08/09**: sizes, quantized options, the TensorFold attempt, machine state |
| `REVIEW.md` | Review of the original prep PR (superseded) |
| `SWAP-RUNBOOK.md` | vLLM cutover procedure (superseded: the checkpoint does not fit) |
| `systemd/deepseek-v4.1-flash.service` | Draft systemd unit (mirrors V4 unit, adapted paths/names) |
| `systemd/deepseek-v4.1-flash-watchdog.service` | Draft watchdog unit |
| `systemd/deepseek-v4.1-flash-watchdog.timer` | Draft watchdog timer |
| `scripts/serve-dspark-ds41.sh` | Draft start wrapper (mirrors V4's `serve-dspark-ds4.sh`) |
| `scripts/dspark-wait-cluster-v41.sh` | Draft pre-start gate (image name updated) |
| `scripts/dspark-ds41-mkcache.sh` | Draft HF-cache builder |
| `scripts/deepseek-v4.1-flash-watchdog.sh` | Draft watchdog script |
| `config/DEPLOYED.env.dspark.v41` | Draft `.env.dspark` for V4.1 (annotated with TODOs) |
| `config/env-deltas-v41.md` | Deltas vs the V4.1 recipe example (once available) |
| `patches/` | TensorFold RDMA GID-index patch (untested); vLLM recipe patches TBD |

## Upstream references

- **Model (Sept):** <https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash>
- **Model (Oct):** <https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017>
- **V4 recipe (current):** <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash>
- **V4.1 recipe:** <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4.1-Flash> — **does not exist yet**
- **vLLM V4.1 support:** `vllm.models.deepseek_v41` module in vLLM main
- **Anemll DSpark (V4 only):** <https://github.com/Anemll/dspark-vllm-gx10>
- **Community Spark image:** `eugr/spark-vllm-b12x:latest` (referenced by V4 recipe for DGX Spark)
