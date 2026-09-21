---
docType: tasks
slice: resident-process-and-recovery
project: amoeba
lld: user/slices/102-slice.resident-process-and-recovery.md
dependencies: [101]
projectState: Continuation of 102-tasks.resident-process-and-recovery-1.md. Sections 1-4 (journal, read-only open, recovery protocol, both observers) are complete when this file begins.
dateCreated: 20260919
dateUpdated: 20260921
status: not_started
---

## Context Summary

- Working on the **resident-process-and-recovery** slice (102). This is **part 2 of 2**; see `102-tasks.resident-process-and-recovery-1.md` for the slice context, key design commitments, and Sections 1–4.
- **Entry state for this file:** the command journal exists in the store at schema version 3, `Store.open_read_only` exists, the recovery protocol reconciles unresolved entries against an observer registry, and both observers (Squadron runs, CF read-back) are implemented and tested against real fixtures. Nothing runs as a process yet and there is no CLI.
- **What remains:** single-instance enforcement, the host loop and `Tenant` seam, the `amoeba` CLI (lifecycle plus inspection), the sole-writer guard test, the `tests/load/` tier, and the contract documentation.
- **Next planned slice:** 103 (Durable Inbox and Message Queue), which plugs its apply loop into the `Tenant` seam built here.

**Reading note for the executing developer:** where a task says "per the LLD," open `user/slices/102-slice.resident-process-and-recovery.md` at the named section and follow it. Nothing about locking or signal handling is mocked in tests — that is a design requirement, not a preference.

---

## Section 5: Instance Lock and PID File

### Task 5.1: Implement InstanceLock and the PID file
**Owner**: Junior AI
**Dependencies**: Section 4 complete
**Effort**: 3
**Objective**: Create `src/amoeba/process/instance_lock.py` — an advisory `fcntl.flock` on `{store_dir}/amoeba.lock` plus an informational JSON PID file.

**Steps**:
- [ ] Implement `InstanceLock` acquiring a non-blocking `fcntl.flock` on `{store_dir}/amoeba.lock`, resolving the directory through `amoeba.store.paths`
- [ ] Expose acquire (failing cleanly when already held), release, and a held-by-another-process test that `stop` and `status` use
- [ ] Write `amoeba.pid` as JSON with pid, started-at, and version — **informational only**; nothing trusts it without testing the lock
- [ ] Fail at import on a platform without `fcntl`, with an explicit error — **no degraded mode**, per the LLD's exclusion of Windows
- [ ] Never delete a lock file to recover; a stale lock cannot exist because the kernel releases it on any death

**Success Criteria**:
- [ ] Acquire fails cleanly, not by raising an unhandled `OSError`, when another process holds the lock
- [ ] The PID file is never consulted to decide liveness
- [ ] An unsupported platform fails loudly at import
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/process/instance_lock.py`

---

### Task 5.2: Test the lock with real processes
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Validate locking against real OS behavior. Mocks cannot validate `flock`, per the LLD's third risk.

**Steps**:
- [ ] Test a second acquire from a **real subprocess** fails while the first holds it
- [ ] Test `kill -9` of the holder releases the lock immediately, with no cleanup — the central crash-only claim
- [ ] Test the lock is released on normal exit
- [ ] Test a stale PID file with a free lock is recognized as stale
- [ ] Test the lock is held but the PID file is **absent or corrupt** — the state Task 6.4 and Task 7.2 must handle
- [ ] Mock nothing about locking or signals anywhere in this file

**Success Criteria**:
- [ ] All five behaviors asserted with real processes
- [ ] No mock or patch of `fcntl`, `os.kill`, or `subprocess` in this file
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add single-instance lock and pid file`

**Files to Create**: `tests/test_instance_lock.py`

---

## Section 6: The Host Loop

### Task 6.1: Implement the Tenant protocol and ResidentProcess lifetime
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 3
**Objective**: Create `src/amoeba/process/host.py` with the two-member `Tenant` protocol and the process lifetime the LLD specifies.

