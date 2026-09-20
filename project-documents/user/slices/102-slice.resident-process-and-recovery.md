---
docType: slice-design
slice: resident-process-and-recovery
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101]
interfaces: [103, 104, 105, 106, 107]
dateCreated: 20260919
dateUpdated: 20260919
status: not_started
---

# Slice Design: resident-process-and-recovery

## Overview

Slice 101 shipped a library: a test can open a store, write nodes, and query them, but nothing runs, nothing enforces the sole-writer model, and nothing remembers that a side-effecting command was in flight when the process died. This slice adds the three things that turn the library into a substrate:

1. **The resident process** — one long-lived, per-supervisor process with a start/stop/status lifecycle, single-instance enforcement, and graceful shutdown. It hosts *tenants* (the Runner in initiative 120, the inbox apply loop in slice 103) and is the only thing that opens a store read-write.
2. **The command journal and recovery** — an entry is committed *before* a side-effecting command is issued and resolved when its result arrives. On start, every journaled-but-unresolved entry is reconciled **by observing the external system**, never by re-issuing. Exactly one match is adopted; anything else becomes an explicit `blocked_on_human` node carrying the journal entry.
3. **The inspection surface** — `amoeba inspect`, a read-only CLI over store contents, so nobody has to write a client or open `sqlite3` by hand to see what the process believes.

The design is deliberately **crash-only**: graceful shutdown and `kill -9` converge on the same recovery path. Shutdown never needs to be clever, because an in-flight command that outlives the process is exactly what the journal exists for.

## Value

Architectural enablement. The concept's single load-bearing decision — *a checkpoint is a persisted blocked-state, not a blocking call* — is only true if the thing holding the state can die and come back without guessing. After this slice:

- Initiative 120 has a host to run inside and a two-call journal API (`journal_issue` / `journal_resolve`) that makes every Runner command restart-safe without the Runner implementing recovery.
- Slice 103 has a process to append into and a tenant seam for its apply loop.
- The sole-writer model stops being a convention in a contract document and becomes a held lock plus a mechanical guard test.
- The PM can run `amoeba status` and `amoeba inspect` and see real state.

This is the highest-risk slice in initiative 100 and is sequenced second so that its problems surface before four more slices depend on it.

## Technical Scope

**Included**

- `amoeba` console script with `start`, `stop`, `status`, and `inspect` subcommands.
- Single-instance enforcement per supervisor (advisory file lock) and an informational PID file.
- Signal-driven graceful shutdown with a bounded grace period.
- The host loop and the `Tenant` protocol that 103 and 120 plug into. This slice ships **no tenants**: the process starts, recovers, idles, and stops.
- Command journal: schema migration `003`, closed vocabularies, store API, contract documentation.
- Recovery: the reconcile protocol, the `Observer` protocol, and the two observers the slice plan names — Squadron runs-directory matching and Context Forge read-back.
- Read-only store open, and a guard test that only the resident process opens a store read-write.
- Inspection listings for projects, nodes, blocked states, and journal entries, with `--json`.
- A load-test tier (`tests/load/`), which the Python rules require now that concurrency and process boundaries enter the codebase.

**Excluded**

- The Runner, routing, and any decision about *what* to do after recovery — initiative 120. Recovery records outcomes; it does not act on them.
- The inbox, channels, and apply loop — slice 103.
- Findings and verdict tables, and therefore their inspection listings — slice 104 (see Decisions, D4).
- Change feed and filesystem detection — slice 105.
- Self-daemonizing, launchd/systemd units, log rotation (see D1).
- Any network listener. Stop and status need no IPC beyond a signal and two files.
- Windows. `fcntl` and POSIX signals are assumed; an unsupported platform fails at import with an explicit error, not a degraded mode.
- Pruning of Squadron's paused runs — slice 106.

## Dependencies

### Prerequisites

- **Slice 101 (complete, merged at `eb310f0`)** — `Store`, the migration mechanism (`EXPECTED_SCHEMA_VERSION = 2`), typed failure modes, central path resolution, `block()`.
- **`pydantic`** — first runtime dependency (see D3). Used only at the Squadron run-file and `cf get --json` parsing boundaries.
- **Squadron run-state files** as an observed external format (`src/squadron/pipeline/state.py`).
- **`cf` CLI** on `PATH` for read-back.

