import os, torch, torch.distributed as dist
pre = float(os.environ.get("PREALLOC_GB", "0"))
mb  = int(os.environ.get("TEST_MB", "1"))
torch.cuda.set_device(0)
hog = None
if pre > 0:
    n = int(pre * 1024**3 // 2)
    hog = torch.empty(n, dtype=torch.float16, device="cuda")
    print(f"preallocated {pre} GiB, free/total={[x/1e9 for x in torch.cuda.mem_get_info()]}", flush=True)
dist.init_process_group("nccl")
r, w = dist.get_rank(), dist.get_world_size()
t = torch.ones(mb * 1024 * 1024 // 4, dtype=torch.float32, device="cuda")
dist.all_reduce(t)
torch.cuda.synchronize()
print(f"[rank {r}/{w}] all_reduce OK on {mb} MiB with {pre} GiB preallocated", flush=True)
dist.barrier(); dist.destroy_process_group()
