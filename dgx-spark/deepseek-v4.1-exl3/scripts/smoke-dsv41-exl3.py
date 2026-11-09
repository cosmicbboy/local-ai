#!/usr/bin/env python3
"""Smoke test for the OpenAI-compatible DeepSeek service on :8888 (standard library only).

Checks the things our agent harnesses depend on: the model alias, a plain chat, reasoning, a forced and an automatic
tool call, streaming, single-stream decode speed, and a needle in a long prompt. Prints one line per check and a JSON
summary; exits 1 if any check fails. Runs against V4 too, so the two services can be compared with the same client.

    ./smoke-dsv41-exl3.py [--base http://127.0.0.1:8888/v1] [--model deepseek-v4-flash-0731] [--long-tokens 32000]
"""
import argparse
import json
import random
import sys
import time
import urllib.request

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
}


def post(base, path, body, timeout=900):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8888/v1")
    ap.add_argument("--model", default="deepseek-v4-flash-0731")
    ap.add_argument("--long-tokens", type=int, default=32000, help="approximate prompt size for the needle check; 0 skips it")
    a = ap.parse_args()
    results = {}

    def check(name, fn):
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001 - a smoke test reports every failure the same way
            ok, detail = False, f"{type(e).__name__}: {e}"
        results[name] = {"ok": ok, "seconds": round(time.time() - t0, 1), "detail": detail}
        print(f"{'PASS' if ok else 'FAIL'}  {name:14s} {results[name]['seconds']:6.1f}s  {detail}", flush=True)

    def chat(messages, **kw):
        return post(a.base, "/chat/completions", {"model": a.model, "messages": messages, **kw})

    def models():
        with urllib.request.urlopen(a.base + "/models", timeout=30) as r:
            ids = [m["id"] for m in json.load(r)["data"]]
        return a.model in ids, f"served: {ids}"

    def plain():
        r = chat([{"role": "user", "content": "What is 17 * 23? Answer with just the number."}], max_tokens=2048)
        m = r["choices"][0]["message"]
        reasoning = m.get("reasoning_content") or m.get("reasoning") or ""
        return "391" in (m.get("content") or ""), f"content={m.get('content')!r} reasoning_chars={len(reasoning)}"

    def tool_forced():
        r = chat([{"role": "user", "content": "What's the weather in Lisbon, in celsius?"}], tools=[WEATHER_TOOL],
                 tool_choice={"type": "function", "function": {"name": "get_weather"}}, max_tokens=1024)
        calls = r["choices"][0]["message"].get("tool_calls") or []
        args = json.loads(calls[0]["function"]["arguments"]) if calls else {}
        return bool(calls) and "lisbon" in str(args.get("city", "")).lower(), f"calls={[c['function'] for c in calls]}"

    def tool_auto():
        msgs = [{"role": "user", "content": "Use the tool to check the weather in Tokyo, then tell me if I need a coat."}]
        r = chat(msgs, tools=[WEATHER_TOOL], tool_choice="auto", max_tokens=2048)
        m = r["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        if not calls:
            return False, f"no tool call; content={str(m.get('content'))[:120]!r}"
        # second turn: feed a tool result back and expect a plain answer
        msgs += [{"role": "assistant", "content": m.get("content") or "", "tool_calls": calls},
                 {"role": "tool", "tool_call_id": calls[0]["id"], "content": json.dumps({"temp_c": 4, "rain": True})}]
        r2 = chat(msgs, tools=[WEATHER_TOOL], max_tokens=2048)
        ans = r2["choices"][0]["message"].get("content") or ""
        return bool(ans.strip()), f"call={calls[0]['function']['name']} answer={ans[:80]!r}"

    def stream():
        body = {"model": a.model, "stream": True, "max_tokens": 64,
                "messages": [{"role": "user", "content": "Count from 1 to 10."}]}
        req = urllib.request.Request(a.base + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        chunks, first = 0, None
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=300) as r:
            for line in r:
                if line.startswith(b"data: ") and line.strip() != b"data: [DONE]":
                    chunks += 1
                    first = first or time.time() - t0
        return chunks > 1, f"chunks={chunks} first_chunk={first:.2f}s" if first else f"chunks={chunks}"

    def decode_speed():
        t0 = time.time()
        r = chat([{"role": "user", "content": "Write a Python function that parses an ISO 8601 date without libraries, with tests."}],
                 max_tokens=512, temperature=0, chat_template_kwargs={"thinking": False})
        dt = time.time() - t0
        n = r["usage"]["completion_tokens"]
        return n > 0, f"{n} tokens in {dt:.1f}s = {n / dt:.1f} tok/s (includes prefill)"

    def needle():
        rnd = random.Random(7)
        words = "the of and to in is was for on that with as by at from it an be this which or".split()
        filler = " ".join(rnd.choice(words) for _ in range(int(a.long_tokens * 0.75)))
        cut = len(filler) // 2
        prompt = filler[:cut] + " The secret code is PELICAN-4471. " + filler[cut:]
        r = chat([{"role": "user", "content": prompt + "\n\nWhat is the secret code? Reply with the code only."}],
                 max_tokens=1024, chat_template_kwargs={"thinking": False})
        got = r["choices"][0]["message"].get("content") or ""
        return "PELICAN-4471" in got, f"prompt_tokens={r['usage']['prompt_tokens']} reply={got[:60]!r}"

    check("models", models)
    check("chat+reasoning", plain)
    check("tool forced", tool_forced)
    check("tool auto", tool_auto)
    check("stream", stream)
    check("decode speed", decode_speed)
    if a.long_tokens:
        check("long needle", needle)
    print(json.dumps(results, indent=1))
    sys.exit(0 if all(r["ok"] for r in results.values()) else 1)


if __name__ == "__main__":
    main()
