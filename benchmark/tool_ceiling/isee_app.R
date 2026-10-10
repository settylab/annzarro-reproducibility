#!/usr/bin/env Rscript
# iSEE on a SingleCellExperiment .rds: one full-width ReducedDimensionPlot of
# the UMAP coloured by cell_line_id (Downsample off, iSEE's default: every cell
# drawn). web_task.py then switches the colour to the gene in the running app.
# Usage: isee_app.R SCE.rds PORT
suppressPackageStartupMessages({library(iSEE); library(SingleCellExperiment)})
args <- commandArgs(trailingOnly = TRUE)
sce <- readRDS(args[1])
p <- ReducedDimensionPlot(Type = "UMAP", ColorBy = "Column data", ColorByColumnData = "cell_line_id",
                          PanelWidth = 12L, Downsample = FALSE)
app <- iSEE(sce, initial = list(p), appTitle = "iSEE (tool_ceiling)")
shiny::runApp(app, host = "127.0.0.1", port = as.integer(args[2]), launch.browser = FALSE)
