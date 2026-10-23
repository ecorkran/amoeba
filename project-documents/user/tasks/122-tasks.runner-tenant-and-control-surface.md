---
docType: tasks
slice: runner-tenant-and-control-surface
project: amoeba
lld: user/slices/122-slice.runner-tenant-and-control-surface.md
dependencies:
- 120
- 121
projectState: Initiative 100 (101–110) is merged, and slices 120 and 121 are merged.
  `poll_run`, `RunOutcomeDocument`, `PollFailure`, `SQ_EXECUTABLE`, `PARAM_RUN_ID`,
  `launch_grace_seconds` and the by-id recovery observer exist (120). Project-scoped
  escalation and the done-terminal rule exist (121). `amoeba start` composes only
  `standard_tenants`. There is no `amoeba.runner` package, recovery adopts every id-bearing
  entry whose run has a state, and `tests/sq_stub.py` has no `run` mode.
dateCreated: 20261023
dateUpdated: 20261023
status: complete
turns: 29
promptTokens: 2323064
cachedTokens: 2214829
cacheWriteTokens: 108183
completionTokens: 32976
durationSeconds: 222.3
costUsd: 0.984363
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

## Context Summary

- Working on the **runner-tenant-and-control-surface** slice (122), the third slice of initiative 120 (Runner and Routing Engine). It builds the Runner's loop with no lifecycle in it: launch, confirm, observe, finish, survive a crash.
- **Current state:** `amoeba start` builds `ResidentProcess(... tenants=standard_tenants(settings, supervisor_dir))` in `cli/lifecycle.py`. `Observation = Adopt | NotApplied | Unknown` lives in `process/recovery.py`. The by-id observer is `process/observers/sq_run_id.py`. `ProcessSettings` is `process/settings.py`. Start flags are `cli/settings_flags.py`. `ExitCode` is in `cli/main.py`. The contract suite's stand-in Runner is `tests/contract/runner_tenant.py` (`ProofRunner`).
- **Dependencies:** 120 (run ids, `poll_run`, by-id observer) and 121 (`raise_project_escalation`, `open_project_escalations`, `close_project_escalation`, done-terminal). Both are merged.
- **What this slice delivers:** `RunnerTenant` and the `amoeba.runner` package; recovery's `InFlight` answer (D3); the three new settings and flags (D10); `UPSTREAM_SHAPE` exit code; the `sq` start probe and per-link `cf` probes (D9); the stub `sq run` mode and a stub `cf`; a `SIGKILL` crash proof; contract text and CHANGELOG. No production code launches anything: the production planner tuple is empty.
- **Next planned slice:** 123 (reconciliation), which adds the first tick-time `cf` reads.

