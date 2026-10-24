---
docType: tasks
slice: intent-vocabulary
project: amoeba
lld: user/slices/124-slice.intent-vocabulary.md
dependencies:
- 121
- 122
- 123
projectState: Slices 120–123 are merged. `amoeba.runner` has the tick (`ProjectTick.run`,
  with a `# [apply intents - slice 124]` slot before observe), `ProjectView(project_id,
  now, tree, in_flight, link_probes)` with `ready_unbusy()`, `decide()` with a duplicate-action
  rule, and `PRODUCTION_PLANNERS = ()` in `runner/factory.py`. `amoeba.runner.lifecycle`
  has `LifecycleStep`, `StepLevel`, `STEP_MAP`, `LifecycleTree`, `HumanStepPlanner`
  (plans over `view.tree.ready_steps()`) and `BlockHumanStep`. The store has `pending_intents`,
  `desired_state(s)`, `acknowledge_message(..., desired_state=)`, `SetDesiredState`,
  `ClearDesiredState` and `DesiredState`. `amoeba.runner.intent` and `STEP_SEQUENCE`
  do not exist.
dateCreated: 20261023
dateUpdated: 20261024
status: in_progress
turns: 52
promptTokens: 4177544
cachedTokens: 4071088
cacheWriteTokens: 106366
completionTokens: 32580
durationSeconds: 229.0
costUsd: 1.158835
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

## Context Summary

- Working on the **intent-vocabulary** slice (124), the fifth slice of initiative 120 (Runner and Routing Engine). It defines how the PM steers the Runner (five intent kinds) and makes the Runner obey it (drive, hold, current steps).
- **Current state:** the tick has an empty slot before observe. Intents are accepted by the inbox and sit pending. Nothing is governed: `HumanStepPlanner` sees every ready step and is not in production.
- **Dependencies:** 121 (acknowledgment outcomes, desired-state rows), 122 (tick, `Planner`, `decide()`, fault boundary), 123 (tree, steps, `HumanStepPlanner`). All merged.
- **What this slice delivers:** `STEP_SEQUENCE`/`step_rank`; the `amoeba.runner.intent` subpackage (`vocabulary.py`, `apply.py`, `governance.py`); the apply stage and `DesiredStateIndex` in the tick; `ProjectView.desired`/`current_steps` and the current-step guard in `decide()`; `HumanStepPlanner` in production; the `desired-states` listing; contract text and CHANGELOG. No schema change.
- **Next planned slice:** 125 (run dispatch and outcome ingestion), which dispatches from `view.current_steps`.

**Branch:** all implementation happens on `124-slice.intent-vocabulary`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/124-slice.intent-vocabulary.md` at the named decision (D1–D10), "Architecture", or "Implementation Details". Keep every new or changed source file near 300 lines and each function near 50.

**Commit cadence:** one commit per task. A commit never holds untested behavior. Run `uv run ruff format .` before each commit. Commit type is `feat:` for new behavior, `refactor:` for behavior-preserving change, `test:` for test-only work, `docs:` for contract text.

**Task-level additions to the LLD:**
- **Planner tuple location.** The LLD's Component Structure puts the production tuple in `tenant.py`. In the code it is `PRODUCTION_PLANNERS` in `runner/factory.py`. Change it there.
- **Module split.** `vocabulary.py` holds the enums, `IntentBody` and `until_applies`. `apply.py` holds `interpret` and `apply_pending_intents`. If `interpret` passes ~300 lines with its helpers, put the row-merge rules in `intent/merge.py`. `governance.py` has no store import.
- **Shared names, defined once.** `IntentKind`, `IntentRejection`, `STEP_SEQUENCE`, the 512-character reason bound (`REASON_DETAIL_LIMIT`) and `RUNNER_ACTOR` (`runner/faults.py`). Tests import them. They never retype a value.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`. Pydantic's `ValidationError` is caught only in `interpret`, to produce `malformed_body`.
- **Test doubles.** Pure functions get table-driven tests with hand-built trees and rows (see `tests/runner/lifecycle/tree_support.py`). Store-backed tests use `Store.open_temporary()`. Tick-level tests use the support in `tests/runner/tick_support.py` and `plan_tick_support.py` (stub `cf`, stub `sq`). Nothing sleeps or runs a real `cf` or `sq`.
- **Test naming.** Tests are named for the rule they prove, for example `test_project_pause_wins_over_slice_resume`, `test_same_intent_twice_is_no_op`.
- **Test location.** `tests/runner/intent/` (add `__init__.py`).

