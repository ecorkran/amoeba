---
docType: tasks
slice: code-audit
project: amoeba
lld: user/slices/220-slice.code-audit.md
dependencies: []
projectState: Slices up to 182 are partly merged to main; the 182 branch (`182-slice.program-concept-as-a-source`)
  is unmerged. `src/amoeba` holds cli, feed, inbox, inspection, process, program,
  runner, serve, store and upstream. The program-tool architecture (`user/architecture/220-arch.program-tool.md`)
  has a Current State table that guesses what stays. No audit document exists and
  `user/analysis/` does not exist yet.
dateCreated: 20261107
dateUpdated: 20261108
status: in_progress
turns: 10
promptTokens: 291955
cachedTokens: 259908
cacheWriteTokens: 32031
completionTokens: 6515
durationSeconds: 45.6
costUsd: 0.219593
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.2195932
    completionTokens: 6515
---

# Tasks: Code Audit

## Context Summary

This slice writes one document, `user/analysis/220-analysis.code-audit.md`, giving a verdict (`keep`, `rework`, `squadron`, `delete`) with a one-line reason for every piece of current code. It changes no file under `src/`, `tests/`, `scripts/` or `docs/`. Verdict rules are in the slice design (D1 to D5): coarsest level where everything agrees; every `keep` or `rework` names a scenario (A, B, C or set-up); judge by scenarios, not code quality; tests follow the code they exercise. Scenarios are defined in the architecture. Work on branch `220-slice.code-audit`. Do answering and store first, since other verdicts follow from them.

Document sections, in order: Summary, Verdicts, Dependencies of kept code, Slice 182, Live tests, Move to Squadron, Differences from the architecture.

