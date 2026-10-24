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
dateUpdated: 20261024
status: not_started
turns: 33
promptTokens: 1938080
cachedTokens: 1802314
cacheWriteTokens: 135728
completionTokens: 39123
durationSeconds: 268.2
costUsd: 1.114739
usageRounds: 2
pricedRounds: 2
revision_number: 1
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

- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `123-slice.lifecycle-model-and-reconciliation` from the target. If it exists, switch to it
- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each. Record the passed-test count in this task
- **Success Criteria**:
  - [ ] On the slice branch. Baseline suite, `ruff` and `pyright` are clean. If not, write `BLOCKED:` with the failure and stop. No commit needed

---

## Section 2: Store contract changes (migration 010)

### Task 2.1: Migration `010` and `CFReference.index`, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

Per the LLD, D1 and "Database / Storage Schema". Create `store/schema/010_node_cf_index.sql` and `tests/store/test_migration_010.py` (follow `test_migration_009.py`). Edit `store/models.py`, `store/sql.py`, `store/nodes.py`, `store/mapping.py` and any row-values helper that lists the node columns (`grep -n "cf_slice\|COL_NODE_CF" src/amoeba/store/*.py`).

- [ ] SQL exactly as the LLD gives: `ALTER TABLE nodes ADD COLUMN cf_index INTEGER` and the partial unique index `idx_nodes_cf_link` on `(project_id, kind, cf_project, cf_index) WHERE cf_index IS NOT NULL`
- [ ] `CFReference` gains `index: int | None = None` (docstring: the store still never interprets it). Define the column-name constant once in `sql.py`. `create_node`, `update_cf_reference` and the node mapping read and write it
- [ ] Update the schema-version expectations the existing migration tests pin (`grep -rn "009\|SCHEMA_VERSION" tests src/amoeba/store/migrations.py`)
- [ ] Tests: migration applies to a populated v9 store, existing rows get a null `cf_index`, and node data is unchanged; a node round-trips `CFReference(index=…)`; `update_cf_reference` replaces the index; two nodes with the same `(project, kind, cf_project, cf_index)` raise `StoreIntegrityError`; the same index under a different kind, a different CF project, or a different Amoeba project is allowed; null indexes never collide
- **Success Criteria**:
  - [ ] New tests, the migration and store tests, `uv run pytest tests/contract -q`, `ruff` and `pyright` pass. Commit: `feat: add node cf_index with a partial unique link index`

### Task 2.2: `amoeba inspect nodes` shows the index, with tests
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 2

Edit `inspection/listing.py` and its tests in `tests/inspection/test_listing.py`. Follow how `cf_slice` and the other CF fields are shown.

- [ ] The nodes listing gains a `cf_index` column; `--json` output gains `cf.index` (null when unset)
- [ ] Tests: a node with an index shows it in both forms; a node without shows an empty cell and `null`; existing columns and JSON keys are unchanged
- **Success Criteria**:
  - [ ] Tests pass. Commit: `feat: show node cf index in inspect nodes`

---

## Section 3: Plan models and captured fixtures

### Task 3.1: Capture CF output fixtures
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 2

Per the LLD, "Technology Choices". The parser rule in CLAUDE.md requires real output. Reads against CF are pre-authorized and write nothing. Find this repository's CF project id with `cf list projects --json` (the entry whose `projectPath` equals the repo root). Record `cf --version` in `tests/fixtures/README.md`.

- [ ] Save, under `tests/fixtures/cf/`: `list_initiatives_a.json` (`cf list initiatives --json -a -p <id>`), `list_slices_120.json` (`cf list slices 120 --json -p <id>`), `list_slices_100.json`, and `list_slices_error.json` (`cf list slices 140 --json -p <id>`: exit 1, `{"error": true, …}`; save the stdout document)
- [ ] Failure paths: if no project entry matches the repo root, or any command fails other than the one expected error, write `BLOCKED:` with the command and its output and stop. If `cf list slices 140` returns a plan instead of an error, use another initiative from the initiatives fixture whose command exits 1 with an error document, and name the file after it in the README; if none does, `BLOCKED:` the same way
- [ ] Replace the machine-specific project id and absolute paths if any appear. Keep every key CF printed
- [ ] Add one line per file to `tests/fixtures/README.md`: command, CF version, capture date
- **Success Criteria**:
  - [ ] Four JSON files exist and parse with `json.load`. The error fixture has `error: true`. Commit: `test: capture CF plan read fixtures`

### Task 3.2: Plan models and parsers, with tests
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 4

Per the LLD, D12 and Component Structure. Create `upstream/context_forge/plan.py` and `tests/upstream/test_cf_plan.py`. Export through `upstream/context_forge/__init__.py` and update any public-API pin test (`grep -rn "context_forge" tests/*public*`). pydantic v2 is already a dependency.

