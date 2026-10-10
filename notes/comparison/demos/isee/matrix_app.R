# iSEE matrix-mark check on bm_demo_sce.rds (8,090 cells). Usage:
#   Rscript matrix_app.R main            # preset panels (every setting is also reachable in the GUI)
#   Rscript matrix_app.R landing         # default landing page: upload an SE RDS and an initial-state RDS
#   Rscript matrix_app.R restore <rds>   # relaunch from a "Download RDS" state file
suppressMessages({library(iSEE); library(iSEEu); library(SingleCellExperiment)})
a <- commandArgs(TRUE); mode <- if (length(a)) a[1] else "main"
sce <- readRDS(file.path(Sys.getenv("DEMO_ROOT", path.expand("$DEMO_ROOT")), "_data", "bm_demo_sce.rds"))
init <- list(
  ReducedDimensionPlot(PanelId=1L, Type="UMAP", PanelWidth=4L, ColorBy="Column data",
     ColorByColumnData="highres_celltype", VisualBoxOpen=TRUE),
  ColumnDataTable(PanelId=1L, PanelWidth=4L),
  ReducedDimensionPlot(PanelId=2L, Type="UMAP", PanelWidth=4L, ColorBy="Column data",
     ColorByColumnData="highres_celltype", ColumnSelectionSource="ColumnDataTable1",
     ColumnSelectionRestrict=TRUE, SelectionBoxOpen=TRUE),
  FeatureAssayPlot(PanelId=1L, PanelWidth=4L, YAxisFeatureName="Mpo", DataBoxOpen=TRUE),
  DynamicMarkerTable(PanelId=1L, PanelWidth=8L, ColumnSelectionSource="ReducedDimensionPlot1")
)
port <- 8902
if (mode == "main") {
  app <- iSEE(sce, initial=init, appTitle="iSEE matrix check")
} else if (mode == "landing") {
  app <- iSEE(landingPage=createLandingPage(), appTitle="iSEE matrix check (landing page)")
} else {
  st <- readRDS(a[2]); message("state file entries: ", paste(names(st), collapse=", "))
  app <- iSEE(sce, initial=st$memory, appTitle="iSEE matrix check (restored)")
}
shiny::runApp(app, host="127.0.0.1", port=port, launch.browser=FALSE)
