# The shared tahoe_first<N>.h5ad as a .cloupe for Loupe Browser, through LoupeR's
# create_loupe() (what create_loupe_from_seurat() calls after taking the counts,
# clusters and reductions out of a Seurat object; no Seurat needed).
# X (cells x genes, CSR) is read as the genes x cells dgCMatrix LoupeR wants: the
# same three arrays. Barcodes become LoupeR's accepted "cellid_<9 digits>" form
# (validate.R L102), since Tahoe's are not 10x barcodes; clusters: cell_line_id;
# projection: X_umap. Input preparation, not measured.
# Needs: loupeR installed and loupeR::setup() run once by the operator (EULA, louper binary).
# Usage: Rscript loupe_build.R IN.h5ad OUTDIR NAME   (NAME --dry: read and check only)
a <- commandArgs(TRUE)
dry <- identical(a[3], "--dry")  # read and check the input only
suppressMessages({ library(hdf5r); library(Matrix); if (!dry) library(loupeR) })
f <- H5File$new(a[1], mode = "r")
shape <- h5attr(f[["X"]], "shape")
n <- shape[1]; g <- shape[2]
stopifnot(h5attr(f[["X"]], "encoding-type") == "csr_matrix", n <= 999999999)
p <- f[["X/indptr"]]$read()
stopifnot(p[length(p)] < 2^31)  # dgCMatrix stores at most 2^31 - 1 values
m <- new("dgCMatrix", i = as.integer(f[["X/indices"]]$read()), p = as.integer(p), x = as.numeric(f[["X/data"]]$read()),
         Dim = as.integer(c(g, n)))
ix <- f[["var/_index"]]  # anndata 0.11: a nullable-string-array group (values, mask)
genes <- if (inherits(ix, "H5Group")) ix[["values"]]$read() else ix$read()
bc <- sprintf("cellid_%09d", seq_len(n))
dimnames(m) <- list(genes, bc)
cl <- f[["obs/cell_line_id"]]
codes <- cl[["codes"]]$read(); cats <- cl[["categories"]]$read()
clusters <- list(cell_line_id = factor(cats[codes + 1], levels = cats))
umap <- t(f[["obsm/X_umap"]]$read())
if (nrow(umap) != n) umap <- t(umap)
rownames(umap) <- bc
f$close_all()
if (dry) { print(m[1:3, 1:3]); str(clusters); print(dim(umap)); print(summary(colSums(m != 0))); quit(save = "no") }
t0 <- Sys.time()
create_loupe(m, clusters = clusters, projections = list(umap = umap), output_dir = a[2], output_name = a[3], force = TRUE)
cat(sprintf("%s: %d cells x %d genes, %.0f s\n", file.path(a[2], paste0(a[3], ".cloupe")), n, g,
            as.numeric(difftime(Sys.time(), t0, units = "secs"))))
