.libPaths(c(Sys.getenv("RLIB"), .libPaths()))
suppressMessages({library(SingleCellExperiment); library(HDF5Array); library(iSEE)})
cat("iSEE", as.character(packageVersion("iSEE")), "| HDF5Array", as.character(packageVersion("HDF5Array")), "\n")
sce <- readRDS(file.path(Sys.getenv("DEMO_DATA"), "bm_demo_sce.rds"))
cat("in memory: class(assay(sce, 'logcounts')) =", class(assay(sce, "logcounts")), "\n")
h5 <- file.path(Sys.getenv("OUT"), "bm_logcounts.h5")
if (file.exists(h5)) unlink(h5)
assay(sce, "logcounts", withDimnames = FALSE) <- writeHDF5Array(assay(sce, "logcounts"), h5, "logcounts", chunkdim = c(1L, ncol(sce)))
a <- assay(sce, "logcounts")
cat("file-backed: class =", class(a), "| seed:", class(seed(a)), basename(path(a)), "\n")
cat("object.size in R:", format(object.size(a), units = "Kb"), "| file on disk:", round(file.size(h5) / 2^20, 1), "MB\n")
reads <- 0L
trace("h5mread", where = asNamespace("HDF5Array"), print = FALSE, tracer = quote({
  reads <<- reads + 1L
  sel <- function(s) if (is.null(s)) "all" else if (!length(s)) "none" else paste(unique(range(s)), collapse = "-")
  cat("  h5mread", name, "| rows", sel(starts[[1]]), "| cols", if (length(starts) > 1) sel(starts[[2]]) else "-", "\n") }))
cat("one gene (Mpo), as iSEE's FeatureAssayPlot reads it: assay(se)[\"Mpo\", ]\n")
v <- as.numeric(a["Mpo", ])
cat("got", length(v), "values with", reads, "HDF5 read(s); nonzero:", sum(v > 0), "\n")
