#!/usr/bin/env bash
# Measure decode throughput of the DS4 endpoint.  Usage: ./bench-ds4.sh [port] [think:on|off]
PORT="${1:-8001}"
THINK="${2:-off}"
[ "$THINK" = "on" ] && TK='{}' || TK='{"enable_thinking":false}'

read -r -d '' BODY <<JSON
{"model":"deepseek-v4-flash",
 "messages":[{"role":"user","content":"Write a complete Python implementation of a LRU cache with unit tests."}],
 "max_tokens":512,"temperature":0.6,"chat_template_kwargs":$TK}
JSON

START=$(date +%s.%N)
RESP=$(curl -s "http://localhost:$PORT/v1/chat/completions" -H 'Content-Type: application/json' -d "$BODY")
END=$(date +%s.%N)

echo "$RESP" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if 'error' in d: print('ERROR:', d['error']); sys.exit(1)
u=d.get('usage',{})
el=float('$END')-float('$START')
ct=u.get('completion_tokens',0)
print(f\"prompt tokens : {u.get('prompt_tokens',0)}\")
print(f\"output tokens : {ct}\")
print(f\"wall time     : {el:.2f} s\")
print(f\"throughput    : {ct/el:.1f} tok/s   (thinking $THINK)\")
"
