import logging, re, time, anndata as ad, zarr
from zarr.storage import FsspecStore
calls = []                                   # every S3 request s3fs makes, from its debug log
class Log(logging.Handler):
    def emit(self, r):
        m = re.search(r"CALL: (\w+) .*'Key': '([^']+)'", r.getMessage())
        if m: calls.append((m.group(1), m.group(2).split(".anndata.zarr/")[-1]))
logging.getLogger("s3fs").setLevel(logging.DEBUG); logging.getLogger("s3fs").addHandler(Log())

url = "s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr"      # public bucket, no credentials
t = time.time()
store = FsspecStore.from_url(url, storage_options={"anon": True}, read_only=True)
a = ad.experimental.read_lazy(zarr.open_group(store, mode="r"))
print(f"anndata {ad.__version__}, zarr {zarr.__version__}: opened {url}")
print(f"  {a.n_obs:,} x {a.n_vars:,} in {time.time() - t:.1f} s; X is a {type(a.X).__module__.split('.')[0]} {type(a.X).__name__}, chunks {a.X.chunksize}")
n0 = len(calls); gets0 = sum(c[0] == "get_object" for c in calls)
print(f"  S3 requests to open: {n0} ({gets0} GET), e.g. {sorted({c[1].split('/')[0] for c in calls})}")
t = time.time(); g = a.var_names[0]
col = a[:, g].X.compute()
new = [c for c in calls[n0:] if c[0] == "get_object"]
print(f"one gene ({g}): {col.shape[0]:,} x {col.shape[1]} in {time.time() - t:.1f} s, {len(new)} GET requests:")
for c in new[:10]: print("  GET", c[1])
if len(new) > 10: print(f"  ... {len(new) - 10} more")
