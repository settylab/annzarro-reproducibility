# SCope: does a selection or filter in one view restrict or highlight the same cells in the other linked views? (paste this whole prompt into the Claude desktop app)

You are helping check one capability of a web app for a scientific software comparison (the AnnZarro paper). You have
computer use on this Mac (user `user`). The app is SCope 1.8.2, running on this Mac in Docker at
`http://127.0.0.1:55850/`. You will drive SCope in a browser, make a lasso selection and filters, look at what the
other views do, take screenshots and write a record. Write down what you actually see; never guess, never round,
never infer from source code. If something does not work, record exactly what happened.

## The question and the verdict rule

The comparison matrix has one column, "selection or filter restricts linked views". Its definition: a selection or
filter made in one view highlights or restricts the same cells in other linked views, in the GUI. Mark for SCope:

- **Y:** you made a selection or filter in one view, in the GUI, and saw the same cells highlighted or restricted in at
  least one other view on the page (name which views, and count the cells if SCope shows a number);
- **P:** the effect appears only in part (for example the selection is made and listed but a linked view does not show
  it, or it works on one page but not another); say exactly which part;
- **N:** you made the selection or filter and no other view changed.

The earlier attempt (headless browser, public site) could not complete the lasso, so the mark is P for lack of an
observation. A mark from this run needs the observation itself: screenshots plus the numbers you read. You do not
choose the mark from what SCope's documentation or source suggests.

## Rules

- Use only the web browser (showing `http://127.0.0.1:55850/` and nothing else), the Bash tool of this app, Finder
  and TextEdit. Do not browse the web, open other sites, or open other apps. The SCope page shows an "Authenticate
  with ORCID" button and links to external sites (scope.aertslab.org, motif logos, g:Profiler): never click them.
- Do not change any setting (system or browser). Do not install anything. Do not force-quit or kill anything. Never
  sign in, create an account, type a password or accept terms.
- Upload nothing, share nothing. Do not click "Get new session", "Upload new dataset", the trash, the sitemap icon
  or the save (download) icon next to a loom in the left sidebar. Do not click the permalink icon in the top bar (it
  shortens the link through bit.ly, an outside service).
- Run commands only with this app's Bash tool. Terminal is "click" tier for computer use (typing is blocked), so do
  not type into Terminal. Write the record and the markers from Bash.
- If the browser only lets you look but not click or type (a "read" tier), or any permission prompt appears
  (screen recording, accessibility, file access): stop and tell the operator. Never change the setting yourself.
- If anything differs from this prompt (a command prints an error, a menu has another name, the browser crashes,
  the page shows an error dialog), stop and ask the operator. Do not improvise around it. The SCope page keeps a
  hidden "An error occured when connecting to SCope back-end" dialog in its DOM; judge by what you can see.

## Before you start (once)

1. Make the folder and check the server answers (Bash tool):

       mkdir -p $DEMO_ROOT/scope/selection/shots
       curl -s -m 5 -o /dev/null -w "frontend %{http_code}\n" http://127.0.0.1:55850/
       curl -s -m 5 http://127.0.0.1:8000/echo/up; echo
       docker ps --filter name=scope-selection --format '{{.Names}} {{.Status}}'

   Expect `frontend 200`, `{"echo":"up"}` and a line `scope-selection Up ...`. If one of them fails, run the start
   script once and read its last line (it takes about 1 minute; it needs Docker Desktop running):

       $DEMO_ROOT/scope/selection/start_scope.sh

   Expect `frontend: 200  api: {"echo":"up"}`. If it still fails, or a port is reported in use, stop and ask the operator.
2. Open the browser (Google Chrome if the operator named none) in a new window and go to
   `http://127.0.0.1:55850/`. Make the window large (full screen is fine). If a cookie banner appears, click "I decline".
   The address bar changes to `.../#/<a session id>/*/welcome`. That is normal.
3. Note the browser name and version for the record (Chrome > About Google Chrome shows it; do not update anything).

## Dataset

SCope's own 100-cell test file `SCope_Test.loom` (from SCope's repository, `opt/test/data`): two embeddings
("Vertical Clusters" and "Horizontal Clusters", chosen in the left sidebar under SETTINGS > Coordinates), two
clusterings (Cluster set 0 and 1, four clusters each), one annotation ("Half cells": First half, Second half) and
eight regulons (TrackRegulon_1 to 4, MotifRegulon_1 to 4). It is small on purpose: every point is a cell and a lasso
around one dot group selects about 25 cells.

To open it: in the left sidebar click the small round arrow icon left of "Test Loom" (not its text), then click
"SCope_Test" that appears. (Clicking the text of a folder does nothing. A file "tahoe5k_selection" under
"Uncategorized" is not used here.) The page changes to the Gene page.

