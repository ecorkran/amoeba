---
docType: tasks
slice: resolutions-and-resumption
project: amoeba
lld: user/slices/127-slice.resolutions-and-resumption.md
dependencies:
- 121
- 122
- 123
- 124
- 125
- 126
projectState: Slices 120–126 are merged. The route stage runs in `runner/tick.py`,
  and `runner/routing/` holds inputs, reduce, evidence and the shipped `default.yaml`.
  A `resolution` submission fills the slot and returns the node to `runnable`, with
  no decision and no Runner answer. `dispatch_state(entries, *, pointer_confirmed)`
  reads only the journal. The store is at schema version 11. `runner/tick.py` (324
  lines), `runner/observe.py` (335) and `runner/launch.py` (299) are at or over the
  size guideline. `amoeba.runner.resolutions` does not exist.
dateCreated: 20261025
dateUpdated: 20261025
status: in_progress
turns: 46
promptTokens: 4994737
cachedTokens: 4813986
cacheWriteTokens: 180671
completionTokens: 53506
durationSeconds: 533.3
costUsd: 3.47889
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.4788900000000003
    completionTokens: 53506
revision_number: 2
---

## Context Summary

- Working on the **resolutions-and-resumption** slice (127), the eighth slice of initiative 120 (Runner and Routing Engine). A PM's `resolution` now carries a `decision` (`retry`, `accept`, `handled`, `rerun`, `stop`) and optional `instructions`. The Runner acknowledges each one `applied` or `rejected` with a code, in one transaction with its effect, and carries out applied decisions: it resumes paused runs with `sq run --resume`, observes runs the PM handled, accepts escalated outcomes, reruns and stops.
- **Current state:** a resolution of a pipeline step returns it to `runnable`, and 125's rules then rewrite the pointer and launch a fresh run. Nothing resumes a paused run.
- **Dependencies:** 121 (`StatusEffect`, `BlockEffect`), 122 (tick, launch, `LaunchTracker`, `TickBudget`, faults), 123 (`STEP_MAP`, `Executor`), 124 (current-step guard, store-only stage pattern), 125 (entry results, `dispatch_state`, checkout hold, ingestion), 126 (route stage, input vocabulary, table). All merged. Squadron 0.23.5 or later, by shape (LLD "Interfaces Required").
- **What this slice delivers:** migration `012` and three store methods; the `resolution` payload fields; `amoeba.runner.resolutions` (vocabulary, `classify`, `judge_resolution`, stage, `ContinuationPlanner`, acts, confirmation); `ResumeRun` and `ObserveRun`; recovery's continuation rules; the `resume_failed` outcome, the `review_accepted` input and one table rule; `blocked_state_id` in `inspect blocked`; contract text and CHANGELOG.
- **Next planned slice:** 128 (gates, git and human steps), which reads this slice's identifiable accept (LLD D7) and applies its branch check to `ResumeRun`.

**Branch:** all implementation happens on `127-slice.resolutions-and-resumption`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/127-slice.resolutions-and-resumption.md` at the named decision (D1–D9), "Architecture" or "Implementation Details". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/` or `docs/`. Keep every new or changed source file near 300 lines and each function near 50. Where this file's "Task-level additions" differ from the LLD, this file wins; the LLD is not amended.

**Order and dependencies:** work tasks in file order. Each task's **Dependencies** lists only its real prerequisites. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off; only its dependents wait.

**Commit cadence:** each task ends in one commit. An implementation task with no commit step is committed together with the test task right after it, so a commit never holds untested behavior. Run `uv run ruff format .` before each commit. Commit type is `feat:` for new behavior, `refactor:` for behavior-preserving change, `test:` for test-only work, `docs:` for contract text.

