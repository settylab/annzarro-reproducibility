# Files edited after the HPC worker copy

`MANIFEST_fhfast_copy.tsv` records the sha256 of each file as copied from $SCRATCH. Three files here
differ from it by design (manuscript-writer, 2026-10-06, operator rule: no pre-v0.4.0 AnnZarro build
anywhere in the paper's evidence):

- `CONDITIONS.md`: the rows for runs J and R (a pre-v0.4.0 build) and the competitor
  CxG 20M row removed, with the sentences comparing J3 to them. J3's own conditions are unchanged.
- `NOTES.md`: the scheduling and pinning history before the v0.4.0 repin (earlier builds,
  their smoke timings) removed; the v0.4.0 pin, the jobs and the node-cold protocol are unchanged.
- `j3_filerwarm.sh`: two comments that named the earlier runs' build and their smoke timings reworded;
  no executable line changed.

Every other file matches its MANIFEST sha256 (checked on import, 2951fc4). The originals are in the
HPC worker copy ($DATA_ROOT/annzarro-scale-results/j3_v040/) and on
annzarro-reproducibility branch dominik/scale-hpc (fab9ba1).
