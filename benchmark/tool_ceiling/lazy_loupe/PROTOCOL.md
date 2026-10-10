# Loupe Browser Part D: does Loupe read its files lazily? (paste this whole prompt into the Claude desktop app)

You are helping measure a desktop app for a scientific software comparison (the AnnZarro paper). You have computer
use on this Mac (user `user`). You will open two Loupe Browser files three times each, in a freshly started app each
time, and record Loupe's memory at three moments. A command-line memory monitor (memmon) does the measuring; you start
it, do the clicks, and mark the moments. Write down what you actually see; never guess or round.

## The question and the verdict rule

Two .cloupe files hold the SAME 1,000,000 cells (same cell lines, same UMAP); they differ only in genes:

| set | file | genes | stored values per cell | size |
|---|---|---|---|---|
| g200 | `$DEMO_ROOT/loupe/lazy/cloupe/tahoe_first1000000_g200.cloupe` | 200 | 101.5 | 393,358,341 B (0.366 GiB) |
| g2000 | `$DEMO_ROOT/loupe/lazy/cloupe/tahoe_first1000000_g2000.cloupe` | 2,000 | 589.0 | 2,363,578,797 B (2.201 GiB) |

If Loupe loads the whole expression matrix when it opens a file, its memory after opening grows with the file
(N, not lazy). If it reads expression on demand, its memory after opening stays flat while the file grows six-fold
(Y, lazy). In between is P (partial), reported with the numbers.

Concretely, with the median of three "opened" footprints per set (phys_footprint of Loupe's whole process tree, the
"Memory" figure of Activity Monitor), delta = median(g2000) - median(g200), and D_file = 1.835 GiB (the size
difference):
- **Y (lazy):** delta < 0.18 GiB (10% of D_file);
- **N (not lazy):** delta >= 0.92 GiB (50% of D_file);
- **P (partial):** anything else.
The readout script at the end computes this and also prints the spread between repetitions; you do not judge it yourself.

## Rules

- Use only Loupe Browser 9, Terminal, Finder and TextEdit. Do not browse the web or open other apps.
- Do not change any setting (system or Loupe preferences). Do not install anything. Do not force-quit or kill
  anything; quit Loupe only through its menu (Loupe Browser 9 > Quit) and choose "Don't Save" if asked.
- Never sign in, create an account, type a password or other credential, or accept a licence or terms. The operator
  is already signed in to Loupe. If Loupe asks for any of this, stop and ask the operator.
- Upload nothing, share nothing, save no Loupe file.
- Type the Terminal commands below exactly; do not run other commands.
- If anything differs from this prompt (a file is missing, a menu has another name, a command prints an error,
  Loupe crashes), stop and ask the operator. Do not improvise.

## Before you start (once)

1. Open Terminal (Applications > Utilities > Terminal). Check the files and tools exist, by typing:

       ls -l $DEMO_ROOT/loupe/lazy/cloupe/ benchmark/tool_ceiling/memmon.py benchmark/tool_ceiling/.venv/bin/python $DEMO_ROOT/loupe/lazy/partD_readout.py

   Expect both .cloupe files with the sizes in the table, and the three other paths. If a .cloupe file is missing,
   stop and tell the operator to rebuild it (below, "If a file is missing").
2. Make the record folder:

       mkdir -p $DEMO_ROOT/loupe/lazy/partD

3. Check Loupe's version: open Loupe Browser 9 from /Applications, then Loupe Browser 9 > About Loupe Browser. Expect
   "Version 9.1.0". Quit it (Loupe Browser 9 > Quit).
4. Open a second Terminal window (Shell > New Window). Call the first one **Terminal A** (it runs the monitor) and the
   second **Terminal B** (it marks the moments).

## One repetition (six in all, in this order: g200 r1, g2000 r1, g200 r2, g2000 r2, g200 r3, g2000 r3)

Below, replace SET with g200 or g2000 and K with 1, 2 or 3, exactly as in the order above.

1. Make sure Loupe Browser 9 is NOT running (quit it through its menu if it is). Then start Loupe Browser 9 from
   /Applications and wait for its start page with nothing loaded. Skip any tour you can skip.
