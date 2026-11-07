# `.env.dspark` — V4.1 deployed deltas vs upstream example

> **STATUS: DRAFT — will be finalized once the V4.1 recipe is available**

The serving config for the DeepSeek-V4.1-Flash vLLM service will live in
`~/dspark-ds41/.env.dspark` on node 1 (synced by the launcher to node 2 at every start).

This document will track the deltas between the upstream `.env.dspark.example` (from the
V4.1 recipe, once available) and the deployed `.env.dspark` for this cluster.

## Anticipated deltas from V4 config

These are the changes from the V4 `DEPLOYED.env.dspark` that are already known:

| Key | V4 Value | V4.1 Value | Why |
|-----|----------|------------|-----|
| `DSPARK_MODEL_OFFICIAL` | `deepseek-ai/DeepSeek-V4-Flash-0731` | `deepseek-ai/DeepSeek-V4.1-Flash-1017` | New model |
| `DSPARK_REVISION` | `9e165c30e2704aec5d9d593cce3eebd58bbef1cb` | `main` (TODO: pin) | New checkpoint |
| `SERVED_MODEL_NAME` | `deepseek-v4-flash-0731` | `deepseek-v4.1-flash-1017` | API model name |
| `DSPARK_VLLM_IMAGE` | `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` | TBD (blocker #2) | Must support V4.1 arch |
| `DEFAULT_THINKING` | `low` | `high` | V4.1 default; clients can override |
| `MTP_NUM_TOKENS` | `5` (DSpark k) | `5` or `3` (depends on blocker #3) | Spec decoding method |

## Architecture-specific changes

V4.1 introduces a new architecture (`DeepseekV41ForCausalLM`) with these implications:

- **Tokenizer mode:** `--tokenizer-mode deepseek_v41` (automatic in vLLM ≥ 0.28.0)
- **Chat template:** Built-in Jinja template (no `encoding/` folder dependency)
- **Vision:** `image-text-to-text` pipeline (optional, can be disabled)
- **Reasoning effort:** Accepts `low/medium/high/max` or integer 1–100 (budget)

## Merge procedure (once recipe is available)

```bash
cd dspark-ds41
cp .env.dspark.example .env.dspark
# Apply the deltas from the table above
# Or copy from config/DEPLOYED.env.dspark.v41 in this repo
```

> ⚠️ `NCCL_MAX_NCHANNELS=8` still needs the passthrough patch from
> `patches/0001-nccl-nchannels-passthrough.patch` (same as V4).