**Task-level additions to the LLD** (code facts the LLD does not state, checked against the code on 20261025; each resolves a placement, not a product decision):
- **The production planner tuple** is `PRODUCTION_PLANNERS` in `runner/factory.py`, not `tenant.py`. `ContinuationPlanner()` is added there.
- **Journal keys live in the store.** `amoeba.process` (the recovery observer) may not import the Runner. So `PARAM_CONTINUATION`, `PARAM_CONTINUES` and `PARAM_RESOLUTION` (`"continuation"`, `"continues"`, `"resolution"`) go in `store/journal_models.py` beside `PARAM_RUN_ID`, and the Runner imports them. The `Continuation` enum is Runner vocabulary, in `runner/resolutions/vocabulary.py`. The observer checks only that the key is present.
- **`usage_limit` is not yet a `CheckpointKind` member.** Task 3.1 adds `USAGE_LIMIT = "usage_limit"` to `process/sq_outcome.py`, so D2 check 4 compares a member and never a string. 126's `checkpoint_kind` value set is built from the enum and gains the value with no other edit.
- **`classify` reads entry fields only.** The LLD's sketch passes routing decisions, but every D2 row reads the entry (`awaits_routing` is on `JournalEntry`). The signature is `classify(node, executor, entries) -> Situation`, with `executor` `None` for a node that is not a step.
- **The claimed-id guard needs the owner's node.** `recorded_result_run_ids` maps run id to entry id, and prune uses it unchanged. Task 2.4 adds a sibling read, `recorded_result_run_nodes(project_id) -> dict[str, str]` (run id to node id, same query), which `process/supervisor.py` passes to `SquadronRunIdObserver`. It is documented beside the other three methods.
- **The resumed-from pause.** Confirmation (D6) compares a poll with the `paused_at` the continued entry recorded. Before Observe, the tick reads `store.journal_entry(continues)` for each unresolved `retry`/`accept` continuation and passes the observer a mapping from entry id to that `paused_at` (`datetime | None`). A missing continued entry or an unparseable document maps to `None`, which the confirmation rule treats as "cannot confirm": it waits out the grace period and fails `no_claim_within_grace`.
- **Size.** `tick.py`, `observe.py` and `launch.py` cannot take this slice's code. Task 1.2 moves the act stage out of `tick.py` into `runner/act.py` and splits a `spawn(argv, checkout, logs, popen)` out of `launch()`, behavior unchanged. The resume path of Observe is a new `runner/observe_resume.py` that `RunObserver` delegates to, so `observe.py` grows by a dispatch line or two.
- **The checkout hold names its holders.** D5 lets `ContinuationPlanner` act in a checkout held only by its own step. `dispatch/hold.py` gains `checkout_holders(...) -> Mapping[Path, frozenset[str]]` (node ids), and `held_checkouts` becomes `frozenset(checkout_holders(...))`. `ProjectView` gains `checkout_holders`; `DispatchPlanner` is unchanged.
- **Dispatch facts.** `StepDispatchFacts` gains `resolution: BlockedState | None` (the latest applied resolution with a decision) and `continues: JournalEntry | None` (the latest `sq_run` entry, set for `RESUME` and `REOBSERVE`). `WriteSlicePointer` gains `resolution: str | None`, written as `PARAM_RESOLUTION` on the `cf_write` entry.
- **A failed resume is a `Finished` value.** `runner/observed.py` gains `ResumeFailed(failure, exit_code, tail, document)`, and `finish.record` records it (D6 payload and result). `ResumeFailure` is in `runner/faults.py` beside `LaunchFailure`. `RESULT_RESUME_FAILURE` (`"resume_failure"`) is in `runner/finish.py` beside `RESULT_LAUNCH_FAILURE`.
- **`resume_skipped` is a parameter.** D4 journals it with the entry ("the entry is journaled as an observation, with continuation `observe` and `resume_skipped`"), and the entry has no result until ingestion resolves it. The LLD's "Patterns and Conventions" list calls it a result key; this file follows D4, and Task 9.3's process-contract text names it as a parameter. It is journaled as the parameter `PARAM_RESUME_SKIPPED` with the value `RESUME_SKIPPED_RUN_NOT_AT_PAUSE`, both defined in Task 3.1.
- **Shared names, defined once.** Everything in the LLD's "Patterns and Conventions" list, plus the three journal keys above and the rejection detail texts. Tests import them; they never retype a value.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`.
- **Test doubles.** Pure functions get table-driven tests. Store-backed tests use `Store.open_temporary()`. Tick-level tests use `tests/runner/tick_support.py` and `plan_tick_support.py` with the stub `cf` and stub `sq` on `PATH` under a temporary `HOME`, and a small routing table. Nothing sleeps or runs a real `cf` or `sq`, except Task 9.5's walkthrough step 3.
- **Test location and naming.** New package `tests/runner/resolutions/` (with `__init__.py`). Tests are named for the rule they prove (LLD, Verification Walkthrough step 1).