**Section map.** 1 baseline; 2 step order and vocabulary; 3 interpret and apply; 4 governance (index and `governing`, then `current_steps`); 5 view, guard and planners (the helpers apply intents directly, so 5 does not need 6); 6 tick wiring; 7 tick-level behavior tests; 8 desired-states listing; 9 contract text and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Create `124-slice.intent-vocabulary` from the target. If it exists, switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each. Record the passed-test count in this task. Baseline: 2760 passed
- **Success Criteria**:
  - [x] On the slice branch. Baseline suite, `ruff` and `pyright` are clean. If not, write `BLOCKED:` with the failure and stop. No commit needed

---

## Section 2: Step order and vocabulary

### Task 2.1: `STEP_SEQUENCE` and `step_rank`, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 1

Per the LLD, D4. Edit `runner/lifecycle/steps.py` and `tests/runner/lifecycle/test_steps.py`.

- [x] Add `STEP_SEQUENCE: Final[tuple[LifecycleStep, ...]]` listing the seven steps in process order: `architecture`, `slice_plan`, `slice_design`, `tasks`, `implementation`, `merge`, `integration`. Write the order out explicitly. Do not derive it from enum declaration order
- [x] Add `step_rank(step) -> int`, the position in `STEP_SEQUENCE`
- [x] Export both from `runner/lifecycle/__init__.py` if the package exports its public names. N/A: the package exports nothing
- [x] Tests: `STEP_SEQUENCE` holds every `LifecycleStep` exactly once (set equality plus length), `step_rank` is strictly increasing along the sequence, and the explicit order matches the seven names above
- **Success Criteria**:
  - [x] `tests/runner/lifecycle/test_steps.py`, `ruff` and `pyright` pass. Commit: `feat: define the lifecycle step order`

### Task 2.2: The intent vocabulary and the `until` rule, with tests
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 2

Per the LLD, D1, D3 and D4 ("`until_not_applicable`"), and "Internal API". Create `runner/intent/__init__.py`, `runner/intent/vocabulary.py` and `tests/runner/intent/test_vocabulary.py`.

- [x] `IntentKind(StrEnum)`: `drive`, `exclude`, `pause`, `resume`, `clear`
- [x] `IntentRejection(StrEnum)`: `malformed_body`, `target_not_initiative_or_slice`, `target_unlinked`, `until_not_applicable`
- [x] `IntentBody` (pydantic v2, `extra="forbid"`): `intent: IntentKind`, `until: LifecycleStep | None = None`. A model validator rejects `until` with any kind but `drive`
- [x] Tests (parametrized): each of the six body forms parses; an unknown key (`"untill"`) fails; an unknown `intent` value fails; an unknown `until` value fails; `until` with `exclude`, `pause`, `resume` and `clear` fails; a non-object body (list, string) fails when validated
- [x] Add `TargetKind(StrEnum)` to `vocabulary.py`: `project`, `initiative`, `slice`. Defined once; Task 3.1 maps a node's kind to it
- [x] Add `until_applies(target: TargetKind, step: LifecycleStep) -> bool`. A `slice` target accepts only steps where `STEP_MAP[step].level is StepLevel.SLICE`. `initiative` and `project` targets accept any step
- [x] Tests (table-driven over all seven steps and the three target kinds): on a slice, `architecture`, `slice_plan` and `integration` are not applicable and the other four are; on an initiative and on the project, all seven apply
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: add the intent vocabulary and body model`

---

## Section 3: Interpreting and applying intents

### Task 3.1: `interpret` — target rules, with tests
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 3

Per the LLD, D2, D3 and "Component Structure". Create `runner/intent/apply.py` (the pure part only) and `tests/runner/intent/test_interpret_targets.py`. Add a small test builder for a tree of initiative, slice and step nodes (reuse `tree_support.py`; add to it only if it lacks a needed shape, such as an unlinked orphan).

`interpret(message, tree, current_row) -> Interpretation` is pure. `Interpretation` is a frozen dataclass: `outcome` (`AcknowledgmentOutcome`), `reason` (`str | None`), `desired_state` (`SetDesiredState | ClearDesiredState | None`). In this task only the rejection paths and the target lookup are complete; the merge arrives in 3.2.

- [x] Validate `message.payload` against `IntentBody`. On `ValidationError` return `rejected` with reason `malformed_body: <first pydantic error>`, bounded to `REASON_DETAIL_LIMIT` (512) characters. Define the bound once
- [x] Resolve the target from `message.node_id`: none is the project. A step node returns `target_not_initiative_or_slice`. A node that is not linked (`tree.is_linked`) returns `target_unlinked`. Order: malformed body first, then target kind, then linked, then `until`
- [x] For `drive` with `until`, map the target node's kind to `TargetKind` and call `until_applies`; failure returns `until_not_applicable`
- [x] Reason format is `"<code>: <detail>"` with the `IntentRejection` value as the code. Nothing in the code branches on the detail
- [x] Tests: each of the four rejection codes is produced by the inputs in the LLD Functional Requirements (malformed body, unknown key, `until` on a non-drive kind, a step-node target, an orphaned target, `architecture` as `until` on a slice); a long malformed detail is cut to 512 characters; the reason starts with the code and `": "`; a valid body on a linked initiative, slice and the project passes through without rejection
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: reject intents the Runner cannot apply`
  - Note: added the `LifecycleTree.node(node_id)` accessor in `tree.py` for the target lookup.