- [ ] `PlanEntryStatus` `StrEnum`: `complete`, `in_progress`, `not_started`, `deprecated`, `deferred`, `degraded`. A status outside it parses to an explicit unknown value carrying the raw text (a small frozen dataclass), never a default
- [ ] Models with `extra="ignore"`: `CFInitiative(index, name, arch_file, is_checked, status)` and `CFSliceEntry(index, name, design_file, status, is_checked)` (aliases `archFile`, `designFile`, `isChecked`), `CFSliceList(entries)`, `CFErrorDocument(error: true, …)`. Required: `index`, `name`, `isChecked`, `entries`. Optional: `archFile`, `designFile`
- [ ] `parse_initiatives(text) -> list[CFInitiative]` and `parse_slice_list(text) -> CFSliceList | CFErrorDocument`. A missing required field, malformed JSON or wrong top-level form raises one `PlanParseError` naming the read, the entry index when one was parsed, and the pydantic message
- [ ] "Reported complete" predicate defined once here: `status == complete` or `is_checked`. A function `reported_complete(entry)` used by later tasks
- [ ] Tests, using the captured fixtures: initiatives parse with every index; `archFile: null` parses; slice list parses; the error fixture parses to `CFErrorDocument`; unknown extra fields are ignored; a missing `index`, a missing `entries` and a non-array initiatives document each raise `PlanParseError` with the read named; an out-of-vocabulary status is explicit-unknown with the raw value; `degraded` is its own member; `reported_complete` is true for `complete` and for `is_checked` alone, false otherwise
- **Success Criteria**:
  - [ ] Tests pass with real fixtures. `pyright` strict clean. Commit: `feat: add Context Forge plan models and parsers`

---

## Section 4: The probe set (D11)

### Task 4.1: Probe `cf list initiatives -a` with the full model and share the `cf` call, with tests
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 3

Per the LLD, D11. 122 already dropped the slices probe, so this swaps in the full model and shares the command constants and the call code that Task 6.3's plan read reuses. Both changes are to `probes.py`, and neither adds behavior beyond the stricter initiatives check. Edit `runner/probes.py`; create `runner/lifecycle/__init__.py` (empty exports for now), `runner/lifecycle/commands.py` and `runner/cf_call.py`; edit `tests/runner/test_probes.py`.

- [ ] `cf_call.py` holds one function, `run_cf(argv, run, timeout_seconds)`, returning the completed process or a failure detail (timeout, `OSError`), extracted from `probe_link`'s call code. `probe_link` uses it. Existing probe tests pass unchanged

- [ ] `commands.py` defines once: `CF_EXECUTABLE`, `CF_PROJECT_FLAG`, `CF_JSON_FLAG`, the status command, the initiatives command with `-a`, and a function building the slice-list command for an index. `probes.py` imports them and no longer defines them
- [ ] The initiatives probe now fails unless `parse_initiatives` accepts the output. `cf status` keeps 122's top-level object check
- [ ] Tests: the probe passes on the captured initiatives fixture and fails on a document missing `index`; the probe invokes `list initiatives --json -a -p <id>`; existing probe tests still pass; the stub `cf` in `tests/cf_stub.py` answers `-a` (update its argument check and its good initiatives output to the captured shape)
- **Success Criteria**:
  - [ ] Probe and stub tests pass; no CF command string is defined outside `commands.py`. Commit: `refactor: probe initiatives with the plan model`

---

## Section 5: The lifecycle model

### Task 5.1: `LifecycleStep` and the step map, with tests
**Owner**: Junior AI | **Dependencies**: 4.1 | **Effort**: 3

Per the LLD, D3. Create `runner/lifecycle/steps.py` and `tests/runner/lifecycle/__init__.py`, `tests/runner/lifecycle/test_steps.py`.

- [ ] `LifecycleStep` `StrEnum` with the seven values of D3. `StepLevel` (initiative, slice) and `Executor` (`pipeline`, `human`) enums. Frozen `StepSpec(level, executor, pipeline)`, where `pipeline` is set if and only if the executor is `pipeline`; construction enforces it
- [ ] `STEP_MAP: Mapping[LifecycleStep, StepSpec]` exactly as the D3 table (pipelines `P4`, `P5`, `P6`). Read-only mapping
- [ ] Completion predicates, one per step, defined once: `architecture` (initiative has an arch file), `slice_plan` (slice list read successfully), `slice_design`/`tasks`/`implementation`/`merge` (reported complete, from Task 3.2), `integration` (initiative `is_checked`). A function `step_complete(step, observation)` over a small frozen `PlanObservation` holding the entry's fields and whether its slice list was read
- [ ] Helper `steps_at(level)` returning the steps of a level in map order, used by reconcile to create children
- [ ] Tests: every step has a spec; pipeline is set exactly for `slice_design`, `tasks`, `implementation`; a `StepSpec` with a pipeline on a human executor (and the reverse) raises; each predicate true and false case, including `architecture` with no arch file, `slice_plan` with an unread list, `integration` from `is_checked` and not from `status`; `steps_at` returns three initiative steps and four slice steps
- **Success Criteria**:
  - [ ] Tests pass. Step values and names appear nowhere else as literals. Commit: `feat: add lifecycle step vocabulary and step map`

### Task 5.2: `LifecycleTree` basics, with tests
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 3

