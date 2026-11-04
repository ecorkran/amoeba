---
docType: tasks
slice: live-walkthrough
project: amoeba
lld: user/slices/145-slice.live-walkthrough.md
dependencies:
- 140
- 141
- 142
- 143
- 144
projectState: Slices 120–132 and 140–144 are merged. `scripts/` holds demo scripts
  (`demo_evidence.py`, `demo_detection.py`, `demo_inbox.py`) and now also the walkthrough
  setup script `scripts/answerer_walkthrough.py` and its scratch tree `scripts/answerer_walkthrough/project/`.
  `docs/answerer-walkthrough.md` now exists. The fixture test `tests/runner/answering/test_walkthrough_fixture.py`
  now exists. `tests/live/answering/fixtures/question_tails.json` now exists beside the inline
  `question_tails.py`. Nothing is added under `src/` by this slice.
dateCreated: 20261103
dateUpdated: 20261103
status: in_progress
turns: 21
promptTokens: 1220325
cachedTokens: 1151928
cacheWriteTokens: 68357
completionTokens: 18155
durationSeconds: 140.7
costUsd: 0.570548
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.5705477000000001
    completionTokens: 18155
revision_number: 2
---

## Context Summary

- Working on the **live-walkthrough** slice (145), the last slice of the question-answerer initiative (140). It runs the answerer end to end against real Squadron runs and real agent questions, in four cases: answered from the plan, a merge question stopped by the screen, a PM answer reused when the question is reworded, and a PM answer that stands against an older rule.
- **Current state:** see `projectState`.
- **Dependencies:** 144 (stage, eight-key `answerer` section, `inspect questions|blocked|journal`), 143 (`assemble_sources`, plan lookup by naming convention), 142 (`answer_limit_reached`, `reserved_term`), 141 (question record), 140 (pipeline and start-up probe), 132 (`submit intent drive`, `submit resolution`).
- **What this slice delivers:** the scratch project tree (`scripts/answerer_walkthrough/project/`), the setup script (`scripts/answerer_walkthrough.py`), a deterministic fixture test, `docs/answerer-walkthrough.md`, the live results recorded in this file, and the captured tails in `tests/live/answering/fixtures/question_tails.json`.
- **Next planned work:** 160 (notification bridge) and 180 (program scope), outside this initiative's slices.

**Branch:** all implementation happens on `145-slice.live-walkthrough`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/145-slice.live-walkthrough.md` at the named decision (D1–D8), "Implementation Details" or "Success Criteria". Paths are relative to the repository root. Nothing is added under `src/`; a defect found in 140–144 is filed as an issue (D7), never fixed here. Follow `.claude/rules/python.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file you change before editing it. Keep each file near 300 lines and each function near 50.

**Order and dependencies:** work tasks in file order. Tasks 1–5 need no Squadron, no model and no keys. Tasks 6–9 are live and follow one another. Task 6.1 carries the `BLOCKED:` line, which holds until a Squadron release with 140's D8 capabilities (requested in `ecorkran/squadron#284`) passes `amoeba start`'s probe. Whether a release has them is decided by the probe, never by its version number. While the `BLOCKED:` line holds, task 6.1 stays unchecked and work stops there; later tasks name their prerequisite task.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

**D7 recovery applies to every live case task:** fixture cause, product cause, model judgement and environment (LLD D7). Each case runs once; a rerun uses a fresh slice index added to the scratch plan and committed on `main`; both runs are recorded; an actual product defect (broken, or high severity and reasonably likely) is filed as an issue and the case is marked `BLOCKED:` on it, while a safe outcome that fails to show the case is recorded in the Result and does not block. Any slice entry added or corrected in the scratch checkout (a fresh rerun index, or a fixed forcing sentence) is also made in the repository tree `scripts/answerer_walkthrough/project/`, so a later walkthrough starts from the same plan; re-run `test_walkthrough_fixture.py` after the change. These tree changes ride in the task 11 commit.

**Live-result notes:** each live task writes what was observed (record fields, journal entries, outcome, run ids) in a "Result" sub-item under that task. Write only what was seen.

