# Patches against the recipe checkout

The DSpark recipe (`~/dspark-ds4-0731`, branch `0731-ablit`) is an upstream repo that is
referenced and pinned, not vendored (see the service runbook, Step 1). These are the local
changes that must be re-applied to a fresh checkout of it.

| Patch | Why |
|---|---|
| [`0001-nccl-nchannels-passthrough.patch`](0001-nccl-nchannels-passthrough.patch) | Adds `NCCL_MAX_NCHANNELS` / `NCCL_MIN_NCHANNELS` to `docker-compose.dspark.yml`. **Required for the node-2 memory-region workaround to have any effect** — see runbook 7.5. |

## The gotcha this patch exists for

`docker-compose.dspark.yml`'s `environment:` map is an **explicit allowlist**. It names
every variable the container receives; anything else in `.env.dspark` is read by the
launcher and then silently dropped on the floor. There is no warning, and
`validate-dspark-config.sh` does not catch it.

So setting a *new* `NCCL_*` knob in `.env.dspark` is a two-part change every time:

1. add `FOO: "${FOO:-}"` to the fabric-passthrough block in `docker-compose.dspark.yml`, and
2. add `if [ -z "$${FOO:-}" ]; then unset FOO; fi;` to the entrypoint's unset run.

Step 2 matters because a compose map cannot conditionally omit a key: an unset knob would
otherwise arrive as a *defined-but-empty* variable, which masks NCCL's own config-file
defaults (`/etc/nccl.conf`, `NCCL_CONF_FILE`) since NCCL loads those with `overwrite=0`.

## Applying

```bash
cd ~/dspark-ds4-0731
git apply /path/to/local-ai/dgx-spark/deepseek-v4-vllm/patches/0001-nccl-nchannels-passthrough.patch
./validate-dspark-config.sh      # confirm the new knob renders in the vLLM command
```

Verify it actually reached the **serving process** (this is the check that would have
caught the silent drop). Read the vLLM process's own environment, not `docker exec
printenv` — `docker exec` starts a fresh process with the env compose configured, so it
still shows the defined-but-empty knobs that the entrypoint unset before `exec`:

```bash
docker exec deepseek-v4-flash-vllm-dspark-1 sh -c \
  'tr "\0" "\n" < /proc/1/environ | grep NCCL_'
```

Verified on 2026-09-22: both ranks show `NCCL_MAX_NCHANNELS=8`, and `NCCL_MIN_NCHANNELS`
is absent from the process env (left empty in `.env.dspark`, so correctly unset).