### Task 3.2: `interpret` — merge, normalization and no-op, with tests
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 3

Per the LLD, D1's table and D5. Edit `apply.py` (or add `intent/merge.py`) and create `tests/runner/intent/test_interpret_merge.py`.

- [x] Compute the merged row from the current row (a `DesiredState` or `None`) for each kind, exactly as D1's table gives: `drive` sets `drive=true` and sets or clears `until`, keeping hold; `exclude` sets `drive=false`, clears `until`, keeping hold; `pause` sets `hold=true`, keeping drive and `until`; `resume` unsets hold, keeping drive and `until`; `clear` deletes the row
- [x] Normalize: hold is stored `true` or not set, never `false`. A merged row with drive and hold both unset is a deletion (`ClearDesiredState`), as `clear` is
- [x] No-op: if the merged row equals the current row (comparing drive, `until`, hold), or the result is a deletion and no row exists, return `no_op` with no `desired_state`. Otherwise return `applied` with `SetDesiredState` (or `ClearDesiredState`) carrying the target's `node_id`
- [x] "Driving to a passed step" is not special-cased: it is `applied` when it changes the row, `no_op` when it does not
- [x] Tests (table-driven, one row per D1 body form crossed with current row = none, drive-only, drive-with-until, hold-only, drive+hold): the resulting `SetDesiredState` or `ClearDesiredState`, or `no_op`. Include: same intent twice is `no_op`; `drive until tasks` then `drive until implementation` ends `until=implementation`; `pause` then `drive` keeps the pause; `resume` with no hold on a row with drive keeps the row and is `no_op`; `resume` that removes the only setting deletes the row; `clear` with no row is `no_op`; `drive` without `until` clears a stored `until`; `exclude` clears a stored `until`; a drive-until-passed-step that restricts is `applied` (LLD D5 example)
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: merge intents into desired-state rows`
  - Note: the merge rules live in `intent/merge.py`.

### Task 3.3: `apply_pending_intents`, with tests
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 3

Per the LLD, D9 and "Data Flow". Edit `apply.py`; create `tests/runner/intent/test_apply_pending.py`.

- [x] `apply_pending_intents(store, project_id) -> int`: read `pending_intents`; if none, return 0 without reading the tree. Otherwise build `LifecycleTree(store.nodes_for_project(project_id))` once
- [x] For each intent in ascending `seq`: read the target's current row with `store.desired_state(project_id, node_id=...)` (after the previous intent's write), call `interpret`, then `store.acknowledge_message(id, acknowledged_by=RUNNER_ACTOR, outcome=..., reason=..., desired_state=...)`. One acknowledgment per intent. Return the count acknowledged
- [x] Do not read link state or check the budget (D9). Do not catch store failures; `STORE_FAILURES` propagate to the tenant (122, D8)
- [x] Tests with `Store.open_temporary()`: no pending intents returns 0 and does not call `nodes_for_project` (spy); each outcome (`applied`, `no_op`, `rejected` per code) is stored on the message with its reason; two intents for one target in one call are applied in `seq` order (the second sees the first's write); the row's `message_id` is the intent that last changed it and stays unchanged by a `no_op`; an intent on a project whose CF link is failed or missing is still applied
- [x] Crash test: inject a store failure inside `acknowledge_message` (follow `tests/store/test_desired_state.py` and `tests/runner/lifecycle/test_reconcile_crash.py`). The intent stays pending and no row is written. A second call applies it exactly once
- [x] Test that every `applied` case in Task 3.2's table is accepted by the store: submit each as an intent against a temporary store (seeding the current row first where the case needs one) and assert `apply_pending_intents` acknowledges it `applied` with the expected stored row, so 121's shape rules never reject what `interpret` produces
- [x] Test that an `interpret` result which breaks 121's shape rules raises `ValueError` out of `apply_pending_intents` and leaves the intent pending (monkeypatch `interpret` to return one)
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: apply pending intents against the store`
  - Note: the "failed or missing CF link" test covers the missing-link case; apply takes no link input.

