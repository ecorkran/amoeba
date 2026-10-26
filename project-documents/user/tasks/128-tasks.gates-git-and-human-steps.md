---
docType: tasks
slice: gates-git-and-human-steps
project: amoeba
lld: user/slices/128-slice.gates-git-and-human-steps.md
dependencies:
- 107
- 122
- 123
- 124
- 125
- 126
- 127
projectState: Slices 120–127 are merged. The tick (`runner/tick.py`, 279 lines) runs
  intents, resolutions, Observe, record, the pointer stage, the view, routing, decide
  and act. `DispatchPlanner` launches every `POINTED` or `REISSUE` step it picks,
  and `ContinuationPlanner` every `RESUME`, with no check of the checkout. `dispatch_params`
  always passes `merge=false` to `P6`. `HumanStepPlanner` blocks every current human
  step. The Runner never runs `git`. `amoeba.runner.gates` does not exist.
dateCreated: 20261026
dateUpdated: 20261026
status: in_progress
turns: 51
promptTokens: 4746462
cachedTokens: 4581749
cacheWriteTokens: 164637
completionTokens: 44494
durationSeconds: 417.9
costUsd: 3.123913
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.1239130999999998
    completionTokens: 44494
revision_number: 2
---

## Context Summary

- Working on the **gates-git-and-human-steps** slice (128), the ninth slice of initiative 120 (Runner and Routing Engine). It adds the checks around dispatch so the Runner can work in a checkout the PM also uses: CF's gate and the two ungate hatches read when a run completes, the clean-tree, branch and entry-gate checks before a launch or resume, the gate-disagreement check record (issue #15), the per-project merge policy, and the merge observed in git.
- **Current state:** see `projectState`. CF's gate is read only by the start-up probe, and nothing reads the slice design's frontmatter.
- **Dependencies:** 107 (`record_check`, `CheckInput`, `check_standing`), 122 (`TickBudget`, faults, closure, settings flags), 123 (`STEP_MAP`, stem rule, slice-list parser, completion write, `HumanStepPlanner`), 124 (current-step guard), 125 (dispatch state, checkout, `dispatch_params`, ingestion), 126 (input vocabulary, table, `StartupFailedError` loading), 127 (`ResumeRun`, `ContinuationPlanner`, the identifiable accept). All merged. Context Forge and `git` by shape (LLD "Interfaces Required").
- **What this slice delivers:** `amoeba.runner.gates`, `runner/git_read.py`, `runner/project_config.py`; `BlockDispatch` and five `FaultKind` members; the `gate_state` and `check_standing` routing inputs and the table edit; `--project-config`; stub `cf` modes and captured fixtures; contract text and CHANGELOG.
- **Next planned slice:** 129 (first proof), which drives a real slice to a human merge on these checks.

**Branch:** all implementation happens on `128-slice.gates-git-and-human-steps`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/128-slice.gates-git-and-human-steps.md` at the named decision (D1–D11), "Architecture" or "Implementation Details". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/` or `docs/`. Keep every new or changed source file near 300 lines and each function near 50. Task 1.1 folds the interface changes in "Task-level additions" into the LLD, so after it the two agree; the rest of that list is task-local placement notes.

**Order and dependencies:** work tasks in file order. Each task's **Dependencies** lists only its real prerequisites. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off; only its dependents wait.

**Commit cadence:** each task ends in one commit. An implementation task with no commit step is committed together with the test task right after it. Run `uv run ruff format .` before each commit. Commit types: `feat:` new behavior, `refactor:` behavior-preserving change, `test:` test-only work, `docs:` contract text.