Per the LLD, D1, D4 and "API Contracts". Create `runner/lifecycle/tree.py` and `tests/runner/lifecycle/test_tree.py`, with a builder in `tests/runner/lifecycle/tree_support.py` that makes nodes through `Store.open_temporary()` and returns `LifecycleTree(store.nodes_for_project(...))`.

- [ ] `LifecycleTree(nodes)`: frozen view, no I/O. Indexes by `(kind, cf.project, cf.index)` for linked nodes and by parent for children. Properties `nodes` and methods `children(node)`, `parent(node)`, `find_linked(kind, cf_project, index)`, `step_of(node) -> LifecycleStep | None` (from `cf.phase` on a `phase_or_artifact` node; `None` otherwise; an unrecognized phase raises `ValueError`)
- [ ] `is_linked(node)`: true when the node and every ancestor has a non-null `cf.index`, except step nodes (which have no index) that are linked through their parent. A node with an unlinked ancestor is not linked
- [ ] Tests: lookup by link key distinguishes initiative 120 from slice 120 and two CF projects; `step_of` on step, slice and initiative nodes; `is_linked` true for a linked step under linked parents, false for a step under an orphan (index cleared) and false for an unlinked initiative; an invalid `cf.phase` raises
- **Success Criteria**:
  - [ ] Tests pass. No store import beyond node models in `tree.py`. Commit: `feat: add lifecycle tree with link lookup`

### Task 5.3: `predecessors` and `predecessors_done`, with tests
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 4

Per the LLD, D4 (table, eligible slice, "previous means by ascending index"). Create `runner/lifecycle/predecessors.py` and `tests/runner/lifecycle/test_predecessors.py`.

- [ ] `predecessors(tree, node) -> tuple[Node, ...]` implements the D4 table, one rule per step. This is the only place that says what a step waits for. Module direction is fixed to avoid a circular import: `predecessors.py` imports `LifecycleTree` from `tree.py` only under `TYPE_CHECKING` and uses the tree through its methods; `tree.py` imports `predecessors.py` at module level (Task 5.4 uses it)
- [ ] Eligible slice: linked, has step children, CF status not `deferred` or `deprecated` is expressed by "has step children" (D6 gives those slices none). Orphans are excluded. "Previous" is the eligible slice with the next lower `cf.index` in the same initiative
- [ ] `integration` waits on `slice_plan` and on `merge` of every eligible slice in its initiative
- [ ] `predecessors_done(tree, node)`: true when every predecessor is `done`
- [ ] Tests, one per table row: `architecture` has none; `slice_plan` waits for architecture; `slice_design` waits for `slice_plan` of the initiative; `tasks` waits for `slice_design`; `implementation` waits for `tasks` and for the previous slice's `merge`, and the first slice waits only for `tasks`; `merge` waits for `implementation`; `integration` waits for all eligible merges. Also: slice n+1's `slice_design` does not wait for slice n; an orphaned slice and a stepless slice are skipped as "previous"; ordering follows `cf.index` not creation order; an unknown-status slice (steps present) holds the next slice's `implementation`
- **Success Criteria**:
  - [ ] Tests pass. `predecessors_done` is true for a step with no predecessors. Commit: `feat: add lifecycle predecessor function`

### Task 5.4: `ready_steps`, with tests
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

Per the LLD, D4 (`ready_steps`). Edit `tree.py` (it imports `predecessors_done` from `predecessors.py`, per Task 5.3); tests in `tests/runner/lifecycle/test_ready_steps.py`.

- [ ] `LifecycleTree.ready_steps()` returns step nodes that are `runnable`, linked, have no blocked ancestor, and whose predecessors are done. Pure, over the tree only. Docstring states the later narrowing (124 drive/hold, 125 journal and checkout, 128 gates)
- [ ] Tests: a fresh first initiative's `architecture` is ready and its `slice_plan` is not; marking `architecture` done readies `slice_plan`; a blocked step and a step with a blocked parent are not ready; nothing under an orphan is ready; slice n+1's `implementation` is not ready until slice n's `merge` is done, while its `slice_design` is ready once `slice_plan` is done; a `done` step is not ready; the result is deterministic for the same tree
- **Success Criteria**:
  - [ ] Tests pass; `uv run pyright` strict clean. Commit: `feat: add lifecycle ready steps`

---

## Section 6: The plan read

### Task 6.1: `plan_read_interval_seconds` and `--plan-read-interval`, with tests
**Owner**: Junior AI | **Dependencies**: 5.4 | **Effort**: 2

Per the LLD, D7 and "Settings and CLI". Edit `process/settings.py`, `cli/settings_flags.py`, `runner/factory.py`, `tests/test_settings_flags.py`, `tests/runner/test_factory.py`. Follow how `--run-poll-interval` and its bounds check were added in 122.

- [ ] `ProcessSettings.plan_read_interval_seconds` default 30.0, with an attribute doc; the default appears only in `settings.py`
- [ ] `amoeba start --plan-read-interval` overrides it
- [ ] `runner_tenant()` adds the field to its positive-value bounds check, raising `StartupFailedError` naming the field
- [ ] Tests: the flag overrides the field; an absent flag leaves the default; a non-numeric value is a usage error as for the existing flags; zero and a negative value each fail `runner_tenant()` with the field named
- **Success Criteria**:
  - [ ] Tests pass; `--help` lists the flag. Commit: `feat: add plan read interval setting`

