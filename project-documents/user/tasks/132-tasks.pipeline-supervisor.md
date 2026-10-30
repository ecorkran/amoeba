---
docType: tasks
slice: pipeline-supervisor
project: amoeba
lld: user/slices/132-slice.pipeline-supervisor.md
dependencies:
- 128
projectState: Slices 120–128 are merged. The Runner (`src/amoeba/runner/`, 12057 lines
  on 20261029) steps each slice through P4, P5 and P6 step nodes, writes CF's pointers
  before each launch, reads CF's gate at completion and before dispatch, routes every
  outcome through a table (`routing/`), records the ungate hatches, applies a merge
  policy and observes merges. Squadron 0.24.9 is installed. Nothing of slice 132 is
  built.
dateCreated: 20261029
dateUpdated: 20261029
status: in_progress
turns: 54
promptTokens: 4789658
cachedTokens: 4635143
cacheWriteTokens: 154431
completionTokens: 51562
durationSeconds: 458.2
costUsd: 3.194335
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.194335400000001
    completionTokens: 51562
revision_number: 2
---

## Context Summary

- Working on the **pipeline-supervisor** slice (132), the last slice of initiative 120. It cuts the Runner to a supervisor over each project's Squadron pipeline: one launch of the configured pipeline per driven slice, an outcome map, automatic resume of transient failures, question blocks for 140, two resolutions, intents without `until`, one blocked list across projects, and the deletion of the policy layer the pipeline owns.
- **Current state:** see `projectState`.
- **Dependencies:** 128 and everything before it, merged. Squadron 0.24.9 by shape (LLD D10).
- **What this slice delivers:** `runner/supervise.py`; the config keys `pipeline` and `params`; the setting `auto_resume_limit`; the store's atomic-completion option; slice-level dispatch with no pointer write; automatic resume; the cut vocabularies; `amoeba inspect blocked` across projects; the deletions in D9; contract text and CHANGELOG.
- **Next planned work:** 140 (question answerer) and 160 (notification bridge), which read what this slice writes.

**Branch:** all implementation happens on `132-slice.pipeline-supervisor`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/132-slice.pipeline-supervisor.md` at the named decision (D1–D11), "Architecture" or "Implementation Details". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/` or `docs/`. Keep every new or changed source file near 300 lines and each function near 50.

**Order and dependencies:** work tasks in file order. Each task's **Dependencies** lists only its real prerequisites. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off; only its dependents wait. The LLD's invariant holds after every task: the resident process starts and the full suite passes.

**Commit cadence:** each task ends in one commit. Run `uv run ruff format .` before each commit. Commit types: `feat:` new behavior, `refactor:` behavior-preserving change or a deletion of unused code, `test:` test-only work, `docs:` contract text. Deleting a module deletes its tests in the same commit; a test of a surviving behaviour that imported a deleted module is rewritten against the slice model, not removed (LLD "Patterns and Conventions").

**Order versus the LLD's Migration Plan.** The LLD orders config and dispatch first. Dispatch cannot move to slice nodes while routing, the CF outcome read and the step map are still on the tick, because each of them keys on a step. So this breakdown adds every new piece first (Sections 2–5), takes the post-completion policy off the tick (Section 6), adds automatic resume (Section 7), cuts the vocabularies (Section 8), then switches dispatch to slice nodes in one sequence (Section 9) and deletes what is left unused (Section 10). Every step of the Migration Plan is covered; only the order differs. Task 1.1 records this in the LLD.

**Task-level additions to the LLD** (code facts the LLD does not state, checked against the code on 20261029; each resolves a placement, not a product decision):
- **What survives of `gates/`.** The LLD keeps "the git half of `predispatch.py`". The dispatch check also uses `gates/candidates.py` (`launch_candidates`), `gates/dispatch_reads.py` (the reads, `check_candidate`), the target read in `gates/cf_reads.py` (`read_target`, `read_config`, `DEFAULT_TARGET_BRANCH`, needed for "on the target") and the dispatch half of `gates/stage.py` (`GateStage.check_dispatch`). These survive with their CF gate parts removed and move to `runner/dispatch/` in Task 10.2: `checkout_check.py` (the rules, as the LLD names it), `candidates.py`, `checkout_reads.py` (reads and `read_target`/`read_config`) and `check_stage.py` (the stage). `context-forge-contract.md` says the Runner still reads `git.integration_branch`.
- **Atomic completion lives on `record_runner_report`.** `runner/ingest/record.py` already resolves the entry and marks `runner_issued` in one call, `Store.record_runner_report(entry_id, reviews, outcome=, result=)`. The option is an added keyword `complete_node_id: str | None = None`: when set, that node is marked `done` in the same transaction.
- **The transient-resume record.** Ingest decides "under the bound" and resolves the entry with the outcome document, as now. The view lists a resume candidate from the slice's latest resolved `sq_run` entry: `DispatchState` gains `AUTO_RESUME` beside `RESUME`, set by `dispatch/state.py` when that entry's outcome classifies `TRANSIENT` and the slice is not blocked. `resets_at` is read from the entry's result by Decide, not by state.
- **The count function** is `supervise.resume_count(entries, step) -> int` over the slice's `sq_run` entries newest first, pure, and is the only place the D5 rule is written. Ingest calls it.
- **`ResumeRun` after the cut:** `node_id`, `run_id`, `continues`, `checkout`, `cause: ResumeCause`, `instructions: str | None`, `resolution: str | None` (set only for `cause=resolution`), `journal_extra`. `ResumeCause` (`transient`, `resolution`) and `PARAM_RESUME_CAUSE` live in `resolutions/vocabulary.py` beside `PARAM_*` (LLD "Patterns and Conventions").
- **The blocked listing.** A `Listing` today has either `rows` (one project) or `supervisor_rows` (all). `blocked` gets both: `read_listing` uses `rows` when the request names a project and `supervisor_rows` when it does not. The supervisor rows open each store from `discover_project_ids` read-only, as `projects` does.
- **`launch.py` is at 305 lines.** New launch constants go in `dispatch/params.py`, not `launch.py`.
- **The routing package data.** `tests/runner/routing/test_wheel_contents.py` checks the wheel carries `routing/tables/default.yaml`. Delete it with `routing/`, and remove any package-data entry for the table from `pyproject.toml`.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`.
- **Test doubles.** Pure functions get table-driven tests. Store-backed tests use `Store.open_temporary()`. Tick-level tests use `tests/runner/tick_support.py`, `tests/runner/dispatch/tick_rig.py` and `plan_tick_support.py` with the stub `cf` and `sq` on `PATH` under a temporary `HOME`, and a real temporary git repository (`tests/runner/git_repo.py`) as the checkout. Nothing runs a real `sq` except Task 13.3.

**Section map.** 1 baseline; 2 config and settings (D2, D5 setting); 3 Squadron shapes (D10); 4 store atomic completion (D4); 5 `supervise.py` (D4, D5); 6 ingest by the outcome map; 7 automatic resume (D5); 8 resolutions and intents (D6, D7); 9 the slice switch (D1, D3, D11); 10 deletions (D9, D11); 11 blocked list (D8); 12 end-to-end; 13 docs and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting point
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Run `git status --short`. Uncommitted edits to planning documents (the arch, the initiative plan, the slice or these tasks) are committed to the target first as `docs:`, each file by name. If any other file is dirty, write `BLOCKED:` naming it and stop
- [x] Fold this file's "Task-level additions" and "Order versus the LLD's Migration Plan" into the LLD, so the code review compares against one design: the surviving `gates/` modules and their new homes in "Component Structure"; `complete_node_id`, `DispatchState.AUTO_RESUME`, `resume_count` and the `ResumeRun` fields in "API Contracts"; the order note under "Migration Plan". Commit to the target as `docs:`
- [x] Confirm issue #22 exists and is open (`gh issue view 22`)
- [x] Create `132-slice.pipeline-supervisor` from the target and switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright`. If any fails, write `BLOCKED:` with the failure and stop
- [x] Record under this task: the pass count, and `find src/amoeba/runner -name '*.py' | xargs wc -l | tail -1` (the "before" line count for the final commit message)
- [x] **Success:** the planning edits are committed to the target; on the slice branch, the suite is green and both numbers are recorded. No commit on the slice branch

