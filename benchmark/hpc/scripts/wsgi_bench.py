"""WSGI entry for the benchmark AnnZarro instance.

Mirrors the live pilot shim (work/annzarro/wsgi_pilot.py) so the measured
server is configured like the deployed one: DEFAULT_CONFIG plus auth off,
cache on, cache_memory_mb=8000, cache_dataset_limit=6. Only data_dir, port and
log_file differ, and all three come from the environment so that every run is
bound to localhost on its own port and logs outside the project tree.

Launch (done by bench_http.py, never by hand on a login node):
    gunicorn --workers 1 --worker-class sync --bind 127.0.0.1:$PORT wsgi_bench:app
"""
import os

from annzarro.server.core import create_app, DEFAULT_CONFIG

config = dict(DEFAULT_CONFIG)
config.update({
    "host": "127.0.0.1",
    "port": int(os.environ["ANNZARRO_BENCH_PORT"]),
    "data_dir": os.environ["ANNZARRO_BENCH_DATA_DIR"],
    "auth_enabled": False,
    "cache_enabled": os.environ.get("ANNZARRO_BENCH_CACHE", "1") == "1",
    "cache_memory_mb": int(os.environ.get("ANNZARRO_BENCH_CACHE_MB", "8000")),
    "cache_dataset_limit": int(os.environ.get("ANNZARRO_BENCH_CACHE_DATASETS", "6")),
    "log_file": os.environ["ANNZARRO_BENCH_LOG"],
    "log_level": "WARNING",
})

app = create_app(config)
