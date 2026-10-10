#!/usr/bin/env Rscript
# The Seurat v5 task: open the dataset, DimPlot coloured by cell line, then
# FeaturePlot of one gene, each to a PNG. Run inside memmon.py.
#
# Variants (both read the h5ad the way the Seurat v5 BPCells vignette does,
# https://satijalab.org/seurat/articles/seurat5_bpcells_interaction_vignette):
#   default  open_matrix_anndata_hdf5() then as(, "dgCMatrix"): counts in memory
#   bpcells  open_matrix_dir() on a BPCells directory written beforehand by
#            write_matrix_dir() (the conversion, measured as its own phase:
#            variant "bpcells_write")
# obs (all columns) and obsm/X_umap are read with hdf5r. FeaturePlot colours
# by the stored values (slot "counts"), the same values sc.pl.umap uses from X;
# NormalizeData is not part of the task, as it is not for Scanpy.
# Every cell drawn: nrow of the plot's data must equal the number of cells
# (DimPlot rasterises with scattermore above 100,000 cells, which still draws
# every point).
#
# Usage: seurat_task.R VARIANT H5AD OUTPREFIX [BPCELLS_DIR]
suppressPackageStartupMessages({
  library(Seurat); library(BPCells); library(hdf5r); library(ggplot2); library(jsonlite)
})
args <- commandArgs(trailingOnly = TRUE)
variant <- args[1]; h5ad <- args[2]; out <- args[3]; bpdir <- if (length(args) > 3) args[4] else NA
gene <- "MALAT1"; colour <- "cell_line_id"
rec <- list(variant = variant, path = h5ad, phases = list(), checks = list(),
            versions = list(R = R.version.string, Seurat = as.character(packageVersion("Seurat")),
                            SeuratObject = as.character(packageVersion("SeuratObject")),
                            BPCells = as.character(packageVersion("BPCells")),
                            ggplot2 = as.character(packageVersion("ggplot2"))))
t0 <- Sys.time()
mark <- function(k) {
  rec$phases[[k]] <<- round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 2)
  message(sprintf("[%8.1fs] %s", rec$phases[[k]], k))
  write_json(rec, paste0(out, ".json"), auto_unbox = TRUE, pretty = TRUE)
}

read_obs <- function(f) {
  g <- f[["obs"]]
  cols <- h5attr(g, "column-order")
  idx <- g[[h5attr(g, "_index")]]$read()
  df <- data.frame(row.names = idx)
  for (k in cols) {
    e <- g[[k]]
    if (inherits(e, "H5Group")) {
      codes <- e[["codes"]]$read()
      df[[k]] <- factor(e[["categories"]]$read()[codes + 1L], levels = e[["categories"]]$read())
    } else {
      df[[k]] <- e$read()
    }
  }
  df
}

if (variant == "bpcells_write") {
  write_matrix_dir(open_matrix_anndata_hdf5(h5ad), bpdir, overwrite = TRUE)
  mark("write_matrix_dir")
  quit(status = 0)
}

f <- H5File$new(h5ad, "r")
meta <- read_obs(f)
umap <- t(f[["obsm/X_umap"]]$read())   # hdf5r returns the transposed (2 x n) array
f$close_all()
mark("read_obs_obsm")
if (variant == "default") {
  counts <- as(open_matrix_anndata_hdf5(h5ad), "dgCMatrix")
} else if (variant == "bpcells") {
  counts <- open_matrix_dir(bpdir)
} else stop("unknown variant ", variant)
mark("read_counts")
obj <- CreateSeuratObject(counts = counts, meta.data = meta)
rm(counts, meta); invisible(gc())
rownames(umap) <- colnames(obj); colnames(umap) <- c("umap_1", "umap_2")
obj[["umap"]] <- CreateDimReducObject(embeddings = umap, key = "umap_", assay = "RNA")
rm(umap)
rec$n_obs <- ncol(obj)
mark("load")

plots <- list(cat = function() DimPlot(obj, reduction = "umap", group.by = colour),
              gene = function() FeaturePlot(obj, features = gene, reduction = "umap", slot = "counts"))
for (tag in names(plots)) {
  p <- plots[[tag]]()
  png <- sprintf("%s_%s.png", out, tag)
  ggsave(png, p, width = 7, height = 6, dpi = 150, device = ragg::agg_png)
  n_drawn <- nrow(p[[1]]$data)
  img <- png::readPNG(png)[, , 1:3]
  n_col <- nrow(unique(matrix(round(img * 255), ncol = 3)))
  rec$checks[[tag]] <- list(n_drawn = n_drawn, all_cells = n_drawn == ncol(obj), n_colours = n_col, png = png)
  rm(p); invisible(gc())
  mark(paste0("plot_", tag))
}
rec$ok <- all(sapply(rec$checks, function(x) x$all_cells)) && rec$checks$cat$n_colours >= 20
mark("done")
quit(status = if (rec$ok) 0 else 3)