**Section map.** 1 baseline and the act-stage refactor; 2 store and inbox contract (D9); 3 vocabulary, classify and judge; 4 the resolution stage; 5 dispatch state and the planner; 6 the continuation acts; 7 resume confirmation and failures; 8 routing inputs; 9 inspection, end-to-end proofs, contract text and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and confirm the design's edits
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Run `git status --short`. Uncommitted edits to planning documents (the arch, the initiative plan, the slice or these tasks) are committed to the target first as `docs:`, each file by name. If any other file is dirty, write `BLOCKED:` naming it and stop
- [x] Confirm the edits the LLD lists under "Special Considerations" are present in `user/architecture/120-slices.runner-routing-engine.md` (entries 8 and 9, the 20261020 Notes entry, Future Work 11) and in `120-arch.runner-routing-engine.md` (how stop is held, the `handled` journaling exception). Make any missing edit per the LLD and commit it to the target as `docs:`
- [x] Create `127-slice.resolutions-and-resumption` from the target and switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright`. Record the pass count under this task. If any fails, write `BLOCKED:` with the failure and stop
- [x] Create `src/amoeba/runner/resolutions/__init__.py` (docstring only) and `tests/runner/resolutions/__init__.py`
- [x] **Success:** on the slice branch, the suite is green and both packages exist. Commit `chore: add the resolutions package skeleton`

**Note:** baseline suite 3611 passed; ruff check, ruff format --check and pyright clean.

### Task 1.2: Move the act stage out of the tick and split `spawn` from `launch`
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] Create `runner/act.py` holding the act stage now in `ProjectTick._act`, `_launch`, `_reissue` and `_start`, with the same behavior and the same budget checks. `tick.py` calls it and keeps the `wrote` accounting
- [x] `runner/launch.py`: extract `spawn(argv, checkout, logs, popen) -> ChildHandle | LaunchError` from `launch()`; `launch()` builds its argv and calls it
- [x] **Success:** full suite green with no test changed; `tick.py` and `launch.py` are each under 300 lines. Commit `refactor: extract the act stage and the detached spawn`

**Note:** full suite 3614 passed after the refactor; tick.py 249 lines, launch.py 298 lines.

---

## Section 2: Store and Inbox Contract (D9)

### Task 2.1: Add migration `012` and extend the models
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

- [x] Create `store/schema/012_resolution_decisions.sql` with the six columns and the partial index, per the LLD "Database / Storage Schema". Set `EXPECTED_SCHEMA_VERSION` to 12 in `store/migrations.py`. Add the column-name constants to `store/sql.py` beside `COL_BLOCKED_RESOLUTION_DETAIL`
- [x] In `store/models.py`: `Resolution` gains `decision: str | None` and `instructions: str | None`; add `ResolutionOutcome(StrEnum)` (`applied`, `rejected`); `BlockedState` gains `awaits_runner: bool`, `runner_outcome: ResolutionOutcome | None`, `runner_code: str | None`, `runner_reason: str | None`. All default so existing constructors are unchanged. Export `ResolutionOutcome` from `amoeba.store`
- [x] Update the blocked-state SELECTs in `store/sql.py` and `map_blocked_state` in `store/mapping.py` to read the new columns. An unknown `runner_outcome` text raises `UnknownVocabularyValueError`, as other vocabulary columns do
- [x] Tests: `tests/store/test_migration_012.py`, following `test_migration_011.py`: applies to a populated v11 store, existing rows read null in all six columns and map with `awaits_runner` false, the index exists (its use is asserted in Task 2.3); mapping tests: each new column round-trips and an unknown outcome text raises
- [x] **Success:** tests, existing migration tests and pyright pass. Commit `feat: add migration 012 and carry resolution decisions on blocked states`

### Task 2.2: Add the resolution payload fields and the inbox flag
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 2

- [x] `inbox/envelope.py`: `ResolutionPayload` gains `decision: str | None = None` and `instructions: str | None = None`. Each, when present, must be non-blank after trimming (D1); the value is stored as submitted. The decision vocabulary is not checked here
- [x] `store/inbox_models.py`: add `RESOLUTION_DECISION` and `RESOLUTION_INSTRUCTIONS`
- [x] `store/inbox.py` `_apply_resolution` and `store/_block_writer.py` `_write_resolution`: store both fields, and set `awaits_runner = 1`, in the same transaction, only on the inbox path. `resolve()` (the Runner's own path) passes neither and never sets the flag
- [x] Tests (`tests/store/test_inbox_apply.py`, `tests/inbox/`): a resolution with both fields stores them and is flagged; one with neither is flagged with nulls; a blank decision or blank instructions is refused by the payload model; `store.resolve()` leaves the flag unset; `amoeba submit resolution --help` lists `--decision` and `--instructions` (the flag rule in `cli/submit.py` derives them; no CLI code change)
- [x] **Success:** tests pass. Commit `feat: accept a decision and instructions on resolution submissions`

**Note:** the migration/older-version tests now stage with tests/legacy_nodes.py LEGACY_FILL_RESOLUTION_SLOT.

### Task 2.3: Add `pending_resolutions`, `acknowledge_resolution` and `blocked_state`
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 3

- [x] In `store/blocking.py`, per D9 "Store methods":
  - [x] `pending_resolutions(project_id)`: flagged rows for the project, oldest `resolved_at` first, through the partial index
  - [x] `acknowledge_resolution(blocked_state_id, *, outcome, code=None, reason=None, effect=None)`: one transaction records outcome, code and reason, clears the flag, and applies a `StatusEffect` or `BlockEffect` through the writers 121's `record_routing_decision` uses. `rejected` without code and reason, or `applied` with a code, raises `ValueError`. A row that is unresolved or not flagged raises `InvalidTransitionError`. An effect failure rolls back everything
  - [x] `blocked_state(blocked_state_id) -> BlockedState | None`, usable through a read-only handle
- [x] `tests/store/test_resolutions.py`: ordering; project scoping; applied with no effect; applied with `StatusEffect(done)` marks the node done; rejected with a `BlockEffect` blocks again and the new block is the open one; the argument rules; acknowledging twice raises; an effect that fails (for example done on a node with an unresolved entry) leaves the flag set and nothing written; `blocked_state` through a read-only store; `EXPLAIN QUERY PLAN` of the method's query uses `idx_blocked_states_awaits_runner`
- [x] **Success:** tests pass. Commit `feat: add the store methods for acknowledging resolutions`

### Task 2.4: Add the journal keys and the recovery observer's continuation rules
**Owner**: Junior AI | **Dependencies**: 2.3 | **Effort**: 3

- [x] `store/journal_models.py`: `PARAM_CONTINUATION`, `PARAM_CONTINUES`, `PARAM_RESOLUTION` (Task-level additions). `REQUIRED_PARAMETER_KEYS` is unchanged: all three are optional, on `sq_run`, and `PARAM_RESOLUTION` also on `cf_write` (D9)
- [x] `store/journal.py`: add `recorded_result_run_nodes(project_id)` (Task-level additions). Pass it from `process/supervisor.py` to `SquadronRunIdObserver` as a new required argument `claimed_run_nodes`
- [x] `process/observers/sq_run_id.py`, for an entry carrying `PARAM_CONTINUATION`, per D9 "Recovery observer":
  - [x] the claimed-id guard ignores an owner on the same node; an owner on another node is still `Unknown`
  - [x] no run state (`not_found`, after the grace rule) is `Unknown` with reason `resume_run_missing` (a named constant), never `NotApplied`
  - [x] a state that exists is `InFlight`, as now
- [x] `tests/test_observer_sq_run_id.py`: each rule above, plus an entry without the key behaving exactly as before; `test_continuation_never_reissued` asserts the missing-run answer is `Unknown`
- [x] **Success:** tests pass; `tests/test_import_boundaries.py` passes (the observer imports no Runner module). Commit `feat: recover continuation entries without reissuing them`

**Note:** `tests/load/test_recovery_scale.py::test_a_pass_of_id_bearing_entries_polls_once_each_and_scans_nothing` fails at baseline 41c1f7a too (the load tier is not collected by default); unrelated to this slice.

### Task 2.5: Make the contract suite's stand-in Runner acknowledge resolutions
**Owner**: Junior AI | **Dependencies**: 2.4 | **Effort**: 1

- [x] `tests/contract/runner_tenant.py` `ProofRunner.tick`: acknowledge each `pending_resolutions` row `applied` with no effect, before performing intents
- [x] Run `uv run pytest tests/contract -v`
- [x] **Success:** the contract suite passes with the new payload fields and observer rules. Commit `test: acknowledge resolutions in the contract stand-in Runner`

---

## Section 3: Vocabulary, Classify and Judge (D2, D3)

### Task 3.1: Define the resolution vocabulary
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] Create `runner/resolutions/vocabulary.py` per the LLD "API Contracts": `ResolutionDecision`, `Situation`, `ResolutionRejection`, `Continuation`; `ALLOWED: Mapping[Situation, frozenset[ResolutionDecision]]` from D2's table; the payload reasons `REASON_RESOLUTION_REJECTED`, `REASON_STOPPED`, and the payload keys of D3 (`code`, `detail`, `rejected_blocked_state_id`, `allowed`, `stopped_blocked_state_id`); `PARAM_RESUME_SKIPPED` (`"resume_skipped"`) and its value `RESUME_SKIPPED_RUN_NOT_AT_PAUSE` (`"run_not_at_pause"`)
- [x] `runner/faults.py`: add `ResumeFailure` (D6). `runner/finish.py`: add `RESULT_RESUME_FAILURE` (Task-level additions). `process/sq_outcome.py`: add `CheckpointKind.USAGE_LIMIT` (Task-level additions)
- [x] `tests/runner/resolutions/test_vocabulary.py`: `ALLOWED` matches D2 row for row; `UNRESOLVABLE` and `NO_DECISION` allow nothing; `Continuation` values are `retry`, `accept`, `observe`; 126's `checkpoint_kind` value set contains `usage_limit`
- [x] **Success:** tests pass. Commit `feat: add the resolution vocabulary`

### Task 3.2: Implement `classify`
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 3

- [x] Create `runner/resolutions/classify.py` with the pure `classify(node, executor, entries) -> Situation` (Task-level additions), testing rows in D2's order: `unresolvable`, `no_decision`, `paused_run`, `completed_outcome`, `ended_run`, `before_run`
- [x] "Paused" and "completed" are read from the latest `sq_run` entry's `RESULT_OUTCOME` (`runner/ingest/record.py`) against `RunOutcome` values, never from the block kind. `completed_outcome` also requires no `RESULT_RESUME_FAILURE` in the result. A `cf_write` latest entry, or no entry, is `before_run`
- [x] `tests/runner/resolutions/test_classify.py`, table-driven over every D2 row and the order cases: an unrouted pause is `unresolvable`; a failed resume (outcome `paused`, with `resume_failure`) is `paused_run`; a `run_missing` resume (outcome `not_found`) is `ended_run`; a paused run whose step is blocked on `HUMAN` is still `paused_run`; a human step is `no_decision`; a recovery-resolved entry is `ended_run`
- [x] **Success:** tests pass; `classify` does no I/O. Commit `feat: classify a blocked step for its resolution`

**Note:** the signature is `classify(executor, entries)`; the `node` argument the task text lists was dropped because nothing reads it.

### Task 3.3: Implement `judge_resolution`
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 3

- [x] Create `runner/resolutions/judge.py` with the frozen `Acknowledgment(outcome, code, reason, effect)` and the pure `judge_resolution(blocked, situation, checkpoint) -> Acknowledgment`
  - [x] Checks 0–7 in D2's order; the first failure is the rejection. `checkpoint` is the latest `sq_run` entry's `outcome_document.checkpoint`, parsed with 125's model; a document that does not parse is passed as `None` (D2)
  - [x] Effects per D3's table: a rejection's `BlockEffect` on `HUMAN` with context `resolution rejected: <code>` and payload `{reason, code, detail, rejected_blocked_state_id, allowed}` (`allowed` sorted, as values); `stop`'s `BlockEffect` with context `stopped by <resolved_by>`; `accept` on `completed_outcome` is `StatusEffect(done)`; the rest have none
  - [x] Add a small helper in the same module, `checkpoint_of(entry) -> RunCheckpoint | None`, used by the stage, that never raises for a bad document
- [x] `tests/runner/resolutions/test_judge.py`, table-driven over every check and every D3 row, including `test_accept_refused_when_not_at_loop` (`is_loop` false and null), `usage_limit_pause` at a loop, `checkpoint_unknown` for a null kind and for a null `paused_at`, `interactive_checkpoint` for retry, `instructions_not_applicable` for handled, rerun and stop, a decision on a human step (`decision_not_applicable`), a bare resolution of a human step (applied, no effect), a bare resolution of a pipeline step (`decision_required`), an unparseable document (`checkpoint_unknown`)
- [x] **Success:** tests pass; no rejection raises. Commit `feat: judge a resolution against its situation`

---

## Section 4: The Resolution Stage (D3)

### Task 4.1: Implement `apply_pending_resolutions`
**Owner**: Junior AI | **Dependencies**: 2.3, 3.3 | **Effort**: 2

- [x] Create `runner/resolutions/stage.py` with `apply_pending_resolutions(store, project_id, tree, context) -> bool` (whether anything was acknowledged). For each pending row, oldest first: set `context` to its node, read the node's entries, find its step and executor through the lifecycle tree and `STEP_MAP`, `classify`, `judge_resolution`, then `acknowledge_resolution`
- [x] Store errors propagate unchanged (D3, "Store failures")
- [x] `tests/runner/resolutions/test_stage.py`, store-backed: one applied and one rejected resolution in the same call, each with its effect; ordering; a second call does nothing; a rejection's new block is open and carries `allowed`
- [x] **Success:** tests pass. Commit with Task 4.2

### Task 4.2: Run the stage first in the project tick
**Owner**: Junior AI | **Dependencies**: 1.2, 4.1 | **Effort**: 3

- [x] `runner/tick.py`: call the stage right after `_apply_intents` and before Observe, with the context cleared afterwards, and fold its result into `self.wrote`. No budget check (it starts no subprocess). The tree the stage needs is built the way `_build_view` builds it; if that needs a store read the view also makes, read it once
- [x] Tick tests (`tests/runner/resolutions/test_tick_stage.py`): a resolution submitted and applied by the inbox is acknowledged in the next project tick, before any planner sees the node; `test_poisoned_resolution_is_contained`: one step's resolution with an unparseable outcome document is rejected, and another step's finished run in the same project is still ingested that tick
- [x] Run `uv run pytest -q`. Every failure caused by a pipeline step's bare inbox resolution now being rejected `decision_required` (D2, check 2) is changed to submit the decision the test means (usually `rerun`), or to call `store.resolve()` where the test is about the store and not the Runner. Any other failure is a defect: fix it here, or write `BLOCKED:` with the failure
- [x] **Success:** full suite green. Commit `feat: acknowledge pending resolutions at the start of each project tick`

**Note:** full suite 3754 passed; no existing test needed its bare inbox resolution changed.

---

## Section 5: Dispatch State and the Continuation Planner (D5)

### Task 5.1: Extend `dispatch_state` with the latest applied resolution
**Owner**: Junior AI | **Dependencies**: 2.4, 3.1 | **Effort**: 2

- [x] `runner/dispatch/state.py`: add `RESUME` and `REOBSERVE`; the signature becomes `dispatch_state(entries, resolution, *, pointer_confirmed)`. After the `IN_FLIGHT` and `AWAITING_ROUTING` checks, a resolution with `runner_outcome` `applied` and a decision that no entry names in `PARAM_RESOLUTION` decides per D5's table (`rerun` is `NEEDS_POINTER`, even where 125 would say `REISSUE`). Otherwise 125's rules apply unchanged
- [x] `tests/runner/dispatch/test_state.py`, table-driven over D5's rows: each decision unnamed and named; a `rerun` after a `not_applied` entry; a rejected or undecided resolution changes nothing; an unresolved continuation is `IN_FLIGHT`
- [x] Update every existing caller and test of `dispatch_state` to the new signature, passing `resolution=None`; their expected states do not change
- [x] **Success:** tests pass. Commit with Task 5.2

### Task 5.2: Carry the resolution, the continued entry and the checkout holders into the view
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 3

- [x] `runner/dispatch/build_view.py` `_facts_for`: read `blocked_state_for(node.id, include_resolved=True)`; pass it to `dispatch_state` only when it is applied with a decision; set `StepDispatchFacts.resolution` and, for `RESUME`/`REOBSERVE`, `continues` (Task-level additions). Add `RESUME` and `REOBSERVE` to `_NEEDS_CHECKOUT`
- [x] `runner/dispatch/hold.py`: `checkout_holders` and the derived `held_checkouts`; `ProjectView` gains `checkout_holders` (Task-level additions)
- [x] Tests: facts for a step with an applied `retry` are `RESUME` with `continues` set; a paused run's checkout is held by its own node only; a pointed step and an in-flight run in one checkout name both holders; existing hold and view tests pass
- [x] **Success:** tests pass. Commit `feat: derive resume and reobserve states from applied resolutions`

**Note:** the dispatch tests in tests/runner/dispatch/test_view_resolution.py build the view with DispatchRig and build_dispatch_view directly.

### Task 5.3: Add `ResumeRun`, `ObserveRun` and `ContinuationPlanner`
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 3

- [x] `runner/decide.py`: add the two frozen dataclasses per the LLD "API Contracts" and widen `Action`
- [x] Create `runner/resolutions/planner.py` with the pure `ContinuationPlanner`: for each current pipeline step in `RESUME` or `REOBSERVE` with a resolved checkout, emit `ResumeRun` (decision `retry` or `accept` as `Continuation`) or `ObserveRun`, with run id, checkout and `continues` from the continued entry and `resolution` the blocked state id. It acts when the checkout's holders are empty or only the step itself; otherwise it waits
- [x] `tests/runner/resolutions/test_planner.py`: one action per eligible step; a checkout held by another node waits; a held step (not current) gets nothing; `DispatchPlanner` and `ContinuationPlanner` never act on the same step; `decide` accepts the new actions under the current-step guard
- [x] **Success:** tests pass. Commit `feat: plan resumes and observations for resolved steps`

### Task 5.4: Carry the resolution on a rerun's pointer write
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 1

- [x] `runner/dispatch/planner.py` `_action` sets `WriteSlicePointer.resolution` from the facts' resolution when its decision is `rerun`; `runner/dispatch/pointer.py` writes it as `PARAM_RESOLUTION` on the `cf_write` entry
- [x] Tests: the pointer write after a `rerun` names the resolution, and the next `dispatch_state` follows 125's rules; a pointer write with no resolution has no key
- [x] **Success:** tests pass. Commit `feat: name the carried-out resolution on a rerun's pointer write`

