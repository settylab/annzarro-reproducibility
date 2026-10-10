"""`cirro launch` with a Python audit hook that logs every file the server opens under the dataset path.
Run with the Cirrocumulus venv python:  cirro_audit_launch.py <audit.log> <dataset> [cirro launch args...]
The log (one line per open: epoch seconds, path) shows which chunk files a gene request reads, i.e.
whether the server reads the prepared dataset lazily."""
import sys
import time

LOG, DATASET = sys.argv[1], sys.argv[2]
_f = open(LOG, "a", buffering=1)


def hook(event, args):
    if event in ("open", "os.open") and args and isinstance(args[0], str) and args[0].startswith(DATASET):
        _f.write(f"{time.time():.3f}\t{args[0][len(DATASET):].lstrip('/')}\n")


sys.addaudithook(hook)
from cirrocumulus.__main__ import main  # noqa: E402

sys.argv = ["cirro", "launch", DATASET] + sys.argv[3:]
sys.exit(main())
