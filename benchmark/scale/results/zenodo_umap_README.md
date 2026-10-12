# AnnZarro paper data

Data for the AnnZarro preprint (Otto, Baasri and Setty; bioRxiv, https://doi.org/10.64898/2026.10.10.758158).
The record has two parts:

1. **`bm_aging_annzarro.zarr`**: an AnnZarro-ready store of single-cell CITE-seq of murine
   bone marrow across aging (8,090 cells x 16,285 genes). The AnnZarro documentation,
   tutorials and paper-figure pages open this store.
2. **A UMAP of every cell of Tahoe-100M** (95,624,334 cells), behind the paper's scale figure
   and scale benchmark.

DOI of this record: https://doi.org/10.5281/zenodo.23277103. AnnZarro software: https://doi.org/10.5281/zenodo.23222216
(all versions). Documentation: https://annzarro.readthedocs.io

## Files

| file | part | size | what |
| --- | --- | ---: | --- |
| `bm_aging_annzarro.zarr.zip` | 1 | 5,742,844,951 bytes | the store, zipped without compression (its chunks are already compressed) |
| `bm_aging_annzarro.FIELDS.md` | 1 | | every field of the store, with shape, dtype, chunks and definition |
| `tahoe100m_umap.parquet` | 2 | 1,205,375,373 bytes | UMAP coordinates of all 95,624,334 cells |
| `tahoe100m_umap_reference.parquet` | 2 | 7,081,992 bytes | the 999,073 reference cells the UMAP was fitted on |
| `SHA256SUMS` | | | SHA-256 of the four data files above, in `sha256sum -c` format |
| `README.md` | | | this file |

Check the downloads with `sha256sum -c SHA256SUMS` (on macOS: `shasum -a 256 -c SHA256SUMS`).

## Part 1: bm_aging_annzarro.zarr

### Source and license

Derived from

> Single-cell CITE-seq of murine bone marrow across aging (Young, Mid, Old). Fred Hutchinson
> Cancer Center. Zenodo (2025). https://doi.org/10.5281/zenodo.15587768
> (file `murine_bone_marrow_aging.h5ad`, MD5 `3e346c91e029e5fde551a9ebf9ecee78`)

The source is licensed CC BY 4.0, and so is this store. Cite the source record and this record.

### How to open it

```bash
unzip bm_aging_annzarro.zarr.zip          # gives the directory bm_aging_annzarro.zarr (4,243 files)
pip install annzarro                      # AnnZarro 0.4.2 or later
annzarro start --data-dir .               # the folder that holds the store
```

Then open http://127.0.0.1:8000/ and pick `bm_aging_annzarro.zarr`. The store is plain Zarr
format 2 with consolidated metadata, so `anndata.read_zarr` and `zarr.open_group` read it as well.

### What is in it

All of the processed source data: `X`, the count layers, `obs`, `var`, PCA, Harmony and the 2-D
UMAP, the scanpy kNN graph, the Palantir diffusion kernel and eigenvectors, a five-step diffusion
walk, the Kompot differential expression and abundance results (Young to Old) with their smoothed
and fold-change layers, and two gene x gene Spearman correlation matrices. In addition:

- **3-D UMAP** `obsm/X_umap_3d`, from the same kNN graph as the 2-D `X_umap` (parameters in
  `uns/umap_3d`).
- **Cell-cell similarity**: `obsp/diffusion_distance` (Palantir multiscale diffusion space),
  `obsp/umap_distance`, `obsm/X_diffusion`.
- **Gene statistics**: `varm/mean_by_celltype`, `varm/fraction_expressing_by_celltype`,
  `varm/mean_by_age`, `varm/fraction_expressing_by_age`, `var/detection_rate`,
  `var/variance_logged`.
- **Kompot z-scores**: `layers/kompot_de_Young_to_Old_fold_change_zscores`.
- **Figure fields** behind the paper's figures, with descriptive names and their colors in `uns`.

`bm_aging_annzarro.FIELDS.md` lists every field; the same text is in the store as `uns/README`.

### How it was made

With two scripts in the AnnZarro repository, https://github.com/settylab/annzarro:

1. `docs/_tools/datasets/bm_aging.py` builds `bm_aging.zarr` from the source h5ad (Kompot 0.8.0,
   about 30 GB of RAM). The `bm_aging.zarr` used here has the store MD5
   `b0d150cf4161887febefafe460b0a4b4` (MD5 over every file of the directory store: sorted relative
   path, then its bytes; the rule is in the AnnZarro documentation, Demo data). A rebuild from the
   h5ad differs from it by about 1e-6 in Kompot's floating-point outputs, so its MD5 differs.
2. `docs/_tools/make_annzarro_store.py` adds the fields above to a copy of `bm_aging.zarr`,
   checks every figure field against the numbers reported in the paper (it stops if one does not
   reproduce), and writes `uns/README` and the field list.

The store in this record has the store MD5 `a372502012ded8cd238e5eb83e408b89` by the same rule.

## Part 2: a UMAP of every cell of Tahoe-100M

Two-dimensional UMAP coordinates for all 95,624,334 cells of Tahoe-100M, the single-cell
perturbation atlas by Tahoe Therapeutics and the Arc Institute (Zhang et al., Cell 2026,
https://doi.org/10.1016/j.cell.2026.08.035). Tahoe-100M ships without a UMAP.

### Files

| file | rows | columns |
| --- | ---: | --- |
| `tahoe100m_umap.parquet` | 95,624,334 | `cell_index` (int64), `BARCODE_SUB_LIB_ID` (string), `umap_1`, `umap_2` (float32), `is_reference` (bool) |
| `tahoe100m_umap_reference.parquet` | 999,073 | `cell_index` (int64), `BARCODE_SUB_LIB_ID`, `plate`, `cell_line_id` (string) |

Both are Apache Parquet with zstd compression.

- **`cell_index`** is the cell's row in Tahoe-100M's order: the Hugging Face release
  `tahoebio/Tahoe-100M` (dataset card last modified 2025-07-23), 3,388 parquet shards read in file
  order, then rows within each shard in order.
- **`BARCODE_SUB_LIB_ID`** is the release's cell identifier. All 95,624,334 values are distinct.
- **`is_reference`** marks the cells the UMAP was fitted on.
- The raw little-endian float32 bytes of `[umap_1, umap_2]` in `cell_index` order have SHA-256
  `575e8bb1efac3a69d556d129f3d44b53946501554b0122061a60766e3fda458a`. That is the `obsm/X_umap`
  of the store drawn in the paper's scale figure.

### How to join with Tahoe-100M

Join on `BARCODE_SUB_LIB_ID`, or by position (reading the shards in file order gives row
`cell_index`):

```python
import pandas as pd
umap = pd.read_parquet("tahoe100m_umap.parquet", columns=["BARCODE_SUB_LIB_ID", "umap_1", "umap_2"])
cells = pd.read_parquet("train-00000-of-03388.parquet", columns=["BARCODE_SUB_LIB_ID"])  # any shard
cells = cells.merge(umap, on="BARCODE_SUB_LIB_ID", how="left")
```

In an AnnData object built from the shards in order, set
`adata.obsm["X_umap"] = umap[["umap_1", "umap_2"]].to_numpy()` after checking `adata.obs_names`
against `BARCODE_SUB_LIB_ID`.

### Method

Scripts: `benchmark/scale/build_tahoe.py` (PCA), `benchmark/scale/umap_tahoe.py` (UMAP and
placement) and `benchmark/scale/zenodo_umap.py` (this deposit), in
https://github.com/settylab/annzarro-reproducibility.

1. **Expression space.** Counts normalized to 10,000 per cell, then log1p. The 2,000 genes of
   highest variance are kept and centered, and 50 principal components are computed by randomized
   SVD (seed 0), fitted on the reference cells of step 2. PC1 and PC2 explain 2.35% and 1.64% of
   the variance of the 2,000 genes, the 50 PCs together 17.0%. Every cell is projected exactly onto
   the 50 components.
2. **Reference sample.** Up to 1,430 cells from every stratum of plate x `cell_line_id` (all cells
   of a smaller stratum; numpy `default_rng(0)`): 999,073 reference cells from 700 strata (14 plates
   x 50 cell lines; 10 strata, all CVCL_1571, had fewer than 1,430 cells). The ids in
   `tahoe100m_umap_reference.parquet` were regenerated with the same rule and seed; they match the
   UMAP run in the total and in each of the 700 stratum counts. The run's own index file was not
   archived, so identity cell by cell follows from the deterministic rule and was not compared
   directly.
3. **Fit.** umap-learn 0.5.12 (pynndescent 0.6.0, numba 0.68.0, numpy 2.4.6, Python 3.11.6) on the
   reference cells' 50 PCs: `n_neighbors=15`, `min_dist=0.3`, `metric="euclidean"`,
   `random_state=0`.
4. **Placement.** Every other cell is placed at the mean of the UMAP coordinates of its 15 nearest
   reference cells in PC space, weighted by 1/(L2 distance + 0.001); the neighbors come from
   faiss-cpu 1.15.1 IVF-Flat (`nlist=4096`, `nprobe=32`), with recall 0.997 against exact search on
   100,000 random non-reference cells. Reference cells keep their fitted coordinates.
5. **Validation** (on samples of the layout): 15-nearest-neighbor cell-line purity 0.948 (0.950 in
   PC space; 0.027 at random); silhouette by cell line 0.597 (0.162 in PC space); same-plate fraction
   of the 15 nearest neighbors 0.093, against 0.079 if plates were fully mixed within cell lines.

The placed cells are an out-of-sample projection, not a joint UMAP of all 95.6M cells. Distances
and densities in the layout are not quantitative.

### License

These derived coordinates and reference ids are released under CC BY 4.0. Tahoe-100M itself is
released under CC0 1.0 (Hugging Face dataset card).

## How to cite

Cite this record and the AnnZarro paper (Otto, D. J., Baasri, S. and Setty, M., bioRxiv 2026, https://doi.org/10.64898/2026.10.10.758158). For part 1 also cite the source record
https://doi.org/10.5281/zenodo.15587768; for part 2 also cite Tahoe-100M: Zhang, J. et al.
Tahoe-100M: mapping drug-induced molecular phenotypes at single-cell resolution. Cell 189,
5945-5961.e8 (2026). https://doi.org/10.1016/j.cell.2026.08.035

## Contact

Dominik J. Otto and Manu Setty, Fred Hutchinson
Cancer Center, Seattle, WA, USA.
