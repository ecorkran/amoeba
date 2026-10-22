---
docType: tasks
slice: run-identity-and-supported-run-surfaces
project: amoeba
lld: user/slices/120-slice.run-identity-and-supported-run-surfaces.md
dependencies:
- 101
- 102
- 103
- 104
- 105
- 106
- 107
- 108
- 109
- 110
projectState: Initiative 100 (101–110) is merged. Recovery's `sq_run` observer (`process/observers/sq_runs.py`,
  297 lines) and `amoeba prune sq-runs` (`cli/prune.py`, `process/run_pruning.py`)
  both read Squadron's run-state files under `~/.config/squadron/runs/`. `REQUIRED_PARAMETER_KEYS[SQ_RUN]`
  is `{"pipeline", "params"}`. `SQ_EXECUTABLE` is defined twice (`cli/prune.py`, `process/version_label.py`).
  `tests/sq_stub.py` answers only `runs prune`. This slice adds `process/sq_outcome.py`
  and `process/observers/sq_run_id.py`, makes `run_id` a required key, and moves recovery
  of id-bearing entries and all of pruning onto `sq runs wait <id> --timeout 0 --json`.
dateCreated: 20261021
dateUpdated: 20261022
status: not_started
turns: 19
promptTokens: 1017085
cachedTokens: 944122
cacheWriteTokens: 72929
completionTokens: 21523
durationSeconds: 235.5
costUsd: 1.20314
usageRounds: 1
pricedRounds: 1
---

## Context Summary

- Working on the **run-identity-and-supported-run-surfaces** slice (120), the first slice of initiative 120 (Runner and Routing Engine). It changes 100's side only and adds no Runner code.
- **Current state:** recovery is `reconcile` (`process/recovery.py`) over a registry from `build_observer_registry` (`process/supervisor.py`), which scans the runs directory eagerly. `Adopt`, `NotApplied`, `Unknown` are the observation types and are exported from `amoeba.process`, whose `__all__` is pinned by `tests/test_process_public_api.py`. `ProcessSettings` is `process/settings.py`; its flags are `cli/settings_flags.py`. Import Rule 9 (`tests/test_import_boundaries.py`) lets `run_pruning.py` import only the standard library and the run-file parser. Contract-suite imports must be public exports (`tests/contract/test_public_api_rule.py`).
- **Dependencies:** 100's recovery protocol, journal, `recorded_result_run_ids`, and `Store.open_read_only`, all unchanged. squadron-ai 0.23.5+ shapes (S10) only for the manual walkthrough; automated tests use the stub.
- **What this slice delivers:** `run_id` as a required `sq_run` key; one outcome reader (`poll_run`); by-id recovery with the launch grace rule; a dispatcher that sends id-less (pre-120) entries to the unchanged matcher with a lazy scan; pruning over outcome documents; `launch_grace_seconds` / `--launch-grace`; no-reads proofs; contract docs. See the LLD "Technical Scope".
- **Next planned slice:** 121 (store contract changes for the Runner), then 122, which consumes `poll_run` and `launch_grace_seconds`.