### Task 6.2: Extend the stub `cf` for plan reads
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 3

Per the LLD, "Technology Choices". Edit `tests/cf_stub.py` (if it passes ~300 lines, move scripts to `tests/cf_stub_plan.py`); extend `tests/test_cf_stub*.py` or add `tests/test_cf_stub_plan.py`.

- [ ] `cf list initiatives --json -a -p <id>` and `cf list slices <index> --json -p <id>` answer from a directory named by `CF_STUB_PLAN_DIR`: `initiatives.json` and `slices-<index>.json`. A missing `slices-<index>.json` prints the captured error document (Task 3.1) and exits 1
- [ ] "Next answer" support: when `slices-<index>.<n>.json` files exist, successive calls answer from them in order (a counter file in the plan dir), so a test can change the plan between reads
- [ ] Existing modes (`GOOD`, `EMPTY`, `WRONG_FORM`, `FAIL`, `SLEEP`) still apply to the new commands. `CF_STUB_LOG` records each call
- [ ] Tests: each command answers from the dir; the missing-file error document; the numbered sequence advances; a failure mode applies to a slice read; the log records both commands
- **Success Criteria**:
  - [ ] Existing stub users pass unchanged. New tests pass. Commit: `test: add plan reads to the stub cf`

### Task 6.3: One link's plan read under the budget, with tests
**Owner**: Junior AI | **Dependencies**: 6.2 | **Effort**: 5

Per the LLD, D5 (read scoping), D7 (cut-off), D8 (error document). Create `runner/lifecycle/plan_read.py` and `tests/runner/lifecycle/test_plan_read.py`. Make every call through `run_cf` from `runner/cf_call.py` (Task 4.1).

- [ ] Result types, frozen: `PlanRead` (a complete read: the initiatives, and for each initiative a `SliceList`, `NoSlicePlan` or `SliceReadFailed(detail)`), `PlanReadFailed(detail)` (the initiatives read failed, or a slice error needed escalation), `PlanReadCutOff`. `type PlanReadResult` is their union
- [ ] `read_plan(cf_project_id, linked_slice_initiatives, run, budget, timeout_seconds)`: initiatives first, then each initiative's slice list, each a separate call that checks `budget.allows_call()` first. Any refusal returns `PlanReadCutOff` and nothing else. `linked_slice_initiatives` is the set of initiative indexes that already have linked slice nodes
- [ ] An error document (exit 1, `error: true`) from a slice read means: no linked slices under that initiative gives `NoSlicePlan`; linked slices give `SliceReadFailed` naming the initiative. The decision never reads the error's `message`
- [ ] Timeout, non-zero exit without an error document, and parse failure of a slice read give `SliceReadFailed`; the same on the initiatives read gives `PlanReadFailed`. Detail names the command and the head of the output (`OUTPUT_HEAD_CHARS` from `probes.py`). Never retried in the tick
- [ ] Tests with an injected runner returning canned `CompletedProcess` values from the captured fixtures: complete read; no-plan initiative without linked slices; the same with linked slices is `SliceReadFailed`; each failure kind for both read levels; cut-off before the first call, between initiatives and mid-way, each returning `PlanReadCutOff` with no result for earlier calls; a read that would pass the deadline starts no further call
- **Success Criteria**:
  - [ ] Tests pass. Every call is preceded by a budget check. Commit: `feat: add budgeted plan read for one CF link`

### Task 6.4: Plan read cadence and early trigger, with tests
**Owner**: Junior AI | **Dependencies**: 6.3 | **Effort**: 4

Per the LLD, D7 (interval, early read) and D8 (closure state). Create `runner/lifecycle/cadence.py` and `tests/runner/lifecycle/test_cadence.py`.

- [ ] `PlanReadSchedule(interval_seconds, clock)`: in-memory state per link: last complete read time, last observed snapshot id seen, whether the last read failed. `due(project_id, link, snapshots) -> bool`: true on first sight, when the interval has passed, or when the latest observed snapshot's id differs from the last one seen and its `changed` list is non-empty. `snapshots` is the tuple from `store.latest_cf_snapshots`
- [ ] A failed snapshot (`changed` null) is never the latest observed row and so triggers nothing; a recovery with `changed: []` updates the seen id and triggers nothing. `record_complete(link)`, `record_failed(link)`, `record_cut_off(link)` (leaves the link due), and `last_failed(link)` for the closure rule (Task 9.3)
- [ ] Tests with an injected clock: due on first call; not due before the interval and due at it; a changed snapshot makes it due now; the same snapshot id twice is not a second trigger; failed snapshot and `changed: []` make no early read; a cut-off read stays due next call; `last_failed` is set by a failure and cleared by a complete read; two links are independent
- **Success Criteria**:
  - [ ] Tests pass; no sleeping. Commit: `feat: add plan read cadence and snapshot trigger`

---

## Section 7: Fault vocabulary

### Task 7.1: New fault kinds and payload keys, with tests
**Owner**: Junior AI | **Dependencies**: 6.4 | **Effort**: 2

