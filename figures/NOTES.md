# Analysis figures 3 to 5: notes for captions and text

Script names predate the current numbering. Paper figure -> script:

| Paper | Label | Script |
|---|---|---|
| Fig. 1a-c | `fig:overview` | `fig1_overview.py` (c is drawn by `fig_comparison.draw`) |
| Fig. 2 | `fig:app` | `fig5_app.py` |
| Fig. 3 | `fig:cellcell` | `fig2_cell_by_cell.py` |
| Fig. 4 | `fig:genegene` | `fig3_gene_by_gene.py` |
| Fig. 5 | `fig:cellgene` | `fig4_cells_by_genes.py` |
| Fig. 6 | `fig:deploy` | TikZ, `manuscript/figures/fig_deploy.tex` |
| Fig. 7 | `fig:performance` | `fig6_performance.py` |

The numbers in `figures/numbers/fig{2,3,4}.json` follow the script names.

All numbers come from `data/bm_aging.zarr`, the demo store with 8,090 cells, 16,285 genes, and Kompot Young vs Old (Kompot 0.8, 190 DE genes, Mahalanobis threshold 5.82). The scripts also write every number below to `figures/numbers/fig{2,3,4}.json`, so a caption can be checked against the json. Regenerate with:

```
.venv/bin/python figures/fig2_cell_by_cell.py     # ~20 s, ~3 GB RAM (two 8,090^2 distance matrices)
.venv/bin/python figures/fig3_gene_by_gene.py     # ~5 s
.venv/bin/python figures/fig4_cells_by_genes.py   # ~5 s
```

`figures/_load.py` is the shared loader. It reads keys and example cells and genes from `data_prep/demo_panelsets/examples.json`, reads one row or column at a time, and holds the shared plotting helpers (`ring`, `highlight`, `write_numbers`). One added dependency: `adjustText` 1.4.0 for label placement. `scikit-learn` was already present.

---

## Figure 3: cell x cell (`fig2_cell_by_cell`)

**Keys:** `obsp/diffusion_walk_t5` (rows), `obsp/DM_Kernel` (graph), `obsm/DM_EigenVectors` with `uns/DM_EigenValues` (diffusion space), `obsm/X_umap`, `obs/highres_celltype`.

**Diffusion distance used (b, c):** Palantir's multiscale diffusion distance, which is the Euclidean distance in `DM_EigenVectors[:, 1:40] * λ/(1−λ)` (39 non-trivial components, summed over all walk lengths). This is the space in which Palantir computes pseudotime. I rejected the exact t = 5 diffusion distance computed from the walk matrix. Beyond the walk's reach it does not saturate cleanly: it reflects the *other* cell's walk concentration, not similarity. That makes it unusable for a global comparison.

### (a) Walk rows along HSC → monocyte
- **How the trajectory is defined:** the shortest path from the example HSC (`HSPC_Old_1#GAAGCCCGTGGCTCTG-1`) to the example monocyte (`Mature_Young_2#TCAATTCAGTGAGGCT-1`) on the DM_Kernel graph, with each edge weighted by its multiscale diffusion distance. The path has 13 cells: HSC ×2, LMPP ×4, GMP ×5, Monocyte ×2. The thin ink line in each panel is this path.
- **How the intermediates are chosen:** the path cells closest to 1/3 and 2/3 of the path's diffusion length, i.e. evenly spaced in diffusion pseudo-distance.
  - LMPP `HSPC_Old_2#ACTCTCGCAAACCGGA-1` (fraction 0.319)
  - GMP `HSPC_Old_3#ATTTCACTCGTAGTGT-1` (fraction 0.626)
- **Colour:** one shared log10 scale from 1e-5 to 0.0126 (the largest entry across the four rows). Cells with walk probability < 1e-5 are NEUTRAL. The neutral cells hold at most 0.33% of any row's mass.
- **Per focus cell:**

  | Focus | n_eff = 1/Σp² | Cells ≥ 1e-5 | Mass in own cell type |
  |---|---|---|---|
  | HSC | 251 | 956 | 90.7% |
  | LMPP | 517 | 1,953 | 72.5% |
  | GMP | 559 | 2,148 | 24.3% |
  | Monocyte | 289 | 844 | 88.6% |