Baseline (20261029): 4419 tests passed; ruff check, ruff format and pyright clean; runner 12057 lines.

---

## Section 2: Config and Settings (D2, D5)

### Task 2.1: Add `pipeline` and `params` to the project config
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] `runner/project_config.py`: each project entry gains `pipeline: str | None` and `params: Mapping[str, str]` (empty by default). `merge_policy` stays for now; Task 10.4 removes it. `ProjectSettings` carries both. A project the file does not name has `pipeline` `None` (no default pipeline, D2)
- [x] Load-time validation per D2, every problem listed in one `StartupFailedError`: a key `slice`; a key containing `,` or `=`; a value containing `,`; a non-string value; an entry naming a project with no `pipeline`; any key beside `pipeline`, `params` and `merge_policy` (Task 10.4 removes `merge_policy` from that list). The pipeline name itself is not validated. Reuse the forbidden-character rule `build_argv` enforces (import it, do not copy it)
- [x] Update the loader's docstring: `params` are pipeline parameters and hold no secrets (LLD "Special Considerations")
- [x] `tests/runner/test_project_config.py`: a named project with and without `params`; an unnamed project gives `pipeline` `None`; each failure; two problems in one file both named, the `slice` one as `projects.<id>.params.slice`
- [x] **Success:** tests pass, existing config tests pass. Commit `feat: name the pipeline and its parameters per project`

### Task 2.2: Add the `auto_resume_limit` setting and flag
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 1

- [x] `process/settings.py`: `auto_resume_limit: int = 3`, defined once there, documented as the most consecutive automatic resumes of one run at one step (D5). Reject a value below 1 at load with the existing validation style
- [x] `cli/settings_flags.py`: `--auto-resume-limit N`
- [x] Tests in `tests/test_settings_flags.py`: default 3; the flag sets it; 0 is refused
- [x] **Success:** tests pass. Commit `feat: add the auto-resume limit setting`

---

## Section 3: Squadron Shapes (D10)

### Task 3.1: Read `question`, `resets_at` and `agent_text`
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] `process/sq_outcome.py`: `RunCheckpoint` gains `question: str | None` and `resets_at: datetime | None`; `RunFailure` gains `agent_text: str | None`; `CheckpointKind` gains `AGENT_QUESTION = "agent_question"`. All optional; an absent field is `None`; extra keys are still ignored
- [x] Capture one `sq runs wait <id> --timeout 0 --json` document per new shape from the installed `sq` if one is reachable without a paid run; otherwise build the fixtures from the LLD's field list and say so in the fixtures README. Add them to the existing sq run fixtures (`tests/sq_run_fixtures.py` or its fixture directory) with the `sq` version and date
- [x] Tests in `tests/test_observer_sq_outcome_fields.py`: each new field parsed; each absent gives `None`; `agent_question` with no `question`; a `resets_at` with a timezone offset; an unknown checkpoint kind still parses as unknown
- [x] **Success:** tests pass; the existing shape probe still passes. Commit `feat: read Squadron's question, resets_at and agent_text`

---

## Section 4: Store Atomic Completion (D4)

### Task 4.1: Add `complete_node_id` to `record_runner_report`
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] `store/runner_report.py` (and the `Store` method that calls it): the keyword `complete_node_id: str | None = None` (Task-level additions). When set, the node is marked `done` in the same transaction that resolves the entry and marks `runner_issued`. 121's `done`-terminal rule is unchanged: an already `done` node is not an error; a node in any state the rule forbids raises as a direct status write would
- [x] `docs/store-contract.md`: document the option beside `record_runner_report`, and why (a crash between two writes would relaunch a completed run, D4)
- [x] Contract test in `tests/contract/` (the one test D4 adds): with the option, the entry is resolved and the node `done`; with a fault injected after the node write (`tests/fault_injection.py`), neither change is visible; without the option, behaviour is unchanged. 100's existing contract tests pass unchanged
- [x] **Success:** tests pass. Commit `feat: resolve an entry and complete its node in one transaction`

---

## Section 5: The Supervisor Rules (D4, D5)

### Task 5.1: Implement `supervise.classify`
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 2

- [x] Create `runner/supervise.py`, pure: `OutcomeClass` (`COMPLETED`, `TRANSIENT`, `QUESTION`, `BLOCKED`); `classify(observed) -> OutcomeClass` over a run document, vanished, launch failed or resume failed, per the D4 table. Define once here: the payload reasons `agent_question`, `paused`, `failed`, `auto_resume_exhausted`, and the transient failure kinds `provider_error` and `stall`
- [x] `usage_limit` is `TRANSIENT` only with `resets_at`; without it, `BLOCKED`. `agent_question` with no `question` is still `QUESTION` (D10)
- [x] `tests/runner/test_supervise.py`, table-driven: one case per D4 row, plus every listed `paused` and `failed` kind of the "any other" rows and an unknown kind of each
- [x] Add a purity test for `supervise.py` in `tests/runner/test_supervise.py`, using `io_use` from `tests/runner/gates/purity.py` for now (Task 10.2 moves that helper to `tests/runner/purity.py` and fixes this import). It must outlive `gates/`: `supervise.py` imports nothing that does I/O
- [x] **Success:** tests pass. Commit `feat: add the outcome map`

### Task 5.2: Implement the resume bound
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 3

- [x] `supervise.py`: `step_of(document) -> str | None` (`checkpoint.step` or `failure.step`); `resume_count(entries, step) -> int` per D5 (Task-level additions). Count trailing `sq_run` entries with `resume_cause` `transient` whose resumed-from outcome stopped at `step`; an `orphaned` outcome with no step counts as the step of the entry before it; a fresh launch, a `resolution` resume or a different step ends the run of entries
- [x] `resume_ready(document, now) -> bool`: true for every `TRANSIENT` outcome except a `usage_limit` pause before its `resets_at` (D5 "When")
- [x] Tests (same file): count 0 for a fresh launch; 1, 2, 3 at one step; a different step restarts at 0; a `resolution` resume restarts at 0; an orphaned outcome inherits the step; `resume_ready` before, at and after `resets_at`
- [x] **Success:** tests pass and `supervise.py` is fully covered (`uv run pytest --cov=amoeba.runner.supervise`). Commit `feat: add the resume bound`

---

## Section 6: Ingest by the Outcome Map

### Task 6.1: Add the supervised outcome plan
**Owner**: Junior AI | **Dependencies**: 2.2, 4.1, 5.2 | **Effort**: 3

- [x] `runner/ingest/outcome.py`: add `plan_supervised(finished, run_id, count, limit) -> OutcomePlan` beside `plan_outcome`, built on `supervise.classify`; nothing calls it yet. Each class gives its D4 effect: `COMPLETED` resolves and completes the node; `QUESTION` blocks `SQ_CHECKPOINT` with `{run_id, reason, step, question}`; `BLOCKED` keeps the payloads D4 lists, with `agent_text` inside `failure` when sent; vanished, launch failed and resume failed are as today. Every text field passes through `cut_to_bound`
- [x] `TRANSIENT`: with `count` below `limit`, resolve the entry with its outcome document and do not block. At the bound, block `HUMAN` with `{reason: auto_resume_exhausted, step, count, checkpoint | failure}`
- [x] Tests in `tests/runner/ingest/`: one per D4 row's plan; `TRANSIENT` under and at the bound; a question longer than the bound is cut
- [x] **Success:** tests pass and the full suite is green. Commit `feat: add the supervised outcome plan`