Per the LLD, D8. Edit `runner/faults.py` and `tests/runner/test_faults.py`.

- [ ] `FaultKind` gains `plan_read_failed`, `lifecycle_orphan`, `plan_status_unknown`
- [ ] Payload key constants defined once next to `PAYLOAD_FAULT_KIND`: `former_index`, `former_slice_name`, `cf_project_id`, `index`, `status`, `step`
- [ ] Docstring marks `plan_read_failed` as project-scoped only, and the other two as node-scoped block payload kinds
- [ ] Tests: the three members exist with the exact string values; a `Fault` of kind `plan_read_failed` raises one project escalation and a repeat adds no row (existing `raise_expected_faults` path)
- **Success Criteria**:
  - [ ] Tests pass. Commit: `feat: add plan read fault kinds`

---

## Section 8: Reconcile

All tests in this section run against `Store.open_temporary()` with hand-built `PlanRead` values and a helper `tests/runner/lifecycle/reconcile_support.py` that builds a plan (initiatives, slice lists). Per the LLD, D5 and D6. `reconcile(store, project_id, cf_project_id, read, faults) -> bool` (whether anything was written) is the entry point; it runs the rules in the fixed order orphan → create → update → complete. It is first created in Task 8.3, so the tests of 8.1 and 8.2 call their rule functions directly (`checked_scope`, then the orphan function), and later tasks call `reconcile`.

### Task 8.1: Read checks (safety rules), with tests
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 4

Per the LLD, D5 "Safety rules". Create `runner/lifecycle/read_checks.py` and `tests/runner/lifecycle/test_read_checks.py`.

- [ ] `checked_scope(tree, cf_project_id, read) -> ReadScope`: the initiatives whose slice lists may be applied, whether the initiatives read may be applied, and the faults to raise. A duplicate initiative index, two initiatives listing one slice index, or a repeated index inside one list makes that read `plan_read_failed` naming the index and applies nothing for its scope
- [ ] An empty initiatives list while linked initiative nodes exist, or an empty slice list while that initiative has linked slices, is `plan_read_failed` naming the linked count, not a mass orphaning. An empty list with no linked nodes is valid
- [ ] A `SliceReadFailed` removes only that initiative from the scope and adds one fault; a `PlanReadFailed` removes the whole link
- [ ] Tests (`test_empty_list_with_linked_nodes_orphans_nothing` lives in Task 8.2): duplicate initiative index; the same slice index under two initiatives; a repeat inside one list; empty initiatives with and without linked nodes; empty slice list with and without linked slices; a failed slice read narrows only its initiative; a failed initiatives read removes everything
- **Success Criteria**:
  - [ ] Tests pass; the module touches no store writes. Commit: `feat: add plan read safety checks`

### Task 8.2: Orphan rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 5

Per the LLD, D5 step 1 and D2 (orphaning). Create `runner/lifecycle/orphaning.py`; tests in `tests/runner/lifecycle/test_orphaning.py`.

- [ ] A linked initiative missing from a successful initiatives read, a slice missing from every successful slice read whose own initiative's read succeeded, and a slice listed under a different initiative from its parent are each orphaned
- [ ] Orphaning clears `cf.index` and `cf.slice_name` in one `update_cf_reference` call, then blocks a node that is neither blocked nor done on `HUMAN` with context `orphaned: CF no longer reports index <n>` and payload `{fault_kind: lifecycle_orphan, cf_project_id, former_index, former_slice_name}`. A done node is unlinked, not blocked, and logs INFO. An already-blocked node keeps its open escalation, is unlinked, and logs a WARNING naming the former index
- [ ] Descendants are not touched; a step under an orphan is unlinked through `is_linked` only
- [ ] Tests, calling `checked_scope` then the orphan function on nodes staged in the store: a renumbered slice (index no longer listed) is orphaned once (the new node's creation is tested in Task 8.3); a moved slice orphaned; a completed slice leaving the plan is unlinked and not blocked; an already-blocked orphan keeps one escalation; the payload carries the former values; `test_empty_list_with_linked_nodes_orphans_nothing`; a failed slice read orphans none of that initiative's slices; an unlinked node is never re-orphaned on the next read (idempotent)
- **Success Criteria**:
  - [ ] Tests pass. Nothing is deleted. Commit: `feat: orphan nodes CF no longer reports`

### Task 8.3: Create rule and statuses at creation, with tests
**Owner**: Junior AI | **Dependencies**: 8.2 | **Effort**: 5

Per the LLD, D1 (display data), D2 (`slice_name` stem rule), D6. Create `runner/lifecycle/reconcile.py` (the only `create_node` caller) with the `reconcile` entry point calling orphan then create; tests in `tests/runner/lifecycle/test_reconcile_create.py`.

- [ ] An initiative with no linked node gets an initiative node (title from `name`, `cf.project`, `cf.index`, `cf.artifact_path` from `archFile`) and then its `architecture`, `slice_plan`, `integration` steps. A slice listed under a read initiative with no linked node gets a slice node under that initiative, then its four steps. A linked node missing a step child gets only that step. Step nodes carry `cf.project`, a null index and `cf.phase` set to the step value; titles are the step value
- [ ] `slice_name` comes from the `{index}-slice.` stem of `designFile` (the stem rule is defined once in `runner/lifecycle/slugs.py`). A `designFile` of another form leaves it null and logs a WARNING naming the file. No `designFile` leaves it null. Amoeba never builds a slug
- [ ] Statuses (D6): a step is created `done` if its completion predicate (Task 5.1) holds, else `runnable`; a container node is `runnable`. A slice reported `deferred` or `deprecated` gets a node and no steps, and gains steps on a later read with another status
- [ ] An unknown status (`degraded` or out of vocabulary): the slice gets four `runnable` steps and is blocked on `HUMAN` with payload `{fault_kind: plan_status_unknown, index, status}`; `plan_read_failed` is not raised
- [ ] Each check-before-write: a rerun of the same read writes nothing
- [ ] Tests: linking a project whose fixture plan has initiative 100 (checked) and 120 with slices: node counts, step sets per level, every step in 100's subtree `done`, every node carrying its index; initiative with no `archFile` gets a runnable `architecture`; `in_progress` slice gets four runnable steps; `slice_name` for the stem, an odd file name (WARNING, null), and no file; deferred slice has no steps and gains them later, a slice with steps keeps them when later deferred; `degraded` slice blocked once with the payload, still blocked after a second identical read, no `plan_read_failed`; `test_renumber_yields_one_orphan_and_one_new_node` (one orphan escalation, one new linked node, the orphan's index and `slice_name` cleared); rerunning writes nothing; a slice listed under the other initiative is orphaned and recreated
- [ ] Guard test in `tests/test_create_node_guard.py` (follow `tests/test_writer_guard.py`: walk the AST of `src/amoeba`, not a text search): fails if any module other than `runner/lifecycle/reconcile.py` calls `create_node`. A self-test shows a synthetic module calling it (source string parsed with `ast`) is detected
- **Success Criteria**:
  - [ ] Tests pass. Adding a `create_node` call elsewhere in `src/amoeba` fails the guard. Commit: `feat: create initiative, slice and step nodes from the plan`

