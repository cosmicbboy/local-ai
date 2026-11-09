# DeepSeek-V4.1-Flash-1017 EXL3 2.7 bpw service (TP=2 across 2× DGX Spark)

> **Status: LIVE since 2026-11-09 15:58 EST** on `http://192.168.100.10:8888/v1` as
> `deepseek-v4-flash-0731` (same name as V4, so harness configs are unchanged). V4 is stopped but intact
> and can be restored in one step (see "Rolling back to V4" below).
>
> **Not yet production-hardened:** no systemd unit or watchdog, so it won't restart after a crash
> or reboot. The recipe's 2-hour agent soak test hasn't been run.

## What runs

| | |
|---|---|
| Weights | [`0xSero/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw`](https://huggingface.co/0xSero/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw) @ `e34ef55bda7c37d17d8dcc86a8a64e7cb875481e`, `~/models/dsv41-1017-exl3` on both nodes (185 GB) |
| Engram tables | DeepSeek's official 1017 shards 47–48, hardlinked from `~/models/deepseek-v4.1-flash-1017-fp8` (read from NVMe at lookup time, not loaded into memory) |
| Engine | sudoingX's recipe (vLLM `6e517b15` + patch series + `vllm_exl3_moe`), checkout `~/dsv41-0xsero/recipe` @ `cc59c360`, unmodified |
| Image | `ghcr.io/sybil-solutions/deepseek-v4.1-flash-exl3-spark@sha256:5817414f…e9e4` (pinned by digest) |
| Shape | TP=2, container `dsv41-serve` on each node, recipe defaults: `MAX_SEQS=2`, 262K context, text only, DSpark speculator |

Our site settings live in [`scripts/serve-dsv41-exl3.sh`](scripts/serve-dsv41-exl3.sh), which wraps the recipe's
`dsv41_tp2.sh`:

- Uses the fabric port that's up on our nodes (`enp1s0f1np1` / `rocep1s0f1`). The recipe derives the RoCE v2 GID index (3) from that port's IPv4 address.
- Sets `NCCL_MAX_NCHANNELS=8` because of node 2's memory-region ceiling.
- Runs a drop-caches sidecar while booting only. The recipe's own `sudo -n` drop fails here, and its "drop_caches needs sudo -n" warning is expected.

```bash
scripts/serve-dsv41-exl3.sh up        # refuses if :8888 is already served; ~10-11 min to ready
scripts/serve-dsv41-exl3.sh status | logs [head|worker] | down
python3 scripts/smoke-dsv41-exl3.py   # same checks as for V4; exits 1 on any failure
```

## Swap test, 2026-11-09

These were each measured once, with the same smoke-test client against both services.

| Check | V4-Flash-0731 | V4.1 EXL3 2.7 bpw |
|---|---|---|
| models / chat+reasoning / tool forced / tool auto (2-turn) / stream | all PASS | all PASS |
| Decode, 512 tokens, temp 0, single stream (includes prefill) | 73.8 tok/s | **87.0 tok/s** |
| Needle in 24,031-token prompt | PASS, 12.6 s | PASS, 12.7 s |
| Boot to ready | — | 677 s |
| Free memory after load, node 1 / node 2 | — | 8–9 / 10–11 GiB (recipe wants ≥ 4) |
| Max context / concurrent sequences | 1M / more | 262K / 2 |

Staging: the 0xSero download from Hugging Face (no token) took several hours because of repeated read timeouts. The copy to node 2 (rsync capped at 400 MB/s while V4 served) took 9 min. `MANIFEST.sha256` passed on both nodes.

Caveat: the smoke test only checks that the API behaves as harnesses expect. It doesn't measure quality.
The quant's quality loss on tool-call turns (see [`../deepseek-v4.1-vllm/FINDINGS.md`](../deepseek-v4.1-vllm/FINDINGS.md) §3)
still needs to be checked on our own agent workloads.

## Rolling back to V4

```bash
scripts/serve-dsv41-exl3.sh down
systemctl --user start deepseek-v4-flash.service deepseek-v4-flash-watchdog.timer   # restart the watchdog too
curl -s http://127.0.0.1:8888/v1/models    # max_model_len 1048576 means V4 is back
```

`deepseek-v4-flash.service` and its watchdog timer are still enabled (with lingering on), and the `dsv41-serve`
containers have `restart=no`. So **a reboot rolls back to V4 automatically**. Run `down` and stop V4 before you run `up` again.

## TODO before calling this production

- A systemd user unit and a watchdog for `dsv41-serve`, and disable `deepseek-v4-flash.service`.
- The recipe's 2-hour agent soak test.
- Tool-call quality on our agent harnesses.
