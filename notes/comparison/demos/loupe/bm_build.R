# bm_demo.h5ad (the shared 8,090-cell bone marrow demo every Fig. 1c tool was scored on) as a .cloupe, through
# LoupeR's create_loupe(), adapted from benchmark/tool_ceiling/loupe_build.R.
# Counts: layers/counts (raw UMI counts; X is log-normalised). Barcodes: "Sample#ACGT...-1" -> "Sample_ACGT...-1",
# the 10x GEM form LoupeR accepts (validate.R: prefix must end in ':' or '_'), so each cell keeps its identity.
# Clusters: every categorical obs column (LoupeR takes categorical metadata only). Projections: X_umap,
# X_draw_graph_fa, X_pca (PC1-2) and X_diffusion (DC1-2; DC0 is the constant component).
# Usage: Rscript bm_build.R IN.h5ad OUTDIR NAME
a <- commandArgs(TRUE)
suppressMessages({ library(hdf5r); library(Matrix); library(loupeR) })
f <- H5File$new(a[1], mode = "r")
X <- f[["layers/counts"]]
shape <- h5attr(X, "shape"); n <- shape[1]; g <- shape[2]
stopifnot(h5attr(X, "encoding-type") == "csr_matrix")
m <- new("dgCMatrix", i = as.integer(X[["indices"]]$read()), p = as.integer(X[["indptr"]]$read()),
         x = as.numeric(X[["data"]]$read()), Dim = as.integer(c(g, n)))
rd <- function(ds) { if (inherits(ds, "H5Group")) ds[["values"]]$read() else ds$read() }
genes <- rd(f[["var/_index"]]); bc <- gsub("#", "_", rd(f[["obs/_index"]]), fixed = TRUE)
stopifnot(!anyDuplicated(bc), !anyDuplicated(genes))
dimnames(m) <- list(genes, bc)
obs <- f[["obs"]]; clusters <- list()
for (k in obs$ls()$name) {
  o <- obs[[k]]
  if (inherits(o, "H5Group") && all(c("codes", "categories") %in% o$ls()$name)) {
    codes <- o[["codes"]]$read(); cats <- o[["categories"]]$read()
    clusters[[k]] <- factor(ifelse(codes < 0, NA, cats[codes + 1]), levels = cats)
  }
}
emb <- function(key, cols) { e <- f[[paste0("obsm/", key)]]$read(); if (nrow(e) != n) e <- t(e); e <- e[, cols, drop = FALSE]; rownames(e) <- bc; e }
projections <- list(umap = emb("X_umap", 1:2), draw_graph_fa = emb("X_draw_graph_fa", 1:2),
                    pca = emb("X_pca", 1:2), diffusion = emb("X_diffusion", 2:3))
f$close_all()
cat("clusters:", paste(names(clusters), collapse = ", "), "\n")
t0 <- Sys.time()
create_loupe(m, clusters = clusters, projections = projections, output_dir = a[2], output_name = a[3], force = TRUE)
cat(sprintf("%s: %d cells x %d genes, %.0f s\n", file.path(a[2], paste0(a[3], ".cloupe")), n, g,
            as.numeric(difftime(Sys.time(), t0, units = "secs"))))
