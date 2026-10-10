#!/usr/bin/env Rscript
# The h5ad as a SingleCellExperiment .rds, the input iSEE and ShinyCell take:
# assay "counts" = X as a genes x cells dgCMatrix (h5ad CSR read as CSC with
# hdf5r), colData = every obs column, reducedDim "UMAP" = obsm/X_umap.
# Measured as a conversion run charged to iSEE/ShinyCell. (The Bioconductor
# route, zellkonverter::readH5AD, goes through Python anndata and is not
# installed here.) A dgCMatrix holds at most 2^31 - 1 values, which this panel
# store reaches at about 19.5M cells.
#
# Usage: to_sce.R H5AD OUT.rds
suppressPackageStartupMessages({library(hdf5r); library(SingleCellExperiment); library(Matrix)})
args <- commandArgs(trailingOnly = TRUE)
f <- H5File$new(args[1], "r")
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
X <- f[["X"]]
shape <- h5attr(X, "shape")
nnz <- X[["data"]]$dims
if (nnz > .Machine$integer.max) stop(sprintf("X has %.0f values; a dgCMatrix holds at most 2^31 - 1", nnz))
counts <- new("dgCMatrix", i = X[["indices"]]$read(), p = as.integer(X[["indptr"]]$read()),
              x = as.double(X[["data"]]$read()), Dim = as.integer(c(shape[2], shape[1])),
              Dimnames = list(genes, idx))
umap <- t(f[["obsm/X_umap"]]$read())
f$close_all()
dimnames(umap) <- list(idx, c("UMAP_1", "UMAP_2"))
sce <- SingleCellExperiment(assays = list(counts = counts), colData = obs, reducedDims = list(UMAP = umap))
rm(counts, umap, obs); invisible(gc())
saveRDS(sce, args[2], compress = FALSE)
print(sce)