---

## Section 4: Governance

### Task 4.1: `DesiredStateIndex` and `governing`, with tests
**Owner**: Junior AI | **Dependencies**: 3.3 | **Effort**: 4

Per the LLD, D4 ("within drive") and D6. Create `runner/intent/governance.py` (no store import; it may import the `DesiredState` model type), `tests/runner/intent/test_governance_index.py` and `tests/runner/intent/test_governing.py`.

- [x] `DesiredStateIndex` is built from a sequence of `DesiredState` rows. It maps a target (`None` for the project, else a node id) to its row. Provide a lookup `row_for(target) -> DesiredState | None`
- [x] `drives_anything() -> bool`: true when any row has `drive is True`
- [x] Index tests: lookup of the project row, of a node row, of a missing target; `drives_anything` is false for no rows, for `drive=false` only and for hold-only rows, and true when any row drives
- [x] `Governance` frozen dataclass: `driven: bool`, `held: bool`
- [x] `governing(tree, index, step) -> Governance`. The path is the step's container (slice or initiative), the slice's initiative if any, then the project (key `None`). Use `LifecycleTree` accessors (`step_of`, parent lookups); add a small accessor to `tree.py` only if the path cannot be walked with what exists, and say so in the commit
- [x] Drive: the nearest row on the path whose `drive` is set decides `driven` with that row's value. The step must also be within that row's `until`: `until` unset, or `step_rank(step) <= step_rank(until)`. No row sets drive: not driven (the default)
- [x] Held: true if any row on the path has `hold` set
- [x] Tests (table-driven, hand-built tree and rows, no store), asserting `driven` and `held` per step: nothing driven by default; project drive drives every step; initiative `exclude` under a driven project leaves that initiative's steps undriven and a slice `drive` under it restores that slice's; project `pause` with a slice `resume` leaves the slice's steps held; no project pause leaves them not held; `drive until slice_design` on an initiative drives the initiative's `architecture` and `slice_plan` and every slice's `slice_design`, and never `tasks` or `integration`; `drive until tasks` on a slice leaves `implementation` undriven; a pause on a slice does not hold its sibling
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. `governance.py` imports nothing from `amoeba.store` except model types. Commit: `feat: add the desired-state index and resolve drive and hold`
  - Note: no tree accessor was added. `LifecycleTree.node` (added in 3.1) was sufficient for the path walk.

### Task 4.2: `current_steps`, with tests
**Owner**: Junior AI | **Dependencies**: 4.1 | **Effort**: 2

Per the LLD, D6. Edit `governance.py`; extend `tests/runner/intent/test_governing.py`.

