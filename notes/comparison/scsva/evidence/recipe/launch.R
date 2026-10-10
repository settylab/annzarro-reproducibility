# Launch scSVA. Host shim only: shinyFiles 0.8.0 getVolumes() on Linux calls dir_ls("/media") and
# errors when /media does not exist (as inside this sandbox), which breaks every file chooser.
# When /media is absent, getVolumes() returns just c(Computer = "/"), which is what it returns
# on a Linux host with an empty /media. scSVA's own code is not modified.
port <- as.integer(commandArgs(TRUE)[1])
suppressMessages(library(shinyFiles))
if (!dir.exists("/media")) {
  gv <- function(exclude) function() c(Computer = "/")
  for (env in list(asNamespace("shinyFiles"), as.environment("package:shinyFiles"))) {
    unlockBinding("getVolumes", env); assign("getVolumes", gv, envir = env); lockBinding("getVolumes", env)
  }
  message("host shim: /media absent, shinyFiles::getVolumes() -> c(Computer='/')")
}
# Headless host: no X11, and this R build defaults bitmapType to "Xlib", so Shiny's png() fails
# ("unable to start device PNG"; scSVA sets shiny.usecairo=FALSE). Cairo is compiled in; use it.
options(bitmapType = "cairo")
shiny::runApp(system.file("scSVA", package = "scSVA"), host = "127.0.0.1", port = port, launch.browser = FALSE)
