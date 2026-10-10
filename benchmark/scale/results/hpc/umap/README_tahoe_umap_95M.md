# tahoe_umap_95M.f32.npy

A 2-D UMAP layout of every cell of Tahoe-100M (Hugging Face `tahoebio/Tahoe-100M`, CC0-1.0; Zhang et al.,
bioRxiv 2025, doi:10.1101/2025.02.20.639398). Computed on the Fred Hutch HPC, 2026-10-02/03.

- **Array:** float32, shape (95,624,334, 2), C order, .npy format 1.0 with a 128-byte header (764,994,800 bytes). Load with `np.load(path, mmap_mode="r")`.
- **Row order:** shard order of the 3,388 parquet shards (train-00000 … train-03387), cells in file order within a shard. This is the row order of every store in stores_panel/; the N-cell store holds rows 0..N-1.
- **sha256:**
  - the file: 2030af2865828666e891a6c0d5da80bcfc7a309b9418be2b9d155bf73b82bf22
  - the data section (bytes after the header) = obsm/X_umap of tahoe_panel_95.6M_plot.zarr: 575e8bb1efac3a69d556d129f3d44b53946501554b0122061a60766e3fda458a

## How it was made (annzarro-reproducibility, branch dominik/scale-hpc, benchmark/scale/)

1. **Reference sample** (`umap_tahoe.py sample --per-stratum 1430`, seed 0):
   - up to 1,430 cells from every plate × cell_line_id stratum, all cells of smaller strata;
   - 999,073 cells from 700 strata (14 plates × 50 lines; 10 strata below 1,430, all CVCL_1571);
   - table: results/hpc/umap/ref_strata.csv.
2. **PCA** (`build_tahoe.py refit` on the reference sample):
   - counts normalised to 1e4 per cell, log1p, the 2,000 genes of highest variance on the sample, centred, 50 PCs by randomized SVD (seed 0);
   - PC1-2 explain 2.35% / 1.64%, the 50 PCs 17.0%;
   - every cell projected exactly (`build_tahoe.py master --n-pcs 50`).
3. **UMAP** (`umap_tahoe.py fit`): umap-learn 0.5.12 on the reference cells' 50 PCs, n_neighbors 15, min_dist 0.3, euclidean, random_state 0, low_memory.
4. **Placement** (`umap_tahoe.py place`):
   - every non-reference cell gets the inverse-distance-weighted mean (weights 1/(L2 + 1e-3)) of the UMAP coordinates of its 15 nearest reference cells in PC space;
   - neighbours from faiss-cpu 1.15.1 IndexIVFFlat, nlist 4096, nprobe 32, which gives recall@15 = 0.997 against exact search on 100,000 non-reference cells;
   - reference cells keep their fitted coordinates.
5. **Validation** (`umap_tahoe.py validate`; results/hpc/umap/validate.json, knn_preservation_by_pool.json):
   - 15-NN cell-line purity 0.948 (PCA 0.950, random 0.027); silhouette by cell line 0.597 (PCA 0.162);
   - same-plate fraction of the 15-NN 0.093 vs 0.079 if plates were fully mixed within cell lines; plate entropy 2.91 vs 3.02 bits;
   - kNN preservation PC→UMAP depends on the pool size: reference 0.027 (1M pool), 0.115 (100k), 0.373 (10k), 0.481 (5k), with uniform placed pools 0.004-0.027 below the reference cells at each size (knn_preservation_by_pool_v2.json; the v1 control drew biased placed pools); the pool trend alone does not separate a good layout from a bad one, since a within-line shuffle null also falls (0.00063 at 1M, 0.113 at 5k, so the layout is 42× and 4× the null), and a UMAP fitted fresh on a 5k pool scores 0.471 against 0.481 for the 1M fit's 5k subsample (skeptic pass, $SCRATCH/scale-worker-sk/out/sk_umap.json);
   - previews: results/hpc/umap/preview_1M_*.png.

Environment: Python 3.11.6, numpy 2.4.6, numba 0.68.0, pynndescent 0.6.0, scikit-learn 1.9.1 (results/hpc/venv_panel.freeze.txt). Jobs and nodes: results/hpc/builds_hpc.csv.

$SCRATCH purges files 30 days after creation, so this copy expires around 2026-11-01.