---

## Section 6: The Continuation Acts (D4)

### Task 6.1: Add the stub `sq`'s resume mode
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

- [x] Add `sq run --resume <id> [--decision D] [--instructions T]` to the stub per the LLD "Technology Choices": environment-configured claim delay, exit code and resulting outcome (pause again with a new `paused_at`, complete, refuse with exit 2, exit before the claim, never claim). It records its argv to the stub log, and a missing run exits 1. Put the resume code in a new `tests/sq_stub_resume.py` so `tests/sq_stub.py` stays near 300 lines
- [x] `tests/test_sq_stub_run.py`: each mode leaves the documented state; the argv log holds the instructions element unchanged
- [x] **Success:** tests pass. Commit `test: add a resume mode to the stub sq`

**Note:** the resume-mode tests are in tests/test_sq_stub_resume.py (a new file, to keep test_sq_stub_run.py from growing), and sq_stub.py is 304 lines.

### Task 6.2: Record a failed resume
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 2

- [x] `runner/observed.py`: `ResumeFailed` (Task-level additions). `runner/finish.py`: `record` handles it per D6: block on `HUMAN` with `{reason: resume_failed, resume_failure, run_id, exit_code, stderr_tail}` (4 KiB tail), resolve `failed` with `{run_id, outcome, outcome_document, resume_failure}`; outcome `paused` and the last poll for every failure except `run_missing`, whose outcome is `not_found`
- [x] `tests/runner/test_finish.py`: the block payload and result for `refused` and for `run_missing`; a failed resume keeps the checkout held (`held_checkouts`) and `classify` reads `paused_run`; after `run_missing` the hold is released and `classify` reads `ended_run`
- [x] **Success:** tests pass. Commit `feat: record failed resumes`