**Upstream versions are not pinned.** Squadron and Context Forge are both under active development and will keep moving while this slice is built; both had already moved past the versions the architecture document records by the time this design was written (observed 20260919: SQ 0.12.5, CF 0.15.0 — a dated observation, not a requirement). This slice depends on *shapes*, not versions: the handful of fields listed below. The observers tolerate unknown fields, treat a missing required field as `Unknown`, and record the run file's own `schema_version` in the journal result as provenance. No code compares against an upstream version number, and a version bump alone is never a reason to revisit this design — a change to one of the listed facts is.

### Interfaces Required

From slice 101, all public contract: `Store.open`, `get_node`, `nodes_for_project`, `blocked`, `block(node_id, *, kind=, context=)`, the `StoreError` family, `amoeba.store.paths` central-directory resolution, and the numbered-migration mechanism.

From Squadron, read-only, header fields of `~/.config/squadron/runs/*.json` only: `schema_version`, `run_id`, `pipeline`, `params`, `started_at`, `status`. Facts this design relies on, each checked in source:

- Run ids are generated inside `init_run`; the CLI offers no way to supply one (dependency S9 still open).
- `pipeline` is lower-cased before it is persisted.
- Persisted `params` are the pipeline definition's defaults **merged with** the caller's overrides — not just what the caller passed.
- Files are written atomically (write `.tmp`, then rename), so a partially-written `.json` is never observed.
- Completed and failed runs beyond the newest 10 per pipeline are pruned at the start of each new run. Paused runs are never pruned.
- The runs directory has no environment override.

## Architecture

### Component Structure

```
src/amoeba/
  cli/
    main.py            argparse entry point; subcommand dispatch; exit codes
    lifecycle.py       start / stop / status
    inspect.py         read-only listings
  process/
    settings.py        ProcessSettings — every tunable, defined once
    instance_lock.py   InstanceLock (flock) + PID file
    host.py            ResidentProcess, Tenant protocol, signal handling
    recovery.py        reconcile protocol, Observer protocol, Observation types
    observers/
      sq_runs.py       Squadron runs-directory matcher
      cf_readback.py   Context Forge read-back comparer
  store/
    journal.py         JournalMixin (joins Store alongside nodes/blocking)
    journal_models.py  CommandKind, JournalOutcome, JournalResolver, JournalEntry
    sql_journal.py     every journal statement and column name
    schema/003_command_journal.sql
```

`sql.py` is already at 306 lines and `models.py` at 200, so journal SQL and journal models get sibling modules rather than pushing either file further past budget. The slice 101 discipline is unchanged: every statement and column name is defined once, in a `sql*` module.

**`ResidentProcess`** owns the lifetime: acquire lock → write PID file → open stores → recover → tick tenants until stop is requested → close stores → remove PID file → release lock. It exposes `store_for(project_id)` to tenants and a `stop_requested` flag they must honor inside long operations.

**`Tenant`** is a two-member protocol: `name: str` and `tick(host) -> bool`, returning whether work was done. The loop ticks each tenant in registration order; when no tenant worked, it waits on the stop event for `idle_interval_seconds`. With zero tenants the process is a correct, idle, recoverable host — which is this slice's working end state.

**Recovery** is a function over a store and an observer registry keyed by `CommandKind`. It knows nothing about Squadron or Context Forge; the observers do.

### Data Flow

Normal operation (performed by a tenant — the Runner, from initiative 120):

```
journal_issue(node, kind, parameters)  ── commit ──▶  entry (outcome NULL)
        │
        ▼
   side effect (sq run … / cf set …)
        │
        ▼
journal_resolve(entry, outcome, result) ── commit ──▶  entry closed
```

A crash at any point leaves one of three states, and recovery distinguishes them only by observation:

| Crash point | Journal | Reality | Recovery sees |
| --- | --- | --- | --- |
| Before `journal_issue` commits | no entry | not issued | nothing to do |
| After issue, before side effect | unresolved | not issued | CF: `not_applied`. SQ: zero matches → human |
| After side effect, before resolve | unresolved | happened | CF: `adopted`. SQ: one match → `adopted` |

Recovery at start, per project store, per unresolved entry, oldest first:

```
observer = registry[entry.kind]        # absent → Unknown
observation = observer.observe(entry)
  Adopt(result)      → journal_resolve(outcome=adopted,     resolved_by=recovery)
  NotApplied         → journal_resolve(outcome=not_applied, resolved_by=recovery)
  Unknown(reason, …) → journal_escalate(entry, reason)      # one transaction:
                         outcome=unknown + block(node, kind=HUMAN, context=…)
```

Each entry is reconciled in its own transaction, so recovery is itself crash-safe: a second crash mid-recovery re-runs only what is still unresolved.

### State Management

- **Durable, in each project's store:** the `command_journal` table. This is the only new persistent state.
- **Durable, in the supervisor directory** (the directory `amoeba.store.paths` already resolves): `amoeba.lock` (the lock is the truth about liveness) and `amoeba.pid` (JSON: pid, started-at, version — informational; a stale one is harmless because nothing trusts it without testing the lock).
- **In memory only:** open `Store` handles, the tenant list, and the stop event. All reconstructible; none is authoritative.

The stop flag is a `threading.Event` set from the signal handler and read by the loop and tenants. That is the single piece of state published across an execution boundary, and the `Event` is its publication mechanism.

## Technical Decisions

Five of these are choices a reasonable Project Manager could make differently. They are marked **(PM)** and summarized again in Implementation Notes.

### Technology Choices

**D1 — Foreground process; no self-daemonizing. (PM)** `amoeba start` runs in the foreground and logs to stderr. Detaching is the job of whatever launched it (`launchd`, `tmux`, a shell `&`). Double-fork daemonization, log files, and rotation are a well-known source of subtle bugs and buy nothing the supervisor does not already provide. `stop` and `status` work identically either way because they key on the lock, not on a parent relationship.

**D2 — Synchronous host loop. (PM)** The store is synchronous `sqlite3`, the process is the sole writer, and the Runner is specified as a deterministic state machine. A plain loop with a stop event has no event-loop-starvation failure mode and no shared mutable state between coroutines to audit. A tenant that launches a long subprocess polls it and checks `stop_requested`; it does not block the loop invisibly. *Reversal note:* if slice 105's subscriber transport needs a listening socket, it runs in its own thread with a queue into the loop — the loop itself stays synchronous. If that proves awkward, this is the decision to revisit, and it is cheaper to revisit at 105 than to adopt asyncio speculatively now.

**D3 — `argparse` for the CLI; `pydantic` at parsing boundaries only. (PM)** The project has zero runtime dependencies today. `argparse` keeps the CLI dependency-free. `pydantic` is added because the Python rules require it wherever external data is parsed, and this slice parses two external formats. It is used with unknown fields ignored, so an upstream that adds fields does not break recovery. Tunables are a frozen `ProcessSettings` dataclass overridable by CLI flag; no new environment variables and no `.env`, so `AMOEBA_STORE_DIR` in `paths.py` remains the project's only environment read and there is no second source of truth.

**Single instance via `fcntl.flock`, not a PID file.** The kernel releases an advisory lock when the holder dies by any means, including `kill -9`, so a stale lock cannot exist. PID files go stale and PIDs get reused; using one as the lock is a well-known anti-pattern. `stop` verifies the lock is held before signalling the recorded PID, so a reused PID is never signalled.

**Sole-writer enforcement in two parts.** (a) The instance lock guarantees at most one resident process per supervisor directory. (b) `Store.open_read_only(...)` (SQLite `mode=ro`) is added for every out-of-process consumer, and a guard test — AST-based, in the manner of `tests/test_store_safety.py` — fails if any module under `src/amoeba/` other than `process/host.py` calls the read-write `Store.open`. This does not stop a third party importing the library and writing; it makes it impossible to do so by accident inside Amoeba, which is the realistic failure.

### Patterns and Conventions

**Closed vocabularies, defined once, all `StrEnum`:**

- `CommandKind`: `cf_write`, `sq_run`.
- `JournalOutcome`: `completed`, `failed` (both written by the issuer), `adopted`, `not_applied`, `unknown` (written only by recovery).
- `JournalResolver`: `issuer`, `recovery`.
- `ExitCode`: one enumeration for every CLI exit status; no bare integers at call sites. Includes `ALREADY_RUNNING`, `NOT_RUNNING`, `STOP_TIMEOUT`, `NO_STOP_TARGET`, and `GRACE_EXPIRED`.