Commits are at `**Commit**:` markers only. Task files are updated by the `task-checker` agent.

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 220-slice.code-audit {target}`
  - [x] Success: `git branch --show-current` prints `220-slice.code-audit`

- [x] **0.2 Read the inputs**
  - [x] Read `user/slices/220-slice.code-audit.md` and `user/architecture/220-arch.program-tool.md` (scenarios A, B, C, set-up; the Current State table)
  - [x] Read `user/architecture/220-slices.program-tool.md` for the 221 to 224 scope lines
  - [x] Read `file-naming-conventions.md` for the `analysis` frontmatter
  - [x] Success: you can state each scenario in one sentence each

- [x] **0.3 Create the audit skeleton**
  - [x] Create `user/analysis/220-analysis.code-audit.md` with `analysis` frontmatter (`topic: code-audit`, status `in_progress`) and the seven section headings, each with a placeholder line
  - [x] Success: file has seven headings in the order listed above

**Commit**: `docs: add code audit skeleton`

## 1. Answering and Store Verdicts

- [x] **1.1 Audit `runner/answering/`**
  - [x] Read each module: `artifacts.py`, `decide.py`, `finish.py`, `gate.py`, `inputs.py`, `launch.py`, `passages.py`, `pipeline_file.py`, `settle.py`, `source_reads.py`, `sources.py`, `stage.py`, `answering.yaml`
  - [x] For each, record imports from, and uses of, nodes, journal entries, blocked states, the tick, and question `node_id`
  - [x] Add one row per module (split further only if a module is mixed) to the Verdicts table with verdict and scenario-naming reason

- [x] **1.2 Audit `store/` question and answer units**
  - [x] Cover `questions.py`, `question_models.py`, `sql_questions.py`, `mapping_questions.py`, `answering.py`, `answer_submission.py`, `project_escalations.py`, `routing_decisions.py`
  - [x] Note schema columns each relies on (including `node_id`)
  - [x] Add rows to Verdicts

- [x] **1.3 Audit `store/` node, journal, block and check units**
  - [x] Cover `nodes.py`, `journal*.py`, `mapping_journal.py`, `sql_journal.py`, `blocking.py`, `_block_writer.py`, `checks.py`, `check_models.py`, `_check_writer.py`, `sql_checks.py`, `desired_states.py`, `attribution.py`, `calibration.py`
  - [x] Add rows to Verdicts

- [x] **1.4 Audit remaining `store/` and its schema directories**
  - [x] Cover connection, migrations, paths, base, models, program store and schema (`program_*`, `_program_*`, `sql_program.py`, `mapping_program.py`, `schema/`, `program_schema/`), messages and inbox, feed, cf, evidence, runner and verdict units
  - [x] Group by the coarsest agreeing level per D1; split `store/` by module where mixed
  - [x] Add rows to Verdicts

- [x] **1.5 Record the first dependency entries**
  - [x] In Dependencies of kept code, add an entry for each `keep` or `rework` unit from 1.1 to 1.4: what deleted thing it relies on, and one replacement per D3 (new store table or field, 223/224 operation, caller-passed value, or nothing with reason)
  - [x] Include coupling an import list misses: `node_id` on question records, schema columns, `answering.yaml` references, and answering code started by the tick
  - [x] Any replacement the architecture lacks goes in Differences, not designed here

**Commit**: `docs: audit answering and store verdicts`

## 2. Runner, Process, Upstream and Program Verdicts

- [x] **2.1 Audit remaining `runner/` top-level modules and subpackages**
  - [x] Cover `tick.py`, `act.py`, `decide.py`, `observe*.py`, `launch.py`, `finish.py`, `supervise.py`, `tenant.py`, `factory.py`, `budget.py`, `faults.py`, `probes.py`, `cf_call.py`, `git_read.py`, `project_*`, `pipeline_resource.py`, `record_runs.py`
  - [x] Cover `dispatch/`, `ingest/`, `intent/`, `lifecycle/`, `resolutions/`, `program/`
  - [x] Add rows to Verdicts

- [x] **2.2 Audit `runner/request_run/` (slice 180)**
  - [x] Per D5, default `delete`; keep only if you can name a scenario that calls it
  - [x] Cover `slice_writing.yaml`, its tests and fixtures
  - [x] Add rows to Verdicts

- [x] **2.3 Audit `process/`**
  - [x] Cover host, supervisor, tenants, recovery, observers, instance lock, settings, review detection and scan, inbox tenants, cf watch, sq outcome, run pruning, log limit, grace, version label, project stores
  - [x] Split by module (D1) and add rows to Verdicts

- [x] **2.4 Audit `upstream/` and `program/`**
  - [x] `upstream/context_forge` and `upstream/squadron`: split by module; note which are the `sq` launch, poll and resume code
  - [x] `program/` (`members.py`)
  - [x] Add rows to Verdicts

- [x] **2.5 Audit `cli/`, `inspection/`, `serve/`, `inbox/`, `feed/`**
  - [x] `cli/` (each command file), `inspection/` (each module)
  - [x] `serve/`, `inbox/`, `feed/`: one row each if uniform
  - [x] Add rows to Verdicts

- [x] **2.6 Record dependency entries for 2.1 to 2.5**
  - [x] Same rules as 1.5, including nodes, journal entries, blocked states and the tick loop as explicit entries

**Commit**: `docs: audit runner, process, upstream and program verdicts`

## 3. Tests, Scripts, Docs and Packaged Resources

- [x] **3.1 Audit `tests/` directories and top-level files**
  - [x] Cover each directory (`cli`, `contract`, `feed`, `fixtures`, `inbox`, `inspection`, `live`, `load`, `process`, `program`, `runner`, `serve`, `store`, `upstream`) and each top-level `test_*.py` and harness file
  - [x] For `live`, add one row pointing to the Live tests section; per-file verdicts under `tests/live/answering/` are written only in 5.1
  - [x] A test of deleted code is `delete`; a test of kept code is `rework` only if its claim holds without nodes, journal entries or the tick, otherwise `delete` and note 223 writes new ones
  - [x] Add rows to Verdicts

- [x] **3.2 Audit `scripts/` and `docs/`**
  - [x] One row per script and per doc file (`docs/*.md` and `scripts/*`), with reason
  - [x] Add rows to Verdicts

- [x] **3.3 Audit packaged resources**
  - [x] Confirm rows exist for `answering.yaml` (1.1) and `slice_writing.yaml` (2.2); add rows for the schema directories and the console entry point (read `pyproject.toml`)
  - [x] Add rows to Verdicts

- [x] **3.4 Coverage check by hand**
  - [x] List every directory under `src/amoeba` and `tests`, plus `scripts/` and `docs/`; confirm each is covered by a row
  - [x] Add rows for anything missed

**Commit**: `docs: audit tests, scripts, docs and resources verdicts`

## 4. Slice 182

- [x] **4.1 Sort the 182 diff**
  - [x] Run `git diff --stat {target}...182-slice.program-concept-as-a-source` and `git diff --name-only` for the same range
  - [x] Sort every changed file into take, rewrite or drop (D4); read commit `e0a4615` to place it
  - [x] Write the Slice 182 section: verdict (merge, reuse parts, or redo) and the three groups
  - [x] Check that no listed file is a `delete` row in Verdicts, or explain in Differences

- [x] **4.2 Note on the slice plan**
  - [x] If the verdict is reuse parts or redo, add a one-line note to the 223 entry in `user/architecture/220-slices.program-tool.md` pointing to the Slice 182 section
  - [x] If a verdict changes any other slice plan entry's scope, add a one-line note there too

**Commit**: `docs: audit slice 182 branch`

## 5. Live Tests, Squadron and Differences

- [ ] **5.1 Live tests**
  - [ ] For `conftest.py`, `harness.py`, `question_tails.py`, `stage_harness.py`, `test_answering_run.py`, `test_pipeline_run.py`, `test_precedence.py`, `test_sdk_refusal.py` and `fixtures/` under `tests/live/answering/`: state stays, waits on 223 (name the scenario A claim it covers), or delete
  - [ ] Write the Live tests section

- [ ] **5.2 Squadron candidates**
  - [ ] List units that Squadron users in general would want and that can be described without mentioning Amoeba
  - [ ] Run `gh issue list -R ecorkran/squadron --state open` and check each candidate against it (#299, #302, #303, #304 exist)
  - [ ] For each remaining candidate, read #302 and #303 for style, then file an issue with `gh issue create -R ecorkran/squadron`; if there are none, say so
  - [ ] Write the Move to Squadron section with an issue link per item; set `squadron` rows' reasons to include the link

- [ ] **5.3 Differences from the architecture**
  - [ ] Compare Verdicts against the architecture's Current State table
  - [ ] List each difference with the reason, plus any uncovered replacements from the Dependencies section

**Commit**: `docs: audit live tests, squadron items and differences`

## 6. Finish

- [ ] **6.1 Write the Summary**
  - [ ] A few lines: what stays, the 182 verdict, issues filed
  - [ ] Set frontmatter status to `complete`

- [ ] **6.2 Verify success criteria**
  - [ ] All seven sections are filled; no placeholder lines remain
  - [ ] Every `squadron` row links an open issue
  - [ ] Every `keep` and `rework` row names a scenario
  - [ ] Every directory under `src/amoeba` and `tests`, plus `scripts/` and `docs/`, has a row (repeat of 3.4)
  - [ ] Every file in the 182 diff is sorted (repeat of 4.1)
  - [ ] `git diff --name-only {target}...HEAD` lists only files under `project-documents/` (nothing under `src/`, `tests/`, `scripts/` or `docs/`)

**Commit**: `docs: complete code audit`
