# DSH — DeepSeek Harness web service (macOS)

This folder installs and manages the **DeepSeek Harness** (dsh) as an always‑on background web
service on macOS: a LaunchAgent keeps `dsh web` running on `http://127.0.0.1:3080/`, and a small
Swift menu‑bar app gives you a green status icon to open/restart/observe it from the top‑right.

Everything is **rehydratable**: paths and the LaunchAgent label are derived from the current user
at install time (no hardcoded `nielsbantilan`/node‑version references), and real API keys are never
committed (referenced via env / credentials template).

## What's in here

```
dsh/
├── README.md                        # this file
├── install.sh                       # install/update LaunchAgent + menu bar app
├── launchagent/dsh-web.plist.tpl    # LaunchAgent template (label/paths substituted at install)
├── menubar/dsh-menubar.swift        # macOS menu bar status app (Swift, no deps)
├── scripts/setup-web-profile.sh     # one-time bootstrap: dsh CLI, web profile, providers, creds
├── profile/web/                     # the "web" dsh profile (bundle manifest + patch layer)
└── config/
    ├── settings.yaml                # provider config for llm-pi-ai (dgx-spark + qwen-token-plan)
    └── credentials.example.yaml     # template for ~/.dsh/.credentials.yaml (secrets)
```

## Concept / context

- **dsh** is the DeepSeek Harness agent — a Node CLI (`@deepseek-ai/dsh`) with an extensible
  profile system. `dsh web` serves a browser UI on port `3080`.
- **Profiles** live in `~/.dsh/profiles/<name>/`; this stack ships a `web` profile whose bundles
  (`@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-web-app`) compose the Web app.
- **Providers** are declared in `~/.dsh/settings.yaml` under `llm-pi-ai.providers`:
  - `dgx-spark` — locally hosted DeepSeek V4 Flash at `http://100.70.69.103:8888/v1` (default model).
  - `qwen-token-plan` — QwenCloud token‑plan API (cloud DeepSeek V4), key via `QWEN_TOKEN_PLAN_API_KEY`.
- Keys are resolved from the environment or from `~/.dsh/.credentials.yaml` (0600).

## Prerequisites

- macOS (LaunchAgent + menu bar app are macOS‑specific).
- [nvm](https://github.com/nvm-sh/nvm) with a Node.js ≥ 20 runtime.
- The DGX Spark box reachable at `http://100.70.69.103:8888/v1` (Tailscale) — or update the URL.

## Install (fresh machine)

```bash
cd local-ai/dsh

# 1) bootstrap: installs dsh CLI, creates the web profile, provider settings, credentials template
./scripts/setup-web-profile.sh

# 2) fill in the cloud key either in your shell rc or the credentials file:
#    nano ~/.dsh/.credentials.yaml          # set refs: QWEN_TOKEN_PLAN_API_KEY

# 3) install the service (LaunchAgent + menu bar app + login item)
./install.sh
```

After install, open <http://127.0.0.1:3080/> and a green **DSH** menu‑bar icon sits top‑right.

## Start / Stop / Restart / Status

`install.sh` runs everything, but the underlying service is a LaunchAgent labeled
`com.<username>.dsh-web`. Replace `USER` below with your username, or grab the real label with:

```bash
LAUNCHCTL_LABEL="com.$(whoami).dsh-web"
```

| Action | Command |
|--------|---------|
| **Start** (load + enable) | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.$(whoami).dsh-web.plist` |
| **Restart** | `launchctl kickstart -k gui/$(id -u)/com.$(whoami).dsh-web` |
| **Stop** (unload) | `launchctl bootout gui/$(id -u)/com.$(whoami).dsh-web` |
| **Status** (state/PID/last exit) | `launchctl print gui/$(id -u)/com.$(whoami).dsh-web` |
| Show managed plist | `launchctl print gui/$(id -u)/com.$(whoami).dsh-web | head -1` |

> The LaunchAgent has `KeepAlive = true`, so it auto‑restarts if the process crashes, and
> `RunAtLoad = true` so it starts at login. To temporarily stop the UI without uninstalling, use
> `kickstart` off‑cycle or `bootout`, and `bootstrap` again to bring it back.

The menu bar app also exposes **Restart Service** (⌘R) and **Open Web UI** (⌘O) from its menu.

## Observe

- **Web UI:** <http://127.0.0.1:3080/>
- **stdout log:** `~/Library/Logs/dsh-web.out.log`
- **stderr log:** `~/Library/Logs/dsh-web.err.log`
- **Follow live:**
  ```bash
  tail -f ~/Library/Logs/dsh-web.out.log ~/Library/Logs/dsh-web.err.log
  ```
- **Is it up?** `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3080/`
- **Process:** `pgrep -fl "dsh web"` — a running PID means the service is alive.
- Menu bar icon is **green** when the service responds, **gray** when down (checked every 10s).

## Rehydration notes

- `./install.sh` and `./scripts/setup-web-profile.sh` are idempotent — safe to re‑run after updates.
- If you upgrade `dsh` globally (`npm i -g @deepseek-ai/dsh`), the LaunchAgent keeps pointing at the
  old binary path because it's baked into the plist. Fix by re‑running `./install.sh` (it re‑writes
  the plist with the current `command -v dsh`). To verify: `launchctl print … | grep -A2 dsh`.
- `model id`s in `config/settings.yaml` must match model ids the provider exposes. If a provider
  changes its catalog, update the `models` list there.
- Never commit `~/.dsh/.credentials.yaml` or real keys — use the template + env vars.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Gray icon / UI unreachable | `launchctl kickstart -k gui/$(id -u)/com.$(whoami).dsh-web`, then check `dsh-web.err.log` |
| Port 3080 in use | `lsof -nP -iTCP:3080 -sTCP:LISTEN`; a stray manual `dsh web` may hold it — kill it, then kickstart |
| "dsh: command not found" at login | Node path missing in launchd — re‑run `./install.sh` so `__NODE_BIN__` is correct |
| Cloud model 401/403 | `QWEN_TOKEN_PLAN_API_KEY` not set/rotated — refresh it in env or `~/.dsh/.credentials.yaml` |
| Want a different port | Edit `dsh-web.plist.tpl` `ProgramArguments` to add `--port 8080`, then re‑run `./install.sh` |
