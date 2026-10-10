## Chunk rule check ($SCRATCH)

| dataset | chunks | role | cell row cold / warm (HTTP) | gene col cold / warm (HTTP) | row / col cold (raw zarr) | server peak RSS, MB |
|---|---|---|---|---|---|---|
| spatial-A 75k×18k | allx64 | served | 1.89 (1.87–1.92) / 0.977 | 0.148 (0.145–0.151) / 0.132 | 1.90 / 0.035 | 1052 |
| spatial-A 75k×18k | 1024x512 | RULE | 0.141 (0.137–0.153) / 0.108 | 0.250 (0.229–0.357) / 0.227 | 0.072 / 0.117 | 222 |
| spatial-A 75k×18k | 1024x1024 |  | 0.105 (0.101–0.124) / 0.078 | 0.292 (0.274–0.475) / 0.223 | 0.048 / 0.157 | 305 |
| spatial-A 75k×18k | 512x512 |  | 0.124 (0.123–0.179) / 0.108 | 0.327 (0.303–0.33) / 0.291 | 0.064 / 0.165 | 205 |
| spatial-A 75k×18k | 4096x256 |  | 0.236 (0.231–0.24) / 0.153 | 0.170 (0.168–0.272) / 0.178 | 0.180 / 0.042 | 285 |
| spatial-A 75k×18k | 256x4096 |  | 0.080 (0.0787–0.097) / 0.066 | 0.590 (0.587–0.601) / 0.516 | 0.026 / 0.396 | 297 |
| spatial-A 75k×18k | 2048x2048 |  | 0.137 (0.137–0.142) / 0.092 | 0.783 (0.318–0.791) / 0.304 | 0.068 / 0.622 | 796 |

| dataset | chunks | role | cell row cold / warm (HTTP) | gene col cold / warm (HTTP) | row / col cold (raw zarr) | server peak RSS, MB |
|---|---|---|---|---|---|---|
| scPLM 460k×34k | allx4 | served | 50.05 (50–50.1) / 14.15 | 0.847 (0.842–0.862) / 0.713 | 50.00 / 0.065 | 586 |
| scPLM 460k×34k | 2048x256 | RULE | 0.398 (0.395–0.399) / 0.193 | 1.34 (1.33–1.37) / 0.904 | 0.330 / 0.533 | 317 |
| scPLM 460k×34k | 1024x1024 |  | 0.249 (0.244–0.25) / 0.112 | 2.61 (2.58–2.62) / 1.19 | 0.165 / 1.92 | 422 |
| scPLM 460k×34k | 2048x128 |  | 0.515 (0.51–0.517) / 0.273 | 1.13 (1.13–1.14) / 0.861 | 0.415 / 0.428 | 273 |
| scPLM 460k×34k | 4096x256 |  | 0.660 (0.638–0.662) / 0.220 | 1.34 (1.32–1.34) / 0.820 | 0.606 / 0.549 | 403 |
| atlas 1.17M×12.7k | allx4 | served | 45.07 (44.9–45.1) / 11.44 | 1.76 (1.75–1.76) / 1.68 | 44.75 / 0.156 | 1164 |
| atlas 1.17M×12.7k | 8192x64 | RULE | 0.475 (0.458–0.501) / 0.219 | 1.97 (1.96–1.98) / 1.74 | 0.448 / 0.381 | 431 |
| atlas 1.17M×12.7k | 1024x1024 |  | 0.135 (0.134–0.135) / 0.066 | 5.92 (5.86–6.04) / 2.92 | 0.073 / 4.41 | 568 |
| atlas 1.17M×12.7k | 4096x64 |  | 0.389 (0.353–0.399) / 0.208 | 2.23 (2.23–2.26) / 1.84 | 0.344 / 0.562 | 383 |
| atlas 1.17M×12.7k | 8192x128 |  | 0.456 (0.452–0.497) / 0.170 | 2.23 (2.22–2.29) / 1.80 | 0.454 / 0.708 | 530 |
| atlas 1.17M×12.7k | 16384x64 |  | 0.862 (0.814–0.867) / 0.290 | 1.99 (1.97–2.01) / 1.77 | 0.895 / 0.399 | 513 |

## Dense pairwise rows ($SCRATCH)

| matrix | row chunk | values/chunk | HTTP cold / warm | raw cold / warm | payload MB | server peak RSS, MB |
|---|---|---|---|---|---|---|
| corr_20000 | 64 | 1.3e+06 | 0.106 / 0.021 | 0.028 / 0.014 | 0.43 | 91 |
| corr_30000 | 64 | 1.9e+06 | 0.119 / 0.030 | 0.037 / 0.019 | 0.67 | 98 |
| corr_30000 | 32 | 9.6e+05 | 0.111 / 0.030 | 0.028 / 0.014 | 0.67 | 91 |
| dist_100000 | 16 | 1.6e+06 | 0.181 / 0.087 | 0.041 / 0.024 | 2.19 | 104 |
| dist_100000 | 8 | 8e+05 | 0.185 / 0.086 | 0.034 / 0.019 | 2.19 | 99 |
| dist_200000 | 16 | 3.2e+06 | 0.301 / 0.173 | 0.065 / 0.041 | 4.38 | 126 |
| dist_200000 | 4 | 8e+05 | 0.280 / 0.164 | 0.041 / 0.027 | 4.38 | 106 |
| dist_200000 | 64 | 1.3e+07 | 0.416 / 0.175 | 0.163 / 0.121 | 4.38 | 175 |
| dist_50000 | 16 | 8e+05 | 0.118 / 0.046 | 0.025 / 0.014 | 1.09 | 93 |
| kernel_100000 | 16 | 1.6e+06 | 0.115 / 0.024 | 0.036 / 0.027 | 0.44 | 99 |
| kernel_200000 | 16 | 3.2e+06 | 0.238 / 0.106 | 0.061 / 0.046 | 2.19 | 116 |
| kernel_50000 | 16 | 8e+05 | 0.111 / 0.034 | 0.025 / 0.015 | 0.66 | 91 |