### Task 6.3: Decide the act from the pre-poll, and build the resume command line
**Owner**: Junior AI | **Dependencies**: 3.1, 5.3 | **Effort**: 2

- [x] Create `runner/resolutions/argv.py` with the flag constants `--resume`, `--decision`, `--instructions` and `resume_argv(run_id, decision, instructions) -> list[str]` per D4 step 3. The instructions are one element; no pipeline, `-p` or `--run-id`. `observe` is refused with `ValueError`
- [x] Create `runner/resolutions/prepoll.py` with the pure `prepoll_decision(action, poll, resumed_from)` per D4 step 1: a `PollFailure` is wait; `not_found` is run missing; a `ResumeRun` whose run is paused at `resumed_from` is launch; any other `ResumeRun` poll is observe with `PARAM_RESUME_SKIPPED` set to `RESUME_SKIPPED_RUN_NOT_AT_PAUSE` (Task-level additions); an `ObserveRun` with a run state is observe
- [x] Tests: argv for retry and accept, with and without instructions; instructions with spaces, quotes, newlines and non-ASCII are one element, byte for byte; `prepoll_decision`, table-driven over every branch
- [x] **Success:** tests pass; both modules do no I/O. Commit `feat: decide continuation acts from the pre-poll`

### Task 6.4a: Implement the continuation act's pre-poll, wait, run-missing and observe branches
**Owner**: Junior AI | **Dependencies**: 1.2, 2.4, 6.2, 6.3 | **Effort**: 3

