---
docType: tasks
slice: lifecycle-model-and-reconciliation
project: amoeba
lld: user/slices/123-slice.lifecycle-model-and-reconciliation.md
dependencies:
- 121
- 122
projectState: Slices 120, 121 and 122 are merged. `amoeba.runner` has the tick skeleton,
  `TickBudget`, `ProjectView(runnable_nodes, in_flight, link_probes)`, the `Planner`
  seam, the one-member `Action` union, `FaultKind` (four members), `LinkProbes` and
  the two `cf` probes (`cf status`, `cf list initiatives`; the slices probe is already
  gone). Migration `009` is the newest. `CFReference` has no index. `nodes.cf_index`,
  `amoeba.upstream.context_forge.plan`, `amoeba.runner.lifecycle` and `plan_read_interval_seconds`
  do not exist. `tests/cf_stub.py` answers only `status` and `list initiatives` without
  `-a`.
dateCreated: 20261023
dateUpdated: 20261023
status: complete
turns: 41
promptTokens: 3211960
cachedTokens: 3057189
cacheWriteTokens: 154717
completionTokens: 48609
durationSeconds: 336.1
costUsd: 1.411075
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

## Context Summary

- Working on the **lifecycle-model-and-reconciliation** slice (123), the fourth slice of initiative 120 (Runner and Routing Engine). It projects each linked CF project's plan into the node tree, keeps the tree in step as the plan changes, and defines the lifecycle vocabulary (steps, predecessors, "ready") that 124–129 build on.
- **Current state:** the Runner ticks per project in `runner/tick.py` (`ProjectTick.run`: observe, probes, record, decide, act, close). Faults are in `runner/faults.py`, probes in `runner/probes.py`, the planner seam in `runner/decide.py`, settings in `process/settings.py`, start flags in `cli/settings_flags.py`. The store's node writes are `create_node`, `update_cf_reference`, `update_node_status`, `block`, `resolve` (`store/nodes.py`, `store/blocking.py`). The stub `cf` is `tests/cf_stub.py`; captured CF outputs go under `tests/fixtures/cf/`.
- **Dependencies:** 121 (done-terminal, project-scoped escalation, opaque `step` columns, migration `009`) and 122 (tick, budget, planner seam, faults, probes). Both are merged.
- **What this slice delivers:** migration `010` and `CFReference.index`; `upstream/context_forge/plan.py`; the `amoeba.runner.lifecycle` subpackage (step map, tree, predecessors, plan read, reconcile, `HumanStepPlanner`); `plan_read_interval_seconds` and `--plan-read-interval`; three fault kinds and `BlockHumanStep`; a guard that only `reconcile.py` calls `create_node`; contract text and CHANGELOG. `HumanStepPlanner` is not in the production planner tuple (124 registers it).
- **Next planned slice:** 124 (intent vocabulary), which targets the nodes this slice creates.

**Branch:** all implementation happens on `123-slice.lifecycle-model-and-reconciliation`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/123-slice.lifecycle-model-and-reconciliation.md` at the named decision (D1–D12), "Architecture", or "Implementation Details". Keep every new or changed source file near 300 lines and each function near 50.

**Commit cadence:** one commit per task. A commit never holds untested behavior. Run `uv run ruff format .` before each commit. Commit type is `feat:` for new behavior, `refactor:` for behavior-preserving change, `test:` for test-only work, `docs:` for contract text.

**Task-level additions to the LLD:**
- **Module split.** `create_node` is called only in `lifecycle/reconcile.py` (D10), which holds the create rule and the orchestration. The other rules live beside it: `lifecycle/read_checks.py` (D5 safety rules), `lifecycle/orphaning.py` (D5 orphan), `lifecycle/completion.py` (D5 complete). Split further only if a file passes ~300 lines.
- **`ProjectView` follows the LLD.** `tree` replaces 122's `runnable_nodes`. 122's test planners (the production tuple is empty) pick their own nodes through one shared test helper, `runnable_unbusy(view)` in `tests/runner/tick_support.py`: nodes of `view.tree` with status `runnable` and no node id among `view.in_flight` entries. Task 9.1 makes the change.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`.
- **No magic values.** Defaults for the new setting live only in `settings.py`. Every CF command, key name and payload key is defined once and imported (LLD "Patterns and Conventions").
- **Test doubles.** The clock, subprocess runner and `Popen` are injected; unit tests never sleep and never run the real `cf` or `sq`. Reconcile tests use `Store.open_temporary()`.
- **Ordering rule for tests.** Rule tests are named for the rule they prove (LLD Verification Walkthrough step 1).

**Section map.** 1 baseline; 2 store (migration, index, inspect); 3 plan models and fixtures; 4 probe set; 5 steps and tree; 6 setting, stub, plan read; 7 fault vocabulary; 8 reconcile; 9 tick wiring; 10 human steps; 11 contract text and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Create `123-slice.lifecycle-model-and-reconciliation` from the target. If it exists, switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each. Record the passed-test count in this task — baseline: 2384 passed
- **Success Criteria**:
  - [x] On the slice branch. Baseline suite, `ruff` and `pyright` are clean. If not, write `BLOCKED:` with the failure and stop. No commit needed

---

## Section 2: Store contract changes (migration 010)

### Task 2.1: Migration `010` and `CFReference.index`, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

Per the LLD, D1 and "Database / Storage Schema". Create `store/schema/010_node_cf_index.sql` and `tests/store/test_migration_010.py` (follow `test_migration_009.py`). Edit `store/models.py`, `store/sql.py`, `store/nodes.py`, `store/mapping.py` and any row-values helper that lists the node columns (`grep -n "cf_slice\|COL_NODE_CF" src/amoeba/store/*.py`).

- [x] SQL exactly as the LLD gives: `ALTER TABLE nodes ADD COLUMN cf_index INTEGER` and the partial unique index `idx_nodes_cf_link` on `(project_id, kind, cf_project, cf_index) WHERE cf_index IS NOT NULL`
- [x] `CFReference` gains `index: int | None = None` (docstring: the store still never interprets it). Define the column-name constant once in `sql.py`. `create_node`, `update_cf_reference` and the node mapping read and write it
- [x] Update the schema-version expectations the existing migration tests pin (`grep -rn "009\|SCHEMA_VERSION" tests src/amoeba/store/migrations.py`)
- [x] Tests: migration applies to a populated v9 store, existing rows get a null `cf_index`, and node data is unchanged; a node round-trips `CFReference(index=…)`; `update_cf_reference` replaces the index; two nodes with the same `(project, kind, cf_project, cf_index)` raise `StoreIntegrityError`; the same index under a different kind, a different CF project, or a different Amoeba project is allowed; null indexes never collide
- **Success Criteria**:
  - [x] New tests, the migration and store tests, `uv run pytest tests/contract -q`, `ruff` and `pyright` pass. Commit: `feat: add node cf_index with a partial unique link index`

### Task 2.2: `amoeba inspect nodes` shows the index, with tests
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 2

Edit `inspection/listing.py` and its tests in `tests/inspection/test_listing.py`. Follow how `cf_slice` and the other CF fields are shown.