### (b) UMAP distance vs diffusion distance, one focused cell
- **Discordant groups,** defined on the focused cell's rank percentiles:
  - A = among its 5% nearest in UMAP, but outside its 20% nearest in diffusion space.
  - B = the reverse.
- The dashed lines mark these quantiles.
- **How the focus was chosen.** The criterion is objective. Take the cell type whose cells most consistently have both groups: the largest median over its cells of min(|A|, |B|), considering only types with ≥ 10 cells. Then take the cell of that type closest to the type median, which is a typical member rather than the extreme.
  - The winner is **Plasma cell**, median 266. Next are MBEP 142, Basophil 92 and Basophil Progenitor 62. Every other type is ≤ 4.
  - Focus: `Mature_Mid_1#GCCATGGAGTATGATG-1`.
  - (The single most extreme cell is an LMPP whose diffusion neighbours are neutrophils. I did not use it because it is likely an outlier or mislabelled.)
- **Focused plasma cell:**
  - Spearman ρ(UMAP distance, diffusion distance) = **0.62** over 8,089 cells.
  - kNN-30 Jaccard = 0.20.
  - **A = 265 cells:** pDC 92, NK 66, basophil 43, T 40, CD8 TEM 18, and others. They receive **0.09%** of the focused cell's 5-step walk mass.
  - **B = 392 cells:** naive B 274, memory B 111, immature B 7. They receive **59.2%** of the walk mass.
  - The 5% UMAP-nearest cells hold 23.1% of the walk mass. The 5% diffusion-nearest hold 78.6%.
- **Robustness:** all 12 of 12 plasma cells have both groups ≥ 15. Their median walk mass is 0.2% on A and 53.2% on B.

### (c) The same groups on X_umap
The direct labels name the cell types with ≥ 20 cells in each group and give that group's walk mass. The focus is ringed.

### Dataset-wide numbers (suggested for text or caption, all 8,090 cells as focus)
- **Global rank order is preserved well.** The per-cell Spearman ρ between UMAP and diffusion distance has median **0.85** (IQR 0.65–0.92). The example HSC is at 0.95.
- **Local neighbourhoods are not preserved.** The kNN-30 Jaccard between UMAP and diffusion space has median **0.30** (IQR 0.20–0.50), i.e. a median of 14 of 30 neighbours shared.
- 33.9% of cells have at least one "near in UMAP, far in diffusion" cell. 14.7% have at least one of the reverse.
- 236 cells have both groups ≥ 15: LMPP 58, CLP 54, basophil 47 (of 47), Basophil Progenitor 25, MBEP 14, MKP 13, plasma 12 (of 12), and others.
- **Honest caveat for the text:** for the HSC → monocyte trajectory cells the UMAP is largely faithful. The HSC has A = 21 (all LMPP) and B = 0. Distortion concentrates in small or isolated populations (plasma cells, basophils, MBEP), whose placement between clusters is arbitrary. That is the Chari & Pachter point, and the text should not claim UMAP is globally wrong here.

---

## Figure 4: gene x gene (`fig3_gene_by_gene`)

**Keys:** `varp/spearman_fold_change`, `varp/spearman_smoothed`, `var/kompot_de_Young_to_Old_mean_lfc`, `var/kompot_de_Young_to_Old_mahalanobis`, `var/kompot_de_Young_to_Old_is_de`.

### (a) Volcano coloured by H2-Q7's spearman_fold_change row
- DIV colour scale, −1 to 1. The strongest |ρ| is drawn on top. The dashed line is the DE threshold (Mahalanobis 5.82, FDR 5%).
- H2-Q7 has mean LFC 0.372 and Mahalanobis 15.2 (rank 1).
- Top partners labelled: H2-Q6 0.82 (DE), Tapbpl 0.73, H2-D1 0.66, Fxyd5 0.65, Sec62 0.63. Next are B2m 0.60, Plekha5 0.60, Tle5 0.59, Ezh1 0.57 and H2-T22 0.57 (DE).
- **Only H2-Q6 among the top partners is DE.**
- Genes with ρ > 0.7: 2. Genes with ρ > 0.5: 35. Genes with ρ < −0.5: 53.