**Parameters are validated at issue time, not at recovery time.** Each `CommandKind` declares the parameter keys recovery needs. `journal_issue` raises if they are missing — discovering at 3 a.m., after a crash, that an entry cannot be reconciled because a field was never written is the failure this prevents.

- `sq_run` requires `pipeline` and `params`.
- `cf_write` requires `project` and `expected` (a mapping of CF field name to the value the write should leave behind).

Additional keys are stored and ignored.

**Provenance on both ingested shapes.** The architecture requires that every ingested record store the upstream it was parsed from, because neither upstream moves by semver. The two observers satisfy this differently, because the two upstreams expose different things:

- **Squadron** — the run file carries its own `schema_version`; the adopted result records it.
- **Context Forge** — `cf get --json` exposes **no version field** (verified 20260919: its keys are project metadata only). The observer therefore records two things in the adopted result: the project record's own `updatedAt` timestamp, which is what actually dates the observed values, and the string from a single `cf --version` invocation per recovery pass, captured as an opaque label. Neither is ever compared, parsed for ordering, or branched on — recording provenance is not the same as depending on a version, and the rule that no code compares upstream version numbers stands. If `cf --version` fails or is unavailable, the observer records it as unavailable and continues; provenance capture never turns an otherwise-clean adoption into an escalation.

**D5 — Squadron matching is subset-on-params. (PM)** A run file is a candidate when all of: `pipeline` equals the journaled pipeline (compared lower-cased, because Squadron lower-cases it); every journaled `params` key is present in the run's `params` with an equal value; `started_at` is no earlier than the entry's `issued_at` less a named clock tolerance; and its `run_id` is not already recorded in another journal entry's result. Exact equality on `params` would never match, because Squadron persists definition defaults merged with overrides. Subset matching is looser, and the looseness is safe: a wider net can only turn a would-be single match into several, and several is escalated, never guessed.

**Unknown is a value.** Every one of these yields `Unknown` and therefore a `blocked_on_human` node: no observer registered for the kind; zero candidates; two or more candidates; runs directory missing or unreadable; `cf` missing, timing out, exiting non-zero, or emitting unparseable output. A run file that fails to parse is logged at WARNING, counted, and named in the `Unknown` reason if the entry ends up unmatched — it is never silently skipped into a confident answer.

**Already-blocked node.** `block()` refuses a node that is already blocked, and the unique partial index forbids a second open blocked state. If an unresolved entry's node is already blocked, `journal_escalate` marks the entry `unknown` and does not write a second block; the node is already stopped, and the entry is visible through `amoeba inspect journal`. This is handled as an explicit branch, not by catching `InvalidTransitionError`.

**Error handling.** Observers raise nothing for expected external failure — those are `Unknown`. Unexpected exceptions are logged with `logger.exception` and re-raised; a recovery that cannot complete aborts startup rather than letting tenants run against unreconciled state. `cli/main.py` is the one documented process-boundary handler that maps `StoreError` and lifecycle errors to `ExitCode` values.

**Lifecycle failure modes are enumerated, not implicit.** The observer ladder above covers the external boundaries; these three cover the process's own lifetime, where it must decide rather than converge.

- **Lock held, PID file absent or unreadable.** The start sequence acquires the lock before writing the PID file, so a live process can legitimately hold the lock with no PID file yet; a truncated or non-JSON PID file presents identically. `stop` does not guess a signal target: it reports `ExitCode.NO_STOP_TARGET` naming the lock path, and says the process is running but not addressable. `status` reports `running (pid unknown)` — distinct from `stopped (stale pid file)`, which is the inverse case (PID file present, lock free). The remedy is the operator's, and it is safe because the lock, not the PID file, is the truth about liveness.
- **Grace period expires.** The loop stops ticking new work as soon as the stop event is set; the grace period bounds only the *current* tick. On expiry the process logs at ERROR, naming the tenant that did not return, and exits with `ExitCode.GRACE_EXPIRED` without waiting further — stores are closed, but a tenant mid-tick is abandoned in place rather than interrupted. This is safe precisely because of crash-only: an abandoned tick is indistinguishable from `kill -9` and is reconciled on the next start by the same recovery path. The process never escalates to killing its own thread.
- **A tenant hangs.** **By decision, there is no per-tick timeout** — no watchdog, no tick budget in `ProcessSettings`. A synchronous loop (D2) cannot interrupt a tenant that does not return without threads or signals whose failure modes are worse than the one they fix, and crash-only already makes an external `kill -9` a correct and recoverable remedy. The obligation therefore sits on the tenant: `tick()` must return promptly and poll `stop_requested` inside long operations, which `docs/process-contract.md` states as a requirement rather than a suggestion for slices 103 and 120. The observable consequence is bounded and named: the grace period expires, `stop` returns `STOP_TIMEOUT`, and the operator kills the process. Revisit if a real tenant cannot honor the contract.

