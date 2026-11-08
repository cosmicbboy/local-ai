# Code Review: DeepSeek V4.1 Migration Preparation

**Reviewer:** AI Assistant  
**Date:** 2026-11-06  
**Branch:** `dgx-spark/deepseek-v4.1-prep`  
**PR:** #7

---

## Executive Summary

This PR prepares the infrastructure to migrate from DeepSeek-V4-Flash-0731 to DeepSeek-V4.1-Flash-1017 on the 2× DGX Spark cluster. **No services are changed** — this is purely preparation work. The migration is blocked by three issues (no vLLM recipe, no DSpark/GB10 image, unconfirmed DSpark support) that must be resolved before the actual cutover.

**Overall Assessment:** ✅ **Ready to merge** (with minor clarifications noted below)

---

## File-by-File Review

### 1. `README.md` — Overview and Blocker Tracking

**Strengths:**
- Clear status indicator at the top (PREPARED — NOT YET DEPLOYABLE)
- Excellent blocker table with visual status indicators (🔴/🟡/🟢)
- Comprehensive V4 vs V4.1 comparison table covering architecture, capabilities, and tooling
- File manifest makes navigation easy
- Upstream references section provides context

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Excellent

---

### 2. `SWAP-RUNBOOK.md` — Cutover Procedure

**Strengths:**
- Well-structured with clear table of contents
- Prerequisites section includes a checklist
- Pre-swap preparation is clearly marked as "Zero Downtime"
- Validation gate with explicit checkbox list prevents premature cutover
- The swap section has realistic downtime estimate (10-20 min)
- Rollback procedure is prominently featured and includes emergency steps
- Post-swap cleanup is marked as "only after 24h stability"
- Known risks section covers 8 different failure modes with mitigations
- Appendix A (command cheatsheet) is practical and copy-paste friendly
- Appendix B (API differences) helps client developers prepare

**Minor Issues:**

1. **Step 2.7 (Dry-run):** Mentions testing on :8889 while V4 runs on :8888, but doesn't explicitly warn that both services will use the same RoCE fabric and NCCL resources simultaneously. However, this should be fine since they're different Docker containers with different ports.

2. **Step 5.3 (Performance baseline):** References `~/bench-dspark.py` which is from the V4 setup. Should clarify whether this script works with V4.1 or if a V4.1-specific benchmark is needed.

3. **Step 1 (Prerequisites):** References `~/dspark-ds4-0731/status-deepseek-v4-flash-dspark.sh` for V4 baseline. V4.1 will have its own status script from the recipe — should mention this.

**Rating:** ⭐⭐⭐⭐⭐ Excellent (minor clarifications would help)

---

### 3. `systemd/deepseek-v4.1-flash.service`

**Strengths:**
- Mirrors V4 service structure exactly
- Type=oneshot with RemainAfterExit=yes (correct for this use case)
- ExecStartPre ordering is correct (wait-cluster, then cold stop)
- SuccessExitStatus=3 handles "already running" case
- TimeoutStartSec=90min is generous but appropriate
- Comment explicitly notes "NOT enabled by default"

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 4. `systemd/deepseek-v4.1-flash-watchdog.service`

**Strengths:**
- After=deepseek-v4.1-flash.service ensures proper ordering
- Type=oneshot is correct for periodic checks
- TimeoutStartSec=5min is appropriate

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 5. `systemd/deepseek-v4.1-flash-watchdog.timer`