## Real data (HTTP), $SCRATCH vs node tmpfs

| request | $SCRATCH cold / warm | tmpfs cold / warm | payload MB |
|---|---|---|---|
| atlas-1.17M-raw:X_gene_col | 1.19 / 1.10 | 1.02 / 0.986 | 7.6 |
| atlas-1.17M-raw:cell_names | 0.993 / 0.855 | 0.912 / 0.822 | 36.2 |
| atlas-1.17M-raw:obs_col:cell_type | 0.768 / 0.154 | 0.768 / 0.149 | 12.7 |
| atlas-1.17M-scvi:X_gene_col | 1.21 / 1.23 | 1.06 / 1.03 | 9.8 |
| atlas-1.17M-scvi:cell_names | 0.991 / 0.878 | 0.900 / 0.806 | 36.2 |
| atlas-1.17M-scvi:dense_layer_cell_row:kompot_smooth_all_smoothed | 45.16 / 12.38 | 12.74 / 11.95 | 0.3 |
| atlas-1.17M-scvi:dense_layer_gene_col:kompot_smooth_all_smoothed | 1.92 / 1.85 | 1.67 / 1.62 | 26.0 |
| atlas-1.17M-scvi:obs_col:cell_type | 0.761 / 0.152 | 0.692 / 0.145 | 12.7 |
| atlas-1.17M-scvi:obs_col:kompot_da_lfc | 0.806 / 0.395 | 0.750 / 0.372 | 13.3 |
| atlas-1.17M-scvi:obsm_col:X_scVI | 1.80 / 1.61 | 1.63 / 1.46 | 25.4 |
| atlas-1.17M-scvi:obsm_col:X_umap | 1.84 / 1.65 | 1.62 / 1.44 | 24.4 |
| atlas-1.17M-scvi:obsp_csr_row:connectivities | 0.297 / 0.192 | 0.242 / 0.190 | 4.7 |
| atlas-1.17M-scvi:sparse_layer_gene_col:lognorm | 1.28 / 1.20 | 1.06 / 1.01 | 8.6 |
| scPLM:X_gene_col | 0.611 / 0.465 | 0.473 / 0.395 | 2.9 |
| scPLM:cell_names | 0.466 / 0.446 | 0.453 / 0.428 | 18.9 |
| scPLM:dense_layer_cell_row:kompot_smooth_all_smoothed | 51.05 / 15.49 | 14.61 / 13.82 | 0.7 |
| scPLM:dense_layer_gene_col:kompot_smooth_all_smoothed | 0.882 / 0.739 | 0.820 / 0.677 | 11.4 |
| scPLM:obs_col:cell_type | 0.338 / 0.073 | 0.316 / 0.074 | 4.6 |
| scPLM:obs_col:nCount_RNA | 0.270 / 0.126 | 0.254 / 0.123 | 3.6 |
| scPLM:obsm_col:X_umap | 0.833 / 0.621 | 0.771 / 0.562 | 9.7 |

## Filesystem arm, spatial-A (HTTP cold / warm)

| request | $SCRATCH | node tmpfs |
|---|---|---|
| X_gene_col | 0.125 / 0.112 | 0.100 / 0.093 |
| cell_names | 0.094 / 0.085 | 0.062 / 0.054 |
| dense_layer_cell_row:kompot_de_Xenium_smoothed | 1.84 / 1.01 | 1.04 / 0.964 |
| dense_layer_gene_col:kompot_de_Xenium_smoothed | 0.237 / 0.156 | 0.183 / 0.144 |
| obs_col:celltype | 0.114 / 0.014 | 0.075 / 0.014 |
| obsm_col:X_umap | 0.181 / 0.125 | 0.153 / 0.126 |
| obsp_dense_row:dist_spatial | 0.123 / 0.054 | 0.096 / 0.056 |
| varp_dense_row:gene_corr_pearson_lognorm | 0.055 / 0.005 | 0.035 / 0.005 |

## Concurrency, 3 workers (slowest request, median over repeats, s)

| store | N=1 | N=2 | N=4 | N=8 |
|---|---|---|---|---|
| 1024x1024_hpctemp | 0.0933 | 0.168 | 0.239 | 0.371 |
| 1024x512_hpctemp | 0.121 | 0.176 | 0.313 | 0.516 |
| allx64_hpctemp | 1.73 | 1.93 | 2.79 | 4.2 |

## $SCRATCH canary over the measurement jobs (n=29)

read p50 2.9 ms (range 2.3–6.1); p95 44 ms (max 59); max single read 68 ms; 2026-10-02T12:01:34.665-07:00 → 2026-10-03T06:15:37.295-07:00
