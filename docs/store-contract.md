---
docType: reference
project: amoeba
slice: store-foundation-and-node-model
dateCreated: 20260917
dateUpdated: 20260927
status: complete
---

# The Amoeba Store Contract

This document is the contract for `amoeba.store`. It is written so that a slice
design in initiative 120, 140, or 160 can proceed **without reading the store
implementation**. If you find yourself opening `store.py` to answer a design
question, that is a gap in this document — say so.

## What the store is

One SQLite file holding a project-keyed tree of lifecycle nodes, plus the
blocked states that record what any node is waiting on.

The load-bearing idea: **a checkpoint is a persisted blocked-state, not a
blocking call.** A node blocked with an unfilled resolution slot *is* the
checkpoint. Nothing waits on a socket; the block survives a restart because it
is a row. Everything that makes Amoeba async by construction follows from this.

## What the store is not

- **Not a process.** This is a synchronous, in-process library. The resident
  process that hosts it is `amoeba.process` — see
  [`process-contract.md`](process-contract.md).
- **Not a single-writer enforcer on its own.** See
  [Writer model](#writer-model): slice 102 added the enforcement around it, and
  the distinction is easy to assume wrongly.
- **Not a parser.** CF and SQ values are stored opaquely. See
  [Reference fields](#reference-fields).

## Importing

Everything below is exported from `amoeba.store` directly:

```python
from amoeba.store import Store, Node, NodeKind, NodeStatus, BlockedKind
from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver
from amoeba.store import Channel, Message, SubmissionKind, SubmissionRecord
```

`sql`, `sql_journal`, `sql_inbox`, `mapping`, `mapping_journal`,
`mapping_inbox`, `migrations`, `paths`, `_base`, and `_block_writer` are
internal. They are not re-exported and are not contract. A test
(`tests/test_public_api.py`) pins the export set, so this list cannot drift
silently.

## Vocabularies

All vocabularies are `StrEnum`, so the values stored in the database file are
readable strings — `amoeba inspect` reads them directly.

**A value outside a vocabulary is an error, not a default.** Reading a row whose
status is not in `NodeStatus` raises `UnknownVocabularyValueError` rather than
returning a partially-populated object. Do not write code that expects a
fallback; there is none.

### `NodeStatus`

| Value | Meaning |
| --- | --- |
| `runnable` | Awaiting work. Returned by `runnable()`. |
| `in_progress` | Work has started. Not runnable, not blocked. |
| `blocked_on_human` | Waiting on a person. Returned by `blocked()`. |
| `blocked_on_judge` | Waiting on a Judge pseudopod. Returned by `blocked()`. |
| `blocked_on_sq_checkpoint` | Waiting on a Squadron checkpoint. Returned by `blocked()`. |
| `done` | Finished. Terminal. |

`BLOCKED_STATUSES` is the frozenset of the three `blocked_on_*` values. Use it
rather than string-prefix tests or a hand-kept list of your own.

### `NodeKind`

`initiative`, `phase_or_artifact`, `slice`, `gate`. What a node represents in
the lifecycle tree.

### `BlockedKind`

`human`, `judge`, `sq_checkpoint`. What a blocked node is waiting on. Parallel
to the blocked statuses but a distinct vocabulary: the status says *that* the
node is blocked, this says *on whom*.

`BLOCKED_KIND_TO_STATUS` maps each blocker kind to the status it implies. The
store applies it for you — you never choose the status when blocking.

## Types

All are frozen dataclasses. They are transfer objects, not ORM rows: mutating
one changes nothing in the database.

- **`Node`** — `id`, `project_id`, `kind`, `status`, `title`, `parent_id`,
  `cf`, `sq`, `created_at`, `updated_at`.
- **`CFReference`** — `project`, `phase`, `slice_name`, `artifact_path`.
- **`SQReference`** — `run_id`, `review_artifact_path`, `reviewed_sha`.
- **`Resolution`** — `resolved_by`, `detail`, `resolved_at`.
- **`BlockedState`** — `id`, `node_id`, `kind`, `context`, `resolution`,
  `created_at`, `updated_at`, plus an `is_resolved` property.
- **`BlockedNode`** — a `node` and its `blocked_state`, returned by `blocked()`.

### Node identity

`Node.id` is a store-generated opaque string. It is deliberately **not** derived
from CF coordinates: a node's CF pointers can change — a slice is renumbered, an
artifact path moves — without the node becoming a different node. Correlate on
`id`; never reconstruct it.

### Reference fields

`CFReference` and `SQReference` are held as **opaque, unparsed values**. The
store writes them and reads them back verbatim. It does not validate their
shape, does not decompose a Squadron run id into its date/slug/uuid parts, and
does not resolve artifact paths.

This is a boundary, not an oversight. Slice 104 correlates provenance against
these fields, and the Runner — not the store — parses CF and SQ output. If you
need a parsed value, parse it in your own slice and store the result in a field
your slice owns.

## Lifecycle

```python
store = Store.open(path)  # explicit path
store = Store.open(project_id="amoeba")  # central per-supervisor path
store = Store.open_temporary()  # throwaway, in-memory
store.close()
```

All three support the context-manager form, which releases the connection on
normal **and** exception exit:

```python
with Store.open(path) as store:
    ...
```

`open()` creates parent directories, connects, sets WAL journal mode and the
busy timeout, then migrates the schema to the version the code expects. Passing
neither `path` nor `project_id` raises `ValueError` rather than guessing.

`busy_timeout_seconds` may be passed to `open()`; it defaults to the named
constant and exists so contention tests need not wait the production timeout.

## Node writes

| Method | Effect |
| --- | --- |
| `create_node(*, project_id, kind, title, parent_id=None, status=RUNNABLE, cf=None, sq=None)` | Creates a node and returns it, with its generated `id`. Raises `NodeNotFoundError` if `parent_id` names no node, and `InvalidTransitionError` if `status` is a blocked status. |
| `update_node_status(node_id, status)` | Sets status, validated against the vocabulary. Returns the updated node. Raises `InvalidTransitionError` if the node is blocked or `status` is a blocked status. |
| `update_cf_reference(node_id, cf)` | Replaces all CF fields. The node's `id` is unchanged. |
| `update_sq_reference(node_id, sq)` | Replaces all SQ fields. The node's `id` is unchanged. |

`project_id` is required on every node from the first row written. This is the
architecture's "project is a first-class key from day one" — it does not mean
multi-project supervision exists yet.

**No write returns a status code you can ignore.** Failures raise.

`update_node_status` cannot block or unblock a node, and `create_node` cannot
create one already blocked: both raise `InvalidTransitionError` for any blocked
status. Use `block()` and `resolve()`, which keep status and blocked-state
consistent.

## Node reads

| Method | Returns |
| --- | --- |
| `get_node(node_id)` | The node, or `None` if there is none. Absence is not an error. |
| `nodes_for_project(project_id)` | Every node in the project, oldest first. |
| `children_of(node_id)` | Direct children only, oldest first. |

## Blocked-state writes

These are the load-bearing operations of the slice.

```python
state = store.block(node_id, kind=BlockedKind.HUMAN, context="awaiting PM ruling")
state = store.block(node_id, kind=BlockedKind.HUMAN, context="…", payload={"options": […]})
state = store.resolve(node_id, resolved_by="pm", detail="add the task to 101")
```

**Each is one call and one transaction.** `block()` writes the blocked-state
record *and* sets the node's status together; `resolve()` fills the resolution
slot *and* flips the node back to `runnable` together.

**A `HUMAN` block also writes its escalation (slice 103, D3).** In the same
transaction, `block(kind=HUMAN)` writes one row on the `escalation` message
channel carrying the node id, the blocked-state id, and the optional opaque
`payload` — whatever the eventual resolver needs to decide. A human-blocked node
without its escalation row cannot exist. `JUDGE` and `SQ_CHECKPOINT` blocks
write no message. Every block, whoever asks for it, goes through one internal
writer, so there is no path that blocks without escalating. The `payload` is
stored only on the escalation row; `BlockedState` does not carry it.

There is deliberately **no public path that writes one half**. Node status and
blocked state cannot disagree, because the caller is never able to make them
disagree: `create_node` and `update_node_status` refuse every blocked status, so
`block()` and `resolve()` are the only writers of either half.

Invalid transitions raise `InvalidTransitionError` rather than silently
overwriting:

- blocking a node that is already blocked
- resolving a node that is not blocked

A node may be blocked again after resolution; each block is a separate record.

| Method | Returns |
| --- | --- |
| `blocked_state_for(node_id, *, include_resolved=False)` | The open blocked state, or the most recent one when `include_resolved=True`. `None` if there is none. |
| `all_blocked_states(node_id)` | Iterator over every blocked state the node has had, oldest first. |

## The two Runner queries

```python
store.runnable(project_id)  # -> list[Node]
store.blocked(project_id)  # -> list[BlockedNode]
```

**`runnable(project_id)`** returns nodes in `runnable` status for the project.

**`blocked(project_id)`** returns every node in any `blocked_on_*` status, each
already carrying its open blocked-state record — so *"on whom?"* is answered
**without a second call**. Do not follow up with `blocked_state_for()`; the
answer is in hand.

Both queries:

- are **project-scoped**: a query for one project never returns another's nodes
- use the `(project_id, status)` index
- return an **empty list** when there is nothing, which is not an error

## The command journal

*Added by slice 102. Schema version 3.*

A record of every side-effecting command, written **before** the command is
issued and closed when its result arrives. Its whole purpose is one ordering
guarantee:

> `journal_issue` **commits before it returns.** A crash in the window between
> that commit and the side effect therefore leaves a durable unresolved entry.

That entry is what lets the resident process, on its next start, ask the
external system what actually happened — rather than guessing, or re-issuing a
command that may already have run. The reconcile protocol itself is
[`process-contract.md`](process-contract.md)'s subject; this section covers only
what the store offers.

### Vocabularies

All `StrEnum`, all defined once, exported from `amoeba.store`.

| Vocabulary | Members |
| --- | --- |
| `CommandKind` | `cf_write`, `sq_run` |
| `JournalOutcome` | `completed`, `failed` (written by the issuer); `adopted`, `not_applied`, `unknown` (written only by recovery) |
| `JournalResolver` | `issuer`, `recovery` |

`unknown` is a *recorded outcome* — recovery could not determine what happened —
and is distinct from an unmappable stored string, which raises
`UnknownVocabularyValueError` like any other vocabulary violation.

### Required parameter keys

`REQUIRED_PARAMETER_KEYS` maps each `CommandKind` to the keys recovery needs.
`journal_issue` validates them **before writing anything**:

| Kind | Required keys |
| --- | --- |
| `sq_run` | `pipeline`, `params` |
| `cf_write` | `project`, `expected` (a mapping of CF field name to the value the write should leave behind) |

Additional keys are stored and returned unchanged.

Validating at issue time rather than at recovery time is deliberate: discovering
at 3 a.m., after a crash, that an entry cannot be reconciled because a matching
field was never recorded is the failure this prevents.

### Methods

| Method | Effect |
| --- | --- |
| `journal_issue(node_id, *, kind, parameters)` | Validates the parameters for the kind, writes an unresolved entry, **commits**, returns it. Call before the side effect. Raises `NodeNotFoundError` for an unknown node and `ValueError` for a missing required key — in both cases writing nothing. |
| `journal_resolve(entry_id, *, outcome, result=None, resolved_by=ISSUER)` | Closes the entry. Raises `InvalidTransitionError` if it does not exist or is already resolved; a first outcome is never silently overwritten. |
| `journal_escalate(entry_id, *, reason)` | **One transaction:** sets outcome `unknown`, blocks the node on `HUMAN` with a context naming the entry, and writes an escalation row carrying the entry id. If the node is already blocked, marks the entry, writes no second blocked state, and writes one escalation row pointing at the existing open block. |
| `journal_entry(entry_id)` | One entry, or `None`. |
| `unresolved_journal_entries(project_id)` | Entries still in flight, oldest first. What recovery consumes. |
| `journal_entries(project_id, *, node_id=None, include_resolved=True)` | What inspection consumes. |
| `recorded_result_run_ids(project_id)` | Run ids already recorded in some entry's result, mapped to that entry's id. The Squadron matcher's fourth candidate condition reads this. |

### `JournalEntry`

A frozen dataclass: `id`, `project_id`, `node_id`, `kind`, `parameters`,
`issued_at`, `outcome`, `result`, `resolved_at`, `resolved_by`, plus an
`is_resolved` property derived from `outcome` — not a separate stored flag, so
the two cannot disagree.

### The already-blocked branch

`block()` refuses a node that is already blocked, and a unique partial index
forbids a second open blocked state. When an unresolved entry's node is already
blocked, `journal_escalate` marks the entry `unknown` and does **not** write a
second block: the node is already stopped, and the entry stays visible through
`amoeba inspect journal`.

It **does** write one escalation row (slice 103, D3), pointing at the node's
existing open blocked state with the entry id set — whatever kind that block
is. A human must hear that a command's outcome is unknown even when the node
was already waiting on a Judge. For such a row, "the blocked state is still
open" does not mean "no human has seen it": that block's own owner can resolve
it. Deliver escalations by `seq` cursor, not by open-ness.

This is an explicit branch in the implementation, not a caught
`InvalidTransitionError` — catching would also swallow a genuine transition bug.

### Security

> **`parameters` and `result` are stored verbatim and are shown by
> `amoeba inspect`, including in `--json` output. Callers must not place secrets
> in them.**

Store a reference — a path, an id, a key name — not the secret itself.

### Retention

Entries are never deleted in this slice. Retention is Future Work.

## The inbox record and messages

*Added by slice 103. Schema version 4.*

The store's half of the inbox. How a submission gets here, what each kind
means, and what is and is not guaranteed are
[`inbox-contract.md`](inbox-contract.md)'s subject; this section covers only
what the store offers.

### Vocabularies

| Vocabulary | Members |
| --- | --- |
| `SubmissionKind` | `create_project`, `resolution`, `intent` |
| `SubmissionOutcome` | `applied`, `rejected` |
| `Channel` | `intent`, `escalation` |
| `QuarantineReason` | `unparseable_envelope`, `unknown_envelope_version`, `unknown_kind`, `invalid_project_id`, `invalid_payload`, `no_store_for_project` (recorded beside a quarantined file, never in the store) |

### Types

- **`SubmissionRecord`** — `applied_seq`, `id`, `project_id`, `kind`,
  `submitted_by`, `submitted_at`, `payload`, `outcome`, `reason` (set when
  rejected), `applied_at`.
- **`Message`** — `seq`, `id`, `project_id`, `channel`, `node_id`,
  `blocked_state_id`, `journal_entry_id`, `submission_id`, `payload`,
  `created_at`, `acknowledged_at`, `acknowledged_by`, plus an `is_acknowledged`
  property.

`applied_seq` and `seq` are assigned by the store at write time — the
authoritative order (D4). They are never reassigned, even after a delete.
`submitted_at` is the submitter's clock and orders nothing.

### Methods

| Method | Effect |
| --- | --- |
| `apply_submission(*, submission_id, project_id, kind, submitted_by, submitted_at, payload)` | **One transaction:** replay check, precondition, effect, record. On replay returns the existing record unchanged and does nothing else. A failed precondition is recorded `rejected` with a reason, never raised. Raises `ValueError` for a payload malformed for its kind, writing nothing. Called by the resident process; outside parts use `amoeba.inbox.submit`. |
| `submission(submission_id)` | One record, or `None` until applied. |
| `submissions(project_id, *, outcome=None)` | Records in `applied_seq` order. |
| `messages(project_id, *, channel, after_seq=0)` | Rows with `seq > after_seq`, ascending. The replay primitive; stable across calls. |
| `pending_intents(project_id)` | Unacknowledged `intent` rows, ascending. What the Runner consumes. |
| `acknowledge_message(message_id, *, acknowledged_by)` | Marks an `intent` consumed. Raises `InvalidTransitionError` if it does not exist, is not an intent, or is already acknowledged. |

All reads work through a **read-only** handle, so a consumer following a channel
needs no write access. `apply_submission` takes plain, already-validated values:
`amoeba.store` never imports `amoeba.inbox`.

### Security and retention

Submission payloads and message payloads are stored verbatim and shown by
`amoeba inspect`. **Callers must not place secrets in them.** Records and
messages are never deleted in this slice.

## Verdicts and findings

*Added by slice 104. Schema version 5.*

The store records what each review said: one verdict per review and one
observation per finding, each keyed by content so rounds can be compared. The
matching rule, the trust label, how the previous round is chosen, and the
`verdict` inbox kind are [`evidence-contract.md`](evidence-contract.md)'s
subject; this section lists only what the store offers.

### Vocabularies

| Vocabulary | Members |
| --- | --- |
| `ReviewVerdict` | `PASS`, `CONCERNS`, `FAIL`, `UNKNOWN` |
| `FindingSeverity` | `pass`, `note`, `concern`, `fail` |
| `VerdictDerivation` | `stated`, `derived`, `imposed`, `not_reported` |
| `RecordSource` | `stdout_json`, `artifact_frontmatter` |
| `FindingChange` | `new`, `recurring`, `gone` |
| `VerdictStanding` | `provider_failure`, `unparsed`, `findings_unparsed`, `imposed`, `derived`, `unattested`, `stated` |

`SubmissionKind` gains `verdict`.

### Types

`VerdictInput`, `FindingInput`, `Provenance`, `VerdictRecord`,
`FindingObservation`, `FindingSummary`, `TaggedFinding`, and `FindingChanges`,
all frozen. Fields are listed in the evidence contract.

### Methods

| Method | Effect |
| --- | --- |
| `record_verdict(verdict, *, project_id)` | **One transaction:** retry check, checks, the verdict row, one row per finding. An id already recorded returns the existing record, with a WARNING if the content differs. |
| `verdict(verdict_id)` | One record, or `None`. |
| `verdicts(project_id, *, node_id=None)` | Records in arrival (`recorded_seq`) order. |
| `observations(verdict_id)` | One review's findings in the reviewer's order. Raises `VerdictNotFoundError`. |
| `findings(project_id, *, node_id=None)` | One summary per content key per node. |
| `finding_changes(verdict_id)` | New, recurring, and gone against the previous comparable round. Raises `VerdictNotFoundError`. |

All reads work through a read-only handle. `verdict_standing`, `parse_verdict`,
`parse_severity`, and `COMPARABLE_STANDINGS` are exported beside them. The
matching rule is `amoeba.store.finding_identity`, importable without a store.

### Retention

Verdicts and observations are never deleted in this slice.

## Writer model

**This library does not enforce single-writer on its own.** WAL journal mode is
set at open, which permits concurrent readers alongside one writer. Two
processes that both open a store read-write will contend, and contention
surfaces as `StoreBusyError` once the busy timeout is exhausted — the library
does not prevent it.

**Slice 102 added the enforcement, and it is now mechanical rather than
conventional:**

1. **An advisory instance lock** (`amoeba.lock` in the supervisor directory)
   guarantees at most one resident process per supervisor. The kernel releases
   it when the holder dies by any means, so a stale lock cannot exist.
2. **A guard test** (`tests/test_writer_guard.py`) walks the AST of every module
   under `src/amoeba/` and fails if any module other than `process/host.py`
   calls the read-write `Store.open`.

Every out-of-process consumer uses [`Store.open_read_only`](#read-only-access)
instead, which is a genuine SQLite `mode=ro` handle: a write attempted through
it raises. That was **measured** on this project's Python and SQLite build
rather than assumed — see `tests/test_read_only_open.py`, which records the
measurement and its date.

Stated honestly: this does not stop a third party importing `amoeba.store` and
writing. Nothing in a library can. It makes the mistake impossible to make *by
accident inside Amoeba*, which is the realistic failure.

The full process-side contract is in
[`process-contract.md`](process-contract.md).

## Read-only access

```python
Store.open_read_only(path=None, *, project_id=None)
```

A read-only handle for every out-of-process consumer — `amoeba inspect` uses it
for all of its listings.

- **It never migrates.** A store at any version other than the one this code
  expects raises `StoreSchemaError` and the file is left exactly as it was
  found. Migrating would be a write.
- **It never creates.** Opening a path with no store raises
  `StorePermissionError` rather than creating an empty database.
- **It cannot write.** The handle is SQLite `mode=ro`; every write method raises
  through it.

Reads through it return the same values a read-write open does, whether or not
a writer is currently alive.

## Failure modes

Every failure raises a specific typed exception. **No failure path degrades to a
default, an empty result, or a fallback store** — a caller silently operating
against a throwaway store it did not ask for is the worst available outcome.

| Condition | Exception |
| --- | --- |
| Busy timeout exhausted under lock contention | `StoreBusyError` (names the contended operation) |
| File is not a readable SQLite database, or `schema_meta` is unreadable | `StoreCorruptError` |
| Store path or its parent cannot be created, read, or written | `StorePermissionError` (includes the resolved path) |
| Store is stamped at a schema version newer than the code | `StoreSchemaError` |
| Stored value outside a closed vocabulary, read back | `UnknownVocabularyValueError` |
| Node id does not exist | `NodeNotFoundError` |
| Verdict id does not exist, for `observations` or `finding_changes` | `VerdictNotFoundError` |
| Block or resolve against a node in the wrong state, or a blocked status written through `create_node` / `update_node_status` | `InvalidTransitionError` |
| Schema-level invariant (foreign key, one open blocked state per node) violated by a write | `StoreIntegrityError` |

All inherit from `StoreError`, so `except StoreError` catches the family.

Notes on specific modes:

- **A corrupt store is never re-created, truncated, or treated as fresh.**
  Silently replacing it would destroy lifecycle history, which is exactly the
  state this component exists to protect.
- **There is no fallback location.** A permission failure raises; it does not
  quietly fall back to a temp path or an in-memory database.
- **A failed commit propagates.** Writes are transactional, so SQLite's own
  guarantees leave the database consistent; the store's obligation is to surface
  the failure rather than report success.

## Store locality

One store per **supervisor**, at a central path, **keyed by project** —
following the architecture's "resident process per supervisor, not per project".

Resolution precedence, highest first:

1. `AMOEBA_STORE_DIR` — used verbatim
2. `XDG_CONFIG_HOME` — yields `$XDG_CONFIG_HOME/amoeba`
3. `~/.config/amoeba` — the default, matching Squadron's `~/.config/squadron`

The project's store file is that directory plus `{project_id}.sqlite3`.

Resolution is a **pure computation**: it creates nothing and touches no
filesystem. Directory creation happens in `Store.open()`.

**There is no per-project override.** The design declines it deliberately —
adding one would put two locality paths in the foundation slice before any
consumer needs either. Do not add one without a PM decision.

## Migrations

`schema_meta` holds a single version stamp, read at open before anything else.
The runner applies numbered `.sql` files in order, each in a transaction,
advancing the stamp as it goes.

To add a schema change in your slice: add `src/amoeba/store/schema/00N_name.sql`
and bump `EXPECTED_SCHEMA_VERSION`. The mechanism is proven end to end — a
deliberately trivial `002` migration ships purely to exercise N→N+1 — so you are
adding a table onto working machinery, not debugging both at once.

**A store stamped newer than the code raises `StoreSchemaError`.** It is never
silently downgraded.

## Testing against the store

Open a throwaway store; never the central one. `tests/conftest.py` provides
`store_file` (a path under `tmp_path`) and `store` (an open store at that path).
A guard test (`tests/test_store_safety.py`) scans test modules for references to
the central-path resolver and fails on offenders, so the property is checked
mechanically rather than assumed. The scan is AST-based and therefore
multiline-aware.

## Future work

**Storage engine reversal trigger (PM).** The decision to use raw stdlib
`sqlite3` rather than SQLAlchemy Core + Alembic should be revisited if *either*:

- schema churn across slices 102–106 makes hand-written migrations painful, or
- the hand-rolled layer becomes recurring maintenance — repeated tweaks and bug
  fixes in the store plumbing itself.

Recorded so the switch is a decision made on evidence rather than a drift. The
mitigation that makes raw viable is structural: every SQL statement and every
column name lives in `sql.py`, so a column-name typo is a single-definition
concern.