**Task-level additions to the LLD** (code facts the LLD does not state, checked against the code on 20261026; each resolves a placement, not a product decision):
- **CF command words are spelled once,** in `runner/lifecycle/plan_read.py` (`tests/runner/test_cf_commands_defined_once.py`). `CF_STATUS_COMMAND` already exists (the probe uses it). Task 4.2 adds the `--worktree` flag, a `config_get_command(key)` builder and the two key names `git.integration_branch` and `workflow.review_gate_effective_date` there, and adds `config`, `--worktree` and both key names to the test's `COMMAND_WORDS`. `status` and `get` are not added: other modules use them as result keys.
- **`cf` and `git` run in a checkout** the way the pointer write does (`runner/dispatch/pointer.py`): through 122's injected `CfRun`, bound with `partial(run, cwd=...)`, under `run_cf`'s timeout handling for `cf`.
- **Gates' own vocabulary.** `runner/gates/checks.py` (not in the LLD's component list) holds `RunnerCheck`, `check_id(entry_id, name)` (`chk-<entry id>-<name>`) and `runner_provenance(amoeba_version, source, source_path)`, so hatches and the disagreement record share one definition. The exit and entry gate of each step (`EXIT_GATE`, `ENTRY_GATE`) live in `runner/gates/cf_status.py` beside `GatePosition`, not in `lifecycle/steps.py`, so the lifecycle package never imports gates. `DEFAULT_TARGET_BRANCH` lives in `runner/gates/cf_reads.py` beside the target read.
- **Key names.** `RESULT_OUTCOME_OBSERVATION` and `RESULT_CHECK_IDS` go in `runner/ingest/record.py` beside `RESULT_VERDICT_IDS`. `PARAM_MERGE_POLICY`, `PARAM_TARGET` and `PARAM_DISPATCH_CHECK` go in `runner/dispatch/params.py` (`runner/launch.py` is at 298 lines). The standing order `STANDING_WORST_FIRST` goes in `routing/inputs.py` beside `VERDICT_WORST_FIRST`.
- **The slice's own branch** is read with `parse_slice_stem` from `amoeba.upstream.context_forge`. A branch name containing `/` is never the slice's own branch, because `parse_slice_stem` reads only the last path part and Squadron names slice branches `{index}-slice.{name}` with no prefix.
- **Candidates come from the dispatch facts.** The view's dispatch facts already hold each current step's `DispatchState`, resolved checkout and the checkout holders. So `launch_candidates(current, facts, holders)` takes those, instead of the LLD's `(tree, desired, entries, held)`, and recomputes nothing. A candidate is a `POINTED` step; a `REISSUE` step in a checkout no one holds; or a `RESUME` step whose checkout is held by no one or only by itself. Its pipeline is `pipeline_for(step)` for `POINTED`, and the `pipeline` parameter of `reissue_of` or `continues` otherwise. Reads use that entry's checkout for a reissue or resume, and the resolved `Checkout` otherwise; `--worktree` takes the resolved `Checkout.worktree_id`.
- **Tick placement.** `tick.py` cannot take this slice's code. The gate stages go in `runner/gates/stage.py` as `GateStage`, called from `tick.py` with a few lines each: the outcome observation right after `observer.observe` and before `_record_finished`; the merge observation after the pointer stage and before the view; the pre-dispatch reads and disagreement records right after the view is built, the view then extended with `dataclasses.replace`. `GateStage` is built in `ProjectTick.__init__` like `ActStage`.
- **The view carries the policy.** `ProjectView` gains `merge_policy: MergePolicy`, defaulting to `PROJECT_DEFAULTS`'s value, so planners stay pure. `ProjectTick` passes the policy the loaded `ProjectConfig` gives its project.
- **Evidence on actions.** `LaunchRun` and `ResumeRun` gain `journal_extra: Mapping[str, object]` (empty by default). The act stage writes its keys into the entry's parameters. A `P6` launch's extras are `merge_policy`, `target` and `dispatch_check`; any other launch or resume carries `dispatch_check`. A reissue copies `merge_policy` and `target` from its old entry when present, and adds this tick's `dispatch_check`. `BlockHumanStep` gains `payload_extra: Mapping[str, object]` (empty by default), merged into its block payload, for `unobservable`.
- **`BlockDispatch` is applied with 125's `block_once`,** so an already blocked step is not blocked twice.
- **The completion write is shared.** `lifecycle/completion.py`'s `_complete` becomes public `complete_step(store, node, step, has_open_entry, *, detail)`; the plan read passes its current detail text, and the merge observation passes `observed: <head> reachable from <target>`.
- **CF version.** The installed `cf` is 0.19.19 on 20261026; the LLD's 0.19.16 is a dated observation. Fixtures are captured from whatever `cf` is installed, and the version is recorded in the fixtures' README.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`.
- **Test doubles.** Pure functions get table-driven tests. Store-backed tests use `Store.open_temporary()`. Tick-level tests use `tests/runner/tick_support.py`, `tests/runner/dispatch/tick_rig.py` and `plan_tick_support.py` with the stub `cf` and `sq` on `PATH` under a temporary `HOME`, a real temporary git repository as the checkout, and a small routing table. Nothing runs a real `cf` or `sq` except Tasks 2.1 and 4.1 (capture only) and Task 11.2.
- **Test location and naming.** New package `tests/runner/gates/` (with `__init__.py`), plus `tests/runner/test_git_read.py` and `tests/runner/test_project_config.py`. Tests are named for the rule they prove (LLD, Verification Walkthrough step 1).

**Section map.** 1 baseline; 2 git read (D10); 3 per-project config and merge policy (D8); 4 CF status and the stub (D1); 5 outcome observation (D2, D4); 6 routing inputs and table (D3); 7 pre-dispatch checks (D5, D6, D11); 8 the gate disagreement (D7); 9 merge observation (D9); 10 invariants; 11 contract text and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and confirm the design's edits
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Run `git status --short`. Uncommitted edits to planning documents (the arch, the initiative plan, the slice or these tasks) are committed to the target first as `docs:`, each file by name. If any other file is dirty, write `BLOCKED:` naming it and stop
- [x] Confirm the edits the LLD lists under "Special Considerations" are present: plan entry 9 and Future Work 13 in `user/architecture/120-slices.runner-routing-engine.md`, and the three arch sections in `120-arch.runner-routing-engine.md`. Make any missing edit per the LLD and commit it to the target as `docs:`
- [x] Fold the interface changes from "Task-level additions" into the LLD, so the code review compares against one design: in "API Contracts", the `launch_candidates(current, facts, holders)` signature, `LaunchRun.journal_extra`, `ResumeRun.journal_extra`, `BlockHumanStep.payload_extra`, `ProjectView.merge_policy` and the public `complete_step`; in "Component Structure", the modules `gates/checks.py`, `gates/stage.py`, `gates/dispatch_reads.py` and `gates/accepted.py`, and the homes of `EXIT_GATE`, `ENTRY_GATE` and `DEFAULT_TARGET_BRANCH`. Also drop `list slices` from the stub's new modes (the stub already answers it). Commit it to the target as `docs:`
- [x] Confirm issues #15, #17 and #18 exist (`gh issue view <n>`). If #17 or #18 is missing, file it with the text the LLD gives (D7, D6) and note its number under this task
- [x] Create `128-slice.gates-git-and-human-steps` from the target and switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright`. Record the pass count under this task. If any fails, write `BLOCKED:` with the failure and stop
- [x] Create `src/amoeba/runner/gates/__init__.py` (docstring only) and `tests/runner/gates/__init__.py`
- [x] **Success:** on the slice branch, the suite is green and both packages exist. Commit `chore: add the gates package skeleton`

