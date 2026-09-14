#!/usr/bin/env python3
"""Streaming single-stream decode benchmark for the DSpark vLLM endpoint.
Usage: ./bench-dspark.py [--port 8888] [--runs 3] [--think off|low|high] [--prompt code|prose]"""
import argparse, json, time, urllib.request
ap = argparse.ArgumentParser()
ap.add_argument("--port", default="8888"); ap.add_argument("--model", default="deepseek-v4-flash-0731")
ap.add_argument("--runs", type=int, default=3); ap.add_argument("--think", default="off")
ap.add_argument("--prompt", default="code"); ap.add_argument("--max-tokens", type=int, default=768)
a = ap.parse_args()
PROMPTS = {"code": "Write a complete Python implementation of an LRU cache with unit tests.",
           "prose": "Write a short story about a lighthouse keeper who discovers a message in a bottle."}
kw = {"thinking": False} if a.think == "off" else {"thinking": True, "reasoning_effort": a.think}
for i in range(a.runs):
    body = json.dumps({"model": a.model, "messages": [{"role": "user", "content": PROMPTS[a.prompt] + f" (run {i})"}],
                       "max_tokens": a.max_tokens, "temperature": 0.6, "stream": True,
                       "stream_options": {"include_usage": True}, "chat_template_kwargs": kw}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/chat/completions", body, {"Content-Type": "application/json"})
    t0 = time.time(); first = None; usage = {}
    with urllib.request.urlopen(req) as r:
        for line in r:
            if not line.startswith(b"data: ") or line.strip() == b"data: [DONE]": continue
            d = json.loads(line[6:])
            if d.get("usage"): usage = d["usage"]
            ch = d.get("choices") or []
            if ch and first is None and (ch[0]["delta"].get("content") or ch[0]["delta"].get("reasoning_content") or ch[0]["delta"].get("reasoning")):
                first = time.time()
    end = time.time(); n = usage.get("completion_tokens", 0)
    print(f"run {i}: {n} tok  ttft {first-t0:.2f}s  decode {(n-1)/(end-first):.1f} tok/s  e2e {n/(end-t0):.1f} tok/s  "
          f"(think={a.think}, prompt={a.prompt})", flush=True)