### Task 6.2: Take routing and the CF outcome read off the tick
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

- [x] `runner/tick.py`: remove `GateStage.observe_outcomes`, `route_outcomes` and `watch_overruns`. `ProjectTick` stops taking `routing_table`. `runner/ingest/record.py`: stop marking `awaits_routing`; drop the `observation` argument and the hatch-check writes; `record_finished` no longer takes outcome observations. The routing, outcome and overrun modules stay on disk, unused, until Section 10
- [x] Tick tests, file by file (unit tests of the unused modules stay until their modules go):
  1. [x] Delete `tests/runner/gates/test_tick_outcome.py` and `tests/runner/gates/test_tick_routing.py`: they prove the CF outcome read, the hatches and gate-based routing, which D9 removes
  2. [x] `tests/runner/routing/test_tick_routing.py`: delete the rerun, held-step and recompute tests (D9 removes them). Delete `test_advance_dispatches_successor_next_tick`; Task 6.3 replaces it
  3. [x] `tests/runner/resolutions/test_tick_accept_routing.py`: delete the two `accept` tests (D6 removes `accept`). Move `test_a_failed_resume_escalates_once_and_offers_the_pause_decisions_again` to `test_tick_resume.py`, dropping only an assertion about a routing decision if it makes one
- [x] **Success:** full suite green. Commit `refactor: take routing and the CF outcome read off the tick`

### Task 6.3: Ingest by the outcome map
**Owner**: Junior AI | **Dependencies**: 6.1, 6.2 | **Effort**: 3

- [x] `runner/ingest/record.py`: `ingest` uses `plan_supervised` with `supervise.resume_count` and passes `complete_node_id` for `COMPLETED`; remove `plan_outcome`. Pass `auto_resume_limit` from settings through the tick to `record_finished`
- [x] Tick test replacing Task 6.2's deleted advance test: a completed run's node is `done` and its successor launches on the next tick
- [x] Crash test with `tests/runner/crash_harness.py`: kill between ingest's writes of a completed run; after restart the node is `done` and nothing is relaunched (Success Criteria, "A crash between ingest's writes")
- [x] **Success:** full suite green. Commit `feat: ingest finished runs by the outcome map`

Note (20261029): 6.2 and 6.3 landed in one commit, `feat: ingest finished runs by the outcome map`, because routing off the tick leaves completed steps never marked done until ingest completes them, so 6.2 alone could not keep the suite green. Beyond the listed deletions: removed tests/runner/gates/test_tick_merge.py, test_tick_disagreement.py, tests/runner/routing/test_overrun.py, the gate-read budget test in test_budget_coverage.py, the accept and rerun tests in test_decisions_e2e.py, and four awaiting-routing state tests (their behaviour is gone). `awaits_routing` is still set by the store on every issuer resolution; the Runner no longer reads it (dispatch/state.py and resolutions/classify.py dropped it, and DispatchState.AWAITING_ROUTING is gone). Task 13.x store-contract wording must say 'not read by the Runner', not 'not written'. A completed run's successor now dispatches in the same tick that ingests it.

---

## Section 7: Automatic Resume (D5)

### Task 7.1: Add the resume cause and reshape `ResumeRun`
**Owner**: Junior AI | **Dependencies**: 6.3 | **Effort**: 2

- [x] `resolutions/vocabulary.py`: `ResumeCause` (`transient`, `resolution`) and `PARAM_RESUME_CAUSE = "resume_cause"` (Task-level additions) (already added in Task 5.2; verify only)
- [x] `decide.py`: `ResumeRun` gains `cause` and `instructions`; `resolution` becomes optional, required when `cause` is `resolution` (raise `ValueError` in `__post_init__` otherwise). `decision` stays until Task 8.1b
- [x] The act stage writes `resume_cause` into every resume entry's parameters, and `--instructions` only when `instructions` is set. Today's resolution resumes write `resume_cause: resolution`
- [x] Tests: `tests/runner/resolutions/test_act.py` and `test_argv.py` for both causes, with and without instructions
- [x] **Success:** tests pass. Commit `feat: record why each resume was issued`

Note (20261029): a resolution resume reads the PM's instructions from the resolution slot in the act stage only (tests/runner/resolutions/test_instructions_flow.py requires act.py to be the one reader), so `ResumeRun.instructions` is set only for a transient resume. `ResumeRun` takes `cause` and `instructions` as keyword-only fields. test_argv.py is unchanged: the argv builder did not change.

### Task 7.2: List transient outcomes as resume candidates and widen the hold
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 3

- [x] `dispatch/state.py`: `DispatchState.AUTO_RESUME` (Task-level additions): the latest `sq_run` entry is resolved, its outcome classifies `TRANSIENT` (call `supervise.classify`, do not re-derive), and the node is not blocked
- [x] `dispatch/hold.py`: `_paused` becomes "recorded `paused`, `failed` or `orphaned`" (D3); rename it to match. Release is unchanged
- [x] `gates/candidates.py`: an `AUTO_RESUME` node is a candidate on the same terms as `RESUME` (its checkout held by no one or only by itself; pipeline and checkout from the resumed entry)
- [x] The pre-dispatch check treats an `AUTO_RESUME` candidate as a resume: it calls `gates/predispatch.py`'s `branch_rule` with `resume=True`, which already skips the clean-tree check. The branch rule itself is Task 9.1's
- [x] Tests in `tests/runner/dispatch/test_state.py`, `test_hold.py` and `tests/runner/gates/test_dispatch_reads.py`: each transient outcome gives `AUTO_RESUME`; a blocked node does not; a `failed` and an `orphaned` entry hold the checkout; an `AUTO_RESUME` candidate with a dirty tree on the target passes
- [x] **Success:** tests pass and the full suite is green. Commit `feat: list transient outcomes as resume candidates`

Note (20261029): `observed.py` now imports `InFlightRun` only under TYPE_CHECKING, to break the cycle decide -> dispatch.state -> supervise -> observed -> decide. A failed run now holds its checkout (D3), so test_a_failed_run_keeps_its_checkout_until_released replaced the old test that dispatched the second slice at once. `Candidate.resume` is true for `AUTO_RESUME` as well, so the existing `branch_rule(resume=True)` path covers it.

### Task 7.3: Issue `ResumeRun(cause=transient)` from Decide
**Owner**: Junior AI | **Dependencies**: 7.2 | **Effort**: 2

- [x] The dispatch planner issues `ResumeRun(node, run_id, continues, checkout, cause=transient, instructions=None)` for an `AUTO_RESUME` candidate when `supervise.resume_ready(document, view.now)` and its pre-dispatch check is `Ok`. A held node is not current, so it gets nothing (D5 "Who resumes")
- [x] Tests in `tests/runner/dispatch/test_planner.py`: an orphaned, a `provider_error` and a `stall` outcome each resume; a `usage_limit` pause is not resumed before `resets_at` and is at it; a held node is not resumed; a failed check blocks rather than resumes
- [x] **Success:** tests pass. Commit `feat: resume transient run failures automatically`

### Task 7.4: Confirm a resume against the state it left
**Owner**: Junior AI | **Dependencies**: 7.3 | **Effort**: 3

- [x] `resolutions/confirm.py`: `resume_progress` judges every resume entry, automatic or resolution, against the resumed-from entry's recorded `outcome` and `updated_at` (D5 "Confirmation"). A poll showing `timed_out` or a later `updated_at` confirms; the old state is `StillResuming` and is never ingested
- [x] `observe_resume.py`: after a resume the child failed, poll once more. `running` resolves the entry `not_applied`, observes the run again as in flight and counts nothing; any other state takes the `ResumeFailed` path (block `HUMAN`, `resume_failed`, no further automatic resume) (D5 "A run that is still live")
- [x] The act-time pre-poll (`resolutions/prepoll.py`) applies to `cause=transient` too: a run no longer in its classified state is not resumed and is observed again
- [x] Tests in `tests/runner/resolutions/test_confirm.py`, `test_observe_resume.py`, `test_prepoll.py`: a resume from `failed` and from `orphaned` confirmed by `updated_at`; `StillResuming` while the old state shows; the refused-live resume resolves `not_applied`; an exited child with the old state shown blocks `resume_failed`
- [x] **Success:** tests pass. Commit `feat: confirm a resume against the state it was resumed from`