Implementation note: the listing lives in `inspection/__init__.py` and `inspection/core.py` (rows are flat), so the column is `cf_index` in the table and `--json` (null when unset), not a nested `cf.index`; tests are in `tests/inspection/test_node_rows.py`.

- [x] The nodes listing gains a `cf_index` column; `--json` output gains `cf.index` (null when unset)
- [x] Tests: a node with an index shows it in both forms; a node without shows an empty cell and `null`; existing columns and JSON keys are unchanged
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: show node cf index in inspect nodes`

---

## Section 3: Plan models and captured fixtures

### Task 3.1: Capture CF output fixtures
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 2

Per the LLD, "Technology Choices". The parser rule in CLAUDE.md requires real output. Reads against CF are pre-authorized and write nothing. Find this repository's CF project id with `cf list projects --json` (the entry whose `projectPath` equals the repo root). Record `cf --version` in `tests/fixtures/README.md`.

Finding: with cf 0.19.17 the `cf list slices 140` error document is written to **stderr** (stdout empty, exit 1). `list_slices_error.json` holds the stderr text. Tasks 4.1 (`run_cf` must keep stderr), 6.3/6.2 (stub writes it to stderr) and 8.1 (read classification) must read the error document from stderr when stdout is empty. Recorded in tests/fixtures/README.md.

- [x] Save, under `tests/fixtures/cf/`: `list_initiatives_a.json` (`cf list initiatives --json -a -p <id>`), `list_slices_120.json` (`cf list slices 120 --json -p <id>`), `list_slices_100.json`, and `list_slices_error.json` (`cf list slices 140 --json -p <id>`: exit 1, `{"error": true, …}`; save the stdout document)
- [x] Failure paths: if no project entry matches the repo root, or any command fails other than the one expected error, write `BLOCKED:` with the command and its output and stop. If `cf list slices 140` returns a plan instead of an error, use another initiative from the initiatives fixture whose command exits 1 with an error document, and name the file after it in the README; if none does, `BLOCKED:` the same way
- [x] Replace the machine-specific project id and absolute paths if any appear. Keep every key CF printed
- [x] Add one line per file to `tests/fixtures/README.md`: command, CF version, capture date
- **Success Criteria**:
  - [x] Four JSON files exist and parse with `json.load`. The error fixture has `error: true`. Commit: `test: capture CF plan read fixtures`

### Task 3.2: Plan models and parsers, with tests
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 4

Per the LLD, D12 and Component Structure. Create `upstream/context_forge/plan.py` and `tests/upstream/test_cf_plan.py`. Export through `upstream/context_forge/__init__.py` and update any public-API pin test (`grep -rn "context_forge" tests/*public*`). pydantic v2 is already a dependency.

Implementation note: D12 lists no required `status`, so an absent status parses to `None` (CF reported none), distinct from `UnknownPlanStatus` (an out-of-vocabulary value). Slice 124+ and Task 8.4 treat only `UnknownPlanStatus` as unknown.

- [x] `PlanEntryStatus` `StrEnum`: `complete`, `in_progress`, `not_started`, `deprecated`, `deferred`, `degraded`. A status outside it parses to an explicit unknown value carrying the raw text (a small frozen dataclass), never a default
- [x] Models with `extra="ignore"`: `CFInitiative(index, name, arch_file, is_checked, status)` and `CFSliceEntry(index, name, design_file, status, is_checked)` (aliases `archFile`, `designFile`, `isChecked`), `CFSliceList(entries)`, `CFErrorDocument(error: true, …)`. Required: `index`, `name`, `isChecked`, `entries`. Optional: `archFile`, `designFile`
- [x] `parse_initiatives(text) -> list[CFInitiative]` and `parse_slice_list(text) -> CFSliceList | CFErrorDocument`. A missing required field, malformed JSON or wrong top-level form raises one `PlanParseError` naming the read, the entry index when one was parsed, and the pydantic message
- [x] "Reported complete" predicate defined once here: `status == complete` or `is_checked`. A function `reported_complete(entry)` used by later tasks
- [x] Tests, using the captured fixtures: initiatives parse with every index; `archFile: null` parses; slice list parses; the error fixture parses to `CFErrorDocument`; unknown extra fields are ignored; a missing `index`, a missing `entries` and a non-array initiatives document each raise `PlanParseError` with the read named; an out-of-vocabulary status is explicit-unknown with the raw value; `degraded` is its own member; `reported_complete` is true for `complete` and for `is_checked` alone, false otherwise
- **Success Criteria**:
  - [x] Tests pass with real fixtures. `pyright` strict clean. Commit: `feat: add Context Forge plan models and parsers`

---

## Section 4: The probe set (D11)

### Task 4.1: Extract the shared `cf` call, with tests
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 2

Behavior-preserving, so a separate commit from Task 4.2. Edit `runner/probes.py`; create `runner/cf_call.py`; tests in `tests/runner/test_probes.py` stay unchanged.

Implementation note: `cf_call.py` also holds `CfRun` and `CfCallFailed(detail)`; `run_cf` keeps stdout and stderr (CF writes some error documents to stderr). Added `tests/runner/test_cf_call.py`; `tenant.py` imports `CfRun` from `cf_call`.

- [x] `cf_call.py` holds `run_cf(argv, run, timeout_seconds)`, returning the completed process or a failure detail (timeout, `OSError`), extracted from `probe_link`'s call code, and `OUTPUT_HEAD_CHARS` moved from `probes.py` so later modules can import both without a cycle. `probe_link` uses them
- **Success Criteria**:
  - [x] Existing probe tests pass with no edits. Commit: `refactor: extract the shared cf call`

### Task 4.2: Probe `cf list initiatives -a` with the full model, with tests
**Owner**: Junior AI | **Dependencies**: 4.1 | **Effort**: 2

Per the LLD, D11 ("the commands are defined once in `plan_read.py`, and `probes.py` uses the same constants"). 122 already dropped the slices probe. Create `runner/lifecycle/__init__.py` (empty exports for now) and `runner/lifecycle/plan_read.py` holding only the command constants for now (Task 6.3 adds the read); edit `runner/probes.py`, `tests/cf_stub.py`, `tests/runner/test_probes.py`.

Implementation note: added `CF_ALL_FLAG` and `slice_list_command(index)` in `plan_read.py`; the existing probe test that pins the initiatives argv was updated for `-a` (spec change). Guard test: `tests/runner/test_cf_commands_defined_once.py` (excludes `-p`, which `sq` also uses). `FakeCf` still answers `[]` by default, which the new probe accepts.

- [x] `plan_read.py` defines once: `CF_EXECUTABLE`, `CF_PROJECT_FLAG`, `CF_JSON_FLAG`, the status command, the initiatives command with `-a`, and a function building the slice-list command for an index. `probes.py` imports them and no longer defines them
- [x] The initiatives probe now fails unless `parse_initiatives` accepts the output. `cf status` keeps 122's top-level object check
- [x] Tests: the probe passes on the captured initiatives fixture and fails on a document missing `index`; the probe invokes `list initiatives --json -a -p <id>`; existing probe tests still pass; the stub `cf` in `tests/cf_stub.py` answers `-a` (update its argument check and its good initiatives output to the captured shape)
- **Success Criteria**:
  - [x] Probe and stub tests pass; no CF command string is defined outside `plan_read.py`. Commit: `feat: probe initiatives with the plan model`

---

## Section 5: The lifecycle model

### Task 5.1: `LifecycleStep` and the step map, with tests
**Owner**: Junior AI | **Dependencies**: 4.2 | **Effort**: 3

Per the LLD, D3. Create `runner/lifecycle/steps.py` and `tests/runner/lifecycle/__init__.py`, `tests/runner/lifecycle/test_steps.py`.

Implementation note: `reported_complete` (plan.py) now takes a `PlanEntryLike` protocol (`is_checked`, `status`) so `PlanObservation` reuses the one rule; `PlanObservation(is_checked, status=None, arch_file=None, slice_list_read=False)`. Pipeline names are the constants `PIPELINE_P4/P5/P6`.

- [x] `LifecycleStep` `StrEnum` with the seven values of D3. `StepLevel` (initiative, slice) and `Executor` (`pipeline`, `human`) enums. Frozen `StepSpec(level, executor, pipeline)`, where `pipeline` is set if and only if the executor is `pipeline`; construction enforces it
- [x] `STEP_MAP: Mapping[LifecycleStep, StepSpec]` exactly as the D3 table (pipelines `P4`, `P5`, `P6`). Read-only mapping
- [x] Completion predicates, one per step, defined once: `architecture` (initiative has an arch file), `slice_plan` (slice list read successfully), `slice_design`/`tasks`/`implementation`/`merge` (reported complete, from Task 3.2), `integration` (initiative `is_checked`). A function `step_complete(step, observation)` over a small frozen `PlanObservation` holding the entry's fields and whether its slice list was read
- [x] Helper `steps_at(level)` returning the steps of a level in map order, used by reconcile to create children
- [x] Tests: every step has a spec; pipeline is set exactly for `slice_design`, `tasks`, `implementation`; a `StepSpec` with a pipeline on a human executor (and the reverse) raises; each predicate true and false case, including `architecture` with no arch file, `slice_plan` with an unread list, `integration` from `is_checked` and not from `status`; `steps_at` returns three initiative steps and four slice steps
- **Success Criteria**:
  - [x] Tests pass. Step values and names appear nowhere else as literals. Commit: `feat: add lifecycle step vocabulary and step map`

### Task 5.2: `LifecycleTree` basics, with tests
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 3

Per the LLD, D1, D4 and "API Contracts". Create `runner/lifecycle/tree.py` and `tests/runner/lifecycle/test_tree.py`, with a builder in `tests/runner/lifecycle/tree_support.py` that makes nodes through `Store.open_temporary()` and returns `LifecycleTree(store.nodes_for_project(...))`.

Implementation note: `tests/runner/lifecycle/tree_support.py` holds `TreeBuilder` (initiative/slice/step creation, `done`, `block`, `orphan`, `fresh`, `tree`). Nodes are immutable snapshots, so tests re-read a node with `fresh()` after changing it. `link_key(node)` is a module function in `tree.py`.

- [x] `LifecycleTree(nodes)`: frozen view, no I/O. Indexes by `(kind, cf.project, cf.index)` for linked nodes and by parent for children. Properties `nodes` and methods `children(node)`, `parent(node)`, `find_linked(kind, cf_project, index)`, `step_of(node) -> LifecycleStep | None` (from `cf.phase` on a `phase_or_artifact` node; `None` otherwise; an unrecognized phase raises `ValueError`)
- [x] `is_linked(node)`: true when the node and every ancestor has a non-null `cf.index`, except step nodes (which have no index) that are linked through their parent. A node with an unlinked ancestor is not linked
- [x] Tests: lookup by link key distinguishes initiative 120 from slice 120 and two CF projects; `step_of` on step, slice and initiative nodes; `is_linked` true for a linked step under linked parents, false for a step under an orphan (index cleared) and false for an unlinked initiative; an invalid `cf.phase` raises
- **Success Criteria**:
  - [x] Tests pass. No store import beyond node models in `tree.py`. Commit: `feat: add lifecycle tree with link lookup`

### Task 5.3: `predecessors` and `predecessors_done`, with tests
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 4

Per the LLD, D4 (table, eligible slice, "previous means by ascending index"). Create `runner/lifecycle/predecessors.py` and `tests/runner/lifecycle/test_predecessors.py`.

Implementation note: a required predecessor step that does not exist yet is omitted by `predecessors` but makes `predecessors_done` false (reconcile creates missing steps), and `predecessors` raises `ValueError` for a non-step node.

- [x] `predecessors(tree, node) -> tuple[Node, ...]` implements the D4 table, one rule per step. This is the only place that says what a step waits for. Module direction is fixed to avoid a circular import: `predecessors.py` imports `LifecycleTree` from `tree.py` only under `TYPE_CHECKING` and uses the tree through its methods; `tree.py` imports `predecessors.py` at module level (Task 5.4 uses it)
- [x] Eligible slice: a linked slice that has step children. A `deferred` or `deprecated` slice has none (D6), so it is skipped; orphans are excluded too. "Previous" is the eligible slice with the next lower `cf.index` in the same initiative
- [x] `integration` waits on `slice_plan` and on `merge` of every eligible slice in its initiative
- [x] `predecessors_done(tree, node)`: true when every predecessor is `done`
- [x] Tests, one per table row: `architecture` has none; `slice_plan` waits for architecture; `slice_design` waits for `slice_plan` of the initiative; `tasks` waits for `slice_design`; `implementation` waits for `tasks` and for the previous slice's `merge`, and the first slice waits only for `tasks`; `merge` waits for `implementation`; `integration` waits for all eligible merges. Also: slice n+1's `slice_design` does not wait for slice n; an orphaned slice and a stepless slice are skipped as "previous"; ordering follows `cf.index` not creation order; an unknown-status slice (steps present) holds the next slice's `implementation`
- **Success Criteria**:
  - [x] Tests pass. `predecessors_done` is true for a step with no predecessors. Commit: `feat: add lifecycle predecessor function`

### Task 5.4: `ready_steps`, with tests
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

Per the LLD, D4 (`ready_steps`). Edit `tree.py` (it imports `predecessors_done` from `predecessors.py`, per Task 5.3); tests in `tests/runner/lifecycle/test_ready_steps.py`.

- [x] `LifecycleTree.ready_steps()` returns step nodes that are `runnable`, linked, have no blocked ancestor, and whose predecessors are done. Pure, over the tree only. Docstring states the later narrowing (124 drive/hold, 125 journal and checkout, 128 gates)
- [x] Tests: a fresh first initiative's `architecture` is ready and its `slice_plan` is not; marking `architecture` done readies `slice_plan`; a blocked step and a step with a blocked parent are not ready; nothing under an orphan is ready; slice n+1's `implementation` is not ready until slice n's `merge` is done, while its `slice_design` is ready once `slice_plan` is done; a `done` step is not ready; the result is deterministic for the same tree
- **Success Criteria**:
  - [x] Tests pass; `uv run pyright` strict clean. Commit: `feat: add lifecycle ready steps`

---

## Section 6: The plan read

### Task 6.1: `plan_read_interval_seconds` and `--plan-read-interval`, with tests
**Owner**: Junior AI | **Dependencies**: 5.4 | **Effort**: 2

Per the LLD, D7 and "Settings and CLI". Edit `process/settings.py`, `cli/settings_flags.py`, `runner/factory.py`, `tests/test_settings_flags.py`, `tests/runner/test_factory.py`. Follow how `--run-poll-interval` and its bounds check were added in 122.

Implementation note: the positive-bound check is `validate_settings` in `runner/factory.py`, which `runner_tenant()` calls; it now lists `plan_read_interval_seconds`.

Verified by the Project Manager: committed (feat: add plan read interval setting); tests, ruff and pyright clean; `--help` lists the flag (tested).

- [x] `ProcessSettings.plan_read_interval_seconds` default 30.0, with an attribute doc; the default appears only in `settings.py`
- [x] `amoeba start --plan-read-interval` overrides it
- [x] `runner_tenant()` adds the field to its positive-value bounds check, raising `StartupFailedError` naming the field
- [x] Tests: the flag overrides the field; an absent flag leaves the default; a non-numeric value is a usage error as for the existing flags; zero and a negative value each fail `runner_tenant()` with the field named
- **Success Criteria**:
  - [x] Tests pass; `--help` lists the flag. Commit: `feat: add plan read interval setting`

### Task 6.2: Extend the stub `cf` for plan reads
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 3

Per the LLD, "Technology Choices". Edit `tests/cf_stub.py` (if it passes ~300 lines, move scripts to `tests/cf_stub_plan.py`); extend `tests/test_cf_stub*.py` or add `tests/test_cf_stub_plan.py`.

Implementation note: the missing-slice error document is printed on stderr (see Task 3.1 finding). Numbered sequences also work for `initiatives.<n>.json`; the last numbered file repeats once exhausted. Tests: `tests/runner/test_cf_stub_plan.py`.

- [x] `cf list initiatives --json -a -p <id>` and `cf list slices <index> --json -p <id>` answer from a directory named by `CF_STUB_PLAN_DIR`: `initiatives.json` and `slices-<index>.json`. A missing `slices-<index>.json` prints the captured error document (Task 3.1) and exits 1
- [x] "Next answer" support: when `slices-<index>.<n>.json` files exist, successive calls answer from them in order (a counter file in the plan dir), so a test can change the plan between reads
- [x] Existing modes (`GOOD`, `EMPTY`, `WRONG_FORM`, `FAIL`, `SLEEP`) still apply to the new commands. `CF_STUB_LOG` records each call
- [x] Tests: each command answers from the dir; the missing-file error document; the numbered sequence advances; a failure mode applies to a slice read; the log records both commands
- **Success Criteria**:
  - [x] Existing stub users pass unchanged. New tests pass. Commit: `test: add plan reads to the stub cf`

### Task 6.3: One link's plan read under the budget, with tests
**Owner**: Junior AI | **Dependencies**: 6.2 | **Effort**: 5

Per the LLD, D5 (read scoping), D7 (cut-off), D8 (error document). Add the read to `runner/lifecycle/plan_read.py` (Task 4.2) and create `tests/runner/lifecycle/test_plan_read.py`. Make every call through `run_cf` from `runner/cf_call.py` (Task 4.1).

Implementation note: `plan_read.py` also has `cf_argv(command, cf_project_id)` (probes use it). `SliceList` is the existing `CFSliceList`. A non-zero slice read is classified from both streams, stdout first, because CF prints the error document on stderr (Task 3.1 finding); a parseable error document on either stream is an error document. Tests: `tests/runner/lifecycle/test_plan_read.py`.

- [x] Result types, frozen: `PlanRead` (a complete read: the initiatives, and for each initiative a `SliceList`, `NoSlicePlan` or `SliceReadFailed(detail)`), `PlanReadFailed(detail)` (the initiatives read failed, or a slice error needed escalation), `PlanReadCutOff`. `type PlanReadResult` is their union
- [x] `read_plan(cf_project_id, linked_slice_initiatives, run, budget, timeout_seconds)`: initiatives first, then each initiative's slice list, each a separate call that checks `budget.allows_call()` first. Any refusal returns `PlanReadCutOff` and nothing else. `linked_slice_initiatives` is the set of initiative indexes that already have linked slice nodes
- [x] An error document (exit 1, `error: true`) from a slice read means: no linked slices under that initiative gives `NoSlicePlan`; linked slices give `SliceReadFailed` naming the initiative. The decision never reads the error's `message`
- [x] Timeout, non-zero exit without an error document, and parse failure of a slice read give `SliceReadFailed`; the same on the initiatives read gives `PlanReadFailed`. Detail names the command and the head of the output (`OUTPUT_HEAD_CHARS` from `cf_call.py`). Never retried in the tick
- [x] Tests with an injected runner returning canned `CompletedProcess` values from the captured fixtures: complete read; no-plan initiative without linked slices; the same with linked slices is `SliceReadFailed`; each failure kind for both read levels; cut-off before the first call, between initiatives and mid-way, each returning `PlanReadCutOff` with no result for earlier calls; a read that would pass the deadline starts no further call
- **Success Criteria**:
  - [x] Tests pass. Every call is preceded by a budget check. Commit: `feat: add budgeted plan read for one CF link`

### Task 6.4: Plan read cadence and early trigger, with tests
**Owner**: Junior AI | **Dependencies**: 6.3 | **Effort**: 4

Per the LLD, D7 (interval, early read) and D8 (closure state). Create `runner/lifecycle/cadence.py` and `tests/runner/lifecycle/test_cadence.py`.

Implementation note: schedule state is keyed by `(project_id, cf_project_id)`, so `record_complete`, `record_failed`, `record_cut_off` and `last_failed` take both (the spec's `(link)` alone would merge two Amoeba projects linking one CF project). A failed read does not restart the interval (D7: interval runs from the last *complete* read), so a failed link is due on every call until a read completes. `due` takes `LinkSnapshots` = the `(latest, latest_observed)` tuple from `store.latest_cf_snapshots`.

- [x] `PlanReadSchedule(interval_seconds, clock)`: in-memory state per link: last complete read time, last observed snapshot id seen, whether the last read failed. `due(project_id, link, snapshots) -> bool`: true on first sight, when the interval has passed, or when the latest observed snapshot's id differs from the last one seen and its `changed` list is non-empty. `snapshots` is the tuple from `store.latest_cf_snapshots`
- [x] A failed snapshot (`changed` null) is never the latest observed row and so triggers nothing; a recovery with `changed: []` updates the seen id and triggers nothing. `record_complete(link)`, `record_failed(link)`, `record_cut_off(link)` (leaves the link due), and `last_failed(link)` for the closure rule (Task 9.3)
- [x] Tests with an injected clock: due on first call; not due before the interval and due at it; a changed snapshot makes it due now; the same snapshot id twice is not a second trigger; failed snapshot and `changed: []` make no early read; a cut-off read stays due next call; `last_failed` is set by a failure and cleared by a complete read; two links are independent
- **Success Criteria**:
  - [x] Tests pass; no sleeping. Commit: `feat: add plan read cadence and snapshot trigger`

---

## Section 7: Fault vocabulary

### Task 7.1: New fault kinds and payload keys, with tests
**Owner**: Junior AI | **Dependencies**: 6.4 | **Effort**: 2

Per the LLD, D8. Edit `runner/faults.py` and `tests/runner/test_faults.py`.

Implementation note: payload constants are `PAYLOAD_CF_PROJECT_ID`, `PAYLOAD_INDEX`, `PAYLOAD_FORMER_INDEX`, `PAYLOAD_FORMER_SLICE_NAME`, `PAYLOAD_STATUS`, `PAYLOAD_STEP` in `runner/faults.py`. The pinned vocabulary test in `tests/runner/test_launch_ids.py` was updated for the three new kinds.

- [x] `FaultKind` gains `plan_read_failed`, `lifecycle_orphan`, `plan_status_unknown`
- [x] Payload key constants defined once next to `PAYLOAD_FAULT_KIND`: `former_index`, `former_slice_name`, `cf_project_id`, `index`, `status`, `step`
- [x] Docstring marks `plan_read_failed` as project-scoped only, and the other two as node-scoped block payload kinds
- [x] Tests: the three members exist with the exact string values; a `Fault` of kind `plan_read_failed` raises one project escalation and a repeat adds no row (existing `raise_expected_faults` path)
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: add plan read fault kinds`

---

## Section 8: Reconcile

All tests in this section run against `Store.open_temporary()` with hand-built `PlanRead` values and a helper `tests/runner/lifecycle/reconcile_support.py` that builds a plan (initiatives, slice lists). Per the LLD, D5 and D6. `reconcile(store, project_id, cf_project_id, read, faults) -> bool` (whether anything was written), where `faults` is the tick's `TickFaults` (`runner/faults.py`): reconcile adds the `plan_read_failed` faults found by the read checks to it, while orphan and unknown-status blocks are direct store writes, not faults in it. It is the entry point; runs the rules in the fixed order orphan → create → update → complete. It is first created in Task 8.3, so the tests of 8.1 and 8.2 call their rule functions directly (`checked_scope`, then the orphan function), and later tasks call `reconcile`.

### Task 8.1: Read checks (safety rules), with tests
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 4

Per the LLD, D5 "Safety rules". Create `runner/lifecycle/read_checks.py` and `tests/runner/lifecycle/test_read_checks.py`.

Implementation note: `checked_scope(tree, cf_project_id, read: PlanRead | PlanReadFailed) -> ReadScope(initiatives, slice_initiatives, faults)`. A `NoSlicePlan` initiative is neither in `slice_initiatives` nor a fault. A duplicate initiative index or an empty initiatives list with linked initiatives refuses the whole link. The cut-off result is handled by the caller (applies nothing). Shared test builders: `tests/runner/lifecycle/reconcile_support.py` (`cf_initiative`, `cf_slice`, `slice_list`, `plan`).

- [x] `checked_scope(tree, cf_project_id, read) -> ReadScope`: the initiatives whose slice lists may be applied, whether the initiatives read may be applied, and the faults to raise. A duplicate initiative index, two initiatives listing one slice index, or a repeated index inside one list makes that read `plan_read_failed` naming the index and applies nothing for its scope
- [x] An empty initiatives list while linked initiative nodes exist, or an empty slice list while that initiative has linked slices, is `plan_read_failed` naming the linked count, not a mass orphaning. An empty list with no linked nodes is valid
- [x] A `SliceReadFailed` removes only that initiative from the scope and adds one fault; a `PlanReadFailed` removes the whole link
- [x] Tests (`test_empty_list_with_linked_nodes_orphans_nothing` lives in Task 8.2): duplicate initiative index; the same slice index under two initiatives; a repeat inside one list; empty initiatives with and without linked nodes; empty slice list with and without linked slices; a failed slice read narrows only its initiative; a failed initiatives read removes everything
- **Success Criteria**:
  - [x] Tests pass; the module touches no store writes. Commit: `feat: add plan read safety checks`

### Task 8.2: Orphan rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 5

Per the LLD, D5 step 1 and D2 (orphaning). Create `runner/lifecycle/orphaning.py`; tests in `tests/runner/lifecycle/test_orphaning.py`.

Implementation note: entry point is `orphan_unlisted(store, tree, cf_project_id, read, scope) -> bool`. **Departure from the LLD's order:** the block is written before `cf.index` and `cf.slice_name` are cleared (the LLD says clear, then block). A crash between the two writes then leaves a node that is blocked and still linked, which the next read finishes; the LLD order would leave an unlinked, unblocked node that no later read could find. A slice whose parent initiative is itself unlinked, and which CF lists under a linked initiative, is treated as a move and orphaned, so its index cannot collide with the recreated slice. Block payloads live on the escalation message (`TreeBuilder.escalation_payloads`).

- [x] A linked initiative missing from a successful initiatives read, a slice missing from every successful slice read whose own initiative's read succeeded, and a slice listed under a different initiative from its parent are each orphaned
- [x] Orphaning clears `cf.index` and `cf.slice_name` in one `update_cf_reference` call, then blocks a node that is neither blocked nor done on `HUMAN` with context `orphaned: CF no longer reports index <n>` and payload `{fault_kind: lifecycle_orphan, cf_project_id, former_index, former_slice_name}`. A done node is unlinked, not blocked, and logs INFO. An already-blocked node keeps its open escalation, is unlinked, and logs a WARNING naming the former index
- [x] Descendants are not touched; a step under an orphan is unlinked through `is_linked` only
- [x] Tests, calling `checked_scope` then the orphan function on nodes staged in the store: a renumbered slice (index no longer listed) is orphaned once (the new node's creation is tested in Task 8.3); a moved slice orphaned; a completed slice leaving the plan is unlinked and not blocked; an already-blocked orphan keeps one escalation; the payload carries the former values; `test_empty_list_with_linked_nodes_orphans_nothing`; a failed slice read orphans none of that initiative's slices; an unlinked node is never re-orphaned on the next read (idempotent)
- **Success Criteria**:
  - [x] Tests pass. Nothing is deleted. Commit: `feat: orphan nodes CF no longer reports`

### Task 8.3: Create rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.2 | **Effort**: 4

Per the LLD, D1 (display data), D2 (`slice_name` stem rule), D6 (statuses at creation). Create `runner/lifecycle/reconcile.py` (the only `create_node` caller) with the `reconcile` entry point calling orphan then create; tests in `tests/runner/lifecycle/test_reconcile_create.py`.

Implementation note: `slug` rule is `slice_name_from_design_file` in `slugs.py` (name between `nnn-slice.` and `.md`, e.g. `the-design`, matching the review frontmatter `slice`). `reconcile(store, project_id, cf_project_id, read: PlanRead | PlanReadFailed, faults)` adds the read checks' faults to `faults`. A deferred/deprecated slice never gets new steps; a slice with steps keeps them. Test plan helper: `_fixture_plan(slices_100=..., slices_120=...)` in `test_reconcile_create.py`.

- [x] An initiative with no linked node gets an initiative node (title from `name`, `cf.project`, `cf.index`, `cf.artifact_path` from `archFile`) and then its `architecture`, `slice_plan`, `integration` steps. A slice listed under a read initiative with no linked node gets a slice node under that initiative, then its four steps. A linked node missing a step child gets only that step. Step nodes carry `cf.project`, a null index and `cf.phase` set to the step value; titles are the step value
- [x] `slice_name` comes from the `{index}-slice.` stem of `designFile` (the stem rule is defined once in `runner/lifecycle/slugs.py`). A `designFile` of another form leaves it null and logs a WARNING naming the file. No `designFile` leaves it null. Amoeba never builds a slug
- [x] Statuses (D6): a step is created `done` if its completion predicate (Task 5.1) holds, else `runnable`; a container node is `runnable`. A slice reported `deferred` or `deprecated` gets a node and no steps, and gains steps on a later read with another status
- [x] Each check-before-write: a rerun of the same read writes nothing
- [x] Tests: linking a project whose fixture plan has initiative 100 (checked) and 120 with slices: node counts, step sets per level, every step in 100's subtree `done`, every node carrying its index; initiative with no `archFile` gets a runnable `architecture`; `in_progress` slice gets four runnable steps; `slice_name` for the stem, an odd file name (WARNING, null), and no file; deferred slice has no steps and gains them later, a slice with steps keeps them when later deferred; `test_renumber_yields_one_orphan_and_one_new_node` (one orphan escalation, one new linked node, the orphan's index and `slice_name` cleared); rerunning writes nothing; a slice listed under the other initiative is orphaned and recreated
- [x] Guard test in `tests/test_create_node_guard.py` (follow `tests/test_writer_guard.py`: walk the AST of `src/amoeba`, not a text search): fails if any module other than `runner/lifecycle/reconcile.py` calls `create_node`. A self-test shows a synthetic module calling it (source string parsed with `ast`) is detected
- **Success Criteria**:
  - [x] Tests pass. Adding a `create_node` call elsewhere in `src/amoeba` fails the guard. Commit: `feat: create initiative, slice and step nodes from the plan`

### Task 8.4: Unknown-status block, with tests
**Owner**: Junior AI | **Dependencies**: 8.3 | **Effort**: 3

Per the LLD, D6 ("An unknown status") and D8 (`plan_status_unknown` is node-scoped). A rule run on every read, not only at creation, so a block the PM resolved is restored. Create `runner/lifecycle/status_block.py`, called by `reconcile` after the create rule; tests in `tests/runner/lifecycle/test_status_block.py`.

Implementation note: `block_unknown_status(store, tree, cf_project_id, read, scope) -> bool` runs in `reconcile` after the create rule, on a tree rebuilt when anything was created. Only slices are blocked (D6); an initiative with an unknown status is not.

- [x] A linked slice whose CF status is unknown (`degraded` or outside the vocabulary) gets four `runnable` steps if it has none (the create rule does this), and the slice node is blocked on `HUMAN` with payload `{fault_kind: plan_status_unknown, index, status}` when it is neither blocked nor done. `plan_read_failed` is not raised
- [x] Tests: a new `degraded` slice is created with four steps and blocked once; a second identical read writes nothing; the PM resolves the block while the status is still unknown and the next read blocks it again; once CF reports a known status the node is not blocked again; a `done` slice is not blocked; an out-of-vocabulary value blocks with its raw text in the payload; the next slice's `implementation` is not ready while the unknown slice's `merge` is not done
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: block slices with an unknown plan status`

### Task 8.5: Update rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.4 | **Effort**: 2

Per the LLD, D2 (rename) and D5 step 3. Edit `reconcile.py`; tests in `tests/runner/lifecycle/test_reconcile_update.py`.

Implementation note: the rule is `update_references` in a new `runner/lifecycle/references.py` (called by `reconcile`; `reconcile.py` stays the only `create_node` caller). CF supplying no `archFile`/`designFile` is treated as no information, so existing values are kept (slice 125 sets `slice_name` before CF lists a design file). An odd new design file updates `artifact_path`, keeps `slice_name` and logs a WARNING. Tests: `test_reconcile_update.py`.

- [x] A linked node whose `slice_name` or `artifact_path` differs from CF's is updated through `update_cf_reference`, replacing only those fields (project, index, phase kept). Titles are never updated
- [x] Tests: a renamed slice keeps its node id and link and raises no orphan escalation; a changed `designFile` updates `slice_name` and `artifact_path`; a changed `archFile` updates an initiative; an unchanged read writes nothing; a changed title alone updates nothing
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: update node CF references on plan edits`

### Task 8.6: Complete rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.5 | **Effort**: 4

Per the LLD, D5 step 4 and D3. Create `runner/lifecycle/completion.py`; tests in `tests/runner/lifecycle/test_completion.py`.

Implementation note: `complete_observed_steps(store, tree, project_id, cf_project_id, read, scope)` in `completion.py`, called on a freshly built tree. The crash test (`test_reconcile_crash.py`) fails the k-th store write for all 28 writes of a first-link reconcile; a fresh reconcile reaches the uninterrupted tree each time. The block-before-unlink order in the orphan rule (Task 8.2) is what makes that hold.

- [x] For each linked step whose completion predicate holds: `runnable` with no unresolved journal entry becomes `done`; `blocked_on_human` with a human executor is resolved by `resolve(resolved_by="runner", detail="observed: <predicate>")` and then marked `done`; anything else (in-flight, blocked pipeline step, unresolved entry) is left alone
- [x] Steps already `done` are untouched. A crash between the resolve and the status write is repaired by the next pass (the block is already resolved, the step runnable)
- [x] Tests, no-slice-plan state: an initiative whose slice read is `NoSlicePlan` keeps `slice_plan` runnable and raises no fault; a later read that returns a slice list completes `slice_plan`; `architecture` completes when an `archFile` appears
- [x] Tests: runnable step with a true predicate is done; a step with an unresolved journal entry is not; a blocked human step is resolved by `runner` then done; a blocked pipeline step is left; `merge` completes from the slice being reported complete; `integration` completes from `isChecked` and not from status; the crash-between-writes case, simulated by resolving first and then running the rule, finishes with one resolved block and a done step; a done step is untouched
- [x] Crash repair (D5 "Failures during reconcile"), in `tests/runner/lifecycle/test_reconcile_crash.py`, now that every rule exists: wrap the store so the k-th write raises, for every k across a first-link reconcile; a fresh `reconcile` on the same store afterwards completes the tree with no duplicate linked nodes and the same final tree as an uninterrupted run
- **Success Criteria**:
  - [x] Tests pass; `reconcile` runs orphan → create → update → complete. Commit: `feat: complete observed lifecycle steps`

---

## Section 9: Tick wiring

### Task 9.1: Put the lifecycle tree in `ProjectView`, with tests
**Owner**: Junior AI | **Dependencies**: 8.6 | **Effort**: 3

Per the LLD, "API Contracts" (`ProjectView` gains `tree`, which replaces the flat runnable list). Behavior-preserving: no plan read yet. Edit `runner/decide.py`, `runner/tick.py`, `tests/runner/tick_support.py` and the four test planners that read `view.runnable_nodes` (`grep -rn runnable_nodes tests src`).

Implementation note: `runnable_unbusy` is in `tests/runner/tick_support.py`; the four planners (tick_support, test_end_to_end, crash_entry, test_tenant) and `test_decide.py` use it / `LifecycleTree(())`. New tests: `test_tick.py::test_the_view_tree_holds_every_node_of_the_project` and two view-build failure tests in `test_tenant.py` (the one catch is the tenant's).

- [x] `ProjectView.tree: LifecycleTree` replaces `runnable_nodes` (no default; a missing tree fails loudly). `ProjectTick._decide` builds it from `store.nodes_for_project(project)` and no longer computes the busy list
- [x] Add `runnable_unbusy(view)` to `tests/runner/tick_support.py` (see "Task-level additions") and switch the four test planners to it
- [x] A failure while building the view follows 122's catch (store failures re-raise; anything else reaches the one catch), and Decide does not run for that project that tick (D5)
- [x] Tests: 122's tick, tenant, end-to-end and crash tests pass unchanged in behavior (a node with an unresolved entry is still not launched twice); `view.tree` holds every node of the project; a store failure while building the tree re-raises; another exception raises one project-scoped `unexpected_fault` and no action is taken
- **Success Criteria**:
  - [x] Full runner tests, `ruff` and `pyright` pass. Commit: `refactor: give ProjectView the lifecycle tree`

### Task 9.2: Plan read and reconcile in the project tick, with tests
**Owner**: Junior AI | **Dependencies**: 9.1, 8.6, 6.4 | **Effort**: 5

Per the LLD, "Data Flow", D5, D7 (polling first, which links), D8 (closure), D11. Edit `runner/tick.py`, `runner/factory.py`/`runner/tenant.py` (pass the schedule and settings through), `tests/runner/tick_support.py`; tests in `tests/runner/test_tick_plan.py`, `tests/runner/test_tick_plan_faults.py` and `tests/runner/test_budget_coverage.py`.

Implementation note: the stage is `PlanStage` in `runner/lifecycle/plan_stage.py` (owns the `PlanReadSchedule`, the failure replay and the per-link read/reconcile); `ProjectTick` takes `plans=`, and `RunnerTenant` builds it from `plan_read_interval_seconds`, `cf_run` and the call timeout. A failed link stays due (D7: interval runs from the last *complete* read) so it is retried every tick and replays its `plan_read_failed` faults. Test support: `FakeCf.replies` (per command key, optional `@<cf project>` suffix), `tests/runner/plan_tick_support.py`, `Rig.planners`. Budget coverage cases added to `test_budget_coverage.py`.

- [x] In `ProjectTick.run`, after in-flight polling and the probe check (the `[reconciliation reads - slice 123]` slot): for each link whose probe passed and for which the schedule says due, run `read_plan` with the remaining budget. `PlanReadCutOff` applies nothing, logs a WARNING naming the link, records nothing, and returns the link to due. `PlanReadFailed` calls `record_failed` and adds a `plan_read_failed` fault. A complete read goes through `reconcile`, then `record_complete` (a read with any slice-level failure counts as failed). The tree in `ProjectView` is built after reconcile
- [x] Closure (D8): a link whose last plan read failed counts as a `plan_read_failed` recurrence on every tick until a read of that link succeeds, as `LinkProbes` does for a failed probe. A failure for a link the project no longer has is not replayed
- [x] A plan read never runs for a link that failed its probe. Polling and its budget come first, so a cut-off poll leaves no plan read
- [x] Tests (injected clock, runner and stub): first tick reads and reconciles and `ProjectView.tree` shows the new nodes; the next tick before the interval reads nothing; after the interval a new slice in the plan's next answer gets a node while `projects.json` is unchanged; a changed snapshot triggers an early read; a cut-off read applies nothing, raises no fault and is read again on the next tick; a run's poll is never cut off by the plan read in the same tick; a probe-failed link is not read; a failed initiatives read raises one `plan_read_failed`, which stays open on later ticks that do not read and closes on the tick of the next successful read of that link; an empty-list-with-linked-nodes read, a duplicate index and a slice read error with linked slices each raise one `plan_read_failed` and orphan nothing; a failed slice read for one initiative leaves another initiative's slices applied; two links in one project keep independent state; a repeating fault adds no rows; a tick with the (empty) production planner tuple creates nodes, launches nothing, blocks no human step and raises no fault
- [x] Budget coverage: extend `test_budget_coverage.py` so its failing runner and `Popen` also drive a tick through the plan read with the budget exhausted before the initiatives read and between slice reads. Neither is called after the deadline and nothing is written for the link
- **Success Criteria**:
  - [x] Tests pass, and 122's tick, probe, tenant and end-to-end tests pass. Commit: `feat: read and reconcile the plan in the project tick`

### Task 9.3: Reconcile exceptions, with tests
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 2

Per the LLD, D5 (failures during reconcile). Edit `runner/tick.py`; tests in `tests/runner/test_tick_plan_faults.py`.

Implementation note: `ProjectTick._plan_reads` clears the node context first, so a reconcile exception takes the tenant's project-scoped path rather than blocking a node left in context by polling. Because the catch is the tenant's, the three tests are in `tests/runner/test_tenant.py` (not `test_tick_plan_faults.py`); `tests/runner/lifecycle/crash_support.py` has `fail_nth_write` / `restore_writes`.

- [x] Store failures (`STORE_FAILURES`) mid-reconcile re-raise. Any other exception stops this link's reconcile, leaves the link due (it is not recorded complete), and reaches 122's one catch (a project-scoped `unexpected_fault`, no node in context). Decide does not run for that project that tick
- [x] Tests: an exception injected into reconcile after the k-th write raises one `unexpected_fault`, leaves the link due, and the next tick completes the tree with no duplicates; the same exception every tick adds no rows; a store failure propagates
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: leave a link due after a reconcile exception`

---

## Section 10: Human steps

### Task 10.1: `HumanStepPlanner` and `BlockHumanStep`, with tests
**Owner**: Junior AI | **Dependencies**: 9.3 | **Effort**: 4

Per the LLD, D9. Create `runner/lifecycle/human_steps.py`; edit `runner/decide.py` (`Action` union), `runner/tick.py` (Act); tests `tests/runner/lifecycle/test_human_steps.py` and `tests/runner/test_tick_human_steps.py`.

Implementation note: `BlockHumanStep` is in `runner/decide.py`; `HumanStepPlanner` and `block_human_step(store, action)` are in `runner/lifecycle/human_steps.py`; `ProjectTick._act` dispatches with `match` (the budget is checked only for `LaunchRun`). Tests: `tests/runner/lifecycle/test_human_steps.py`, `tests/runner/test_tick_human_steps.py`.

- [x] `BlockHumanStep(node_id)` frozen dataclass; `type Action = LaunchRun | BlockHumanStep`. `decide` still raises on two actions for one node
- [x] `HumanStepPlanner.plan(view)` returns a `BlockHumanStep` for each step in `view.tree.ready_steps()` whose `STEP_MAP` executor is `human`. One small class with no abstraction around it
- [x] Act applies a `BlockHumanStep` as one `store.block(node_id, kind=HUMAN, context="<step> is a human step", payload={step, cf_project_id, index})`, where `index` is the initiative's or slice's CF index. It is not journaled and does not call the launch path. A comment records "store-only actions are applied in one transaction and not journaled" (D9)
- [x] The production planner tuple stays empty (register nothing). A test asserts it
- [x] Tests: the planner returns actions for a ready human step and for nothing else; with the planner in a test tuple, `architecture` on an initiative with no `archFile` is `blocked_on_human` on that tick with the payload; `merge` after `implementation` is done is blocked; when the predicate becomes true the next read resolves the block by `runner` and the step is `done`; a person resolving the block without doing the work gets it blocked again on the next tick; a step under an orphan or already blocked gets no action; a pipeline step gets none; the production tuple is empty
- **Success Criteria**:
  - [x] Tests pass. Nothing launches. Commit: `feat: block human steps through a planner action`

---

## Section 11: Contract text and final validation

### Task 11.1: Contract documents
**Owner**: Junior AI | **Dependencies**: 10.1 | **Effort**: 3

Per the LLD, "Provides to Other Slices" (Contract documents). Edit under `docs/`. Keep existing structure and anchors; the substrate-guide row links must still resolve.

Implementation note: store-contract gained "Lifecycle nodes and the CF index" (and the migrations paragraph names `010`); context-forge-contract gained "Plan reads (slice 123)" (shapes from the captured 0.19.17 fixtures, the stderr error document, the `indexSource` upstream ask, the `cf status` observations); process-contract gained "The plan read" and the flag, fault, probe edits; the substrate-guide 120 row links all three.

- [x] `store-contract.md`: `CFReference.index`, migration `010` and its partial unique index, `inspect nodes` showing the index, and the rule that only the Runner's reconcile creates nodes (the guard)
- [x] `context-forge-contract.md`: the two plan reads and their shapes, the error-document rule (D8, `code: UNKNOWN` observed), the `cf status` observations for 125 and 128 (`-p` without `--worktree` reports only project-level pointers; `--worktree` accepts the worktree id), and the explicit-index requirement with the `indexSource` upstream ask
- [x] `process-contract.md`: the plan-read setting and flag, the plan read stage, which projects are read, and how a read is cut off
- [x] `substrate-guide.md`: extend the 120 row with the lifecycle model and reconciliation, linking the new anchors
- **Success Criteria**:
  - [x] Each document states the points above. Links resolve (`grep -rn "](" docs | …` spot check on the changed anchors). Commit: `docs: add lifecycle model contract text`

### Task 11.2: CHANGELOG, architecture and slice-plan edits
**Owner**: Junior AI | **Dependencies**: 11.1 | **Effort**: 2

Per the LLD, "Special Considerations". Edit `CHANGELOG.md`, `project-documents/user/architecture/120-arch.runner-routing-engine.md`, `project-documents/user/architecture/120-slices.runner-routing-engine.md`. Preserve any "User-Provided Concept" section.

Implementation note: the arch and slice-plan edits listed here were already present when this task started (from the slice 123 design phase and later slice designs): no gate nodes and no CF-write executor (arch, lifecycle model paragraph), store-only actions not journaled (Observe/decide/act), Observe reads plans on an interval, the slice list is not a start-up probe, done or already-blocked orphan (arch, reconciliation rules); plan entry 4 wording, entry 5 (124) `HumanStepPlanner` criterion, and Future Work "Mark a step done" and "CF asks: indexSource". Each was verified by reading; only CHANGELOG.md changed, so `git diff --stat` for this commit touches that one file.

- [x] CHANGELOG `[Unreleased]` entry in the style of slice 122's: the lifecycle model and reconciliation, `plan_read_interval_seconds` and `--plan-read-interval`, migration `010`
- [x] Arch edits: no gate nodes in v1 (D3); no v1 step with a CF-write executor (D3); Observe reads every linked project's plan on an interval (D7); store-only actions are not journaled (D9); the slice list is not a start-up probe (D11); a done or already-blocked orphan does not get its own escalation (D5)
- [x] Slice plan, entry 4: "appears on the next plan read"; "triggers no early plan read"; steps are a pipeline or a human step; `cf status` left to 125 and 128; human-step criterion proven under a test planner; done or already-blocked orphan; entry 5 (124): register `HumanStepPlanner` with the drive filter, with a criterion; Future Work gains "Mark step done" and "CF `indexSource`"
- **Success Criteria**:
  - [x] Each listed edit is present and no unrelated text changed (`git diff --stat` touches only these three files). Commit: `docs: record slice 123 departures in the arch and slice plan`

### Task 11.3: Full validation and the verification walkthrough
**Owner**: Junior AI | **Dependencies**: 11.2 | **Effort**: 3

Per the LLD, "Verification Walkthrough". Run each command once and read its output.

Result (20261023): all gates clean. Walkthrough steps 3 and 4 passed; deviations and exact commands are recorded in the slice design's Verification Walkthrough. Gate failure found and fixed on the way: `tests/test_import_boundaries.py` rule 11 (commit `fix: import public names in the Runner and check its subpackages`).

- [x] `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`; then `uv run pytest tests/contract -v` and `uv run pytest tests/runner/lifecycle tests/upstream/test_cf_plan.py tests/store/test_migration_010.py -v`
- [x] Walkthrough step 3 with the real `cf` and a temporary `AMOEBA_STORE_DIR`: start, create the project, link this repository's CF project, then `amoeba inspect nodes` and `amoeba inspect messages --json`. Check against the LLD's expected output (initiative rows with indexes; steps under initiative 100 and slices 101–110 `done`; initiative 120's slices with four `runnable` steps each; later initiatives with a `runnable` `architecture`; no `plan_read_failed`, orphan or human-step blocks). Then `amoeba stop`
- [x] Walkthrough step 4 (LLD): copy this repository to a temporary directory, register it with `cf init`, link it as in step 3 and wait for the first read. Edit the name of slice 131 in the copy's `120-slices.runner-routing-engine.md`; after `plan_read_interval_seconds` check that `amoeba inspect nodes` shows the same node id still linked to index 131 and `inspect messages` has no orphan escalation. Change `(131)` to `(132)`; after the next read check for one `lifecycle_orphan` escalation naming former index 131, a new slice node 132 and the old node unlinked. Then `amoeba stop`. If `cf init` cannot run non-interactively, write `BLOCKED:` with its error under this task and stop
- **Success Criteria**:
  - [x] All gates clean. The walkthrough matches the expected output or the deviation is written in this task. Commit any fixes as `fix:` or `refactor:` and any notes as `docs:`
