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
status: not_started
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

- [ ] **0.1 Create the branch**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [ ] Confirm the working tree is clean and you are on the target
  - [ ] `git checkout -b 221-slice.the-cut {target}`
  - [ ] Success: `git branch --show-current` prints `221-slice.the-cut`

- [ ] **0.2 Confirm the audit and read it**
  - [ ] Confirm `user/analysis/220-analysis.code-audit.md` exists with `status: complete`; if not, write `BLOCKED: audit 220 not complete` under this task and stop
  - [ ] Read its Verdicts, Dependencies of kept code, Live tests, Move to Squadron and Differences from the architecture sections
  - [ ] Compare design predictions (D2 deletions, D3 moves, D4 types, D5 settings) with the audit; list differences in a note under this task
  - [ ] Success: you hold the delete list, the kept list, and every Dependencies of kept code entry

- [ ] **0.3 Record the baseline**
  - [ ] Run the checks once on the untouched branch and note the result
  - [ ] Note whether `AMOEBA_LIVE_*` variables and `sq` are available for the live tier
  - [ ] Success: a baseline note exists; failures present before the cut are written down, not fixed

## 1. Leaf deletions

Delete units no kept unit depends on. A file that imports one of them is edited only if the audit keeps or reworks it (remove the import and its use, no rewiring); a file the audit marks `delete` is deleted outright.

- [ ] **1.1 Delete `serve/`, `inbox/`, `feed/` and `inspection/`**
  - [ ] `git rm -r` `src/amoeba/serve`, `inbox`, `feed` and `inspection`, and their tests
  - [ ] Success: none of the four directories or their test directories remains

- [ ] **1.2 Delete `cli/`**
  - [ ] `git rm -r src/amoeba/cli` and its tests
  - [ ] Remove the `[project.scripts] amoeba` entry from `pyproject.toml` (D7)
  - [ ] Success: `pyproject.toml` has no `[project.scripts]` table and no `amoeba.cli` reference remains

- [ ] **1.3 Delete `runner/request_run/` and `slice_writing.yaml`**
  - [ ] `git rm -r src/amoeba/runner/request_run` (includes `slice_writing.yaml`) and its tests
  - [ ] Remove the `slice_writing.yaml` glob from wheel `artifacts` in `pyproject.toml`
  - [ ] Success: no `request_run` or `slice_writing` path or reference remains

- [ ] **1.4 Delete `tests/load/`**
  - [ ] `git rm -r tests/load`; remove `--ignore=tests/load` from pytest `addopts` (D7, D8)
  - [ ] Success: `addopts` is `["--ignore=tests/live"]`; `tests/load` is gone

- [ ] **1.5 Delete the audit's `delete` scripts and docs**
  - [ ] Delete each file under `scripts/` and `docs/` whose audit verdict is `delete`; leave every `keep` or `rework` file
  - [ ] Success: every remaining file under `scripts/` and `docs/` has a `keep` or `rework` audit row

- [ ] **1.6 Verify the leaf cut**
  - [ ] Run `git grep -nE "amoeba\.(serve|inbox|feed|cli|inspection)|request_run"` over `src tests scripts`; fix each hit as the section intro says
  - [ ] Checks pass
  - [ ] Success: the grep finds nothing and the checks pass

**Commit**: `chore: delete leaf packages, load tests and demo scripts`

## 2. Move, sever and delete

Checks run once, at task 2.21; do not re-point old code to keep it compiling. Take unit lists from the audit and the design's Migration Plan table, not from memory. The old code cannot compile between the moves and the deletions, so this section has one commit, after the gate. Its parts: 2.1 to 2.9 move and sever, 2.10 to 2.13 delete, 2.14 to 2.20 tests, docs, packaging and live files, 2.21 the gate.

- [ ] **2.1 Delete rework units that need a later replacement (D2)**
  - [ ] Delete each `rework` unit whose behavior only works with a later replacement (question record, `sq` launch, store submit), with its tests, at its old path; D2 lists the predicted units, the audit decides
  - [ ] For a unit with a kept half, keep that half where the audit's `rework` reason says; if it names no destination, place it in `src/amoeba/answering/` (D3)
  - [ ] For each deleted unit, change its audit row to `delete` and add a line to Differences from the architecture with the reason; note it here (D1)
  - [ ] Success: no stub or placeholder remains for launch, stage, settle or submit

- [ ] **2.2 Move the answering library and its tests**
  - [ ] `git mv` each kept module from `src/amoeba/runner/answering/` and `runner/pipeline_resource.py` to `src/amoeba/answering/` (Migration Plan table); `git mv` their tests to `tests/answering/`
  - [ ] Create `src/amoeba/answering/__init__.py` re-exporting nothing (D3)
  - [ ] Update imports to name the defining module; no compatibility re-exports at old paths
  - [ ] Success: moved files exist only at the new paths; `git status` shows renames

