# OpenCode

[OpenCode](https://opencode.ai) configuration for two DeepSeek V4 endpoints plus Ollama.

## Providers

| Provider | Endpoint | Key | Models |
|----------|----------|-----|--------|
| `dgx-spark` | `http://100.70.69.103:8888/v1` (local) | `EMPTY` | `deepseek-v4-flash-0731` |
| `qwen-token-plan` | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` (cloud) | `QWEN_TOKEN_PLAN_API_KEY` | `deepseek-v4-pro`, `deepseek-v4-flash-0731`, `glm-5.2` |
| `ollama` | `http://localhost:11435/v1` | — | `glm-4.7-flash`, `qwen3-coder-next` (auto-launched) |

Default model is the locally‑hosted `dgx-spark/deepseek-v4-flash-0731`.

## Install

1. Install OpenCode (see https://opencode.ai/docs/).
2. Copy the config into place:

```bash
mkdir -p ~/.config/opencode
cp opencode.json ~/.config/opencode/opencode.json
```

3. Make sure the QwenCloud key is exported when you launch OpenCode:

```bash
export QWEN_TOKEN_PLAN_API_KEY="sk-..."
```

The `apiKey` field uses OpenCode's `${env:QWEN_TOKEN_PLAN_API_KEY}` reference, so OpenCode reads
the key from your environment — nothing secret is stored on disk.

## Use

- Default: `opencode` → uses the local DGX Spark model.
- Pick a cloud model: use the model switcher inside OpenCode, or set
  `"model": "qwen-token-plan/deepseek-v4-pro"` at the top of `opencode.json`.
- Ollama models appear automatically if you have Ollama running on port `11435`.

## Notes for rehydration

- The DGX Spark box's IP (`100.70.69.103`) is a Tailscale LAN address — update it if the box
  moves or the machine joins a different tailnet.
- `opencode.json` is secret‑free (the cloud key is env‑referenced and the local key is `EMPTY`),
  so it's safe to commit.
