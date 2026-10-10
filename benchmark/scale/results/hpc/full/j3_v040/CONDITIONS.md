# Measurement conditions: J3

Operator rulings 2026-10-05/06: "cold" means NODE-cold only: a fresh server process plus the compute node's page
cache evicted for the store's files. File-server-cold is dropped, because it cannot be guaranteed. The filer cache is
never controlled. J3 reads the Tahoe-100M-derived stores (public, CC0-1.0) in place on $SCRATCH (NFS4,
nfs-scratch-filer:/temp/lab/user).

| run | job | AnnZarro | filer | node | tool |
|---|---|---|---|---|---|
| **J3 (full/j3_v040)** | **10100751** | **v0.4.0: RC 3bdeb09, tree bb2ace6 = tag v0.4.0 49e2a19** | each store read once before its rung (warmup.tsv); filer speed 175-240 MB/s pre/post at every rung, i.e. the warm-up had no measurable effect, so the filer is uncontrolled | cold | cold |

J3: hpc-node-27, 2026-10-06 08:09:52-11:41:43 PDT, harness annzarro-reproducibility bfd7cd0 benchmark/scale/bench_http.py, 3 cold
reps + 2 warm per click, rungs 1M..95.6M. 1518 rows: 1507 status 200, 11 skipped. The skips are all
cell_row_cscscan_all: 2 at 10M by the 120 s slow-rule, and 3 each at 20M/50M/95.6M by --skip. At 1M every rep
ran (j3_slow1m.txt = a). The exact eviction is in cold_protocol.json: posix_fadvise(DONTNEED) on every store file,
per-file errors ignored, no per-rep mincore check in this harness.

OPEN ITEM (for the J4 local-scratch read, not investigated): 50M gene_high_all warm_new median 3.261 s is above its
cold median 1.959 s; check whether it recurs with the store on node-local scratch.