- [x] Create `runner/resolutions/act.py` with `act_continuation(...)`, called from `runner/act.py` for `ResumeRun` and `ObserveRun`, in D4's order: budget check, one `observer.poll_run`, `prepoll_decision`, then:
  - [x] wait: write nothing; a `PollFailure` adds a `run_observation_failed` fault. A spent budget returns cut-off with nothing written
  - [x] run missing: journal the continuation entry, then record `ResumeFailed(run_missing)` through `finish.record`; launch nothing
  - [x] observe: after a second budget check, journal the entry (`PARAM_CONTINUATION` `observe`, `PARAM_CONTINUES`, `PARAM_RESOLUTION`, `PARAM_RESUME_SKIPPED` when set, plus the continued `pipeline`, `params`, `run_id`, `checkout`); launch nothing. Put the journaling in a helper that Task 6.4b reuses
  - [x] launch decision: raises `NotImplementedError("resume launch: Task 6.4b")`. No tick reaches it, because `ContinuationPlanner` is not registered until Task 7.3
- [x] `tests/runner/resolutions/test_act.py`: a spent budget and a failed pre-poll write nothing and the step stays `RESUME`; `test_missing_run_launches_nothing`; `test_run_moved_by_hand_is_observed`; `handled` journals and launches nothing; a run not at its pause is observed with `resume_skipped`
- [x] **Success:** tests pass. Commit `feat: observe continuation runs and handle a missing run`

**Note:** the act stage now takes the tick's TickFaults and the tick raises them after the act stage, because a failed pre-poll adds run_observation_failed there.