## Implementation Details

### API Contracts

**Store additions (public, exported from `amoeba.store`, pinned by `tests/test_public_api.py`):**

| Method | Effect |
| --- | --- |
| `journal_issue(node_id, *, kind, parameters)` | Validates parameters for the kind, writes an unresolved entry, **commits**, returns the `JournalEntry`. Call before the side effect. Raises `NodeNotFoundError` for an unknown node. |
| `journal_resolve(entry_id, *, outcome, result, resolved_by=ISSUER)` | Closes the entry. Raises `InvalidTransitionError` if it is already resolved. |
| `journal_escalate(entry_id, *, reason)` | One transaction: outcome `unknown`, and blocks the node on `HUMAN` with a context naming the entry — unless the node is already blocked. |
| `unresolved_journal_entries(project_id)` | Oldest first. What recovery consumes. |
| `journal_entries(project_id, *, node_id=None, include_resolved=True)` | What inspection consumes. |
| `Store.open_read_only(path=None, *, project_id=None)` | Read-only handle. Never migrates; a store at an unexpected schema version raises `StoreSchemaError`. |

`JournalEntry` is a frozen dataclass: `id`, `project_id`, `node_id`, `kind`, `parameters`, `issued_at`, `outcome`, `result`, `resolved_at`, `resolved_by`, with an `is_resolved` property.

**Recovery protocol (`amoeba.process.recovery`):**

```python
class Observer(Protocol):
    def observe(self, entry: JournalEntry) -> Observation: ...

Observation = Adopt | NotApplied | Unknown   # frozen dataclasses
```

