# Pi

[pi](https://github.com/earendil-works/pi-coding-agent) configuration for the local AI stack.

## Providers

| Provider | Endpoint | Key | Models |
|----------|----------|-----|--------|
| `dgx-spark` | `http://100.70.69.103:8888/v1` (local) | `EMPTY` | `deepseek-v4-flash-0731` |
| `qwen-token-plan` | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` (cloud) | `QWEN_TOKEN_PLAN_API_KEY` | `deepseek-v4-flash-0731`, `deepseek-v4-pro`, `deepseek-v4-pro-0813`, `glm-5.2`, `qwen3.8-max` |

Defaults (in `settings.json`): `dgx-spark` / `deepseek-v4-flash-0731` — the locally hosted model.

## Files

- `settings.json` → `~/.pi/agent/settings.json` — default provider/model, theme, packages.
- `models.json` → `~/.pi/agent/models.json` — the custom provider + model registry.
- `auth.json.example` → `~/.pi/agent/auth.json` — API key references (env‑only, no secrets).

> `models-store.json` (pi's cached remote catalog under `~/.pi/agent/`) is generated at runtime and
> is **not** committed — the essential, hand‑authored pieces are the three files above.

## Install / rehydrate

```bash
mkdir -p ~/.pi/agent
cp settings.json ~/.pi/agent/settings.json
cp models.json  ~/.pi/agent/models.json
cp auth.json.example ~/.pi/agent/auth.json
chmod 600 ~/.pi/agent/auth.json

# ensure the key is exported in your shell rc
export QWEN_TOKEN_PLAN_API_KEY="sk-..."
```

Then just run `pi` in any repo. The `pi-vision` and `pi-sessions` packages in `settings.json` are
pulled automatically by pi on first launch.

## Notes

- `auth.json` uses `apiKeyEnv` — a *reference* to the env var, so it's safe to version. Keep the
  real key in your shell profile or keychain.
- Update the DGX Spark `baseUrl` if the LAN box's Tailscale IP changes.
- The vision extension (`~/.pi/agent/extensions/pi-vision.json`) routes image understanding through
  `qwen-token-plan/qwen3.8-max` — a handy cloud fallback for vision on the local stack.
