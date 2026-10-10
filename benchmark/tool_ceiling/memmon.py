#!/usr/bin/env python
"""Peak memory of a process tree on macOS, by phys_footprint.

phys_footprint (proc_pid_rusage, RUSAGE_INFO_V4) is what Activity Monitor calls
"Memory": anonymous and dirty memory, including the parts the kernel has
compressed or swapped out, without clean file-backed pages (mmap, page cache)
that the kernel can drop at no cost. RSS is logged as well.

Two peaks are kept for every group of processes:
- `fp_peak`: the largest sum over the group's processes, sampled every
  `interval` s. This is the concurrent peak, which a sampler can underestimate
  between samples.
- `fp_lifetime_sum`: the sum of each process's ri_lifetime_max_phys_footprint,
  which the kernel tracks exactly. It is an upper bound on the concurrent peak
  (processes need not peak at the same time), and equals it for one process.

Use as a library (Monitor) or as a wrapper:

  memmon.py --out run.json [--timeout S] [--cap-gb G] -- CMD ...

which runs CMD, watches its process tree, kills it on timeout or when the tree
passes the cap, and writes {status, rc, wall_s, peaks, ps_before} to run.json.

For a desktop app started by someone else (a person, or a computer-use session):

  memmon.py --out run.json --attach-name "ManiVault Studio" --until DONE_FILE ... [--started-file F]

waits for a process of that name, samples it and its children (group "app")
until one of the --until files exists or the app exits, then writes the same
record (status "ok", "app_exited", "timeout" or "cap"). The cap still kills the
app: it is the machine guard. --started-file is written once sampling runs.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

import psutil

_libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
RUSAGE_INFO_V4 = 4


class _RusageV4(ctypes.Structure):
    _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [(f"f{i}", ctypes.c_uint64) for i in range(40)]


# uint64 field positions after ri_uuid in struct rusage_info_v4 (<sys/resource.h>)
_RESIDENT, _FOOTPRINT, _LIFETIME_MAX = 6, 7, 28


def rusage(pid: int) -> tuple[int, int, int] | None:
    """(phys_footprint, lifetime max phys_footprint, resident size) in bytes."""
    buf = _RusageV4()
    if _libproc.proc_pid_rusage(pid, RUSAGE_INFO_V4, ctypes.byref(buf)) != 0:
        return None
    return getattr(buf, f"f{_FOOTPRINT}"), getattr(buf, f"f{_LIFETIME_MAX}"), getattr(buf, f"f{_RESIDENT}")


def tree(pid: int) -> list[int]:
    try:
        p = psutil.Process(pid)
        return [pid] + [c.pid for c in p.children(recursive=True)]
    except psutil.NoSuchProcess:
        return []


_names: dict[int, str] = {}


def _name(pid: int) -> str:
    if pid not in _names:
        try:
            p = psutil.Process(pid)
            _names[pid] = p.name() + " " + " ".join(p.cmdline()[:3])
        except (psutil.Error, OSError):
            _names[pid] = ""
    return _names[pid]


HARNESS = re.compile(r"playwright|^node |ceiling\.py|_task\.py")


def web_groups(root: int) -> dict:
    """Split the tree under a web driver (root, not counted) into client (every
    Chromium process), server (the tool's processes) and harness (Playwright's
    node driver)."""
    def members(kind):
        def fn():
            out = []
            for pid in tree(root)[1:]:
                nm = _name(pid)
                k = "client" if "Chrom" in nm or "chrome" in nm else "harness" if HARNESS.search(nm) else "server"
                if k == kind:
                    out.append(pid)
            return out
        return fn
    return {k: members(k) for k in ("client", "server", "harness")}


OTHERS = re.compile(r"pytest|ms-playwright|Chrome for Testing|npm (run )?test|vitest|jest")


def others_active() -> list[str]:
    """Other agents' test runs or Playwright browsers alive at the start of a run
    (time-unclean, not memory-unclean). This process tree has nothing yet."""
    out = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
        except (psutil.Error, OSError):
            continue
        if p.info["pid"] != os.getpid() and OTHERS.search(cmd):
            out.append(f'{p.info["pid"]} {cmd[:160]}')
    return out


def ps_snapshot() -> str:
    out = subprocess.run("ps -axo pid,rss,pcpu,comm | sort -k3 -nr | head", shell=True,
                         capture_output=True, text=True).stdout
    level = subprocess.run(["sysctl", "-n", "kern.memorystatus_level"], capture_output=True, text=True).stdout
    swap = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    return f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\nmemorystatus_level={level.strip()} swap={swap.strip()}\n{out}"


HANG_CPU = 2.0  # CPU seconds over the whole hang window below which a run has made no progress


class Monitor(threading.Thread):
    """Sample groups of processes; `groups` maps a name to a function returning pids."""

    def __init__(self, groups: dict, interval: float = 0.05, cap: int | None = None, on_cap=None,
                 hang_s: float | None = None, on_hang=None):
        super().__init__(daemon=True)
        self.groups, self.interval, self.cap, self.on_cap = groups, interval, cap, on_cap
        self.peak = {g: {"fp_peak": 0, "rss_peak": 0, "fp_lifetime": {}, "n_proc_max": 0} for g in groups}
        self.total_fp_peak = 0
        self.total_rss_peak = 0
        self.capped = False
        self._halt = threading.Event()
        self.trace: list[tuple[float, int]] = []
        # no progress: the measured processes together used < HANG_CPU s of CPU over hang_s s
        self.hang_s, self.on_hang, self.hung = hang_s, on_hang, False
        self.cpu_marks: list[tuple[float, float]] = []

    def sample(self):
        tot_fp = tot_rss = 0
        for g, fn in self.groups.items():
            fp = rss = n = 0
            for pid in set(fn()):
                r = rusage(pid)
                if r is None:
                    continue
                fp += r[0]
                rss += r[2]
                n += 1
                lt = self.peak[g]["fp_lifetime"]
                lt[pid] = max(lt.get(pid, 0), r[1])
            pk = self.peak[g]
            pk["fp_peak"] = max(pk["fp_peak"], fp)
            pk["rss_peak"] = max(pk["rss_peak"], rss)
            pk["n_proc_max"] = max(pk["n_proc_max"], n)
            if g != "harness":
                tot_fp += fp
                tot_rss += rss
        self.total_fp_peak = max(self.total_fp_peak, tot_fp)
        self.total_rss_peak = max(self.total_rss_peak, tot_rss)
        return tot_fp

    def run(self):
        t0 = time.time()
        k = 0
        while not self._halt.is_set():
            fp = self.sample()
            if k % 20 == 0:
                self.trace.append((round(time.time() - t0, 2), fp))
            k += 1
            if self.hang_s and k % 20 == 0 and not self.hung:
                now, cpu = time.time() - t0, self.cpu_total()
                self.cpu_marks.append((now, cpu))
                old = [c for t, c in self.cpu_marks if t <= now - self.hang_s]
                if old and cpu - old[-1] < HANG_CPU:
                    self.hung = True
                    if self.on_hang:
                        self.on_hang()
            if self.cap and fp > self.cap and not self.capped:
                self.capped = True
                if self.on_cap:
                    self.on_cap()
            self._halt.wait(self.interval)

    def cpu_total(self) -> float:
        tot = 0.0
        for g, fn in self.groups.items():
            if g == "harness":
                continue
            for pid in set(fn()):
                try:
                    c = psutil.Process(pid).cpu_times()
                    tot += c.user + c.system
                except (psutil.Error, OSError):
                    pass
        return tot

    def stop(self) -> dict:
        self._halt.set()
        self.join()
        out = {}
        for g, pk in self.peak.items():
            out[g] = {"fp_peak": pk["fp_peak"], "fp_lifetime_sum": sum(pk["fp_lifetime"].values()),
                      "rss_peak": pk["rss_peak"], "n_proc_max": pk["n_proc_max"]}
        tot = [g for g in out if g != "harness"]
        out["total"] = {"fp_peak": self.total_fp_peak, "rss_peak": self.total_rss_peak,
                        "fp_lifetime_sum": sum(out[g]["fp_lifetime_sum"] for g in tot)}
        return out


def kill_tree(pid: int):
    for p in reversed(tree(pid)):
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass


def app_pids(name: str) -> list[int]:
    """Every process named `name`, with its children."""
    out = []
    for p in psutil.process_iter(["pid", "name"]):
        if p.info["name"] == name:
            out += tree(p.info["pid"])
    return out


def attach(a) -> int:
    ps_before, others, t0 = ps_snapshot(), others_active(), time.time()
    while not app_pids(a.attach_name):
        if time.time() - t0 > a.timeout:
            raise SystemExit(f"no process named {a.attach_name!r} within {a.timeout:.0f} s")
        time.sleep(0.5)
    found = sorted(app_pids(a.attach_name))
    mon = Monitor({"app": lambda: app_pids(a.attach_name)}, cap=int(a.cap_gb * 2**30),
                  on_cap=lambda: [kill_tree(pid) for pid in app_pids(a.attach_name)])
    mon.start()
    if a.started_file:
        open(a.started_file, "w").write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} pids={found}\n")
    t1, status = time.time(), "timeout"
    while time.time() - t1 < a.timeout:
        if any(os.path.exists(f) for f in a.until):
            status = "ok"; break
        if not app_pids(a.attach_name):
            status = "app_exited"; break
        time.sleep(0.5)
    peaks = mon.stop()
    status = "cap" if mon.capped else status
    res = {"attach_name": a.attach_name, "pids_at_start": found, "status": status,
           "ended_by": [f for f in a.until if os.path.exists(f)], "wall_s": round(time.time() - t1, 2),
           "peaks": peaks, "trace": mon.trace, "ps_before": ps_before, "others_at_start": others}
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("status", "wall_s")}),
          f"fp_peak={peaks['app']['fp_peak'] / 2**30:.2f}GB lifetime={peaks['app']['fp_lifetime_sum'] / 2**30:.2f}GB",
          file=sys.stderr)
    return 0 if status == "ok" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--cap-gb", type=float, default=85)  # machine guard (48 until 2026-10-05)
    ap.add_argument("--hang-s", type=float, default=0,
                    help="end the run as 'hang' when its processes (client and server; not the harness) use "
                         "< HANG_CPU s of CPU over this many seconds (0: off)")
    ap.add_argument("--web", action="store_true",
                    help="CMD is a browser driver: report client/server groups, not the driver itself")
    ap.add_argument("--attach-name", help="watch the running app of this process name instead of running CMD")
    ap.add_argument("--until", nargs="+", default=[], help="--attach-name: stop when any of these files exists")
    ap.add_argument("--started-file", help="--attach-name: written once sampling has started")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    if a.attach_name:
        sys.exit(attach(a))
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    ps_before = ps_snapshot()
    others = others_active()
    t0 = time.time()
    proc = subprocess.Popen(cmd, start_new_session=True)
    groups = web_groups(proc.pid) if a.web else {"proc": lambda: tree(proc.pid)}
    mon = Monitor(groups, cap=int(a.cap_gb * 2**30), on_cap=lambda: kill_tree(proc.pid),
                  hang_s=a.hang_s or None, on_hang=lambda: kill_tree(proc.pid))
    mon.start()
    try:
        rc = proc.wait(timeout=a.timeout)
        status = "ok" if rc == 0 else "error"
    except subprocess.TimeoutExpired:
        kill_tree(proc.pid)
        rc = proc.wait()
        status = "timeout"
    wall = time.time() - t0
    peaks = mon.stop()
    if mon.capped:
        status = "cap"
    elif mon.hung:
        status = "hang"
    elif rc == -signal.SIGKILL and status == "error":
        status = "killed"
    res = {"cmd": cmd, "status": status, "rc": rc, "wall_s": round(wall, 2), "peaks": peaks,
           "trace": mon.trace, "ps_before": ps_before,
           "others_at_start": others}
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("status", "rc", "wall_s")}),
          f"fp_peak={peaks['total']['fp_peak'] / 2**30:.2f}GB lifetime={peaks['total']['fp_lifetime_sum'] / 2**30:.2f}GB",
          file=sys.stderr)
    sys.exit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