### (b) Same volcano, focus H2-Aa
- Top partners: H2-Eb1 0.93, H2-Ab1 0.88, Ciita 0.84 (not DE), Cd74 0.81, H2-DMb1 0.74 (not DE).
- Genes with ρ > 0.7: 6. Genes with ρ > 0.5: 127.
- ρ_fc(H2-Q7, H2-Aa) = **0.20**. ρ_smoothed between them = 0.47.

### (c) Continuous vs discrete
- **Palette (revised):** module 1 = purple CAT[6], module 2 = dark green CAT[5] (labelled directly), module 3 = amber CAT[3]. This avoids the DIV blue/red that encode the sign of ρ in a and b. Panel d uses the same non-DIV hues: purple = age response, amber = cell-state pattern only.
- **Method:** the 190 DE genes, average-linkage hierarchical clustering on 1 − ρ (spearman_fold_change). Average linkage is WGCNA's default linkage; it is used here on 1 − ρ, not on TOM.
- **Choosing k:** k = **3**, the maximum mean silhouette over k = 2..12. The silhouette is nearly flat at 0.23–0.25 for k = 2–6, so the data offer no natural cut; that is itself worth saying.
- **Modules** (renumbered: 1 = H2-Q7's):
  - **Module 1, 87 genes:** H2-Q7, Cd74, H2-Aa, H2-Ab1, H2-Eb1, AW112010, Ifitm3, H2-Q6, and others. MHC-I and MHC-II are lumped together.
  - **Module 2, 68 genes:** Tyrobp, Cd3g, Trbc2, Plac8, Fcer1g, and others.
  - **Module 3, 35 genes:** Igkc, S100a9, S100a8, Cd52, Ighm, Cd79a, and others.
- **H2-Q7 (top strip):**
  - Median ρ to its 86 module-mates is **0.16**. **52 of 86** have ρ < 0.2 and 24 have ρ < 0.
  - Cd74 (0.24) and H2-Aa (0.20) are in its module.
  - **0** non-members have ρ > 0.5. The best non-member is Fyb at 0.42.
  - **Key point:** its strongest partners after H2-Q6 (Tapbpl 0.73, H2-D1 0.66, Fxyd5 0.65, Sec62 0.63, B2m 0.60) are **not DE**, so they belong to no module at all. 30 non-DE genes have ρ > 0.5.
- **S100a9 (bottom strip):**
  - In module 3. Median in-module ρ = 0.24, and **13 of 34** members have ρ < 0.2.
  - Outside its module: **Camp 0.72 and Ngp 0.61** (module 2). That is **1** non-member with ρ > 0.7, 2 with ρ > 0.5 and 6 with ρ > 0.4.
- **Sensitivity at k = 5:**
  - Camp and Ngp still fall outside S100a9's module.
  - H2-Q7's module shrinks to 27 genes, with median 0.39 and 4 genes < 0.2. The "weak members" effect for H2-Q7 is therefore k-dependent, while the boundary-crossing for S100a9 is not.

### (d) spearman_smoothed vs spearman_fold_change rows of H2-Q7
- **Smoothed ρ > 0.7:** 204 genes. **Fold-change ρ > 0.7:** 2 genes. **Both:** 1 gene (H2-Q6).
- **Orange, "cell-state pattern only"** (smoothed > 0.7, fold change < 0.5): 192 genes, e.g. H2-K1 (0.90 / 0.21) and Zc3h6 (0.88 / 0.39).
- **Blue, "age response"** (fold change > 0.5): 35 genes. Several share the age response with *opposite* cell-state patterns: Fxyd5 −0.21 / 0.66, Nod2 −0.48 / 0.55, Lcp2 −0.47 / 0.53. H2-D1 is 0.15 / 0.66.
- Pearson between the two rows is 0.35 (Spearman 0.36).
- **Interpretation:** H2-K1, a classical MHC-I gene, follows H2-Q7's cell-state pattern but not its age response.

---

## Figure 5: cells x genes (`fig4_cells_by_genes`)

**Keys:** `layers/kompot_de_Young_to_Old_fold_change`, `layers/kompot_de_Young_smoothed`, `layers/kompot_de_Old_smoothed`. The fold change is Old − Young smoothed log2 expression; this is checked in the script, max |diff| 2e-7. The expression is `logged_counts`, i.e. log2(x + 0.1) − log2(0.1).

**Focus gene: S100a9.** It is the store's focus gene (examples.json).
- Mean LFC **−0.051**, but Mahalanobis 10.4 (rank 8).
- The per-cell fold change ranges from −1.46 to +0.31.
- It is strongly negative only in HSCs: HSC median **−1.35** (next lowest is non-classical monocyte at −0.21 (−0.206)). 3.9% of cells have FC < −0.5, of which 288 are HSC, 24 LMPP and 5 MKP.
- **The point:** the gene-level mean hides a large, cell-state-restricted loss.

### (a) Fold-change column
DIV scale, symmetric at ±1.46. Rings mark the locked HSC and the focused monocyte. Their FC is −1.35 for the HSC and −0.02 for the monocyte.

### (b, c) Smoothed expression, Young vs Old
- One shared SEQ scale, 0 to 3.77.
- **HSC median: Young 1.74, Old 0.39.**
- Neutrophils are 3.53 (Young) vs 3.63 (Old). Monocytes are 1.86 vs 1.84.

### (d) Rows of the fold-change layer: locked HSC (x) vs focused monocyte (y)
- 16,285 genes. Equal aspect, with the identity line.
- **Encoding is threshold-free (revised).** Non-DE genes are grey. DE genes are coloured only by the sign of x·y, with no magnitude cut: purple (CAT[6]) = same direction, amber (CAT[3]) = opposite direction. These hues avoid panel a's DIV blue/red.
- **Labels:** the 5 strongest opposite-direction DE genes by min(|x|, |y|), plus S100a9 (ringed).

  | Gene | HSC FC | Monocyte FC |
  |---|---|---|
  | Apoe | +0.94 | −0.35 |
  | Hmgn2 | −0.29 | +0.18 |
  | Wfdc21 | −0.62 | +0.17 |
  | G0s2 | −0.21 | +0.11 |
  | Il1b | −0.10 | +0.11 |

- **The HSC's age effects are much larger than the monocyte's.** Median |FC| over DE genes is 0.41 in the HSC vs 0.068 in the monocyte. The monocyte's range is only −0.37 to 0.39.
- **Agreement between the two cells:** Spearman ρ between the two rows is **0.53 over DE genes** and 0.18 over all genes.
- **Opposite-direction DE genes, threshold-free: 61 of 190 (32%).** The other 129 change in the same direction. For comparison, 43% of all genes have opposite signs.
- **Opposite-direction genes are mostly small changes.** Median min(|x|, |y|) is 0.028 for opposite-direction DE genes vs 0.080 for same-direction ones. Most opposite calls are therefore near-zero changes in at least one cell.
- **Noise level (approximate).** The Kompot fold-change z-score layer was **not stored**. As a substitute, a gene-shared per-cell fold-change s.d. is sqrt(sd_Y² + sd_O²) from obs `kompot_de_{Young,Old}_std`: 0.153 for the HSC and 0.121 for the monocyte.
  - DE genes beyond 1.96 s.d.: 120 in the HSC and 13 in the monocyte.
  - Beyond 1.96 s.d. in both cells: **1 opposite-direction gene (Apoe)** and 10 same-direction genes.
  - This s.d. ignores gene-specific variance, so treat it as approximate.
- The old hard-threshold counts (626 / 100 / 2 genes at |FC| > 0.05 / 0.1 / 0.2) are superseded and no longer in the figure.

---

## Open issues
1. **Fig 3 framing:** for the trajectory cells the UMAP is faithful (ρ ≈ 0.95). The "UMAP misleads" example is a plasma cell, not the HSC. Text and captions must say this, and the dataset-wide numbers back it.
2. **Fig 4c module choice:** clustering on DE genes only is what the brief asked for. It excludes H2-Q7's best partners (Tapbpl, H2-D1, B2m), which arguably strengthens the argument but is a design choice reviewers may question. The silhouette is flat, so k = 3 is weakly determined.
3. **Fig 5d noise level:** the noise estimate uses Kompot's per-cell s.d. (shared across genes) because the fold-change z-score layer was not stored. Storing `kompot_de_Young_to_Old_fold_change_zscores` would give a per-gene, per-cell noise level.
4. Volcano labels in the dense core (Sec62, Fxyd5) sit on points. They are legible at print size, but a light halo could help.