**Branch:** all implementation happens on `122-slice.runner-tenant-and-control-surface`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/122-slice.runner-tenant-and-control-surface.md` at the named decision (D1–D10), "Architecture", or "API Contracts". Keep every new or changed source file near 300 lines and each function near 50.

**Commit cadence:** one commit per task. A commit never holds untested behavior. Run `uv run ruff format .` before each commit. Commit type is `feat:` for new behavior, `refactor:` for the D3 change, `test:` for test-only work, `docs:` for contract text.

**Task-level additions to the LLD:**
- **Package layout.** Create `src/amoeba/runner/` with `__init__.py` exporting only `runner_tenant` and `RunnerTenant`. Tests live in `tests/runner/` (with `__init__.py`, created by Task 5.1).
- **Exception rule.** `amoeba.runner` has exactly one `except Exception` (the per-project catch in `tenant.py`, Task 10.2). Every other `except` names a specific exception with a comment saying why swallowing or handling is correct, or re-raises after `logger.exception`.
- **No magic values.** Every comparison value in the LLD's "Patterns and Conventions" list is defined once and imported. Defaults for the new settings live only in `settings.py`.
- **Test doubles.** The clock, the subprocess runner and `Popen` are injected, so unit tests never sleep and never run the real `sq` or `cf`.

**Section map.** 1 baseline; 2 settings, flags, exit code; 3 recovery `InFlight`; 4 stub `sq` run mode; 5 launch; 6 decide and tick budget; 7 observe; 8 finish; 9 project tick; 10 faults and tenant; 11 probes, factory and `amoeba start`; 12 crash proof; 13 contract text and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Create `122-slice.runner-tenant-and-control-surface` from the target. If it exists, switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each. Record the passed-test count in this task. Note: baseline: 2158 passed
- **Success Criteria**:
  - [x] On the slice branch. Baseline suite, `ruff` and `pyright` are clean. If not, write `BLOCKED:` with the failure and stop. No commit needed

---

## Section 2: Settings, flags, exit code

### Task 2.1: Add the three settings fields
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 1

Per the LLD, D10 table. Edit `process/settings.py`.

- [x] Add `tick_deadline_seconds` (5.0), `tick_call_timeout_seconds` (8.0) and `run_poll_interval_seconds` (15.0) to `ProcessSettings`, with attribute docs
- [x] Reword the `sq_timeout_seconds` doc: it bounds start-up calls, which here includes the `sq` probe. Remove "no tick starts a subprocess"
- [x] Update the `launch_grace_seconds` doc only if it still says the Runner "will" read it
- **Success Criteria**:
  - [x] Defaults appear nowhere outside `settings.py`. `uv run pyright` clean

### Task 2.2: Add the start flags, with tests
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 2

Edit `cli/settings_flags.py`. Follow how an existing float flag (for example `--sq-timeout`) is declared and applied, and extend `tests/test_settings_flags.py` the same way.

- [x] Add `--tick-deadline`, `--tick-call-timeout` and `--run-poll-interval` to `amoeba start`, each overriding the matching field
- [x] Tests: each flag overrides its field; absent flags leave the `ProcessSettings` defaults; a non-numeric value is a usage error as for the existing flags
- **Success Criteria**:
  - [x] New tests pass with the existing flag tests. `--help` lists the three flags. Commit: `feat: add tick deadline, call timeout and run poll settings`

### Task 2.3: Add `UpstreamShapeError` and `ExitCode.UPSTREAM_SHAPE`, with tests
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 2

Edit `process/errors.py` and `cli/main.py`.

- [x] Add `UpstreamShapeError(ProcessError)` next to `StartupFailedError`, with a docstring: an upstream tool lacks a shape the Runner needs. It is exported from `amoeba.process`, because `amoeba.runner` may import only public names; update `__all__` and `EXPECTED_EXPORTS` in `tests/test_process_public_api.py` from 20 to 21 names in this task (Task 3.1 then adds `InFlight`)
- [x] Add `ExitCode.UPSTREAM_SHAPE = 15` (the LLD says 8, but 8 is `NOT_RUNNING_STATUS`; 15 is the next free value) with the condition in its comment. Map `UpstreamShapeError` to it in the boundary handler, as `StartupFailedError` maps to `STARTUP_FAILED`
- [x] Tests, following how the existing exit-code mappings are tested in `tests/test_cli_lifecycle.py`: raising `UpstreamShapeError` from a tenant exits 15 and prints the message; the exit code values are unchanged for all existing members
- **Success Criteria**:
  - [x] Tests pass. Exit code 15 is not used by any other member. Commit: `feat: add UPSTREAM_SHAPE exit code and UpstreamShapeError`

---

## Section 3: Recovery leaves a run in flight (D3)

This is the slice's first behavior change. It lands, with every dependent test, before any Runner code.

### Task 3.1: Recovery leaves an existing run in flight, with tests
**Owner**: Junior AI | **Dependencies**: 2.3 | **Effort**: 4

Edit `process/recovery.py`, `process/observers/sq_run_id.py`, `process/__init__.py`, `tests/test_recovery.py`, `tests/test_observer_sq_run_id.py`, `tests/test_process_public_api.py` and the contract suite. Per the LLD, D3. This is one task and one commit because the observer change breaks the contract suite until its stand-in and oracle are updated.

- [x] Add frozen dataclass `InFlight(run_id: str, outcome: RunOutcome)` and add it to `Observation`. Docstring: the command reached its system and is not finished, so the entry is left unresolved for its issuer
- [x] `reconcile` handles `InFlight` with a `match` case: log at INFO naming the entry, run id and outcome, resolve nothing. Add `in_flight: int` to `RecoverySummary`, include it in `total` and in `describe()`
- [x] Export `InFlight` from `amoeba.process`; update `__all__` and the pinned list in `tests/test_process_public_api.py` (Task 2.3 already added `UpstreamShapeError`, so the pin goes to 22 names)
- [x] By-id observer: in `_classify`, return `InFlight(run_id, outcome)` for every outcome in `STATE_BEARING_OUTCOMES` (completed, failed, paused, timed_out, unknown_status, orphaned). Remove the `Adopt` import and the `RESULT_*` result building if now unused. `NotApplied`, `Unknown` and the claimed-id guard stay. Rewrite the module docstring bullet "Any run state … adopt" to the in-flight rule. The legacy matcher (`SquadronRunsObserver`) keeps adopting
- [x] Contract suite (`tests/contract/runner_tenant.py`, `steps.py`, `end_state.py`, the oracle; run `grep -n "adopted\|ADOPTED" tests/contract/*.py` first): after a restart the stand-in Runner finishes each unresolved id-bearing `sq_run` entry of its project, resolving it `completed` by `issuer` with the run id in the result. The oracle and `check_adopted_review` expect that where they expected `adopted` by recovery for id-bearing entries; rename the check if its name now misleads. Weaken no other assertion
- [x] Tests: in `test_recovery.py`, an observer returning `InFlight` leaves the entry unresolved, the summary counts and names it, and the existing cases are unchanged. In `test_observer_sq_run_id.py`, expect `InFlight` for each state-bearing outcome; a state on the second poll after the grace wait gives `InFlight`; a claimed run id is still `Unknown`; a legacy entry still adopts
- **Success Criteria**:
  - [x] pyright strict accepts the exhaustive `match`. `uv run pytest tests/contract -q`, the recovery, observer and public-API tests, full `uv run pytest -q`, `ruff` and `pyright` are clean. Commit: `refactor: recovery leaves an existing run in flight`

---

## Section 4: Stub `sq` run mode

### Task 4.1: Add `run --run-id` to the stub `sq`, with tests
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 4

Edit `tests/sq_stub.py` (171 lines now; if it passes ~300, move the run mode to `tests/sq_stub_run.py` and import it); tests in new `tests/test_sq_stub_run.py`, running the stub as a subprocess under a temporary runs directory. Read the existing `runs wait` mode and `tests/sq_run_fixtures.py` first: the run mode writes the same per-id state documents. Per the LLD, "Stub `sq` run mode".

- [x] `sq run <pipeline> --run-id <id> -p k=v …`: validate the id against Squadron's rule (restate the pattern in the stub, since the stub is a separate program) and exit 1 if the id already has state; exit 2 on an unknown flag
- [x] Otherwise write the id's document as still running, print exactly `run_id=<id>` to stderr, sleep `SQ_STUB_RUN_SECONDS`, write the final document (`SQ_STUB_RUN_OUTCOME`, default `completed`) and exit 0
- [x] `SQ_STUB_RUN_MODE` selects: `exit_before_line` (exit 1 with no line and no state), `no_line` (create the state but never print the line), `late_line` (sleep, then create the state and print the line), `usage_error` (exit 2, no state)
- [x] Append every invocation (argv) to the file named by `SQ_STUB_LOG`
- [x] Tests, one per behavior above: normal run writes running then completed; duplicate id exits 1; unknown flag exits 2; each `SQ_STUB_RUN_MODE`; the log records each call
- **Success Criteria**:
  - [x] Existing stub users still pass. New tests pass in a few seconds at most (short `SQ_STUB_RUN_SECONDS`). Commit: `test: add detached run mode to the stub sq`

---

## Section 5: Launch

### Task 5.1: Create the package and run-id minting, with tests
**Owner**: Junior AI | **Dependencies**: 4.1 | **Effort**: 2

Create `tests/runner/__init__.py`, `src/amoeba/runner/__init__.py` (empty exports for now), `runner/faults.py` and `runner/launch.py`; tests `tests/runner/test_launch_ids.py`. Per the LLD, D5 and D8.

- [x] `faults.py` holds the shared vocabulary so later tasks import it: `FaultKind` `StrEnum` (`run_observation_failed`, `launch_overdue`, `cf_probe_failed`, `unexpected_fault`), `LaunchFailure` `StrEnum` (`spawn_error`, `exited_before_line`, `usage_error`) and the `STORE_FAILURES` tuple (`StoreBusyError`, `StoreCorruptError`, `StorePermissionError`, `StoreSchemaError`, `sqlite3.Error`). Escalation writes are added in Task 10.1
- [x] `SQUADRON_RUN_ID_PATTERN` defined once in `launch.py`
- [x] `mint_run_id(now: datetime) -> str` returns `amoeba-<UTC yyyymmddTHHMMSSZ>-<12 hex of uuid4>`. It asserts nothing at runtime
- [x] Tests: a fixed `now` gives the expected prefix and 36 characters (`amoeba-` 7 + timestamp 16 + `-` 1 + hex 12); a property-style loop of many mints all match the pattern and are unique; a non-UTC aware `now` is converted to UTC
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: add runner package and run-id minting`

### Task 5.2: Launch log paths, exact-line check and tail, with tests
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 3

Edit `runner/launch.py` (or add `runner/launch_logs.py` if it nears 300 lines). Per the LLD, D4 and D6.

- [x] Constants defined once: `launch-logs` directory name, `.stdout.log`/`.stderr.log` suffixes, the `run_id=` line prefix (share 120's constant if one exists; `grep -rn "run_id=" src/amoeba`), the 64 KiB head limit and 4 KiB tail limit
- [x] `log_paths(supervisor_dir, entry_id)` names logs by entry id
- [x] `stderr_confirms(path, run_id) -> bool`: reads at most the head limit, true only when a whole line equals `run_id=<id>` after removing only the line terminator. Lets `OSError` propagate to the caller
- [x] `stderr_tail(path) -> str`: the last 4 KiB, decoded with replacement, empty string for an empty file; `OSError` propagates
- [x] Tests: exact line confirms; the id inside another line does not; `run_id=<id>x` and a different id do not; `\r\n` terminator confirms; a line past 64 KiB is not seen; tail is bounded; a missing file raises `OSError`
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: add launch log paths and confirmation line check`

### Task 5.3: The detached launch, with tests
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 3

Edit `runner/launch.py`; tests `tests/runner/test_launch.py`. Per the LLD, D2 (parameters), D4 and the `LaunchTracker` note in State Management. `PARAM_CHECKOUT` joins `PARAM_RUN_ID` in `store/journal_models.py` only if that module is where `PARAM_RUN_ID` lives; otherwise define it once beside the other launch constants.

- [x] `build_argv(pipeline, run_id, params)`: `[SQ_EXECUTABLE, "run", pipeline, "--run-id", run_id, "-p", "k=v", …]`. Raises `ValueError` for a value containing `,`, or a key containing `,` or `=` (called before journaling)
- [x] `launch(entry, supervisor_dir, popen)` opens both logs for exclusive creation, calls the injected `Popen` with `cwd=checkout`, `stdin=DEVNULL`, the two files, `start_new_session=True`, `close_fds=True`, the inherited environment, then closes the parent's handles. Returns the child handle or a `LaunchFailure.SPAWN_ERROR` answer on `OSError` from either log open or `Popen` (`FileExistsError` included). The environment is never logged
- [x] Import `LaunchFailure` from `runner/faults.py` (defined in Task 5.1); do not redefine it
- [x] `LaunchTracker`: keeps the handle and confirmation flag per entry id; `reap()` calls `poll()` on each handle and drops exited, settled ones
- [x] Tests with a fake `Popen` recording its kwargs: exact argv and flags; params with `,`/`=` rejected; log open failure and `Popen` `OSError` each give `spawn_error` and no `Popen` call after a log failure; an existing log file gives `spawn_error`; `reap` drops exited settled handles and keeps live ones
- **Success Criteria**:
  - [x] Tests pass. One integration test launches the stub `sq` for real under `tmp_path`, reaps it and finds `run_id=<id>` in the stderr log. Commit: `feat: add detached launch and launch tracker`

Deviation: SQ_EXECUTABLE (amoeba.process) and PARAM_RUN_ID/PARAM_CHECKOUT (amoeba.store) were not public; exported them and updated both public-API pins (process now 23 names; store +2). launch() returns LaunchError(failure, detail) rather than a bare LaunchFailure so the error text reaches the escalation.

---

## Section 6: Decide and the tick budget

### Task 6.1: `decide.py` and `TickBudget`, with tests
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

Create `runner/decide.py` and `runner/tick.py` (holding `TickBudget` for now); tests `tests/runner/test_decide.py` and `tests/runner/test_budget.py`. Per the LLD, D1, D10 and API Contracts.

- [x] `RunState` `StrEnum` (launching, running, finished, fault). Frozen dataclasses `InFlightRun(entry, run_id, state)`, `LaunchRun(node_id, pipeline, params, checkout)`, and `ProjectView(project_id, now, runnable_nodes, in_flight, link_probes)`. `type Action = LaunchRun`
- [x] `Planner` Protocol with `plan(view) -> Sequence[Action]`
- [x] `decide(view, planners)` runs planners in order. Two actions for one node raise `ValueError` naming the node; it never drops one silently. Pure: no I/O, no clock read
- [x] Tests: empty planner tuple gives no actions; two planners concatenate in order; a duplicate node raises `ValueError`; `decide` is deterministic for the same view; `ProjectView` is immutable
- [x] `TickBudget(deadline, host, clock)` made from a monotonic clock. `allows_call()` is false once the deadline passed or `host.stop_requested` is set. Provide a result `StrEnum` `TickResult` with `COMPLETE` and `CUT_OFF`
- [x] Budget tests with an injected clock and a fake host: allowed before the deadline; refused at and after it; refused after a stop request even before the deadline
- **Success Criteria**:
  - [x] Tests pass. Commit: `feat: add runner decide stage, planner seam and tick budget`

Deviation: TickBudget and TickResult live in runner/budget.py (not tick.py), because tick.py (ProjectTick) imports observe.py, which needs the budget.

---

## Section 7: Observe

### Task 7.1: Observation of one in-flight run, with tests
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 5

Create `runner/observe.py`; tests `tests/runner/test_observe.py` (split into `test_observe_launch.py` and `test_observe_poll.py` if past ~300 lines). Per the LLD, "A launch, end to end" and D6, D10. Inject the clock, `poll_run`, the tracker and the budget.

- [x] Confirmed run: poll only when `run_poll_interval_seconds` has passed since its last poll (in-memory last-poll times) and the budget allows a call. Classify: `timed_out` → running; `completed`/`failed`/`paused`/`orphaned` → finished; `not_found` after confirmation → finished (vanished); `unreadable`, `unknown_status` or `PollFailure` → fault (project-scoped `run_observation_failed`, polling continues)
- [x] Unconfirmed launch (tracked handle): confirmed by the exact stderr line or by a poll with any outcome other than `not_found`. Not polled on the interval; polled once when the child exits without the line and once when the grace period passes
- [x] Overdue (grace passed, no line, one poll finds no state, child alive): entry stays unresolved, `launch_overdue` recorded for the project, then polled on the run interval with the line still checked; the child is never killed
- [x] Child exited without the line and one poll finds no state: launch failed (`exited_before_line`, with exit code and stderr tail). If that poll finds a state, the run is observed instead. Exit code 2 with no state is `usage_error` and marks the tick for `UpstreamShapeError`
- [x] Unreadable stderr log: answer "no line" for this tick, record `run_observation_failed` naming the entry and error, let the run state decide; the tail in a failure is replaced by the error
- [x] Entries with no tracked handle (left by a crash) are treated as confirmed and only polled
- [x] Runs are observed least-recently-polled first
- **Success Criteria**:
  - [x] One test per rule above, each named for its rule, all passing with no sleeping. Poll count assertions: a confirmed run is polled at most once per call and not before the interval. Commit: `feat: add in-flight run observation`

Note: Fault, TickFaults and NodeContext were added to runner/faults.py here (observe needs them); a standing poll fault is replayed between polls so its escalation does not close and reopen. observe.py is 341 lines.

---

## Section 8: Finish

### Task 8.1: Record a finished run, with tests
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 3

Create `runner/finish.py`; tests `tests/runner/test_finish.py`. Per the LLD, D2 and D6. The body is minimal; 125 replaces it.

- [x] `record(store, entry, finished)`: `completed` → `journal_resolve(completed, result={run_id, outcome, status})`. `failed`/`paused` → block the node on `HUMAN` first, then resolve `completed` with `failure` or `checkpoint` added to the result as reported. `orphaned` or vanished → block on `HUMAN`, resolve `failed`. A failed launch → block on `HUMAN` with the `LaunchFailure` reason, exit code and tail, resolve `failed` with `result={run_id, launch_failure}`
- [x] Order is always block, then resolve. A node already blocked is not blocked again, so re-entry after a crash between the two writes finishes the sequence and leaves one blocked state
- **Success Criteria**:
  - [x] Tests against a real temporary store cover each outcome's entry result, the node's blocked state, and re-entry after a simulated crash between block and resolve (one blocked state, entry resolved). Commit: `feat: add minimal finished-run recording`

Note: the outcome document has no failure field, so a failed run records outcome and status only; paused records checkpoint.paused_at. BlockedState exposes no payload, so tests assert on context.

---

## Section 9: The project tick

### Task 9.1: Act and the project tick, with tests
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 5

Complete `runner/tick.py`; tests `tests/runner/test_tick.py`. Per the LLD, "One project's tick", D1, D5, D10.

- [x] `ProjectTick(...).run(budget) -> TickResult`: observe → record finished → decide → act → close. Slots for 123/124/126 are comments only
- [x] Act: for each `LaunchRun`, while the budget allows, mint the run id, `journal_issue(sq_run, {pipeline, params, run_id, checkout})`, then launch. A failed launch is recorded through `finish.record`. Nothing else is issued
- [x] `ProjectView` is built from `runnable`, excluding any node with an unresolved entry, plus the in-flight runs
- [x] Close: only on a `COMPLETE` tick, close each open project escalation whose kind did not recur this tick, `closed_by="runner"`. A tick that was cut off closes nothing
- [x] The tick sets the current node before each node-scoped step (read by the catch in Task 10.2)
- **Success Criteria**:
  - [x] Tests with a test planner and a fake `Popen`: journal entry exists before the launch call; a node with an unresolved entry is not offered to Decide; `COMPLETE` closes a non-recurring escalation; `CUT_OFF` closes nothing; the budget is checked before `Popen` and before every poll. Commit: `feat: add runner project tick`

Note: expected faults are raised by faults.raise_expected_faults (Task 10.1 adds the exception escalation path). ProjectTick, not the tenant, raises UpstreamShapeError after recording the failed launch; the tenant re-raises it (Task 10.2).

---

## Section 10: Faults and the tenant

### Task 10.1: Fault vocabulary and escalation writes, with tests
**Owner**: Junior AI | **Dependencies**: 9.1 | **Effort**: 3

Extend `runner/faults.py` (created in Task 5.1); tests `tests/runner/test_faults.py`. Per the LLD, D8.

- [x] Import `FaultKind` and `STORE_FAILURES` from `runner/faults.py` (Task 5.1)
- [x] A tick fault set that collects expected faults. `escalate(store, project_id, node_context, fault_kind, error)`: a node in context with no run in flight and not done blocks on `HUMAN` with payload `{fault_kind, error}` (nothing more if already blocked); otherwise raise a project-scoped escalation with node and run ids in the payload
- **Success Criteria**:
  - [x] Tests on a real store: node block; already-blocked node writes nothing; in-flight node, done node and no node each take the project path; a repeated fault adds no rows. Commit: `feat: add runner fault vocabulary and escalation`

Note: raise_expected_faults and TickFaults were added earlier (Tasks 7.1/9.1); this task added escalate() and NodeContext use.

### Task 10.2: `RunnerTenant` and the one catch, with tests
**Owner**: Junior AI | **Dependencies**: 10.1 | **Effort**: 4

Create `runner/tenant.py`; tests `tests/runner/test_tenant.py`. Per the LLD, D8 and "One tick".

- [x] `RunnerTenant(name="runner", planners, ...)` implements the `Tenant` protocol. `tick(host)`: build the `TickBudget`, order carried-over projects first then the rest of `host.project_ids` (read every tick), run each `ProjectTick`, carry over `CUT_OFF` projects and stop when the budget is spent. Returns true only if something was written or issued
- [x] The single `except Exception` around each project tick: re-raise `STORE_FAILURES` and `UpstreamShapeError` first; log everything else with `logger.exception` and escalate via Task 10.1. An escalation write that fails is not caught again
- [x] A launch child that exited 2 with no run state: the entry is already finished as failed by Task 8.1; the tenant then raises `UpstreamShapeError` naming `sq run … --run-id`
- **Success Criteria**:
  - [x] Tests: an unexpected exception in project A is logged at ERROR and project B still ticks the same call; a store failure and `UpstreamShapeError` propagate; a cut-off project goes first next tick and its runs are polled first; a tick that only polled a running run returns false; `grep -c "except Exception" src/amoeba/runner` is 1. Commit: `feat: add RunnerTenant with per-project fault isolation`

Note: the tenant takes cf_run (subprocess.run) for the link probes; project ticks that raise return COMPLETE and are not carried over.

---

## Section 11: Probes, factory and `amoeba start`

### Task 11.1: The `sq` start probe and `cf` link probes, with a stub `cf`
**Owner**: Junior AI | **Dependencies**: 10.2 | **Effort**: 4

Create `runner/probes.py`, a stub `cf` (follow the stub `sq` pattern; put it in `tests/cf_stub.py`), and `tests/runner/test_probes.py`. Per the LLD, D9. Run `cf status --help` and `cf list initiatives --help` once to confirm both take `-p` (observed on CF 0.19.16).

- [x] `probe_sq(settings, now)`: `poll_run(<freshly minted id>, timeout_seconds=sq_timeout_seconds)` must give outcome `not_found` and the same `run_id`; anything else raises `StartupFailedError` naming `sq runs wait <id> --timeout 0 --json` and the answer
- [x] `CF_EXECUTABLE` and the two commands defined once. `probe_link(cf_project_id, run, budget)`: each command is a separate call, checks `TickBudget` first, uses `stdin=DEVNULL`, captured output, `timeout=tick_call_timeout_seconds`, `check=False`. Status output must be a JSON object, initiatives a JSON array; the two top-level checks are private functions. `TimeoutExpired`, non-zero exit or the wrong shape is a failure naming command, exit code and output head
- [x] A link is probed once per lifetime on first observation of its project; a failure marks the link failed for the lifetime and counts as a recurrence of `cf_probe_failed` on every later tick (deduplicated raise). A probe cut off partway records nothing and restarts from its first command
- [x] Wire the probe into the project tick's observe step
- **Success Criteria**:
  - [x] Tests: good stub passes; empty output, a wrong top-level form and a timeout each fail; a failed link raises one escalation and other projects continue; a cut-off probe starts no call after the deadline; a failed link keeps its escalation open until a later lifetime's complete tick passes. Commit: `feat: add sq start probe and cf link probes`

Note: confirmed on CF 0.19.17 that cf status and cf list initiatives both take -p. Probe wired into ProjectTick via LinkProbes; the tick-level link tests are in tests/runner/test_probes.py.

### Task 11.2: `runner_tenant()` factory with bounds check, with tests
**Owner**: Junior AI | **Dependencies**: 11.1 | **Effort**: 3

Create `runner/factory.py`; export `runner_tenant` and `RunnerTenant` from `runner/__init__.py`; tests `tests/runner/test_factory.py`. Per the LLD, D9, D10, API Contracts.

- [x] `runner_tenant(settings, supervisor_dir, *, planners=None)`: validate every new setting is positive and `tick_call_timeout_seconds < shutdown_grace_seconds`, else `StartupFailedError` naming the field; create `<supervisor>/launch-logs/`; run the `sq` probe; build the tenant with `subprocess.run` and `subprocess.Popen`. `planners=None` selects the production tuple, which is empty; a passed value is used as given
- **Success Criteria**:
  - [x] Tests: each bound violation fails with the field named; the probe failure surfaces as `StartupFailedError`; `launch-logs/` exists after build; production tuple is empty. Commit: `feat: add runner_tenant factory with start-up validation`

### Task 11.3: Compose the Runner in `amoeba start`, with boundary tests
**Owner**: Junior AI | **Dependencies**: 11.2 | **Effort**: 2

Edit `cli/lifecycle.py`; tests in `tests/test_cli_lifecycle.py`, `tests/test_import_boundaries.py`.

- [x] Compose `(*standard_tenants(settings, supervisor_dir), runner_tenant(settings, supervisor_dir))`
- [x] Fix the now-false statements that no tick starts a subprocess: the `standard_tenants` docstring in `process/tenants.py` and the module docstring in `process/cf_watch.py`. Say instead that those tenants start none; the Runner does, under `TickBudget`
- [x] Import-boundary test: only `amoeba.cli` imports `amoeba.runner`, and `amoeba.runner` imports `amoeba.store`, `amoeba.process`, `amoeba.upstream` only through public names
- [x] Author `tests/runner/test_budget_coverage.py` (LLD Technical Requirements): it injects a subprocess runner and `Popen` that fail the test when called after the budget is spent, drives a tick through observe, act and the `cf` probes with the budget exhausted, and asserts no call was made
- [x] Tests: `start` with a failing `sq` probe exits `STARTUP_FAILED` (7) naming the shape; `tests/test_writer_guard.py` passes unchanged
- **Success Criteria**:
  - [x] Full `uv run pytest -q` clean (run once). Commit: `feat: compose the Runner tenant in amoeba start`

Note: tests/cli_harness.cli_environment now puts the stub sq first on PATH (the start probe would otherwise run the real sq), and the detection e2e harness fake sq answers runs wait with not_found. Boundary rules 10 and 11 added to tests/test_import_boundaries.py. Full suite: 2359 passed.

---

## Section 12: Crash proof

### Task 12.1: Proof entry point and harness
**Owner**: Junior AI | **Dependencies**: 11.3 | **Effort**: 4

Create `tests/runner/crash_entry.py` and `tests/runner/crash_harness.py`. Read `tests/contract/launched.py` and `tests/contract/harness.py` first and follow their pattern for starting the resident process as a subprocess.

- [x] The entry point composes `(*standard_tenants(...), runner_tenant(..., planners=(proof_planner,)))`. The proof planner launches the stub's no-op pipeline once for each test node with no journal entry; the test names nodes by the ids it created, never by title
- [x] Kill points reachable by environment variable or marker file: after journaling and before launch; while the run runs; after the run finished and before it is recorded; between a node block and the resolve
- [x] The harness starts the process, waits for a named point, sends `SIGKILL`, restarts, waits for quiescence, and reads the stub's `SQ_STUB_LOG` to count `sq run` calls per run id
- **Success Criteria**:
  - [x] The harness runs a no-kill scenario end to end under `tmp_path`, using the stub `sq` first on `PATH` and a temporary `HOME`. Commit: `test: add crash proof harness for the runner`

Note: the entry builds RunnerTenant directly (not via runner_tenant()) so it can hook Popen, poll and Store.journal_resolve; it still runs probe_sq. Kill points are armed by PROOF_KILL_AT.

### Task 12.2: One test per kill point
**Owner**: Junior AI | **Dependencies**: 12.1 | **Effort**: 4

Create `tests/runner/test_crash_recovery.py`. Each test asserts the entry's final outcome, its result, the node's blocked state, and the `sq run` count for the id. Per the LLD, Verification Walkthrough step 2.

- [x] `test_kill_before_launch_is_not_applied_and_not_relaunched`: entry `not_applied`, zero `sq run` calls for the id, no relaunch
- [x] `test_kill_while_running_is_recorded_after_restart`: left in flight by recovery, then recorded `completed`; one call
- [x] `test_kill_after_finish_before_record_is_recorded_on_first_tick`: same, with the run already completed while down; one call
- [x] `test_kill_between_block_and_resolve_finishes_the_sequence`: use a `failed` run outcome; the node has one blocked state and the entry is resolved
- **Success Criteria**:
  - [x] All four pass, repeated three times without flakiness (no fixed sleeps; wait on conditions). Commit: `test: add runner crash recovery proof`

Note: all four pass, repeated three times (8.3-8.8 s per run), no fixed sleeps beyond the 0.05 s polling interval.

### Task 12.3: End-to-end launch and fault scenarios
**Owner**: Junior AI | **Dependencies**: 12.2 | **Effort**: 3

Create `tests/runner/test_end_to_end.py` using the stub `sq` and a real store in-process (no kill).

- [x] Normal path: journaled, launched detached, confirmed by its `run_id=` line, polled to `completed`, recorded with `run_id`, `outcome`, `status`
- [x] `exit_before_line`: entry `failed`, node blocked with reason and log tail. `no_line` with a live child: one `launch_overdue` escalation, entry unresolved; `late_line`: confirmed, recorded, escalation closed. `usage_error`: node blocked, entry `failed`, process path raises `UpstreamShapeError` (exit 15 when run through `amoeba start`)
- **Success Criteria**:
  - [x] All pass with no fixed sleeps. Commit: `test: add runner end-to-end launch scenarios`

Deviation: stub no_line creates the run state (per Task 4.1), so the poll confirms the launch and it is never overdue; the overdue path is covered with late_line (delay longer than the grace period). A real amoeba start cannot reach exit 15 because the production planner tuple is empty; the last test drives the same UpstreamShapeError through the CLI boundary handler.

---

## Section 13: Contract text and final validation

### Task 13.1: Contract text, plan edits, CHANGELOG and final validation
**Owner**: Junior AI | **Dependencies**: 12.3 | **Effort**: 3

Per the LLD, "Contract documents". Edit the docs, keeping their front matter. Follow each document's existing heading structure.

- [ ] `process-contract.md`: four tenants in `amoeba start`; the tenant obligation's tick-time subprocess rule (a deadline and stop check before every call, bounded by `tick_call_timeout_seconds`), replacing "no tick starts a subprocess"; also reword the same sentence in `docs/context-forge-contract.md` (line ~189) and `docs/process-contract.md` (line ~216), which describe the version-label capture and stay true only for those tenants; the recovery property "An id-bearing `sq_run` entry whose run exists is left unresolved, in flight, for its issuer to finish" and the `InFlight` answer; the supervisor directory table gains `launch-logs/`; the three start flags and settings; exit code 15 and `STARTUP_FAILED`'s new cases; a note that a block payload must not hold secrets; hosting surface 22 names
- [ ] `substrate-guide.md`: update the 120 row for the in-flight change and add the 122 row
- [ ] In `user/architecture/120-slices.runner-routing-engine.md`, change the launch sentence that fails a launch at grace expiry to the overdue rule (LLD D6). In the slice plan's entry for slice 122, change the grace criterion the same way and change "polled once per tick" to "polled at most once per tick and no more often than the run poll interval" (D10). Locate both with `grep -n "grace\|once per tick" <file>`
- [ ] Add a CHANGELOG entry under the unreleased heading: the Runner tenant and `sq_run` control surface, the three new flags, exit code 15, and the recovery change for id-bearing entries
- [ ] Run once each: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, and `uv run pytest tests/contract -v`. Fix any failure at its cause
- [ ] Verify "123 and 125 can add their reads and planner without changing `tenant.py` or `launch.py`": `grep -n "Planner\|cf_probe\|dispatch" src/amoeba/runner/tenant.py src/amoeba/runner/launch.py` finds no reference to a concrete planner; the end-to-end and crash tests inject their planner only through `planners=`
- [ ] Verify the technical requirements: exactly one `except Exception` in `src/amoeba/runner`; no module over ~300 lines (`wc -l src/amoeba/runner/*.py`); public API pins 22 names; `tests/runner/test_budget_coverage.py` exists and fails if a call starts after the budget is spent
- [ ] Walkthrough steps 1–3 and 5 of the LLD (automated tests and the refused start with a fake `sq` that exits 2, expecting exit 7). Run step 4 against the real `sq` and `cf` in a throwaway supervisor directory (`AMOEBA_STORE_DIR=$(mktemp -d)`): read-only, no run is launched. Record the observed output in the DEVLOG entry convention used by earlier slices
- **Success Criteria**:
  - [ ] Contract text, plan and architecture edits are present, no other text in those documents changed, all gates are clean, and the walkthrough output matches the LLD's expected results. The last task ends at a commit (`docs: update process contract and record slice 122 plan changes`); no merge happens here