**Branch:** all implementation happens on `120-slice.run-identity-and-supported-run-surfaces`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges; merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/120-slice.run-identity-and-supported-run-surfaces.md` at the named decision (D1–D8), "Data Flow", "Migration Plan", or "API Contracts". Keep every new source file near 300 lines; `observers/sq_runs.py` is at 297, so new observer code goes in `observers/sq_run_id.py`.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with the test task that follows it; every other task commits on its own. Run `uv run ruff format .` before each commit.

**Task-level additions to the LLD:**
- `process/version_label.py` also defines `SQ_EXECUTABLE`. To honor D2's "defined only here", it imports the constant from `sq_outcome.py` (Task 2.2).
- The stub keeps its outcome documents in its own state directory, defined once in `tests/sq_stub.py`, apart from the runs directory. This is what lets the D8 tests point a runs directory at contrary files. The stub's prune modes move to that directory in Task 6.3, so 100's prune tests stay green until then.
- The LLD's caller list is incomplete. The re-grep also finds `tests/store/test_attribution.py` and `tests/store/test_verdicts.py`. The migration tests (`test_migration_004/005/006.py`) insert raw pre-120 rows with SQL and are left unchanged.
- `scripts/demo_journal.py` is retired in Section 4 rather than step 6, because it breaks as soon as `run_id` becomes required.

**Section map.** 1 baseline; 2 the outcome reader and stub; 3 the setting; 4 the required key and callers; 5 by-id recovery; 6 pruning; 7 contract suite; 8 docs and validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `120-slice.run-identity-and-supported-run-surfaces` from the target; if it exists, switch to it
- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each
- [ ] Re-grep `CommandKind.SQ_RUN` and `"sq_run"` across `src/`, `tests/`, `scripts/`. Record in this task, as a sub-list, every file that journals an `sq_run` through `journal_issue`. Section 4 works from that list, not from the LLD's
- **Success Criteria**:
  - [ ] On the slice branch; baseline suite, `ruff`, and `pyright` clean. If not, write `BLOCKED:` with the failure and stop
  - [ ] Caller list recorded. No commit needed

---

## Section 2: The Outcome Reader

### Task 2.1: Add the `runs wait` mode to the `sq` stub (test infrastructure)
**Owner**: Junior AI | **Dependencies**: Task 1.1 | **Effort**: 2

- [ ] In `tests/sq_stub.py`, define the stub's state directory once (a constant relative to `$HOME`, separate from `.config/squadron/runs`) and an exit-code table for the eight outcomes. The table must match the LLD "Interfaces Required" exit codes; it is the stub's copy of Squadron's rule and is not imported from `amoeba`
- [ ] Dispatch on arguments before reading `MODE_ENV`, so `runs wait` works without a mode set. `runs wait <id> --timeout 0 --json`: if `{state_dir}/{id}.json` exists, print it and exit with the code for its `outcome`; otherwise print `{"run_id": id, "outcome": "not_found"}` and exit 5 (LLD "Migration Plan")
- [ ] Add a test-side helper in `tests/sq_stub.py` that writes one outcome document into the state directory for a given `HOME`. Callers pass every field; the helper adds nothing
- [ ] Leave the `runs prune` modes unchanged (Task 6.3 moves them)
- **Success Criteria**:
  - [ ] Existing prune tests still pass: `uv run pytest tests/process/test_prune_sq_runs.py tests/contract -q`
  - [ ] Committed with Task 2.4

### Task 2.2: Add `RunOutcome`, `OUTCOME_EXIT_CODES`, and the document models
**Owner**: Junior AI | **Dependencies**: Task 2.1 | **Effort**: 2

- [ ] Create `src/amoeba/process/sq_outcome.py` with a module docstring saying it is the only module that runs `sq runs wait` or parses its output
- [ ] Add `SQ_EXECUTABLE` here. Change `cli/prune.py` and `process/version_label.py` to import it; remove both local definitions
- [ ] Add `RunOutcome` (`StrEnum`, eight members) and `OUTCOME_EXIT_CODES` per D2 and "API Contracts"
- [ ] Add `RunCheckpoint` and `RunOutcomeDocument` as frozen pydantic models with `extra="ignore"`, fields exactly as D2 lists. No default other than `None`
- [ ] Add `PollFailure` (frozen dataclass, `reason: str`) and `type RunPoll = RunOutcomeDocument | PollFailure`
- **Success Criteria**:
  - [ ] `grep -rn 'SQ_EXECUTABLE.*=' src/` finds exactly one definition
  - [ ] `uv run pyright` clean. Committed with Task 2.4

### Task 2.3: Implement `poll_run`
**Owner**: Junior AI | **Dependencies**: Task 2.2 | **Effort**: 3

- [ ] Implement `poll_run(run_id, *, timeout_seconds) -> RunPoll` with the exact argv and `subprocess.run` options in D2
- [ ] Return `PollFailure` for each case in D2's list, catching only the named exceptions (`FileNotFoundError`, `subprocess.TimeoutExpired`, `OSError`, `pydantic.ValidationError`, `json.JSONDecodeError` as needed). Each `except` carries a comment saying why the failure is an answer (the `cf_readback.py` convention)
- [ ] Map the exit code back to an outcome through `OUTCOME_EXIT_CODES` (one inverse lookup, built from the table, not a second table). Exit 2 or an unmapped code is a failure whose reason includes the stderr tail
- [ ] Check the parsed `outcome` against the exit code, and `run_id` against the requested id
- [ ] Every reason names the run id and what happened
- **Success Criteria**:
  - [ ] Module stays near 150 lines; `uv run ruff check .` and `uv run pyright` clean
  - [ ] Committed with Task 2.4

### Task 2.4: Test the outcome reader
**Owner**: Junior AI | **Dependencies**: Task 2.3 | **Effort**: 3

- [ ] Create `tests/test_observer_sq_outcome.py`. Unit tests patch `subprocess.run`:
  1. One test per outcome: the right exit code and document give a `RunOutcomeDocument` with that outcome
  2. not_found and unreadable documents with only `run_id` and `outcome` parse, other fields `None`
  3. Unknown extra keys are ignored; a null `checkpoint.paused_at` stays `None`
  4. One test per `PollFailure` case in D2: missing `sq`, timeout, other `OSError`, exit 2, unmapped exit, non-JSON, validation failure, outcome/exit mismatch, `run_id` mismatch. Each asserts the reason names the cause
  5. `OUTCOME_EXIT_CODES` covers every `RunOutcome` member with distinct codes
- [ ] Integration tests run the stub on `PATH` under a temporary `HOME`: a written paused document round-trips; a missing id gives `NOT_FOUND`
- **Success Criteria**:
  - [ ] `uv run pytest tests/test_observer_sq_outcome.py -v` passes; full suite green
  - [ ] Commit, e.g. `feat: add sq runs wait outcome reader`

### Task 2.5: Export the reader from `amoeba.process`
**Owner**: Junior AI | **Dependencies**: Task 2.4 | **Effort**: 1

- [ ] Add `RunOutcome`, `OUTCOME_EXIT_CODES`, `RunCheckpoint`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, and `poll_run` to `amoeba/process/__init__.py` and `__all__` (LLD "API Contracts")
- [ ] Update `EXPECTED_EXPORTS` in `tests/test_process_public_api.py`
- **Success Criteria**:
  - [ ] `uv run pytest tests/test_process_public_api.py tests/contract/test_public_api_rule.py -q` passes
  - [ ] Commit, e.g. `feat: export the outcome reader from amoeba.process`

---

## Section 3: The Launch Grace Setting

### Task 3.1: Add `launch_grace_seconds` and `--launch-grace`
**Owner**: Junior AI | **Dependencies**: Task 2.5 | **Effort**: 1

- [ ] Add `ProcessSettings.launch_grace_seconds: float = 60.0` with a docstring entry per D7 (read by recovery here and by 122)
- [ ] Add `--launch-grace SECONDS` in `cli/settings_flags.py`, defaulting from `ProcessSettings()` like its neighbours, and pass it through
- [ ] Reword the docstrings of `sq_runs_dir` and `clock_tolerance_seconds`, and the `--sq-runs-dir` help text, to say they are used only by legacy matching (D5, D7)
- **Success Criteria**:
  - [ ] Committed with Task 3.2

### Task 3.2: Test the setting
**Owner**: Junior AI | **Dependencies**: Task 3.1 | **Effort**: 1

- [ ] In `tests/test_settings_flags.py`: the default reaches `ProcessSettings`; `--launch-grace 5` sets 5.0; the help text for `--sq-runs-dir` says legacy
- **Success Criteria**:
  - [ ] `uv run pytest tests/test_settings_flags.py -q` passes; full suite green
  - [ ] Commit, e.g. `feat: add launch_grace_seconds setting and --launch-grace flag`

---

## Section 4: The Required `run_id` Key

### Task 4.1: Add the shared `sq_run_parameters` test helper
**Owner**: Junior AI | **Dependencies**: Task 3.2 | **Effort**: 1

- [ ] Create `tests/sq_run_fixtures.py` with `sq_run_parameters(...)`: it takes the parameters a caller would pass and a run id, and returns them with `run_id` added. Nothing else (LLD "Migration Plan")
- [ ] Add a raw `sqlite3` helper in the same module that writes one pre-120 `sq_run` journal row without `run_id`, for store-level legacy tests (LLD "Migration Plan", `test_observer_sq_runs.py`)
- **Success Criteria**:
  - [ ] Helper imports cleanly; committed with Task 4.3

### Task 4.2: Make `run_id` required
**Owner**: Junior AI | **Dependencies**: Task 4.1 | **Effort**: 1

- [ ] In `store/journal_models.py`, define `PARAM_RUN_ID: Final = "run_id"` and add it to `REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN]` (D1). Reference the constant, never the literal
- **Success Criteria**:
  - [ ] The suite now fails at every id-less `journal_issue` call; Task 4.3 fixes them. Committed with Task 4.3

### Task 4.3: Update every journaling caller
**Owner**: Junior AI | **Dependencies**: Task 4.2 | **Effort**: 3

Work from the list recorded in Task 1.1. One sub-item per group:
- [ ] Store tests: `test_journal.py`, `test_journal_models.py`, `test_read_only_open.py`, `store/test_runner_report.py`, `store/test_messages.py`, `store/test_attribution.py`, `store/test_verdicts.py`
- [ ] Process and CLI tests: `test_recovery.py`, `test_host.py`, `test_cli_lifecycle.py`, `process/test_review_detection_ownership.py`, `process/test_prune_sq_runs.py`
- [ ] Harnesses and tiers: `inspection_harness.py`, `inspection/test_feed.py`, `load/load_harness.py`, `load/test_recovery_scale.py`
- [ ] Contract suite: `contract/runner_tenant.py` mints the id with `new_run_id` before `journal_issue` and passes it in `parameters`; `contract/end_state.py` and `contract/harness.py` as the grep requires
- [ ] `tests/test_observer_sq_runs.py`: matcher cases keep id-less `JournalEntry` values; any store-level legacy case uses the raw-row helper from Task 4.1
- [ ] Leave `store/test_migration_00{4,5,6}.py` unchanged (raw pre-120 rows)
- [ ] Use `sq_run_parameters` everywhere; never spell `"run_id"` in a test's parameters
- **Success Criteria**:
  - [ ] Full suite green, matcher tests unchanged in outcome
  - [ ] Committed with Task 4.4

### Task 4.4: Test the required key
**Owner**: Junior AI | **Dependencies**: Task 4.3 | **Effort**: 1

- [ ] In `tests/test_journal.py`: `journal_issue` refuses an `sq_run` without `run_id`, and the error names the key; it accepts one with it
- [ ] In `tests/test_journal_models.py`: `PARAM_RUN_ID` is in `REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN]`
- **Success Criteria**:
  - [ ] Full suite green
  - [ ] Commit, e.g. `feat: require run_id in sq_run journal parameters`

### Task 4.5: Retire `scripts/demo_journal.py`
**Owner**: Junior AI | **Dependencies**: Task 4.4 | **Effort**: 1

- [ ] Delete `scripts/demo_journal.py` and its entry in `PERMITTED_SCRIPTS` (`tests/test_writer_guard.py`). Grep for other references (README, docs) and remove them
- **Success Criteria**:
  - [ ] `grep -rn demo_journal .` (excluding `.git`) finds only history documents; full suite green
  - [ ] Commit, e.g. `chore: retire demo_journal script`

---

## Section 5: By-Id Recovery

### Task 5.1: Implement `SquadronRunIdObserver` (state and failure paths)
**Owner**: Junior AI | **Dependencies**: Task 4.5 | **Effort**: 3

- [ ] Create `src/amoeba/process/observers/sq_run_id.py`. The constructor takes `launch_grace_seconds`, `poll_timeout_seconds`, `claimed_run_ids`, a `now` callable, and a `sleep` callable. All are required; the registry passes the real ones (Task 5.4)
- [ ] `observe(entry)`: read `entry.parameters[PARAM_RUN_ID]`. A value that is not a non-empty string is `Unknown`, naming the value (D1)
- [ ] Poll once. Any of the six state-bearing outcomes adopts with a result holding `run_id`, `outcome`, `status` (D3). Define the set of state-bearing outcomes once, from `RunOutcome`
- [ ] An id in `claimed_run_ids` under another entry is `Unknown` instead of adopting (D3)
- [ ] `UNREADABLE` and any `PollFailure` are `Unknown` with the reason
- [ ] Do not record `schema_version`
- **Success Criteria**:
  - [ ] `uv run pyright` clean. Committed with Task 5.3

### Task 5.2: Implement the launch grace rule
**Owner**: Junior AI | **Dependencies**: Task 5.1 | **Effort**: 2

- [ ] On `NOT_FOUND`, follow D4 and "Data Flow" exactly: null `issued_at` is `Unknown`; inside grace, sleep until `issued_at + grace` capped at `launch_grace_seconds`, then poll once more (state adopts, failure is `Unknown`, still not_found is `NotApplied`); past grace is `NotApplied("no run state for <id> after the launch grace period")`
- [ ] Sleep at most once per entry; no retry after a failed poll
- **Success Criteria**:
  - [ ] Committed with Task 5.3

### Task 5.3: Unit-test the by-id observer
**Owner**: Junior AI | **Dependencies**: Task 5.2 | **Effort**: 3

- [ ] Create `tests/test_observer_sq_run_id.py` with a fake `poll_run`, a fixed `now`, and a recording `sleep`. Build entries as `JournalEntry` values:
  1. Each of the six state-bearing outcomes adopts with `run_id`, `outcome`, `status` in the result
  2. `UNREADABLE` and a `PollFailure` escalate with the reason
  3. Non-string, empty, and missing-value `run_id` escalate, naming the value
  4. A claimed id escalates
  5. not_found past grace is `NotApplied`; null `issued_at` is `Unknown`
  6. not_found inside grace: sleeps the remaining time, then adopts / `NotApplied` / `Unknown` per the second poll
  7. `issued_at` ahead of the clock: the sleep is capped at `launch_grace_seconds`
- **Success Criteria**:
  - [ ] `uv run pytest tests/test_observer_sq_run_id.py -v` passes
  - [ ] Commit, e.g. `feat: add by-id sq_run recovery observer with launch grace`

### Task 5.4: Add the dispatcher, the lazy scan, and registry wiring
**Owner**: Junior AI | **Dependencies**: Task 5.3 | **Effort**: 2

- [ ] In `sq_run_id.py`, add `SquadronRunObserver`: `PARAM_RUN_ID` present goes to the by-id observer, absent goes to `SquadronRunsObserver` (D5)
- [ ] In `supervisor.build_observer_registry`, build the dispatcher; build the matcher with `scan=None`; drop the eager `scan_runs_directory` import and call; pass `launch_grace_seconds`, `sq_timeout_seconds`, the claimed ids, and the real clock and sleep. Update the docstring (no eager scan)
- [ ] In `observers/sq_runs.py`, reword the module docstring: legacy-only, for entries journaled before 120. No logic change
- [ ] Export `SquadronRunObserver`/`SquadronRunIdObserver` from `observers/__init__.py` only if the existing module exports its siblings
- **Success Criteria**:
  - [ ] `sq_runs.py` stays under 300 lines; full suite green
  - [ ] Committed with Task 5.5

### Task 5.5: Test dispatch and store-level recovery, including the D8 proof
**Owner**: Junior AI | **Dependencies**: Task 5.4 | **Effort**: 3

- [ ] In `tests/test_observer_sq_run_id.py`: the dispatcher routes by key presence; the matcher's scan is not touched for an id-bearing entry
- [ ] In `tests/test_recovery.py`, with the stub on `PATH` under a temporary `HOME`: an id-bearing entry with a stub document is adopted; one with none past grace is `not_applied`; a legacy raw row still recovers through the matcher with unchanged results
- [ ] Add `test_recovery_by_id_reads_no_run_state_file` per D8: id-bearing entries covering adopted, `not_applied`, and `unknown`; `scan_runs_directory` and `parse_run_file` patched to fail if called; `sq_runs_dir` pointing at files that would match
- **Success Criteria**:
  - [ ] Both test files pass; full suite green
  - [ ] Commit, e.g. `feat: route sq_run recovery by run id with lazy legacy scan`

### Task 5.6: Update the load tier
**Owner**: Junior AI | **Dependencies**: Task 5.5 | **Effort**: 2

- [ ] In `tests/load/test_recovery_scale.py`, replace the one-scan-per-pass assertion with: zero scans for a pass of id-bearing entries, one for a pass with legacy entries, one poll per id-bearing entry (LLD "Migration Plan")
- [ ] Add the D4 startup-bound test: N in-grace not_found entries with a fake clock and recording sleep; assert total sleep ≤ `launch_grace_seconds` and polls ≤ 2 × N
- **Success Criteria**:
  - [ ] `uv run pytest tests/load -q` passes
  - [ ] Commit, e.g. `test: assert by-id recovery scan, poll, and startup bounds`

---

## Section 6: Pruning on Outcome Documents

### Task 6.1: Rewrite `select_prunable` over `RunOutcomeDocument`
**Owner**: Junior AI | **Dependencies**: Task 5.6 | **Effort**: 2

- [ ] In `process/run_pruning.py`, take `RunOutcomeDocument` values instead of `SquadronRun`; apply D6's five conditions, with any null making a non-candidate. Keep `PRUNE_RETENTION` and `PAUSED_STATUS` defined here; compare outcome to `RunOutcome.PAUSED`. Update the module docstring
- [ ] Update Rule 9 in `tests/test_import_boundaries.py`: the allowed non-stdlib import becomes `amoeba.process.sq_outcome`; update the rule's docstring line and its negative test
- **Success Criteria**:
  - [ ] Committed with Task 6.4 (the CLI depends on the old signature until Task 6.3)

### Task 6.2: Test selection
**Owner**: Junior AI | **Dependencies**: Task 6.1 | **Effort**: 2

- [ ] Rewrite `tests/process/test_prune_selection.py` over documents: owned/held rules unchanged; one non-candidate test per D6 condition (outcome not paused, status not paused, null or naive `paused_at`, null or naive `updated_at`, inside retention); the boundary at exactly `PRUNE_RETENTION` is a candidate
- **Success Criteria**:
  - [ ] Selection and import-boundary tests pass. Committed with Task 6.4

### Task 6.3: Rewrite the prune command to poll
**Owner**: Junior AI | **Dependencies**: Task 6.2 | **Effort**: 3

- [ ] In `cli/prune.py`, follow "Data Flow" (Pruning): poll each owned id with `poll_run`, timeout from `ProcessSettings().sq_timeout_seconds`; print `could not check: <id> (<reason>)` on stderr for each failure; select; preview; with `--yes` call `sq runs prune` once
- [ ] After pruning, poll each candidate: `NOT_FOUND` is removed, anything else is still present and gives `PRUNE_INCOMPLETE`
- [ ] Remove `_read_runs`, the `runs_dir` parameter, and the imports of `observers.sq_runs` and `DEFAULT_SQ_RUNS_DIR`. Interface, exit codes, preview format, and kept-count meaning stay (LLD "Behaviour preserved")
- [ ] In `tests/sq_stub.py`, move the `runs prune` modes to delete files in the stub state directory
- **Success Criteria**:
  - [ ] `uv run pyright` clean. Committed with Task 6.4

### Task 6.4: Test the command, including the D8 proofs
**Owner**: Junior AI | **Dependencies**: Task 6.3 | **Effort**: 3

- [ ] Rewrite `tests/process/test_prune_sq_runs.py` to set up runs as stub documents: preview, `--yes`, every stub mode, `PRUNE_INCOMPLETE`, a poll failure named on stderr and never chosen with exit `OK`
- [ ] Add `test_prune_reads_no_run_state_file` per D8: a runs directory whose files would select differently; the result follows the stub's documents
- [ ] Add the D8 import-boundary test in `tests/test_import_boundaries.py`: `cli/prune.py` and `process/run_pruning.py` import nothing from `observers.sq_runs` and do not import `DEFAULT_SQ_RUNS_DIR`
- **Success Criteria**:
  - [ ] `uv run pytest tests/process tests/test_import_boundaries.py -q` passes; full suite green
  - [ ] Commit, e.g. `feat: prune paused runs from sq runs wait outcome documents`

---

## Section 7: Contract Suite Through the Stub

### Task 7.1: Move the stand-in Runner onto stub outcome documents
**Owner**: Junior AI | **Dependencies**: Task 6.4 | **Effort**: 3

- [ ] In `tests/contract/standin.py`, `runner_tenant.py`, and `steps_late.py`, write stub outcome documents (via the Task 2.1 helper) where they now call `write_run_file`. Carry the same status, `updated_at`, and checkpoint facts. Remove `write_run_file` and the runs-directory fixture use if nothing else needs them
- [ ] In `tests/contract/harness.py`, put the stub's bin directory first on `PATH` for every process the harness starts, so recovery polls the stub. `sq --version` failing is acceptable (`version_label.py` records it as unavailable)
- [ ] In `steps_prune.py`, check presence through the stub state directory
- [ ] All new imports from `amoeba` must be public exports
- **Success Criteria**:
  - [ ] `uv run pytest tests/contract -v` passes, including recovery steps and step 12's pruning
  - [ ] Commit, e.g. `test: drive the contract suite through the stub's runs wait`

