# Server profiling hook (tool_ceiling), no tracing overhead: on SIGUSR1, walk the
# GC-tracked containers, find the numpy arrays and Python strings they hold, and
# write the largest arrays with their owner (the holding container's type and the
# attribute/key it sits under) and totals by owner to $TC_PROF_OUT.<pid>.
import os, signal

if os.environ.get("TC_PROF_OUT"):
    def _dump(signum, frame):
        import gc, sys, collections
        import numpy as np
        seen, arrays = set(), []
        strs = [0, 0]
        for obj in gc.get_objects():
            if isinstance(obj, dict):
                items = obj.items()
            elif isinstance(obj, (list, tuple, set, frozenset)):
                items = ((i, v) for i, v in enumerate(obj))
            elif hasattr(obj, "__dict__") and isinstance(getattr(obj, "__dict__", None), dict):
                continue  # its __dict__ is visited as a dict
            else:
                continue
            for k, v in items:
                if isinstance(v, np.ndarray):
                    base = v if v.base is None else v.base
                    if id(base) in seen:
                        continue
                    seen.add(id(base))
                    nb = base.nbytes if isinstance(base, np.ndarray) else v.nbytes
                    owner = type(obj).__name__
                    for r in gc.get_referrers(obj)[:3]:
                        if hasattr(r, "__dict__") and getattr(r, "__dict__", None) is obj:
                            owner = f"{type(r).__module__}.{type(r).__qualname__}"
                            break
                    arrays.append((nb, owner, str(k)[:40], str(v.dtype), str(v.shape)))
                elif isinstance(v, str):
                    strs[0] += 1
                    strs[1] += sys.getsizeof(v)
        arrays.sort(reverse=True)
        by_owner = collections.Counter()
        for nb, owner, k, dt, sh in arrays:
            by_owner[f"{owner}.{k}"] += nb
        with open(os.environ["TC_PROF_OUT"] + f".{os.getpid()}", "w") as f:
            f.write(f"numpy arrays reachable from containers: {len(arrays)}, {sum(a[0] for a in arrays)} bytes\n")
            f.write(f"str values in containers: {strs[0]}, {strs[1]} bytes\n== largest arrays\n")
            for a in arrays[:40]:
                f.write("\t".join(map(str, a)) + "\n")
            f.write("== by owner.key\n")
            for k, nb in by_owner.most_common(30):
                f.write(f"{nb}\t{k}\n")
    signal.signal(signal.SIGUSR1, _dump)