- [x] `current_steps(tree, index) -> Sequence[Node]`: `tree.ready_steps()` filtered to steps that are driven and not held, in `ready_steps` order
- [x] Tests (hand-built tree and rows): only ready steps can be current; a driven, unheld ready step is current; a held ready step and an undriven ready step are not; an orphan's row never affects a current step; the result keeps `ready_steps` order
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: derive the current steps from governance`
  - Note: `current_steps` lives in `runner/intent/governance.py`.

---

## Section 5: View, guard and planners

### Task 5.1: `ProjectView` gains `desired` and `current_steps`, with tests
**Owner**: Junior AI | **Dependencies**: 4.2 | **Effort**: 3

Per the LLD, D7. Edit `runner/decide.py`; update every place that builds a `ProjectView` (`grep -rn "ProjectView(" src tests`), including `runner/tick.py`'s `_decide` for now (pass an index from `desired_states` there; Task 6.1 moves the read). Edit `tests/runner/tick_support.py` and `tests/runner/test_decide.py`.

- [x] Add `desired: DesiredStateIndex` and `current_steps: Sequence[Node]` to `ProjectView`. The tick computes `current_steps` with `current_steps(tree, index)` when it builds the view
- [x] Test helpers in `tests/runner/tick_support.py`: `view_for(tree, rows=(), in_flight=())` builds a `ProjectView` from hand-built `DesiredState` rows and computes `current_steps`; `drive_project(store, project_id)` submits a project-level `{"intent": "drive"}` through the inbox (as `plan_tick_support.py` submits other messages) and then calls `apply_pending_intents(store, project_id)` itself, so the row exists before the next tick. It must not depend on the tick's apply stage, which Task 6.1 adds. Update existing view construction to use `view_for`
- [x] Leave `ready_unbusy()` and its test unchanged. Slice 125 owns the dispatch planner and decides how it excludes busy nodes from `current_steps`
- [x] Tests: a view built from a driven project exposes the expected `current_steps`, and one built with no rows exposes none
- **Success Criteria**:
  - [x] Existing 122 and 123 runner tests pass unchanged apart from how they build the view. No behavior changes yet: planners and `decide()` still ignore `current_steps` until Tasks 5.2 and 5.3. `ruff` and `pyright` pass. Commit: `refactor: give ProjectView the desired-state index and current steps`
  - Note: `view_for` and `drive_project` were added to `tests/runner/tick_support.py`. `drive_project` uses `tests/runner/intent/intent_support.submit`. The interim desired-state read is in `tick.py` `_decide`, to be removed in Task 6.1.

### Task 5.2: The current-step guard in `decide()`, with tests
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 2

Per the LLD, D7 ("The guard"). Edit `runner/decide.py`; extend `tests/runner/test_decide.py`.

- [x] `decide(view, planners)` raises `ValueError` if an action's `node_id` is not the id of a node in `view.current_steps`. Message names the node and project, as the duplicate rule does. Check the guard before the duplicate rule. Nothing is silently dropped
- [x] Update the docstring's `Raises:` section
- [x] Tests: a test planner that emits an action for every ready step, with a held step, an undriven step and an excluded step, raises `ValueError`; a planner acting only on current steps passes; an action naming an unknown node raises; the duplicate-action rule still raises for two actions on one current step
- [x] Migrate the existing test planners without weakening the guard. List every user with `grep -rn "runnable_unbusy" tests`. Change `runnable_unbusy(view)` in `tests/runner/tick_support.py` to take nodes from `view.current_steps` (still `runnable` and not in flight). In each test that builds a view by hand, pass a project drive row to `view_for`. In each test that ticks through a store, call `drive_project` before the tick. Run `uv run pytest tests/runner -q`; any remaining guard `ValueError` names a test still missing a drive. Record the list of migrated test files in the commit message
- **Success Criteria**:
  - [x] Tests, `uv run pytest tests/runner -q`, `ruff` and `pyright` pass. Commit: `feat: refuse actions on steps that are not current`

**Notes (5.2)**:
- The 122-era tests used plain unlinked slices, which can never be current steps. They were migrated to a new `ready_step(store, project_id)` helper in `tests/runner/tick_support.py` (a linked initiative's architecture step) plus `drive_project`.
- Migrated files: `test_tick`, `test_tenant`, `test_end_to_end`, `test_probes`, `test_tick_human_steps`, `crash_harness`, `test_decide`.
- `runnable_unbusy` now reads `current_steps`.

### Task 5.3: `HumanStepPlanner` plans over current steps and joins production, with tests
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 3

Per the LLD, D7 and D8. Edit `runner/lifecycle/human_steps.py`, `runner/factory.py`, `tests/runner/lifecycle/test_human_steps.py`, `tests/runner/test_tick_human_steps.py` and `tests/runner/test_factory.py`.

- [x] `HumanStepPlanner.plan` iterates `view.current_steps` instead of `view.tree.ready_steps()`. Everything else is unchanged
- [x] Update its docstring: it blocks each current step whose executor is a person
- [x] Tests: with the project driven, a ready human step is blocked as before; with nothing driven, it plans nothing; with the project driven and paused, it plans nothing; a human step that is already `blocked_on_human` is not current and is not blocked again; update 123's existing human-step tests to drive the project in their setup (`drive_project`)
- [x] `PRODUCTION_PLANNERS = (HumanStepPlanner(),)`. Update the comment: slice 125 appends its dispatch planner
- [x] Update `tests/runner/test_factory.py` (and any test pinning the empty tuple or relying on it, for example in `test_tenant.py`, `test_end_to_end.py`, `tests/contract`)
- [x] Test: `None` planners select a tuple holding exactly one `HumanStepPlanner`; a passed value still overrides it
- **Success Criteria**:
  - [x] Full `uv run pytest -q`, `ruff` and `pyright` pass. Commit: `feat: plan human steps over current steps and register them in production`

**Notes (5.3)**:
- The `HumanStepPlanner` change to `current_steps` landed in the 5.2 commit (108e8ac) because the guard would otherwise fail its tests. The 5.3 commit holds the production tuple and factory tests.
- Full suite: 2912 passed; `ruff` and `pyright` clean.

---

## Section 6: Tick wiring

### Task 6.1: The apply stage and the per-tick index, with tests
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

Per the LLD, D6 and D9, "Data Flow" and "State Management". Edit `runner/tick.py` (replace the `# [apply intents - slice 124]` comment) and create `tests/runner/test_tick_intents.py`.

