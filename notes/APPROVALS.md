# Approvals and decisions

Updated 2026-10-06 14:30 PDT (coordinator). Every item of round 6 is answered and processed; nothing waits for you on this page.
Open author decisions and tasks now live in the working ledger, section M ("For Manu" and "For Dominik").

## Open

- Nothing here. Y5 (publishing the paper repo and the evidence site) stays deferred: it is ledger row M2.
- One action only you can take: V14, removing the two Linux assets from the v0.4.0 release (the agent was not permitted). Listed under "For Dominik".

## Decided in round 6 (2026-10-05 and 2026-10-06)

| ID | Decision | Outcome |
|---|---|---|
| V0 | Release v0.4.0 (you merged #81; tagged and published) | done: tag 49e2a19, PyPI 0.4.0, GitHub release |
| V1 | Paper re-targeted to v0.4.0, every AnnZarro number re-measured (yes) | done for every laptop series (f8cd6ec, 8899ff4, 75fc92c, cbdad91); HPC: J3 done, J4 and a reduced T running (ledger row A15) |
| V2 | v0.3.1 runs stopped or moved to v0.4.0 (sounds good) | done |
| V3 | Nexus J3/T on v0.4.0 (start now) | J3 done 08:09-11:41 PDT; cold = fresh server plus the node's page cache evicted; J4 on /loc/scratch and a reduced T run after the UCSC 95.6M session (passed 20:35Z) |
| V4 | Loupe calls (another desktop prompt only if needed) | none needed |
| V5 | Gene-set panel fixes, plus a real 404 or no network shown correctly | in v0.4.0; the failure messages are on the v0.4.1 branch (0da1f73) |
| V6 | 1M recolour gate resolved; fix #82 in v0.4.1 | v0.4.1 in progress |
| V7 | Smaller calls (sounds good) | done |
| V8 | Abstract: "with the default subset switched off" (yes) | done 0ce1cd2 |
| V9 | Gene-set panel fetches, computes nothing | done aea3394 (merged 26abb19) |
| V10 | Supplementary Video 1: you record a narrated demo | cited as pending; shot list notes/supplementary_video_plan.md; on your list |
| V11 | En dash and hyphen ranges compare equal (keep) | done |
| V12 | No login on the lab services; hosted instances confine paths, admins may open any path (your answer: allow admins) | v0.4.1 branch dominik/v041-paths |
| V13 | Automatic size and opacity follow the points in view (yes) | v0.4.1 in progress |
| V14 | Licence audit: option B (withdraw the Linux assets until v0.4.1) | fixes on the v0.4.1 branch (6ef36cb); the asset removal is yours |
| V15 | Ceiling rule: median of the repeats | done d899555 |
| V16 | Disclose AI assistance correctly | done c7c9ae3 (four sentences; Y6 facts applied) |
| Y1 | Correct the v0.3.1 release notes (edit) | done |
| Y2 | One release PR with the gene-set panel, docs and log-scale fix | done (#81, v0.4.0) |
| Y3 | Gene-set panel defaults, with your changes | done in v0.4.0 |
| Y4 | Connectome store: no deposit, our own download script | done |
| X9 | Measure ManiVault and Loupe in a desktop session | done |
| Y5 | Paper repo and evidence site: decide later | deferred: repo paths only in LaTeX comments (8dfe540); ledger row M2 |
| Y6 | AI-use facts (models, checks, code, data) | answered in chat and applied (c7c9ae3) |
| - | Remove TissUUmaps and napari-spatialdata (spatial-specific) | done c1e6c9d, a7d1614 (13 tools in Fig. 1c) |
| - | No claims about AnnZarro 0.1.1; no unused claims | done af8f17c, 3841a0d; ledger has no unplaced claims |
| - | Log toggle without refresh; button corners; Strong on top follows the colour bar's top | v0.4.1 branches (faf6df6/9c9b545, button corners and ordering in progress) |

<details>
<summary>Round 6 as written at the time (the item texts and your answers)</summary>

## Round 6: decided on your behalf, for review after the fact (2026-10-05, from 22:00 PDT)

You asked for the whole thing to run without prompts (the v0.4.0 release and its benchmarks, the manuscript
TODOs, the HPC worker service, the evidence site, and the paper moved to v0.4.0), with every call logged here. IDs are V0-V12 (R0-R12 until 2026-10-06; renamed to avoid clashing with rounds 1 and 4). Each
item says what was done and what I recommend. Write "rerun" or a note on its Answer line to reverse it.

### V0. DONE: AnnZarro v0.4.0 released (you merged #81; I tagged and published)
Tag v0.4.0 (object e8039c7) points to the merge commit 49e2a19; its tree bb2ace6d4f0078c41738dabd1bb6f64de15771ca equals the release candidate 3bdeb0913d7e, so every v0.4.0 benchmark run on the RC stands (manuscript-writer checks the tree before citing). Published on PyPI (0.4.0) and as a GitHub release with 8 desktop assets and SHA256SUMS; notes in `notes/release/annzarro_v0.4.0_notes.md`, tag record in `notes/sources/annzarro_v0.4.0_tag.txt`. CI green on every job; locally 1345 passed / 15 skipped.
  Answer:

### V12. Lab services on v0.4.0 (HPC worker, 2026-10-06 06:59Z)
Both lab services run v0.4.0 (tag commit 49e2a19): annzarro :8766 (46 datasets) and annzarro-xiulan :8768 (3). The A/B against v0.3.0 found every X/obs/obsm/obsp value identical, and all 13 liver-met S5 objects passed. The switch happened in a quiet window. `external_requests` stays at "ask". Rollback is one symlink plus a restart (v0.3.0 is kept). Two calls:
- Refresh is open to anonymous callers there, because those services run with login off on the internal network (unchanged). It is read-only and rate-limited, so I left it open. Say "refuse" to have the HPC worker require login for it.
- Each service now has its own ANNZARRO_HOME: a shared one let any instance's start or reset invalidate the others' ETags. The docs will recommend this.
  Answer: No login required for the HPC. Yes, the docs should not allow arbiotraty paths in publicly hosted instances and limit what the server can read (disable arbitrary fil paths by default unless run as --admin)
  > Processed: refresh stays open without login on the lab services. Restricting readable paths (no arbitrary dataset paths on hosted instances unless --admin) goes into v0.4.1 with docs.

### V1. Paper re-targeted from v0.3.1 to v0.4.0: every AnnZarro number is re-measured
Your instruction. All laptop series (every cell, synthetic, subset, conf95, HTTP, performance, scale shots,
tool ceilings, beyond-budget runs) and the HPC worker runs J3/T rerun on the v0.4.0 tag. The v0.3.1 rows stay,
marked superseded, never deleted. Cost: roughly a day of laptop time plus the HPC queue.
- Done that way. Recommended: yes, since a paper must cite the version its numbers came from.
  Answer: yes

### V2. v0.3.1 runs stopped or deferred to v0.4.0
The guard-off 160M-300M and 1.25-1.5B runs (not started), the Fig. 8 screenshots, and the laptop performance
rerun (A14) all move to v0.4.0. The 95.6M HTTP reps on v0.3.1 finish as the A/B baseline for v0.4.0.
  Answer: sounds good

### V3. Nexus J3/T repinned to v0.4.0 if not started; else the v0.3.1 run is kept as a baseline and both rerun
  Answer: should be started now, right?
  > Processed: J3 has run on v0.4.0 since 08:09 PDT 2026-10-06 (hpc-node-27); T starts after the UCSC 95.6M session. Cold now means node-cold, with stores on /loc/scratch.

### V4. Loupe Browser 9.1.0 calls (measured in the desktop session)
- "every cell drawn" scored Y on what the app showed: single points at zoom, no sampling notice, and cluster
  counts summing to exactly the cell count at 8,090, 1M, 2M and 5M. Loupe reports no draw count, so this is a
  visual judgement in the competitor's favour.
- The ceiling is 5M (5.72 GiB). At 10M the window went blank when colouring by a gene, in both attempts: the
  renderer process exited at 4.03 GiB with the app at 8.2 GiB, far under the 16 GiB budget. Loupe embeds
  Electron 28.3.2 (Chromium 120). The paper says a per-renderer memory cap "would explain this, but was not
  established".
- The 20M .cloupe build was cancelled (moot after the 10M failure, and a ~100 GB build would have distorted
  the timed runs). The dgCMatrix input limit stays recorded as untested.
- Fig. 1c: a hollow, heavier-edged glyph now marks "crashed below the budget" (Kana 2M, Loupe 10M).
  Superseded 2026-10-06 (operator): no hollow glyph; a crash joins unreadable input as the triangle, "failed (crash or unreadable input)".
  AnnZarro's 160M guard refusal stays filled (a refusal, not a crash). The 10x-account clause was dropped
  (not established).
  Answer: provide me another claude app promt if any other measurments are needed
  > Processed: no further desktop measurement is needed now; if one is, a new desktop prompt comes to you.

### V5. Gene-set panel changes from your test session (in the v0.4.0 batch)
- STRING's HTTP 404 "did not find any matches" is reported as "not found", naming the species and the
  inferred one when they differ. A selected species that differs from the inferred one is warned about even
  when some genes map (a wrong species silently maps look-alike names, e.g. unc-13 to human UNC13D).
- No raw service HTML or entities on screen.
- "n not found" only in the coverage bar; its breakdown lists every missing gene (scrollable, copyable).
- Under "All categories": "FDR is corrected within each category by STRING, not across the N categories shown
  together". No pooled correction is computed, because STRING returns only the terms that pass its threshold,
  so a recomputed correction would be wrong (and the spec forbids local computation).
- "Sections n/m" updates on hide; the Links list stays hideable from the top and the bottom.
  Answer: Sounds good, make sure a real 404 or lack of network connection is also indicated correctly.
  > Processed: v0.4.1 makes a real HTTP 404 and a lost network connection show distinct, correct messages, with tests.

### V6. RESOLVED: release gate on the 1M recolour timing
The 1.64-1.73 s against 0.40-0.47 s was a measurement artefact: the batched Plotly.react made the old harness read the trace data before the draw. Timed to the draw, a 1M recolour takes about 1.6 s on both v0.3.1 and v0.4.0; the series now reports max(data, drawn). The 10M large-mode "timeout" was a bug in a copy of the harness script, not in AnnZarro (fixed eb1a2f2, a6c6e5d); paper data unaffected. The remaining ~1.3 s main-thread tail at 1M is issue settylab/annzarro#82 for v0.4.1.
  Answer: Make a PR to fix in 0.4.1.
  > Processed: #82 is fixed in the v0.4.1 PR.

### V7. Smaller calls
- `docs/_tools/BRIEF.md` (internal writers' brief with /Users paths) moves out of the public repo into this one.
- Fig. 2 is re-shot on v0.4.0 (not v0.3.1), with the status line under each plot and "Strong on top" pressed.
- One extra conf95 run at the automatic point size and opacity on v0.4.0, so Step 36 can quote the default.
- The test instance at :8786 served AnnZarro 0.1.1 for about 80 s (21:36:30-21:37:50 PDT) during a HPC worker
  worker's check of its branch guard. It was restored, and the guard now requires a descendant of v0.3.1.
- The HPC worker-managed AnnZarro service is updated to v0.4.0 after the release, per your instruction, with the
  HPC worker's rollback venv kept.
  Answer: sounds goo

### V8. Manuscript: abstract says the every-cell plot needs the subset switched off (ledger row H7)
"one plot draws all 95.6 million cells" now reads "with the default subset switched off, one plot draws all
95.6 million cells"; to stay at 250 words, "five worked examples and a walkthrough for millions of cells"
became "six worked examples" (Worked example 6 is the millions-of-cells walkthrough).
- Done that way. Recommended: yes; without it the abstract implies the default view draws every cell.
  Answer: yes

### V9. Manuscript: the gene-set panel is mentioned once; "computes nothing" stays unqualified
One sentence in Applications (gene-by-gene) with a link to docs/user-guide/gene-set. The read-only hosting and Limitations (read-only data) sentences say the panel queries outside services from the browser, never the server, after consent, sending only gene ids, the species and the gene background. Your correction (2026-10-06): the panel fetches results and computes nothing (building links isn't computation), so the Comparison, Limitations and Experimental design sentences keep "computes nothing" without an exception. The branch manuscript/v040-geneset is being revised to match (annzarro-reproducibility-d4) and lands with the v0.4.0 re-source.
  Answer: fetching is not computing (applied)

### V10. Manuscript: no supplementary videos for now (ledger row H16)
Nature Protocols encourages them for complicated steps; the online tutorial already reproduces every figure
with deep links. Recommended: defer to revision, where an editor may ask for them.
  Answer: I will record a video with an annzarro demo that I sepak on.
  > Processed: Supplementary Video 1 (your narrated AnnZarro demo) is planned; ledger row H16 updated, and the paper cites it once recorded.

### V11. Evidence check: a numeric range compares equal with an en dash or a hyphen (ledger row H4)
evidence/tools/claims.py normalises digit-dash-digit, so the prose uses en dashes (19 ranges, 9278b3e) while
claim texts and formats keep hyphens. Recommended: keep.
  Answer: keep

### V13. Paper correction: every-cell timings were at the automatic point size, not size 5 (f8cd6ec)
The every-cell runs (v0.3.0, v0.3.1 and v0.4.0) always used the app's automatic size and opacity (0.78 px and 0.16 at 95.6M). The paper said "point size 5, opacity 1". The text now says "at the automatic size and opacity" (Option F, Anticipated results, Fig. 8d caption), and the abstract's first-plot time is "about 5 to 6 s" (was 6 to 12 s). Fig. 8 panel c stays a point-size-5 zoom, because at the automatic size a zoom into 95.6M cells is almost blank (0.78 px at opacity 0.16).
Recommended product follow-up for v0.4.1: base the automatic size and opacity on the points in view, not all points drawn, so a zoom becomes readable by itself. Say "file it" and I open the issue.
  Answer: Yes, sounds good.
  > Processed: issue and fix in v0.4.1 (automatic size and opacity follow the points in view).

### V14. licence audit of v0.4.0 (MIT confirmed, one conflict in the Linux desktop app)
Your rule: MIT holds if it does not conflict with shipped software. Audit of the tag, the PyPI wheel/sdist and the published desktop assets (2026-10-06):
- Code, wheel, sdist, vendored JS/CSS/fonts, Python runtime dependencies, data (no CeNGEN-derived store shipped), paper repo fonts and evidence site: compatible with MIT.
- **Conflict:** the Linux .deb (and the AppImage from the same build) ships GNU Readline (GPL-3.0), pulled in by PyInstaller through Python's `readline` module; only `flask shell` imports it and AnnZarro never runs that. Fix: exclude `readline` in `annzarro/desktop/freeze.py`, plus a packaging test.
- **Notice obligations not met (no conflict):** the PSF licence for the bundled Python (all desktop apps); the licence texts of about 15 bundled packages and native libraries (scipy, h5py/HDF5, OpenSSL, Jinja2, PyYAML, zlib, libffi, ...); Electron/Chromium licence files in the macOS app; Plotly's bundled BSD-3/ISC/BSD-2/Zlib modules (mapbox-gl, d3, ...), whose licence file says "all MIT except ieee754" (wheel and the paper repo's plotly copy too).
- Optional: credit "CeNGEN, GPL-3.0" on the connectome screenshots.
Recommended: all fixes in one v0.4.1 bundle PR (with #82 and V13). Your call on the v0.4.0 Linux downloads meanwhile:
- [ ] A: leave them up until v0.4.1
- [x] B: remove the Linux .deb and AppImage from the v0.4.0 release now, note `pip install annzarro` for Linux, re-add in v0.4.1 (recommended)
  Answer: B
  > Processed: the fixes (readline exclusion, all notices, Plotly licences) go into the v0.4.1 PR. Removing the two Linux assets from the v0.4.0 release was refused to the agent by the permission system, so the operator removes them by hand (commands in chat); the release text gets the matching note.

### V15. Ceiling rule: a size fits only if the median of its repeats fits (d899555)
summarize.py counted a size as fitting if ANY ok repeat stayed within the budget. Scanpy lazy h5ad at 39.7M fitted in only 1 of 3 repeats (15.99 / 16.10 / 16.26 GiB). The rule is now the median of the ok repeats, for every row; the diff shows only that row moved (39.7M to 31.6M), and no claim or figure reads it. Nine competitor rows that were complete but never marked final are now final (15099fe, status only), and the four claims that read them are ok (9e221a6). Only UCSC (95.6M pending) stays provisional.
- Done that way. Recommended: yes, the stricter rule.
  Answer:

### V16. the AI-assistance paragraph points to the evidence record in rendered text
Your rule: the paper links to evidence only through source comments. The consistency audit found one exception, main.tex:111 (AI assistance): "the evidence record in the companion repository (\repo{evidence/} and \repo{notes/comparison/}) ... documents every mark, number and figure". No other rendered pointer to claim ids, the evidence site or its pages was found.
- [x] Keep it: a disclosure statement may say where the verification lives
- [ ] Drop the paths: "every number in the paper is traceable to the data in the companion repository" (recommended if the rule has no exceptions)
  Answer: Keep it: AI assistance must be disclosed correctly (operator, chat 2026-10-06).
  > Processed: the paragraph stays; d4 checks it against the journal AI-disclosure policy so that it is accurate and complete.

## Open decisions

### Y1. Correct the published v0.3.1 release notes (50M timing)?
The release notes (github.com/settylab/annzarro/releases/tag/v0.3.1, fix #79) say the first plot by gene at 50M
cells "now takes 6.6-6.7 s against 6.8-9.6 s on v0.3.0 (two runs each)". That came from the fix's own check run,
whose start and end points are not stated. The paper's harness (fresh server, browser and cold store per run,
timed from opening the page until both panels are drawn, 3 runs) gives **3.35 s on v0.3.1 against 6.22 s on
v0.3.0**, and the fix commit (adae3ef) agrees: about 2.8 s saved from 6.2 s. The notes' own "second draw cost
about 2.7 s" cannot leave 6.6 s on the same measure, so a reader comparing notes and paper gets two stories.
The paper uses the series and does not cite the notes either way.
- [x] Edit the notes to: "The first plot coloured by a gene at 50M cells now takes 3.35 s against 6.22 s on
  v0.3.0 (Tahoe-100M; per run a fresh server, browser and uncached store, timed from opening the page until
  both panels are drawn; 3 runs each)." (recommended: one public number, the one the paper reproduces)
- [ ] Leave the notes as they are
  Answer:

### Y2. How to merge the two finished AnnZarro branches (CI budget)?
Both are local, tested, not pushed. Every PR runs the full test workflow, and so does the merge to main.
- **Gene-set panel** (`dominik/gene-set-panel`, 7 commits on v0.3.1): STRING, g:Profiler, MyGene, Enrichr,
  Reactome and HPA sections, links per gene and per set, species picker, auto-update off by default with a
  stale bar. Tests: JS 559/559, browser 14/14 (all services mocked), Python 1327 passed and 1 flaky
  (`test_session_expiry`, passes alone), docs `-W` clean, desktop smoke 0 external requests. Live check on
  human (TP53) and mouse (Trp53) filled every section. Screenshots: `scratchpad/geneset/live-*.png`.
- **Paper tutorial docs** (`dominik/paper-docs-renumber`, 5 commits; the connectome section is being added):
  pages named by topic (old figN URLs redirect), new scale and procedure pages, the current four-panel
  performance figure, a "data for the views" table. The live docs still show the old numbering and the
  JSON-era performance figure until this merges.
- [ ] Docs PR now (after the v0.3.1 figures and the connectome section, about 20:30-21:00 PDT); gene-set panel
  goes into v0.4.0 (recommended: the paper links the tutorial, so it should be current; the panel is a feature)
- [x] Both together in one release PR now (one CI run, but the docs wait for your review of the panel)
- [ ] Hold both
  Answer: Also include the fix on the log-scale behaviour. And of course, extend the documentation to the new gene-set panel with screenshots etc.

### Y3. Gene-set panel defaults (taken by default; confirm or change)
The implementation used these four defaults. Each is a small change if you want it otherwise.
- [x] Genes = the rows that pass the gene table's filter (the app-wide meaning of "selection"). Clicking rows to
  select them as a second source is about 40 lines more and was left out.
  
  Not sure what you mean by clicking rows. But yes, we should select a table if available. Otherwise just state that not gene-table has been made yet and how to do it.
  
  Also note that by default we may look for a gene-id, gene-ensemble-id, gene-name, gene-symbole column in .obs, fall back to teh index, and allow the user to select here where the gene name or ids are and if this should be interpreted as ID or name.
  
  Note that StringDB (and potentially other services) has a certain max number of genes to we can query. Do not query in that case but have a button that allows the user to force a try anyway (report the error if it comes up)

- [x] Enrichment background = whole genome; the dataset's own genes is a per-section option (STRING, g:Profiler).

  This too should be selectable in the panel, however, the full list available in the data should be the default.

- [x] Species is global for the app (no per-panel override), set from the panel's picker by name or taxonomy id.

- [x] Outside services default to "ask": a one-time consent bar per service; hosted deployments can set
  `integrations.external_requests: off` (links only) or `on`. Enrichr, Reactome and HPA are opt-in, and
  Enrichr warns that the list it receives becomes publicly readable there.


  Note that this agreement is a client decision. A deep link may carry it for the specific gene selection but if a user changes the selection it has ot fall back to whatever the user has decided before. A global policy can be specified by the server config.


  Answer:

### Y4. C. elegans connectome store: licence if we deposit it
The Fig. 4d store is built by `data_prep/neuro_demo.py` from public downloads (checksums verified). Its inputs:
Varshney 2011 connectivity (CC BY), CeNGEN `cengenDataSC` (GPL-3.0), Wang 2024 (CC BY 4.0). A deposited copy
of the store would have to be GPL-3.0, unlike the CC BY Tahoe UMAP. Cook 2019 was not used (no redistribution
licence). Only matters at the Zenodo step (U1).
- [ ] Deposit the store under GPL-3.0 with the script (recommended: readers get the exact store)
- [x] Do not deposit; the docs point to the build script only
  Answer: Write our own download script that we can distribute freely if needed.

### X9 (reopened). Measure ManiVault (and Loupe) with a Claude desktop session
Your answer (2026-10-05): "provide me with the prompt I should give the claude app so it can run this interactively
and coordinate it/talk with you." So X9 is reopened: ManiVault gets measured instead of predicted. Until it runs,
the paper keeps the round-5 interim (Supp. Note 1 and Fig. 1c say "predicted over budget at 1M", 6191639).
- The desktop prompt is being prepared (ceiling-benchmarker: memory monitor attached to the app by name, the shared
  5,000-gene inputs at 0.25M/0.5M/1M, and a file channel so the desktop session and this session talk). I'll put
  its path here and in chat. The session must run while the bench lock is free (no timed queue running), which
  today means after about 01:00 PDT, or another day.
- Loupe still has the licence question (EULA s. 4.1: use only with data from 10x products). Tick one:
- [x] Loupe: include it in the same desktop session (you accept the EULA question for a scholarly comparison)
- [ ] Loupe: skip; it keeps "licence: 10x data only"
  Answer:

### Y5. Paper repository at submission: public, or deposited?
The manuscript points readers to many paths in `settylab/annzarro-reproducibility` (benchmark/..., figures/scale/...,
notes/comparison/<tool>.md, notes/sources/..., evidence/), and Code availability names that repository. It is
private today (P2: private now; bioRxiv and the evidence site on GitHub Pages later). Those paths only work for
readers if the repository is public, or a snapshot is deposited with a DOI, at submission. Otherwise every path
in the text needs rewriting.
- [ ] Make settylab/annzarro-reproducibility public at submission, and deposit a tagged snapshot on Zenodo with a DOI (recommended:
  every path in the text stays valid, and the DOI pins the exact version reviewed)
- [ ] Deposit a Zenodo snapshot only; the repository stays private (Code availability cites the DOI)
- [ ] Neither; rewrite the paths (large change)
  Answer: Mark all these references so we can decide later.
  > Processed: every reader-facing path into the paper repo is wrapped in \repo{...} (42 places) and the repo URL in
  > \paperrepo{} (manuscript session, ce70bc9). PDF unchanged; \showrepotrue highlights them. One definition change
  > turns them into links, DOI paths or rewrites once you decide. New paths from other agents use \repo{...} too.

### Y6. AI-assistance paragraph: facts only you can supply (V16 follow-up)
Answered in chat (2026-10-06) and applied:
- Models: say "Claude" (Opus 4.6 to Opus 5.5 and some Sonnet models; no version list). Policy asks for disclosure, not versions.
- Checks: D.J.O. read and edited the full text, checked the figures against the running app and real data, and worked on the code so that every figure shows real data.
- Code: D.J.O. and S.B. both used AI when coding AnnZarro, and tested and edited the code by hand.
- Confidentiality: no sensitive data was handled; no statement needed (all data in the paper are public).
- Shortened on request (chat, 2026-10-06) to four sentences; the companion-repository paths (\repo{evidence/}, \repo{notes/comparison/}) are dropped until the evidence site's publication is decided (Y5), which reverses V16's "keep it". Relink then if wanted.

## Things only you can do

- [ ] **Test instance on the HPC worker: http://hpc-demo-node:8786/** (Hutch network or VPN). Separate from the lab
  server and the benchmarks. Now AnnZarro v0.4.0 (gene-set panel, fixes), with the C. elegans connectome and bone-marrow stores. (The last smoke test, 2026-10-05 19:05 PDT, was on v0.3.1.)
- [x] **Try the gene-set panel** before it merges (done 2026-10-05; changes in V5). Say the word and I start a local session and send a
  smoke-tested link (bone-marrow store, mouse).
- [x] **Say "all browser sessions done"** when no more competitor sessions are wanted on the HPC (after UCSC 50M,
  and 95.6M if 50M passes). The HPC worker HPC re-measure T (~21-25 h, v0.3.1) starts only then.
- [x] **Look at Fig. 4d** (connectome) next to the docs' reproduction once the docs agent reports; any visible
  difference will be listed here.
- The Zenodo uploads wait for the preprint (U1, ledger row F7).

  Have the HPC worker update its annzarro and provide me the link for testing without interferring with the benchmakrs and local tests.


> **Processed 2026-10-05 18:45 PDT** (coordinator):
> - Y1 done: v0.3.1 release notes now say 3.35 s vs 6.22 s with the method named (the "2.7 s" sentence removed).
> - Y2: one v0.4.0 release PR with the gene-set panel, the paper tutorial docs, the gene-set user guide with
>   screenshots, and fixes for the log-scale limits (data units), colour bar title, scale direction, remote-recolour
>   busy state, a flaky test and plural wording (fix agent, branch dominik/v040-fixes).
> - Y3: changes dispatched to the gene-set agent: auto-select a gene table (or say none exists and how to make one);
>   id column auto-detected from var (gene_id, ensembl, gene_name, symbol; index fallback), user-selectable, ID vs name;
>   over a service limit no query but a "Try anyway" button reporting the error; background default = the dataset's
>   genes, genome selectable; consent stored on the client, a deep link carries consent only for its own selection,
>   server policy on top.
> - Y4: no deposit; our own download-and-build script goes into the public annzarro repo (docs agent); private-repo
>   paths removed from the docs.
> - X9: ManiVault and Loupe both measured in the desktop session; prompt gets an operator-only Part B0 (install Loupe
>   with your 10x account, accept LoupeR's EULA yourself); interim paper wording "not measured yet" for both.
> - "All browser sessions done": the HPC worker starts T automatically after J3 and the UCSC rungs.
> - Test instance: the HPC worker serves a separate AnnZarro instance (not :8766, not the benchmark nodes or stores), v0.3.1 now
>   and the v0.4.0 branch when ready; link follows here.

## Reviews coming (not ready yet; I'll link them here)

State 2026-10-06 09:00 PDT. Everything below runs on v0.4.0 (RC tree = tag tree).

| What | From | Status |
|---|---|---|
| Fig. 8 (scale) series: every cell, ceiling, guard, subset, conf95, conf95 automatic, HTTP (7 stores x 3) | scale-benchmarker | committed (369d261) |
| Fig. 8 screenshots 8a-d | scale-benchmarker, manuscript-writer | taken; committed with the re-source because two claims move (6.4-7.5 s to 6.3-7.7 s; 7.2 s to 7.3 s) |
| conf95 by category, first plot: 6.22 s on v0.4.0 vs 4.88 s on v0.3.1 | scale-benchmarker | regression check (interleaved cold reps); not cited until explained |
| Fig. 9 (performance) panels b-d, laptop | scale-benchmarker | resumed after a crash on a missing 300k store (0b1a5db); running |
| Tool ceilings past the budgets; 1B timing and subset-request profiles | ceiling-benchmarker | ladder done to 1.5B; profiles and commit pending |
| UCSC Cell Browser 95.6M (Fig. 1c) | HPC worker, ceiling-benchmarker | build running (job 10098747); session after it |
| Fig. 9 HPC series: HPC worker J3 (10100751) then T (10100753) | HPC worker, then manuscript-writer | queued behind the UCSC build to keep the shared filer quiet |
| Paper re-source to v0.4.0: claims, Fig. 1c, Fig. 8, version text, gene-set wording (V9), evidence site superseded flip | manuscript-writer | after the data above; one commit |
| Docs PR: analyst workflow (Jupyter edits plus one refresh), one ANNZARRO_HOME per service | coordinator | branch dominik/docs-analyst-workflow pushed; PR after the re-source |

</details>

## Decided in round 5 (2026-10-05)

| ID | Decision | Going to |
|---|---|---|
| J3 | Idle window approved: J3 (job 10093086, v0.3.1; resubmitted, earlier ids 10071033 and 10093065 cancelled) runs right after the UCSC 50M session (or right after a failed 50M build); 95.6M waits; results copied off $SCRATCH | HPC worker |
| X9 | Interim: per-tool reasons in Supp. Note 1 and Fig. 1c (6191639); reopened above: ManiVault to be measured in a desktop session | open |
| Z1 | Fig. 1c: no arrows on documented-size diamonds; "more than" explained once in Supp. Note 1 (7f54785) | done |
| Z2 | Supplementary Fig. S1 (JSON vs binary) dropped (d6f84fe); Fig. 9 b-d re-measured on v0.3.1 binary | done; reruns queued |
| Z3 | Procedure flowchart added as Fig. 3; later figures renumbered; site and docs take numbers from labels | done |
| Z4 | Every AnnZarro number re-measured on v0.3.1 | all agents |
| Z5 | Data preparation is not measured for any tool; 32 GiB server budget for all servers; laptop cap 85 GiB | done |
| Z6 | Tahoe-100M cited as the Cell paper (230c002, a890789) | done |
| Z7 | Neuron connectome as Fig. 4d (c3f8fa6); docs reproduce it | manuscript session, docs agent |
| Z8 | Claim entries are edited only by manuscript-writer; the manuscript session sends .tex patches with claim mappings | all |
| Z9 | Evidence site: claims searchable by ID and linked to the chart that shows them; guard refusal explained | evidence-curator |

## Decided in round 4 (2026-10-04)

| ID | Decision | Going to |
|---|---|---|
| X8 | Subset column, stricter: only subsets that reduce what is loaded and drawn count. Plus: symbols instead of text in the rows, e.g. a column for the max cells a tool can render and a column for automatic subsetting that enables larger datasets | comparison-auditor (marks), manuscript-writer (figure) |
| R6 | Colour performance fix dropped from v0.3.0 (12% gain only when pixel-identical); tag with fixes 1 and 3 | scale-fixes, coordinator |
| U1 | Zenodo upload and publication only with the preprint; kept in the publication to-do (ledger row F7) | you, at the preprint |
| U2 | Go for v0.3.0: merge everything and release once done | coordinator |
| R4 | Memory-guard choices kept. (Your question: the ~4.4 GB Chrome limit is the JS heap and is always enforced; "no limit" was only the optional extra cap on the whole tab, see the chat) | done |
| P9 | `dominik/scale-hpc` merged into main (9250988, a merge commit, so 09496f7 stays citable) | done |
| E1 | Per-card review marks removed; you review and send corrections as you find them | evidence-curator |

## Decided in round 3 (2026-10-04)

| ID | Decision | Going to |
|---|---|---|
| T7 | Memory guard approved after your test ("seems great"); its numbers get replaced by measurements | memory-guard |
| A1 | Login, share links and access control: the v0.4.0 plan approved ("good plan"); the session-expiry fix goes into v0.3.0 now | server-hardening |

## Decided in round 2 (2026-10-04)

| ID | Decision | Going to |
|---|---|---|
| X1 | Reading B ("can") for lazy reads and every cell drawn | manuscript-writer, evidence-curator |
| X2 | Host CELLxGENE and Cirrocumulus servers temporarily on the HPC; measure their browser side above 20M | ceiling-benchmarker drafts, coordinator sends to the HPC worker |
| X4 | Cellenics/Trailmaker: text mention | done |
| P7 | Code licence MIT (matches AnnZarro); text and figures CC BY 4.0 | evidence-curator |
| T8 | Reopened tables keep their search text | memory-guard |
| X7 | ManiVault scored by a Claude desktop session you run (prompt: `$DEMO_ROOT/manivault/DESKTOP_PROMPT.md`) | you, comparison-auditor answers its questions |
| P4 | New Zenodo record for the Tahoe UMAP; files and metadata prepared, you upload | scale-benchmarker |
| P5 | Tahoe-only HPC rerun, plus other public datasets if helpful and a synthetic arm for AnnZarro's limits | manuscript-writer drafts, coordinator sends to the HPC worker |
| P10 | Demo panel sets become "start here" deep links in the docs, with host/port instructions | subset-presets |
| I1 | Docker VM raised (33.6 GB); hard-limit check runs | ceiling-benchmarker |

## Decided in round 1 (2026-10-04)

| ID | Decision | Going to |
|---|---|---|
| T1-T6 | Interface approved for the release | bundle PR |
| R1 | Three performance fixes before tagging. "Should fast colours be marked?": no, they must look identical; tests prove pixel identity with Plotly's colours | scale-fixes |
| R2 | Stay ad-hoc signed until the Fred Hutch signature; docs explain the first launch | desktop-release |
| R3 | Large-plot threshold lowered to **1M** (several plots with hover and click fit in memory) | subset-presets; paper text by manuscript-writer |
| R5 | Tag as soon as the bundle PR is green, within a week | coordinator |
| X3 | Server-rendered marker for iSEE and ShinyCell2 | manuscript-writer, ceiling-benchmarker |
| X4 | Cellenics/Trailmaker: text mention, not tested for lack of an account | manuscript-writer |
| X5 | Matrix stays in Fig. 1; caption to the facing page if needed | manuscript-writer |
| X6 | Add Kana, napari-spatialdata, Loupe Browser as rows; SCope in the text only | manuscript-writer |
| M1 | Timing section: authors' estimates, labelled | manuscript-writer |
| M2 | Fig. 7 a-c keep point size 1 / opacity 0.2 | manuscript-writer |
| M3 | HPC: only the new version, completed on it | coordinator (HPC worker, after the tag) |
| M4 | Inter as the body font | manuscript-writer |
| P2 | Everything stays private in this repo; later bioRxiv and the evidence site on GitHub Pages | evidence-curator |
| P3 | archive.org snapshots | evidence-curator |
| P5 | No lab dataset names; public data only (follow-up above) | manuscript-writer |
| P6 | Agent names mapped to roles; one Methods sentence on AI assistance | evidence-curator |
| P7 | ~~Code GPL-3.0~~ superseded by round 2 P7 (code MIT); text and figures CC BY 4.0 | evidence-curator |
| P8 | Third-party screenshots as scholarly comparison, credited | evidence-curator |
| P9 | Old HPC branches stay out of any release | evidence-curator |
| P11 | Bone-marrow data: the existing Zenodo record (CC BY 4.0) | evidence-curator |
