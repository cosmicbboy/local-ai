#!/usr/bin/env bash
# Build an HF hub cache entry for DeepSeek-V4-Flash-0731 @ pinned rev, hardlinked from ~/models.
set -euo pipefail
REV=9e165c30e2704aec5d9d593cce3eebd58bbef1cb
SRC=$HOME/models/deepseek-v4-flash-0731-fp8
REPO=$HOME/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4-Flash-0731
SNAP=$REPO/snapshots/$REV
mkdir -p "$SNAP" "$REPO/refs"
echo -n "$REV" > "$REPO/refs/main"
for f in "$SRC"/*; do
  b=$(basename "$f"); [ -e "$SNAP/$b" ] || ln "$f" "$SNAP/$b"
done
for p in .gitattributes README.md encoding/README.md encoding/encoding_dsv4.py encoding/test_encoding_dsv4.py \
  encoding/tests/test_input_1.json encoding/tests/test_input_2.json encoding/tests/test_input_3.json encoding/tests/test_input_4.json \
  encoding/tests/test_output_1.txt encoding/tests/test_output_2.txt encoding/tests/test_output_3.txt encoding/tests/test_output_4.txt \
  inference/README.md inference/config.json inference/convert.py inference/generate.py inference/kernel.py inference/model.py inference/requirements.txt; do
  mkdir -p "$SNAP/$(dirname "$p")"
  [ -s "$SNAP/$p" ] || curl -fsSL "https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731/resolve/$REV/$p" -o "$SNAP/$p"
done
echo "$(hostname): $(find "$SNAP" -type f | wc -l) files, $(du -shL "$SNAP" | cut -f1)"
