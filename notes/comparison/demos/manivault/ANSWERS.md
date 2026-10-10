# Answers from the comparison auditor

One heading per question, with the step number. Newest at the bottom.

## Step 6: which dimension label is cell index 4236? (answered after the session; the watcher had expired, sorry)

"4237" was correct. In ManiVault's H5AD loader, a dense 2-D obs-indexed dataset such as obsp/diffusion_distance gets 1-based dimension labels: `dimensionNames[l] = QString::number(l + 1)` (HDF5Loader 8907734, src/H5ADLoader/H5ADUtils.cpp L1303-L1306). So label "4237" is 0-based column 4236, i.e. cell Mature_Young_2#TCAATTCAGTGAGGCT-1. Note: sparse matrices in the same loader get 0-based labels (`QString::number(l)`, H5ADUtils.cpp L697-L699), so the labelling is inconsistent between dense and sparse inputs.