Baseline: 3951 passed; ruff check, ruff format --check and pyright clean. Issues #15, #17, #18 exist.

---

## Section 2: Git Read (D10)

### Task 2.1: Capture real `git status` output
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] Add `tests/fixtures/git/` with a README naming the git version and date. In throwaway repositories under a temporary directory, capture `git --no-optional-locks status --porcelain=v2 --branch --untracked-files=normal` for: clean on `main`; a modified file; an untracked file; a staged file; a renamed file; an unmerged file (a real conflicting merge); a detached HEAD; a path with a space. One file per case
- [x] Add `tests/runner/git_repo.py`: helpers that create a temporary repository on a named branch with one commit, make a branch, commit, combine one test branch into another inside the temporary repository, delete a branch, and detach HEAD, all with real `git` (identity set by `-c` flags, not global config)
- [x] **Success:** fixtures exist and are byte-for-byte git's output. Commit `test: capture git status fixtures and a git repository helper`

### Task 2.2: Implement `git_read` and the porcelain parser
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 3

- [x] Create `runner/git_read.py` per D10: `GIT_SUBCOMMANDS`, the two argument builders (`status_args()`, `is_ancestor_args(head, target)`), `git_read(args, cwd, budget, run, timeout_seconds) -> GitReadResult | GitReadFailure | None` (`None` when the budget refuses the call), stdin `/dev/null`, `GIT_TERMINAL_PROMPT=0` in the environment, a subcommand outside the allowlist raises `ValueError`
- [x] `parse_porcelain_v2(text) -> GitStatus(branch: str | None, head: str | None, dirty: tuple[str, ...])`: `(detached)` gives `branch` `None`; unknown header lines are ignored; the path is read by entry kind (for a rename, the new path)
- [x] `tests/runner/test_git_read.py`: the parser on every captured fixture; the allowlist refuses `commit`, `checkout` and `push`; `git_read` against a real repository for `status_args()` and for `is_ancestor_args(...)` exit 0 and 1; a timeout and a missing executable are `GitReadFailure`; a spent budget starts nothing
- [x] **Success:** tests pass. Commit `feat: read git through one allowlisted function`

Note: porcelain v2 rename lines (type 2) are `<new path>TAB<old path>`, so the parser reads the path by entry kind (splitting on the field count, then on the TAB for renames) instead of taking the last field; this keeps paths with spaces and gives the new path for renames.

---

## Section 3: Per-Project Config and Merge Policy (D8)

### Task 3.1: Implement `ProjectConfig` and its loader
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] Create `runner/project_config.py` per D8: `MergePolicy`, `PROJECT_DEFAULTS`, the pydantic models (`extra="forbid"`, values trimmed and lower-cased), `ProjectConfig.for_project(project_id)` returning the entry merged over the defaults, and `load_project_config(path: Path | None) -> ProjectConfig`. `None` gives defaults. A missing or unreadable file, bad YAML, an unknown key or value raises `StartupFailedError` listing every problem
- [x] `tests/runner/test_project_config.py`: no path; a named project; an unnamed project; an omitted key; `" Auto "` normalised; each failure, with two problems in one file both named
- [x] **Success:** tests pass. Commit with Task 3.2

### Task 3.2: Add the setting and flag, and load the config at start
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 2

- [x] `process/settings.py`: `project_config_path: Path | None = None`, documented beside `routing_table_path`. `cli/settings_flags.py`: `--project-config PATH`
- [x] `runner/factory.py`: `runner_tenant()` loads the config once, after the routing table; with no path, logs at INFO naming the defaults. Pass it through `RunnerTenant` to each `ProjectTick`
- [x] Tests: `tests/test_settings_flags.py` for the flag; `tests/runner/test_factory.py`: an invalid file raises `StartupFailedError`; `amoeba start --project-config` with `merge_policy: sometimes` exits `STARTUP_FAILED` naming `merge_policy` and `sometimes` (CLI test)
- [x] **Success:** tests pass. Commit `feat: load a per-project config holding the merge policy`

Note: RunnerTenant takes a required `project_config: ProjectConfig` keyword (no default); the four test constructions pass `ProjectConfig()`. `load_projects(settings)` in factory.py loads and logs it.

### Task 3.3: Pass the merge policy into `dispatch_params`
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 2