`Adopt` carries the `result` mapping to store; `Unknown` carries a human-readable `reason` and any `candidates`. Initiative 120 may register observers for command kinds it adds; adding a kind means adding an enum member, its required parameter keys, and an observer.

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba start` | Foreground. Refuses with `ExitCode.ALREADY_RUNNING` if the lock is held. Logs a recovery summary per project before entering the loop. |
| `amoeba stop` | Confirms the lock is held, sends `SIGTERM` to the recorded PID, waits for the lock to release. `ExitCode.NOT_RUNNING` if nothing holds it; `ExitCode.STOP_TIMEOUT` if the wait expires; `ExitCode.NO_STOP_TARGET` if the lock is held but the PID file is absent or unreadable (see below). Never escalates to `SIGKILL` on its own. |
| `amoeba status` | `running` (with pid and start time), `stopped`, or `stopped (stale pid file)`. Exit status distinguishes running from not. |
| `amoeba inspect projects` | Project ids that have a store in the supervisor directory. |
| `amoeba inspect nodes\|blocked\|journal --project ID` | Read-only listings. `journal` accepts `--unresolved`. All accept `--json`. |

Inspection listings are declared in one registry (name → query → columns), so slice 104 adds `findings` and `verdicts` by registering them rather than by editing the CLI.

### Database / Storage Schema

Migration `003_command_journal.sql`, `EXPECTED_SCHEMA_VERSION` → 3.

`command_journal`: `id` (store-generated, opaque), `project_id`, `node_id` (foreign key to `nodes`), `kind`, `parameters` (JSON text), `issued_at`, `outcome` (NULL while unresolved), `result` (JSON text, nullable), `resolved_at`, `resolved_by`. A partial index on `(project_id, issued_at) WHERE outcome IS NULL` serves the recovery query. Entries are never deleted in this slice; retention is already listed as Future Work in the slice plan.

Migration `003` is the first real use of the mechanism slice 101 proved with its deliberately trivial `002`. Existing stores at version 2 upgrade in place on the next `amoeba start`.

## Integration Points

### Provides to Other Slices

- **103:** the `Tenant` protocol for its apply loop; `ResidentProcess.store_for()`; the guarantee that the apply loop is the only writer; `open_read_only` for out-of-process readers; the supervisor directory as the home for the inbox's durable files.
- **104:** the inspection listing registry.
- **105:** the host to run detection inside, and D2's reversal note about a subscriber thread.
- **106:** `start`/`stop`/`kill -9`/`start` as the restart-injection mechanism for the end-to-end proof.
- **107:** a resident process for CF events to arrive at.
- **Initiative 120:** `journal_issue` / `journal_resolve`, the `Observer` registry, journal outcomes as the facts the Runner routes on after a restart, and `stop_requested`.

`docs/store-contract.md` gains a Journal section and its "Not a journal" and "Writer model" sections are updated; a new `docs/process-contract.md` covers lifecycle, tenants, and recovery semantics. Both hold to slice 101's bar: a downstream design proceeds without reading the implementation.

### Consumes from Other Slices

Slice 101 only, through its public contract. `StoreError` subclasses raised during startup abort the start with a specific exit code and the store's own message; the process never falls back to a different store or starts with a project skipped. A corrupt store for one project therefore stops the supervisor — deliberately: running while blind to one project is worse than not running.

## Success Criteria

### Functional Requirements

- [ ] `amoeba start` runs, `amoeba status` reports it running with its pid, `amoeba stop` ends it within the grace period, and `status` then reports stopped.
- [ ] A second `amoeba start` exits with `ExitCode.ALREADY_RUNNING` and does not disturb the first.
- [ ] After `kill -9`, `amoeba start` succeeds immediately with no manual cleanup, and `status` in between reports a stale pid file rather than running.
- [ ] With the lock held and the PID file removed or corrupted, `stop` exits `NO_STOP_TARGET` without signalling anything, and `status` reports `running (pid unknown)`.
- [ ] A tenant that does not return within the grace period causes exit with `GRACE_EXPIRED` and an ERROR log naming the tenant; the next start recovers normally.
- [ ] An adopted `cf_write` result carries the project record's `updatedAt` and a captured `cf --version` label; with `cf --version` unavailable the adoption still succeeds and records it as unavailable.
- [ ] A `cf_write` entry left unresolved is resolved `adopted` when CF holds the expected values and `not_applied` when it does not. Neither re-issues anything.
- [ ] An `sq_run` entry left unresolved with exactly one matching run file is resolved `adopted` with that `run_id`.
- [ ] An `sq_run` entry with zero matching run files, and one with two, each become outcome `unknown` with the node `blocked_on_human` and the blocked-state context naming the journal entry.
- [ ] The Squadron matcher matches when the journaled `params` are a strict subset of the persisted ones, and rejects a run started before the entry was issued.
- [ ] A run id already recorded in another journal entry is not a candidate.
- [ ] `journal_escalate` against an already-blocked node marks the entry `unknown` and writes no second blocked state.
- [ ] Recovery interrupted partway and re-run reconciles each entry exactly once.
- [ ] `journal_issue` with a missing required parameter raises and writes nothing.
- [ ] `amoeba inspect` lists projects, nodes, blocked states, and journal entries, human-readable and as `--json`, while the process is running and while it is stopped.
- [ ] Inspection never migrates, creates, or writes a store.

### Technical Requirements

- [ ] All vocabularies are `StrEnum`s defined once; no exit-code integers or outcome strings at call sites.
- [ ] Every tunable (idle interval, shutdown grace, stop timeout, clock tolerance, `cf` timeout, runs directory) lives in `ProcessSettings`.
- [ ] Squadron matcher fixtures are **real** run files copied from `~/.config/squadron/runs/` at implementation time, including at least one `paused` and one `failed`. The CF fixture is captured from real `cf get --json` output. Each fixture notes the date it was captured; none is tied to an upstream version.
- [ ] A run file or `cf` output missing a field the observer requires yields `Unknown`, not an exception and not a match — so upstream drift degrades to a human escalation.
- [ ] The guard test fails when a read-write `Store.open` call is added outside `process/host.py`.
- [ ] Process-level tests drive the real CLI as a subprocess against a `tmp_path` supervisor directory via `AMOEBA_STORE_DIR`; none touches `~/.config/amoeba` or the real Squadron runs directory.
- [ ] `tests/load/` contains a crash-loop test and a recovery-scale test (see Implementation Notes) with asserted bounds.
- [ ] `ruff`, `pyright` strict, and the full test suite are clean. Source files stay near 300 lines.
- [ ] `docs/process-contract.md` exists; `docs/store-contract.md` is updated; `CHANGELOG.md` has entries.

### Integration Requirements

- [ ] A throwaway `Tenant` defined in a test is ticked by the real host, writes through `store_for()`, observes `stop_requested`, and the process exits cleanly — proving the seam 103 and 120 will use.
- [ ] A store created by slice 101 code at schema version 2 is upgraded to 3 by `amoeba start` with its nodes and blocked states intact.

### Verification Walkthrough

Draft; to be refined with real output at the end of Phase 6. None of these commands exists yet. Everything runs against a scratch supervisor directory so the real one is never touched.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
```

