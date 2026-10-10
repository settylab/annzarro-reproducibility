<!-- Copy of the prompt given to the computer-use desktop session (Loupe in-app validation, Part C, 2026-10-05). Paths are placeholders: <work dir> = the audit's working folder outside the repo (apps, data, channel folders); <paper repo> = this repository. Otherwise verbatim. -->

# Desktop session, Part C: Loupe Browser in-app validation (interleaved with the Loupe ladder)

You are helping score a desktop app for a scientific software comparison (the AnnZarro paper). You have
computer use on this Mac. Part C runs in Loupe Browser 9.1.0 on a small demo file and produces screenshots plus a
one-line-per-step log. A comparison agent in a terminal (the "auditor") reads them afterwards. You do the
clicking and write down what you actually see; you never guess or judge the score.

## When to run Part C (it interleaves with the Loupe ladder)

The Loupe ladder (Part B, channel `<work dir>/loupe/session_v031/`) has priority. Part C fills its
waits:

- **Run Part C steps only while the ladder is idle**: the last line of
  `<work dir>/loupe/session_v031/watcher_status.txt` says the watcher is waiting for a build
  ("waiting for <N> .cloupe build (Part C may run now)"), or the file `stop` exists there, and every
  `next_<N>_<k>` in that folder already has its `drawn_<N>_<k>` or `failed_<N>_<k>`.
- Check that folder between steps (about every step, at least every 2 minutes).
- **As soon as a new `next_<N>_<k>` appears:** finish the step you are on (save its screenshot and its
  notes line), then quit Loupe through Loupe Browser > Quit Loupe Browser and choose "Don't Save". Write a
  notes line `paused at step <s> for next_<N>_<k>`. Run that ladder size exactly as Part B says (it must
  start from a freshly opened Loupe with nothing loaded).
- **After that size's `drawn_` or `failed_` is written** and the ladder is idle again: reopen Loupe, open
  `bm_demo.cloupe` again with File > Open, write `resumed at step <s>`, and continue. If a step depends on an
  earlier one (the `lasso1` group from step 12, for example), redo the earlier step quickly first; no new
  screenshot is needed for the redone step.
- Part C is not timed and its memory is not a ceiling measurement, so pausing and resuming does no harm.

## Rules

- Use only Loupe Browser, Finder and TextEdit. Do not open or touch any other app or window, and do not
  browse the web.
- Do not change any setting (system or Loupe preferences), do not install anything, and do not force-quit or
  kill anything. Quit an app only through its own menu (Loupe Browser > Quit Loupe Browser).
- Never create an account, sign in, type a password or other credential, or accept a licence or terms. The
  operator is already signed in. If Loupe asks for any of this, stop and ask the operator (and write a
  question, see below).
- Save no Loupe file except the one copy the checklist asks for (step 16: `bm_demo_saved.cloupe` in the
  validation folder). When quitting, choose "Don't Save".
- Do not run Reanalyze or anything that downloads or uploads data. Open dialogs only to look, then Cancel.
- If something unexpected happens, or a step does not match what you see, write it down and ask (see
  "Questions"). Do not improvise around it.

## What to do

1. Read the checklist: `<paper repo>/notes/comparison/loupe_checklist.md`. It has 20
   numbered steps; each names an exact action, what to look for, and the exact screenshot file name.
2. Data: `<work dir>/loupe/validation/bm_demo.cloupe` (8,090 cells, the bone marrow demo). Open it
   with File > Open in Loupe Browser, not by double-click.
3. Screenshots go into `<paper repo>/notes/comparison/screens/loupe/` with the exact
   names from the checklist (they all contain `_APP_`). Use a window shot: Cmd-Shift-4, then Space, then click
   the Loupe window. It lands on the Desktop; move it into that folder and rename it. Check each shot shows the
   Loupe window and not the remote-control overlay. Do not overwrite or delete any existing file there (the
   `_DOCS_` files are earlier documentation shots).
4. Log: after each step, add one line to `<work dir>/loupe/validation/session_notes.txt`: step number,
   screenshot name, and what you saw (counts, exact control names, what changed and what did not). If a
   control is named differently from the checklist, write the name you saw.
5. When done (step 20), quit Loupe through its menu with "Don't Save", write `done` as the last line of
   `session_notes.txt`, and tell the operator Part C is finished.

## Questions

Channel folder: `<work dir>/loupe/validation/`.

- To ask, write `question_<n>.txt` there (n = 1, 2, ...): which step, what you see, what you need to know.
- The auditor answers in `answer_<n>.txt` in the same folder. Check for it about every minute. Do not continue
  that step until the answer arrives; you may continue with other steps that do not depend on it.

How to write a file: use your file-writing tool if you have one. Otherwise TextEdit: new document, Format >
Make Plain Text, type, File > Save into the folder with the exact name; if asked about an extension, choose
"Use .txt" or "Don't append" (both are fine).

How to read a file: your file-reading tool, or Finder (View > as List, sorted by Date Modified) and Space to
Quick Look.