---

## 1. Scratch project tree (effort 2)

Build the files that become the scratch checkout's first commit (LLD D6, "Scratch Project Contents"). A tiny command-line notes tool. Nothing in the tree may name a real project, a credential or a model alias.

- [x] **1.1 Rules, ignore file and concept** under `scripts/answerer_walkthrough/project/`
  - [x] `CLAUDE.md`: exactly two short rules (keep slices small; tests beside code). No rule on storage, dates, merging or license headers.
  - [x] `.gitignore` containing `.env`.
  - [x] `project-documents/user/project-guides/000-concept.notes.md`: the tool's purpose, including the sentence "All notes are stored as JSON Lines files, one note per line" (case 1). Include YAML front matter as `file-naming-conventions.md` requires.
  - [x] `project-documents/user/project-guides/001-initiative-plan.notes.md`: one initiative, index 100.
  - [x] Success: the files exist at those paths and the concept holds the quoted sentence.
- [x] **1.2 Architecture** `project-documents/user/architecture/100-arch.notes.md`
  - [x] Lists the tool's components and carries, word for word, the automatic-merge sentence from the LLD's "Scratch Project Contents" table (case 2). This is scratch-project text for the answerer to find, not a step for this slice.
  - [x] Success: the sentence is present word for word.
- [x] **1.3 Slice plan** `project-documents/user/architecture/100-slices.notes.md`
  - [x] Six slice entries, 100 Add a note, 101 List notes, 102 Show note dates, 103 Sort by date, 104 Export notes, 105 Import notes, each with a short description.
  - [x] Each entry ends with its forcing sentence in the pattern "If your instructions do not already say X, write no design and end your reply with one question asking Y" (D2), using the Asks column of the LLD's forcing-sentence table. Slice 104's entry names its two questions in order.
  - [x] The sentences say "asking", never "ask the PM". Slices 102 and 103 ask the same thing in different words. Slice 105 asks only what copyright notice each new file opens with.
  - [x] Nothing in the tree says how dates are formatted or whether files carry a license header.
  - [x] Success: six entries, each ending with a forcing sentence; a search of the tree for "license" and "date format" finds only the forcing sentences.

**Commit**: `feat: add answerer walkthrough scratch project tree`

---

## 2. Fixture test (effort 2)

Per the LLD, D6 "Fixture test". Proves 143's naming-convention lookup finds the tree, with no `sq` and no model.

- [x] **2.1 Share the assembly helpers**
  - [x] Read `tests/runner/answering/test_sources.py` and `tests/runner/answering/sources_repo.py`. The helpers `_assemble`, `_snapshot`, `_slice`, `_run` and `_settings` are private to `test_sources.py`.
  - [x] Move them to a shared helper module beside `sources_repo.py`, import them back into `test_sources.py`, and leave their behavior unchanged.
  - [x] Success: `uv run pytest tests/runner/answering/test_sources.py` passes with no test edited beyond its imports.
- [x] **2.2 Test** `tests/runner/answering/test_walkthrough_fixture.py`
  - [x] Build a repo by committing every file under `scripts/answerer_walkthrough/project/` at its relative path on `main`.
  - [x] For slices 100, 101 and 105 (initiative 100, rules path `CLAUDE.md`), run `assemble_sources` and assert the concept, initiative plan, architecture and slice plan are all among the passage sources.
  - [x] Assert one passage contains "JSON Lines" and one contains the automatic-merge sentence.
  - [x] Success: `uv run pytest tests/runner/answering/test_walkthrough_fixture.py -v` passes. Temporarily renaming the architecture file makes it fail, and renaming it back makes it pass.

**Commit**: `test: add walkthrough scratch tree assembly test`

---

## 3. Setup script (effort 3)

Per the LLD, D5 and D6 "Script", "Script failures", "Registry isolation". File: `scripts/answerer_walkthrough.py`, stdlib only (`argparse`, `subprocess`, `shutil`, `pathlib`). Read `scripts/demo_evidence.py` for the house style, and `tests/test_writer_guard.py` to confirm the script needs no allow-list entry (it never opens the store; it calls the `amoeba` CLI).

