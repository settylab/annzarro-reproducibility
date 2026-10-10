# HPC benchmark findings

Measured on AnnZarro v0.4.1 (HPC worker jobs J4, T, J5 and T2; ledger row A15, closed). The
per-case results and their case map are under `benchmark/scale/results/hpc/full/`
(`benchmark/scale/NOTES.md`, "HPC on v0.4.1"). Cold
means a fresh server with the node's page cache evicted. The stores are public:
Tahoe-100M-derived and synthetic, read from node-local scratch.

The earlier HPC findings (AnnZarro 0.1.1, 58030e1) are in `HISTORY.md`; they are superseded
and not cited by the paper.
