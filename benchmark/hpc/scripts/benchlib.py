"""Shared helpers for the AnnZarro HPC benchmark.

Cold-cache control. We cannot drop the kernel page cache (no root), so before
every cold repeat we evict the files of the arrays a request touches with
posix_fadvise(POSIX_FADV_DONTNEED), and we VERIFY the eviction with mincore()
(fraction of pages resident before and after). This makes "cold" mean
*client-node cold*. The NFS filer's own cache (server side) is outside our
control; repeat 0 of every case is the only true first touch and is flagged in
the output (`first_touch`), so the two can be told apart.
"""
import ctypes
import ctypes.util
import datetime as _dt
import json
import mmap
import os
import platform
import random
import socket
import subprocess

_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
_libc.mmap.restype = ctypes.c_void_p
_libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, ctypes.c_long]
_libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
_libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte)]
_PAGE = os.sysconf("SC_PAGE_SIZE")
_MAP_FAILED = ctypes.c_void_p(-1).value


def now_iso():
    return _dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def array_files(store, arrays):
    """Every chunk/metadata file under the given array subpaths of a zarr v2 store."""
    out = []
    for a in arrays:
        root = os.path.join(store, a)
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                out.append(os.path.join(dp, fn))
    return out


def _resident_pages(path):
    """(resident_pages, total_pages) for one file, via mmap + mincore."""
    size = os.path.getsize(path)
    if size == 0:
        return 0, 0
    npages = (size + _PAGE - 1) // _PAGE
    fd = os.open(path, os.O_RDONLY)
    try:
        addr = _libc.mmap(None, size, mmap.PROT_READ, mmap.MAP_SHARED, fd, 0)
        if addr is None or addr == _MAP_FAILED:
            raise OSError(ctypes.get_errno(), "mmap failed: " + path)
        try:
            vec = (ctypes.c_ubyte * npages)()
            if _libc.mincore(addr, size, vec) != 0:
                raise OSError(ctypes.get_errno(), "mincore failed: " + path)
            return sum(v & 1 for v in vec), npages
        finally:
            _libc.munmap(addr, size)
    finally:
        os.close(fd)


def resident_fraction(files):
    res = tot = 0
    for f in files:
        r, t = _resident_pages(f)
        res += r
        tot += t
    return (res / tot) if tot else 0.0


def evict(files):
    for f in files:
        fd = os.open(f, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)


def pick_indices(n, chunk, k, seed):
    """k indices along an axis of length n, from DISTINCT chunks when the axis has
    >= k chunks (so no two picks share a chunk), otherwise distinct indices.
    Seeded, so a rerun selects the same indices."""
    rng = random.Random(seed)
    nchunks = (n + chunk - 1) // chunk
    if nchunks >= k:
        chunks = rng.sample(range(nchunks), k)
        return [min(n - 1, c * chunk + rng.randrange(min(chunk, n - c * chunk))) for c in chunks]
    if n >= k:
        return rng.sample(range(n), k)
    return [rng.randrange(n) for _ in range(k)]  # tiny axis (e.g. a 2-D embedding): repeats unavoidable


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def proc_status_mb(pid):
    """VmRSS and VmHWM (peak RSS) of a process, in MiB."""
    out = {}
    with open(f"/proc/{pid}/status") as fh:
        for line in fh:
            if line.startswith(("VmRSS:", "VmHWM:")):
                k, v = line.split(":")
                out[k] = int(v.split()[0]) / 1024.0
    return out.get("VmRSS"), out.get("VmHWM")


def _sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # environment capture must never abort a run
        return f"<error: {e}>"


def environment(paths=(), annzarro_dir=None):
    """Node / CPU / RAM / filesystem / version facts for environment.json."""
    import importlib.metadata as md
    # lscpu needs /sys, which the job sandbox hides; /proc/cpuinfo is visible.
    cpu = {"model_name": _sh("grep -m1 '^model name' /proc/cpuinfo | cut -d: -f2-"),
           "logical_cpus_on_host": _sh("grep -c ^processor /proc/cpuinfo"),
           "nproc_allowed": _sh("nproc")}
    env = {
        "captured_at": now_iso(),
        "hostname": socket.gethostname(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cpus_on_node": os.environ.get("SLURM_CPUS_ON_NODE"),
        "slurm_mem_per_node_mb": os.environ.get("SLURM_MEM_PER_NODE"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION"),
        "kernel": platform.release(),
        "os": _sh("lsb_release -ds"),
        "cpu": cpu,
        "mem_total": _sh("grep MemTotal /proc/meminfo"),
        "python": platform.python_version(),
        "packages": {p: md.version(p) for p in
                     ["annzarro", "zarr", "numcodecs", "numpy", "flask", "gunicorn", "requests",
                      "psutil", "scipy"]},
        "filesystems": {p: {"df": _sh(f"df -PT {p} | tail -1"),
                            "mount": _sh(f"findmnt -no SOURCE,FSTYPE,OPTIONS -T {p}")}
                        for p in paths},
    }
    if annzarro_dir:
        env["annzarro_commit"] = _sh(f"git -C {annzarro_dir} rev-parse HEAD")
    here = os.path.dirname(os.path.abspath(__file__))
    env["bench_commit"] = _sh(f"git -C {here} rev-parse HEAD")
    env["bench_dirty"] = _sh(f"git -C {here} status --porcelain -- .")
    return env


def write_json(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
