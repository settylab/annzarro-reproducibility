# The read ShinyCell's generated server.R does for one gene (app/server.R L189-191), on the bone marrow app.
suppressMessages(library(hdf5r))
inpGene <- readRDS("sc1gene.rds")
h5file <- H5File$new("sc1gexpr.h5", mode = "r")
h5data <- h5file[["grp"]][["data"]]
cat("grp/data dims (genes x cells):", h5data$dims, "| chunk dims:", h5data$chunk_dims, "\n")
cat("Mpo is gene", inpGene["Mpo"], "of", length(inpGene), "\n")
t <- system.time(val <- h5data$read(args = list(inpGene["Mpo"], quote(expr=))))
cat("h5data$read(args = list(inpGene['Mpo'], quote(expr=))):", length(val), "values in", t[["elapsed"]], "s\n")
h5file$close_all()