**1. Lifecycle and single instance**

```bash
uv run amoeba start &          # foreground process, backgrounded by the shell
uv run amoeba status           # → running  pid=<n>  since=<timestamp>
uv run amoeba start            # → refuses; echo $? shows the ALREADY_RUNNING code
uv run amoeba stop             # → stopped
uv run amoeba status           # → stopped
```

**2. Crash leaves nothing to clean up**

```bash
uv run amoeba start &
kill -9 %1
uv run amoeba status           # → stopped (stale pid file)
uv run amoeba start &          # → starts; no manual lock or pid removal
uv run amoeba stop
```

**3. Recovery — the three Squadron outcomes.** A helper script, `scripts/demo_journal.py` (to be written in this slice, a few lines over the public store API), creates a project `demo` with three nodes and issues one unresolved `sq_run` entry per node against a scratch runs directory seeded with copies of real run files: one entry with exactly one matching file, one with none, one with two.

```bash
uv run python scripts/demo_journal.py --runs-dir "$AMOEBA_STORE_DIR/runs"
uv run amoeba inspect journal --project demo --unresolved    # → three entries
uv run amoeba start --sq-runs-dir "$AMOEBA_STORE_DIR/runs" &
#   log: recovery demo: 1 adopted, 0 not_applied, 2 unknown
uv run amoeba inspect journal --project demo --unresolved    # → none
uv run amoeba inspect journal --project demo
#   → one 'adopted' carrying a run_id; two 'unknown'
uv run amoeba inspect blocked --project demo
#   → two nodes blocked_on_human; each context names its journal entry
```

**4. Nothing is re-issued or double-handled**

```bash
uv run amoeba stop && uv run amoeba start --sq-runs-dir "$AMOEBA_STORE_DIR/runs" &
#   log: recovery demo: nothing to reconcile
uv run amoeba inspect blocked --project demo                 # → still exactly two
```

**5. Committed state survives a kill.** `kill -9` the process, then `amoeba inspect nodes --project demo --json` and compare with the listing taken before the kill: identical.

**6. Quality gates**

```bash
uv run pytest && uv run pytest tests/load
uv run ruff check . && uv run pyright
```

## Risk Assessment

### Technical Risks

- **A wrong adoption is silent.** If the matcher adopts a run that was not the journaled one, the Runner proceeds on someone else's verdict and nothing flags it. This is the rewrite-expensive failure the architecture warns about.
- **Read-only open of a WAL database.** SQLite needs the `-shm` file to read a WAL-mode database; `mode=ro` against a store whose writer is down behaves differently across SQLite versions.
- **Signals and `flock` are platform behavior** that unit tests with mocks cannot validate.

### Mitigation Strategies

- The matcher is biased entirely toward escalation: every ambiguity, parse failure, and unreadable directory is `Unknown`. The only path to `adopted` is exactly one candidate passing all four conditions. Fixtures are real files, and the two-match and zero-match cases are first-class success criteria. S9 (caller-supplied run id) stays in Future Work as the real fix.
- The first task of the inspection work is a test that opens a store read-only with no writer alive, on the project's actual Python/SQLite. If it fails, the fallback is a read-write handle that the inspection code never writes through, with the guard test extended to cover `cli/inspect.py` — decided on that evidence, not in advance. **If the fallback is taken, it softens the sole-writer invariant and both contract documents must say so**: `docs/process-contract.md` and the writer-model section of `docs/store-contract.md` state that inspection holds a read-write handle it never writes through, rather than leaving "only the resident process opens a store read-write" standing as an unqualified claim. A weaker invariant documented honestly is acceptable; a stale contract is not.
- Lifecycle tests run the real CLI as a subprocess and send real signals. Nothing about locking or signal handling is mocked.

