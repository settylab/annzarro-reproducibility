<!-- Copy of the prompt given to the computer-use desktop session (ManiVault and Loupe ceiling ladders, Parts A, B0 and B, 2026-10-05). Paths are placeholders: <work dir> = the audit's working folder outside the repo (apps, data, channel folders); <paper repo> = this repository. Otherwise verbatim. -->

# Desktop session: largest dataset ManiVault Studio (and, if ticked, Loupe Browser) can draw

You are helping measure a desktop app for a scientific software comparison (the AnnZarro paper). You have
computer use on this Mac. A measuring agent in a terminal (the "watcher") records the app's memory while you
work. You and the watcher talk only through files in one folder (the "channel"). You do the clicking; the
watcher measures. Neither of you guesses: write down what you actually see.

Operator switches (the operator edits these two lines before pasting this prompt):

- [x] ManiVault Studio
- [x] Loupe Browser   (do Parts B0 and B only if this box is ticked: `[x]`)

Order: Part B0 first (with the operator, about 15 minutes), then Part A, then Part B.

## Rules

- Use only ManiVault Studio (and Loupe Browser, if ticked), Finder and TextEdit. Do not open or touch any
  other app or window, and do not browse the web. The one exception is Part B0, where you guide the
  operator through a download page and a Terminal window that the operator operates.
- Do not change any system setting, do not install anything, and do not force-quit or kill anything. The one
  exception to "install" is Loupe Browser, installed by the operator in Part B0. Quit an app only through its
  own menu (app name menu > Quit).
- Never create an account, type a password or other credential, or accept a licence. Those are the
  operator's own actions at the keyboard; you only tell them what to do and wait.
- Do not save any ManiVault project or Loupe file. Close or quit without saving whenever asked.
- If something unexpected happens, or a step does not match what you see, write what you saw into the
  channel (see "Talking to the watcher") and wait. Do not improvise around it.

## The channel

Folder: `<work dir>/manivault/session_v031/` (for Loupe: `<work dir>/loupe/session_v031/`).
Screenshots go into its `shots/` subfolder.

Files the watcher writes (you only read them):

- `next_<N>_<k>`: get ready for size N, attempt k. It holds three lines: `size=`, `attempt=`, and `file=`
  (the full path of the data file to open).
- `go_<N>_<k>`: the watcher is measuring. Import now.
- `stop`: the ladder is over. It holds the reason. Stop.

Files you write (plain text, exact names):

- `ready_<N>_<k>`: the app is freshly opened and nothing is imported yet.
- `drawn_<N>_<k>`: the plot was drawn and coloured both ways (contents below).
- `failed_<N>_<k>`: something went wrong (contents below).

How to write a channel file:

- If you have a file-writing tool, write the file directly.
- Otherwise use TextEdit:
  1. Open a new document and choose Format > Make Plain Text.
  2. Type the contents.
  3. Choose File > Save, go to the channel folder, and type the exact name (e.g. `ready_250000_1`).
  4. If asked about an extension, choose "Don't append" / "Use none". A `.txt` ending is also accepted.

How to read a channel file:

- Use your file-reading tool if you have one.
- Otherwise open the folder in Finder (View > as List, sorted by Date Modified) and press Space on a file to
  Quick Look it.
- Check for new watcher files about every 30 seconds. The watcher can take a while to answer: it waits for
  other measurements on this Mac to finish first. That is normal, so keep waiting.

N is a number of cells: 250000, 500000, 1000000, 2000000, 5000000, 10000000, and so on. k is the attempt,
1 to 3. Always use the exact N and k from the `next_` file.

## Part A: ManiVault Studio

App: `<work dir>/manivault/ManiVault Studio/ManiVault Studio.app`. This is version 1.5.0; its start
page says "ManiVault Studio 1.5.0-dev". Open it by double-click in Finder.

Things learned in an earlier session with this app:

- **Data hierarchy** is the dock with the tree of datasets. **Data properties** sits below it and shows the
  selected dataset's details.
- F2 inside a view (click the plot first, so it has keyboard focus) opens a "Save Screenshot" dialog that
  saves only that view.
