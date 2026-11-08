---
docType: tasks
slice: the-cut
project: amoeba
lld: user/slices/221-slice.the-cut.md
dependencies:
- 220-slice.code-audit
projectState: Slice 220's audit (`user/analysis/220-analysis.code-audit.md`) is the
  delete list; it must be `complete` before task 0.2 passes. `src/amoeba` holds cli,
  feed, inbox, inspection, process, program, runner, serve, store and upstream. `runner/answering/`
  holds the answering library. No command, store or tick is in use by anyone.
dateCreated: 20261107
dateUpdated: 20261108
status: complete
turns: 10
promptTokens: 375191
cachedTokens: 336092
cacheWriteTokens: 39081
completionTokens: 9539
durationSeconds: 66.0
costUsd: 0.285655
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.2856551
    completionTokens: 9539
---

# Tasks: The Cut

## Context Summary

- Working on slice 221, The Cut (design: `user/slices/221-slice.the-cut.md`; decisions D1 to D9 are cited below by number).
- The audit gives every unit a verdict. This slice deletes every `delete` and `squadron` unit, moves the `keep` and `rework` units into `src/amoeba/answering/` and `src/amoeba/upstream/`, severs them from deleted code, reworks or deletes their tests, fixes packaging, and rewrites the README.
- No new behavior. Where a sever changes a signature, the function's tests move to the new signature and keep their assertions. Do not fix bugs in kept code; file an issue under the Fixes rule.
- Where the design's predictions differ from the audit, the audit wins (D1). A changed audit row goes in the same commit as the code, with a one-line reason, and a note under the task.
- Checks, run from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" below means all four.
- Work on branch `221-slice.the-cut`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slice: 222, store config and set-up.

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 221-slice.the-cut {target}`
  - [x] Success: `git branch --show-current` prints `221-slice.the-cut`

- [x] **0.2 Confirm the audit and read it**
  - Note: Differences between the design's predictions and the audit: none new at the start. During the cut, the audit rows changed (D1) are listed in the audit's "Verdicts changed while cutting (slice 221, D1)" section and in the rows marked "Changed from rework in 221": finish.py, scripts/answerer_walkthrough.py, docs/answerer-walkthrough.md, fault_injection.py, cli_harness.py, observe_support.py, test_import_direction.py, test_migrations.py, test_paths.py, test_read_only_open.py, test_failure_modes.py, test_public_api.py, test_process_public_api.py (all rework to delete).
  - [x] Confirm `user/analysis/220-analysis.code-audit.md` exists with `status: complete`; if not, write `BLOCKED: audit 220 not complete` under this task and stop
  - [x] Read its Verdicts, Dependencies of kept code, Live tests, Move to Squadron and Differences from the architecture sections
  - [x] Compare design predictions (D2 deletions, D3 moves, D4 types, D5 settings) with the audit; list differences in a note under this task
  - [x] Success: you hold the delete list, the kept list, and every Dependencies of kept code entry

- [x] **0.3 Record the baseline**
  - Note: Baseline on untouched main: ruff format, ruff check and pyright clean; 4760 tests passed in about 6m42s. AMOEBA_LIVE_* variables are not set in the shell but .env holds them (and OPENROUTER_API_KEY); sq and cf are on PATH.
  - [x] Run the checks once on the untouched branch and note the result
  - [x] Note whether `AMOEBA_LIVE_*` variables and `sq` are available for the live tier
  - [x] Success: a baseline note exists; failures present before the cut are written down, not fixed

## 1. Leaf deletions

Delete units no kept unit depends on. A file that imports one of them is edited only if the audit keeps or reworks it (remove the import and its use, no rewiring); a file the audit marks `delete` is deleted outright.

- [x] **1.1 Delete `serve/`, `inbox/`, `feed/` and `inspection/`**
  - [x] `git rm -r` `src/amoeba/serve`, `inbox`, `feed` and `inspection`, and their tests
  - [x] Delete the rigs the audit marks `delete` for these packages (`feed_harness.py`, `inbox_harness.py`, `ingest_e2e_harness.py`, `inspection_harness.py`, `serve_harness.py`, `program_harness.py`), and drop the fixtures in `tests/conftest.py` that import them; keep the rest of that file for now (task 2.14 trims it to `reap_orphans`) (design, Audit items)
  - [x] Success: none of the four directories or their test directories remains; `tests/conftest.py` imports no deleted rig

- [x] **1.2 Delete `cli/`**
  - [x] `git rm -r src/amoeba/cli` and its tests
  - [x] Remove the `[project.scripts] amoeba` entry from `pyproject.toml` (D7)
  - [x] Success: `pyproject.toml` has no `[project.scripts]` table and no `amoeba.cli` reference remains

- [x] **1.3 Delete `runner/request_run/` and `slice_writing.yaml`**
  - [x] `git rm -r src/amoeba/runner/request_run` (includes `slice_writing.yaml`) and its tests
  - [x] Remove the `slice_writing.yaml` glob from wheel `artifacts` in `pyproject.toml`
  - [x] Success: no `request_run` or `slice_writing` path or reference remains

- [x] **1.4 Delete `tests/load/`**
  - [x] `git rm -r tests/load`; remove `--ignore=tests/load` from pytest `addopts` (D7, D8)
  - [x] Remove the "Load tests" step from `.github/workflows/ci.yml`, and the header comments that describe a separate load tier (design, Audit items)
  - [x] Success: `addopts` is `["--ignore=tests/live"]`; `tests/load` is gone; `ci.yml` has no `tests/load` reference

- [x] **1.5 Delete the audit's `delete` scripts and docs**
  - [x] Delete each file under `scripts/` and `docs/` whose audit verdict is `delete`; leave every `keep` or `rework` file
  - [x] Success: every remaining file under `scripts/` and `docs/` has a `keep` or `rework` audit row

- [x] **1.6 Verify the leaf cut**
  - Note: The leaf grep (amoeba.serve|inbox|feed|cli|inspection|request_run over src tests scripts) finds nothing. The checks could not be run green after the leaf cut alone: the delete-verdict importers (process/, runner/) went only in section 2. So section 1 and section 2 are one commit, made at the section 2 marker; no separate leaf commit exists.
  - [x] Run `git grep -nE "amoeba\.(serve|inbox|feed|cli|inspection)|request_run"` over `src tests scripts`; fix each hit as the section intro says
  - [x] Checks pass
  - [x] Success: the grep finds nothing and the checks pass

**Commit**: `chore: delete leaf packages, load tests and demo scripts`

## 2. Move, sever and delete

Checks run once, at task 2.21; do not re-point old code to keep it compiling. Take unit lists from the audit and the design's Migration Plan table, not from memory. The old code cannot compile between the moves and the deletions, so this section has one commit, after the gate. Its parts: 2.1 to 2.9 move and sever, 2.10 to 2.13 delete, 2.14 to 2.20 tests, docs, packaging and live files, 2.21 the gate.

- [x] **2.1 Delete rework units that need a later replacement (D2)**
  - Note: D2's predicted deletions held: answering/launch.py (kept passage_refs and the scratch-directory helpers), stage.py, settle.py, finish.py (whole file; row changed to delete), program/members.py. QuestionInvariantError went with finish.py/settle.py (no kept importer).
  - [x] Delete each `rework` unit whose behavior only works with a later replacement (question record, `sq` launch, store submit), with its tests, at its old path; D2 lists the predicted units, the audit decides
  - [x] For a unit with a kept half, keep that half where the audit's `rework` reason says; if it names no destination, place it in `src/amoeba/answering/` (D3)
  - [x] For each deleted unit, change its audit row to `delete` and add a line to Differences from the architecture with the reason; note it here (D1)
  - [x] Before deleting a file, relocate what kept code imports from it (the helpers listed in 2.8); do not delete a unit whose name is in the design's "Names the live tier needs" list, and keep the audit's kept halves (e.g. the scratch-preparation half of `answering/launch.py`, the kept half of `runner/launch.py`) even where D2 predicted a whole-file delete (audit wins, D1)
  - [x] Success: no stub or placeholder remains for launch, stage, settle or submit

- [x] **2.2 Move the answering library and its tests**
  - [x] `git mv` each kept module from `src/amoeba/runner/answering/` and `runner/pipeline_resource.py` to `src/amoeba/answering/` (Migration Plan table); `git mv` their tests to `tests/answering/`
  - [x] Create `src/amoeba/answering/__init__.py` re-exporting nothing (D3)
  - [x] Update imports to name the defining module; no compatibility re-exports at old paths
  - [x] Success: moved files exist only at the new paths; `git status` shows renames

- [x] **2.3 Create `answering/values.py` (D4)**
  - [x] Move unchanged from `amoeba.store`: `DeclineReason`, `GateRefusal`, `AnsweringEvidence`, `PassageRef`, `AnsweredBy`, `GLOB_WILDCARD` and the parameter-name constants the kept code uses
  - [x] Point kept code and tests at `amoeba.answering.values`
  - [x] Do not move `QuestionRecord`, `QuestionState`, `BlockedState` or `JournalEntry`
  - [x] Success: `git grep "amoeba.store"` in `src/amoeba/answering` and `tests/answering` finds nothing

- [x] **2.4 Create `answering/settings.py` (D5)**
  - [x] Move `AnswererSettings` from `runner/project_config.py`, keeping its no-defaults rule
  - [x] Drop `max_concurrent_runs`, and any field only it read
  - [x] Move `validate_repo_relative_path` (from `store/paths.py`; `RulesPath` uses it) with `GLOB_WILDCARD` handled per 2.3, so `answering/settings.py` imports nothing from `amoeba.store`; 222 imports it from there
  - [x] Move its tests to `tests/answering/`, keeping assertions that still apply
  - [x] Success: `AnswererSettings` has no default values and no `max_concurrent_runs`

- [x] **2.5 Move the upstream readers (D3, D4)**
  - Note: Kept modules landed as: upstream/context_forge/{cli_call,plan,target_read}.py, upstream/git_read.py, upstream/bounded_text.py, upstream/squadron/{run_outcome,launch,faults,resume_argv,resume_confirm}.py. plan.py lost its status field and types too.
  - [x] Context Forge: `git mv src/amoeba/runner/cf_call.py src/amoeba/upstream/context_forge/cli_call.py`; keep `upstream/context_forge/plan.py` (rework: drop the plan-status and `reported_complete` helpers); do not move `CFSnapshot` (dropped, D4); the audit deletes `checkout.py`, `projects_file.py`, `diff.py`, `slice_stem.py` and `__init__.py` of that package, so create an empty `__init__.py` (audit wins, D1)
  - [x] Squadron: `git mv src/amoeba/process/sq_outcome.py src/amoeba/upstream/squadron/run_outcome.py` (drop `RunReview` and `reviews`); move the `observed.py` values `RunEnded`, `RunVanished`, `LaunchFailed`, `ResumeFailed` and `Finished` into it as plain values (`decide` imports them from there); add `upstream/squadron/__init__.py` re-exporting nothing if absent
  - [x] Other `sq` and `cf` survivors go to their homes in the design's Audit items (`squadron/launch.py`, `squadron/resume_argv.py`, `squadron/resume_confirm.py`, `squadron/faults.py`, `context_forge/target_read.py`, `bounded_text.py`); each keeps only the audit's kept names, with the drops the design lists
  - [x] `git mv` `runner/git_read.py` to `src/amoeba/upstream/git_read.py` and drop its `TickBudget` parameter and the porcelain-status helpers the audit deletes; `runner/budget.py` is `delete` and is not moved
  - [x] Move the tests of all of the above to `tests/upstream/`; update imports elsewhere
  - [x] Success: each of these exists only under `upstream/`; `poll_run`, `SQ_EXECUTABLE` and the five run values live in `run_outcome.py`; no `CFSnapshot` exists

- [x] **2.6 Sever: values passed in (D2 "Parameter")**
  - [x] For each Dependencies of kept code entry marked "value passed in", make the value a parameter (e.g. `assemble_sources` takes a slice reference and a tuple of `PmAnswer`, not a `Store` and a `Node`)
  - [x] Where a signature changes, move the function's tests to the new signature and keep their assertions
  - [x] Success: every such entry is worked; no kept module takes a `Store` or `Node`

- [x] **2.7 Sever: uses dropped (D2 "Drop")**
  - [x] For each entry marked "dropped", remove the use and any field only it read
  - [x] For each entry whose replacement is the new store or an operation (222 to 224), remove the use now; build no stub
  - [x] Success: every such entry is worked; no kept module reads a journal entry, blocked state or tick

- [x] **2.8 Sever: helpers moved (D2 "Move")**
  - [x] Move each small helper taken from a deleted module next to its only kept user, or into `upstream/` if two kept modules use it
  - [x] Relocate, before the deleting tasks (2.10 to 2.13), what kept code imports from modules that go: `cut_to_bound` (`ingest/outcome.py`), `STDERR_TAIL_LIMIT_BYTES` (`runner/launch.py`), `QuestionInvariantError` (`settle.py`; next to its kept importer, or dropped if its only importer is a deleted unit), `LaunchFailure` and `ResumeFailure` (`faults.py`), `Finished` values (`observed.py`), `SQ_EXECUTABLE`, and `read_config`, `read_target` and the `cf_argv` pieces (`checkout_reads.py`, `plan_read.py`), to the homes in the design's Audit items
  - [x] `BEGIN_IMMEDIATE` and `decode_mapping`/`decode_timestamp` need no move: the whole store goes and 222 creates them; confirm no kept module imports them
  - [x] `DEFAULT_TARGET_BRANCH`: move it unchanged with `read_target`, defined once; add no behavior (223 task 4.6 keeps it as the single named constant, with tests)
  - [x] Split the test helpers before deleting their owners: `tests/runner/observe_support.py` (keep `Clock`, `Host`, `FakeCf`; drop `TickBudget`, `RunObserver`, `LaunchTracker`, journal types), `tests/sq_stub_scripts.py` (drop the review scripts, `runs prune` and any `--timeout 0` assumption), `tests/runner/answering/sources_repo.py` (drop `runner.budget`); kept tests import the split result
  - [x] Success: no kept module or kept test helper imports a deleted module

- [x] **2.9 Check coupling and layering**
  - [x] Search kept code and `answering.yaml` for schema column names, YAML references to deleted files, and anything started by the tick; note any found and fixed here
  - [x] Run `git grep -n "amoeba.answering" src/amoeba/upstream tests/upstream`; move any shared piece it finds down into `upstream/`
  - [x] Success: no such coupling remains and the grep finds nothing

- [x] **2.10 Delete the rest of `runner/`**
  - [x] `git rm -r` every remaining `runner/` unit the audit marks `delete` or `squadron`, with its tests and any shared harness whose last user goes (D8)
  - [x] Success: `src/amoeba/runner` does not exist

- [x] **2.11 Delete `process/` and `program/`**
  - [x] `git rm -r src/amoeba/process src/amoeba/program` and their tests
  - [x] Success: neither directory exists

- [x] **2.12 Delete `store/`**
  - [x] `git rm -r src/amoeba/store`, including `schema/` and `program_schema/`, and its tests and fixtures
  - [x] Success: `src/amoeba/store` does not exist; no `.sql` file remains under `src`

- [x] **2.13 Delete the remaining `delete` and `squadron` rows**
  - [x] Delete what the audit marks `delete` under `upstream/`: `context_forge/{checkout, projects_file, diff, slice_stem}.py` and `squadron/review*.py`, with their tests; only `plan.py`, `cli_call.py`, `target_read.py` and the 2.5 `squadron/` modules stay
  - [x] Delete any other audit `delete` or `squadron` path still present, with its tests
  - [x] Success: every path the audit marks `delete` or `squadron` is gone; `src/amoeba` holds only `__init__.py`, `answering` and `upstream` (plus anything the audit kept under another name)

- [x] **2.14 Rework or delete the remaining tests (D8)**
  - Note: observe_support.py, cli_harness.py and fault_injection.py were deleted rather than split (nothing kept uses them). The kept source-read and git-read tests count calls through a CountingRun wrapper instead of a budget.
  - [x] Handle only tests not already moved or re-signatured in 2.2 to 2.8: keep one only if its claim holds without nodes, journal entries, blocked states or a tick, building its inputs directly; otherwise delete it (223 or 224 writes the replacement)
  - [x] Remove any fixture with old-shape fields (`node_id`, journal ids); a test or helper in doubt with no scenario behind it goes
  - [x] Trim `tests/conftest.py` to `pytest_sessionstart` (orphan reaping, `reap_orphans`): remove `store_file`, `store`, `supervisor_dir` and anything else that imports the deleted store or process packages
  - [x] Keep `tests/test_store_safety.py` (audit: `rework`): replace its `amoeba.store.paths` import with the same names as string literals (`store_dir`, `store_path`, `DEFAULT_STORE_DIR`, `DEFAULT_SQ_RUNS_DIR`, `DEFAULT_CF_DATA_DIR`); the scan and the exemptions are unchanged
  - [x] Success: no test or fixture mentions nodes, journal entries, blocked states or a tick; `test_store_safety.py` imports nothing from `amoeba.store`

- [x] **2.15 Rewrite the import-boundaries test (D6)**
  - [x] Rewrite `tests/test_import_boundaries.py` to enforce one rule: `amoeba.upstream` imports nothing from `amoeba.answering`; remove every rule about deleted packages
  - [x] Success: the test enforces only the D6 rule

- [x] **2.16 Rework the kept scripts and docs**
  - Note: scripts/answerer_walkthrough.py and docs/answerer-walkthrough.md were deleted (audit rows changed to delete): after the old set-up is dropped they would describe commands that do not exist. scripts/answerer_walkthrough/project/ stays as data for 223.
  - [x] For each file under `scripts/` and `docs/` the audit marks `rework`, edit it as the row's reason says so it names only code that exists after the cut
  - [x] Success: no file under `scripts/` or `docs/` names a deleted module, command or store

- [x] **2.17 Remove unused dependencies (D7)**
  - [x] For `starlette`, `uvicorn` and dev `httpx2`, run `git grep -n` for imports across `src tests scripts`; remove each from `pyproject.toml` if nothing kept uses it
  - [x] Run `uv lock` to regenerate `uv.lock`
  - [x] Success: removed packages are absent from `pyproject.toml` and `uv.lock`

- [x] **2.18 Point the wheel at the new pipeline file (D7)**
  - [x] In `pyproject.toml` wheel `artifacts`, remove the schema globs and keep one entry: `src/amoeba/answering/answering.yaml`; update the comment above it
  - [x] Edit `tests/answering/test_wheel_contents.py` (moved there by 2.2; the copy under `request_run` went in 1.3) to check the new path
  - [x] Success: `pyproject.toml` has the single artifact entry and `tests/answering/test_wheel_contents.py` names the new path

- [x] **2.19 Update the `stays` live tests**
  - [x] For each file under `tests/live/answering` that the audit's Live tests section marks `stays`, update imports to the new paths and signatures
  - [x] Keep the names the live tier imports (design, "Names the live tier needs": `SQ_EXECUTABLE`, `RunOutcome`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, `poll_run`, `QUESTION_TAIL_CHARS`, `mint_run_id`, `prepare_scratch`, `OUTPUT_HEAD_CHARS`) with unchanged signatures; only the module paths in the files that import them (`live_harness.py`, `harness.py` and the `stays` tests) change (`amoeba.process` becomes `amoeba.upstream.squadron.run_outcome` and `launch`)
  - [x] Success: each such file is present and imports nothing deleted

- [x] **2.20 Delete the `waits on 223` live tests (D8)**
  - [x] For each file marked `waits on 223`, confirm its Live tests entry names the scenario A claim and the restore commit (the `main` commit this branch forked from); if either is missing, add it to the audit in this commit
  - [x] `git rm` the file, and any file the audit marks `delete`, which includes `tests/live/answering/test_sdk_refusal.py`
  - [x] Remove `SDK_MODEL_VARIABLE` (`AMOEBA_LIVE_SDK_MODEL`) from `tests/live_settings.py`, and any remaining reference to it (`git grep SDK_MODEL_VARIABLE`; the `request_run` copy of `test_live_tier_rules.py` went in 1.3, and the kept `answering` copy must not name it)
  - [x] Confirm the audit's Live tests notes say a restore brings back only the two `waits on 223` files (`launch_rig.py`, `question_harness.py` and the old `observe_support.py` are deleted or split); add the note in this commit if missing
  - [x] Success: every deleted `waits on 223` file has its claim and restore commit recorded in the audit; no `SDK_MODEL_VARIABLE` reference remains

- [x] **2.21 Verify the cut**
  - Note: Final gate run: ruff format --check, ruff check and pyright clean; 544 tests passed. The one grep hit for old package names is the frozen fixture text under tests/answering/fixtures/sources (project documents quoted verbatim), not code.
  - [x] Run the checks once and read the output
  - [x] Fix only breakage from imports of deleted code or moves; apply D1 if a verdict proves wrong
  - [x] Success: the checks pass, live files included in lint and pyright; `tests/answering` and `tests/upstream` pass with no store, tick or resident process

**Commit**: `refactor: move answering library, sever from store, delete the rest`

## 3. Wheel and live tier

These tasks normally change no files, so there is no commit marker.

- [x] **3.1 Build the wheel**
  - Note: `uv build --wheel` built amoeba-0.1.0; the wheel holds amoeba/answering/answering.yaml, no .sql files and no entry_points.txt (a wheel-contents test now asserts all three).
  - [x] Run `uv build`; list the wheel's contents with `unzip -l`
  - [x] Success: the wheel holds `amoeba/answering/answering.yaml`, no `.sql` files, and no console entry point (`entry_points.txt` absent or empty)
  - [x] If a failure here or in 3.2 needs a file change from the cut, make it and commit it as `refactor: {what was fixed}`; this is the only commit in this section

- [x] **3.2 Run the live tier**
  - Note: Live tier ran with the AMOEBA_LIVE_* variables and the provider key taken from .env by name (no whole-.env injection): `uv run pytest tests/live/answering` 7 passed, run twice (after the cut and after the README).
  - [x] With the `AMOEBA_LIVE_*` variables and `sq` available, run `uv run pytest tests/live/answering`
  - [x] If they are unavailable, write `BLOCKED: live tier needs AMOEBA_LIVE_* and sq` under this task and stop
  - [x] Success: the live tests pass

## 4. README

- [x] **4.1 Rewrite the README (D9)**
  - [x] Remove the hero image and old pitch; delete `assets/` if nothing else uses it
  - [x] Say, briefly: what Amoeba is (a tool agents and pipelines call to answer a paused run's first-level questions and keep the record, across a program of repos; no process of its own; optional for Squadron), what exists now (the library, no command), where the design lives (concept, `220-arch.program-tool.md`, the slice plan), and how to run the checks, including the live tier's `AMOEBA_LIVE_*` variables
  - [x] Read each variable name from the live tests' source; do not write one from memory
  - [x] Set `pyproject.toml`'s `description` to the README's first line
  - [x] Success: the README claims nothing the code does not back and mentions no command, store, tick or inbox

- [x] **4.2 Final verification**
  - Note: Final run: ruff format --check, ruff check and pyright clean; 544 tests passed. The old-package grep over src tests scripts README.md finds only two lines of frozen fixture prose in tests/answering/fixtures/sources (project documents quoted verbatim, not code); docs/ no longer exists. Success Criteria walked: all met except the amoeba#32 closure, which happens at merge in Phase 7. Audit rows changed during the cut are in the same commit as their code, with reasons.
  - [x] Run the checks once; rerun `uv run pytest tests/live/answering`
  - [x] `git grep -nE "amoeba\.(runner|process|store|program|serve|inbox|feed|cli|inspection)"` over `src tests scripts docs README.md` finds nothing
  - [x] Walk the slice's Success Criteria list and note each as met (closing `amoeba#32` happens at merge in Phase 7, not here)
  - [x] Any audit row changed during the cut has its reason and is in the same commit as its code
  - [x] Success: every Success Criteria item in the design is met

**Commit**: `docs: rewrite README for the library`