- [x] `runner/dispatch/params.py`: `dispatch_params(step, slice_index, merge_policy)`; `human` gives `merge=false` for `P6`, `auto` no `merge` key. Add `PARAM_MERGE_POLICY`, `PARAM_TARGET`, `PARAM_DISPATCH_CHECK` (Task-level additions). Update the module docstring
- [x] `ProjectView.merge_policy` and `LaunchRun.journal_extra` (Task-level additions); `DispatchPlanner` passes the view's policy and, for `P6`, puts `merge_policy` in `journal_extra`; the act stage writes `journal_extra` into the entry's parameters. `ProjectTick` passes its project's policy into the view
- [x] Tests: `tests/runner/dispatch/`: both policies' params; a `P6` entry records `merge_policy: human` with no config and `auto` when configured; a reissue keeps its old entry's `merge_policy`; 125's import test still passes. `target` and `dispatch_check` are not written yet: they come from the pre-dispatch read and arrive in Task 7.5 (tested in 7.6), so these tests do not cover them
- [x] **Success:** tests pass. Commit `feat: launch P6 under the project's merge policy`

Note: ProjectTick takes a required `project_settings: ProjectSettings` (the tenant passes `project_config.for_project(project_id)`); the test Rig holds `project_settings` (defaults) so tick-level tests can set a policy. A reissue copies `merge_policy` from its old entry into `journal_extra`.

---

## Section 4: CF Status and the Stub (D1)

### Task 4.1: Capture CF status and config output
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

