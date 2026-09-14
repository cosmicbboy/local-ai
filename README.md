# local-ai

Consolidation of my personal **local AI stack** — configuration that lets me rehydrate a
fresh macOS machine (or environment) with the same tooling, providers, and always-on DeepSeek
Harness service I run day‑to‑day.

Everything is plain text, self‑contained, and secret‑free (real API keys are referenced by
environment variable, never committed).

## Layout

| Path | What it is |
|------|-----------|
| [`opencode/`](opencode/) | [OpenCode](https://opencode.ai) config: locally‑hosted DeepSeek V4 (DGX Spark) + the QwenCloud token‑plan API |
| [`pi/`](pi/) | [pi](https://github.com/earendil-works/pi-coding-agent) config: DeepSeek V4 (DGX Spark) + QwenCloud token‑plan API, models and defaults |
| [`dsh/`](dsh/) | The **DSH** (DeepSeek Harness) background web service on macOS: LaunchAgent + menu-bar app, with full run/start/stop/observe docs |
| [`dgx-spark/deepseek-v4-vllm/`](dgx-spark/deepseek-v4-vllm/) | **DeepSeek V4 (vLLM) service** on the 2× DGX Spark cluster: currently-served `deepseek-v4-flash-0731` with DSpark spec decoding, rehydration + ops runbook, systemd unit, wrapper scripts, exact `.env.dspark` |
| [`dgx-spark/dual-dgx/`](dgx-spark/dual-dgx/) | **Dual DGX Spark bring-up**: fabric validation (+ the ConnectX-7 power-throttle fix), node bootstrap, shared storage, and the three cross-node serving paths (vLLM+Ray TP=2, llama.cpp RPC, SGLang) |

## The stack at a glance

- **DGX Spark (local).** DeepSeek V4 Flash, self-hosted on a LAN box at `http://100.70.69.103:8888/v1`
  (OpenAI‑compatible). No key needed (`apiKey: EMPTY`). This is the default model for pi and DSH.
  The serving side of that box is codified under [`dgx-spark/deepseek-v4-vllm/`](dgx-spark/deepseek-v4-vllm/)
  — DeepSeek-V4-Flash-0731, vLLM + DSpark, TP=2 across two DGX Sparks at `http://192.168.100.10:8888/v1`.
- **QwenCloud token‑plan (cloud).** DeepSeek V4 Pro / Flash scoring via Aliyun's token‑plan
  compatible‑mode gateway at `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`.
  Authenticated with `QWEN_TOKEN_PLAN_API_KEY`.
- **DSH (always‑on web service).** The DeepSeek Harness browser UI on `http://127.0.0.1:3080/`,
  kept alive by a LaunchAgent, surfaced through a green menu‑bar icon.
- **2× DGX Spark cluster.** 200 Gb RoCE pair (`spark-a7e9` + `spark-17d7`) hosting the DeepSeek V4
  vLLM service and the media for any multi-node LLM work. Setup/cluster runbooks under [`dgx-spark/`](dgx-spark/).

## Rehydration checklist

1. Clone this repo: `git clone git@github.com:cosmicbboy/local-ai.git`
2. **Node** via nvm (≥ 20 recommended). `dsh` is installed globally with npm.
3. Install the QwenCloud key into your shell profile (see below) so tools pick it up.
4. Follow each subfolder's README in order: `opencode/` → `pi/` → `dsh/`.

```bash
# once, in your shell rc
export QWEN_TOKEN_PLAN_API_KEY="sk-..."   # from QwenCloud token plan
export DGX_SPARK_API_KEY="EMPTY"           # local DGX Spark needs no real key
```

> **Never commit real keys.** Keep them in your shell rc / keychain. The config files in this
> repo read them via `env:...` references and placeholders.
