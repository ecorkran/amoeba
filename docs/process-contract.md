---
docType: reference
project: amoeba
slice: resident-process-and-recovery
dateCreated: 20260921
dateUpdated: 20261023
status: complete
---

# The Amoeba Process Contract

This document is the contract for `amoeba.process` and the `amoeba` CLI. It is
written so that a slice design in 103, 104, 106, 110, 108, or initiative 120 can
proceed **without reading the process implementation**. If you find yourself
opening `host.py` to answer a design question, that is a gap in this document —
say so.

The companion document is [`store-contract.md`](store-contract.md), which covers
the store itself, including the command journal this document's recovery section
depends on.

## What the resident process is

One long-lived process per supervisor directory. It holds the instance lock,
opens every project store **read-write**, reconciles every journaled-but-
unresolved command, and then ticks its *tenants* until it is asked to stop.

The load-bearing idea: **the process is crash-only.** Graceful shutdown and
`kill -9` converge on exactly one recovery path. Shutdown never needs to be
clever, because an in-flight command that outlives the process is precisely what
the journal exists for. Nothing needs cleaning up after a crash — not the lock,
not the PID file, not the store.

## What the resident process is not

- **Not a daemon.** `amoeba start` runs in the foreground and logs to stderr.
  Detaching is the job of whatever launched it (launchd, tmux, a shell `&`).
  There is no double-fork, no log file, no rotation.
