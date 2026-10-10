#!/usr/bin/env Rscript
# A ShinyCell app from the SingleCellExperiment .rds (to_sce.R): createConfig,
# default cell info cell_line_id, default gene MALAT1, UMAP, gene values from
# the "counts" assay. makeShinyApp writes the metadata/coordinates (.rds) and
# a gene-by-cell HDF5 of every gene. Measured as a conversion run.
# Usage: shinycell_build.R SCE.rds APPDIR
suppressPackageStartupMessages({library(ShinyCell); library(SingleCellExperiment)})
args <- commandArgs(trailingOnly = TRUE)
sce <- readRDS(args[1])
conf <- createConfig(sce)
conf <- modDefault(conf, "cell_line_id", "cell_line_id")
makeShinyApp(sce, conf, gene.mapping = FALSE, gex.assay = "counts", shiny.title = "ShinyCell (tool_ceiling)",
             shiny.dir = args[2], default.gene1 = "MALAT1", default.gene2 = "MALAT1", default.dimred = c("UMAP_1", "UMAP_2"))