2. In **Terminal A**, type (one line; it holds the machine's measurement lock and starts memmon):

       /usr/bin/lockf -k $HOME/.annzarro-screen.lock $TMPDIR/teamlead-bench/run-timed benchmark/tool_ceiling/.venv/bin/python benchmark/tool_ceiling/memmon.py --attach-name "Loupe Browser 9" --out $DEMO_ROOT/loupe/lazy/partD/SET_rK.mem.json --started-file $DEMO_ROOT/loupe/lazy/partD/SET_rK.go --until $DEMO_ROOT/loupe/lazy/partD/SET_rK.done --timeout 1700 --cap-gb 85

   It may wait (up to 30 min) while another measurement on this Mac finishes; that is normal. When it is measuring,
   the file `SET_rK.go` appears in the partD folder. Check in **Terminal B**:

       ls $DEMO_ROOT/loupe/lazy/partD/

   Do not continue until `SET_rK.go` is listed. If Terminal A prints an error or exits, stop and ask the operator.
3. In Loupe: File > Open File... and choose exactly the SET file from the table above.
4. When the plot is drawn, wait 10 seconds without touching anything, then in **Terminal B**:

       date +%s > $DEMO_ROOT/loupe/lazy/partD/SET_rK.opened

5. In the Clusters panel, select the group `cell_line_id` (it may already be selected). When the plot shows the
   cell-line colours, wait 10 seconds, then in **Terminal B**:

       date +%s > $DEMO_ROOT/loupe/lazy/partD/SET_rK.cellline

6. Click Features (left rail), type `MALAT1` in "Search genes/features" and select it. When the plot is coloured by
   MALAT1, wait 10 seconds, then in **Terminal B**:

       date +%s > $DEMO_ROOT/loupe/lazy/partD/SET_rK.gene

7. Save a screenshot of the whole screen, in **Terminal B**:

       screencapture -x $DEMO_ROOT/loupe/lazy/partD/SET_rK_gene.png

   If macOS asks to allow Terminal to record the screen, do not change the setting; ask the operator.
8. Stop the monitor, in **Terminal B**:

       touch $DEMO_ROOT/loupe/lazy/partD/SET_rK.done

   Terminal A then finishes and returns to its prompt. If it shows an error, stop and ask the operator.
9. Quit Loupe (Loupe Browser 9 > Quit; Don't Save if asked).
10. Add this repetition's block to the record (below), then go to the next repetition.

If Loupe crashes or stays blank for more than 3 minutes: note it in the record (what you saw, at which step),
`touch .../SET_rK.done` in Terminal B, quit Loupe through its menu if it still responds, and ask the operator whether
to repeat.

## The record

Write it with TextEdit (Format > Make Plain Text) as `$DEMO_ROOT/loupe/lazy/partD/record.txt`,
one block per repetition, exactly in this form:

    set=SET rep=K
    loupe_version=9.1.0
    opened_after_s=<seconds from File > Open until the plot was drawn>
    cellline_after_s=<seconds from selecting cell_line_id until coloured>
    gene_after_s=<seconds from selecting MALAT1 until coloured>
    points_seen=<total cells Loupe shows, e.g. the sum of the cell_line_id cluster counts, or "not shown">
    odd=<anything unexpected, or "none">

## At the end

1. In **Terminal B**, run the readout (it only reads the files and prints a table and the verdict):

       benchmark/tool_ceiling/.venv/bin/python $DEMO_ROOT/loupe/lazy/partD_readout.py > $DEMO_ROOT/loupe/lazy/partD/readout.txt; cat $DEMO_ROOT/loupe/lazy/partD/readout.txt

2. Tell the operator: the readout table and its verdict line, the record, and anything odd. Everything is in
   `$DEMO_ROOT/loupe/lazy/partD/`.

## If Terminal or memmon cannot be used (fallback, only if the operator says so)

Use Activity Monitor (Applications > Utilities), Memory tab, View > All Processes, search "Loupe". At each moment
(steps 4-6) take a screenshot showing every process whose name starts with "Loupe Browser 9" (the app and its
Helper processes, e.g. "Loupe Browser 9 Helper (Renderer)", "(GPU)") and note each one's "Memory" value; the
footprint is their sum. Save the screenshots as `SET_rK_opened.png`, `_cellline.png`, `_gene.png` in the partD folder
and add `opened_mem=`, `cellline_mem=`, `gene_mem=` lines (the sums, with units) to each record block. The verdict
rule is the same, applied by the operator.

## If a file is missing (for the operator, not for Claude)

The inputs are built from `$DEMO_ROOT/loupe/lazy/tahoe_first1000000_{g200,g2000}.h5ad` (both
present) with ceiling-benchmarker's LoupeR script:

    cd $DEMO_ROOT/loupe && $DEMO_ROOT/_mamba/envs/loupe/bin/Rscript benchmark/tool_ceiling/loupe_build.R $DEMO_ROOT/loupe/lazy/tahoe_first1000000_SET.h5ad $DEMO_ROOT/loupe/lazy/cloupe tahoe_first1000000_SET

(about 3 min for g200 and 11 min for g2000, peak 2.3 and 11.6 GB). If an .h5ad is missing too, it is rebuilt by
`benchmark/tool_ceiling/.venv/bin/python $TMPDIR/compare-audit-loupe-lazy/notes/comparison/demos/loupe/lazy_inputs.py 1000000 $DEMO_ROOT/loupe/lazy`
(it reads the 50M Tahoe master in $DATA_ROOT/tahoe_scale/work50 and needs $DEMO_ROOT/loupe/lazy/master_genes.tsv, present).
