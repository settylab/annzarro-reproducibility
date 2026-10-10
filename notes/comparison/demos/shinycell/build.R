# Build a ShinyCell app (SGDDNB/ShinyCell) from the shared bone marrow SingleCellExperiment.
suppressMessages({library(ShinyCell); library(SingleCellExperiment)})
setwd(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE))))
sce <- readRDS("../_data/bm_demo_sce.rds")
sce$fig3_diffusion_dist_to_plasma <- NULL   # keep the config small; continuous columns stay
conf <- createConfig(sce)
makeShinyApp(sce, conf, gene.mapping = FALSE, gex.assay = "logcounts",
             shiny.title = "ShinyCell: bone marrow demo", shiny.dir = "app")