### Task 6.4b: Implement the continuation act's launch branch
**Owner**: Junior AI | **Dependencies**: 6.1, 6.4a | **Effort**: 2

- [x] Replace the `NotImplementedError` in `act_continuation` with the launch path: after a second budget check, journal the entry with the decision's continuation (`retry` or `accept`) through the Task 6.4a helper, then `spawn` `resume_argv` in the checkout with the instructions read from `store.blocked_state(resolution)`, logs named by the entry id. Track the child; a `LaunchError` records `ResumeFailed(spawn_error)`. Keep each function near 50 lines; move the launch path to `runner/resolutions/launch_act.py` if `act.py` passes 300 lines
- [x] Tests (same file): the stub's argv log shows `--resume <id> --decision retry --instructions <text>` with no `--run-id`, pipeline or `-p`; `accept` passes `--decision accept`; the entry is journaled before the spawn; a spawn error blocks with `spawn_error`
- [x] **Success:** tests pass. Commit `feat: resume paused runs for applied resolutions`

---

## Section 7: Resume Confirmation and Failures (D6)

### Task 7.1: Implement the pure confirmation rule
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 2

- [ ] Create `runner/resolutions/confirm.py` with `resume_progress(poll, resumed_from, exit_code, past_grace) -> Confirmed | StillResuming | ResumeFailure` per D6: confirmed on any outcome other than `paused`, or `paused` with a different `paused_at`; `not_found` is `run_missing`; at the old pause, exit 2 is `refused`, another exit code is `exited_before_claim`, no child and past grace (or a child still running past grace) is `no_claim_within_grace`; otherwise still resuming. `resumed_from` `None` never confirms on a pause (Task-level additions)
- [ ] `tests/runner/resolutions/test_confirm.py`, table-driven over every D6 row, including `test_retry_confirmed_by_new_paused_at` and `timed_out` confirming
- [ ] **Success:** tests pass. Commit `feat: add the resume confirmation rule`

### Task 7.2: Observe continuation entries
**Owner**: Junior AI | **Dependencies**: 2.4, 6.2, 7.1 | **Effort**: 3

- [ ] Create `runner/observe_resume.py`; `RunObserver._observe_one` sends a `retry`/`accept` continuation that is not confirmed in memory to it, whether or not it is tracked. It polls on `run_poll_interval_seconds` under the budget, applies `resume_progress`, confirms in the tracker on `Confirmed` and then classifies the poll as `_confirmed` does, and ends with `ResumeFailed` on a failure. `observe` continuations take the existing confirmed path unchanged. `observe` takes the resumed-from mapping as a new argument (Task-level additions), and `ProjectTick` builds that mapping before Observe and passes it, so the suite stays green at this commit
- [ ] `tests/runner/resolutions/test_observe_resume.py`, with a fake poll and tracker: a run that stays paused then claims is confirmed by the first poll after the claim; a new `paused_at` ends the run as a pause; the tick builds the mapping from the continued entries (a missing entry and an unparseable document map to `None`); exit 2, exit before claim and no claim within grace each end with their failure; with no tracked child (after a restart) only the grace rule applies
- [ ] **Success:** tests pass; `observe.py` grows only by the dispatch to `observe_resume.py` and the new argument (a few lines). Commit `feat: confirm resumes by run state`

### Task 7.3: Register the continuation planner and prove resumes in the tick
**Owner**: Junior AI | **Dependencies**: 4.2, 6.4b, 7.2 | **Effort**: 3

- [ ] Add `ContinuationPlanner()` after `DispatchPlanner()` in `PRODUCTION_PLANNERS` (`runner/factory.py`); update `tests/runner/test_factory.py`
- [ ] Tick tests (`tests/runner/resolutions/test_tick_resume.py`), from an applied retry through to routing: confirmed and completed, ingested and routed; a new pause after the retry is recognized by its new `paused_at`, ingested, and routed to escalate; a `handled` resolution on a run that has moved on is observed, its current outcome ingested and routed. Failed-resume ticks are proven in Task 8.2, after `resume_failed` exists as a routing input
- [ ] **Success:** tests pass. Commit `feat: run resumes and their confirmation in the tick`

### Task 7.4: Watch the pointer of continuation entries
**Owner**: Junior AI | **Dependencies**: 7.3 | **Effort**: 1

- [ ] `runner/dispatch/pointer_watch.py` `watched_runs`: for an entry carrying `PARAM_CONTINUATION`, keep the step's latest pointer write for the worktree and slice index, and use the continuation's `issued_at` as the start, so only snapshots after it count (LLD "Consumes from Other Slices", 125)
- [ ] Tests (`tests/runner/dispatch/`): a pointer moved after a continuation's `issued_at` is reported; a move before it, during the pause, is not; a non-continuation entry is unchanged
- [ ] **Success:** a pointer moved while a resumed run is in flight raises 125's pointer-moved fault, a move during the pause does not, and the existing pointer-watch tests pass unchanged. Commit `feat: watch the pointer of continuation entries`

### Task 7.5: Prove crash safety
**Owner**: Junior AI | **Dependencies**: 7.3 | **Effort**: 3

- [ ] Extend `tests/runner/test_crash_recovery.py` and `crash_harness.py` with 125's `SIGKILL` pattern at two new kill points (LLD "Testing approach"): after an acknowledgment, before the continuation is journaled (the next tick issues it once); after a resume is journaled, before the launch (recovery leaves it in flight, Observe fails it `no_claim_within_grace`, and the stub log shows no resume launched)
- [ ] **Success:** tests pass. Commit `test: prove resumes survive a crash at both kill points`