## Steps. Record each one in the record file (format below) as you go.

Timing: note the wall-clock time at the start and end of each step (`date +%H:%M:%S` in Bash) so the record has
seconds. Take each screenshot with this Bash command, replacing NAME (the browser must be in front and not hidden by
anything; the full screen is captured, which is fine):

    screencapture -x $DEMO_ROOT/scope/selection/shots/NAME.png

If macOS asks to allow the Bash tool or its parent to record the screen, do not change the setting; ask the operator.
Then open the PNG and look at it to check the content is what you intended (SCope's viewers are black dots on white
when no colour is chosen). If a shot shows another app or a blank page, take it again.

### S1. Load, Regulon page, nothing selected

1. In the top bar click "Regulon". You see three coloured search boxes, three histograms, and three viewers:
   "Regulon AUC values" (large, left), "Cells passing thresholds" (top right), "Expression levels" (bottom right),
   each showing the same 100 cells as three small groups of dots, plus a right panel tab "Cell selections" that says
   "No user's lasso selections".
2. Wait until the dots appear (up to 60 s the first time; the server is an emulated x86 container). Record the
   seconds. Screenshot: `s1_before_selection.png`.

### S2. Lasso in one viewer, observe the others (the main test)

1. In the narrow toolbar left of the large viewer click the lasso icon (a loop, tooltip "Lasso Tool"). It turns
   orange when active.
2. Draw a closed loop around ONE of the three dot groups (for example the left group) in the large "Regulon AUC
   values" viewer. SCope draws the lasso as you move with the left button held, and it ends when you release. With
   computer use do it as: left_mouse_down at a point beside the group, mouse_move through at least 8 points around the
   group in small steps (a rough circle, pausing a moment between moves), then left_mouse_up near the start. A straight
   `left_click_drag` only makes a line and selects nothing. Take the screenshot `s2_lasso_drawn.png` just before the
   release if the tool lets you (hold the button, capture, then release); if not, skip that shot and say so.
3. After the release, wait 5 seconds. Expected by the page's design (a prediction, not a result): the right panel
   switches to "Cell selections" and lists "Selection 1 (N cells)" with a colour chip, eye, trash and magnifier icons,
   a "Selection/Cluster Overlaps" table and a green "Download Selection 1 .loom file" button; the selected dots are
   recoloured in the large viewer and, if linked, in the two small viewers. Whether that happens is exactly what you
   are testing: write down what you see.
4. Screenshot: `s2_linked_after.png` (all three viewers and the right panel must be visible).
5. Record for each of the three viewers separately: were the same dots recoloured (yes, no, partly), how many are
   recoloured (count if you can; an estimate is acceptable only when labelled as an estimate), and the number N SCope
   prints in "Selection 1 (N cells)". Read the overlap table and copy its rows (clustering, cluster, number of cells,
   percent).
6. Hover the eye icon next to Selection 1 (tooltip "toggle show/hide selection"). Click it once. Record what changes
   in the three viewers. Screenshot: `s2_toggle_hidden.png`. Click it again and screenshot `s2_toggle_shown.png`.

### S3. Second lasso in a different viewer

1. With the lasso tool still active, draw a loop around a different dot group in the "Cells passing thresholds"
   viewer (top right). Wait 5 seconds.
2. Screenshot: `s3_second_lasso_other_viewer.png`. Record whether "Selection 2" shows its own colour in all three
   viewers, and whether the first selection is still shown.

### S4. Selection survives a page change

1. Click "Gene" in the top bar. Wait 10 seconds. The Gene page has a single viewer. Screenshot:
   `s4_gene_page_selections.png`. Record whether the selections are still drawn there and still listed under
   "Cell selections" in the right panel.
2. Click "Regulon" again and record whether both selections are still shown.

### S5. Filter route 1: regulon threshold (a filter in the histogram view)

1. On the Regulon page, click into the first (red) search box and type `TrackRegulon_1`, then click the result
   "TrackRegulon_1". A histogram appears above it and a line "AUC threshold: 0.3577 (matched points: 48 / 100)"
   (if SCope prints other numbers, record those).
2. Record how each of the three viewers changed. In "Cells passing thresholds" the cells above the threshold should
   be red and the rest grey. That would be a recolouring, not a hiding; record whether any dots disappear.
3. Screenshot: `s5_regulon_pick_threshold.png`.
4. Drag the round threshold handle on the line under the histogram to the right by about a third of the line, using
   left_mouse_down / mouse_move / left_mouse_up in small steps. Record the new "matched points" number and whether
   the red dots in "Cells passing thresholds" and in the other viewers changed accordingly. Screenshot:
   `s5_threshold_moved.png`.

