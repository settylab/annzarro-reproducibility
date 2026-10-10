# scSVA server-side path, without the browser (HPC probe for the larger rungs).
# Each step is the call scSVA's server.R makes for the same UI action (line refs: c9e8fd6):
#   load XY        server.R L292-294   vaex$from_arrays(x=numpy$array(h5read(f,"/X"))); add_column('y', ...)
#   load groups    server.R L384       ds$add_column('clusters', numpy$array(h5read(f,"/clusters")))
#   choose gene    server.R L551-556   ds$add_column('Gene', numpy$array(h5read(f, "<gene>")))   (h5_type "G")
#   density view   server.R L653-656   ds$count(binby=(x,y), limits, shape=(grid,grid)) -> dgTMatrix summary
#   gene view      server.R L659-668   + ds$mean('Gene', binby=(x,y), ...)
#   groups view    server.R L690-709   for l in 1:K: ds$select("clusters==l"); ds$count('clusters', selection=T, binby=...)
#   ggplot render  server.R L736ff     ggplot(bin table) + geom_point, drawn to a PNG with the size Shiny uses
# Usage: Rscript backend_probe.R INPUTDIR GENE OUTJSON [GRID]
args <- commandArgs(TRUE); IN <- args[1]; GENE <- args[2]; OUT <- args[3]
GRID <- if (length(args) >= 4) as.integer(args[4]) else 512L   # the 2D slider's default (ui.R L117-121)
suppressMessages({library(reticulate); library(rhdf5); library(Matrix); library(ggplot2)})
reticulate::use_python(Sys.getenv("RETICULATE_PYTHON"), required = TRUE)
vaex <- import("vaex", convert = FALSE); numpy <- import("numpy", convert = FALSE)
T <- list(); tic <- function() proc.time()[["elapsed"]]
step <- function(name, expr) { t0 <- tic(); force(expr); T[[name]] <<- round(tic() - t0, 2); cat(name, T[[name]], "s\n") }
rss_gb <- function() { s <- readLines("/proc/self/status"); v <- as.numeric(sub("[^0-9]*([0-9]+).*", "\\1", grep("^VmRSS", s, value = TRUE))); round(v / 1024^2, 3) }
M <- list()
step("load_xy", { ds <- vaex$from_arrays(x = numpy$array(h5read(file.path(IN, "coords.h5"), "/X")))
                  ds$add_column("y", data = numpy$array(h5read(file.path(IN, "coords.h5"), "/Y"))) })
M$after_xy <- rss_gb()
step("load_groups", ds$add_column("clusters", data = numpy$array(h5read(file.path(IN, "clusters.h5"), "/clusters"))))
step("load_gene", ds$add_column("Gene", data = numpy$array(h5read(file.path(IN, "genes.h5"), GENE))))
M$after_loads <- rss_gb()
N <- py_to_r(ds$count()); X <- c(py_to_r(ds$min("x")), py_to_r(ds$max("x"))); Y <- c(py_to_r(ds$min("y")), py_to_r(ds$max("y")))
lim <- tuple(tuple(X[1], X[2]), tuple(Y[1], Y[2]))
step("density_bin", { xy <- ds$count(binby = tuple(ds$x, ds$y), limits = lim, shape = tuple(GRID, GRID), selection = FALSE)
                      dens <- summary(as(py_to_r(xy), "dgTMatrix")) })
step("gene_bin", { g <- ds$mean("Gene", binby = tuple(ds$x, ds$y), limits = lim, shape = tuple(GRID, GRID), selection = FALSE)
                   gm <- summary(as(py_to_r(g), "dgTMatrix")) })
K <- py_to_r(ds$max("clusters"))
step("groups_bin", { cl <- list(); for (l in 1:K) { ds$select(paste0("clusters==", l))
                     cg <- py_to_r(ds$count("clusters", selection = TRUE, binby = tuple(ds$x, ds$y), limits = lim, shape = tuple(GRID, GRID)))
                     cl[[l]] <- cbind(summary(as(cg, "dgTMatrix")), Cluster_ID = l) }; cl <- do.call(rbind, cl) })
step("render_png", { png(tempfile(fileext = ".png"), width = 800, height = 700, type = "cairo")
                     print(ggplot(dens, aes(i, j, colour = log10(x))) + geom_point(size = 0.5)); dev.off() })
M$end <- rss_gb()
res <- list(n_cells = N, grid = GRID, gene = GENE, n_groups = K, bins_nonempty_density = nrow(dens),
            bins_nonempty_groups = nrow(cl), max_cells_in_one_bin = max(dens$x),
            frac_bins_with_one_cell = round(mean(dens$x == 1), 4),
            seconds = T, rss_self_gb = M, R = R.version.string,
            python = as.character(import("sys")$version), vaex = as.character(py_str(vaex$`__version__`)))
writeLines(jsonlite::toJSON(res, auto_unbox = TRUE, pretty = TRUE), OUT)
cat(readLines(OUT), sep = "\n")
