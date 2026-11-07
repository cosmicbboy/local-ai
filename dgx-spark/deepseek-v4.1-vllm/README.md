# DeepSeek-V4.1-Flash vLLM service (TP=2 across 2× DGX Spark)

> **Status: PREPARED — NOT YET DEPLOYABLE**
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

## Blocking items (must be resolved before swap)

| # | Blocker | Status | Notes |
|---|---------|--------|-------|
| 1 | **No vLLM recipe** | 🔴 Blocker | `recipes.vllm.ai` returns "No recipe for deepseek-ai/DeepSeek-V4.1". Serving parameters (kv-cache-dtype, block-size, TP sizing, memory utilization) are **not yet validated** for this hardware. |
| 2 | **No DSpark/GB10 image** | 🔴 Blocker | The Anemll image (`dspark-vllm-gx10:0.1.1`) targets V4's `DeepseekV4ForCausalLM`. A V4.1-capable image with B12X/SM12x kernels must be built or sourced. Check `eugr/spark-vllm-b12x:latest` or `vllm/vllm-openai:nightly`. |
| 3 | **DSpark support unknown** | 🟡 Risk | V4.1 checkpoints do **not** ship a `dspark_*` config block (unlike the V4 DSpark fused checkpoint). MTP (`method: mtp`) is the known speculative path. Whether a community DSpark module exists for V4.1 is unconfirmed. |
| 4 | **Checkpoint download** | 🟢 Ready | Model is public on HuggingFace (MIT license, no gate). ~155 GiB estimated (similar to V4). Both nodes need the full FP8 checkpoint. |
| 5 | **New tokenizer mode** | 🟡 Verify | V4.1 uses `--tokenizer-mode deepseek_v41` (vs V4's `deepseek_v4`). vLLM main branch has the mode, but the pinned Anemll 0.25.2 image predates it. Stock vLLM ≥ 0.28.0 has it. |
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
| Checkpoint size | ~155.4 GiB (FP8+MXFP4) | ~TBD GiB (FP8) |
| vLLM version | 0.25.2.dev0 (Anemll fork) | ≥ 0.28.0 (stock vLLM has `deepseek_v41`) |
| License | MIT | MIT |

## File manifest (this directory)

| Path | What it is |
|------|------------|
| `README.md` | This file — overview and blocker tracking |
| `SWAP-RUNBOOK.md` | **Step-by-step cutover procedure** from V4 to V4.1 |
| `systemd/deepseek-v4.1-flash.service` | Draft systemd unit (mirrors V4 unit, adapted paths/names) |
| `systemd/deepseek-v4.1-flash-watchdog.service` | Draft watchdog unit |
| `systemd/deepseek-v4.1-flash-watchdog.timer` | Draft watchdog timer |
| `scripts/serve-dspark-ds41.sh` | Draft start wrapper (mirrors V4's `serve-dspark-ds4.sh`) |
| `scripts/dspark-wait-cluster-v41.sh` | Draft pre-start gate (image name updated) |
| `scripts/dspark-ds41-mkcache.sh` | Draft HF-cache builder |
| `scripts/deepseek-v4.1-flash-watchdog.sh` | Draft watchdog script |
| `config/DEPLOYED.env.dspark.v41` | Draft `.env.dspark` for V4.1 (annotated with TODOs) |
| `config/env-deltas-v41.md` | Deltas vs the V4.1 recipe example (once available) |
| `patches/` | Will hold patches once the community image is known |

## Upstream references

- **Model (Sept):** <https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash>
- **Model (Oct):** <https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017>
- **V4 recipe (current):** <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash>
- **V4.1 recipe:** <https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4.1-Flash> — **does not exist yet**
- **vLLM V4.1 support:** `vllm.models.deepseek_v41` module in vLLM main
- **Anemll DSpark (V4 only):** <https://github.com/Anemll/dspark-vllm-gx10>
- **Community Spark image:** `eugr/spark-vllm-b12x:latest` (referenced by V4 recipe for DGX Spark)