- [ ] At the top of `ProjectTick.run`, before observe: clear the node context (the work is project-scoped), call `apply_pending_intents`, and set `self.wrote` true when it returned more than zero
- [ ] Then read `desired_states(project_id)` once into a `DesiredStateIndex`, before observe, and hand the same index to `_decide` for the view. Never cache it across ticks. Remove the interim read added in Task 5.1
- [ ] Leave a short comment at the observe call noting that 125 and 128 read `index.drives_anything()` for their Observe scope. Do not change observe now. Observe is not filtered by hold
- [ ] Tests (stub `cf`/`sq` as in 123): an intent submitted before a tick is acknowledged and its row written in that tick; the same tick's decide sees it (a driven initiative with no `archFile` blocks its `architecture` step in one tick); `tick()` returns true when only an intent was applied; an unexpected exception raised inside apply becomes a project-scoped `unexpected_fault` (monkeypatch `interpret`), earlier acknowledgments stay and the failing intent stays pending; a repeating bug adds no second escalation row; a `STORE_FAILURES` error exits as 122 specifies
- **Success Criteria**:
  - [ ] Tests, the 122 and 123 tick tests, `ruff` and `pyright` pass. Commit: `feat: apply intents at the start of each project tick`

---

## Section 7: Tick-level behavior tests

Only Functional Requirements that no earlier task proves through a tick. Idempotence, order and rejections are proven in Tasks 3.2–3.3; drive-and-block in one tick is proven in 6.1; the not-blocked-again rule in 5.3. Add to `tests/runner/test_tick_intents.py` or, if it passes ~300 lines, `tests/runner/test_tick_governance.py`.

### Task 7.1: Hold through the tick
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 2

- [ ] `test_project_pause_wins_over_slice_resume`: project paused, a slice resumed and driven; the slice's steps are not blocked or planned. Then `resume` on the project; on the next tick they are
- [ ] A test planner that emits an action for every ready step, with a held step, faults the project through 122's catch (`unexpected_fault`, deduplicated); the production tuple with a held human step blocks nothing
- **Success Criteria**:
  - [ ] Tests pass. Commit: `test: prove hold through the tick`

### Task 7.2: Held targets still observe, and linking escalates nothing
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 2

Per the LLD, D7 ("What hold does not stop") and D8.

- [ ] A run in flight under a held slice is still polled and recorded (stub `sq`, as in `test_observe_poll.py`), and a block written before the hold stays
- [ ] `test_linking_a_project_escalates_nothing`: link a fixture project, tick, and assert no escalation and no block
- **Success Criteria**:
  - [ ] Tests, `uv run pytest tests/contract -q`, `ruff` and `pyright` pass. Commit: `test: prove observe continues under hold and linking is quiet`

---

## Section 8: The `desired-states` listing

### Task 8.1: The listing rows, with tests
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 2

