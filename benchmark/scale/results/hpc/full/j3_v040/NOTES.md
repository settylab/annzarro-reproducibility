# J3 notes (AnnZarro v0.4.0)

Earlier scheduling and pinning history (v0.3.1 and older builds) was removed on 2026-10-06: the paper states no value from builds before v0.4.0 (operator rule). See EDITED.md.

- 2026-10-05 23:55 PDT: **J3 and T REPINNED to AnnZarro v0.4.0** (operator via laptop 20261006T063417Z, tag confirmed after).
  Pin: release candidate 3bdeb0913d7e5761c496070dbb30acd2cd32ceb5, tree bb2ace6d4f0078c41738dabd1bb6f64de15771ca, version 0.4.0
  = tag v0.4.0 49e2a1962d30d9adccbf5093f7d199b42b2bce12 (same tree; the RC is not the tag's ancestor). hpcbench/venv_v040rc,
  non-editable from the clean clone hpcbench/src_v040rc; 26 vendor assets verified (vendor_assets.py + --check), shipped;
  `uv pip check` clean, packages identical to v0.3.1's lock (hpcbench/pin_v040rc.json). The guards check commit, tree and
  that tag v0.4.0 names 49e2a19 with the same tree; annzarro_pin.json records all four.
  Smoke run-060 (compute-node): both harnesses rc 0; J3 data clicks byte-identical to v0.3.1 (only open_structure +29 B).
  JOBS: J3 = **run-061** (afterany:10098747, the UCSC 95.6M build: J3 runs on a quiet filer), then UCSC 95.6M server
  10100752 (afterok:build, afterany:J3), then T = **10100753** (afterany:J3,afterany:10100752; run dir hpcbench/run_v040).
  Held 10093086 and T run-059 (v0.3.1) CANCELLED, never ran.
- 2026-10-06 10:45 PDT: OPERATOR (request 20261006T173541Z): cold = NODE-cold only (fresh server + evicted compute-node page
  cache); file-server-cold dropped. J3 run-061 (running since 08:09:52 on compute-node) already complies, unchanged: it never had
  a filer-cold step. Its node-cold = bench_http bfd7cd0 make_cold("fadvise"): posix_fadvise(fd,0,0,POSIX_FADV_DONTNEED) on
  EVERY file of the store (os.walk), per-file OSError IGNORED, no per-rep mincore check ("cold prep" seconds in the startup
  note), then a fresh `annzarro start` per cold rep. LIMITATION vs T: eviction errors are silent and residency is not
  verified per rep; the only mincore evidence is warmcheck.py's 60 sampled files (resident_after_evict 0.0 at every check).
  Filer warm-up (warmread.py) had no measurable effect on filer read speed: warmcheck pre / post_warm / post_measure stayed
  at 175-240 MB/s at every rung (post_warm NOT faster than pre at 1M, 5M, 10M, 20M, 50M, 95.6M: flagged as the filer
  being uncontrolled, consistent with dropping filer-cold).
  Minor overlapped I/O during the 95.6M rung: git commit/push of paper-hpcbench (benchlib.py edit, a few KB) and log reads
  at ~10:40-10:45.
