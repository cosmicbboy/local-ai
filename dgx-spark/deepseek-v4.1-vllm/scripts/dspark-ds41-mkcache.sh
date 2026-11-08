#!/usr/bin/env bash
# Build an HF hub cache entry for DeepSeek-V4.1-Flash @ pinned rev, hardlinked from ~/models.
# NOTE: Revision is a placeholder. Pin to a specific commit after downloading.
set -euo pipefail
# TODO: Pin to a specific revision after downloading and verifying the checkpoint
# REV= (will be set after huggingface-cli download)
REV=main
SRC=$HOME/models/deepseek-v4.1-flash-1017-fp8
REPO=$HOME/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash-1017
SNAP=$REPO/snapshots/$REV
mkdir -p "$SNAP" "$REPO/refs"
echo -n "$REV" > "$REPO/refs/main"
for f in "$SRC"/*; do
  b=$(basename "$f"); [ -e "$SNAP/$b" ] || ln "$f" "$SNAP/$b"
done
# V4.1 has a built-in Jinja chat template, so we don't need the encoding/ folder like V4.
# However, we still fetch small files (README, config, etc.) for completeness.
for p in .gitattributes README.md config.json generation_config.json; do
  [ -s "$SNAP/$p" ] || curl -fsSL "https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/resolve/$REV/$p" -o "$SNAP/$p" || true
done
echo "$(hostname): $(find "$SNAP" -type f | wc -l) files, $(du -shL "$SNAP" | cut -f1)"