### Task 8.4: Update rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.3 | **Effort**: 2

Per the LLD, D2 (rename) and D5 step 3. Edit `reconcile.py`; tests in `tests/runner/lifecycle/test_reconcile_update.py`.

- [ ] A linked node whose `slice_name` or `artifact_path` differs from CF's is updated through `update_cf_reference`, replacing only those fields (project, index, phase kept). Titles are never updated
- [ ] Tests: a renamed slice keeps its node id and link and raises no orphan escalation; a changed `designFile` updates `slice_name` and `artifact_path`; a changed `archFile` updates an initiative; an unchanged read writes nothing; a changed title alone updates nothing
- **Success Criteria**:
  - [ ] Tests pass. Commit: `feat: update node CF references on plan edits`

### Task 8.5: Complete rule, with tests
**Owner**: Junior AI | **Dependencies**: 8.4 | **Effort**: 4

Per the LLD, D5 step 4 and D3. Create `runner/lifecycle/completion.py`; tests in `tests/runner/lifecycle/test_completion.py`.

- [ ] For each linked step whose completion predicate holds: `runnable` with no unresolved journal entry becomes `done`; `blocked_on_human` with a human executor is resolved by `resolve(resolved_by="runner", detail="observed: <predicate>")` and then marked `done`; anything else (in-flight, blocked pipeline step, unresolved entry) is left alone
- [ ] Steps already `done` are untouched. A crash between the resolve and the status write is repaired by the next pass (the block is already resolved, the step runnable)
- [ ] Tests, no-slice-plan state: an initiative whose slice read is `NoSlicePlan` keeps `slice_plan` runnable and raises no fault; a later read that returns a slice list completes `slice_plan`; `architecture` completes when an `archFile` appears
- [ ] Tests: runnable step with a true predicate is done; a step with an unresolved journal entry is not; a blocked human step is resolved by `runner` then done; a blocked pipeline step is left; `merge` completes from the slice being reported complete; `integration` completes from `isChecked` and not from status; the crash-between-writes case, simulated by resolving first and then running the rule, finishes with one resolved block and a done step; a done step is untouched
- [ ] Crash repair (D5 "Failures during reconcile"), in `tests/runner/lifecycle/test_reconcile_crash.py`, now that all four rules exist: wrap the store so the k-th write raises, for every k across a first-link reconcile; a fresh `reconcile` on the same store afterwards completes the tree with no duplicate linked nodes and the same final tree as an uninterrupted run
- **Success Criteria**:
  - [ ] Tests pass; `reconcile` runs orphan → create → update → complete. Commit: `feat: complete observed lifecycle steps`

---

## Section 9: Tick wiring

### Task 9.1: Put the lifecycle tree in `ProjectView`, with tests
**Owner**: Junior AI | **Dependencies**: 8.5 | **Effort**: 3

Per the LLD, "API Contracts" (`ProjectView` gains `tree`, which replaces the flat runnable list). Behavior-preserving: no plan read yet. Edit `runner/decide.py`, `runner/tick.py`, `tests/runner/tick_support.py` and the four test planners that read `view.runnable_nodes` (`grep -rn runnable_nodes tests src`).