## Implementation Notes

### Development Approach

Suggested order — each step leaves the suite green:

1. **Journal in the store** — models, `sql_journal.py`, migration `003`, `JournalMixin`, contract tests. Pure library work in slice 101's style, no process yet.
2. **`open_read_only`** and its WAL test (resolves the second risk early).
3. **Recovery protocol** with fake observers — the reconcile logic, per-entry transactions, the already-blocked branch, interrupted-recovery idempotence.
4. **Squadron observer**, against real run-file fixtures.
5. **CF observer**, against a captured `cf get --json` fixture, with the subprocess boundary mocked for failure modes and one real invocation test.
6. **Instance lock and PID file.**
7. **Host loop, signals, `Tenant`**, and the throwaway-tenant integration test.
8. **CLI** — lifecycle commands, then `inspect` and its registry.
9. **Guard test** for read-write opens.
10. **Load tier.** *Crash loop:* repeatedly start the process with a test tenant that issues journal entries, `SIGKILL` at a random point, restart; assert after every cycle that no committed node or entry is missing, no entry is reconciled twice, and start-to-ready stays under a stated bound. *Recovery scale:* several hundred unresolved entries against a runs directory of a thousand files; assert a bound on total recovery time and that the directory is scanned once per recovery, not once per entry.

    **Candidate bounds, to be confirmed against first measurement:** start-to-ready with an empty journal under 2 s; recovery of 500 unresolved `sq_run` entries against 1000 run files under 30 s; exactly one runs-directory scan per recovery pass regardless of entry count. The first two are starting targets, not derived requirements — the architecture states no NFR for this path. Measure first, then set each assertion at roughly twice the observed value so the test catches a regression in kind (a per-entry directory scan, an accidental O(n²) match) rather than normal machine variance. If a measurement lands wildly off a candidate, record the real number and say why; do not tune the bound silently to whatever passes. The scan-count assertion is exact and is the one that actually guards the algorithm.
11. **Docs** — `process-contract.md`, `store-contract.md`, `CHANGELOG.md`, and the refined walkthrough.

### Special Considerations

**Project Manager decisions.** D4 is ratified and applied (see below). D1, D2, D3, and D5 remain recommendations awaiting ratification; the design is complete under them, and each is reversible at design time and expensive later.

- **D1** — foreground-only `start`, no self-daemonizing.
- **D2** — synchronous host loop with a `Tenant.tick` seam, rather than asyncio.
- **D3** — `argparse`, plus `pydantic` as the project's first runtime dependency.
- **D4 — the slice plan's inspection criterion. RATIFIED 20260919 and applied.** The plan formerly said the inspection surface "lists nodes, findings, verdicts, and journal entries", which this slice could not meet because findings and verdicts do not exist until slice 104. The PM ratified the split: slice 102's criterion now covers nodes, blocked states, and journal entries plus the listing registry, and slice 104's criterion covers findings and verdicts registered into that registry. Slice 104's dependencies moved to `[101, 102]` and this design's `interfaces` now includes 104. Execution order is unchanged.
- **D5** — subset matching on Squadron `params`.

**Journaled-but-never-issued is indistinguishable from issued-and-pruned** for `sq_run`. Both present as zero matches and both escalate. That is correct under "unknown is a value", but it means a crash in the narrow window between `journal_issue` and process launch costs a human interruption. Accepted; S9 removes it.

**Squadron prunes finished runs beyond 10 per pipeline.** A long outage during which the PM runs the same pipeline many times can prune the journaled run before recovery sees it. Result: escalation, not a wrong answer.

**Recovery gates startup.** Tenants do not tick until every project has been reconciled. With the recovery-scale bound in the load tier this is a short, measured delay, and it removes any possibility of the Runner acting on a node whose in-flight command has not been accounted for.

**Security.** Journal `parameters` and `result` are stored verbatim and shown by `amoeba inspect`. The contract will state that callers must not place secrets in them. The supervisor directory is created with the user's default permissions, as in slice 101; no new exposure is introduced.