Note (20261029): the refused-live case differs from the task text. After an exited child's resume the observer polls once more; if the run now shows running, the resume entry is NOT resolved `not_applied`. It stays open and becomes the in-flight entry of the live run (a running run confirms any resume), so the run's eventual outcome ingests onto it, and nothing is blocked. The cost: that entry counts as one transient resume toward the bound. Any other state after the second look takes the `ResumeFailed` path as before. The second look is taken only when the child has exited and the budget allows a call. `resume_progress` now takes a `ResumedFrom` (outcome, updated_at, paused_at) read by `resumed_from_entry`; `resumed_from_pauses` became `resumed_from_states`; the pre-poll launches only on a positive match of the old state (`is_at`).

### Task 7.5: Prove automatic resume at tick level
**Owner**: Junior AI | **Dependencies**: 7.4 | **Effort**: 3

- [x] Add stub `sq` scripts to `tests/sq_stub_scripts.py` for: `failed`/`provider_error` then `completed`; `orphaned` at one step N times; transient at three different steps; `usage_limit` with `resets_at`
- [x] Tick tests (new `tests/runner/test_tick_auto_resume.py`): two transient failures then completion gives two `resume_cause: transient` entries, then `done`; four failures at one step block the fourth `auto_resume_exhausted` with step and count; three steps once each are all resumed; `usage_limit` waits for `resets_at` with an injected clock; releasing a hold resumes
- [x] Crash test with `tests/runner/crash_resume.py`: kill after a transient resume entry is written; after restart the count is unchanged and the resume is confirmed, not reissued
- [x] **Success:** tests pass and the full suite is green. Commit `test: prove automatic resume and its bound`

Note (20261029): the outcome documents are built inline in tests/runner/test_tick_auto_resume.py (each with a later updated_at, as a real run has) instead of as new scripts in tests/sq_stub_scripts.py, which only holds captured review shapes. The crash test kills at BEFORE_RESUME_LAUNCH: the journaled transient resume is never reissued or launched, ends resume_failed after the grace period, and the slice blocks; a confirmed resume after a kill is covered by the existing 127 crash tests, which use the same observer.

---

## Section 8: Resolutions and Intents (D6, D7)

### Task 8.1: Cut the resolution vocabulary and judgement to `resume` and `stop`
**Owner**: Junior AI | **Dependencies**: 7.4 | **Effort**: 2

- [x] `resolutions/vocabulary.py`: `ResolutionDecision` `{RESUME, STOP}`; `Situation` `{RUN_TO_RESUME, NO_RUN, UNRESOLVABLE}`; `ResolutionRejection` `{UNKNOWN_DECISION, DECISION_REQUIRED, INSTRUCTIONS_NOT_APPLICABLE, UNRESOLVABLE}`; `Continuation` `{RESUME}`; `ALLOWED` rewritten
- [x] `classify.py` and `judge.py` per D6 and the vocabulary
- [x] Tests for `vocabulary`, `classify` and `judge` in `tests/runner/resolutions/`: `retry`, `accept`, `handled` and `rerun` are each rejected `unknown_decision`; `resume` with instructions and no run is rejected `instructions_not_applicable`
- [x] **Success:** those tests pass. The planner, act, argv and prepoll tests are red until Task 8.1b, so this task makes no commit; Task 8.1b commits both

### Task 8.1b: Cut the resolution planner, act, argv and prepoll to `resume` and `stop`
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 3

- [x] Remove `ResumeRun.decision` (Task 7.1 kept it) and the `ObserveRun` action
- [x] `planner.py`, `act.py`, `argv.py`, `prepoll.py` per D6: `resume` with a run Squadron still has issues `ResumeRun(cause=resolution, instructions)`; `resume` with no run resolves the block and the node launches afresh when next current; instructions there are rejected `instructions_not_applicable`; `stop` is 127's D3. The pre-dispatch check runs before either. The missing-run and exit-2 rules of 127 stand. `--decision` is never passed
- [x] `docs/inbox-contract.md`: the resolution vocabulary, and one line on the intent `resume` versus resolution `resume` name clash
- [x] Rewrite the remaining resolution tests (`tests/runner/resolutions/`) to the new vocabulary: `resume` with instructions passes them verbatim and resets the D5 count; `resume` with no run relaunches; `stop` keeps the block with reason `stopped`. Delete tests whose only subject was a removed decision
- [x] **Success:** full suite green. Commit Tasks 8.1 and 8.1b together as `feat: reduce resolutions to resume and stop`

### Task 8.2: Remove `until` from intents
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] `intent/vocabulary.py`: `IntentBody` drops `until`; a body carrying it is rejected `malformed_body`; `UNTIL_NOT_APPLICABLE` goes. `intent/apply.py` writes `drive_until_step` as `NULL`; `DesiredStateIndex` ignores it (D7)
- [x] `docs/inbox-contract.md`: the intent body
- [x] Tests in `tests/runner/intent/`: an intent with `until` is rejected `malformed_body`; `drive`, `exclude`, `pause`, `resume`, `clear` unchanged
- [x] **Success:** tests pass. Commit `feat: drop until from the intent body`