- To shoot a whole window, use Cmd-Shift-4, then Space, then click the window. It saves to the Desktop; move
  the file into `shots/` and rename it. Check that each shot shows the ManiVault window and not the
  remote-control overlay.
- Quit through the menu ManiVault Studio > Quit ManiVault Studio. Cmd-Q did not always work.

For each size, repeat these steps until you find a `stop` file:

1. Wait for a `next_<N>_<k>` file. If `stop` appears instead, go to "Finishing".
2. Make sure ManiVault Studio is not running. If it is, quit it through its menu without saving.
3. Open ManiVault Studio fresh. On the start page, choose the blank project.
4. Write `ready_<N>_<k>`. Its contents can be just the time.
5. Wait for `go_<N>_<k>`. Do not import anything before it exists.
6. Import the data:
   1. Choose File > Import data... > the loader with "H5AD" in its name.
   2. Select the file named in the `file=` line of `next_<N>_<k>`.
   3. In the "Load:" dialog, leave the defaults (obs and obsm ticked) and press OK.
   4. If a "Select Dimensions" dialog with a gene list follows, accept all genes with OK. Do not untick
      anything.
   5. Note the clock time when you pressed the last OK.
7. Wait for loading to finish. The progress shows in the status bar or Data hierarchy, and the datasets appear
   in Data hierarchy. Note the clock time when it finished. Then check how it went:
   - **Error dialog:** take a window shot `shots/<N>_<k>_error.png`, then write `failed_<N>_<k>` with the
     dialog's exact text.
   - **The app disappears (crash):** write `failed_<N>_<k>` with first line `crash` and what you saw. Do not
     reopen it until the next `next_` file arrives.
   - **No visible progress for 10 minutes and the app does not respond** (spinning cursor, frozen window):
     write `failed_<N>_<k>` with first line `hang` and what you saw. Then try to quit through the menu. If the
     menu does not respond, leave the app as it is, write that too, and wait. The watcher decides what
     happens next.
   - **It is slow but still progressing:** keep waiting. Note the times.
8. In Data hierarchy, right-click `obsm/X_umap` (the UMAP dataset) > View > Scatterplot.
   - If the view opens as a narrow strip, widen it.
9. Every-cell check:
   1. Select the X_umap dataset in Data hierarchy.
   2. Read "Number of points" in Data properties, and take a window shot `shots/<N>_<k>_points.png` that
      shows it.
   3. Also read the status bar's "Number of data points", if it shows one.
10. Colour the plot by cell line:
    1. In the scatterplot toolbar, open the Datasets popup and set Color to the `cell_line_id` cluster dataset.
       It comes from obs; it may be listed as `cell_line_id` under the file's dataset.
    2. Wait until the plot recolours.
    3. Click the plot, press F2, and save `shots/<N>_<k>_cell_line_id.png`.
11. Colour the plot by gene:
    1. Open the Datasets popup and set Color to the X dataset (named after the file, e.g.
       `tahoe_first250000`).
    2. Open the Coloring popup, set Dimension to `MALAT1` (type it and pick it from the list), and press
       Return.
    3. Wait until the plot recolours.
    4. Press F2 and save `shots/<N>_<k>_MALAT1.png`.
12. Write `drawn_<N>_<k>` with these lines:

    ```
    points=<Number of points from step 9, digits only, no commas>
    statusbar_points=<from the status bar, or none>
    import_ok=<clock time of the last OK in step 6>
    loaded=<clock time loading finished>
    cell_line_id_drawn=<clock time>
    MALAT1_drawn=<clock time>
    notes=<anything unusual: warnings, slowness, missing points, dialogs>
    ```

    If a recolour never finished or failed, write `failed_<N>_<k>` instead, with what you saw, and say which
    colouring it was.
13. Quit ManiVault Studio through its menu without saving, then go back to step 1.

What `failed_<N>_<k>` contains: the first line is one word (`error`, `crash`, `hang` or `other`). The lines
after it describe what you saw, with clock times and the names of any screenshots.

The watcher ends the ladder on its own with `stop`. That happens when:

- a size fails;
- not every cell is drawn;
- the app's memory passes the 16 GiB budget;
- the machine's safety limit of 85 GiB is hit (the watcher may then close the app itself; that is expected);
- or a size hangs three times.

You do not need to judge any of this. Just follow `next_` and `stop`.

## Part B0: Loupe setup, done by the operator with your guidance (only if the Loupe box is ticked)

Do this first, before Part A. Talk the operator through it step by step, and wait for them to confirm each
step. You do not click, type into or accept anything in these steps yourself.

1. Tell the operator to:
   1. open https://www.10xgenomics.com/support/software/loupe-browser/downloads in their browser;
   2. sign in with their own 10x account;
   3. download Loupe Browser 9.1.0 for macOS (Apple Silicon, if offered), accepting the End User Software
      License there themselves;
   4. install it into /Applications by dragging the app from the disk image;
   5. eject the disk image.
2. Ask the operator to open Loupe Browser once from /Applications and confirm that it starts. If macOS asks
   to confirm opening it, the operator answers. Then ask them to quit it (Loupe Browser > Quit).
3. Tell the operator to accept LoupeR's licence:
   1. Open Terminal and type exactly:
      `<work dir>/_mamba/envs/loupe/bin/R`
   2. At the `>` prompt, type: `loupeR::setup()`
   3. R shows the 10x End User Software License (https://10xgen.com/EULA) and asks "Do you accept the
      End-User License Agreement (y/yes or n/no)". The operator reads it and answers it themselves.
   4. setup() then downloads the LoupeR converter. Wait until the `>` prompt is back.
   5. Type `q("no")` and close the Terminal window.
4. Write `loupe_ready` into `<work dir>/loupe/session_v031/`. Its contents: the time, the Loupe
   Browser version shown in its About box (if the operator checked it), and whether setup() finished
   without an error.
5. If anything in B0 fails, write `loupe_failed` with what happened instead, and go on with Part A. The
   watcher then skips Part B.

After `loupe_ready`, the watcher builds the Loupe files (.cloupe) in the background while you do Part A.
The builds never run while a ManiVault size is being measured.

## Part B: Loupe Browser (only if the Loupe box above is ticked)

Do Part B after Part A has stopped.

1. Channel: `<work dir>/loupe/session_v031/`, with the same file protocol. Start only when a
   `next_` file appears there; the watcher writes it once the Loupe files are built.
2. Data: the `file=` line points to a `.cloupe` file. Open it with File > Open in Loupe Browser, not by
   double-clicking.
3. Steps per size, the same as Part A step 1 onwards except:
   - **Open fresh:** open Loupe Browser from /Applications. Skip any sign-in or tour you can skip. If it
     insists on an account sign-in, write `failed_<N>_<k>` with `other` and stop; the operator signs in, not
     you.
   - **Every-cell check:** the total number of cells (barcodes) Loupe shows for the dataset. For example, the
     header, or the sum of the counts in the `cell_line_id` cluster list. Say where you read it, then shoot
     the window as `shots/<N>_<k>_points.png`.
   - **Colour by cell line:** select the `cell_line_id` clustering in the Clusters panel. F2 does not exist in
     Loupe, so use a window shot: `shots/<N>_<k>_cell_line_id.png`.
   - **Colour by gene:** switch to Feature/Gene Expression, search `MALAT1` and select it. Window shot:
     `shots/<N>_<k>_MALAT1.png`.
   - **Quit:** Loupe Browser > Quit, without saving any changes.
4. Write `drawn_` and `failed_` exactly as in Part A. Use `points=` for the total cell count you read.

## Finishing

1. When `stop` appears, read its reason.
2. Make sure the apps are quit without saving.
3. Write a short summary into the channel as `summary.txt`: each size, its result, and anything odd.
4. Tell the operator you are done and what the `stop` file says.

## Talking to the watcher

If you are stuck, or a step does not match what you see, write `question_<n>.txt` in the channel (n = 1, 2, ...).
Then check for `answer_<n>.txt` about every minute. Do not continue the measured step until it arrives.
