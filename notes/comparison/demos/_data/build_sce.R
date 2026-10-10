# Build bm_demo_sce.rds (SingleCellExperiment) from the plain files written by make_demo.py.
# Carries logcounts, colData, UMAP/PCA reducedDims, the kNN graph as colPairs, and one stored
# cell x cell row (diffusion distance to cell 4236) as a colData column, for side-by-side checks.
suppressMessages({library(SingleCellExperiment); library(Matrix); library(S4Vectors)})
setwd(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE))))
X <- as(readMM("X.mtx"), "CsparseMatrix")
obs <- read.csv("obs.csv", row.names = 1, check.names = FALSE)
var <- read.csv("var.csv", row.names = 1)
dimnames(X) <- list(rownames(var), rownames(obs))
sce <- SingleCellExperiment(assays = list(logcounts = X), colData = DataFrame(obs, check.names = FALSE))
reducedDim(sce, "UMAP") <- as.matrix(read.csv("umap.csv", row.names = 1))
reducedDim(sce, "PCA") <- as.matrix(read.csv("pca.csv", row.names = 1))
knn <- read.csv("knn_connectivities.csv")
colPair(sce, "connectivities") <- SelfHits(knn$i, knn$j, nnode = ncol(sce), x = knn$x)
sce$diffusion_distance_to_4236 <- read.csv("diffusion_distance_row_4236.csv", row.names = 1)[, 1]
saveRDS(sce, "bm_demo_sce.rds")
print(sce)