- [ ] `ProjectView.tree: LifecycleTree` replaces `runnable_nodes` (no default; a missing tree fails loudly). `ProjectTick._decide` builds it from `store.nodes_for_project(project)` and no longer computes the busy list
- [ ] Add `runnable_unbusy(view)` to `tests/runner/tick_support.py` (see "Task-level additions") and switch the four test planners to it
- [ ] A failure while building the view follows 122's catch (store failures re-raise; anything else reaches the one catch), and Decide does not run for that project that tick (D5)
- [ ] Tests: 122's tick, tenant, end-to-end and crash tests pass unchanged in behavior (a node with an unresolved entry is still not launched twice); `view.tree` holds every node of the project; a store failure while building the tree re-raises; another exception raises one project-scoped `unexpected_fault` and no action is taken
- **Success Criteria**:
  - [ ] Full runner tests, `ruff` and `pyright` pass. Commit: `refactor: give ProjectView the lifecycle tree`

### Task 9.2: Plan read and reconcile in the project tick, with tests
**Owner**: Junior AI | **Dependencies**: 9.1, 8.5, 6.4 | **Effort**: 4

Per the LLD, "Data Flow", D5, D7 (polling first, which links), D11. Edit `runner/tick.py`, `runner/factory.py`/`runner/tenant.py` (pass the schedule and settings through), `tests/runner/tick_support.py`; tests in `tests/runner/test_tick_plan.py` and `tests/runner/test_budget_coverage.py`.

- [ ] In `ProjectTick.run`, after in-flight polling and the probe check (the `[reconciliation reads - slice 123]` slot): for each link whose probe passed and for which the schedule says due, run `read_plan` with the remaining budget. `PlanReadCutOff` applies nothing, logs a WARNING naming the link, records nothing, and returns the link to due. `PlanReadFailed` calls `record_failed` and adds a `plan_read_failed` fault. A complete read goes through `reconcile`, then `record_complete` (a read with any slice-level failure counts as failed). The tree in `ProjectView` is built after reconcile
- [ ] A plan read never runs for a link that failed its probe. Polling and its budget come first, so a cut-off poll leaves no plan read
- [ ] Tests (injected clock, runner and stub): first tick reads and reconciles and `ProjectView.tree` shows the new nodes; the next tick before the interval reads nothing; after the interval a new slice in the plan's next answer gets a node while `projects.json` is unchanged; a changed snapshot triggers an early read; a cut-off read applies nothing, raises no fault and is read again on the next tick; a run's poll is never cut off by the plan read in the same tick; a probe-failed link is not read; a tick with the (empty) production planner tuple creates nodes, launches nothing, blocks no human step and raises no fault
- [ ] Budget coverage: extend `test_budget_coverage.py` so its failing runner and `Popen` also drive a tick through the plan read with the budget exhausted before the initiatives read and between slice reads. Neither is called after the deadline and nothing is written for the link
- **Success Criteria**:
  - [ ] Tests pass, and 122's tick, probe, tenant and end-to-end tests pass. Commit: `feat: read and reconcile the plan in the project tick`

### Task 9.3: Reconcile faults and `plan_read_failed` closure, with tests
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 3

Per the LLD, D5 (failures during reconcile) and D8 (closure). Edit `runner/tick.py`; tests in `tests/runner/test_tick_plan_faults.py`.

- [ ] Store failures (`STORE_FAILURES`) mid-reconcile re-raise. Any other exception stops this link's reconcile, leaves the link due, and reaches 122's one catch (a project-scoped `unexpected_fault`, no node in context). Decide does not run for that project that tick
- [ ] A link whose last plan read failed counts as a `plan_read_failed` recurrence on every tick until a read of that link succeeds, as `LinkProbes` does for a failed probe. A failure for a link the project no longer has is not replayed
- [ ] Tests: an exception injected into reconcile after the k-th write raises one `unexpected_fault`, leaves the link due, and the next tick completes the tree with no duplicates; a store failure propagates; a failed initiatives read raises one `plan_read_failed`; on later ticks that do not read it stays open; the next successful read of that link closes it on that tick; an empty-list-with-linked-nodes read, a duplicate index and a slice read error with linked slices each raise one `plan_read_failed` and orphan nothing; a failed slice read for one initiative leaves another initiative's slices applied; two links in one project keep independent state; a repeating fault adds no rows
- **Success Criteria**:
  - [ ] Tests pass. Commit: `feat: keep plan_read_failed open until a read succeeds`


---

## Section 10: Human steps

### Task 10.1: `HumanStepPlanner` and `BlockHumanStep`, with tests
**Owner**: Junior AI | **Dependencies**: 9.3 | **Effort**: 4

Per the LLD, D9. Create `runner/lifecycle/human_steps.py`; edit `runner/decide.py` (`Action` union), `runner/tick.py` (Act); tests `tests/runner/lifecycle/test_human_steps.py` and `tests/runner/test_tick_human_steps.py`.

