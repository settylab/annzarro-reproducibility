# iSEE on the shared bone marrow SingleCellExperiment (8,090 cells). Default panel set.
suppressMessages({library(iSEE); library(SingleCellExperiment)})
sce <- readRDS("../_data/bm_demo_sce.rds")
app <- iSEE(sce, appTitle = "iSEE: bone marrow demo (annzarro_compare)")
shiny::runApp(app, host = "127.0.0.1", port = 8902, launch.browser = FALSE)