Note (20261029): 8.1/8.1b are one commit (`feat: reduce resolutions to resume and stop`) and 8.2 another (`feat: drop until from the intent body`), the 8.2 commit made first by path. Beyond the task text: (1) `ObserveRun` and `DispatchState.REOBSERVE` are gone; a resume skipped because the run moved on journals an entry with no `continuation` key, which the observer polls and ingests like any entry. `Continuation` is `{RESUME}` and marks resumes. (2) `WriteSlicePointer.resolution` is gone (no `rerun` to carry). (3) A bare resolution is now always `decision_required`, so the two CLI end-to-end tests submit `--decision resume`. (4) `resume` on a never-started launch takes the existing REISSUE path (same run id), which is a launch afresh. (5) `routing/reduce.py` and `gates/accepted.py` keep local `accept` constants until Task 10 deletes them. (6) The sq stub accepts a plain `--resume` (Squadron's retry) and `--decision` only if given. (7) `run_to_resume` and `RESULT_OUTCOME` live in supervise.py beside the other result keys.

---

## Section 9: The Slice Switch (D1, D2, D3, D11)

### Task 9.1: Cut the pre-dispatch check to git
**Owner**: Junior AI | **Dependencies**: 7.2 | **Effort**: 2

- [x] `gates/dispatch_reads.py`, `gates/predispatch.py`, `gates/stage.py`: stop reading CF's gate; remove the entry-gate rows and the `pending_decision` block. The target read (`read_target`) stays. `dispatch/state.py` loses its pending-decision state
- [x] `gates/predispatch.py`: one allowed-branch rule for every pipeline (D3). `allowed_branches` and `_is_allowed` key on `resume`, not on `PIPELINE_P6`: a fresh launch or reissue may start only on the target; a resume on the target or the slice's own branch. The clean-tree rule is unchanged (checked only when not resuming)
- [x] Tests in `tests/runner/gates/test_predispatch.py`, `test_dispatch_reads.py`, `test_tick_predispatch.py`: no `cf status` call before a launch; a fresh launch of any pipeline on the slice branch blocks `checkout_branch`; a resume on the slice branch with a dirty tree passes; a fresh launch with a dirty tree blocks `checkout_dirty`; delete entry-gate and pending-decision cases
- [x] **Success:** full suite green. Commit `refactor: check only git before dispatch`

Note (20261029): `dispatch/state.py` had no CF pending-decision state, so nothing was removed there (`FaultKind.PENDING_DECISION` and `CF_GATE_BLOCKS` stay until Task 10.5). The dispatch check now reads only `git status` and the target, so the cut-off test counts two reads. `Candidate.needs_gate`, `entry_gate`, `NoResult`, `Disagreement`, the gate evidence keys, `GateStage`'s accepted-outcome and disagreement code are gone; `gates/accepted.py` is unused until Task 10.2b. `branch_rule(status, target, slice_index, resume=...)` no longer takes a pipeline.

### Task 9.2: Launch without the pointer write
**Owner**: Junior AI | **Dependencies**: 9.1 | **Effort**: 3

- [x] `dispatch/state.py` loses `NEEDS_POINTER`; `dispatch/planner.py` issues `LaunchRun` on the first tick; `WriteSlicePointer` is removed from `decide.py`'s `Action`; `act.py` and `ActStage` stop handling pointers; `tick.py` drops `PointerStage`, `watch_pointers` and `_pointer_confirmed`. The pointer modules stay on disk, unused, until Task 10.3
- [x] The CF commands-defined-once test (`tests/runner/test_cf_commands_defined_once.py`) drops the write commands; no code path issues `cf set` (grep test)
- [x] Rewrite `tests/runner/dispatch/test_tick_dispatch.py`, `test_tick_checkout.py`, `test_tick_concurrency.py`: one `sq_run` entry and no `cf_write` entry per launch; delete `test_tick_pointer_moved.py`
- [x] **Success:** full suite green. Commit `feat: launch without moving CF's pointers`

Note (20261029): the pointer modules and their tests were deleted here rather than left dead, because they could not compile once `NEEDS_POINTER`, `pointer_confirmed` and `WriteSlicePointer` went. `DispatchState.POINTED` and `NEEDS_POINTER` became one state, `READY` (nothing in flight, nothing to resume): a ready step launches only in a free checkout, so a checkout is held from its launch, not from a claim. `checkout_holders(entries, done)` lost its facts argument. `routing/overrun.py` and `tests/test_observer_cf_readback_checkout.py` went too. `plan_read.CF_SET_COMMAND`/`set_slice_argv` are gone; a test asserts nothing writes CF. DispatchRig names slice index 125 as CF does (`run-dispatch-and-outcome-ingestion`), since the pointer write used to rename it and reviews are attributed by that name.

### Task 9.3: Add the slice-level ready rule and initiative completion
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] `lifecycle/tree.py`: `ready_slices()` per D1's ready rule. `lifecycle/predecessors.py`: make `_previous_eligible_slice` public as the slice predecessor (the one place 180 extends). `lifecycle/completion.py`: an initiative is `done` when every eligible slice under it is `done`; a CF-complete slice with no unresolved entry and not blocked is `done` (D1). The step rules in these modules stay until Task 10.4 deletes them
- [x] Tests in `tests/runner/lifecycle/test_ready_steps.py` (rename to `test_ready_slices.py`), `test_predecessors.py`, `test_completion.py`: each ready condition; predecessor by index within an initiative; deferred and deprecated skipped; initiative completion
- [x] **Success:** tests pass. Commit `feat: add the slice-level ready rule`

Note (20261029): the slice predecessor is new public code in `predecessors.py` (`slice_predecessor`, `slice_predecessor_done`, `linked_slices_by_index`) beside the step rules, which stay until Task 10.4; the slice level does not require step children, so the old private `_previous_eligible_slice` is untouched. The new slice-level tests are in a new `tests/runner/lifecycle/test_ready_slices.py` (the old `test_ready_steps.py` still covers `ready_steps` until 10.4) and in `test_completion.py`. A deferred or deprecated slice is skipped by never having a node (Task 9.6 stops reconcile creating one); a slice node that already exists and later turns deferred in CF is not retired by this slice, the same as before. Reconcile now also marks a CF-complete slice done and an initiative done when every linked slice under it is done (an initiative with no slices is not done).

### Task 9.4: Take human steps and the merge observation off the tick
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 2

- [x] `factory.py` and `tick.py`: remove `HumanStepPlanner` and the merge observation (`GateStage.observe_merges`); `ProjectView` loses `merge_policy` and `merge_observations`. The modules stay on disk, unused, until Section 10
- [x] Delete `tests/runner/test_tick_human_steps.py` and `tests/runner/gates/test_tick_merge.py`; rewrite any other tick test that asserted a human-step block or a merge completion
- [x] **Success:** full suite green. Commit `refactor: stop planning human steps and observing merges`

