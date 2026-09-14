#!/usr/bin/env bash
# Serve DeepSeek-V4-Flash-0731 across both DGX Sparks via llama.cpp RPC + DSpark spec decoding.
set -euo pipefail
M=/home/nielsbantilan/models/deepseek-v4-flash-0731
LLAMA=/home/nielsbantilan/llama.cpp/build/bin
export LD_LIBRARY_PATH=$LLAMA:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}

# node 2 RPC server must be running:
#   ssh 192.168.100.11 'setsid nohup ~/llama-rpc/start_rpc.sh > ~/llama-rpc/rpc.log 2>&1 < /dev/null &'

exec "$LLAMA/llama-server" \
  -m "$M/DeepSeek-V4-Flash-0731-UD-Q4_K_XL-00001-of-00005.gguf" \
  -md "$M/dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf" \
  --spec-type draft-dspark \
  --spec-draft-n-max 3 \
  --rpc 192.168.100.11:50052 \
  -ngl 999 -ngld 999 \
  -c 32768 \
  --temp 1.0 --top-p 1.0 --min-p 0.01 \
  --alias deepseek-v4-flash \
  --host 0.0.0.0 --port 8080
