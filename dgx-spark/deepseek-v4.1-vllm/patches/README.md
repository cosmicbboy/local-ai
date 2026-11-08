# Patches for DeepSeek-V4.1-Flash recipe

> **STATUS: DRAFT — patches will be created once the V4.1 recipe is available**

This directory will hold patches to apply to the V4.1 recipe checkout
(`~/dspark-ds41/`) before serving.

## Expected patches

### 0001-nccl-nchannels-passthrough.patch

Same as V4: the compose `environment:` map is an explicit allowlist and silently drops
unknown keys. This patch adds `NCCL_MAX_NCHANNELS` to the allowlist so the node-2
kernel-drift workaround (§7.5 of the V4 runbook) takes effect.

**Status:** Will be created once the V4.1 recipe's `docker-compose.dspark.yml` is available.

### Additional patches (TBD)

Depending on the V4.1 recipe and image, additional patches may be needed for:

- V4.1-specific hotfixes (analogous to V4's #22, #27, #43, etc.)
- Vision encoder integration (if served with vision enabled)
- DSpark/MTP speculative decoding configuration

## Applying patches

```bash
cd ~/dspark-ds41
git apply ~/local-ai/dgx-spark/deepseek-v4.1-vllm/patches/0001-*.patch
```

Verify with the recipe's validator (if available):
```bash
./validate-dspark-config.sh
```