- **Not asynchronous.** The host loop is a plain synchronous loop with a stop
  event. See [The tenant obligation](#the-tenant-obligation), which is the
  consequence you must design around.
- **Not a network service.** There is no listener, no IPC, and no port. `stop`
  and `status` need only a signal and two files.
- **Not a decision-maker.** Recovery records what it observed. It never acts on
  the outcome, never re-issues a command, and never routes. That is initiative
  120's job.
- **Not multi-instance.** One process per supervisor directory, enforced by an
  advisory lock. A second `start` refuses.
- **Not available on Windows.** `fcntl` and POSIX signals are assumed. An
  unsupported platform fails at import with an explicit error, not a degraded
  mode.

## The supervisor directory

Resolved by `amoeba.store.paths`, which reads `AMOEBA_STORE_DIR` and otherwise
falls back to XDG and then `~/.config/amoeba`. That is the **only** environment
variable the project reads **for a tunable**. Every process tunable is a CLI
flag instead, so there is never a second source of truth.

*Slice 109:* a credential is not a tunable. `amoeba serve` reads its bearer
token from `AMOEBA_SERVE_TOKEN`, once, at start-up, because a token passed as a
flag would show in `ps`. It is never a field of `ServeSettings` and never
logged. See [`network-contract.md`](network-contract.md).

The directory holds:

| File | Role |
| --- | --- |
| `<project>.sqlite3` | One store per project. |
| `amoeba.lock` | The instance lock. **The truth about liveness.** |
| `amoeba.pid` | JSON: pid, started-at, version. **Informational only.** |
| `launch-logs/` | One stdout and one stderr log per launched `sq_run` entry, named `<entry id>.stdout.log` and `<entry id>.stderr.log`, written by the Runner's detached launch. Created at start; never deleted by Amoeba. They may hold whatever Squadron prints. *(Slice 122.)* |
| `inbox/` | Submissions from outside the process: `tmp/`, `new/`, `quarantine/`, `failed/`. See [`inbox-contract.md`](inbox-contract.md). *(Slice 103.)* |
| `amoeba ingest review --project ID --node NODE_ID --by NAME (--artifact PATH \| --stdout-json PATH) [--upstream-version LABEL] [--id ID]` | Read a Squadron review file, or the captured stdout of `sq review … --output json`, and submit it as a `verdict`. Prints the submission id on stdout and the node, parsed slice (`-` if none), and review type on stderr. Submits and does not wait: read the outcome with `inspect submissions` and `inspect inbox`. Refuses a project with no store file (`SUBMISSION_REFUSED`, nothing written) and opens no store. Works whether or not the process runs. See [`evidence-contract.md`](evidence-contract.md), "Parsing Squadron output". *(Slice 105.)* |

**The lock is the truth; the PID file is a convenience.** The kernel releases an
advisory `flock` when its holder dies by any means, so a stale lock cannot
exist. PID files go stale and PIDs get reused, so nothing decides liveness from
`amoeba.pid`: `stop` confirms the lock is held *before* signalling the recorded
pid, which is why a reused PID is never signalled.

The lock file is never deleted to recover. Deleting it would break the
guarantee, since two processes could then lock two different inodes under one
name.

## The process lifecycle

In order, every time:

1. Acquire the instance lock. If another process holds it, refuse —
   `ExitCode.ALREADY_RUNNING`, and the running process is not disturbed.
2. Write the PID file. (The lock comes first, so a live process can legitimately
   hold the lock with no PID file yet — a state both `stop` and `status` handle
   explicitly.)
3. Open every project store read-write.
4. **Recover every project.** See [Recovery](#recovery).
5. Tick tenants until stop is requested.
6. Close the stores, remove the PID file, release the lock.

Steps 3 and 4 are a gate: **no tenant ticks until every project is reconciled.**
That is what makes it impossible for the Runner to act on a node whose in-flight
command has not been accounted for.

A failure in step 3 or 4 for **any** project aborts the start. The process never
skips a project and never falls back to another store: running while blind to
one project is worse than not running.

**Projects can also be opened at runtime** (slice 103): an applied
`create_project` submission creates the project's store while the process runs,
through `host.open_project`. A new store's journal is empty, so there is nothing
to recover, and the gate above is not reopened.

## The Tenant protocol

Exactly two members:

```python
class Tenant(Protocol):
    @property
    def name(self) -> str: ...
    def tick(self, host: ResidentProcess) -> bool: ...
```

`name` identifies the tenant in logs, including the grace-expiry ERROR.
`tick` does a unit of work and returns whether any work was done.

Tenants are ticked in registration order. When no tenant reports work, the loop
waits on the stop event for `idle_interval_seconds` — it does not busy-loop, and
the wait ends the moment stop is requested.

**`amoeba start` registers four tenants, in this order** (the first three are
`standard_tenants` in `process/tenants.py`; the fourth is `runner_tenant` in
`amoeba.runner`):

1. `InboxTenant` (slice 103). It drains the inbox — see
   [`inbox-contract.md`](inbox-contract.md) — at most `inbox_batch_size` files
   per tick, checking `stop_requested` between files. Registered first so a
   backlog that accumulated while the process was down — `watch_reviews`
   submissions included — drains ahead of any later tenant's work.
2. `ReviewDetectionTenant` (slice 106). See "Review detection" below.
3. `CFWatchTenant` (slice 108). See "Context Forge watch" below. After the inbox,
   so a `link_cf_project` submission is applied before the tenant looks.
4. `RunnerTenant` (slice 122). Observes the project's in-flight `sq_run` entries,
   records the finished ones, and launches what its planners ask for. It is the
   only tenant that starts a subprocess in a tick. No production planner exists
   yet, so nothing launches until slice 125. See "The Runner tenant" below.

What a tenant may use on `host`:

| Member | Meaning |
| --- | --- |
| `store_for(project_id)` | The open read-write store for a project. |
| `project_ids` | Every project this process has open. **Grows at runtime** — see below. |
| `open_project(project_id)` | Create-or-open a project's store read-write and add it to the open set. Idempotent. `project_ids` reflects it at once. Raises on an unsafe project id (before any path is computed) or a store that cannot be opened. *(Slice 103.)* |
| `stop_requested` | Whether shutdown has been requested. **Poll this.** |
| `request_stop()` | Ask the loop to stop. |
| `settings` | The `ProcessSettings` this process was built with. |

> **Do not cache `project_ids`.** It is no longer fixed at startup: a project
> created through the inbox joins it mid-run. Read it each time you need it.
> The Runner in initiative 120 depends on this.

### The tenant obligation

**This is a requirement, not a suggestion, and slices 103 and 120 code against
it:**

> `tick()` must return promptly, and must poll `host.stop_requested` inside any
> long operation.

There is **by decision no per-tick timeout** and no watchdog over a running
tick. A synchronous loop cannot interrupt a tenant that does not return without
threads or signals whose failure modes are worse than the one they fix, and
crash-only already makes an external kill a correct and recoverable remedy.

The consequence of not honoring it is bounded and named:

1. The grace period expires. The process logs at ERROR, naming your tenant.
2. The process exits with `ExitCode.GRACE_EXPIRED`, abandoning the tick in
   place rather than interrupting it.
3. If an operator ran `amoeba stop`, that command reports
   `ExitCode.STOP_TIMEOUT`.
4. The operator kills the process.

An abandoned tick is indistinguishable from `kill -9` and is reconciled by the
same recovery path on the next start. That is *safe*, but it is a human
interruption, and it is yours to avoid.

A tenant that launches a long subprocess polls it and checks `stop_requested`;
it does not block the loop invisibly.

*Tick-time subprocess calls (slice 122).* The shipped inbox, detection and
Context Forge tenants start no subprocess in a tick. A tenant that does (the
Runner) checks a deadline and `host.stop_requested` before **every** call, and
bounds each call by `tick_call_timeout_seconds`. The deadline is
`tick_deadline_seconds` from the start of the tick; it bounds when a call may
begin, so a tick lasts at most the deadline plus one call timeout, and after a
stop request no new call starts. `--tick-call-timeout` must be below
`--shutdown-grace`, so a stop waits for at most one call.

## Hosting tenants

A program that runs its own tenant imports everything it needs from
`amoeba.process` and nothing deeper. The hosting surface is exactly these 23
names (pinned by `tests/test_process_public_api.py`):

| Group | Names |
| --- | --- |
| The host | `ResidentProcess`, `ProcessSettings` |
| Tenants | `Tenant`, `standard_tenants` |
| Recovery observers | `Observer`, `Observation`, `Adopt`, `InFlight`, `NotApplied`, `Unknown` |
| Errors | `ProcessError`, `AlreadyRunningError`, `StartupFailedError`, `GraceExpiredError`, `UpstreamShapeError` |
| Squadron outcomes *(slice 120)* | `SQ_EXECUTABLE`, `RunOutcome`, `OUTCOME_EXIT_CODES`, `RunCheckpoint`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, `poll_run` |

`Observation` is the union `Adopt | InFlight | NotApplied | Unknown`; see "Recovery" below
for what each answer means.

`standard_tenants(settings, supervisor_dir)` returns the three shipped tenants
in the order listed under "The Tenant protocol". `amoeba start` composes the
Runner after them (slice 122):

```python
tenants = (
    *standard_tenants(settings, supervisor_dir),
    runner_tenant(settings, supervisor_dir),
)
```

The Runner ticks after the shipped tenants, so inbox submissions and detection
results from the same pass are visible to it.

`standard_tenants` captures `sq --version` and `cf --version` once, before the
loop. Capture never raises: a missing or slow tool yields the explicit
`unavailable` label. None of these tenants starts a subprocess in a tick.

Run-file parsing (`SquadronRun`, `parse_run_file`) and pruning are internal and
are not part of this surface.

## Review detection

*Added by slice 106.* `ReviewDetectionTenant` notices Squadron reviews nobody in
Amoeba launched — a PM running `sq review` by hand — and records them as
verdicts on the matching slice node, with a detection ledger entry.

**Cadence.** A tick does nothing until `review_scan_interval_seconds` has
passed since its last scan. A scan visits every **active** watch of every open
project once and returns: the tick budget is one pass.

**Baseline.** A watch registered through `watch_reviews` is first baselined:
every top-level `*.md` file already in the directory becomes a silent
`baseline` ledger row, in one transaction, and the watch is marked baselined.
It is all or nothing. A directory that cannot be listed, or any file that
cannot be read, writes nothing and is retried next scan (one WARNING naming
the unreadable file, on a change of reason). A file deleted between listing
and read is left out. Files present at registration are never ingested; use
`amoeba ingest review` for those, oldest round first.

**Settle rule.** A file is examined only once its `(size, mtime_ns)` is
unchanged since the previous scan, so a half-written file is never parsed.
Detection latency is about two scan intervals. The digest is taken from the
bytes actually read.

**Per file** (`review_scan.py`): a `(path, sha256)` already in the ledger is
skipped. Otherwise it is parsed with slice 105's `parse_review_artifact`.
Unparseable → an `unparseable` row with the parser's error. Parsed, but the
review's `slice` matches no slice node or several → an `unattributed` row with
the candidate ids and the parsed record id; nothing is written to any node.
Exactly one match → the verdict and an `ingested` row, in one transaction.
Both refusals are terminal for that digest; changed bytes make a new digest.
**Parser drift:** if Squadron's shape moves and files become `unparseable`,
fix the parser, then re-ingest those files with `amoeba ingest review`.

**The version label** recorded on a detected verdict is the file's own
`squadronVersion` stamp when it carries one; otherwise the `sq --version`
label **captured once at start-up**, before the loop, with `sq_timeout_seconds`
(the explicit `unavailable` marker if that fails). No tick starts a
subprocess. A Squadron upgrade while the process runs is not reflected until
restart.

**Defer (D5).** While a project has an unresolved journal entry of a
review-producing kind (today `sq_run`), its baselined watches are not scanned:
the Runner owns that review. Baselining still happens. One WARNING when a
project starts deferring, one INFO when it resumes. There is no timeout; a
stuck entry shows as `deferred` in `inspect watches`.

**Directories.** Watched directories are expected to be **local**. Listing,
`stat`, and reads run inside the synchronous loop with no timeout, like the
rest of the loop; a directory on a stalled network mount hangs the tick, and
the tenant obligation's remedy applies. A directory that cannot be listed logs
one ERROR when it goes bad and one INFO when it recovers, and never stops the
process. Paths are absolute and stored as given; the same directory under two
spellings is two watches. The tenant never writes into a watched directory.

**A store that cannot record a detection stops the process.** The exception is
logged at ERROR, naming the project and path, and re-raised out of the tick,
which ends `run()`. No attempts counter, no parked state: a store that cannot
record a row is sick.

| Setting | Flag | Default | Meaning |
| --- | --- | --- | --- |
| `review_scan_interval_seconds` | `--review-scan-interval` | 2.0 | Seconds between scans. |
| `sq_timeout_seconds` | `--sq-timeout` | 10.0 | Timeout for `sq --version` at start-up only. |

`amoeba inspect watches --project P` shows each watch with a computed state:
`inactive`; else, in precedence order, `unreachable`, `baseline_pending`,
`deferred`, `ok`. `amoeba inspect detections --project P [--outcome O]` shows
the ledger, with `recorded_since` true once a verdict with the row's record id
exists.

## Context Forge watch

*Added by slice 108.* `CFWatchTenant` notices Context Forge pointer moves by
taking one `stat` of CF's `projects.json` per `cf_scan_interval_seconds`, and
records a snapshot per linked project whose watched fields changed. What it
records, the outcomes, and the file's shape are
[`context-forge-contract.md`](context-forge-contract.md)'s subject. The process
semantics are the same as review detection's: a file that cannot be read is
logged once going bad and once recovering and never stops the process; a store
that cannot record a snapshot is logged at ERROR and stops it; no tick starts a
subprocess. `cf --version` is captured once at start-up with `cf_timeout_seconds`.

| Setting | Flag | Default | Meaning |
| --- | --- | --- | --- |
| `cf_data_dir` | `--cf-data-dir` | `~/.config/context-forge` | Directory holding `projects.json`. `CONTEXT_FORGE_DATA_DIR` is not read. |
| `cf_scan_interval_seconds` | none | 1.0 | Seconds between checks. |

`amoeba inspect cf-links --project P` and `amoeba inspect cf-snapshots --project
P` show the links and the recorded snapshots.

## The Runner tenant

*Slice 122.* `RunnerTenant` (`amoeba.runner`, imported only by `amoeba.cli`) is
composed by `amoeba start` after the shipped tenants. Each tick, for every
project, it runs: **observe** the unresolved `sq_run` entries, **record** each
finished run, **decide** (pure: a `Planner` sees a frozen `ProjectView` and
returns actions), **act** (journal a command, then launch it), and **close** any
project escalation whose fault did not recur. The production planner tuple is
empty, so nothing launches until slice 125; tests supply their own planner.

- **The only control command is `sq_run`.** The entry is journaled with
  `pipeline`, `params`, a minted `run_id` and the `checkout` directory before
  anything is launched, and stays unresolved until the run is finished.
- **Launch.** `sq run <pipeline> --run-id <id> -p k=v …` starts detached: its own
  session, stdin from `/dev/null`, stdout and stderr to
  `launch-logs/<entry id>.{stdout,stderr}.log`. It is confirmed by a stderr line
  exactly equal to `run_id=<id>`, or by Squadron reporting a state for the id. A
  child that exits before the line, with no state, fails the launch (the node
  blocks on a human, the entry resolves `failed`). A child still alive past
  `--launch-grace` with no state is *overdue*: the entry stays unresolved, a
  `launch_overdue` project escalation is raised, and the launch keeps being
  polled. A child that exits 2 with no state exits the process with
  `UPSTREAM_SHAPE` (15).
- **Resolution.** An entry resolves `completed` when the command ran and
  reported an outcome, including a `failed` or `paused` run (the node blocks on a
  human, and the run's outcome is in the entry's `result`). It resolves `failed`
  when the command could not finish: an `orphaned` or vanished run, or a launch
  that failed.
- **Observation** is by run id with `poll_run`, at most once per tick per run and
  no more often than `--run-poll-interval`, least recently polled first.
- **Faults.** One `except Exception` per project, in `tenant.py`. A store failure
  or an `UpstreamShapeError` re-raises and the process exits. Anything else is
  logged and escalated: the node in context blocks on a human when it has no run
  in flight and is not done; otherwise a project-scoped escalation is raised.
  Expected faults (`run_observation_failed`, `launch_overdue`, `cf_probe_failed`)
  are project-scoped escalations; one open row exists per project and kind.
- **Probes.** `sq runs wait <fresh id> --timeout 0 --json` must answer
  `not_found` before the loop starts, or `start` exits `STARTUP_FAILED`. Each
  Context Forge link is probed once per lifetime (`cf status --json -p <id>` and
  `cf list initiatives --json -p <id>`); a failing link raises `cf_probe_failed`
  for its project and the others carry on.
- **Crash safety.** Recovery leaves an existing run in flight; the Runner's first
  tick polls it and records it. A kill before `Popen` leaves an entry with no run,
  which recovery marks `not_applied` once the launch grace period has passed. The
  Runner does not relaunch it; the reissue is slice 125's (issue #9).

## Lifecycle failure modes

Three cases where the process must decide rather than converge. Each is
enumerated deliberately.

### Lock held, PID file absent or unreadable

The start sequence takes the lock before writing the PID file, so a live process
can legitimately be in this state; a truncated or non-JSON PID file presents
identically.

- `stop` does **not** guess a signal target. It reports
  `ExitCode.NO_STOP_TARGET`, names the lock path, and **signals nothing**.
- `status` reports `running (pid unknown)`.

The remedy is the operator's, and it is safe because the lock, not the PID file,
is what says something is alive.

### Grace period expires

The loop stops ticking new work as soon as the stop event is set; the grace
period bounds only the **current** tick. On expiry the process logs at ERROR
naming the tenant that did not return, closes its stores, and exits with
`ExitCode.GRACE_EXPIRED` without waiting further. It never escalates to killing
its own thread.

### A tenant hangs

By decision, there is no per-tick timeout — see
[The tenant obligation](#the-tenant-obligation). The observable consequence is
the grace-expiry path above.

## Recovery

On start, per project store, per unresolved journal entry, oldest first:

```
observer = registry[entry.kind]        # absent → Unknown
observation = observer.observe(entry)
  Adopt(result)      → journal_resolve(outcome=adopted,     resolved_by=recovery)
  InFlight(run, …)   → nothing resolved; logged; left for its issuer to finish
  NotApplied(reason) → journal_resolve(outcome=not_applied, resolved_by=recovery)
  Unknown(reason, …) → journal_escalate(entry, reason)
```

Five properties you may rely on:

1. **Journal before side effect.** `journal_issue` commits before returning, so
   a crash immediately afterward leaves a durable unresolved entry.
2. **Observe, never re-issue.** Recovery calls observers and the store, and
   nothing else. There is no code path that re-runs a command.
3. **Exactly one adopted.** The only route to `adopted` is, for a legacy entry
   (journaled before slice 120, with no run id), exactly one matching candidate.
4. **An existing run is left in flight.** An id-bearing `sq_run` entry whose run
   exists is left unresolved, in flight, for its issuer to finish. Recovery
   neither resolves it nor records anything on it (slice 122). The gate still
   holds: before any tenant ticks, every entry is resolved or tied to a run
   Squadron reports. A host without the Runner leaves such entries open, and
   detection stays deferred for that project.
5. **Everything else escalates.** Zero candidates, several candidates, an
   unregistered kind, an unreadable upstream, a parse failure, a missing
   required field — all become outcome `unknown` plus a `blocked_on_human` node
   whose blocked-state context names the journal entry.

Each entry is reconciled in **its own transaction**, so recovery is itself
crash-safe: a second crash partway through re-runs only what is still
unresolved, and no entry is ever reconciled twice.

An unexpected exception from an observer is logged and re-raised, aborting
startup. Recovery that cannot complete must not let tenants run against
unreconciled state.

A per-project summary is logged before the loop is entered, including
`nothing to reconcile`.

### The Observer protocol

```python
class Observer(Protocol):
    def observe(self, entry: JournalEntry) -> Observation: ...


Observation = Adopt | InFlight | NotApplied | Unknown  # frozen dataclasses
```

An observer **never** issues, retries, or repairs anything. Expected external
failure is reported as `Unknown`, not raised — those are answers, not bugs.

`Adopt` carries the `result` mapping to record. `InFlight(run_id, status)`
means the command reached its system and is not finished (`status` is the
upstream's own word for the run's state, opaque to recovery): recovery resolves
nothing and leaves the entry for its issuer. `NotApplied` is returned only by
an observer that can genuinely distinguish "did not happen" from "cannot tell".
`Unknown` carries a human-readable `reason` and any `candidates`.

**`not_applied` for an `sq_run` means "no run state after the launch grace
period", not proof that the run never started.** A run whose state was later
removed (for example by `sq runs prune`) answers the same way. An issuer that
would reissue after a `not_applied` `sq_run` must first check its launch log and
poll once more; recovery never reissues anything.

Initiative 120 may register observers for command kinds it adds. Adding a kind
means three things, all of them: an enum member, its required parameter keys,
and an observer. A kind with no observer escalates rather than being skipped.

### The two shipped observers

**Squadron runs** (`sq_run`) are recovered by a dispatcher on whether the entry's
parameters carry a `run_id` key. `run_id` is a required `sq_run` parameter key,
so every entry journaled since slice 120 has one.

*By id.* The by-id observer asks Squadron for that one run:
`sq runs wait <id> --timeout 0 --json`, bounded by `--sq-timeout`. It never reads
a run-state file. Any of the six outcomes that mean Squadron holds a state
(`completed`, `failed`, `paused`, `timed_out` — still running — `unknown_status`,
`orphaned`) answers `InFlight(run_id, status)` (`status` is the outcome's value): the entry stays unresolved and
the summary counts it as `in_flight`. What an orphaned or unknown-status run
means is the Runner's decision, not recovery's. `unreadable`, a missing `sq`, a timeout, exit 2, output that is not
JSON, an outcome that disagrees with the exit code, a document for another run,
a run id already recorded on another entry, and a `run_id` that is not a
non-empty string each escalate (`unknown`) with a reason naming the cause.

*Launch grace.* On `not_found`: with no `issued_at` the entry escalates. Inside
`issued_at + --launch-grace` (default 60 s) the launch may still be creating its
run, so recovery waits out the remainder (never more than one grace period),
polls once more, and then leaves it in flight, escalates, or marks the entry `not_applied`.
Past the grace period the entry is `not_applied` at once. A start-up after a
crash within one grace period of a launch therefore stalls by at most the grace
still remaining; each id-bearing entry makes at most two polls.

*Legacy.* An entry without a `run_id` key (a row from before slice 120) goes to
the attribute matcher below, unchanged. It reads
`~/.config/squadron/runs/*.json`, lazily: a pass with no legacy entry reads no
run-state file, and a pass with legacy entries scans the directory once. A run
is a candidate when **all four** hold:
the pipeline is equal compared lower-cased; every journaled `params` key is
present in the run's params with an equal value (**subset**, because Squadron
persists definition defaults merged with the caller's overrides); `started_at`
is no earlier than `issued_at` minus the clock tolerance; and its `run_id` is not
already recorded in another entry's result. Exactly one candidate adopts,
recording the `run_id` and the run file's own `schema_version` as provenance.
Anything else escalates.

The matcher cannot distinguish a never-issued run from a pruned one — both
present as zero matches, and both escalate.

**The ownership guarantee.** A run is Amoeba's, for pruning, when some journal
entry's `result` carries its `run_id` (`recorded_result_run_ids`), whatever the
entry's outcome or kind. Two writers put it there: recovery, on `adopted`, and
the issuer. **An issuer of an `sq_run` command must include `run_id` in the
`result` it resolves the entry with**; `record_runner_report` refuses an
`sq_run` entry whose `result` lacks it. A run that breaks this rule is simply
never pruned. An escalated (`unknown`) entry has no result, so the run behind it
is never owned; a human resolves the escalation and that run is theirs to prune
with `sq runs prune`.

**Context Forge read-back** (`cf_write`) compares `cf get --json` output against
the entry's `expected` mapping. All present and equal adopts; any present and
differing is `not_applied`; any **absent** field is `Unknown`, because a field
CF does not carry cannot be compared. Adoption records the project record's own
`updatedAt` and an opaque `cf --version` label captured once per recovery pass.
If that capture fails, the label is recorded as unavailable and the adoption
still succeeds — provenance capture never turns a clean adoption into an
escalation.

**No code compares an upstream version number.** Versions are recorded as
provenance and never parsed, ordered, or branched on.

## The CLI

| Command | Behavior |
| --- | --- |
| `amoeba start` | Foreground. Refuses if the lock is held. Logs a recovery summary per project before entering the loop. |
| `amoeba stop` | Confirms the lock is held, sends `SIGTERM` to the recorded pid, waits for release. **Never escalates to `SIGKILL`.** |
| `amoeba status` | `running` (pid, start time, version), `running (pid unknown)`, `stopped (stale pid file)`, or `stopped`. |
| `amoeba inspect projects\|inbox` | Supervisor-level: project ids with a store; inbox files pending, quarantined, or failed. Open no store. |
| `amoeba inspect nodes\|blocked\|journal\|submissions\|messages --project ID` | Read-only listings. `journal` accepts `--unresolved`; `messages` accepts `--channel`. All accept `--json`. |
| `amoeba submit create-project\|resolution\|intent ...` | Write one submission to the inbox and print its id. Opens no store; works whether or not the process runs. See [`inbox-contract.md`](inbox-contract.md). *(Slice 103.)* |
| `amoeba prune sq-runs [--yes]` | Previews the paused Squadron runs Amoeba may prune; with `--yes`, asks `sq runs prune` to delete them. Read-only on every store. See "Pruning paused runs". *(Slice 110.)* |
| `amoeba serve [--host] [--port] [--tls-cert --tls-key]` | A second, foreground process serving reads, submissions, and the feed over HTTP. Independent of the resident process: no lock, no PID file, works with it stopped. See [`network-contract.md`](network-contract.md). *(Slice 109.)* |

`start` exposes every loop-governing `ProcessSettings` tunable as a flag:
`--idle-interval`, `--shutdown-grace`, `--clock-tolerance`, `--cf-timeout`,
`--sq-runs-dir`, `--inbox-batch-size`, `--inbox-max-attempts`,
`--review-scan-interval`, `--sq-timeout`, `--cf-data-dir`, `--launch-grace`,
`--tick-deadline`, `--tick-call-timeout`, `--run-poll-interval`.
`--clock-tolerance` and `--sq-runs-dir` are used only by legacy matching.
`--launch-grace SECONDS` (slice 120) is how long after a launch Squadron may still
be creating the run; recovery reads it, and the Runner reads the same value to
confirm launches. *(Slice 122.)* `--tick-deadline SECONDS` (default 5) is how long
after a tick starts the Runner may still begin a subprocess call;
`--tick-call-timeout SECONDS` (default 8) bounds each call and must be below
`--shutdown-grace`; `--run-poll-interval SECONDS` (default 15) is the least time
between two polls of one run. All three must be positive, or `start` exits
`STARTUP_FAILED`. `--sq-timeout` also bounds the `sq` probe at start. `stop` exposes the one tunable it consumes: `--stop-timeout`.

### Exit codes

Every status, and the condition that produces it. Defined once in
`amoeba.cli.main.ExitCode`; there is no bare integer at any call site.

| Code | Name | Produced when |
| --- | --- | --- |
| 0 | `OK` | The command did what it was asked to do. |
| 1 | `FAILURE` | An unexpected failure reached the process boundary. A traceback is logged. |
| 2 | `ALREADY_RUNNING` | `start`: another process holds the instance lock. The running process is untouched. |
| 3 | `NOT_RUNNING` | `stop`: nothing holds the instance lock. |
| 4 | `STOP_TIMEOUT` | `stop`: the process did not release the lock before `--stop-timeout`. No `SIGKILL` follows. |
| 5 | `NO_STOP_TARGET` | `stop`: the lock is held but the PID file is absent or unreadable. **Nothing was signalled.** |
| 6 | `GRACE_EXPIRED` | `start`: a tenant did not return within `--shutdown-grace`. |
| 7 | `STARTUP_FAILED` | `start`: a store could not be opened, or recovery could not complete, for any project; **or** the Runner's `sq` probe failed (`sq runs wait <id> --timeout 0 --json` did not answer `not_found` for a fresh id); **or** a tick bound was not positive or `--tick-call-timeout` was not below `--shutdown-grace`. **Also** any store error that stops a running process — including an inbox apply that fails below its attempt limit — since the boundary maps every `StoreError` here, except `VerdictNotFoundError` (`NOT_FOUND`). |
| 8 | `NOT_RUNNING_STATUS` | `status`: the supervisor is not running. Not a failure — it distinguishes running from stopped by exit status alone. |
| 9 | `SUBMISSION_REFUSED` | `submit` and `ingest review`: the submission was invalid or could not be written, or (`ingest review`) the project has no store. Nothing was left in the inbox. *(Slice 103.)* |
| 10 | `NOT_FOUND` | `inspect`: a record named on the command line (e.g. `changes --verdict ID`) does not exist. *(Slice 104.)* |
| 11 | `NOT_COMPARABLE` | `inspect changes`: the review failed or was unparsed, so it has no changes to report. *(Slice 104.)* |
| 12 | `REVIEW_UNREADABLE` | `ingest review`: the file could not be read or parsed, or the review has no version label (or one that disagrees with its stamp). Nothing was left in the inbox. *(Slice 105.)* |
| 13 | `SERVE_REFUSED` | `serve`: the bind policy refused the configuration (`token_required`, `tls_required`, `token_too_short`, `tls_unusable`). Nothing was bound. A bind failure at start-up (a port in use) is `FAILURE` (1), not uvicorn's own status. On `SIGTERM` the server exits by the signal after its shutdown grace. *(Slice 109.)* |
| 14 | `PRUNE_INCOMPLETE` | `prune sq-runs --yes`: a candidate is still present after `sq` ran, or `sq` is missing, failed, or timed out. Every remaining candidate is printed. Amoeba deleted no file. *(Slice 110.)* |
| 15 | `UPSTREAM_SHAPE` | `start`: a launch child exited 2 and left no run, so a Squadron shape the Runner needs (`sq run … --run-id`) is missing. The launch is recorded failed first. *(Slice 122; 8 was already `NOT_RUNNING_STATUS`.)* |

## Pruning paused runs

`amoeba prune sq-runs` offers the paused Squadron runs Amoeba is finished with.
**Amoeba chooses, Squadron deletes, a human confirms.** It opens every store
read-only, so it works with the resident process running or stopped.

**Which runs.** Amoeba asks Squadron about each owned run with
`sq runs wait <id> --timeout 0 --json` and decides from the outcome document it
gets back, never from a run-state file. A run is a candidate only if **all
five** hold, and a null in any of them makes it a non-candidate:

1. Amoeba owns it: its id is in some project's `recorded_result_run_ids` (see
   "The ownership guarantee").
2. Its `outcome` and its `status` both say `paused`, and `checkpoint.paused_at`
   is present and timezone-aware.
3. No node in any project that is not `done` names it in `sq.run_id`. This is
   stricter than "no open checkpoint": after a human resolves a checkpoint the
   node is runnable and the Runner has not yet issued `sq run --resume`, and
   pruning then would delete the run it is about to resume. "Every node that
   names it is done" is the earliest point at which Amoeba is provably finished
   with a run. The rule reads each node's *current* `sq.run_id`, never history.
4. Its `updated_at` is present, timezone-aware, and at least `PRUNE_RETENTION`
   (7 days, in `process/run_pruning.py`, with no flag) before now.

Runs the PM launched fail condition 1 and are never touched.

**Preview and `--yes`.** The default is a preview: the candidates (`run_id`,
pipeline, `updated_at`, owning project) and how many owned paused runs were
kept. Deleting another tool's files is not reversible, so `--yes` is required,
and it mirrors `sq runs prune`. Nothing from a preview is saved: `--yes` re-reads
every store, polls every owned run, and selects again immediately before it calls
`sq runs prune <ids…> --yes` once, with non-TTY stdin and a 30 s timeout. Amoeba
never deletes a run itself, even when `sq` is missing or too old to have the
command; the candidates then stay, and the command reports `PRUNE_INCOMPLETE`.

**The outcome is observed, not parsed.** `sq runs prune` has no JSON output and
its text is not a contract. Its exit status is printed but never decides the
result: it exits 1 for a file someone else already removed, which is still the
goal state. After `sq` exits or times out, Amoeba polls each candidate again:
`not_found` means removed, and anything else, including a failed poll, means still
present. Every candidate gone is success. Any candidate still present, including
one `sq` refused as live, is printed with `sq`'s exit status and stderr, and the command
exits `PRUNE_INCOMPLETE` (14). Running it again converges, because it selects
afresh.

**Unknown is a value, never a guess.** A store that cannot be read refuses the
whole command before `sq` is called, because the held set would be incomplete. A
run whose outcome cannot be read (`sq` missing, a timeout, an unexpected exit, a
document that does not parse) is printed on stderr as
`could not check: <id> (<reason>)` and is never a candidate; the preview still
exits `OK`. A run with no `paused_at` or no `updated_at` is never a candidate.

**Two narrow windows, and what initiative 120 must do.** The stores are read one
project at a time, not as one snapshot, and a run linked again to a node between
selection and deletion is not yet covered (`sq` itself refuses to prune a live
run, which covers a resume that has started). Both windows are narrow, and the
failure is explicit: a later `sq run --resume <id>` fails on the missing run.
**Requirement for initiative 120 (PM confirmed 20261020):** a resume whose run
is missing is a failed command. The journal entry resolves with that outcome, the
node blocks on a human, and the run is never relaunched automatically.

**No runs-directory flag, and no runs directory.** Pruning reads no run-state
file, so there is no directory to point it at: it selects from what Squadron
reports and Squadron deletes the same runs. Tests put a stub `sq` first on `PATH`
instead (`tests/sq_stub.py`).

**No journal entry.** Pruning is not issued by the resident process, writes
nothing to the store, and converges. Command-before-result exists so recovery can
learn the outcome of a command the store depends on; no store state depends on
whether a paused run's file still exists, and the store's `sq.run_id` references
stay as history.

## Inspection

`amoeba inspect` opens every store with `Store.open_read_only`. It **never
migrates, never creates, and cannot write** — the handle is SQLite `mode=ro`,
measured against this project's Python and SQLite build rather than assumed.
Listings work identically whether the resident process is running or stopped.

Listings are declared in one registry (name → query → columns). Slice 104 adds
`findings` and `verdicts` by registering them, not by editing the CLI. Subcommand
names derive from the registry, never the reverse.

A store at an unexpected schema version raises rather than being migrated, and
inspecting a project with no store does not create one.

## The writer model

Two parts, both mechanical:

1. **The instance lock** guarantees at most one resident process per supervisor
   directory.
2. **A guard test** (`tests/test_writer_guard.py`) walks the AST of every module
   under `src/amoeba/` and fails if any module other than
   `process/project_stores.py` calls the read-write `Store.open`. *(Slice 103
   moved read-write opening there from `process/host.py`, which now delegates;
   the permitted set is still exactly one module.)*

Parts outside the process never write a store: they submit to the inbox, and
the process applies what they submit. `amoeba.inbox` never imports `Store`.

Stated honestly: this does not stop a third party importing `amoeba.store` and
writing. Nothing in a library can. It makes the mistake impossible to make *by
accident inside Amoeba*, which is the realistic failure.

## Security

Journal `parameters` and `result` are stored verbatim and are **shown by
`amoeba inspect`**, including in `--json` output that may be piped into logs or
tickets.

> **Callers must not place secrets in journal parameters or results.** The same
> holds for inbox submission payloads and message payloads (slice 103), which
> are stored and shown the same way.

This applies to every caller that issues a journaled command, including the
Runner in initiative 120. Store a reference — a path, an id, a key name — not
the secret itself. A blocked-state payload is covered too: the Runner stores the
last 4 KiB of a failed launch's stderr there, and Squadron prints no credentials.
Launch logs under `launch-logs/` hold whatever Squadron prints; the inherited
environment is passed to `sq` and is never logged or journaled.

The supervisor directory is created with the user's default permissions, as in
slice 101. No new exposure is introduced.

## Testing against the process

- Point `AMOEBA_STORE_DIR` at a `tmp_path` directory. Never at the real
  supervisor directory.
- Put a stub `sq` first on `PATH` (`tests/sq_stub.py`), with `HOME` at a scratch
  directory: recovery and pruning ask `sq runs wait`, and the real Squadron is
  never asked. Pass `--sq-runs-dir` at a throwaway directory only for legacy
  matching, never at the real Squadron runs directory.
- Nothing about locking or signal handling is mocked anywhere in this project's
  tests, deliberately: mocks cannot validate `flock` or POSIX signals. Tests
  drive real subprocesses and send real signals.
- `tests/host_harness.py` builds a real `ResidentProcess` in a subprocess with a
  throwaway tenant. Both `tests/test_host.py` and `tests/load/` use it.
- The load tier is excluded from the default suite; run it with
  `uv run pytest tests/load`.

## Future work

Named here so a downstream design knows what is *not* coming for free:

- **Reissue after `not_applied`.** Squadron now takes a caller-supplied run id,
  so a launch is found by id; recovery marks a launch with no state after the
  grace period `not_applied`. Deciding whether to reissue it is the Runner's
  (launch-log check, then one more poll; see "The Observer protocol").
- **Journal retention.** Entries are never deleted in this slice.
- **A per-tick budget**, should a real tenant prove unable to honor the tenant
  obligation. Revisit then, not speculatively.
