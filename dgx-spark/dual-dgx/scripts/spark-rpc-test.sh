#!/usr/bin/env bash
# Cross-node LLM serving test for two DGX Sparks via llama.cpp RPC.
# No sudo required. Uses the CX-7 fabric (TCP, not RDMA).
set -euo pipefail

NODE2=192.168.100.11
RPC_PORT=50052
LLAMA=/home/nielsbantilan/llama.cpp/build
MODEL=/home/nielsbantilan/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/c8b5954a88c2775c546b92593eda40ea041d3176/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf
REMOTE_DIR=/home/nielsbantilan/llama-rpc
LOG=/home/nielsbantilan/.claude/jobs/df003680/tmp

mem() { # $1 = host label, $2 = ssh target or "local"
  if [ "$2" = "local" ]; then free -g | awk '/Mem:/{print $3}'
  else ssh -o BatchMode=yes "$2" "free -g | awk '/Mem:/{print \$3}'"; fi
}

echo "=== Baseline memory (GiB used) ==="
B1=$(mem node1 local); B2=$(mem node2 $NODE2)
echo "node1 spark-a7e9: ${B1}   node2 spark-17d7: ${B2}"

echo "=== Shipping RPC binaries to node 2 ==="
ssh -o BatchMode=yes $NODE2 "mkdir -p $REMOTE_DIR"
rsync -a "$LLAMA/bin/rpc-server" $LLAMA/bin/*.so "$NODE2:$REMOTE_DIR/" 2>/dev/null || \
  rsync -a "$LLAMA/bin/rpc-server" "$NODE2:$REMOTE_DIR/"
find "$LLAMA" -name 'libggml*.so' -o -name 'libllama*.so' -o -name 'libmtmd*.so' 2>/dev/null \
  | xargs -r -I{} rsync -a {} "$NODE2:$REMOTE_DIR/"

echo "=== Starting rpc-server on node 2 ==="
# NOTE: never put `pkill -f rpc-server` in the same ssh command as the launch --
# pkill -f matches the ssh wrapper's own cmdline and kills the session.
cat > "$LOG/start_rpc.sh" <<'EOF'
#!/usr/bin/env bash
cd /home/nielsbantilan/llama-rpc
export LD_LIBRARY_PATH=/home/nielsbantilan/llama-rpc:/usr/local/cuda/lib64:$LD_LIBRARY_PATH
exec ./rpc-server -H 0.0.0.0 -p 50052
EOF
rsync -a "$LOG/start_rpc.sh" "$NODE2:$REMOTE_DIR/start_rpc.sh"
ssh -o BatchMode=yes $NODE2 "chmod +x $REMOTE_DIR/start_rpc.sh; setsid nohup $REMOTE_DIR/start_rpc.sh > $REMOTE_DIR/rpc.log 2>&1 < /dev/null & echo started"
sleep 3
ssh -o BatchMode=yes $NODE2 "tail -5 $REMOTE_DIR/rpc.log"

echo "=== Starting llama-server on node 1, splitting across local GPU + node 2 ==="
export LD_LIBRARY_PATH=$LLAMA/bin:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}
setsid nohup "$LLAMA/bin/llama-server" \
  -m "$MODEL" \
  --rpc ${NODE2}:${RPC_PORT} \
  -ngl 999 \
  --host 0.0.0.0 --port 8080 \
  -c 4096 \
  > "$LOG/llama-server.log" 2>&1 < /dev/null &
echo "llama-server pid $!"