- [x] In a scratch CF project under a temporary directory (never this repository's CF project), with `workflow.review_enabled` and `workflow.decision_gate_enabled` set to `true`, capture `cf status --json -p <id>` for each `activeSlice.status` in the LLD's D1 table: `needs-design`, `needs-tasks`, `in-implementation`, `complete`, `no-active-slice`, `pending-decision`, and `pending-review` and `review-failed` at each of the `slice`, `tasks` and `code` gates. Reach each state by CF's position rules (LLD "Interfaces Required"; CF source `reviewGate.ts`). Also capture one with `gateExempt` (`review: none`), one from a worktree with `--worktree`, and `cf config get <key> --json` for both keys, empty and set
- [x] Save under `tests/fixtures/cf/status/` and `tests/fixtures/cf/config/`, one file per case, with a README naming the CF version, date and how each state was reached. Remove the scratch CF project afterwards
- [x] If a state cannot be reached, write `BLOCKED:` naming it and the attempt; only Task 4.3's row for that state waits
- [x] **Success:** a fixture exists for every D1 row and both config keys. Commit `test: capture CF status and config fixtures`

Note: `cf status --json --worktree` accepts the worktree id (`wt_...`) as well as its name. Fixtures are in tests/fixtures/cf/status/ (15 files) and tests/fixtures/cf/config/ (4 files); the README names how each state was reached. CF 0.19.19.

### Task 4.2: Add the CF command words and the gate and config reads
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [ ] `runner/lifecycle/plan_read.py`: the additions under Task-level additions; update `COMMAND_WORDS` in the source test
- [ ] Create `runner/gates/cf_reads.py`: `DEFAULT_TARGET_BRANCH` (citing the key's description); `read_config(key, checkout, cf_project_id, budget, run, timeout) -> str | ReadFailure | None` (a missing or non-string `value` is a failure, never a default; `None` when cut off); `read_target(...)` mapping empty to `DEFAULT_TARGET_BRANCH`; `read_gate(checkout, worktree_id, cf_project_id, budget, run, timeout) -> dict | ReadFailure | None` returning the parsed JSON for Task 4.3's model
- [ ] Tests (`tests/runner/gates/test_cf_reads.py`) with a fake `CfRun`: argv for each read, with and without `--worktree`; `cwd` is the checkout; a non-string value, a non-zero exit, bad JSON and a timeout are failures; empty target is `main`; a spent budget starts nothing
- [ ] **Success:** tests pass, including `test_cf_commands_defined_once.py`. Commit with Task 4.3

### Task 4.3: Implement the CF status model and `position_of`
**Owner**: Junior AI | **Dependencies**: 4.1, 4.2 | **Effort**: 2

- [ ] Create `runner/gates/cf_status.py` per D1 and "API Contracts": `CFActiveSlice` (lenient about added keys, strict about mapped fields), `parse_status(document) -> CFActiveSlice | None`, `GatePosition` with `PENDING_DECISION` and `UNKNOWN` outside the ordered scale, `position_of(active_slice)`, `EXIT_GATE` and `ENTRY_GATE` (Task-level additions)
- [ ] `tests/runner/gates/test_cf_status.py`: every D1 row against its captured fixture; trimmed and upper-case status text; an unknown status, an unknown review type and a missing `gateInfo` are `UNKNOWN`; `rationale` and `pendingDecisions` are carried, never matched
- [ ] **Success:** tests pass. Commit `feat: read CF's gate position from cf status`

### Task 4.4: Add the stub `cf` gate modes and the rig helpers
**Owner**: Junior AI | **Dependencies**: 2.1, 4.1 | **Effort**: 3

- [ ] Put the new stub code in `tests/cf_stub_gates.py` (`tests/cf_stub.py` is 325 lines): `status --json` answers with a fixture named by an environment variable (or a per-index mapping file), defaulting to the existing probe answer when unset; `config get <key> --json` answers from a state file, empty values by default; a failure mode for each. Every call is logged to the stub log, as now
- [ ] Add rig helpers in a new `tests/runner/gate_rig.py`: make a rig's checkout a real git repository on `main` (Task 2.1's helper), write a slice design with given frontmatter at the path the stub's `list slices` reports, and set the stub's status fixture for a slice
- [ ] Tests (`tests/test_cf_stub_gates.py`): each mode returns its fixture byte for byte; the probe answer is unchanged; existing stub tests pass
- [ ] **Success:** tests pass. Commit `test: add gate modes to the stub cf`

---

## Section 5: Outcome Observation (D2, D4)

### Task 5.1: Implement the check vocabulary and `hatch_checks`
**Owner**: Junior AI | **Dependencies**: 4.3 | **Effort**: 3

- [ ] Create `runner/gates/checks.py` (Task-level additions). Create `runner/gates/hatches.py` with `read_frontmatter(text) -> Mapping | FrontmatterError` (D4's frontmatter rule, byte-order mark and leading whitespace allowed, `dateCreated` converted back to text) and the pure `hatch_checks(entry_id, slice_node_id, design, effective_date, amoeba_version) -> tuple[CheckInput, CheckInput]`. `design` is the path and text, or a reason it is unknown or missing; `effective_date` is text or a failed read
- [ ] `tests/runner/gates/test_hatches.py`, table-driven over every D4 cell: each `failed`, `passed` and `errored` case of both checks; a missing design is `vacuous` for both (`examined_count` 0); `None`/`NONE` escalate; `dateCreated: 20261021` as an integer compares as text; ids and provenance as D4 gives them
- [ ] **Success:** tests pass; the module does no I/O. Commit `feat: record the ungate hatches as checks`

### Task 5.2: Implement `observe_outcome` and `gate_state_at_exit`
**Owner**: Junior AI | **Dependencies**: 2.2, 4.2, 4.4, 5.1 | **Effort**: 3

- [ ] Create `runner/gates/outcome.py` per D2: `OutcomeObservation` (the gate part, `design_path`, the optional git part, the two `CheckInput`s) with `to_result()` producing the "Entry result" shape; `observe_outcome(entry, step, slice_node, initiative_index, budget, cf_run, timeout, amoeba_version) -> OutcomeObservation | None` running D2's five reads in order, `None` only when the budget cut it off. A gate read for another slice index is recorded as a gate failure. The design file is resolved against the checkout as 125 (D7) resolves review paths
- [ ] The pure `gate_state_at_exit(step, gate_record) -> str` per D3's `gate_state` rules, reading the stored gate record
- [ ] `tests/runner/gates/test_outcome.py`: with the stub `cf` and a real repository, each read's answer lands in the observation; `git` is present only for `implementation`; each failed read is recorded, not raised; a cut-off between reads returns `None`; `gate_state_at_exit` table-driven over D3's rows for all three steps, including `misplaced` and `unknown`
- [ ] **Success:** tests pass. Commit with Task 5.3

### Task 5.3: Record the observation at ingestion and wire the stage
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 3

- [ ] `runner/ingest/record.py` and `runner/finish.py`: `record` takes `observation: OutcomeObservation | None`. For a `completed` outcome: both `record_check` calls first, then 125's block, then the result with `outcome_observation` and `check_ids` (D2 "Order"). Other outcomes ignore it. A `completed` outcome without an observation raises `ValueError`
- [ ] Create `runner/gates/stage.py` with `GateStage.observe_outcomes(runs, budget)` returning the observations by entry id for each finished `completed` run. `tick.py` calls it after Observe; `_record_finished` records a `completed` run only when its observation is present, otherwise leaves the entry unresolved and keeps it tracked (D2, "Only a TickBudget cut-off defers")
- [ ] Tests: `tests/runner/ingest/`: the write order (checks, block, report); a repeat after a crash between the writes keeps the first check records; `tests/runner/gates/test_tick_outcome.py`: a completed `P5` records two checks on the slice node and the observation in its result; a cut-off before the observation leaves the entry unresolved and the next tick records it once
- [ ] Run `uv run pytest -q`. Each failure because a tick test's rig has no design or gate answer is fixed with Task 4.4's helpers; any other failure is a defect: fix it here or write `BLOCKED:`
- [ ] **Success:** full suite green. Commit `feat: observe CF's gate, the hatches and git when a run completes`

---

## Section 6: Routing Inputs and Table (D3)

### Task 6.1: Add `gate_state` and `check_standing`
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

- [ ] `routing/inputs.py`: the two inputs and their value sets; `STANDING_WORST_FIRST`. `routing/evidence.py`: `gather` reads `outcome_observation` and the check records named by `check_ids` (`store.check`). `routing/reduce.py`: `gate_state` through `gate_state_at_exit`; `check_standing` the worst standing, `unknown` for an id the store does not hold; both `none` for an outcome other than `completed`
- [ ] Tests in `tests/runner/routing/`: each value of both inputs; a pre-128 completed entry (no observation) gives `unknown`; table validation accepts a table naming both; recompute of a decision recorded before this slice reports 126's changed-vocabulary error, as 127's note records for `review_accepted`
- [ ] **Success:** tests pass. Commit with Task 6.2

### Task 6.2: Edit the shipped table
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 3

- [ ] `routing/tables/default.yaml`: the three changed rules per D3; bump the table version
- [ ] Tick tests (`tests/runner/gates/test_tick_routing.py`), one per LLD "Gate at the outcome" and "Hatches" criterion: `P5` PASS with `in-implementation` advances; with `review-failed` at the tasks gate escalates; `test_derived_pass_cleared_by_cf_escalates`; `pending-decision` after `P4` escalates with the decisions in the result; `P6` with `in-implementation` escalates as `misplaced`; a failed gate read escalates as `unknown`; `test_review_none_check_failed_and_escalates`; an early `dateCreated` escalates; a missing design escalates with both checks `vacuous`; in the `review: none` test, `amoeba inspect checks --node <slice>` shows each hatch check with the design path and the values examined; a PM completed-outcome accept of a hatch escalation advances
- [ ] Run `uv run pytest -q`. Each test that now escalates only because its rig gives no gate answer sets the stub status past that step's exit gate; any other failure is a defect
- [ ] **Success:** full suite green. Commit `feat: require a clear gate and passed checks before advancing`

---

## Section 7: Pre-Dispatch Checks (D5, D6, D11)

### Task 7.1: Add the fault kinds, `DispatchCheck` and `BlockDispatch`
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [ ] `runner/faults.py`: the five members per D11, documented in the class docstring (`checkout_read_failed` project-scoped, the rest node blocks)
- [ ] Create `runner/gates/predispatch.py` with `Ok`, `Block` and `DispatchCheck` per "API Contracts" (no import of `decide.py`). `runner/decide.py`: `BlockDispatch`, the widened `Action`, and `ProjectView.dispatch_checks` (empty by default). `ProjectView.merge_observations` waits for Task 9.2, which defines its value type
- [ ] `runner/act.py`: apply `BlockDispatch` with `block_once` on `HUMAN`, with `fault_kind` in the payload, store only
- [ ] Tests: `tests/runner/test_act*.py`: a `BlockDispatch` writes one block and no journal entry, and a second is skipped
- [ ] **Success:** tests pass. Commit `feat: add the dispatch block action and its fault kinds`

### Task 7.2: Implement `branch_rule` and the entry gate
**Owner**: Junior AI | **Dependencies**: 4.3, 7.1 | **Effort**: 3

- [ ] In `runner/gates/predispatch.py`, pure: `allowed_branches(pipeline, target, slice_index)` and `branch_rule(status, target, pipeline, slice_index, *, resume) -> Block | None` per D5's git order and D6's table (Task-level additions for the own-branch rule; dirty paths capped at 20 with the count; a resume never blocks on a dirty tree); `entry_gate(step, active_slice, slice_index, accepted: bool) -> Ok | Block | NoResult | Disagreement` per D5's entry-gate table, where `accepted` says the predecessor was accepted by the PM and `Disagreement` tells the caller to record D7's check, then go on
- [ ] `tests/runner/gates/test_predispatch.py`, table-driven over every D5 and D6 row: `test_dirty_tree_blocks_launch`; `test_planning_run_refused_off_target`; `P6` on its own branch is allowed and on another slice's branch blocks; `test_resume_not_blocked_by_its_own_dirty_tree`; detached blocks; a `/`-prefixed branch is not the slice's own; each entry-gate row for `tasks` and `implementation`; `slice_design` has no entry gate
- [ ] **Success:** tests pass; no I/O. Commit with Task 7.3

### Task 7.3: Implement `launch_candidates` and `read_dispatch_facts`
**Owner**: Junior AI | **Dependencies**: 2.2, 4.2, 7.2 | **Effort**: 3

- [ ] In `runner/gates/predispatch.py`: the pure `launch_candidates(current, facts, holders)` (Task-level additions). In a new `runner/gates/dispatch_reads.py`: `read_dispatch_facts(candidate, budget, run, timeout) -> DispatchReads | ReadFailure | None` doing D5's reads in order (the gate read only for a fresh or reissued `tasks` or `implementation` launch), and `check_candidate(candidate, reads, accepted: bool) -> DispatchCheck | Disagreement | None` combining the two rules and building `Ok`'s evidence (`branch`, `head`, `target`, `gate_status`, `gate_review_type`, plus dirty paths for a resume)
- [ ] Tests: `launch_candidates` over each state and holder case (a `REISSUE` in a held checkout and a `RESUME` in a checkout held by another node are not candidates; `NEEDS_POINTER` and `REOBSERVE` never are); `read_dispatch_facts` with the stub `cf` and a real repository, including a failed read and a cut-off; `check_candidate`'s evidence for a launch and a resume
- [ ] **Success:** tests pass. Commit `feat: check the checkout and the entry gate before dispatch`

### Task 7.4: Run the checks in the tick
**Owner**: Junior AI | **Dependencies**: 5.3, 7.3 | **Effort**: 2

- [ ] `GateStage.check_dispatch(view, budget, faults)`: for each candidate, the reads and the check; a failed read adds `checkout_read_failed` with `{checkout, command, reason}`; returns `dispatch_checks` by node id. (`Disagreement` is treated as `Ok` here; Task 8.2 records it.) `tick.py` replaces the view with them (Task-level additions). No planner reads them yet
- [ ] Tests (`tests/runner/gates/test_stage_dispatch.py`): a tick with a pointed step on a dirty checkout puts a `Block` in the view's `dispatch_checks`; a clean one puts `Ok`; a failed read puts nothing and raises `checkout_read_failed`
- [ ] **Success:** full suite green. Commit `feat: run the pre-dispatch checks in the tick`

### Task 7.5: Filter the planners on the checks
**Owner**: Junior AI | **Dependencies**: 3.3, 7.4 | **Effort**: 3

- [ ] `DispatchPlanner`: the chosen `POINTED` or `REISSUE` step launches only on `Ok`, with `dispatch_check` (and, for `P6`, `target`) in `journal_extra`; a `Block` gives `BlockDispatch`; no entry gives nothing. `ContinuationPlanner`: the same for `RESUME`, and `runner/resolutions/act.py` writes `ResumeRun.journal_extra` into the continuation entry's parameters. `decide()`: a `LaunchRun` or `ResumeRun` for a node without `Ok` in `dispatch_checks` raises `ValueError` (D5 guard)
- [ ] **Rig update** (same commit, so the suite stays green). Using Task 4.4's helpers, make every checkout a clean git repository on `main` and have the stub answer the gate past each step's entry gate, in exactly these files:
  - [ ] `tests/runner/tick_support.py`
  - [ ] `tests/runner/dispatch/tick_rig.py`
  - [ ] `tests/runner/plan_tick_support.py`
  - [ ] `tests/runner/crash_harness.py`, `tests/runner/crash_entry.py` and `tests/runner/crash_resume.py`
- [ ] Run `uv run pytest -q`. A failure the rig update fixes is done. A failure in the planners, `decide()` or `runner/resolutions/act.py` is this task's defect: fix it. Any failure elsewhere: write `BLOCKED:` naming the test and its error, and stop
- [ ] **Success:** full suite green, including 125's dispatch and crash tests and 127's resume tests. Commit `feat: launch and resume only on a passed pre-dispatch check`

### Task 7.6: Prove the pre-dispatch checks in the tick
**Owner**: Junior AI | **Dependencies**: 7.5 | **Effort**: 2

- [ ] `tests/runner/gates/test_tick_predispatch.py`, one test per "Clean tree and branch" and "Gate at dispatch" criterion: a dirty tree blocks a pointed step with the paths and launches nothing; wrong branch and detached block; an integration branch set in the stub's config makes `main` block a planning launch; a reissue is checked like a launch; a resume on a dirty tree resumes; `ObserveRun` and pointer writes are not checked; `pending-decision` blocks; a failing entry gate blocks `cf_gate_blocks`; a position past it launches; a failed read blocks nothing and raises `checkout_read_failed`, which closes on the next complete tick; the guard test (`decide()` refuses `LaunchRun` and `ResumeRun` without `Ok`); a blocked launch resolved with `rerun` is checked again; a launch entry's `dispatch_check` parameter equals the `Ok` evidence (`branch`, `head`, `target`, `gate_status`, `gate_review_type`); a `P6` entry's `target` is the integration branch when one is set and `main` otherwise; a resume entry's `dispatch_check` names its dirty paths
- [ ] **Success:** tests pass. Commit `test: prove the pre-dispatch checks in the tick`

---

## Section 8: The Gate Disagreement (D7)

### Task 8.1: Implement `accepted_by_pm`
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [ ] Create `runner/gates/accepted.py` with the pure `accepted_by_pm(entries, latest_blocked) -> AcceptedOutcome | None`: set when the latest blocked state has `runner_outcome` `applied` and decision `accept`, and the latest `sq_run` entry's `RESULT_OUTCOME` is `completed` (127, D7). It carries the blocked state id, the entry id and the entry's `verdict_ids`. A loop accept (a `continuation` entry) is not counted (issue #17)
- [ ] `tests/runner/gates/test_accepted.py`: accept of a completed outcome; a rejected accept; a `rerun`; a loop accept; no blocked state; an accept followed by a newer run
- [ ] **Success:** tests pass. Commit with Task 8.2

### Task 8.2: Record the disagreement and dispatch
**Owner**: Junior AI | **Dependencies**: 7.5, 8.1 | **Effort**: 2

- [ ] `GateStage.check_dispatch`: for a `tasks` or `implementation` candidate, read the predecessor step's entries and latest blocked state (the previous step in `STEP_SEQUENCE`, same slice) and pass whether `accepted_by_pm` found an `AcceptedOutcome` to `check_candidate`. On `Disagreement`, `record_check` D7's record on the slice node, built from that `AcceptedOutcome` (id `chk-<accepted entry id>-cf_gate_accept_disagreement`), then `Ok` with the check id in its evidence
- [ ] Tick tests (`tests/runner/gates/test_tick_disagreement.py`): after a PM accept of a completed `slice_design` outcome whose slice gate still fails, the `tasks` launch records one check and launches; `test_accept_disagreement_recorded_once` (a rerun of `tasks` adds no record); without an accept, the same gate blocks `cf_gate_blocks`; `amoeba inspect checks --node <slice>` shows it
- [ ] **Success:** tests pass. Commit `feat: record a PM accept CF's gate still fails` with `Fixes #15` in the body

---

## Section 9: Merge Observation (D9)

### Task 9.1: Implement `merge_state` and share the completion write
**Owner**: Junior AI | **Dependencies**: 3.3 | **Effort**: 2

- [ ] Create `runner/gates/merge.py` with `MergeObservation` (`merged`, `not_merged`, `unobservable` with a reason) and the pure `merge_state(entry, slice_index, ancestor_exit) -> MergeObservation | None` per D9's table (`None` for a read failure)
- [ ] `lifecycle/completion.py`: `complete_step` (Task-level additions), plan-read behavior unchanged
- [ ] Tests: `merge_state` table-driven over every D9 row; the existing completion tests pass unchanged
- [ ] **Success:** tests pass. Commit `feat: decide a merge from the recorded head's reachability`

### Task 9.2: Observe merges in the tick and change `HumanStepPlanner`
**Owner**: Junior AI | **Dependencies**: 7.5, 9.1 | **Effort**: 3

- [ ] `runner/gates/merge.py`: `observe_merges(store, tree, project_id, budget, run, timeout, faults) -> Mapping[str, MergeObservation]` for each slice whose `implementation` is done and `merge` is not, reading the step's latest completed `sq_run` entry, the target in its checkout and `merge-base --is-ancestor`; `merged` completes the step with `complete_step` and detail per D9; a read failure adds `checkout_read_failed`. `GateStage` runs it after the pointer stage, only when `desired.drives_anything()`; `runner/decide.py` gains `ProjectView.merge_observations: Mapping[str, MergeObservation]` (empty by default), keyed by the merge step's node id, and the view carries the result there
- [ ] `HumanStepPlanner`: a current `merge` step blocks on `not_merged` or `unobservable` (with `{merge_observation: unobservable, reason}` as `payload_extra`), and is skipped with no observation. Other human steps are unchanged
- [ ] Tick tests (`tests/runner/gates/test_tick_merge.py`), with real merges in the checkout: under `human`, after `P6` the `merge` step blocks; a `git merge --no-ff` completes it on the next tick and resolves its block by `runner`; `test_merge_observed_after_branch_deleted`; a fix-up commit before the merge is observed; a squash merge is not; `test_auto_merge_step_never_blocked`; a `human` entry that ended on the target is `unobservable`; a failed read blocks nothing and raises `checkout_read_failed`, which closes once a read succeeds; a later slice's `P4` in that checkout blocks `checkout_branch` until the merge
- [ ] **Success:** tests pass. Commit `feat: observe merges in git and complete the merge step`

---

## Section 10: Invariants

### Task 10.1: Add the git source test and extend the budget coverage test
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 2

- [ ] Source test (`tests/runner/test_git_read_only_place.py`, using `tests/ast_strings.py`): the string `"git"` as an executable appears in no `src/amoeba/runner` module other than `runner/git_read.py`
- [ ] `tests/runner/test_budget_coverage.py`: wrap the `git` and new `cf` calls so a call starting after the deadline fails the test; drive a tick with an outcome observation, a pre-dispatch check and a merge observation
- [ ] In that same driven tick, wrap the injected runner to record every `git` argv, and assert each recorded subcommand (the first argument after any `--no-optional-locks`) is in `GIT_SUBCOMMANDS`, and that at least one `status` and one `merge-base` call were recorded
- [ ] **Success:** tests pass. Commit `test: guard the git read path and the tick budget`

---

## Section 11: Contract Text and Final Validation

### Task 11.1: Update the contract documents and the CHANGELOG
**Owner**: Junior AI | **Dependencies**: 10.1 | **Effort**: 2

- [ ] Per the LLD "Provides to Other Slices", "Contract documents": `docs/process-contract.md` (the per-project config format, setting and flag, no secrets in it, and the pre-dispatch checks); `docs/evidence-contract.md` (the Runner's checks, ids and provenance); `docs/context-forge-contract.md` (the `cf status` fields and positions, the two config keys, the observed CF version); `docs/substrate-guide.md` (the 120 row, issue #15 closed)
- [ ] Under `[Unreleased]` in `CHANGELOG.md`: the pre-dispatch checks, the gate and hatch checks, the two routing inputs and the table change (completed outcomes now need a clear gate and passed checks to advance), `--project-config` and the merge policy, the merge observation, and the read-only git rule
- [ ] **Success:** every name in the text matches the code. Commit `docs: document gates, git checks and the merge policy`

### Task 11.2: Final validation and walkthrough
**Owner**: Junior AI | **Dependencies**: 11.1 | **Effort**: 2

- [ ] Run LLD Verification Walkthrough steps 1, 2 and 3. Record the pass counts and step 3's exit code and message under this task
- [ ] Confirm every source file this slice created is near 300 lines and that no file it changed grew past 300 (record any that did, with before and after counts); pyright strict is clean
- [ ] Run Verification Walkthrough step 4 on a scratch copy with the real `cf` and `git` (it launches nothing). Record what `inspect journal` and `inspect blocked` showed for the dirty tree and the wrong branch. Pause the project, switch the scratch copy back, `amoeba stop`, and remove the scratch CF project
- [ ] Step 5 is optional and spends three runs. Run it only if steps 1–4 pass; record the result either way
- [ ] A failure caused by this slice's code is fixed here; anything else gets an issue and a note under this task
- [ ] **Success:** steps 1–3 behave as the LLD expects, and step 4 shows `checkout_dirty`, then `checkout_branch`, and no `sq_run`. Commit `docs: record slice 128 validation`
