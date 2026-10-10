<!-- Copy of the prompt given to the computer-use desktop session (ManiVault follow-up F1-F6 and G1, 2026-10-04). Paths are placeholders: <work dir> = the audit's working folder outside the repo (apps, data, channel folders); <paper repo> = this repository. Otherwise verbatim. -->

You are helping score the desktop app ManiVault Studio for a scientific software comparison
(the AnnZarro paper). You have computer use on this Mac. Work carefully and only inside
ManiVault Studio, Finder and TextEdit; do not change any system settings, do not install
anything, do not browse the web.

1. Open the checklist and follow it step by step, exactly:
   <paper repo>/notes/comparison/manivault_checklist.md
   (open it in TextEdit or Finder Quick Look). The app is
   <work dir>/manivault/ManiVault Studio/ManiVault Studio.app
   and the data are named in the checklist.
2. Save every screenshot into <work dir>/manivault/shots/ with the exact file name the
   checklist gives (F2 in a view for plot shots; Cmd-Shift-4, Space, click for window shots,
   then move and rename the file from the Desktop).
3. After each step, append one line to <work dir>/manivault/shots/notes.txt:
   "<step number> <file name or none>: <what you saw>". Report what actually happened, including
   failures, missing menus or options that are not there. Never guess; if unsure, say so.
4. Talking to the team: if you are stuck or a step is ambiguous, append your question to
   <work dir>/manivault/shots/QUESTIONS.md (one heading per question, with the step
   number), then wait about 2 minutes and read <work dir>/manivault/shots/ANSWERS.md for
   the reply. A comparison agent watches these files and answers there. Keep going with other
   steps while you wait if you can.
5. When all 20 steps are done (or skipped with a reason), write "DONE" as the last line of
   notes.txt, quit ManiVault Studio, and tell the user you are finished.

---
## Follow-up session (added 2026-10-04 by the comparison auditor): annotation from a selection

The first session found no way to turn a selection into a label. The Scatterplot plugin's source shows a shipped
"Clustering" toolbar action (icon: a 2x2 grid, "th-large"; ManiVaultStudio/Scatterplot a458c7b, src/ClusteringAction.cpp L12-L32,
L74-L92): "Cluster name", "Cluster color", "Add to" (target cluster dataset, with a "Create cluster dataset" button) and
"Add cluster", enabled once points are selected and a name is typed. Please check it in the app:

F1. Open ManiVault Studio, File > Open Project > <work dir>/manivault/shots/bm_demo.mv (it takes about 5 s).
F2. In the UMAP scatterplot, set the selection tool to Lasso and lasso one island of cells.
F3. Click the scatterplot toolbar icon with the 2x2 grid (it is enabled only while a selection exists; the first session
    noted "two icons whose popups did not open", this is probably one of them). A "Clustering" popup should show
    Cluster name / Cluster color / Add to / Add cluster. Window shot with the popup open: **f1_annot_clustering_popup.png**.
F4. Type the name "my_cells", set "Add to" to an existing cluster dataset (e.g. leiden) or press the create button to make
    a new cluster dataset, then press "Add cluster". Window shot of the Data properties of that cluster dataset showing
    the new cluster "my_cells" with its point count: **f2_annot_cluster_added.png**.
F5. Right-click that cluster dataset in Data hierarchy > Export > Clusters (JSON); save as
    <work dir>/manivault/shots/f3_my_cells_clusters.json. Note in notes.txt whether the file contains "my_cells".
F6. Append one line per step to shots/notes.txt as before, prefixed "F1".."F6", and write "FOLLOW-UP DONE" at the end.
    Do not save the project (keep bm_demo.mv as it was). Quit ManiVault Studio.

## Optional step G1 (only if another desktop session runs anyway; do not schedule one for this)

G1. Open ManiVault Studio, open File > Import data... so its submenu of loaders is visible, and take a window shot:
    <work dir>/manivault/shots/g1_remote_import_data_menu.png. Note in notes.txt whether any item opens a URL
    or cloud store (expected: none; all items are file loaders). Close the menu and quit without saving.