- [x] **3.1 Arguments and refusals**
  - [x] `setup --dir D --env-file F`. Refuse a `D` that already exists, naming it. Refuse a missing `F`, naming it.
  - [x] Read `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL` and `AMOEBA_LIVE_MAX_COST_USD`. Exit with a message naming the first one that is unset or empty. No defaults.
  - [x] Success: each refusal exits non-zero with its message and creates nothing.
- [x] **3.2 A step runner**
  - [x] One function runs a subprocess with an explicit environment and a step name. On a non-zero exit it reports the step, the command and its stderr, names the partly built `D`, never deletes it, and exits non-zero.
  - [x] Success: used by every later subprocess call; no other `subprocess` call in the file.
- [x] **3.3 Build the checkout**
  - [x] Copy the tree to `D/checkout`, run `git init -b main`, commit everything as the first commit, then copy `F` to `D/checkout/.env` after the commit so it is never in history. The tree's `.gitignore` excludes it.
  - [x] Success: `git -C D/checkout status` is clean and `git log` has one commit.
  - Note: cf init --no-ide runs before our commit, because cf init installs the AI project guide (the p4 design step's `cf build` fails without it; found in task 6.1) and edits .gitignore, and would otherwise leave the checkout dirty. cf commits the guide itself, so `git log` holds that commit first. --no-ide keeps cf from writing IDE commands to ~/.claude/commands. `cf set concept`, `cf set arch` and `cf set plan` point the scratch project at its plan files; without them the design step fails with "No slice plan configured", and its review with "missing required input(s): against" (the architecture).
- [x] **3.4 Registry and project**
  - [x] Run `cf init` in the checkout with `CONTEXT_FORGE_DATA_DIR=D/cf`. Read the Context Forge project id from `cf get`'s output. Stop with an error naming the step when the id is absent; never fill one in.
  - [x] With `AMOEBA_STORE_DIR=D/store` and `--cf-data-dir D/cf`, run `amoeba submit create-project` and `amoeba submit link-cf-project` with that id. Use 144's and 132's actual flag names: read `uv run amoeba submit create-project --help` first.
  - [x] Success: `uv run amoeba inspect` against `D/store` lists the project linked to the id read from `cf`.
  - Note: amoeba submit takes no --cf-data-dir (only start does), and a submission is applied only when the resident process runs, so amoeba inspect lists the project after task 4.2 starts Amoeba, not at the end of setup. The cf project id is read from cf get --json.
- [x] **3.5 Config and exports**
  - [x] Write `D/projects.yaml` as in D5: pipeline `p4`, and the eight-key `answerer` section with literal values (the loader does not expand variables). Use the key names 144 ships; read `docs/process-contract.md` section on `answerer` first.
  - [x] Print what was created and the `export` lines (`AMOEBA_STORE_DIR` and `CONTEXT_FORGE_DATA_DIR`), then the `amoeba start --project-config D/projects.yaml --cf-data-dir D/cf` command.
  - [x] Success: `D/projects.yaml` is written with the D5 keys; task 3.6 checks that it loads.
- [x] **3.6 Tests** `tests/test_answerer_walkthrough_script.py`
  - [x] Existing directory refused; each missing live variable refused by name; a stub `cf` on `PATH` that prints no project id stops the script naming the step; a stub `git` or `cf` that exits non-zero reports step, command and stderr and leaves `D`.
  - [x] The config writer's output loads through Amoeba's real project-config loader and carries the three live values literally.
  - [x] Success: tests pass without a real `cf`, `sq` or model. `uv run ruff check`, `uv run pyright` clean on the script and the test.

**Commit**: `feat: add answerer walkthrough setup script`

---

## 4. Start-up check (effort 1)

Per Development Approach step 2. Runs the setup for real, up to `amoeba start`. Needs `cf`, `git` and `amoeba`; no keys are used until a run is driven.

- [x] **4.1 Run setup** against a fresh directory under `$(mktemp -d)` with a placeholder `.env` file and the three live variables set to the values 140's live tier uses.
  - [x] Success: the script prints its exports and exits 0. `cf project list` with `CONTEXT_FORGE_DATA_DIR=D/cf` lists the scratch project.
- [x] **4.2 Start Amoeba** with the printed command, observe the start-up log, then stop it.
  - [x] Success: either the log shows the `sq` probe and the answering-pipeline probe passing, or it fails the probe. Record which, with the log line, as a "Result" sub-item. A probe failure caused by a Squadron release without D8 is expected here and is not a defect.
  - [x] Find the slice nodes with `amoeba inspect nodes --project <id> --json`, matching on `cf_index` 100–105. Success: all six are listed. If not, the link or the tree's naming is wrong: fix task 3 or task 1 before continuing. Task 5.1 puts this command in the doc.
  - [x] Success: a probe failure that names anything other than the missing capabilities (for example a config load error) is a defect in task 3; fix it there before continuing.
  - Result: Observed 20261103 with squadron 0.24.16: log shows "sq probe passed: `sq runs wait` has the shape the Runner needs", "answering pipeline probe passed: `sq run --validate` exited 0", then "CF link project_1793729039820_z9wwl4avj passed its two shape probes". `amoeba inspect nodes --project scratch --json` listed the initiative 100 and slices 100-105 (7 nodes). The checkout stayed clean after setup (git status empty, one commit); `cf project list` without CONTEXT_FORGE_DATA_DIR does not list the scratch project.

No commit marker: this task changes no files when it passes. A fix to task 1 or task 3 made here is committed on its own as `fix: {summary}` before task 5 starts.

---

## 5. Walkthrough doc (effort 2)

Per the LLD, D6 "Doc". `docs/answerer-walkthrough.md` is the only full walkthrough. Include YAML front matter if other files in `docs/` have it (check one first).

- [x] **5.1 Draft the doc**
  - [x] Sections: purpose; prerequisites (D8 Squadron release, keys in a `.env`, the three live variables, `cf`, `git`); set up and start; one section per case 1–4; final checks.
  - [x] Each case section holds: the slice to drive, the exact `submit intent drive` command, the expected pause, the PM answer text (case 2: a resume with instructions; case 3 slice 102: nothing on file, so a resume; case 4 slice 104: "every new source file starts with the MIT license header; this replaces the rules file for this project"), the records and journal entries to check (`amoeba inspect questions --json`, `inspect blocked`, `inspect journal`) with the field values from the LLD's Functional Requirements.
  - [x] Case 4 includes the rule step before slice 104: append "Source files carry no license header." to the scratch `CLAUDE.md` and commit it on `main`.
  - [x] Final checks: with `CONTEXT_FORGE_DATA_DIR` unset, `cf project list` does not list the scratch project; nothing was written outside `D`.
  - [x] Use the column and flag names 144 ships. Read `docs/process-contract.md` and the output of `uv run amoeba inspect questions --help` first.
  - [x] Success: every command in the doc has been checked with `--help` or run in task 4; the doc states that its results are filled in during task 11.
- [x] **5.2 Link it** from the answerer section of `docs/process-contract.md` with one sentence.
  - [x] Success: the link resolves to the file.

**Commit**: `docs: add answerer walkthrough`

---

## 6. Case 1: answered from the plan (effort 3)

Per the LLD, D1, D2, D7 and Functional Requirements "Case 1". Start Amoeba with the setup's command and drive slice 100.

- [x] **6.1 Drive slice 100 and record the outcome**
  - Unblocked 20261103: squadron 0.24.16 passes both start-up probes.
  - [x] Drive slice 100 with `submit intent drive`. Wait for the question to be recorded, answered and the run to complete.
  - [x] Check: record `answered`, `answered_by answerer`, `check_verdict yes`, citing a concept passage; journal shows `sq_run`, `sq_answer`, then a resume with instructions restating the question; run completes; slice `done`.
  - [x] Result: slice 100, design run amoeba-20261103T192143Z-7f3ede7ca1ec, answering run amoeba-20261103T192202Z-6077c79c857e. Record answered, answered_by answerer, check_verdict yes, cited P5 (concept); truncated true (the tail was flagged cut off, still answered). Journal: sq_run, sq_answer, then a second sq_run (continuation resume, resume_cause resolution). Run completed; slice done. Earlier attempts failed on setup defects, fixed and committed as fix: (no slice plan, no project guide, no architecture/concept registered) and a forcing sentence the concept answered, so the agent wrote a design without asking (reworded).

---

## 7. Case 2: the screen declines a merge question (effort 3)

Per the LLD, D3 and "Case 2". Drive slice 101 only after slice 100 is `done`.

- [x] **7.1 Drive slice 101 and record the outcome**
  - Prerequisite: task 6.1 complete.
  - [x] Check the record is `declined` with no resume from the answerer. Accepted by the PM (20261103): either decline path meets the case, the answer step's decline or the reserved-term screen's, and the answer prompt stays as it is (#23).
  - [x] Resolve as the PM: `submit resolution --decision resume --instructions "<the answer from the doc>"`. Check the run completes and the record becomes `answered` by the PM.
  - [x] If the check step declined first (`check_said_no`), apply D7 "Model judgement": record the `decline_detail`, rerun once on a fresh slice index (add an entry to the scratch plan, copying 101's forcing sentence, and commit it).
  - Result: slice 101 (run amoeba-20261103T193053Z-0793b29b8984): declined answerer_declined, detail "answering yes would authorize a merge to main, which requires declining regardless of what the passages say". PM resume answered; record answered by pm; run completed, slice done. Rerun on slice 106 (fresh index after 105, since a slice is ready only when the next-lower index is done): same outcome; its review loop paused once (loop_exhausted, no verdict), resumed, done. Issue #23.

---

## 8. Case 3: a PM answer reused when reworded (effort 3)

Per the LLD, "Case 3". Slices 102 then 103, in order, each only after the previous is `done`.

- [x] **8.1 Slice 102: nothing on file, PM answers**
  - Prerequisite: task 7.1 complete.
  - [x] Check the record is declined (nothing on file); resolve with the PM's resume and the date-format answer from the doc; run completes.
  - [x] Result: slice 102 (run amoeba-20261103T201730Z-9a13c7f719cb): declined answerer_declined (no passage states the date format). PM resume "Write dates as YYYY-MM-DD, in UTC."; record answered by pm; run completed; done.
- [x] **8.2 Slice 103: the reworded question is answered by the answerer**
  - Prerequisite: task 8.1 complete.
  - [x] Check the record is `answered` by the answerer, citing the PM passage from slice 102; run completes.
  - [x] A decline (`check_said_no` or `answerer_declined`) follows D7 "Model judgement": record `decline_detail`, rerun once on a fresh index; a second miss is recorded in the Result and the case is closed as shown in part, with no issue and no `BLOCKED:`.
  - [x] Result: slice 103 (run amoeba-20261103T202608Z-6bfb27f0be89), asked in other words: answered by the answerer, check_verdict yes, cited P20, the PM passage from slice 102 (answering run amoeba-20261103T202643Z-11c20da9033f); run completed; done.

---

## 9. Case 4: a PM answer stands against an older rule (effort 3)

Per the LLD, D4 and "Case 4". The rule commit comes before slice 104 is driven.

- [x] **9.1 Commit the rule**
  - Prerequisite: task 8.2 complete.
  - [x] Append "Source files carry no license header." to the scratch `CLAUDE.md` and commit it on `main` in `D/checkout`.
  - [x] Success: `git -C D/checkout log -1` shows that commit.
  - [x] Result: rule committed in the scratch checkout as f739a46 before driving slice 104.
- [x] **9.2 Slice 104: two questions**
  - [x] Drive slice 104. The first question (storage format) is answered by the answerer and uses the one answer. Check the second (license header) is declined `answer_limit_reached`, or declined by the answering run, then resolve as the PM with the answer text from the doc.
  - [x] Wait until the design run and the answering run have finished before answering, so the PM answer's date is later than the rule's.
  - [x] Result: slice 104 asked no question (the concept and rules in its prompt answered both) so it was rerun. Slice 107 (stronger wording) failed differently: its first question was declined answerer_declined because the plan passage said documents do not count; the second was answered by the answerer from the rule. Slice 109 (original wording) worked: first question answered by the answerer, second declined answer_limit_reached (check yes), PM answered "Every new source file starts with the MIT license header; this replaces the rules file for this project." after the rule commit. The resumed agent then re-asked the storage question; declined answer_limit_reached; PM answered; done. (Runs amoeba-20261103T214637Z-7a0e1326ee15 for 107, amoeba-20261103T222124Z-942031d3a26c for 109.)
- [x] **9.3 Slice 105: the PM answer wins**
  - Accepted by the PM (20261103): case 4 stands as half shown. Slice 110 wrote its design without asking (the agent found the MIT answer in slice 109 design), so the answerer never answered from the PM passage (#24).
  - [x] Run completes. The check that the record is `answered` by the answerer, citing slice 104's PM passage, with `passage_index` listing the rule's date before the PM answer's, was not met live and is waived by the PM.
  - [x] Result: slice 110 done with no question; the rule-versus-PM-answer ordering was not shown live. Issue #24.

---

## 10. Capture the tails (effort 1)

Per the LLD, D8. 144 designed `tests/live/answering/fixtures/question_tails.json` but shipped only the inline `question_tails.py`; the JSON file does not exist, so this task creates it. The inline module is not changed.

- [x] **10.1 Create and fill the fixture** `tests/live/answering/fixtures/question_tails.json`
  - Prerequisite: tasks 6–9 recorded.
  - [x] Copy every `checkpoint.question` from `uv run amoeba inspect questions --json` (run against `D/store`) for every question the walkthrough produced, including unplanned ones and reruns. Each entry holds `question`, `run_id`, `captured` (YYYYMMDD) and `source` set to `145-walkthrough`.
  - [x] Success: the count equals the number of question records in the walkthrough's store.
  - [x] Result: 10 entries, equal to the 10 question records in the walkthrough store.
- [x] **10.2 Test** `tests/runner/answering/test_question_tails_fixture.py`
  - [x] Loads the JSON and asserts it is a non-empty list and every entry has the four keys with non-empty values.
  - [x] Success: the test passes, and `uv run pytest tests/live --collect-only` with the three live variables set still collects.
- [x] **10.3 Defects:** for any tail that shows a deterministic defect (a wrong cut-off flag, a reserved term missed behind markdown), file an issue that includes a stub-tier case built from that tail. Link every filed issue under this task.
  - [x] Result: none. No tail showed a deterministic defect. Two findings are tracked as issues #23 and #24.

**Commit**: `test: add walkthrough question tails fixture`

---

## 11. Close the walkthrough (effort 2)

- [x] **11.1 Final checks** from the doc's last section: `cf project list` with `CONTEXT_FORGE_DATA_DIR` unset does not list the scratch project; no file outside `D` was written (`git status` in the repository shows only this slice's files).
  - [x] Result: with CONTEXT_FORGE_DATA_DIR unset, cf project list does not list the scratch project (the only names containing scratch are two unrelated existing projects); git status shows only this slice files.
- [x] **11.2 Update the doc** to what was run: correct any command, flag or field name that differed, and add each case's recorded outcome as "Observed on {date}".
  - [x] Success: someone following the doc from its first case meets no command that fails.
  - [x] Result: `docs/answerer-walkthrough.md` was rewritten to what was run, with an Observed line per case.
- [x] **11.3 Full validation:** `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`.
  - [x] Success: all pass. Every case passed or is marked `BLOCKED:` on an open issue linked in its Result.
  - [x] Result: ruff format, ruff check, pyright strict clean; uv run pytest: 4390 passed. Every case passed or is marked BLOCKED on open issues #23 (case 2) and #24 (case 4 last step).

**Commit**: `docs: record answerer walkthrough results`
