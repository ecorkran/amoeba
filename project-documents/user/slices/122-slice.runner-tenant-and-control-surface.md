---
docType: slice-design
slice: runner-tenant-and-control-surface
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 120
- 121
interfaces:
- 123
- 124
- 125
- 126
- 127
- 128
- 129
dateCreated: 20261020
dateUpdated: 20261021
status: not_started
turns: 35
promptTokens: 3530573
cachedTokens: 3346441
cacheWriteTokens: 184076
completionTokens: 62735
durationSeconds: 672.8
costUsd: 3.397148
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Runner Tenant and Control Surface

## Overview

This slice builds the Runner's loop, with no lifecycle in it yet. It is a new tenant, `RunnerTenant`, that `amoeba start` composes after `standard_tenants`. Each tick runs every project through observe, decide and act stages. Decide is pure, and Act issues journaled commands and nothing else.

The control surface in this slice is one command kind, `sq_run`:

- **Launch.** A run is launched detached, in its own session, with stdin from `/dev/null`, and with stdout and stderr written to per-entry log files under the supervisor directory.
- **Confirm.** A launch is confirmed by the exact `run_id=<id>` line on the run's stderr, or by Squadron reporting a state for the id.
- **Observe.** Each in-flight run is polled by id through 120's `poll_run`, with no process handle needed, so runs launched in this lifetime and runs left in flight by a crash are observed the same way.
- **Finish.** A finished run resolves its journal entry. This slice records only the outcome document's fields. Reviews, checkpoints and routing come with 125 and 126.
- **Survive a crash.** Recovery leaves an id-bearing entry whose run exists unresolved, for the Runner to finish (D3). An entry recovery marks `not_applied` is left alone. Reissuing it is deferred to 125 (D7, issue #9).

Around that, the slice adds the start-up shape probes, per-project fault isolation with the Runner's one process-boundary catch, a tick deadline checked before every subprocess call, and the settings for all of it.

No production code in this slice launches anything. The production planner tuple is empty. The proof drives the loop with a planner that exists only in tests, against the stub `sq`. 125 adds the first production planner.

## Value

Developer value, and the slice the plan rates highest-risk.

- **A command goes out, is watched without blocking, and survives a crash.** Every later slice adds behaviour to this loop: reconciliation (123), intents (124), dispatch and ingestion (125), routing (126), resolutions (127) and gates (128). None of them builds its own launch, observation, fault handling or deadline logic.
- **Lost and duplicated runs are designed out, not handled later.** Launch confirmation and crash adoption are where the Runner can lose a run or launch one twice. They are proven here against a stub, before anything depends on them.
- **A wrong Squadron is refused at start.** A missing `sq runs wait --json` stops `amoeba start` with the shape named, instead of every run failing later.

## Technical Scope

**Included**

- `amoeba.runner`, a new internal package: the tenant, the tick skeleton, the tick budget, the launcher and launch logs, run-id minting, in-flight observation, minimal outcome recording, the planner seam, the fault boundary and fault vocabulary, and the probes.
- `amoeba start` composes `(*standard_tenants(settings, supervisor_dir), runner_tenant(settings, supervisor_dir))`.
- A change to 120's by-id recovery observer: an entry whose run has a state is left in flight rather than adopted (D3). This adds an `InFlight` answer to `Observation` and a recovery property to `docs/process-contract.md`.
- New `ProcessSettings` fields and start flags: tick deadline, per-call timeout and run poll interval (D10). 120 already adds the launch grace period, and this slice uses it.
- `sq` start-up probe and per-link `cf` probes (D9).
- `tests/sq_stub.py` gains a `run --run-id` mode that plays a detached Squadron run (see Implementation Notes).
- A crash-recovery proof that runs the real resident process as a subprocess and kills it with `SIGKILL` at named points.
- Contract text: `docs/process-contract.md` (tenants, the tenant obligation's new tick-time subprocess rule, recovery, the supervisor directory, settings, exit codes) and `docs/substrate-guide.md` (the 120 row).

**Excluded**

- Every lifecycle decision. That covers node creation and the step map (123), intents and hold (124), pointer writes, dispatch, checkout concurrency, review ingestion and checkpoint blocked-states (125), routing (126), resumes (127), and gates and git (128).
- The `cf_write` act. 125 issues the first pointer write and adds it to Act. The journal kind and its recovery observer already exist in 100.
- Any `cf` read during a tick. The `cf` probes run once per link, and 123 makes the first tick-time `cf` reads.
- Killing a run, under any condition. The Runner never kills a run or a launch child.
- Deleting launch logs. They are kept, and retention is listed under Special Considerations.
- Reissuing a `not_applied` launch, with issue #9's launch-log check. This moves to 125, the first slice that launches in production (D7, issue #9).
- A retry class for transient faults. Every fault escalates in v1 (slice plan Future Work 2).

## Dependencies

### Prerequisites

- **120, merged.** It provides `poll_run`, `RunOutcome`, `RunOutcomeDocument`, `PollFailure`, `SQ_EXECUTABLE`, the `run_id` required key (`PARAM_RUN_ID`), the by-id recovery observer and `launch_grace_seconds`. This slice changes the by-id observer's answer for a run that exists (D3).
- **121, merged.** It provides `raise_project_escalation`, `open_project_escalations` and `close_project_escalation`, and the guarantee that a node with an unresolved entry cannot be marked `done`.
- **squadron-ai 0.23.5 or later** as `sq`. The slice depends on its shapes, not its version: `sq run --run-id`, the `run_id=<id>` stderr line, and `sq runs wait <id> --timeout 0 --json`.
- **Context Forge** as `cf`, for the per-link probes: `cf status --json -p <id>` and `cf list initiatives --json -p <id>`. Both take `-p` (observed on CF 0.19.16, 20261020).

### Interfaces Required

- **Host** (`ResidentProcess`): `project_ids` (read every tick, never cached), `store_for`, `stop_requested`, `settings`.
- **Store**:
  - Journal: `journal_issue`, `journal_resolve`, `unresolved_journal_entries`.
  - Nodes and blocking: `runnable`, `node`, `block`, `blocked_state_for`.
  - 121's project-scoped escalation.
  - `cf_links`.
- **Squadron's run contract** (`sq run --help`, `cli/commands/run.py`):
  - `--run-id` creates the run under that id and is refused when the id already exists.
  - A fresh run prints `run_id=<id>` on stderr before its first step.
  - A usage error exits 2 before anything runs.
- **Evidence contract D5 point 3.** Detection defers while a project has an unresolved entry of a review-producing kind, and `record_runner_report` resolves an unresolved entry. Both are why an `sq_run` entry stays unresolved for the whole life of its run (D2, D3).

## Architecture

### Component Structure

```
amoeba/runner/                 NEW package; imported only by amoeba.cli
  tenant.py        RunnerTenant: project order, deadline carry-over, the fault boundary
  tick.py          one project's tick: observe → record finished → decide → act;
                   TickBudget, the deadline and stop check before every subprocess call
  decide.py        ProjectView, InFlightRun, the Action set (LaunchRun), the Planner
                   protocol, decide(view, planners) → actions
  launch.py        mint_run_id(), SQUADRON_RUN_ID_PATTERN; log paths by entry id, the
                   exact-line check and bounded tail; detached Popen; LaunchTracker
  observe.py       observe in-flight runs: confirmation, poll cadence, classification
  finish.py        record a finished run (minimal; 125 replaces the body)
  faults.py        FaultKind, LaunchFailure, NodeFault, STORE_FAILURES, escalation writes
  probes.py        sq probe at start; per-link cf probes: CF_EXECUTABLE, the two
                   commands, the cf call, the CF JSON top-level checks (D9)
  factory.py       runner_tenant(settings, supervisor_dir): validate settings, probe, build
amoeba/process/
  observers/sq_run_id.py   CHANGED  a run that exists → InFlight (D3)
  recovery.py              CHANGED  InFlight leaves the entry unresolved; summary counts it
  settings.py              CHANGED  + tick_deadline_seconds, tick_call_timeout_seconds,
                                      run_poll_interval_seconds
  errors.py                CHANGED  + UpstreamShapeError
amoeba/cli/
  lifecycle.py             CHANGED  composes the Runner after standard_tenants
  settings_flags.py        CHANGED  + --tick-deadline, --tick-call-timeout, --run-poll-interval
  main.py                  CHANGED  + ExitCode.UPSTREAM_SHAPE
```

`amoeba.runner` is not a public import root. Nothing outside `amoeba.cli` imports it, and an import-boundary test enforces that. It imports `amoeba.store`, `amoeba.process` and `amoeba.upstream` only through their public names, the same as the stand-in Runner does.

### Data Flow

**One tick:**

```
RunnerTenant.tick(host)
  budget ← TickBudget(now + tick_deadline_seconds, host)
  order  ← carried-over projects first, then the rest of host.project_ids
  for project in order:
      try:                                    ── the one process-boundary catch (D8)
          ProjectTick(project).run(budget)    ── returns COMPLETE or CUT_OFF
      except STORE_FAILURES / UpstreamShapeError: re-raise   → the process exits
      except Exception: log ERROR, escalate the node in context, or the project
      CUT_OFF → carry the project over; stop when the budget is spent
  return whether anything was written or issued
```

**One project's tick** (the slots in brackets are filled by later slices):

```
[apply intents — 124]
observe   unresolved sq_run entries → InFlightRun per entry
          (launch confirmation, poll if due, classify: running | finished | fault)
          + first-use cf probe for each link not yet probed (D9)
record    each finished run → finish.record()                     [125 replaces]
[route — 126]
decide    view ← ProjectView(...); actions ← decide(view, planners)   pure, no I/O
act       for each action, while budget allows: journal_issue → side effect
close     on COMPLETE only: close each open project escalation whose kind
          did not recur this tick
```

**A launch, end to end:**

```
tick n    act:      run_id ← mint_run_id(); entry ← journal_issue(sq_run, {pipeline,
                    params, run_id, checkout}); open <entry>.stdout/.stderr logs;
                    Popen([sq, run, pipeline, --run-id, id, -p k=v …], detached)
tick n+k  observe:  stderr has exact "run_id=<id>"         → confirmed, in flight
                    child exited, no line, no run state    → launch failed (D6)
                    grace passed, no line: poll once       → state: in flight; none and
                                                             child alive: overdue (D6)
tick m    observe:  due for a poll: poll_run(id)
                    timed_out (still running)              → in flight
                    completed | failed | paused | orphaned → finished → record
                    not_found after confirmation           → finished (run vanished)
                    unreadable | unknown_status | PollFailure → fault, keep polling
```

### State Management

- **Durable, in the store.** The set of in-flight runs is exactly the project's unresolved `sq_run` entries. Nothing else marks a run in flight. A node is not runnable for Decide while it has an unresolved entry. No node status is written at launch. 125 decides how a node looks while its run is in flight.
- **Durable, on disk.** Launch logs, one pair per journal entry, under `<supervisor>/launch-logs/`. They are the evidence for a failed launch's escalation, and for the reissue check 125 adds (issue #9).
- **In memory, rebuilt from nothing after a restart:**
  - `LaunchTracker`: the `Popen` handle and confirmation flag of each launch made in this lifetime.
  - Each run's last poll time, for the poll interval and least-recently-polled order.
  - The projects carried over by the deadline.
  - The CF links already probed in this lifetime.

  Losing any of these in a crash is safe. After a restart, every in-flight entry has a run state (D3), so it needs no handle and no confirmation, only polling. Poll order starts fresh, and the probes run again.

## Technical Decisions

### D1 — The tick skeleton is fixed code with one seam, the planners
Status: decided
- A project's tick is a fixed sequence of calls in `tick.py`: observe, record finished runs, decide, act and close. Later slices add their stages to this sequence directly. 124 adds intents before observe, 123 and 128 add reads to observe, 125 replaces the body of `record`, and 126 adds routing after it. There is no stage registry. A plugin mechanism would be complexity with one user.
- Decide has the one seam, `Planner`, with `plan(view: ProjectView) -> Sequence[Action]`. A planner is pure: it receives only the frozen view, including `now`, and does no I/O. `decide(view, planners)` runs the planners in order and returns their actions. A node may receive at most one action per tick. A second action for the same node is a programming error and raises `ValueError`, which faults the project. It is never silently dropped.
- `RunnerTenant`'s planners are a constructor argument. `runner_tenant()` passes the production tuple, which is empty in this slice. Tests pass their own. 125 adds its dispatch planner to the production tuple.
- `ProjectView` holds `project_id`, `now`, the runnable nodes that have no unresolved entry, the in-flight runs and the link probe results. Later slices add fields.
- Rejected: Decide reading the store directly. That would make Decide impure and decisions impossible to recompute.

### D2 — An `sq_run` entry spans the whole run
Status: decided
- The entry is journaled before the launch and resolved only when the run is finished: a Squadron outcome other than still running, or the run vanishing. It is not resolved when the launch is confirmed. Two contracts need this. Detection defers only while an unresolved review-producing entry exists (evidence contract D5). And `record_runner_report`, which 125 uses to record a review and resolve the entry in one transaction, accepts only an unresolved entry.
- Journal parameters for `sq_run`. The required keys are unchanged from 120:
  - `pipeline`: a pipeline name or path, required.
  - `params`: a mapping of string to string, passed as `-p key=value`, required.
  - `run_id`: required, minted (D5).
  - `checkout`: the absolute working directory, the launch's `cwd`.
- The launch passes each param as its own `-p key=value`. Squadron splits a `-p` value on commas, so a value containing `,`, or a key containing `,` or `=`, raises `ValueError` before journaling.
- Resolution by `finish.record()`, the minimal body that 125 replaces:
  - **Squadron outcome `completed`.** `journal_resolve(completed, result={run_id, outcome, status})`.
  - **Squadron outcome `failed` or `paused`.** The command ran, so the entry resolves `completed`, with `failure` or `checkpoint` added to the result as reported. The node blocks on `HUMAN` first. In 125, a pause becomes `blocked_on_sq_checkpoint`.
  - **`orphaned`, or `not_found` after confirmation.** The command could not finish. The node blocks on `HUMAN` and the entry resolves `failed`.
- The order is always block, then resolve. Both writes are idempotent on re-entry: a node already blocked is not blocked again. A crash between them leaves an unresolved entry whose run exists, so recovery leaves it in flight (D3), and the next tick re-observes the run and finishes the sequence.

### D3 — Recovery leaves an existing run in flight
Status: decided
- **This changes 120's D3.** 120 adopts an id-bearing entry whenever Squadron holds a state for its id. Adoption resolves the entry. After a crash, that would end detection's deferral while the run may still be writing reviews, and 125 could no longer record the run's review with `record_runner_report`. A run that finished while Amoeba was down has the same problem, so the change cannot be limited to runs that are still running.
- The by-id observer returns a fourth answer, `InFlight(run_id, outcome)`, for every outcome that carries a state: completed, failed, paused, timed_out (still running), unknown_status and orphaned. Recovery logs it and leaves the entry unresolved. The Runner's first tick polls the run and finishes it (D2). `NotApplied` (no state after the grace period) and `Unknown` (unreadable, poll failure, claimed id, bad parameter) are unchanged. The legacy attribute matcher still adopts.
- **Recovery property** added to `docs/process-contract.md`: "An id-bearing `sq_run` entry whose run exists is left unresolved, in flight, for its issuer to finish." The gate still holds. Before any tenant ticks, every entry is either resolved or tied to a run Squadron reports. `InFlight` joins the `amoeba.process` hosting surface, which goes from 13 names to 14.
- **Consequence.** A host that runs without the Runner leaves such entries unresolved, and detection stays deferred for that project. `amoeba start` always composes the Runner, so this arises only in a custom host. The contract suite's stand-in Runner finishes its own in-flight entries after a restart (Implementation Notes).
- Rejected:
  - Adopting, then having the Runner re-journal a watching entry. The claimed-id guard would turn the second entry into `Unknown` after the next crash, and two entries would describe one run.
  - Changing detection to defer on adopted-but-unfinished runs. That would put a second notion of "in flight" into 100.
- **Ownership and sequencing.** The plan gives recovery's move to run ids to 120, and 120 ships it as designed, adoption included. 120 is merged before this slice starts (Prerequisites). This slice then changes 120's shipped observer and its contract text, because the need comes from the in-flight model this slice introduces (D2), which 120 does not have. The change is this slice's first code task and lands before any Runner code, so the Runner codes against the changed contract, as the arch requires. The plan's 122 entry records the change.

### D4 — Detached launch
Status: decided
- `launch()` opens `<entry_id>.stdout.log` and `<entry_id>.stderr.log` in `<supervisor>/launch-logs/` (created by the factory) for exclusive creation. It then calls `subprocess.Popen` with:
  - the argv `[SQ_EXECUTABLE, "run", pipeline, "--run-id", run_id, "-p", "k=v", …]`;
  - `cwd=checkout`, `stdin=DEVNULL`, and stdout and stderr to the two files;
  - `start_new_session=True`, `close_fds=True`, and the inherited environment, because Squadron's providers read their credentials from it.

  The parent closes its file handles once `Popen` returns.
- Logs are named by entry id, not run id, because the reissue 125 adds reuses the run id (issue #9) and must not overwrite the earlier attempt's evidence.
- The `Popen` handle goes into `LaunchTracker`. Each tick calls `poll()` on every tracked handle, which reaps finished children so none is left a zombie, and drops handles that have exited and whose launch is settled. A child outlives a crash of the resident process because it runs in its own session. It is then reparented and never needs reaping.
- Opening either log file can fail after the entry is journaled, for example with a permission error, a full disk, or `FileExistsError` if a log for that entry id already exists. Each is an `OSError`, `Popen` is not called, and the launch fails as `spawn_error` in the same way as the next bullet.
- `Popen` raising `OSError` (for example `sq` missing or `checkout` gone) is a failed launch. The node blocks with the error, and the entry resolves `failed` with no run id claimed beyond the parameters.
- The environment is never logged or journaled.

### D5 — Run ids are minted to Squadron's rule
Status: decided
- `mint_run_id(now)` returns `amoeba-<UTC yyyymmddTHHMMSSZ>-<12 hex chars of uuid4>`, for example `amoeba-20261020T221144Z-3f9a1c0d2b7e`. That is 38 characters, sortable by time, and recognizably Amoeba's in `sq runs list`.
- `SQUADRON_RUN_ID_PATTERN` (letters, digits, `.`, `_`, `-`; a letter or digit first; at most 128 characters) is defined once in `launch.py`. A test asserts that minted ids match it. `mint_run_id` asserts nothing at runtime. A pattern mismatch is a code defect, and the test catches it.
- The id is minted in Act, immediately before `journal_issue`. The id is in the journal before any side effect, so a crash between journaling and launch leaves an entry recovery can look up by id.

### D6 — Launch confirmation
Status: decided
- **Confirmed** when the stderr log has a line exactly equal to `run_id=<id>`, or when a poll returns any outcome other than `not_found`. "Exactly" means a whole line, compared after removing only the line terminator. It is never a substring match inside another line. This line is the one exception to "never read stdout prose" that the arch allows, because S9 documents its format. The check reads at most the first 64 KiB of the file, because Squadron prints the line before its first step.
- **An unreadable log.** If reading the stderr log raises `OSError` (the file was removed, or permissions changed), the check answers "no line" for this tick and raises `run_observation_failed` for the project, naming the entry and the error. The run state still decides: a poll that finds a state confirms the launch, and at grace expiry or child exit the overdue and failure rules below apply, with the error in place of the log tail. Nothing is guessed from the missing file.
- **Still launching**, while unconfirmed: `not_found` from a poll, or no line yet with the child alive and the grace period not passed. An unconfirmed launch is not polled on the interval. It is polled once when the child exits without the line, and once when the grace period passes.
- **Overdue.** The grace period (`launch_grace_seconds` from `issued_at`) passed with no line, one poll finds no state, and the child is still alive. A live child can still create the run, so the launch is not failed and the entry stays unresolved. The tick raises `launch_overdue` for the project, naming the entry, the run id and the log tail. From then on the launch is polled on the run poll interval, like a confirmed run, and the line is still checked. A state or the line confirms it. The fault recurs on every tick while the launch stays overdue, so D8's closure rule closes the escalation only after the launch is confirmed or failed. When the child exits, the exit rule below applies. The child is not killed.
  - This keeps a late run adoptable. A resolved entry could not receive its review through `record_runner_report`, and its checkout would look free.
  - After a restart the child handle is gone. Recovery marks a stateless entry past the grace period `not_applied` (120, D4), and 125's reissue polls again before reissuing and adopts a run that exists (issue #9).
  - Rejected: failing the launch at grace expiry while the child lives. A late run would then be unobserved.
- **Failed**:
  - The child exited before printing the line, and one poll finds no state. This applies to an overdue launch too.
  - The `OSError` case of D4.

  On failure, the node blocks on `HUMAN` with a `LaunchFailure` reason, the child's exit code if known, and the last 4 KiB of the stderr log. The entry then resolves `failed`, with `result={run_id, launch_failure}`.
- **Exit 2** from a launch child that left no run state is a usage error, which means a shape is missing (`--run-id` or the param flags). The launch fails as above, then the tick raises `UpstreamShapeError` naming the command. The process exits with `ExitCode.UPSTREAM_SHAPE` (D8).
  - The whole process exits, not only the Runner tenant, for the same reason as D9's `sq` probe: a process that ran on with its Runner stopped would be a silent fallback. The arch already says this. The decision rests on the observed state (no run) and the exit code, never on the message text.
- A child that exits with any code after its run is confirmed is not the Runner's concern. The run's outcome comes from polling.

### D7 — Reissuing a `not_applied` launch is deferred to 125
Status: decided
- The arch says an entry recovery marks `not_applied` "may be issued again under the same id". This slice issues nothing in production, so no `not_applied` entry can be relaunched here. 125 is the first slice whose planner launches, so the reissue is built there, with the launch-log check. Issue #9 tracks it with the full rules: candidates, the log check, the reissue polls and the hold filter.
- In this slice, a `not_applied` entry is left as recovery wrote it, and its node has no unresolved entry. The test planner launches only for nodes with no journal entry at all, so the crash proof shows the entry is not relaunched.
- What 125 needs from this slice is already here: per-entry launch logs (D4), the exact-line check (D6), `poll_run` before a launch, and the `Planner` seam.

### D8 — Faults: one catch per project, two scopes
Status: decided
- **The catch.** `RunnerTenant.tick` wraps each project's tick in the Runner's one process-boundary catch, as the arch names it. No other `except Exception` exists in `amoeba.runner`.
- **Process failures re-raise.** The process then exits, and 100's recovery takes over on restart:
  - `STORE_FAILURES`, defined once in `faults.py` as `StoreBusyError`, `StoreCorruptError`, `StorePermissionError`, `StoreSchemaError` and `sqlite3.Error`.
  - `UpstreamShapeError`.

  An escalation write that itself fails is not caught again, so a broken store always exits.
- **Every other exception** is logged with `logger.exception` and escalated.
  - **The node in context has no run in flight and is not done.** The node blocks on `HUMAN`, with the context naming the fault and a payload of `{fault_kind, error}`. If the node is already blocked, nothing more is written, so escalations cannot storm.
  - **The node has a run in flight, is done, or no node is in context.** The fault raises a project-scoped escalation instead, with the node and run ids in the payload. A node with a run in flight blocks only when its run ends (D2), as the arch requires. A done node cannot be blocked (121, D1), so its fault takes the project-scoped path, with the node id in the payload.
- **Node context.** Each node-scoped step sets the tick's current node before it runs, the same pattern the host uses to name the current tenant. The catch reads it.
- **Expected faults are answers, not exceptions.** A `PollFailure`, an `unreadable` or `unknown_status` outcome, or a failed cf probe is recorded in the tick's fault set and raised as a project-scoped escalation. The tick continues.
- **`FaultKind`**, the vocabulary 121 left to this slice (a `StrEnum` in `faults.py`):
  - `run_observation_failed`: a poll of an in-flight run gave no usable answer.
  - `launch_overdue`: a launch child is alive past the grace period with no run state (D6).
  - `cf_probe_failed`: a CF link failed its probe (D9).
  - `unexpected_fault`: an exception with no node in context, or on a node with a run in flight.

  `LaunchFailure` (`spawn_error`, `exited_before_line`, `usage_error`) and the run-end reasons (`orphaned`, `vanished`, and the Squadron outcomes) name node blocks. 126 can match on them later.
- **Closure.** At the end of a complete project tick, every open project-scoped escalation whose kind did not recur in that tick is closed with `closed_by="runner"`. A tick that was cut off or faulted closes nothing, because its evidence is incomplete.

### D9 — Shape probes: `sq` at start, `cf` once per link
Status: decided
- **`sq`.** `runner_tenant()` runs `poll_run(<freshly minted id>, timeout_seconds=sq_timeout_seconds)` before the loop. It must return a document with outcome `not_found` and the same `run_id`. Anything else raises `StartupFailedError`, naming the shape `sq runs wait <id> --timeout 0 --json` and the answer (`PollFailure` reason, or the unexpected outcome). `amoeba start` then exits `STARTUP_FAILED`.
  - The process does not start at all. A process that ran with its Runner silently disabled would be a silent fallback, and there is no project to escalate a global shape failure to. The arch and the plan already say this.
- **`cf`.** A probe needs a CF project id, and a link names one. Each CF link is probed once per lifetime, on the first observation of its project. That makes the probe "first use" for links made while the process runs.
  - The two commands are `cf status --json -p <id>` and `cf list initiatives --json -p <id>`, each under `tick_call_timeout_seconds`. `cf list slices --json` is not probed: with no index it reads a project-level pointer that is empty on worktree-scoped projects, so a healthy link would fail. 123 checks the slice-list shape on each plan read (arch "Unknown escalates"; 123, D11).
  - Each is a separate subprocess call and checks `TickBudget` before it starts, like every other call (D10). So the probe keeps the bound of the deadline plus one call timeout. A probe cut off partway records nothing, and the link is probed again from its first command on the next tick.
  - Each output must parse as JSON with the expected top-level form: an object for status and an array for initiatives.
  - A failure raises `cf_probe_failed` for that project, naming the command, the exit code and the output head. It also marks the link failed for this lifetime, and 123 reads that flag before any `cf` read.
  - A link marked failed counts as a recurrence of `cf_probe_failed` on every later tick of its project. The raise is deduplicated, so it writes nothing, and D8's closure rule keeps the escalation open for the rest of the lifetime. It closes on the first complete tick of a later lifetime whose probe of every link passes.
  - A failed link does not stop the Runner. A deleted CF project returns empty output that looks just like a missing shape (observed 20261020). Refusing to start over one dead link, which cannot yet be unlinked (issue #7), would stop every project for one project's fault.
- **Who owns the `cf` call.** `probes.py` does. It defines `CF_EXECUTABLE` and the two probe commands, and runs each through the subprocess runner the tenant is given (`runner_tenant()` passes `subprocess.run`; tests pass a fake). Each call uses `stdin=DEVNULL`, captured output, `timeout=tick_call_timeout_seconds` and `check=False`. A `TimeoutExpired` is a probe failure.
- **Seam for 123.** The two top-level checks are private functions in `probes.py`. This slice adds and changes nothing in `amoeba.upstream`. 123 adds `amoeba.upstream.context_forge.plan` with its full models, swaps them into the probe, and moves the commands to its `plan_read.py` (123, D11). The probe then checks what the reads actually use.
- No probe reads help text. `--run-id` and `--decision` cannot be probed without a real run, so they are checked on first use (D6). `--decision` belongs to 127.

### D10 — Settings and the tick budget
Status: decided
- New `ProcessSettings` fields, each with a start flag. Defaults are defined only in `settings.py`:

  | Field | Default | Flag | Meaning |
  | --- | --- | --- | --- |
  | `tick_deadline_seconds` | 5.0 | `--tick-deadline` | No subprocess call starts after this much of a tick has passed. |
  | `tick_call_timeout_seconds` | 8.0 | `--tick-call-timeout` | Bounds each subprocess call a tick waits on (`sq runs wait`, the `cf` probes). |
  | `run_poll_interval_seconds` | 15.0 | `--run-poll-interval` | The least time between two polls of one confirmed in-flight run. |

  `launch_grace_seconds` (120, 60.0) bounds launch confirmation. `sq_timeout_seconds` keeps bounding start-up calls, which here means the `sq` probe.
- **Why a poll interval.** The plan says "polled once per tick". One `sq runs wait` costs about one second of wall time and 0.7 s of CPU (measured 20261020). The loop ticks about once a second when idle, so polling every run on every tick would keep a core about 70% busy for each run. A run is therefore polled at most once per tick, and only when its interval has passed. The plan's criterion is reworded to match.
- **`TickBudget`.** It is created at tick start from a monotonic clock. `allows_call()` is false once the deadline has passed or `host.stop_requested` is set. Every subprocess call site, including `Popen`, checks it first. When it is false, the stage returns `CUT_OFF`, the project is carried over to go first on the next tick, and the tenant stops. A project cut off during Observe starts again from the top next tick. Unissued actions are simply decided again from a fresh observation.
- **Order within a project.** In-flight runs are polled least-recently-polled first, so a deadline cannot starve the same runs every tick.
- **Bounds checked at start.** `runner_tenant()` raises `StartupFailedError` unless every value above is positive and `tick_call_timeout_seconds < shutdown_grace_seconds`. The worst case for a tick is the deadline plus one call timeout, but after a stop request no new call starts, so shutdown waits for at most one call.
- **Return value.** `tick()` returns true only when it wrote to the store or issued a command. A poll that finds a run still running returns false, so the loop idles between ticks instead of spinning.
- Updating `docs/process-contract.md`: "no tick starts a subprocess" no longer holds. The tenant obligation gains the rule that every tick-time subprocess call is preceded by a deadline and stop check and bounded by `tick_call_timeout_seconds`.

### Technology Choices

- Standard library `subprocess`, `os`, `uuid` and `time.monotonic`, plus pydantic v2 for 120's outcome document. There are no new dependencies.
- The automated tests never run the real `sq` or `cf`. The stub `sq` gains a run mode, and the `cf` probes run against a stub `cf` script with the same pattern. The real tools appear only in the walkthrough, read-only.

### Patterns and Conventions

- Every comparison value is defined once: `FaultKind`, `LaunchFailure`, `STORE_FAILURES`, `SQUADRON_RUN_ID_PATTERN`, the launch-line prefix (shared with 120's `run_id=` constant), the log suffixes, the `launch-logs` directory name, the journal parameter key `checkout` (next to 120's `PARAM_RUN_ID`), the probe commands, the 64 KiB head limit and the 4 KiB tail limit.
- Expected external failures are answers (`PollFailure`, `LaunchFailure`, probe failures), never exceptions. Unexpected exceptions reach the one catch.
- The clock and the subprocess runner are injected, so Observe, Act and the budget can be tested without sleeping.
- Each module stays under about 300 lines, and each function under about 50.

## Implementation Details

### API Contracts

Internal Python API, consumed in-package by 123–129:

```python
class Planner(Protocol):
    def plan(self, view: ProjectView) -> Sequence[Action]: ...

type Action = LaunchRun                         # closed; 125 adds WriteCFPointer
@dataclass(frozen=True)
class LaunchRun: node_id: str; pipeline: str; params: Mapping[str, str]; checkout: Path

@dataclass(frozen=True)
class InFlightRun: entry: JournalEntry; run_id: str; state: RunState  # launching | running
                                                                       # | finished | fault
def runner_tenant(settings: ProcessSettings, supervisor_dir: Path,
                  *, planners: Sequence[Planner] | None = None) -> RunnerTenant: ...
```

`planners=None` selects the production tuple. Passing planners is how tests and later slices compose. Planners take no default argument beyond that.

The recovery surface adds `InFlight(run_id: str, outcome: RunOutcome)` to `Observation` in `amoeba.process`.

CLI:

- `amoeba start` gains `--tick-deadline`, `--tick-call-timeout` and `--run-poll-interval`.
- New exit code `UPSTREAM_SHAPE` (8): a launch exited 2, meaning a Squadron shape the Runner needs is missing.
- `STARTUP_FAILED` (7) now also covers a failed `sq` probe or settings that break D10's bounds.

The supervisor directory table gains `launch-logs/`: one stdout and one stderr log per launched `sq_run` entry, named by entry id and never deleted in this slice.

## Integration Points

### Provides to Other Slices

- **123:**
  - The tick skeleton to add reconciliation to, before Decide.
  - The `cf` probe result per link, and the parser seam to replace with full models.
  - `TickBudget` for its `cf` reads.
  - `tick_call_timeout_seconds`.
- **124:** the slot before observe for applying intents.
- **125:**
  - The `Planner` seam for its dispatch planner.
  - `LaunchRun` and the launch, confirmation and observation primitives.
  - The `finish.record()` body to replace with review ingestion through `record_runner_report` on an entry that is guaranteed unresolved, even across a crash (D3).
  - The `Action` union to extend with the `cf_write` act.
  - The `not_applied` reissue, with the launch-log check (issue #9).
- **126:** the slot after record, and `LaunchFailure` and run-end reasons as routing inputs.
- **127:** the launch primitive, extended for `--resume` and the first-use check for `--decision`. Under the arch, a resume that exits 2 escalates its node rather than raising `UpstreamShapeError`, and 127 owns that branch.
- **128:** Observe as the place for its `git status` read, under `TickBudget`.
- **129:** the crash proof as a template for proving the whole Runner across a restart.
- **Contract documents:**
  - `docs/process-contract.md`: tenants (now four in `amoeba start`), the tenant obligation's tick-time subprocess rule, recovery's `InFlight` property, the supervisor directory, the start flags, and exit codes.
  - `docs/substrate-guide.md`: the 120 row.

### Consumes from Other Slices

- **120:**
  - `poll_run` and the outcome document. A `PollFailure` is a fault, never a guess.
  - The by-id observer, changed here (D3).
  - `launch_grace_seconds`.
  - `PARAM_RUN_ID` and `SQ_EXECUTABLE`.
- **121:**
  - The project-scoped escalation methods. Deduplication on project and fault kind is what keeps a recurring fault from adding rows.
  - Done-terminal enforcement, which guarantees no unresolved entry sits on a done node.
- **100:** the journal, blocking, recovery's gate, the host's tick loop and grace period, and `cf_links`. None changes shape except as listed.

## Success Criteria

### Functional Requirements

- With a test planner and the stub `sq`, a no-op step is journaled, launched detached, confirmed by its `run_id=` line, polled to `completed`, and recorded with `run_id`, `outcome` and `status` in the entry's result.
- Across a `SIGKILL` of the resident process, the run is still recorded correctly in each of these cases:
  - **Killed after journaling, before the launch.** The entry becomes `not_applied`, and nothing relaunches it. The stub saw no `sq run` for the id.
  - **Killed while the run is running.** The entry is left in flight by recovery, then observed and recorded.
  - **Killed after the run finished, before it was recorded.** The entry is left in flight, then recorded on the first tick.
  - **Killed between a node block and the resolve.** The next tick finishes the sequence, and the node has one blocked state.
- A launch whose child exits before the line resolves `failed`, and its node blocks with the reason and the log tail. If a poll at that moment finds a run state, the run is observed instead.
- A launch past the grace period with no line, no run state and a live child stays unresolved and raises one `launch_overdue` escalation. A run that appears later (the stub's late-line mode) is confirmed and recorded, and the escalation closes.
- An unreadable launch log raises `run_observation_failed` and leaves the decision to the run state.
- A launch child that exits 2 with no run state blocks its node, resolves its entry `failed`, and exits the process with `UPSTREAM_SHAPE`.
- With an `sq` whose `runs wait --json` does not return the not-found document, `amoeba start` exits `STARTUP_FAILED`, naming the shape. A CF link whose probe fails raises one `cf_probe_failed` escalation for that project, and other projects continue. A probe cut off by the deadline starts no call after it.
- An unexpected exception in one project is logged at ERROR and escalates the node in context, or raises a project-scoped escalation. The same tick continues with the other projects. A store failure exits the process.
- A recurring fault adds no rows after the first. The first complete tick without it closes its project-scoped escalation.
- No subprocess call starts after the tick deadline or after a stop request. A project cut off goes first on the next tick, and the next tick polls the cut-off runs first.
- A confirmed in-flight run is polled no more than once per tick and no more often than `run_poll_interval_seconds`. A tick that finds nothing new returns false.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- `amoeba.runner` has exactly one `except Exception`, the per-project catch. Every other `except` names a specific exception with a comment.
- An import-boundary test asserts that only `amoeba.cli` imports `amoeba.runner`. The writer guard passes unchanged, because the Runner never opens a store.
- A test asserts that every tick-time subprocess call goes through `TickBudget`. It does this by injecting a runner that fails the test when it is called after the budget is spent.
- Minted run ids match `SQUADRON_RUN_ID_PATTERN` (property test over many mints).
- The contract documents under Provides are updated, and the CHANGELOG has an entry.

### Integration Requirements

- 100's contract suite passes. The stand-in Runner finishes its in-flight entries after restart, and the oracle expects `completed` by `issuer` where it expected `adopted` by `recovery` for id-bearing entries.
- `tests/test_process_public_api.py` pins 14 names, with `InFlight` added.
- 123 and 125 can add their reads and planner without changing `tenant.py` or `launch.py`.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–3 are automated and use the stub `sq` and `cf`. Steps 4–5 use the real tools, read-only. No step launches a real Squadron run, because no production planner launches anything until 125.

1. **Unit and integration tests:**
   ```bash
   uv run pytest tests/runner -v
   ```
   Expected: all pass. The tests are grouped by module: tick and budget, launch and confirmation, observe, faults, probes and planners.

2. **The crash proof:**
   ```bash
   uv run pytest tests/runner/test_crash_recovery.py -v
   ```
   Expected: one test per kill point in the Functional Requirements, each named for its point (for example `test_kill_while_running_is_recorded_after_restart`). Each starts the resident process as a subprocess with a test planner, kills it with `SIGKILL` at the point, restarts it, and asserts the journal entry's final outcome, its result, the node's blocked state, and how many times the stub saw `sq run` for the run id: once, or none for the kill before launch.

3. **Full gate and contract suite:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/contract -v
   ```

4. **Start with the real tools in a throwaway supervisor directory:**
   ```bash
   export AMOEBA_STORE_DIR=$(mktemp -d)
   amoeba start            # in one terminal; leave it running
   ```
   Expected on stderr: the recovery summary, then the Runner's INFO line saying the `sq` probe passed. With no projects, no tick makes a subprocess call. Stop it with `amoeba stop` from a second terminal, or with Ctrl-C.

   Then link a project and watch its `cf` probe. With the process running:
   ```bash
   amoeba submit create-project --project demo --by operator
   amoeba submit link-cf-project --project demo --by operator \
     --cf-project-id "$(cf list projects --json | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')"
   amoeba inspect messages --project demo --json
   ```
   Expected: the process log shows the link's two `cf` probes passing, and no `cf_probe_failed` row appears. Repeat with `--cf-project-id does-not-exist` on a second project. That project gets one open `escalation` row with `fault_kind` `cf_probe_failed`, and `demo` is unaffected.

5. **A refused start.** Put a script named `sq` that exits 2 first on `PATH`:
   ```bash
   d=$(mktemp -d); printf '#!/bin/sh\nexit 2\n' > "$d/sq"; chmod +x "$d/sq"
   PATH="$d:$PATH" amoeba start; echo "exit $?"
   ```
   Expected: an error naming `sq runs wait <id> --timeout 0 --json`, then `exit 7`.

## Risk Assessment

### Technical Risks

- **Lost runs.** Resolving an entry before its run is really finished ends detection's deferral and orphans the review. The 120 adoption rule did this after a crash (D3).
- **The recovery change crosses a slice boundary.** D3 changes recovery code and contract text that 120 ships.
- **The tick-time subprocess cost.** `sq` costs about a second per call, so a project with many runs in flight is always near the deadline.

### Mitigation Strategies

- The crash proof asserts the number of `sq run` calls per id at every kill point. The reissue, where duplicates are possible, is designed in issue #9 for 125.
- An entry resolves only on an observed outcome (D2), and recovery never resolves a run that exists (D3). The crash proof covers the run finishing while the process is down.
- D3 is this slice's first code task, applied to 120's merged code with its observer, recovery and contract tests updated in the same commit, before any Runner code depends on it.
- Poll interval, least-recently-polled order and deadline carry-over bound the cost per tick and keep any run from starving (D10). Multi-project scheduling stays Future Work.

## Implementation Notes

### Development Approach

Relative effort: 4/5. Suggested order. Each step leaves the suite green.

1. The settings fields, flags and start-up bounds check (D10), the exit code, and `UpstreamShapeError`.
2. Recovery's `InFlight` answer (D3), with the observer, recovery and summary tests, the public-API pin, and the contract suite's stand-in and oracle updates.
3. `launch.py`, with the stub `sq` run mode and the confirmation tests (D4–D6).
4. `tick.py` with `TickBudget`, `decide.py`, `observe.py` and `finish.py`, with poll cadence, ordering and the block-then-resolve sequence (D1, D2, D10).
5. `faults.py` and `tenant.py`: the one catch, both escalation scopes and closure (D8).
6. `probes.py`, the stub `cf` and `factory.py`. Then compose the Runner in `amoeba start` (D9).
7. The crash proof (`tests/runner/test_crash_recovery.py`). Then the contract documents and the CHANGELOG.

**Stub `sq` run mode.** `sq run <pipeline> --run-id <id> -p …` validates the id against Squadron's rule. It refuses an id that already has state, with exit 1, and refuses unknown flags with exit 2. Otherwise it writes the id's outcome document as still running (`timed_out` to a `--timeout 0` wait), prints `run_id=<id>` on stderr, and sleeps for a duration taken from `SQ_STUB_RUN_SECONDS`. It then writes the final document (`completed` by default, or as `SQ_STUB_RUN_OUTCOME` says) and exits.
- `SQ_STUB_RUN_MODE` forces the failure cases: exit before the line, never print the line, print the line late, or exit 2.
- Every invocation is appended to `SQ_STUB_LOG`. That log is how the crash proof counts launches per id.
- The state documents are the same per-id files 120's `runs wait` mode reads.

**Testing approach.**
- Unit tests inject the clock, the subprocess runner and `Popen`.
- Integration tests put the stub `sq` and `cf` first on `PATH` under a temporary `HOME` and supervisor directory.
- The crash proof follows the contract suite's pattern: it launches the process with `launched.py`, using a test entry point that composes `(*standard_tenants(...), runner_tenant(..., planners=(proof planner,)))`, and kills it with `SIGKILL`. The proof planner launches the stub's no-op pipeline once, for each test node that has no journal entry. The test identifies those nodes by the ids it created, never by title.

### Special Considerations

- **Security.**
  - Launch logs and the stderr tail stored in a block payload may contain whatever Squadron prints. Squadron does not print credentials. The tail is bounded at 4 KiB, and the contract text repeats the rule that a payload must not hold secrets.
  - The inherited environment is passed to `sq` and never recorded.
  - Journal parameters hold paths and ids only.
- **Retention.** Launch logs are never deleted in this slice. A pruning companion for `launch-logs/`, removing logs of resolved entries past retention, can join `amoeba prune` when volume calls for it. A long run's logs also have no size bound. This is accepted in v1, and the same companion can add a bound if a log grows large.
- **No kill, anywhere.** Neither a launch child past its grace period nor a run past any bound is killed. Time bounds per pipeline are 126's routing input.
- **Slice plan and architecture.** The arch ("Unknown escalates" and "Observing a run without blocking the tick") and entry 3's criteria already record these decisions, so no task edits them again:
  - Probe failure: `sq` stops start, and `cf` escalates per link (D9).
  - Polling: at most once per tick, under the poll interval (D10).
  - Recovery leaves existing runs in flight (D3).
  - A launch that exits 2 exits the process, rather than stopping only the Runner tenant (D6).

  Two edits remain. The arch's launch sentence and entry 3's grace criterion still fail a launch at grace expiry, and need D6's overdue rule. Entry 3's description still says "polled once per tick" (D10).