- [ ] **2.3 Create `answering/values.py` (D4)**
  - [ ] Move unchanged from `amoeba.store`: `DeclineReason`, `GateRefusal`, `AnsweringEvidence`, `PassageRef`, `AnsweredBy`, `GLOB_WILDCARD` and the parameter-name constants the kept code uses
  - [ ] Point kept code and tests at `amoeba.answering.values`
  - [ ] Do not move `QuestionRecord`, `QuestionState`, `BlockedState` or `JournalEntry`
  - [ ] Success: `git grep "amoeba.store"` in `src/amoeba/answering` and `tests/answering` finds nothing

- [ ] **2.4 Create `answering/settings.py` (D5)**
  - [ ] Move `AnswererSettings` from `runner/project_config.py`, keeping its no-defaults rule
  - [ ] Drop `max_concurrent_runs`, and any field only it read
  - [ ] Move its tests to `tests/answering/`, keeping assertions that still apply
  - [ ] Success: `AnswererSettings` has no default values and no `max_concurrent_runs`

- [ ] **2.5 Move the upstream readers (D3, D4)**
  - [ ] Context Forge: `git mv src/amoeba/runner/cf_call.py src/amoeba/upstream/context_forge/cli_call.py`; move `CFSnapshot` into `upstream/context_forge/`; keep the existing exports of its `__init__.py`
  - [ ] Squadron: `git mv src/amoeba/process/sq_outcome.py src/amoeba/upstream/squadron/run_outcome.py`; move `RunEnded`, `RunVanished` and `LaunchFailed` from `runner/observed.py` into it (`decide` imports them from there); add `upstream/squadron/__init__.py` re-exporting nothing if absent
  - [ ] `git mv` `runner/budget.py` and `runner/git_read.py` to `src/amoeba/upstream/`, if the audit keeps them
  - [ ] Move the tests of all of the above to `tests/upstream/`; update imports elsewhere
  - [ ] Success: each of these exists only under `upstream/`; `poll_run` and the three run types live in `run_outcome.py`

- [ ] **2.6 Sever: values passed in (D2 "Parameter")**
  - [ ] For each Dependencies of kept code entry marked "value passed in", make the value a parameter (e.g. `assemble_sources` takes a slice reference and a tuple of `PmAnswer`, not a `Store` and a `Node`)
  - [ ] Where a signature changes, move the function's tests to the new signature and keep their assertions
  - [ ] Success: every such entry is worked; no kept module takes a `Store` or `Node`

- [ ] **2.7 Sever: uses dropped (D2 "Drop")**
  - [ ] For each entry marked "dropped", remove the use and any field only it read
  - [ ] For each entry whose replacement is the new store or an operation (222 to 224), remove the use now; build no stub
  - [ ] Success: every such entry is worked; no kept module reads a journal entry, blocked state or tick

- [ ] **2.8 Sever: helpers moved (D2 "Move")**
  - [ ] Move each small helper taken from a deleted module next to its only kept user, or into `upstream/` if two kept modules use it
  - [ ] Success: no kept module imports a deleted module

- [ ] **2.9 Check coupling and layering**
  - [ ] Search kept code and `answering.yaml` for schema column names, YAML references to deleted files, and anything started by the tick; note any found and fixed here
  - [ ] Run `git grep -n "amoeba.answering" src/amoeba/upstream tests/upstream`; move any shared piece it finds down into `upstream/`
  - [ ] Success: no such coupling remains and the grep finds nothing

- [ ] **2.10 Delete the rest of `runner/`**
  - [ ] `git rm -r` every remaining `runner/` unit the audit marks `delete` or `squadron`, with its tests and any shared harness whose last user goes (D8)
  - [ ] Success: `src/amoeba/runner` does not exist

- [ ] **2.11 Delete `process/` and `program/`**
  - [ ] `git rm -r src/amoeba/process src/amoeba/program` and their tests
  - [ ] Success: neither directory exists

- [ ] **2.12 Delete `store/`**
  - [ ] `git rm -r src/amoeba/store`, including `schema/` and `program_schema/`, and its tests and fixtures
  - [ ] Success: `src/amoeba/store` does not exist; no `.sql` file remains under `src`

- [ ] **2.13 Delete the remaining `delete` and `squadron` rows**
  - [ ] Delete the upstream review parsers and any other audit `delete` or `squadron` path still present, with their tests
  - [ ] Success: every path the audit marks `delete` or `squadron` is gone; `src/amoeba` holds only `__init__.py`, `answering` and `upstream` (plus anything the audit kept under another name)

- [ ] **2.14 Rework or delete the remaining tests (D8)**
  - [ ] Handle only tests not already moved or re-signatured in 2.2 to 2.8: keep one only if its claim holds without nodes, journal entries, blocked states or a tick, building its inputs directly; otherwise delete it (223 or 224 writes the replacement)
  - [ ] Remove any fixture with old-shape fields (`node_id`, journal ids); a test or helper in doubt with no scenario behind it goes
  - [ ] Success: no test or fixture mentions nodes, journal entries, blocked states or a tick