Per the LLD, D10. Create `inspection/desired_states.py`; register in `inspection/__init__.py` following how `messages` or `verdicts` are registered; create `tests/inspection/test_desired_states.py`. Inspection must not import Runner code.

- [ ] Columns: `target` (`project`, or the node id), `drive`, `until`, `hold`, `message_id`, `updated_at`. Unset values are empty strings. Define the column names and the `project` label once
- [ ] Project-scoped listing, no options. It reads `store.desired_states(project_id)` only
- [ ] Tests: a project with a project row, a node row with `until`, and a hold-only row shows each correctly; unset values are empty; `--json`/`/v1/listings/desired-states` carry the same columns (follow `test_read_listing.py` for the HTTP path, and add the name to any test that pins the registry's listing names); an empty project returns no rows; a source check that `inspection/desired_states.py` imports nothing from `amoeba.runner`
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. `amoeba inspect desired-states --help` runs. Commit: `feat: add the desired-states listing`

---

## Section 9: Contract text and final validation

### Task 9.1: Contract documents
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 2

Per the LLD, "Provides to Other Slices" (Contract documents) and "API Contracts". Follow the style of the 123 additions in each file.

- [ ] `docs/inbox-contract.md`: a new "Intent bodies" section replacing the `{"want": "a review"}` example. Give the six body forms, the target rules, the four rejection codes with the `"<code>: <detail>"` reason form, the no-op rule (the target's settings would not change) and how to read the answer (`amoeba inspect messages --project P --channel intent`, `intent_for_submission`). Use the two CLI examples from the LLD
- [ ] `docs/process-contract.md`: the apply stage (store-only, before observe, ignores link state, failure handling), the per-tick index, the current-step guard, what hold does not stop, and that `HumanStepPlanner` is in production
- [ ] `docs/substrate-guide.md`: extend the 120 row with a "Since slice 124" sentence and links to the new sections, in the style of the slice-123 sentence. Update the contract scenario or link-check test if one pins these anchors (`grep -rn "substrate-guide" tests`)
- [ ] Check the architecture document and slice plan already carry the edits the LLD lists under "Special Considerations" (resume removes the hold; no-op means the settings would not change; plan entry 5 wording). Edit them only if they do not
- **Success Criteria**:
  - [ ] Docs link-check tests (if any) pass. Each LLD rule appears once, in one document. Commit: `docs: document intent bodies, the apply stage and the current-step guard`

### Task 9.2: CHANGELOG
**Owner**: Junior AI | **Dependencies**: 9.1 | **Effort**: 1

- [ ] Add entries under `## [Unreleased]` in `CHANGELOG.md`: Added (the intent vocabulary and rejection codes, the apply stage, drive/hold governance and the current-step guard, `amoeba inspect desired-states`, `HumanStepPlanner` in production); Changed (`ProjectView` fields, `decide()` refuses non-current actions, planners see current steps). Match the existing entries' style. Do not bump the version
- **Success Criteria**:
  - [ ] Entry present. Commit: `docs: add CHANGELOG entry for slice 124`

### Task 9.3: Full validation
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 2

Per the LLD, "Verification Walkthrough" steps 1–4.

- [ ] Run `uv run pytest tests/runner/intent tests/runner/test_decide.py -v`, then `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, and `uv run pytest tests/contract -v`. Each once
- [ ] Walkthrough steps 2–4 against a throwaway store (`AMOEBA_STORE_DIR=$(mktemp -d)`), with the real `cf` read-only on this repository: link and see no escalation; drive initiative 140 (`applied`, one escalation for `architecture`); repeat (`no_op`); project `pause`, then drive 150 (`applied`, no escalation); `inspect desired-states` shows three rows; project `resume` (escalation for 150, project row gone); the two rejection submissions show `malformed_body:` and `target_not_initiative_or_slice:`. Stop with `amoeba stop`. Nothing launches a run
- [ ] Confirm file sizes: `wc -l` on each new or changed source file; split any over ~300 lines (note the split in the commit)
- [ ] Confirm `git status` is clean and every task's work is committed on the slice branch
- **Success Criteria**:
  - [ ] All checks clean and the walkthrough matches the LLD's expected results. If a check fails, fix it in the task that owns the code and commit there, or write `BLOCKED:` with the output. Final commit if any fix was needed: `fix: address validation findings for slice 124`. The slice stays on its branch for code review