Note (20261030): beyond the task text, a launch no longer carries `merge=false`, `merge_policy` or `target` (D2: whether a pipeline merges is the pipeline's business), so `dispatch_params(step, index)` returns only the slice and `PARAM_MERGE`, `MERGE_DISABLED` and `PARAM_TARGET` are gone; `PARAM_MERGE_POLICY` stays only for the unused `gates/merge.py` (Task 10.2b). `human_steps.py` stays on disk with its merge branch removed (it could not compile without `merge_observations`); `BlockHumanStep` and `block_human_step` stay until 10.4. `tests/runner/gates/test_tick_merge.py` was already deleted in Task 6.2.

### Task 9.5: Dispatch slice nodes with the configured pipeline
**Owner**: Junior AI | **Dependencies**: 2.1, 8.1b, 8.2, 9.3, 9.4 | **Effort**: 2

- [x] `ProjectView.current_steps` becomes `current_slices` from `ready_slices()`; `ready_unbusy` follows; governance (`intent/governance.py`) resolves on slice nodes; the `decide` guard names slices. Reconcile still creates step nodes until Task 9.6; they are never current
- [x] `dispatch/planner.py` launches `LaunchRun(slice_node, settings.pipeline, {slice: <index>, **settings.params}, checkout)`; the per-checkout order is `(initiative index, slice index)`; reissue (125, D9) is kept. `dispatch/params.py` reads the project settings, not the step. A slice whose project has no `pipeline` launches nothing (its fault arrives in Task 9.7)
- [x] New tick tests: `pipeline: p456` gives `sq run p456 <index> --run-id <id>` with each param as `-p k=v`; the next slice waits for its predecessor `done`
- [x] **Success:** the new tests pass. Tick tests that drove step nodes are red until Task 9.5b, so this task makes no commit; Task 9.5b commits both

### Task 9.5b: Migrate the step-node tick tests to slice nodes
**Owner**: Junior AI | **Dependencies**: 9.5 | **Effort**: 3

- [x] Rewrite the tick tests that drove step nodes against slice nodes, one directory at a time, re-running that directory after each: `tests/runner/test_tick*.py`, then `tests/runner/dispatch/`, then `tests/runner/resolutions/test_tick_*.py`. A test whose only subject was a step is deleted
- [x] **Success:** full suite green; 122's crash tests and 125's ingestion tests pass against the slice node. Commit Tasks 9.5 and 9.5b together as `feat: drive slices with the project's configured pipeline`

Note (20261030): 9.5 and 9.5b are one commit, `feat: drive slices with the project's configured pipeline`. The dispatch facts record is now `SliceDispatchFacts` (no `step`; sort key is (initiative index, slice index)); `ProjectView` has `current_slices` and a `settings` field; the planner launches `settings.pipeline` with `launch_params(settings, index)` and nothing when the project has no pipeline; `Candidate` lost `step` and `pipeline`. Governance resolves on the slice itself (its own row, its initiative's, the project's). Ingest attributes reviews to the entry's node, which must be a slice. Test rigs: `ready_slice` replaces `ready_step`/`ready_slice_step`; `DispatchRig.step` and `slice_and_step` return the slice itself and configure the project with pipeline `p456`; `successor_slice` replaces `tasks_step`; the crash harness configures its project with `p456` through `CRASH_PROJECT`. Deleted with their subjects: `merge_support.py`, `test_human_steps.py`, `test_tick_human_steps.py`, the arch-file human-step intent test, and step-based governance/params cases.

### Task 9.6: Stop creating step nodes
**Owner**: Junior AI | **Dependencies**: 9.5b | **Effort**: 2

- [x] `lifecycle/reconcile.py creates initiative and slice nodes only. Step nodes in an older store are never candidates (LLD "State Management")
- [x] Tests in `tests/runner/lifecycle/test_reconcile_create.py` and `test_reconcile_update.py`: a slice gets no step children; a store holding step nodes from before still ticks and never launches them
- [x] **Success:** full suite green. Commit `refactor: stop creating step nodes`

Note (20261030): a deferred or deprecated slice now gets no node at all (it used to get a node with no steps), so it is never driven and never a predecessor; a node that already exists is not retired when CF later defers it. Step-completion tests in `test_completion.py` and the step cases in `test_status_block.py`/`test_reconcile_crash.py` were deleted or rewritten with their subject; the step rules in `completion.py`, `tree.py` and `predecessors.py` have nothing left to act on and are deleted in Task 10.4. `test_tenant.py` fails writes 1-3 now (three nodes are written, not nine).

### Task 9.7: Raise `pipeline_unconfigured`
**Owner**: Junior AI | **Dependencies**: 9.5b | **Effort**: 1

- [x] `faults.py`: `FaultKind.PIPELINE_UNCONFIGURED`, project-scoped, raised once per tick when a current slice has no configured pipeline; the existing close path closes it (D11)
- [x] Tick tests: an unconfigured project with a driven slice launches nothing and raises one `pipeline_unconfigured`; it closes once the project is configured or the slice is no longer driven; a pipeline the stub `sq` reports not found (exit 1, `Error: Pipeline '<name>' not found.`) blocks only that slice with the stderr while other projects tick
- [x] **Success:** full suite green. Commit `feat: raise an escalation for a project with no pipeline`

Note (20261030): the tick raises `pipeline_unconfigured` after the view is built when `current_slices` is non-empty and the project's settings name no pipeline; the existing close path closes it. The base tick rig and the tenant-building tests now configure their projects with pipeline `p456`, since an unconfigured project raises the escalation. The not-found case is covered through the fake launch: exit 1 with Squadron's stderr blocks only that slice (122's launch-failure path), and another checkout's slice still launches. The five retired FaultKind members stay until Task 10.5.

---

## Section 10: Deletions (D9, D11)

### Task 10.1: Delete routing
**Owner**: Junior AI | **Dependencies**: 9.6, 9.7 | **Effort**: 2

- [x] Delete `runner/routing/` (with `tables/default.yaml`), `inspection/routing.py` and the `routing-decisions` listing in `inspection/__init__.py`; `--routing-table` and `routing_table_path`; the table load in `factory.py` and `cli/lifecycle.py`; `tests/runner/routing/`, `tests/routing_helpers.py` and the package-data entry (Task-level additions). Note: `tests/routing_helpers.py` was kept because surviving store tests (`tests/store/test_routing_*.py`, `test_messages`, `test_desired_state`, etc.) import it; it depends only on `amoeba.store`. The Rule 10 import-boundary exemption for `inspection` was also removed.
- [x] **Success:** full suite green; `amoeba start --routing-table x` fails as an unknown flag. Commit `refactor: delete the routing engine`

### Task 10.2: Move the surviving gate modules to `dispatch/`
**Owner**: Junior AI | **Dependencies**: 10.1 | **Effort**: 2

- [x] Move the survivors to `runner/dispatch/` per Task-level additions and update imports. The dead gate modules stay where they are, unused, until Task 10.2b. Note (20261030): the survivors landed as `dispatch/checkout_check.py`, `candidates.py`, `checkout_reads.py` (plus `read_config`, `read_target`, `ReadFailure`, `DEFAULT_TARGET_BRANCH`, rewritten compactly from `cf_reads`) and `check_stage.py` (class `CheckStage`, takes only `context`, `cf_run`, `call_timeout_seconds`; the outcome half was dropped)
- [x] Move the survivors' tests to `tests/runner/dispatch/`, and `tests/runner/gates/purity.py` to `tests/runner/purity.py`; fix its importers (`test_predispatch.py`, `test_supervise.py`, and `test_hatches.py` until 10.2b deletes it). Note (20261030): tests moved to `tests/runner/dispatch/` as `test_checkout_check`, `test_checkout_reads`, `test_check_stage`, and `test_checkout_target` (split from `test_cf_reads`); the purity helper is now `tests/runner/purity.py`
- [x] **Success:** full suite green; only moves and import changes in the diff. Commit `refactor: move the surviving gate modules to dispatch`

### Task 10.2b: Delete the CF gate, hatch and merge modules
**Owner**: Junior AI | **Dependencies**: 10.2 | **Effort**: 2

- [x] Delete `gates/cf_status.py`, `hatches.py`, `checks.py`, `accepted.py`, `outcome.py`, `outcome_record.py`, `merge.py`, `merge_observation.py`, and `read_gate` from `cf_reads.py`; delete `gates/` and the gate tests whose modules went. Note (20261030): `cf_reads.py` was deleted wholesale (its surviving parts moved to `checkout_reads.py` in 10.2), and `tests/load/test_gate_reads_load.py` was deleted
- [x] Remove the gate modes from `tests/cf_stub_gates.py` (keep `config get`) and the gate helpers from `tests/runner/gate_rig.py`. Note (20261030): `gate_rig.py` now holds only `rig_checkout`, `git_checkout` and `config_knobs`; `cf_stub_gates.py` keeps only `config get` and `STATE_ENV`; the `clear_gates` calls were removed from three tick tests
- [x] Confirm `tests/runner/test_supervise.py` still runs its purity test. Note (20261030): confirmed running
- [x] **Success:** full suite green. Commit `refactor: delete CF gate reads, hatches and merge observation`

### Task 10.3: Delete the pointer modules
**Owner**: Junior AI | **Dependencies**: 10.2b | **Effort**: 1

- [x] (Modules and their tests deleted in Task 9.2; still to do: `tests/test_cf_stub_pointer.py`, the stub's pointer-write code, and `pointer_support.py`'s leftover names are kept because `CfWorld` and the budget helpers live there.) Delete `dispatch/pointer.py`, `pointer_apply.py`, `pointer_watch.py`, `observe_pointer.py`, their tests, `tests/runner/dispatch/pointer_support.py`, `tests/test_cf_stub_pointer.py` and the stub's pointer-write code
- [x] **Success:** full suite green (3677 passed), ruff and pyright clean. Commit `refactor: delete the pointer modules`

Note (20261030): `tests/runner/dispatch/pointer_support.py` was renamed `cf_world.py` rather than deleted; it holds `CfWorld` and the budget helpers and no pointer logic. The stub's `set`/`get` pointer commands, its state file, `STATE_ENV` and `write_cf_state` are gone. The unused status fixtures (`tests/fixtures/cf/status/` and `cf_get_worktree.json`) are deleted.

### Task 10.4: Delete the step map, human steps and merge policy
**Owner**: Junior AI | **Dependencies**: 10.3 | **Effort**: 2

- [x] Delete `lifecycle/steps.py`, `human_steps.py`, the step rules in `completion.py`, `predecessors.py` and `tree.py`, and `BlockHumanStep`
- [x] `project_config.py`: remove `MergePolicy`, `merge_policy`, `PROJECT_DEFAULTS.merge_policy`; an entry with any key beside `pipeline` and `params` fails load (D2). Remove `PARAM_MERGE_POLICY` and `PARAM_TARGET`
- [x] Delete `tests/runner/lifecycle/test_steps.py`, `test_human_steps.py`; update `test_project_config.py` (a `merge_policy` key is refused)
- [x] **Success:** full suite green (3677 passed), ruff and pyright clean. Commit `refactor: delete the step map, human steps and merge policy`

Note (20261030): `PARAM_TARGET` was already gone before this task. `lifecycle/predecessors.py` keeps only the slice-level rules (Task 9.3). `tree.py` lost `step_of` and `ready_steps`, and `is_linked` now needs each node's own CF index. `read_checks.py` now holds `PlanObservation`, moved from its old home. `TreeBuilder` lost its step helpers and gained `phase_node`. The tests `test_steps`, `test_ready_steps` and `test_predecessors` are deleted. A `merge_policy` key now fails config load through `extra=forbid`.

### Task 10.5: Delete the unused fault kinds and pin the boundaries
**Owner**: Junior AI | **Dependencies**: 10.4 | **Effort**: 1

- [x] `faults.py`: remove `pointer_write_failed`, `pointer_moved`, `run_overrun`, `cf_gate_blocks`, `pending_decision` (D11)
- [x] `tests/test_import_boundaries.py`: a grep test that no module under `src/amoeba/runner/` imports `routing`, `gates`, or `dispatch.pointer*`, and that those paths do not exist. The create-node guard test still passes
- [x] Confirm `ProjectView`, `decide.Action`, `tick.py` and `factory.py` hold no field, argument or comment naming a removed concept (`grep -rnw "pointer\|routing\|merge_policy\|gate\|gates" src/amoeba/runner`; each remaining hit is justified or removed)
- [x] **Success:** full suite green (3677 passed), ruff and pyright clean. Commit `refactor: delete unused fault kinds and pin the runner's boundaries`

Note (20261030): five fault kinds are removed (`pointer_write_failed`, `pointer_moved`, `run_overrun`, `cf_gate_blocks`, `pending_decision`), and the duplicate `PAYLOAD_STEP` goes with them. `tests/test_import_boundaries.py` gained Rule 12: the removed paths do not exist and nothing imports them. The grep sweep leaves one justified hit, a docstring in `dispatch/checkout_reads.py` saying CF's gate is not read. Stale comments are fixed in `project_view`, `factory`, `supervise`, `reissue`, `record`, `references` and `cadence`.

---

## Section 11: The Blocked List (D8)

### Task 11.1: List blocked nodes across every project
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] `inspection/__init__.py`, `inspection/core.py`: `blocked` has both row functions (Task-level additions). Columns `project_id`, `node_id`, `title`, `blocked_on`, `reason`, `context`, `blocked_state_id`; `reason` is the payload's `reason` or `fault_kind`, empty with neither. `--json` adds the full payload. Every store opens read-only. Note (20261030): Listing now accepts rows and supervisor_rows together (project-scoped with project_optional=True; CLI --project is optional for it); read_listing uses supervisor_rows when no project is named. Rows for both modes now share one shape, which adds project_id, reason and payload fields to the per-project rows (additive). The payload comes from the escalation message keyed by blocked_state_id; a non-escalating block (judge) has an empty payload.
- [x] The network API's per-project blocked surface is unchanged. Note (20261030): the server route is unchanged and still requires a project.
- [x] Tests in `tests/inspection/` and `tests/test_cli_inspect.py`: two projects each with a blocked slice, listed with no `--project`; `--project` narrows; an `agent_question` block's `--json` row carries the question; a block with neither key has empty `reason`. Note (20261030): tests are in `tests/test_cli_inspect.py` and `tests/inspection/test_listing.py`.
- [x] **Success:** tests pass. Commit `feat: list blocked slices across every project`. Note (20261030): commit made; full suite green, 3682 passed.

