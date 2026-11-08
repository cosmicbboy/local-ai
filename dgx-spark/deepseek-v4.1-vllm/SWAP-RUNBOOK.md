# Swap Runbook: DeepSeek-V4 → V4.1 on 2× DGX Spark

> **Purpose:** Step-by-step procedure to safely migrate the live DeepSeek-V4-Flash-0731
> vLLM service to DeepSeek-V4.1-Flash on the same dual-DGX-Spark pair.
>
> **Estimated downtime:** 30–60 minutes (checkpoint download is separate and can be
> done in advance).
>
> **Rollback:** V4 service and checkpoint are preserved. Rollback is a single
> `systemctl` switch.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Pre-Swap Preparation (Zero Downtime)](#2-pre-swap-preparation-zero-downtime)
3. [Validation Gate](#3-validation-gate)
4. [The Swap (Maintenance Window)](#4-the-swap-maintenance-window)
5. [Post-Swap Validation](#5-post-swap-validation)
6. [Rollback Procedure](#6-rollback-procedure)
7. [Post-Swap Cleanup](#7-post-swap-cleanup)
8. [Known Risks and Mitigations](#8-known-risks-and-mitigations)

---

## 1. Prerequisites

Before starting the swap, confirm all blockers from
[`README.md`](README.md) are resolved:

- [ ] **vLLM recipe exists** for `deepseek-ai/DeepSeek-V4.1-Flash` on recipes.vllm.ai
      (or equivalent validated serving parameters for DGX Spark TP=2)
- [ ] **Container image available** with `DeepseekV41ForCausalLM` support + B12X/SM12x
      kernels for GB10 (check `eugr/spark-vllm-b12x:latest` or build from vLLM ≥ 0.28.0)
- [ ] **Speculative decoding path confirmed** — MTP (`method: mtp`) or community DSpark
      module for V4.1. If neither is available, plan to serve without speculative decoding
      (expect ~40–50% lower throughput)
- [ ] **Both nodes reachable** via SSH from node 1
- [ ] **Sufficient disk space** on both nodes (~200 GiB free for the new checkpoint
      alongside the existing V4 checkpoint)
- [ ] **This runbook reviewed** by a second operator

### Verify current service health (baseline)

```bash
# On node 1 (192.168.100.10)
systemctl --user status deepseek-v4-flash
curl -s localhost:8888/v1/models | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' localhost:8888/health
~/dspark-ds4-0731/status-deepseek-v4-flash-dspark.sh
```

Record the baseline decode throughput:

```bash
~/bench-dspark.py --runs 3 --think off --prompt code
# Expected: ~73–77 tok/s
```

---

## 2. Pre-Swap Preparation (Zero Downtime)

> **The V4 service stays live throughout this phase.** Nothing here causes downtime.

### Step 2.1 — Download the V4.1 checkpoint on both nodes

```bash
# On node 1:
mkdir -p ~/models/deepseek-v4.1-flash-1017-fp8
# Use huggingface-cli or your preferred download method:
huggingface-cli download deepseek-ai/DeepSeek-V4.1-Flash-1017 \
  --local-dir ~/models/deepseek-v4.1-flash-1017-fp8

# Mirror to node 2 over the fabric:
rsync -av --progress ~/models/deepseek-v4.1-flash-1017-fp8/ \
  192.168.100.11:~/models/deepseek-v4.1-flash-1017-fp8/
```

> ⏱️ **Time:** ~2–4 hours depending on network speed. Can run overnight.

### Step 2.2 — Pull/build the V4.1 container image on both nodes

```bash
# On node 1 — pull the image (exact name TBD based on blocker resolution):
docker pull <V41_IMAGE>

# Mirror to node 2:
docker save <V41_IMAGE> | ssh -c aes128-gcm@openssh.com 192.168.100.11 docker load

# Verify image IDs match on both nodes:
docker image inspect --format '{{.Id}}' <V41_IMAGE>
ssh 192.168.100.11 "docker image inspect --format '{{.Id}}' <V41_IMAGE>"
```

### Step 2.3 — Build the HF hub cache on both nodes

```bash
# Adapt the mkcache script for V4.1:
~/dspark-ds41-mkcache.sh
ssh 192.168.100.11 '~/dspark-ds41-mkcache.sh'
```

### Step 2.4 — Clone/prepare the V4.1 recipe checkout on node 1

```bash
# If a community recipe exists (analogous to MiaAI-Lab for V4):
git clone <V41_RECIPE_REPO> ~/dspark-ds41
cd ~/dspark-ds41
git checkout <PINNED_COMMIT>

# Apply any patches from this repo:
cd ~/dspark-ds41
git apply ~/local-ai/dgx-spark/deepseek-v4.1-vllm/patches/0001-*.patch
```

### Step 2.5 — Configure `.env.dspark` for V4.1

```bash
cd ~/dspark-ds41
cp .env.dspark.example .env.dspark
# Apply the deltas from config/env-deltas-v41.md in this repo, or
# copy the prepared config:
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/config/DEPLOYED.env.dspark.v41 .env.dspark
# Review and adjust any TODO markers
```

### Step 2.6 — Install the V4.1 systemd units (disabled)

```bash
# Copy units but do NOT enable or start them:
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/systemd/deepseek-v4.1-flash.service \
  ~/.config/systemd/user/
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/systemd/deepseek-v4.1-flash-watchdog.service \
  ~/.config/systemd/user/
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/systemd/deepseek-v4.1-flash-watchdog.timer \
  ~/.config/systemd/user/

# Install wrapper scripts:
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/scripts/serve-dspark-ds41.sh ~/serve-dspark-ds41.sh
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/scripts/dspark-wait-cluster-v41.sh ~/dspark-wait-cluster-v41.sh
cp ~/local-ai/dgx-spark/deepseek-v4.1-vllm/scripts/deepseek-v4.1-flash-watchdog.sh ~/deepseek-v4.1-flash-watchdog.sh
chmod +x ~/serve-dspark-ds41.sh ~/dspark-wait-cluster-v41.sh ~/deepseek-v4.1-flash-watchdog.sh

# Reload systemd (does not affect running V4 service):
systemctl --user daemon-reload
```

### Step 2.7 — Dry-run: test V4.1 startup without stopping V4

> **⚠️ This requires a temporary port change.** V4 is on :8888; test V4.1 on :8889.

1. Temporarily set `VLLM_PORT=8889` in the V4.1 `.env.dspark`
2. Attempt a manual start:
   ```bash
   ~/serve-dspark-ds41.sh
   ```
3. Validate on the test port:
   ```bash
   curl -s localhost:8889/v1/models | python3 -m json.tool
   curl -s localhost:8889/v1/chat/completions -H 'Content-Type: application/json' -d '{
     "model":"deepseek-v4.1-flash-1017",
     "messages":[{"role":"user","content":"Say hello in one sentence."}],
     "max_tokens":50}'
   ```
4. Tear down the test instance:
   ```bash
   ~/dspark-ds41/stop-deepseek-v4.1-flash-dspark.sh
   ```
5. Reset `VLLM_PORT=8888` in the V4.1 `.env.dspark`

> **If the dry-run fails:** STOP here. Do not proceed to the swap. Debug the V4.1
> image/recipe and iterate until the dry-run succeeds. V4 remains live throughout.

---

## 3. Validation Gate

**Do not proceed past this gate unless ALL of the following are true:**

- [ ] V4 service is currently healthy (recorded baseline in §1)
- [ ] V4.1 checkpoint downloaded on **both** nodes
- [ ] V4.1 container image present on **both** nodes with matching IDs
- [ ] V4.1 HF hub cache built on **both** nodes
- [ ] V4.1 `.env.dspark` configured and reviewed
- [ ] V4.1 systemd units installed (disabled)
- [ ] **V4.1 dry-run succeeded** on :8889 (§2.7) — model loaded, inference responded
- [ ] Rollback procedure (§6) reviewed and understood
- [ ] A second operator has reviewed this checklist

---

## 4. The Swap (Maintenance Window)

> **This is the downtime window.** Expected: 10–20 minutes from V4 stop to V4.1 API up.

### Step 4.1 — Stop the V4 watchdog

```bash
systemctl --user stop deepseek-v4-flash-watchdog.timer
systemctl --user stop deepseek-v4-flash-watchdog.service
```

### Step 4.2 — Stop the V4 service

```bash
systemctl --user stop deepseek-v4-flash
```

Verify both ranks are down:

```bash
docker ps | grep deepseek   # should show nothing
ssh 192.168.100.11 'docker ps | grep deepseek'   # should show nothing
```

### Step 4.3 — Disable V4 systemd units (preserve, don't delete)

```bash
systemctl --user disable deepseek-v4-flash
systemctl --user disable deepseek-v4-flash-watchdog.timer
```

> **Do NOT remove the V4 unit files or scripts.** They are the rollback path.

### Step 4.4 — Enable and start the V4.1 service

```bash
systemctl --user enable deepseek-v4.1-flash
systemctl --user start deepseek-v4.1-flash
```

### Step 4.5 — Monitor startup

```bash
# Watch the journal:
journalctl --user -u deepseek-v4.1-flash -f

# Expected timeline (similar to V4):
# ~3 min weight load
# ~1 min compile/profile
# ~2 min FlashInfer autotune (or Triton JIT if different kernels)
# ~20s CUDA graph capture
# Total: ~6–10 min
```

### Step 4.6 — Enable the V4.1 watchdog

```bash
systemctl --user enable --now deepseek-v4.1-flash-watchdog.timer
```

---

## 5. Post-Swap Validation

### Step 5.1 — Basic health checks

```bash
# Unit status:
systemctl --user status deepseek-v4.1-flash

# API model list:
curl -s localhost:8888/v1/models | python3 -m json.tool
# Expect: deepseek-v4.1-flash-1017 (or whatever SERVED_MODEL_NAME is set to)

# Health endpoint:
curl -s -o /dev/null -w '%{http_code}\n' localhost:8888/health
# Expect: 200
```

### Step 5.2 — Inference smoke test

```bash
# Non-thinking mode:
curl -s localhost:8888/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model":"deepseek-v4.1-flash-1017",
  "messages":[{"role":"user","content":"Write a haiku about two computers sharing memory."}],
  "max_tokens":200,
  "chat_template_kwargs":{"thinking_mode":"chat"}}' | python3 -m json.tool

# Thinking mode (V4.1 uses thinking_mode, not reasoning_effort directly):
curl -s localhost:8888/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model":"deepseek-v4.1-flash-1017",
  "messages":[{"role":"user","content":"What is 17 * 19? Show your work."}],
  "max_tokens":500,
  "chat_template_kwargs":{"thinking_mode":"thinking","reasoning_effort":"high"}}' | python3 -m json.tool

# Tool calling (V4.1 has native DSML tool calling):
curl -s localhost:8888/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model":"deepseek-v4.1-flash-1017",
  "messages":[{"role":"user","content":"What is the weather in Tokyo?"}],
  "tools":[{"type":"function","function":{"name":"get_weather","description":"Get weather for a city","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],
  "max_tokens":200}' | python3 -m json.tool
```

### Step 5.3 — Performance baseline

```bash
# Run the benchmark and compare to V4 baseline (~73–77 tok/s code, ~35 tok/s prose):
~/bench-dspark.py --runs 3 --think off --prompt code
# Record results and compare to §8 of the V4 runbook
```

> **Note:** If V4.1 does not support DSpark speculative decoding, throughput will be
> significantly lower than V4's ~75 tok/s. MTP may partially recover this. Without any
> speculative decoding, expect ~40–50 tok/s on code.

### Step 5.4 — Confirm TP traffic is on RDMA

```bash
C=/sys/class/infiniband/rocep1s0f1/ports/1/counters
N=/sys/class/net/enp1s0f1np1/statistics
R1=$(cat $C/port_xmit_data); T1=$(cat $N/tx_bytes)
# Run a request here
R2=$(cat $C/port_xmit_data); T2=$(cat $N/tx_bytes)
echo "RDMA $(( (R2-R1)*4/1048576 )) MiB, TCP $(( (T2-T1)/1048576 )) MiB"
# Expect: RDMA >> 0, TCP ≈ 0
```

### Step 5.5 — Watchdog validation

```bash
# Confirm watchdog timer is active:
systemctl --user list-timers deepseek-v4.1-flash-watchdog.timer

# Check watchdog state file:
cat ~/deepseek-v4.1-flash-watchdog-state.json

# Wait 2–3 minutes, then confirm no failures:
journalctl --user -u deepseek-v4.1-flash-watchdog --since "5 min ago"
```

### Step 5.6 — Notify clients

Update any downstream clients/harnesses that:
- The model name changed (if `SERVED_MODEL_NAME` differs)
- Reasoning effort format may differ (V4.1 accepts int 1–100 or low/medium/high/max)
- Vision endpoints are now available (if enabled)
- The chat template is now Jinja-based (built-in, no `encoding/` dependency)

---

## 6. Rollback Procedure

> **If anything goes wrong during or after the swap, roll back immediately.**
> The V4 service is preserved and can be restored in ~6–10 minutes.

### Emergency rollback (< 2 minutes to dispatch)

```bash
# 1. Stop V4.1:
systemctl --user stop deepseek-v4.1-flash-watchdog.timer
systemctl --user stop deepseek-v4.1-flash

# 2. Disable V4.1 (keep files in place for debugging):
systemctl --user disable deepseek-v4.1-flash
systemctl --user disable deepseek-v4.1-flash-watchdog.timer

# 3. Re-enable and start V4:
systemctl --user enable deepseek-v4-flash
systemctl --user start deepseek-v4-flash

# 4. Re-enable the V4 watchdog:
systemctl --user enable --now deepseek-v4-flash-watchdog.timer
```

### Rollback validation

```bash
# Wait ~6–10 min for V4 to come back up, then:
systemctl --user status deepseek-v4-flash
curl -s localhost:8888/v1/models | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' localhost:8888/health
~/bench-dspark.py --runs 1 --think off --prompt code
# Expect: model is deepseek-v4-flash-0731, ~73–77 tok/s
```

### Post-rollback

- Do NOT delete V4.1 files — they are needed to debug what went wrong
- Check V4.1 logs: `journalctl --user -u deepseek-v4.1-flash --no-pager`
- Check V4.1 container logs: `docker logs deepseek-v4.1-flash-vllm-dspark-1`
- File a checklist of what failed and update the blocker table in README.md

---

## 7. Post-Swap Cleanup

> **Only after V4.1 has been stable for ≥ 24 hours.**

### Step 7.1 — Remove V4 systemd units

```bash
systemctl --user disable deepseek-v4-flash
systemctl --user disable deepseek-v4-flash-watchdog.timer
rm ~/.config/systemd/user/deepseek-v4-flash.service
rm ~/.config/systemd/user/deepseek-v4-flash-watchdog.service
rm ~/.config/systemd/user/deepseek-v4-flash-watchdog.timer
rm ~/serve-dspark-ds4.sh ~/dspark-wait-cluster.sh ~/deepseek-v4-flash-watchdog.sh
systemctl --user daemon-reload
```

### Step 7.2 — Archive V4 checkpoint (optional)

```bash
# The V4 checkpoint is ~155 GiB per node. If disk pressure is a concern:
# Archive to external storage before deleting:
tar -cf - ~/models/deepseek-v4-flash-0731-fp8 | zstd -T0 > /mnt/backup/ds4-0731-fp8.tar.zst

# Remove the HF hub cache symlinks:
rm -rf ~/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4-Flash-0731

# Remove the recipe checkout:
rm -rf ~/dspark-ds4-0731

# Remove the model files last:
rm -rf ~/models/deepseek-v4-flash-0731-fp8
```

### Step 7.3 — Remove the V4 container image (optional)

```bash
docker rmi ghcr.io/anemll/dspark-vllm-gx10:0.1.1
ssh 192.168.100.11 'docker rmi ghcr.io/anemll/dspark-vllm-gx10:0.1.1'
```

---

## 8. Known Risks and Mitigations

### 8.1 — Throughput regression without DSpark

**Risk:** V4 currently achieves ~75 tok/s with DSpark k=5 speculative decoding.
V4.1 may not have a DSpark module, and MTP alone may yield lower acceptance rates.

**Mitigation:**
- Benchmark V4.1 with MTP during the dry-run (§2.7) before committing to the swap
- If throughput is unacceptable, delay the swap until a community DSpark module emerges
- Consider serving V4 and V4.1 in parallel on different ports during a transition period

### 8.2 — Client breakage from tokenizer/template change

**Risk:** V4's `encoding/`-based chat template differs from V4.1's built-in Jinja template.
Clients that relied on specific tokenization behavior may see different outputs.

**Mitigation:**
- Test all downstream harnesses (pi, hermes, openclaw, etc.) during the dry-run
- The `--tokenizer-mode deepseek_v41` flag is required; verify it is in the serve command
- V4.1's reasoning effort uses budget integers (1–100); verify client code handles this

### 8.3 — Memory pressure from dual checkpoints

**Risk:** Both V4 (~155 GiB) and V4.1 (~TBD GiB) checkpoints on disk simultaneously
during the transition. Each node has ~121 GiB unified memory but disk may be constrained.

**Mitigation:**
- Verify disk space before starting: `df -h ~/models/`
- The checkpoints are loaded into GPU/unified memory one at a time (not simultaneously)
- Only one service runs at a time during the swap

### 8.4 — Watchdog false restart during V4.1 startup

**Risk:** The V4 watchdog may restart V4 if it is still probing during the swap window.

**Mitigation:**
- Stop the V4 watchdog **before** stopping the V4 service (§4.1)
- The V4.1 watchdog is not enabled until V4.1 is confirmed healthy (§4.6)

### 8.5 — NCCL / RoCE fabric issues

**Risk:** The V4 service has known NCCL memory-region ceiling issues on node 2
(`NCCL_MAX_NCHANNELS=8`). V4.1 may have different NCCL communicator patterns.

**Mitigation:**
- Keep `NCCL_MAX_NCHANNELS=8` in the V4.1 `.env.dspark` until node 2's kernel is fixed
- Monitor NCCL init logs during V4.1 startup
- The `nccl-repro.sh` script can be adapted for V4.1 to validate before the swap

### 8.6 — Vision weights not yet downloaded

**Risk:** V4.1 is vision-capable but the vision encoder weights may be a separate
download. Serving without them would disable vision but should not crash text serving.

**Mitigation:**
- Start with text-only serving; add vision later as a non-disruptive update
- Set `PREPARE_VL_SIDECAR_MODEL=0` equivalent for V4.1 if the recipe supports it

---

## Appendix A: Quick Reference — Command Cheatsheet

```bash
# === PRE-SWAP (no downtime) ===
# Download checkpoint
huggingface-cli download deepseek-ai/DeepSeek-V4.1-Flash-1017 --local-dir ~/models/deepseek-v4.1-flash-1017-fp8
rsync -av ~/models/deepseek-v4.1-flash-1017-fp8/ 192.168.100.11:~/models/deepseek-v4.1-flash-1017-fp8/

# Build HF cache
~/dspark-ds41-mkcache.sh
ssh 192.168.100.11 '~/dspark-ds41-mkcache.sh'

# Install units (disabled)
systemctl --user daemon-reload

# Dry-run on :8889
VLLM_PORT=8889 ~/serve-dspark-ds41.sh
curl -s localhost:8889/v1/models
~/dspark-ds41/stop-deepseek-v4.1-flash-dspark.sh

# === SWAP (downtime) ===
systemctl --user stop deepseek-v4-flash-watchdog.timer
systemctl --user stop deepseek-v4-flash
systemctl --user disable deepseek-v4-flash
systemctl --user disable deepseek-v4-flash-watchdog.timer
systemctl --user enable deepseek-v4.1-flash
systemctl --user start deepseek-v4.1-flash
systemctl --user enable --now deepseek-v4.1-flash-watchdog.timer

# === VALIDATE ===
curl -s localhost:8888/v1/models | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' localhost:8888/health
~/bench-dspark.py --runs 3 --think off --prompt code

# === ROLLBACK ===
systemctl --user stop deepseek-v4.1-flash-watchdog.timer
systemctl --user stop deepseek-v4.1-flash
systemctl --user disable deepseek-v4.1-flash
systemctl --user disable deepseek-v4.1-flash-watchdog.timer
systemctl --user enable deepseek-v4-flash
systemctl --user start deepseek-v4-flash
systemctl --user enable --now deepseek-v4-flash-watchdog.timer
```

## Appendix B: V4 ↔ V4.1 API Differences for Clients

| Feature | V4 | V4.1 |
|---------|-----|------|
| Model name | `deepseek-v4-flash-0731` | `deepseek-v4.1-flash-1017` |
| Reasoning control | `chat_template_kwargs: {"reasoning_effort": "low"}` | `chat_template_kwargs: {"thinking_mode": "thinking", "reasoning_effort": "high"}` or `{"thinking_mode": "chat"}` for no-think |
| Reasoning effort values | `low`, `high`, `max` | `low`, `medium`, `high`, `max` or integer 1–100 |
| Vision | Not supported | Supported via `image` content blocks |
| Tool calling | Supported (DSML) | Supported (DSML, same format) |
| Chat template | Custom encoding (no Jinja) | Built-in Jinja (standard OpenAI compat) |
| `enable_thinking` | Not a parameter | Alias for `thinking_mode: "thinking"` |
