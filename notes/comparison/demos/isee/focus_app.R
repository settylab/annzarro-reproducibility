# iSEE on bm_demo_sce.rds with linked panels preset (every setting here is also reachable in the GUI).
suppressMessages({library(iSEE); library(SingleCellExperiment)})
sce <- readRDS(file.path(Sys.getenv("DEMO_ROOT", path.expand("$DEMO_ROOT")), "_data", "bm_demo_sce.rds"))
init <- list(
  RowDataTable(PanelId=1L, PanelWidth=4L),
  ReducedDimensionPlot(PanelId=1L, Type="UMAP", PanelWidth=4L, ColorBy="Feature name",
     ColorByFeatureSource="RowDataTable1", VisualBoxOpen=TRUE),
  ReducedDimensionPlot(PanelId=2L, Type="PCA", PanelWidth=4L, ColorBy="Feature name",
     ColorByFeatureSource="RowDataTable1", ColumnSelectionSource="ReducedDimensionPlot1", SelectionBoxOpen=TRUE),
  ColumnDataTable(PanelId=1L, PanelWidth=4L),
  ReducedDimensionPlot(PanelId=3L, Type="UMAP", PanelWidth=4L, ColorBy="Sample name",
     ColorBySampleSource="ColumnDataTable1", VisualBoxOpen=TRUE),
  ReducedDimensionPlot(PanelId=4L, Type="UMAP", PanelWidth=4L, ColorBy="Column data",
     ColorByColumnData="diffusion_distance_to_4236")
)
app <- iSEE(sce, initial=init, appTitle="iSEE focus check")
shiny::runApp(app, host="127.0.0.1", port=8902, launch.browser=FALSE)