**Steps**:
- [ ] Define `Tenant` as exactly two members: `name: str` and `tick(host) -> bool` returning whether work was done
- [ ] Implement `ResidentProcess` with the lifetime in the LLD's Component Structure: acquire lock → write PID file → open stores → recover → tick tenants until stop → close stores → remove PID file → release lock
- [ ] Expose `store_for(project_id)` and the `stop_requested` flag
- [ ] Tick tenants in registration order; when no tenant worked, wait on the stop event for `idle_interval_seconds` — do **not** busy-loop
- [ ] Ship **no tenants**: with zero registered, the process is a correct idle recoverable host, which is this slice's end state
- [ ] `host.py` is the **only** module permitted to call read-write `Store.open` (Task 8.1 enforces this)

**Success Criteria**:
- [ ] Zero tenants yields a process that starts, recovers, idles, and stops cleanly
- [ ] The idle path waits on the event, so stop is observed promptly rather than after a full interval
- [ ] `uv run pyright` clean; file stays near the 300-line budget

**Files to Create**: `src/amoeba/process/host.py`

---

### Task 6.2: Wire recovery into startup as a gate
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: Make recovery gate the loop — tenants must not tick until every project is reconciled, per the LLD.

**Steps**:
- [ ] Run recovery for **every** project store before the first tick, with the observer registry assembled from both observers
- [ ] Log a per-project recovery summary line before entering the loop
- [ ] An unexpected recovery failure **aborts startup**; the process does not enter the loop against unreconciled state
- [ ] A `StoreError` from any project aborts the start by propagating (or re-raising as a typed lifecycle error carrying the store's own message) — the process never skips a project or falls back to another store, per the LLD's Consumes from Other Slices. This module does **not** define or import `ExitCode`; mapping the failure to an exit code is Task 7.1/7.2's job at the process boundary

**Success Criteria**:
- [ ] No tenant ticks before all projects are reconciled
- [ ] A corrupt store for one project stops the whole supervisor, deliberately, by raising out of `host.py`
- [ ] The summary line appears for each project, including "nothing to reconcile"

**Files to Modify**: `src/amoeba/process/host.py`

---

### Task 6.3: Implement signal handling and graceful shutdown
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 3
**Objective**: Handle `SIGTERM`/`SIGINT` through a `threading.Event`, with the bounded grace period the LLD's lifecycle failure modes specify.

**Steps**:
- [ ] Set the stop `threading.Event` from the signal handler — the single piece of state published across an execution boundary
- [ ] Stop ticking new work as soon as the event is set; the grace period bounds only the **current** tick
- [ ] On grace expiry: log at ERROR **naming the tenant that did not return**, close stores, and raise a typed `GraceExpiredError` (or return a distinct lifecycle result the CLI maps to `ExitCode.GRACE_EXPIRED` in Task 7.2) without waiting further — abandoning a mid-tick tenant in place rather than interrupting it. This module does **not** define or import `ExitCode`
- [ ] Implement **no** per-tick timeout and no watchdog — that is a decision in the LLD, not an omission
- [ ] Ensure stores close, the PID file is removed, and the lock releases on the normal path

**Success Criteria**:
- [ ] `SIGTERM` during idle exits promptly and cleanly
- [ ] Grace expiry signals the lifecycle-error condition the CLI maps to `ExitCode.GRACE_EXPIRED`, with an ERROR log naming the tenant
- [ ] No timeout, watchdog, or thread-kill mechanism is introduced
- [ ] The abandoned-tick path leaves state recoverable by the next start

**Files to Modify**: `src/amoeba/process/host.py`

---

### Task 6.4: Test the host loop with real signals and a throwaway tenant
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 3
**Objective**: Prove the seam slices 103 and 120 will build on, using real subprocesses and real signals.

**Steps**:
- [ ] Define a throwaway `Tenant` in the test that is ticked by the real host, writes through `store_for()`, and observes `stop_requested` — the LLD's Integration Requirement
- [ ] Assert the process exits cleanly afterward and its writes are durable
- [ ] Test `SIGTERM` during an idle wait stops promptly
- [ ] Test a tenant that **ignores** `stop_requested` triggers grace expiry — asserted here as the host's own signal (raised error or lifecycle result, not an `ExitCode`) — and the ERROR log naming it; Task 7.3 separately proves this surfaces as `ExitCode.GRACE_EXPIRED` through the CLI
- [ ] Test zero tenants: start, recover, idle, stop
- [ ] Test recovery gating — a tenant that records its first tick time never ticks before recovery completes
- [ ] Send real signals to real subprocesses; mock nothing

**Success Criteria**:
- [ ] All six behaviors asserted without mocks
- [ ] The hanging-tenant test asserts the process still exits rather than hanging the suite
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add resident host loop and tenant seam`

**Files to Create**: `tests/test_host.py`

---

## Section 7: The CLI

### Task 7.1: Implement the CLI skeleton, ExitCode, and the process boundary
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 2
**Objective**: Create `src/amoeba/cli/main.py` — argparse dispatch and the single documented process-boundary handler.

**Steps**:
- [ ] Create `src/amoeba/cli/` with `__init__.py` and `main.py` using `argparse` (D3 — no CLI dependency)
- [ ] Define the `ExitCode` enum with every status the LLD names plus the two the host layer's typed errors require: `ALREADY_RUNNING`, `NOT_RUNNING`, `STOP_TIMEOUT`, `NO_STOP_TARGET`, `GRACE_EXPIRED`, and a `STARTUP_FAILED` (or equivalent) member for the `StoreError`-during-recovery abort Task 6.2 raises — and use **no bare integers** at call sites
- [ ] Register the `amoeba` console script in `pyproject.toml`
- [ ] Implement the **one** process-boundary handler mapping `StoreError` and the host layer's typed lifecycle errors (from Tasks 6.2/6.3 — `host.py` itself never imports or references `ExitCode`) to exit codes, documented as such per the project exception rule

**Note:** `ExitCode` is defined here, in Section 7, which starts after Section 6 (the host loop) completes. Sections 6's tasks raise typed errors or return lifecycle results; they do not reference `ExitCode` members directly — only this task's boundary handler and Task 7.2 do.
- [ ] Expose `ProcessSettings` tunables as CLI flags (including `--sq-runs-dir`), adding no environment variables

**Success Criteria**:
- [ ] `uv run amoeba --help` works after `uv sync`
- [ ] No exit-code integer literal outside the enum
- [ ] The boundary handler is the only broad exception handler in the package and is commented as the process boundary
- [ ] `grep` for `ExitCode` under `src/amoeba/process/` finds nothing — only `cli/` references it

**Files to Create**: `src/amoeba/cli/__init__.py`, `src/amoeba/cli/main.py`
**Files to Modify**: `pyproject.toml`

---

### Task 7.2: Implement start, stop, and status
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 3
**Objective**: Implement `src/amoeba/cli/lifecycle.py` per the LLD's CLI table and its enumerated lifecycle failure modes.

**Steps**:
- [ ] `start` — foreground, logging to stderr (D1, no daemonizing); refuse with `ALREADY_RUNNING` when the lock is held; log the recovery summary per project before the loop
- [ ] `stop` — confirm the lock is held, send `SIGTERM` to the recorded PID, wait for release; `NOT_RUNNING` when nothing holds it; `STOP_TIMEOUT` when the wait expires; **never** escalate to `SIGKILL`
- [ ] `stop` with the lock held but the PID file absent or unreadable → `NO_STOP_TARGET` naming the lock path, signalling **nothing**
- [ ] `status` — `running` (pid, start time), `stopped`, `stopped (stale pid file)`, and `running (pid unknown)` for the lock-held-no-pid case; exit status distinguishes running from not
- [ ] Verify the lock before signalling so a **reused PID is never signalled**

**Success Criteria**:
- [ ] All four `status` states reachable and distinct
- [ ] `stop` never signals a PID it has not confirmed via the lock
- [ ] No `SIGKILL` anywhere in the lifecycle code
- [ ] Functions stay near the 50-line budget

**Files to Create**: `src/amoeba/cli/lifecycle.py`

---

### Task 7.3: Test lifecycle commands as real subprocesses
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 3
**Objective**: Drive the real CLI against a `tmp_path` supervisor directory, per the LLD's Technical Requirements.

**Steps**:
- [ ] Add test infrastructure invoking the real `amoeba` CLI as a subprocess with `AMOEBA_STORE_DIR` pointed at `tmp_path`
- [ ] Assert **no test touches** `~/.config/amoeba` or the real Squadron runs directory
- [ ] Test the full cycle: `start` → `status` running with pid → `stop` → `status` stopped
- [ ] Test a second `start` exits `ALREADY_RUNNING` and **does not disturb the first**
- [ ] Test `kill -9` then `start` succeeds immediately with no manual cleanup, and `status` between reports the stale pid file
- [ ] Test `stop` with nothing running exits `NOT_RUNNING`
- [ ] Test the lock-held-no-PID-file case exits `NO_STOP_TARGET` and `status` reports `running (pid unknown)`
- [ ] Test migration on start: a store created at version 2 by slice 101 code upgrades to 3 with nodes and blocked states intact

**Success Criteria**:
- [ ] All seven behaviors asserted against the real CLI
- [ ] A deliberate check confirms the real supervisor directory is untouched
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(cli): add start, stop, and status commands`

**Files to Create**: `tests/test_cli_lifecycle.py`

---

### Task 7.4: Implement the inspection listing registry
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 3
**Objective**: Implement `src/amoeba/cli/inspect.py` with listings declared in **one registry** (name → query → columns), so slice 104 adds `findings` and `verdicts` by registering rather than by editing the CLI.

**Steps**:
- [ ] Build the registry as the single structural definition of the listings; subcommand names derive from it, never the reverse (labels are not logical structure)
- [ ] Register `projects`, `nodes`, `blocked`, and `journal`; `journal` accepts `--unresolved`; all accept `--json`
- [ ] `projects` lists project ids having a store in the supervisor directory
- [ ] Open stores **read-only** via `Store.open_read_only` — inspection never migrates, creates, or writes
- [ ] Ensure listings work while the process is running **and** while it is stopped
- [ ] Register no findings or verdicts listing — slice 104 owns those (see the D4 note in this file's closing section)

**Success Criteria**:
- [ ] Adding a listing requires only a registry entry, verifiable by inspection of the code
- [ ] Every listing opens read-only
- [ ] Human-readable and `--json` output for each listing
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/cli/inspect.py`

---

### Task 7.5: Test inspection
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 3
**Objective**: Prove inspection reads everything it claims and writes nothing, ever.

**Steps**:
- [ ] Test each listing human-readable and as `--json`, with the JSON parsed and asserted structurally
- [ ] Test every listing **while the process is running** and **while stopped**
- [ ] Test `journal --unresolved` returns only unresolved entries
- [ ] Test inspection **never migrates**: run it against a version-2 store and assert the file's schema version is unchanged afterward
- [ ] Test inspection against a non-existent store does not create one — check the filesystem
- [ ] Test `inspect projects` against an empty supervisor directory returns empty rather than failing

**Success Criteria**:
- [ ] All six behaviors asserted
- [ ] The never-migrates test inspects the file's stamped version directly, not just the command's exit code
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(cli): add read-only inspect command`

**Files to Create**: `tests/test_cli_inspect.py`

---

## Section 8: The Sole-Writer Guard

### Task 8.1: Implement the AST guard test
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 2
**Objective**: Make the sole-writer model mechanical rather than conventional, in the manner of the existing `tests/test_store_safety.py`.

**Steps**:
- [ ] Add an AST-based test walking every module under `src/amoeba/` and failing if any module **other than `process/host.py`** calls read-write `Store.open`
- [ ] Include `cli/inspect.py` in the covered set — it must use `open_read_only` (unless Task 2.1's evidence forced the fallback, in which case extend the guard to permit it there **and** update both contract docs in Section 9, per the LLD)
- [ ] Add a self-check: the test fails when a read-write call is deliberately introduced elsewhere (verify once by hand, then revert)
- [ ] Document in the test what the guard does **not** cover — a third party importing the library and writing — matching the LLD's honest bound

**Success Criteria**:
- [ ] The guard passes on the current tree and fails on a deliberately added violation
- [ ] `host.py` is the only permitted read-write caller
- [ ] The test docstring states the guard's limits rather than implying total enforcement
- [ ] Commit after this task, e.g. `test: add sole-writer guard for read-write store opens`

**Files to Create**: `tests/test_writer_guard.py`

---

## Section 9: Load Tier, Documentation, and Walkthrough

### Task 9.1: Create the load-test tier and its process harness
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 2
**Objective**: Create `tests/load/`, required by the Python rules now that concurrency and process boundaries enter the codebase, and build the shared harness both load tests drive a real resident process through.

**Steps**:
- [ ] Add `addopts = ["--ignore=tests/load"]` to `pyproject.toml`'s `[tool.pytest.ini_options]`, alongside the existing `testpaths = ["tests"]`, so a bare `uv run pytest` never collects the directory. An explicit `uv run pytest tests/load` still works because a path named directly on the command line is collected regardless of `--ignore` (pytest collects explicitly named paths first; `--ignore` only prunes implicit `testpaths` discovery)
- [ ] Create `tests/load/__init__.py` and `tests/load/conftest.py` for the tier's own fixtures (no marker mechanism needed — `--ignore` handles exclusion directly)
- [ ] Add a small in-process **test-only harness** in `conftest.py` (not a CLI flag — the CLI ships no tenant registration, per the LLD's "ships no tenants") that constructs a `ResidentProcess` directly with one throwaway `Tenant` registered, launches it in a subprocess via a tiny bootstrap script the fixture writes to `tmp_path`, and exposes helpers to signal and wait on it. This is the same shape of harness Task 6.4 already builds for its own throwaway-tenant test; factor the common piece so it is written once and both `test_host.py` and this tier can use it, per the project's DRY rule

**Success Criteria**:
- [ ] `uv run pytest` (default, no args) does not collect anything under `tests/load/`; `uv run pytest tests/load` does collect (even though nothing is in it yet but `__init__.py`/`conftest.py`)
- [ ] The harness starts a real subprocess running `ResidentProcess` with one throwaway tenant and can signal and wait on it — proven by a minimal smoke use in this task, not deferred to 9.2
- [ ] `uv run pyright` clean

**Files to Create**: `tests/load/__init__.py`, `tests/load/conftest.py`
**Files to Modify**: `pyproject.toml`

---

### Task 9.2: Implement the crash-loop test
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 3
**Objective**: Prove crash-only holds under repetition, using the harness Task 9.1 built.

**Steps**:
- [ ] Implement the crash loop per the LLD: repeatedly start the process (via the Task 9.1 harness) with a test tenant that issues journal entries, `SIGKILL` at a **random** point, restart
- [ ] After every cycle assert: no committed node or entry is missing, **no entry is reconciled twice**, and start-to-ready stays under the asserted bound
- [ ] Set the bound by **measuring first**, then asserting at roughly twice the observed value, per the LLD's candidate bounds (start-to-ready under 2 s is a starting target, not a requirement)
- [ ] Record the real measured numbers in the test as a comment; if a measurement lands far from the candidate, record it and say why rather than tuning the bound silently to whatever passes

**Success Criteria**:
- [ ] The loop runs many cycles with `SIGKILL` at varying points and no state loss
- [ ] Double-reconciliation would fail the test
- [ ] Measured values recorded; bounds justified rather than reverse-engineered

**Files to Create**: `tests/load/test_crash_loop.py`

---

### Task 9.3: Implement the recovery-scale test
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 3
**Objective**: Prove recovery scales and, more importantly, that the runs directory is scanned once per recovery rather than once per entry.

**Steps**:
- [ ] Build several hundred unresolved entries against a runs directory of about a thousand files, per the LLD
- [ ] Assert a bound on total recovery time, measured first then set at roughly twice the observation (500 entries against 1000 files under 30 s is the starting candidate)
- [ ] Assert the directory is scanned **exactly once per recovery pass** — an exact assertion, and the one that actually guards the algorithm against a per-entry scan or an accidental O(n²) match
- [ ] Use synthesized run files here (real fixtures are Task 4.1's job); scale, not realism, is what this test measures

**Success Criteria**:
- [ ] The scan-count assertion is exact and would fail under per-entry scanning
- [ ] The time bound is justified by a recorded measurement
- [ ] Commit after this task, e.g. `test: add load tier for crash loop and recovery scale`

**Files to Create**: `tests/load/test_recovery_scale.py`

---

### Task 9.4: Write docs/process-contract.md
**Owner**: Junior AI
**Dependencies**: Task 9.3
**Effort**: 3
**Objective**: Write the downstream contract for lifecycle, tenants, and recovery, held to slice 101's bar — a downstream design proceeds without reading the implementation.

**Steps**:
- [ ] Document the process lifecycle, every CLI command, and **every** `ExitCode` with the condition that produces it
- [ ] Document the `Tenant` protocol, and state as a **requirement** (not a suggestion) that `tick()` returns promptly and polls `stop_requested` — with the consequence of not doing so: grace expiry, `STOP_TIMEOUT`, operator kill. This is the obligation slices 103 and 120 code against
- [ ] Document all three enumerated lifecycle failure modes from the LLD, including that there is **no per-tick timeout by decision**
- [ ] Document recovery semantics: journal-before-side-effect, observe-never-re-issue, exactly-one-adopted, everything-else-escalates
- [ ] State the security note: `parameters` and `result` are stored verbatim and shown by `inspect`, so **callers must not place secrets in them**
- [ ] Add YAML frontmatter per `file-naming-conventions.md`

**Success Criteria**:
- [ ] Every exit code documented with its trigger
- [ ] The tenant obligation is stated as binding, with its consequence
- [ ] A slice 103 designer could build the apply loop from this document alone
- [ ] Commit after this task, e.g. `docs: add process contract`

**Files to Create**: `docs/process-contract.md`

---

### Task 9.5: Update docs/store-contract.md and the changelog
**Owner**: Junior AI
**Dependencies**: Task 9.4
**Effort**: 2
**Objective**: Fold the journal into the existing store contract and correct the sections slice 101 wrote that this slice changes.

**Steps**:
- [ ] Add a Journal section covering all five store methods, the vocabularies, and the required parameter keys per kind
- [ ] Update the **"Not a journal"** section — slice 101 wrote it and this slice makes it wrong
- [ ] Update the **"Writer model"** section: single-writer is now enforced by the instance lock plus the guard test, not merely described. **If Task 2.1's evidence forced the read-write fallback for inspection, state the softened invariant explicitly in both this document and `process-contract.md`** rather than leaving an unqualified claim standing
- [ ] Document `open_read_only` and its never-migrates rule
- [ ] Add `CHANGELOG.md` entries for the journal, the process, the CLI, and the first runtime dependency

**Success Criteria**:
- [ ] No sentence in the contract contradicts what this slice shipped
- [ ] The writer-model section matches the enforcement actually implemented
- [ ] Commit after this task, e.g. `docs: update store contract for the command journal`

**Files to Modify**: `docs/store-contract.md`, `CHANGELOG.md`

---

### Task 9.6: Write the demo helper and refine the verification walkthrough
**Owner**: Junior AI
**Dependencies**: Task 9.5
**Effort**: 2
**Objective**: Make the LLD's walkthrough real, replacing its drafted output with captured output.

**Steps**:
- [ ] Write `scripts/demo_journal.py` — a few lines over the **public** store API — creating a `demo` project with three nodes and one unresolved `sq_run` entry each, against a scratch runs directory seeded with copies of real run files: one entry with exactly one match, one with none, one with two
- [ ] Run the LLD's six walkthrough steps end to end against a scratch `AMOEBA_STORE_DIR`
- [ ] Replace the drafted output in the LLD's Verification Walkthrough with **actual captured output**
- [ ] Confirm the real supervisor directory and real Squadron runs directory were never touched

**Success Criteria**:
- [ ] All six walkthrough steps run as written; any step that does not is fixed in the code or corrected in the document
- [ ] The walkthrough in the LLD shows real output, not drafted output
- [ ] The helper uses only the public store API
- [ ] Commit after this task, e.g. `docs: capture real walkthrough output and add demo script`

**Files to Create**: `scripts/demo_journal.py`
**Files to Modify**: `project-documents/user/slices/102-slice.resident-process-and-recovery.md`

---

### Task 9.7: Wire CI to gate the default suite and the load tier
**Owner**: Junior AI
**Dependencies**: Task 9.6
**Effort**: 2
**Objective**: The repo has no CI at all yet, and the Python rules require CI to gate load tests for slices touching concurrency/process boundaries (`.claude/rules/python.md`). This slice is the first to need it — add the minimal workflow rather than leaving the gate implicit.

**Steps**:
- [ ] Create `.github/workflows/ci.yml` running on push and pull_request: `uv sync`, then `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest` (default suite), and `uv run pytest tests/load`
- [ ] Keep the workflow to one job and one Python version — matching what the project currently targets, not a matrix, since nothing in this slice requires one
- [ ] Do not gate the crash-loop test's non-determinism by suppressing failures — a flaky load test is a signal to fix the test or the bound, not to skip it in CI

**Success Criteria**:
- [ ] The workflow runs the default suite and the load tier as separate steps, both able to fail the run independently
- [ ] A deliberately broken test (verify once locally with `act` or by inspection, not required to run in a real GitHub Actions run before commit) would fail the workflow
- [ ] Commit after this task, e.g. `chore: add CI workflow gating tests and the load tier`

**Files to Create**: `.github/workflows/ci.yml`

---

### Task 9.8: Final verification and slice completion
**Owner**: Junior AI
**Dependencies**: Task 9.7
**Effort**: 2
**Objective**: Verify every success criterion in the LLD, then close the slice.

**Steps**:
- [ ] Run `uv run pytest`, `uv run pytest tests/load`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`
- [ ] Walk the LLD's Functional, Technical, and Integration Requirements lists and confirm each item; anything unmet is fixed or explicitly raised with the Project Manager — **not** quietly checked off
- [ ] Confirm source files are near the 300-line budget and functions near 50 lines
- [ ] Confirm `grep` for `os.environ`/`getenv` across `src/amoeba/` still finds only `paths.py`
- [ ] Delegate the checklist update across both task files to the `task-checker` agent
- [ ] Commit, then merge the slice branch into the integration target — **re-read `cf config get git.integration_branch` first** rather than inferring the target from the current branch or from memory

**Success Criteria**:
- [ ] Every quality command clean
- [ ] Every LLD success criterion checked and honestly reported
- [ ] Both task files updated; slice branch merged into the target
- [ ] The slice's own claim holds: `start`, `kill -9`, `start` loses no committed state and requires no manual cleanup

---

## Resolved: D4 — the inspection criterion (review finding F001)

**Ratified by the Project Manager on 20260919 and applied to the slice plan.** The slice-102 criterion previously read "Inspection surface lists nodes, findings, verdicts, and journal entries", which this slice could not satisfy because findings and verdicts do not exist until slice 104. The criterion is now split:

- **102** — "Inspection surface lists nodes, blocked states, and journal entries, through a listing registry that later slices extend rather than edit." This is what Task 7.4 delivers.
- **104** — lists findings and verdicts *in addition to* the above, registered into this slice's registry rather than by editing the CLI.

Slice 104's declared dependencies moved from `[101]` to `[101, 102]` to match, and this slice's `interfaces` frontmatter now includes 104. Execution order is unchanged (`101 → 102 → 103 → 104`), so no resequencing follows.

**No open items remain for this slice.** Task 7.4 registers no findings or verdicts listing; slice 104 owns those.