---

## Section 8: Routing Inputs (D8)

### Task 8.1: Add `resume_failed` and `review_accepted`
**Owner**: Junior AI | **Dependencies**: 7.3 | **Effort**: 3

- [ ] `runner/routing/inputs.py`: `outcome` gains `resume_failed`; new input `RoutingInput.REVIEW_ACCEPTED` with `true`, `false`, `none` and `unknown`
- [ ] `runner/routing/reduce.py` and `evidence.py`: `OutcomeEvidence` gains `resume_failed` and the continuation and continued `verdict_ids`; `RESULT_RESUME_FAILURE` takes precedence over `outcome` as `launch_failure` does; `review_accepted` per D8. `gather` reads the continued entry once (`store.journal_entry`), so `reduce` stays pure
- [ ] Tests in `tests/runner/routing/`: reduction of each new value; table validation still accepts the shipped table; recompute of a pre-127 decision record (with no `review_accepted`) still matches, or fails with the error 126 defines for a changed vocabulary. If neither holds, write `BLOCKED:` with the failure
- [ ] **Success:** tests pass. Commit with Task 8.2

### Task 8.2: Add `advance-on-accepted-review` to the shipped table
**Owner**: Junior AI | **Dependencies**: 7.3, 8.1 | **Effort**: 2

- [ ] `runner/routing/tables/default.yaml`: the rule per D8, after `advance-on-stated-pass`
- [ ] Tick test: an accepted CONCERNS loop whose final review is the accepted one routes through `advance-on-accepted-review`; one that wrote a newer review routes on that review; a failed resume escalates; exit 2, exit before claim and no claim within grace each block the step with their `ResumeFailure`, route `resume_failed` to escalate once, and the node offers the paused-run decisions again
- [ ] **Success:** tests pass. Commit `feat: route accepted reviews and failed resumes`

---

## Section 9: Inspection, End-to-End Proofs, Contract Text and Final Validation

### Task 9.1: Add `blocked_state_id` to `inspect blocked`
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 1

- [ ] `inspection/__init__.py` and `inspection/core.py` `blocked_rows`: add the column from `BlockedNode.blocked_state.id`
- [ ] Update the inspection and CLI tests that pin the columns
- [ ] **Success:** tests pass. Commit `feat: show the blocked state id in inspect blocked`

### Task 9.2: Prove each decision end to end with the stub `sq`
**Owner**: Junior AI | **Dependencies**: 4.2, 5.4, 8.2, 9.1 | **Effort**: 3

- [ ] `tests/runner/resolutions/test_decisions_e2e.py`, through `amoeba submit resolution` and ticks, for the decisions no earlier task proves at tick level (retry, accept and handled are proven in Tasks 6.4b and 7.3): accept of an escalated completed outcome marks the step done and the successor's pointer write follows next tick, and `blocked_state` and the latest entry's `verdict_ids` give the identifiable accept (D7); rerun after a routed outcome and after `not_applied`; stop blocks with `reason: stopped` and nothing is issued; a held step's resolution is acknowledged and its resume waits until the hold is removed
- [ ] Source test: no Runner module other than `runner/resolutions/act.py` reads `Resolution.instructions`, and none builds an `--instructions` element except `argv.py` (use `tests/ast_strings.py` as other source tests do)
- [ ] **Success:** tests pass. Commit `test: prove each resolution decision end to end`

### Task 9.3: Update the contract documents
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 2

- [ ] Per the LLD "Provides to Other Slices", "Contract documents": `docs/inbox-contract.md` (fields, rules, the Runner's answer, codes, the no-secrets rule for instructions, and the change for existing submitters: a bare resolution of a pipeline step is now rejected `decision_required`); `docs/store-contract.md` (migration `012`, the three methods, `recorded_result_run_nodes`); `docs/process-contract.md` (the resolution stage, continuation entries, resume confirmation, the observer's continuation rules, the `resume_skipped` parameter); `docs/substrate-guide.md` (the 120 row)
- [ ] **Success:** every name in the text matches the code. Commit `docs: document resolutions and resumption`

### Task 9.4: Add the CHANGELOG entry
**Owner**: Junior AI | **Dependencies**: 9.3 | **Effort**: 1

- [ ] Under `[Unreleased]` in `CHANGELOG.md`: the decisions, the Runner's answer, resumes, the new routing rule, the `inspect blocked` column, migration `012`, and the `decision_required` change for existing submitters
- [ ] **Success:** Commit `docs: add the resolutions and resumption changelog entry`

### Task 9.5: Final validation and walkthrough
**Owner**: Junior AI | **Dependencies**: 9.4 | **Effort**: 2

- [ ] Run LLD Verification Walkthrough steps 1 and 2. Record the pass count under this task
- [ ] Run step 3 on a scratch copy (real `sq`, one P4 run, plus P5 if the accept advances it). Record what happened, including which branch (completed or paused) was taken. Pause the project and `amoeba stop` when done. A failure caused by this slice's code is fixed here; anything else gets an issue and a note under this task
- [ ] Confirm every source file this slice created is near 300 lines, that no file this slice changed grew past it (`observe.py` was already over before this slice and may keep only its dispatch lines), and that pyright strict is clean
- [ ] **Success:** steps 1–3 behave as the LLD expects. Commit `docs: record slice 127 validation`
