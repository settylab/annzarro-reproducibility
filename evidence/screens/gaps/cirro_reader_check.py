"""Read one gene at a time straight through Cirrocumulus's ZarrDataset (the prepare_data reader) and count the
files it opens (Python audit hook). Run with the Cirrocumulus venv python: cirro_reader_check.py <prepared.zarr>.
Prints one JSON line per read."""
import collections
import json
import sys
import warnings

warnings.filterwarnings("ignore")
Z = sys.argv[1].rstrip("/")
ops = []
sys.addaudithook(lambda e, a: ops.append(a[0][len(Z) + 1:]) if e in ("open", "os.open") and a and isinstance(a[0], str) and a[0].startswith(Z) else None)
import fsspec  # noqa: E402
from cirrocumulus.zarr_dataset import ZarrDataset  # noqa: E402

fs, d = fsspec.filesystem("file"), ZarrDataset()
for g in ["Mpo", "Car1"]:
    n = len(ops)
    d.read_dataset(fs, Z, keys={"X": [g]})
    c = collections.Counter("/".join(x.split("/")[:2]) for x in ops[n:])
    print(json.dumps({"gene": g, "opened": len(ops) - n, "X_chunks": {k: v for k, v in c.items() if k in ("X/data", "X/indices", "X/indptr")}}))