---

## Section 12: End to End

### Task 12.1: Rewrite the end-to-end test against a stub `p456`
**Owner**: Junior AI | **Dependencies**: 10.5, 11.1 | **Effort**: 3

- [x] Rewrite `tests/runner/test_end_to_end.py` to drive one slice through a stub `p456`, with one run-state script per scenario in `tests/sq_stub_scripts.py` (LLD "Development Approach"): completion then the next slice launching; `-k agent_question` (block with the question, then a `resume` resolution with instructions resumes the run with them verbatim and the slice proceeds). The transient scenarios are Task 7.5's `tests/runner/test_tick_auto_resume.py`; Task 13.3 points walkthrough step 5 there. Note (20261030): tests/runner/test_end_to_end.py now runs the production tenant and planners (project config naming p456, a real git checkout, stub cf and sq on PATH); the existing launch/fault tests moved onto that path; new tests cover completion then the next slice launching, and agent_question (blocks with the question, then a resume resolution with instructions resumes the run with them verbatim, read from the stub's resume argv log). New script builder agent_question_run in tests/sq_stub_scripts.py. FOUND DEFECT, fixed in the same commit: the question block was SQ_CHECKPOINT, and the store keeps a block's payload only on a HUMAN block's escalation row (ESCALATING_KINDS), so the question and reason were silently dropped; the question block is now BlockedKind.HUMAN (ingest/outcome.py _question_block; test_plan_supervised updated). The LLD D4 table and the walkthrough/docs say SQ_CHECKPOINT and must be updated in 13.1/13.3 (node status is blocked_on_human, blocked_on shows human). OPEN: the other paused outcomes (BLOCKED row, reason paused) still build a payload on an SQ_CHECKPOINT block, which the store also drops; their checkpoint is in the entry's result (docs/process-contract.md says so). Full suite 3684 passed; ruff and pyright clean.
- [x] **Success:** tests pass and the full suite is green. Commit `test: drive a slice end to end through a stub p456`

---

## Section 13: Docs and Final Validation

### Task 13.1: Update the contract docs and CHANGELOG
**Owner**: Junior AI | **Dependencies**: 12.1 | **Effort**: 2

- [x] `docs/process-contract.md`: the config format, `auto_resume_limit`, the outcome map and auto-resume
- [x] `docs/store-contract.md`: the routing-decision, table-version and attempt-count tables, `awaits_routing` and `drive_until_step` marked unwritten by the Runner (D9)
- [x] `docs/context-forge-contract.md`: the Runner writes no pointers and reads no gates; it reads `git.integration_branch`
- [x] `docs/substrate-guide.md`: the 120 row
- [x] Confirm `docs/inbox-contract.md` was updated in Tasks 8.1b and 8.2
- [x] `CHANGELOG.md` under `[Unreleased]`: the supervisor (Added, Changed, Removed), naming the removed flags and resolution decisions
- [x] **Success:** every doc named in the LLD's Migration Plan is updated. Commit `docs: describe the pipeline supervisor in the contracts`

### Task 13.2: Final validation
**Owner**: Junior AI | **Dependencies**: 13.1 | **Effort**: 2

- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright`. All clean. Record the pass count under this task
- [x] Check every LLD Success Criterion (Functional, Technical, Integration) against a named test or this task's run; write the test name beside each under this task. Any criterion with no proof gets a test now
- [x] Record the "after" line count of `src/amoeba/runner/` beside Task 1.1's "before"
- [x] **Success:** all green, every criterion mapped. If a test was added, commit `test: close the supervisor's success criteria`; otherwise no commit (the notes are committed with Task 13.3)

Note (20261030): pass count 3685 passed; ruff check, ruff format --check and pyright clean. Runner line count: 12057 before (Task 1.1), 7827 after. Commit `test: close the supervisor's success criteria` (77323db) added a tick-level node-scoped hold/release auto-resume test and a "no cf set" assertion (cf stub call log) to the end-to-end normal path.