- [ ] `BlockHumanStep(node_id)` frozen dataclass; `type Action = LaunchRun | BlockHumanStep`. `decide` still raises on two actions for one node
- [ ] `HumanStepPlanner.plan(view)` returns a `BlockHumanStep` for each step in `view.tree.ready_steps()` whose `STEP_MAP` executor is `human`. One small class with no abstraction around it
- [ ] Act applies a `BlockHumanStep` as one `store.block(node_id, kind=HUMAN, context="<step> is a human step", payload={step, cf_project_id, index})`, where `index` is the initiative's or slice's CF index. It is not journaled and does not call the launch path. A comment records "store-only actions are applied in one transaction and not journaled" (D9)
- [ ] The production planner tuple stays empty (register nothing). A test asserts it
- [ ] Tests: the planner returns actions for a ready human step and for nothing else; with the planner in a test tuple, `architecture` on an initiative with no `archFile` is `blocked_on_human` on that tick with the payload; `merge` after `implementation` is done is blocked; when the predicate becomes true the next read resolves the block by `runner` and the step is `done`; a person resolving the block without doing the work gets it blocked again on the next tick; a step under an orphan or already blocked gets no action; a pipeline step gets none; the production tuple is empty
- **Success Criteria**:
  - [ ] Tests pass. Nothing launches. Commit: `feat: block human steps through a planner action`

---

## Section 11: Contract text and final validation

### Task 11.1: Contract documents
**Owner**: Junior AI | **Dependencies**: 10.1 | **Effort**: 3

Per the LLD, "Provides to Other Slices" (Contract documents). Edit under `docs/`. Keep existing structure and anchors; the substrate-guide row links must still resolve.

- [ ] `store-contract.md`: `CFReference.index`, migration `010` and its partial unique index, `inspect nodes` showing the index, and the rule that only the Runner's reconcile creates nodes (the guard)
- [ ] `context-forge-contract.md`: the two plan reads and their shapes, the error-document rule (D8, `code: UNKNOWN` observed), the `cf status` observations for 125 and 128 (`-p` without `--worktree` reports only project-level pointers; `--worktree` accepts the worktree id), and the explicit-index requirement with the `indexSource` upstream ask
- [ ] `process-contract.md`: the plan-read setting and flag, the plan read stage, which projects are read, and how a read is cut off
- [ ] `substrate-guide.md`: extend the 120 row with the lifecycle model and reconciliation, linking the new anchors
- **Success Criteria**:
  - [ ] Each document states the points above. Links resolve (`grep -rn "](" docs | …` spot check on the changed anchors). Commit: `docs: add lifecycle model contract text`

### Task 11.2: CHANGELOG, architecture and slice-plan edits
**Owner**: Junior AI | **Dependencies**: 11.1 | **Effort**: 2

Per the LLD, "Special Considerations". Edit `CHANGELOG.md`, `project-documents/user/architecture/120-arch.runner-routing-engine.md`, `project-documents/user/slices/120-slices.runner-routing-engine.md`. Preserve any "User-Provided Concept" section.

- [ ] CHANGELOG `[Unreleased]` entry in the style of slice 122's: the lifecycle model and reconciliation, `plan_read_interval_seconds` and `--plan-read-interval`, migration `010`
- [ ] Arch edits: no gate nodes in v1 (D3); no v1 step with a CF-write executor (D3); Observe reads every linked project's plan on an interval (D7); store-only actions are not journaled (D9); the slice list is not a start-up probe (D11); a done or already-blocked orphan does not get its own escalation (D5)
- [ ] Slice plan, entry 4: "appears on the next plan read"; "triggers no early plan read"; steps are a pipeline or a human step; `cf status` left to 125 and 128; human-step criterion proven under a test planner; done or already-blocked orphan; entry 5 (124): register `HumanStepPlanner` with the drive filter, with a criterion; Future Work gains "Mark step done" and "CF `indexSource`"
- **Success Criteria**:
  - [ ] Each listed edit is present and no unrelated text changed (`git diff --stat` touches only these three files). Commit: `docs: record slice 123 departures in the arch and slice plan`

### Task 11.3: Full validation and the verification walkthrough
**Owner**: Junior AI | **Dependencies**: 11.2 | **Effort**: 3

Per the LLD, "Verification Walkthrough". Run each command once and read its output.

- [ ] `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`; then `uv run pytest tests/contract -v` and `uv run pytest tests/runner/lifecycle tests/upstream/test_cf_plan.py tests/store/test_migration_010.py -v`
- [ ] Walkthrough step 3 with the real `cf` and a temporary `AMOEBA_STORE_DIR`: start, create the project, link this repository's CF project, then `amoeba inspect nodes` and `amoeba inspect messages --json`. Check against the LLD's expected output (initiative rows with indexes; steps under initiative 100 and slices 101–110 `done`; initiative 120's slices with four `runnable` steps each; later initiatives with a `runnable` `architecture`; no `plan_read_failed`, orphan or human-step blocks). Then `amoeba stop`
- **Success Criteria**:
  - [ ] All gates clean. The walkthrough matches the expected output or the deviation is written in this task. Commit any fixes as `fix:` or `refactor:` and any notes as `docs:`
