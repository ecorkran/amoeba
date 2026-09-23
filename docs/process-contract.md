---
docType: reference
project: amoeba
slice: resident-process-and-recovery
dateCreated: 20260921
dateUpdated: 20260923
status: complete
---

# The Amoeba Process Contract

This document is the contract for `amoeba.process` and the `amoeba` CLI. It is
written so that a slice design in 103, 104, 105, 106, 107, or initiative 120 can
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
variable the project reads. Every process tunable is a CLI flag instead, so
there is never a second source of truth.

The directory holds:

| File | Role |
| --- | --- |
| `<project>.sqlite3` | One store per project. |
| `amoeba.lock` | The instance lock. **The truth about liveness.** |
| `amoeba.pid` | JSON: pid, started-at, version. **Informational only.** |
| `inbox/` | Submissions from outside the process: `tmp/`, `new/`, `quarantine/`, `failed/`. See [`inbox-contract.md`](inbox-contract.md). *(Slice 103.)* |

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

**`amoeba start` registers one tenant, `InboxTenant`, first** (slice 103). It
drains the inbox — see [`inbox-contract.md`](inbox-contract.md) — at most
`inbox_batch_size` files per tick, checking `stop_requested` between files.
Registered first so a backlog that accumulated while the process was down
drains ahead of any later tenant's work.

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
  NotApplied(reason) → journal_resolve(outcome=not_applied, resolved_by=recovery)
  Unknown(reason, …) → journal_escalate(entry, reason)
```

Four properties you may rely on:

1. **Journal before side effect.** `journal_issue` commits before returning, so
   a crash immediately afterward leaves a durable unresolved entry.
2. **Observe, never re-issue.** Recovery calls observers and the store, and
   nothing else. There is no code path that re-runs a command.
3. **Exactly one adopted.** The only route to `adopted` is exactly one candidate
   passing every matching condition.
4. **Everything else escalates.** Zero candidates, several candidates, an
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


Observation = Adopt | NotApplied | Unknown  # frozen dataclasses
```

An observer **never** issues, retries, or repairs anything. Expected external
failure is reported as `Unknown`, not raised — those are answers, not bugs.

`Adopt` carries the `result` mapping to record. `NotApplied` is returned only by
an observer that can genuinely distinguish "did not happen" from "cannot tell".
`Unknown` carries a human-readable `reason` and any `candidates`.

Initiative 120 may register observers for command kinds it adds. Adding a kind
means three things, all of them: an enum member, its required parameter keys,
and an observer. A kind with no observer escalates rather than being skipped.

### The two shipped observers

**Squadron runs** (`sq_run`) matches journaled commands against
`~/.config/squadron/runs/*.json`. A run is a candidate when **all four** hold:
the pipeline is equal compared lower-cased; every journaled `params` key is
present in the run's params with an equal value (**subset**, because Squadron
persists definition defaults merged with the caller's overrides); `started_at`
is no earlier than `issued_at` minus the clock tolerance; and its `run_id` is not
already recorded in another entry's result. Exactly one candidate adopts,
recording the `run_id` and the run file's own `schema_version` as provenance.
Anything else escalates.

Squadron cannot distinguish a never-issued run from a pruned one — both present
as zero matches, and both escalate.

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

`start` exposes every loop-governing `ProcessSettings` tunable as a flag:
`--idle-interval`, `--shutdown-grace`, `--clock-tolerance`, `--cf-timeout`,
`--sq-runs-dir`, `--inbox-batch-size`, `--inbox-max-attempts`. `stop` exposes the
one tunable it consumes: `--stop-timeout`.

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
| 7 | `STARTUP_FAILED` | `start`: a store could not be opened, or recovery could not complete, for any project. **Also** any store error that stops a running process — including an inbox apply that fails below its attempt limit — since the boundary maps every `StoreError` here. |
| 8 | `NOT_RUNNING_STATUS` | `status`: the supervisor is not running. Not a failure — it distinguishes running from stopped by exit status alone. |
| 9 | `SUBMISSION_REFUSED` | `submit`: the submission was invalid or could not be written. Nothing was left in the inbox. *(Slice 103.)* |

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
the secret itself.

The supervisor directory is created with the user's default permissions, as in
slice 101. No new exposure is introduced.

## Testing against the process

- Point `AMOEBA_STORE_DIR` at a `tmp_path` directory. Never at the real
  supervisor directory.
- Pass `--sq-runs-dir` at a throwaway directory. Never at the real Squadron runs
  directory.
- Nothing about locking or signal handling is mocked anywhere in this project's
  tests, deliberately: mocks cannot validate `flock` or POSIX signals. Tests
  drive real subprocesses and send real signals.
- `tests/host_harness.py` builds a real `ResidentProcess` in a subprocess with a
  throwaway tenant. Both `tests/test_host.py` and `tests/load/` use it.
- The load tier is excluded from the default suite; run it with
  `uv run pytest tests/load`.

## Future work

Named here so a downstream design knows what is *not* coming for free:

- **Caller-supplied Squadron run ids** (dependency S9) would remove the
  journaled-but-never-issued ambiguity entirely. Until then, that narrow crash
  window costs a human interruption.
- **Journal retention.** Entries are never deleted in this slice.
- **Pruning Squadron's paused runs** — slice 106.
- **A per-tick budget**, should a real tenant prove unable to honor the tenant
  obligation. Revisit then, not speculatively.