### S6. Filter route 2: Compare page, annotation filter per display

1. Click "Compare" in the top bar. You see "Number of displays: 4", "Superposition: OR", "Configuration:
   drag-and-drop", an accordion item "Half cells" on the left, and four empty grey displays. (If instead it says
   "Configuration: multi-dataset" and no "Half cells" item, record that and go to S7.)
2. Click "Half cells" to expand it: it lists "First half" and "Second half". Drag "First half" into the first
   display (top left), using left_mouse_down on the item, small mouse_move steps to the display, left_mouse_up. If a
   drag does not take within three tries, record "drag-and-drop did not work with computer use (tried: ...)", skip
   the rest of S6 and go to S7.
3. Drag "First half" and "Second half" both into the third display (bottom left). Superposition OR means the union.
4. Screenshot: `s6_compare_filtered_displays.png`. Record how many dots each display shows (counts if readable;
   otherwise labelled estimates) against the 100 cells of the loom: the first display should show the first half
   only, the third all cells.
5. Click the lasso icon, draw a loop in the third display around one group of dots, release, wait 5 seconds.
   Screenshot: `s6_compare_lasso.png`. Record whether the selection is drawn in the first display for those selected
   cells that belong to the first half, and not for the others. Copy "Selection N (M cells)" from the right panel.

### S7. Selection details and saving a selection as a group

1. In the right panel under "Cell selections", the magnifier icon next to a selection ("show metadata for this
   selection") opens a view for it. Click it, screenshot `s7_selection_metadata.png`, then close it with its own close
   control. Record what it offers (for example a way to add the selection as a clustering). If a sign-in or ORCID dialog
   appears or the control asks for it, close the dialog without signing in and record "requires sign-in".
2. Do not click "Download Selection ... .loom file" and do not add a clustering.

If any step cannot be done as written (for example the lasso draws but no selection is made), record what you saw
in detail, take a screenshot named `sN_problem_<what>.png`, and continue with the next step. Do not retry more than
three times; each retry goes in the record with its outcome.

## The record

Write it from Bash (use a quoted heredoc, `cat >> file <<'EOF'`, never an unquoted one) as plain text
`$DEMO_ROOT/scope/selection/record.txt`, appending as you go. One block per step, exactly in this form:

    step=S2
    start=<HH:MM:SS> end=<HH:MM:SS> seconds=<n>
    action=<what you did, in one line>
    saw=<what each viewer showed, with counts; one line per viewer>
    screenshot=<file names in shots/>
    odd=<anything unexpected, or "none">

Start the file with:

    browser=<name and version>
    scope_url=http://127.0.0.1:55850/
    scope_version=1.8.2
    loom=SCope_Test.loom (100 cells)
    date=<output of: date>

End the file with the verdict, two lines, facts only:

    verdict=<Y or P or N>
    reason=<one sentence: which selection or filter, in which view, restricted or highlighted which cells in which other views, with the numbers read off the screen>

and one line per route:

    route_lasso=<Y/P/N and the numbers from S2, S3, S4>
    route_threshold_filter=<Y/P/N and the numbers from S5>
    route_compare_filter=<Y/P/N/not done and the numbers from S6>
    route_save_group=<what S7 offered or "not done">

## At the end

1. List the folder (`ls -l $DEMO_ROOT/scope/selection/shots`) and print the record
   (`cat $DEMO_ROOT/scope/selection/record.txt`).
2. Tell the operator: the verdict and reason, the per-route lines, and anything odd. Everything is in
   `$DEMO_ROOT/scope/selection/`. The shots are full-screen on purpose; the repository's later
   processing crops them to the browser window.
3. Leave the browser open and the server running. Do not stop the container.

## Notes for the operator, not for Claude

- Server: container `scope-selection` (image `scope:1.8.2-9ae5207-final`, the build documented in the paper's
  `benchmark/tool_ceiling/measured/scope/README.md`): frontend on 55850, API on 8000 and 55851-55853, all on 127.0.0.1.
  Data folder `$DEMO_ROOT/scope/selection/serve/` (`my-looms/SCope_Test.loom`). Restart with
  `start_scope.sh` in this folder; stop with `docker rm -f scope-selection`. The server contacts orcid.org at
  start-up and logs a harmless credential error.
- On 2026-10-09 the lasso on this local server in automated headless Chromium completed (25 cells selected, recoloured
  in all three Regulon-page viewers). The 2026-10-03 failure was on the public site. The headed run here is the
  observation the paper's mark should rest on.
- `PROMPT_earlier_draft.md` in this folder is a superseded draft that used the 5,000-cell Tahoe loom; on that loom the
  Compare page stays in "multi-dataset" mode (no annotation list), so it was dropped.