- [ ] **2.15 Rewrite the import-boundaries test (D6)**
  - [ ] Rewrite `tests/test_import_boundaries.py` to enforce one rule: `amoeba.upstream` imports nothing from `amoeba.answering`; remove every rule about deleted packages
  - [ ] Success: the test enforces only the D6 rule

- [ ] **2.16 Rework the kept scripts and docs**
  - [ ] For each file under `scripts/` and `docs/` the audit marks `rework`, edit it as the row's reason says so it names only code that exists after the cut
  - [ ] Success: no file under `scripts/` or `docs/` names a deleted module, command or store

- [ ] **2.17 Remove unused dependencies (D7)**
  - [ ] For `starlette`, `uvicorn` and dev `httpx2`, run `git grep -n` for imports across `src tests scripts`; remove each from `pyproject.toml` if nothing kept uses it
  - [ ] Run `uv lock` to regenerate `uv.lock`
  - [ ] Success: removed packages are absent from `pyproject.toml` and `uv.lock`

- [ ] **2.18 Point the wheel at the new pipeline file (D7)**
  - [ ] In `pyproject.toml` wheel `artifacts`, remove the schema globs and keep one entry: `src/amoeba/answering/answering.yaml`; update the comment above it
  - [ ] Edit `tests/answering/test_wheel_contents.py` (moved there by 2.2; the copy under `request_run` went in 1.3) to check the new path
  - [ ] Success: `pyproject.toml` has the single artifact entry and `tests/answering/test_wheel_contents.py` names the new path

- [ ] **2.19 Update the `stays` live tests**
  - [ ] For each file under `tests/live/answering` that the audit's Live tests section marks `stays`, update imports to the new paths and signatures
  - [ ] Success: each such file is present and imports nothing deleted

- [ ] **2.20 Delete the `waits on 223` live tests (D8)**
  - [ ] For each file marked `waits on 223`, confirm its Live tests entry names the scenario A claim and the restore commit (the `main` commit this branch forked from); if either is missing, add it to the audit in this commit
  - [ ] `git rm` the file, and any file the audit marks `delete`
  - [ ] Success: every deleted `waits on 223` file has its claim and restore commit recorded in the audit

- [ ] **2.21 Verify the cut**
  - [ ] Run the checks once and read the output
  - [ ] Fix only breakage from imports of deleted code or moves; apply D1 if a verdict proves wrong
  - [ ] Success: the checks pass, live files included in lint and pyright; `tests/answering` and `tests/upstream` pass with no store, tick or resident process

**Commit**: `refactor: move answering library, sever from store, delete the rest`

## 3. Wheel and live tier

These tasks normally change no files, so there is no commit marker.

- [ ] **3.1 Build the wheel**
  - [ ] Run `uv build`; list the wheel's contents with `unzip -l`
  - [ ] Success: the wheel holds `amoeba/answering/answering.yaml`, no `.sql` files, and no console entry point (`entry_points.txt` absent or empty)
  - [ ] If a failure here or in 3.2 needs a file change from the cut, make it and commit it as `refactor: {what was fixed}`; this is the only commit in this section

- [ ] **3.2 Run the live tier**
  - [ ] With the `AMOEBA_LIVE_*` variables and `sq` available, run `uv run pytest tests/live/answering`
  - [ ] If they are unavailable, write `BLOCKED: live tier needs AMOEBA_LIVE_* and sq` under this task and stop
  - [ ] Success: the live tests pass

## 4. README

- [ ] **4.1 Rewrite the README (D9)**
  - [ ] Remove the hero image and old pitch; delete `assets/` if nothing else uses it
  - [ ] Say, briefly: what Amoeba is (a tool agents and pipelines call to answer a paused run's first-level questions and keep the record, across a program of repos; no process of its own; optional for Squadron), what exists now (the library, no command), where the design lives (concept, `220-arch.program-tool.md`, the slice plan), and how to run the checks, including the live tier's `AMOEBA_LIVE_*` variables
  - [ ] Read each variable name from the live tests' source; do not write one from memory
  - [ ] Set `pyproject.toml`'s `description` to the README's first line
  - [ ] Success: the README claims nothing the code does not back and mentions no command, store, tick or inbox

- [ ] **4.2 Final verification**
  - [ ] Run the checks once; rerun `uv run pytest tests/live/answering`
  - [ ] `git grep -nE "amoeba\.(runner|process|store|program|serve|inbox|feed|cli|inspection)"` over `src tests scripts docs README.md` finds nothing
  - [ ] Walk the slice's Success Criteria list and note each as met (closing `amoeba#32` happens at merge in Phase 7, not here)
  - [ ] Any audit row changed during the cut has its reason and is in the same commit as its code
  - [ ] Success: every Success Criteria item in the design is met

**Commit**: `docs: rewrite README for the library`