**Strengths:**
- OnBootSec=3min and OnStartupSec=3min give the service time to start
- OnUnitActiveSec=60s matches V4 watchdog interval
- Unit= points to correct service file
- Persistent=false is correct (don't replay missed ticks)

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 6. `scripts/serve-dspark-ds41.sh`

**Strengths:**
- set -euo pipefail for safety
- NODES array makes it easy to add/remove nodes
- TODO comment clearly marks the image blocker
- IMG uses ${DSPARK_VLLM_IMAGE:-default} for flexibility
- sidecar_up/sidecar_down functions are well-structured
- trap sidecar_down EXIT ensures cleanup
- Kills ggml-rpc-server on node 2 to avoid memory conflicts
- WAIT_ATTEMPTS is configurable

**Minor Issues:**
- Calls `./start-deepseek-v4.1-flash-dspark.sh` which doesn't exist yet (will come from recipe). This is fine but could be clearer in comments.

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 7. `scripts/deepseek-v4.1-flash-watchdog.sh`

**Strengths:**
- All constants are configurable via environment variables
- MODEL and UNIT are correctly set to V4.1 values
- STATE and LOCK file paths are unique (no conflicts with V4 watchdog)
- Probe functions (liveness, generation) are well-implemented
- State management with jq is robust
- Restart bookkeeping prevents restart loops
- All phases (ok, degraded, restarting, givenup, standby) are handled
- GIVING UP log correctly references V4.1 container name

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 8. `scripts/dspark-wait-cluster-v41.sh`

**Strengths:**
- set -uo pipefail (note: no -e, which is intentional for the polling loop)
- NODE2, IFACE, HCA are correct
- TODO comment marks the image blocker
- IMG uses ${DSPARK_VLLM_IMAGE:-default}
- local_ready and remote_ready functions are comprehensive
- Timeout logic is clear
- Sleep 15 at the end allows RoCE GIDs to populate

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 9. `scripts/dspark-ds41-mkcache.sh`

**Strengths:**
- set -euo pipefail
- REV=main with TODO to pin (appropriate for draft)
- SRC and REPO paths are correct for V4.1
- Comment explains that V4.1 has built-in Jinja (no encoding/ folder needed)
- Fetches small files (README, config, generation_config)
- Output shows file count and size

**Minor Issues:**
- Uses `REV=main` which could change. The TODO to pin is good, but the script should probably fail if REV is not pinned in production. However, for a draft this is fine.

**Rating:** ⭐⭐⭐⭐⭐ Correct (for draft status)

---

### 10. `config/DEPLOYED.env.dspark.v41`

**Strengths:**
- Header clearly states "STATUS: DRAFT — NOT YET VALIDATED"
- Lists all three blockers
- All cluster settings are correct
- RoCE/IB settings match V4 (appropriate since hardware is the same)
- Cache settings are correct
- Model settings have TODO to pin revision
- Container image has TODO with options listed
- Serving profile matches V4 (appropriate starting point)
- GPU memory utilization is conservative (0.80)
- Speculative decoding section has TODO with MTP fallback
- DEFAULT_THINKING=high (V4.1 default, can be overridden)
- Vision flags are present but disabled
- All vLLM/runtime knobs are present
- NCCL settings include MAX_NCHANNELS=8 (critical for node 2)

**Minor Issues:**
- `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPH=0` — this is correct but the name is slightly different from V4. Let me check... Actually, looking at the V4 config, it's also `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPH=0`. So this is consistent.

**Rating:** ⭐⭐⭐⭐⭐ Correct

---

### 11. `config/env-deltas-v41.md`

**Strengths:**
- STATUS: DRAFT header is clear
- Anticipated deltas table shows exactly what will change from V4
- Architecture-specific changes section explains the implications
- Merge procedure is practical

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Excellent

---

### 12. `patches/README.md`

**Strengths:**
- STATUS: DRAFT header is clear
- Expected patches section explains what will be needed
- Applying patches instructions are practical
- Mentions the validator script

**Minor Issues:**
- None identified

**Rating:** ⭐⭐⭐⭐⭐ Excellent

---

## Cross-Cutting Concerns

### Consistency
- ✅ All file paths use `/home/nielsbantilan/` prefix consistently
- ✅ All scripts have proper shebang (`#!/usr/bin/env bash`)
- ✅ All scripts are executable (chmod +x verified)
- ✅ All systemd units follow the same pattern as V4
- ✅ All TODOs are clearly marked and reference specific blockers

### Safety
- ✅ No services are enabled or started
- ✅ Rollback procedure is prominent and well-documented
- ✅ Validation gate prevents premature cutover
- ✅ Dry-run on :8889 allows testing without affecting V4
- ✅ Watchdog has give-up logic to prevent restart loops

### Documentation
- ✅ Every file has a clear purpose stated in comments or README
- ✅ Blockers are tracked in multiple places (README, env file, scripts)
- ✅ Upstream references are provided for context
- ✅ API differences table helps client developers

### Testing
- ⚠️ Cannot be tested until blockers are resolved (by design)
- ✅ Dry-run procedure is documented
- ✅ Validation checklist is comprehensive

---

## Potential Issues to Address

### 1. Benchmark Script Compatibility

**Issue:** The runbook references `~/bench-dspark.py` for performance baseline, but this script is from the V4 setup. V4.1 might need different parameters or a different script.

**Recommendation:** Add a note in SWAP-RUNBOOK.md Step 5.3:
```markdown
> **Note:** `~/bench-dspark.py` is from the V4 setup. If the V4.1 recipe ships its own
> benchmark script, use that instead. Otherwise, verify that `bench-dspark.py` works
> with the V4.1 model name and tokenizer.
```

### 2. Status Script Reference

**Issue:** The prerequisites section references `~/dspark-ds4-0731/status-deepseek-v4-flash-dspark.sh` for V4 baseline. V4.1 will have its own status script from the recipe.

**Recommendation:** Add a note in SWAP-RUNBOOK.md Step 1:
```markdown
> **Note:** V4.1 will have its own status script (e.g., `status-deepseek-v4.1-flash-dspark.sh`)
> from the recipe. Use it for V4.1 validation after the swap.
```

### 3. Dry-Run Resource Contention

**Issue:** Step 2.7 (dry-run) tests V4.1 on :8889 while V4 runs on :8888. Both services will use the same RoCE fabric and NCCL resources simultaneously. This should be fine, but it's not explicitly mentioned.

**Recommendation:** Add a note in SWAP-RUNBOOK.md Step 2.7:
```markdown
> **Note:** The dry-run uses the same RoCE fabric and NCCL resources as the live V4 service.
> This is safe because they're different Docker containers with different ports, but monitor
> V4's performance during the dry-run to ensure no interference.
```

### 4. Rollback Assumes V4 Files Are Present

**Issue:** The rollback procedure assumes that V4 systemd units, scripts, and recipe checkout are still present. This is implied but not explicit.

**Recommendation:** Add a note in SWAP-RUNBOOK.md Step 6:
```markdown
> **Note:** This rollback procedure assumes that V4 systemd units, scripts, and the
> `~/dspark-ds4-0731/` recipe checkout are still present. Do NOT delete them until V4.1
> has been stable for ≥ 24 hours (see §7).
```

---

## Comparison with V4 Setup

| Aspect | V4 | V4.1 (Draft) | Notes |
|--------|-----|--------------|-------|
| Service name | `deepseek-v4-flash.service` | `deepseek-v4.1-flash.service` | ✅ Correct |
| Model | `DeepSeek-V4-Flash-0731` | `DeepSeek-V4.1-Flash-1017` | ✅ Correct |
| Architecture | `DeepseekV4ForCausalLM` | `DeepseekV41ForCausalLM` | ✅ Correct |
| Tokenizer | `deepseek_v4` | `deepseek_v41` | ✅ Correct |
| Image | `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` | TBD (blocker) | ✅ Documented |
| Spec decoding | DSpark k=5 | MTP or DSpark (TBD) | ✅ Documented |
| Chat template | Custom encoding/ | Built-in Jinja | ✅ Correct |
| Vision | No | Yes (optional) | ✅ Correct |
| NCCL workaround | `NCCL_MAX_NCHANNELS=8` | `NCCL_MAX_NCHANNELS=8` | ✅ Preserved |
| Watchdog state file | `~/deepseek-v4-flash-watchdog-state.json` | `~/deepseek-v4.1-flash-watchdog-state.json` | ✅ Unique |
| Watchdog lock file | `~/.deepseek-v4-flash-watchdog.lock` | `~/.deepseek-v4.1-flash-watchdog.lock` | ✅ Unique |

All differences are intentional and well-documented.

---

## Final Verdict

### ✅ **Approve and Merge**

This PR is well-structured, comprehensive, and safe. The blocker tracking is excellent, the runbook is thorough, and the rollback procedure is clear. The minor issues identified are clarifications that would help but don't block the merge.

**Recommendation:** Merge this PR as-is, then address the minor clarifications in a follow-up commit if desired.

### What Happens Next

1. **Wait for blockers to resolve:**
   - Monitor https://recipes.vllm.ai for V4.1 recipe
   - Check `eugr/spark-vllm-b12x:latest` or build custom image
   - Confirm DSpark or MTP support for V4.1

2. **Follow the runbook:**
   - Download checkpoint on both nodes
   - Build HF cache
   - Dry-run on :8889
   - Pass validation gate
   - Execute the swap
   - Monitor for 24h
   - Clean up V4 files

3. **Update clients:**
   - Notify downstream harnesses of model name change
   - Update reasoning effort format (if needed)
   - Test vision endpoints (if enabled)

---

## Appendix: Review Methodology

This review examined:
- All 12 new files in `dgx-spark/deepseek-v4.1-vllm/`
- Cross-referenced with V4 setup in `dgx-spark/deepseek-v4-vllm/`
- Checked for consistency, safety, and completeness
- Identified potential issues and provided recommendations
- Compared V4 vs V4.1 configurations side-by-side

The review is thorough but cannot test the actual migration (by design, since blockers exist).
