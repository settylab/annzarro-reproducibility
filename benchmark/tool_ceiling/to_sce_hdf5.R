#!/usr/bin/env Rscript
# iSEE variant 7b: an HDF5-backed SingleCellExperiment. The counts assay is
# HDF5Array::H5ADMatrix on the h5ad itself (a DelayedArray read from disk on
# demand: no dgCMatrix, so no 2^31-1 limit); colData = every obs column and
# reducedDim "UMAP" = obsm/X_umap, in memory. Saved as .rds (the assay keeps
# a reference to the h5ad path). Measured as a conversion run charged to iSEE.
# Usage: to_sce_hdf5.R H5AD OUT.rds   (tool_ceiling's rceiling env: HDF5Array)
suppressPackageStartupMessages({library(hdf5r); library(SingleCellExperiment); library(HDF5Array)})
args <- commandArgs(trailingOnly = TRUE)
f <- hdf5r::H5File$new(args[1], "r")  # HDF5Array also defines H5File
g <- f[["obs"]]
idx <- g[[h5attr(g, "_index")]]$read()
obs <- S4Vectors::DataFrame(row.names = idx)
for (k in h5attr(g, "column-order")) {
  e <- g[[k]]
  if (inherits(e, "H5Group")) {
    lev <- e[["categories"]]$read()
    obs[[k]] <- factor(lev[e[["codes"]]$read() + 1L], levels = lev)
  } else obs[[k]] <- e$read()
}
v <- f[["var"]]
genes <- v[[h5attr(v, "_index")]]$read()
umap <- t(f[["obsm/X_umap"]]$read())
f$close_all()
counts <- H5ADMatrix(normalizePath(args[1]))
dimnames(counts) <- list(genes, idx)
dimnames(umap) <- list(idx, c("UMAP_1", "UMAP_2"))
sce <- SingleCellExperiment(assays = list(counts = counts), colData = obs, reducedDims = list(UMAP = umap))
base::saveRDS(sce, args[2], compress = FALSE)  # the assay points at the h5ad, which stays in place
print(sce)