Criteria map (paths under `tests/`; PARTIAL marks a criterion not fully proven):
**One launch, no `cf set`, done:** `runner/dispatch/test_tick_dispatch.py::test_a_driven_slice_launches_the_configured_pipeline_on_the_first_tick`; `runner/test_end_to_end.py::test_the_normal_path_records_run_id_outcome_and_status` (also asserts no `cf set`).
**Params and bad config:** `test_tick_dispatch.py::test_the_projects_params_become_dash_p_arguments`; `runner/test_project_config.py::test_each_pipeline_or_params_failure_is_named` and `test_two_params_problems_in_one_file_are_both_named`; `runner/test_factory.py::test_an_invalid_project_config_fails_start_before_anything_is_created`.
**Nonexistent pipeline blocks with not-found stderr:** `test_tick_dispatch.py::test_a_pipeline_squadron_does_not_have_blocks_only_that_slice`. PARTIAL: uses a fake Popen and a second worktree of the same project; no two-project test.
**Unconfigured project:** `test_tick_dispatch.py::test_a_driven_slice_in_an_unconfigured_project_launches_nothing_and_escalates`, `test_the_escalation_closes_once_the_project_is_configured`, `test_the_escalation_closes_once_the_slice_is_no_longer_driven` (pause only).
**Index order:** `test_tick_dispatch.py::test_the_next_slice_waits_for_its_predecessor_to_be_done`; `runner/test_end_to_end.py::test_a_completed_slice_is_followed_by_the_next_slice_launching`.
**Dirty tree, off target, own-branch resume:** `runner/dispatch/test_tick_predispatch.py` (`test_a_dirty_tree_blocks_a_pointed_step_with_the_paths_and_launches_nothing`, `test_a_checkout_on_the_wrong_branch_blocks_a_planning_launch`, `test_a_resume_on_a_dirty_tree_resumes_and_names_the_dirty_paths`); `runner/dispatch/test_checkout_check.py::test_a_resume_is_allowed_on_this_slices_own_branch`; `runner/dispatch/test_checkout_reads.py::test_a_resume_on_the_slice_branch_with_a_dirty_tree_passes` (real git).
**Each D4 row:** `runner/test_supervise.py::test_each_observation_has_its_class`; `runner/ingest/test_plan_supervised.py`; `runner/ingest/test_record.py`; `runner/ingest/test_tick_ingest.py`. **Atomic completion:** `contract/test_runner_report_completion.py` (rollback on injected failure) and `runner/test_crash_recovery.py::test_kill_before_the_report_of_a_completed_run_completes_the_node_once`. PARTIAL: the crash window between ingest's writes no longer exists (one transaction), so the proof is the contract rollback test, and the harness tests use a one-launch-per-node planner.
**Transient resume and bound:** `runner/test_tick_auto_resume.py` (`test_two_transient_failures_then_completion_resume_twice_then_finish`, `test_four_failures_at_one_step_block_the_fourth_as_exhausted`, `test_three_steps_once_each_are_all_resumed`); `runner/dispatch/test_planner.py::test_an_orphaned_provider_error_or_stall_outcome_is_resumed`; `runner/test_supervise.py::test_a_different_step_restarts_the_count`. Tick level exercises stall only at the default limit of 3.
**usage_limit `resets_at`:** `runner/test_tick_auto_resume.py::test_a_usage_limit_pause_waits_for_its_reset_time`; `runner/dispatch/test_planner.py` (same name, boundary).
**Hold/release:** `runner/test_tick_auto_resume.py::test_releasing_a_hold_resumes` (project-wide) and `test_a_hold_on_the_slice_itself_blocks_its_resume_until_released` (node-scoped).
**agent_question:** `runner/ingest/test_plan_supervised.py::test_an_agent_question_blocks_on_a_human_with_its_question` and `test_a_question_longer_than_the_bound_is_cut`; `runner/test_end_to_end.py::test_an_agent_question_blocks_with_the_question_then_resumes_with_instructions`.
**Resume/stop and rejected decisions:** end-to-end test above (instructions verbatim from the stub's resume argv); `runner/resolutions/test_argv.py::test_instructions_are_one_element_byte_for_byte`; `runner/resolutions/test_decisions_e2e.py::test_resume_with_no_run_to_resume_launches_again` and `test_stop_blocks_the_node_with_reason_stopped_and_issues_nothing`; `runner/resolutions/test_judge.py::test_each_check_rejects_with_its_code`. PARTIAL: the count reset after a resolution resume is proven only at the pure level (`runner/test_supervise.py::test_a_resolution_resume_restarts_the_count`), not at tick level.
**until rejected:** `runner/intent/test_interpret_targets.py::test_an_until_is_a_malformed_body_on_any_target`; `runner/intent/test_apply_pending.py::test_each_outcome_is_stored_with_its_reason`.
**Inspect blocked across projects:** `test_cli_inspect.py::test_blocked_without_a_project_lists_every_projects_blocks`, `test_blocked_with_a_project_narrows_to_it`, `test_an_agent_question_block_carries_the_question_in_its_json_row`.
**Import boundaries:** `test_import_boundaries.py::test_rule_12_the_removed_runner_paths_do_not_exist` and `test_rule_12_nothing_imports_a_removed_runner_module`.
**No `cf set`:** `runner/test_cf_commands_defined_once.py` (write words gone; `test_no_code_path_writes_to_cf`) plus the end-to-end cf-log assertion.
**supervise.py pure:** `runner/test_supervise.py::test_supervise_does_no_io`. No coverage tool is configured, so "fully covered" is by row/edge tests, not measured.
**140 integration:** the CLI blocked tests plus the end-to-end agent_question test.
**Docs updated:** commit `c099236`. Line counts: Task 1.1 and above.

### Task 13.3: Run the Verification Walkthrough
**Owner**: Junior AI | **Dependencies**: 13.2 | **Effort**: 3

- [ ] Run LLD "Verification Walkthrough" steps 1–8 as written: steps 5–7 against the stubs, steps 1–4 live against a real slice with `sq` (pre-authorized). Write each step's observed output under this task, and fix any step whose command or expectation differs from what the code does
- [x] Update the walkthrough in the LLD to what was run, with step 5 running `tests/runner/test_tick_auto_resume.py`, and remove its "Draft, to be refined after implementation" note
- [ ] **Success:** every step passes as recorded. Commit the LLD and this task's notes as `docs: record the verified walkthrough`, with the before and after line counts of `src/amoeba/runner/` in the message body (LLD "Integration Requirements")

Note (20261030): Observed so far (real CLI, throwaway AMOEBA_STORE_DIR and --cf-data-dir in the session scratchpad; real sq 0.24.9 and cf 0.19.23 installed):
- Step 1: `amoeba start --project-config projects.yaml` logged `project config loaded from …projects.yaml` and `sq probe passed`; no routing-table line. `amoeba status` running, `amoeba stop` stopped it.
- Step 2: with `params: {slice: "1"}` start refused: `projects.amoeba.params.slice: reserved, the Runner passes the slice`.
- Step 5: `pytest tests/runner/test_tick_auto_resume.py` 6 passed (two transient resumes then done; four failures block auto_resume_exhausted).
- Step 6: `pytest tests/runner/test_end_to_end.py -k agent_question` passed (block on a human with the question, resume with instructions verbatim, slice finishes). `amoeba inspect blocked --json` on a store with a HUMAN question block showed `reason: agent_question` and the payload with the question. The block's kind is human, not sq_checkpoint (see Task 12.1 note).
- Step 7: two throwaway projects each with a blocked slice: `amoeba inspect blocked` listed both with project_id and reason; `--project alpha --json` narrowed to one and carried the payload.
- Step 8: `amoeba start --routing-table x` -> `unrecognized arguments: --routing-table x`; `amoeba inspect routing-decisions` -> invalid listing choice.

BLOCKED: steps 3 and 4 need a live run of the real p456 pipeline on a real slice. The only registered Context Forge projects are the PM's real ones (~/.config/context-forge/projects.json); a live run would mutate a real repo and branch, and a scratch CF project would write to the real registry. Needs the PM to name the project and slice to drive (or approve a scratch project).
