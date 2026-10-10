args <- commandArgs(TRUE); snap <- args[1]
options(repos = c(CRAN = snap), Ncpus = 4)
cran <- c("reticulate","Matrix","ggplot2","Cairo","MASS","RColorBrewer","colorRamps","dichromat","viridis",
          "colourpicker","shiny","shinydashboard","shinythemes","shinyFiles","scales","sp","extrafont","plyr",
          "dplyr","ggrepel","plotly","plot3D","DT","data.table","tableHTML","future","future.apply","shinyBS",
          "shinyjqui","shinyAce","gridExtra","magick","googleComputeEngineR","BiocManager")
install.packages(cran)
BiocManager::install("rhdf5", version = "3.10", update = FALSE, ask = FALSE)
miss <- setdiff(c(cran, "rhdf5"), rownames(installed.packages()))
if (length(miss)) stop("not installed: ", paste(miss, collapse = ", "))
ip <- installed.packages(); write.csv(ip[, c("Package","Version")], "/opt/R_packages.csv", row.names = FALSE)