---

## Section 8: Documents and Validation

### Task 8.1: Update `docs/process-contract.md`
**Owner**: Junior AI | **Dependencies**: Task 7.1 | **Effort**: 2

- [ ] Recovery property 3 as worded in D3
- [ ] The `sq_run` `not_applied` definition and the reissue rule from D4: no run state after grace, not proof the run never started; reissue only after the launch-log check and one more poll
- [ ] The shipped observers (by-id, dispatcher, legacy matcher), the supervisor directory table's `runs/` row (legacy only), `--launch-grace` in the start flags, and pruning over outcome documents with the `could not check` line
- **Success Criteria**:
  - [ ] Every item in the LLD "Contract documents" list for this file is covered
  - [ ] Commit, e.g. `docs: update process contract for by-id recovery and pruning`

### Task 8.2: Update `docs/store-contract.md` and `docs/substrate-guide.md`
**Owner**: Junior AI | **Dependencies**: Task 8.1 | **Effort**: 1

- [ ] Store contract: `run_id` in `sq_run`'s required parameter keys
- [ ] Substrate guide, 120 row: the issuer must put `run_id` in both `parameters` and `result`
- **Success Criteria**:
  - [ ] Commit, e.g. `docs: record run_id as a required sq_run key`

### Task 8.3: Add the CHANGELOG entry
**Owner**: Junior AI | **Dependencies**: Task 8.2 | **Effort**: 1

- [ ] Under `[Unreleased]`, one or two lines: slice 120 requires `run_id`, recovers and prunes through `sq runs wait`, adds `--launch-grace`, retires `demo_journal.py`
- **Success Criteria**:
  - [ ] Commit, e.g. `docs: add slice 120 changelog entry`

### Task 8.4: Final validation and walkthrough
**Owner**: Junior AI | **Dependencies**: Task 8.3 | **Effort**: 2

- [ ] Run LLD "Verification Walkthrough" steps 1 and 2 once each
- [ ] Run step 3 against the real `sq` (read-only). If `sq` is not on `PATH`, write `BLOCKED:` under this item with the reason and leave it unchecked
- [ ] Check every LLD "Success Criteria" item against the work; confirm new modules near 300 lines and every new `except` names its exception with a comment
- [ ] Set this file's `status` to `complete`
- **Success Criteria**:
  - [ ] `uv run pytest -q && uv run ruff check . && uv run pyright` clean
  - [ ] Final commit on the slice branch, e.g. `docs: mark slice 120 tasks complete`
