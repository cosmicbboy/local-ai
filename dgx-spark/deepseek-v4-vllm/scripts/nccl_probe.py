#!/usr/bin/env python3
"""Two-rank NCCL probe: does this pair survive N communicators over the RoCE fabric?

Driven by nccl-repro.sh, which stages this file to both nodes and runs it inside the
serving image. vLLM opens several communicators over the same two ranks (world, TP,
and more), and the node-2 memory-region ceiling (README 7.5) only bites on the *third*
one - so a probe that inits a single communicator and stops would report a false PASS.
PROBE_NGROUPS is the knob that makes the failure reproducible in ~1 min instead of a
13-min vLLM boot.

Env: PROBE_RANK (0|1, required), MASTER_ADDR, MASTER_PORT, PROBE_NGROUPS,
     PROBE_PREALLOC_GB (hold N GB of unified memory first, to test under memory pressure).
Prints PROBE_PASS on success; nccl-repro.sh greps for it.
"""
import os, time, torch, torch.distributed as dist

rank = int(os.environ["PROBE_RANK"])
master = os.environ.get("MASTER_ADDR", "192.168.100.10")
port = os.environ.get("MASTER_PORT", "25000")
NGROUPS = int(os.environ.get("PROBE_NGROUPS", "1"))
PREALLOC_GB = float(os.environ.get("PROBE_PREALLOC_GB", "0"))

t0 = time.time()
torch.cuda.set_device(0)

hold = None
if PREALLOC_GB > 0:
    n = int(PREALLOC_GB * (1 << 30) // 2)
    hold = torch.empty(n, dtype=torch.float16, device="cuda")
    print(f"[rank{rank}] preallocated {PREALLOC_GB}GB", flush=True)

dist.init_process_group(
    backend="nccl",
    init_method=f"tcp://{master}:{port}",
    world_size=2,
    rank=rank,
)
print(f"[rank{rank}] world pg init ok in {time.time()-t0:.1f}s", flush=True)

x = torch.ones(1 << 20, dtype=torch.float32, device="cuda")
dist.all_reduce(x)
torch.cuda.synchronize()
print(f"[rank{rank}] world all_reduce ok", flush=True)

# The part that actually reproduces the ceiling: each new communicator registers a
# fresh set of memory regions (one per channel), and node 2 refuses past ~200 of them.
groups = []
for i in range(NGROUPS):
    g = dist.new_group(ranks=[0, 1], backend="nccl")
    y = torch.ones(1 << 22, dtype=torch.float32, device="cuda")
    dist.all_reduce(y, group=g)
    torch.cuda.synchronize()
    groups.append(g)
    print(f"[rank{rank}] subgroup {i} comm init + all_reduce ok "
          f"(t={time.time()-t0:.1f}s)", flush=True)

dist.barrier()
print(f"[rank{rank}] PROBE_PASS total={time.time()-t0:.1f}s", flush=True)
dist.destroy_process_group()
