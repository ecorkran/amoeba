---
docType: reference
project: amoeba
slice: store-foundation-and-node-model
dateCreated: 20260917
dateUpdated: 20261023
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
| `done` | Finished. Terminal, and enforced: no store write moves a done node (see [The Runner contract](#the-runner-contract)). |

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
| `sq_run` | `pipeline`, `params`, `run_id` |
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
  property. Slice 121 adds `acknowledgment_outcome`, `acknowledgment_reason`,
  `fault_kind`, `closed_at` and `closed_by` (see
  [The Runner contract](#the-runner-contract)).

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
| `acknowledge_message(message_id, *, acknowledged_by, outcome, reason=None, desired_state=None)` | Marks an `intent` consumed and records its outcome (and any desired state, in the same transaction). Raises `InvalidTransitionError` if it does not exist, is not an intent, or is already acknowledged. See [The Runner contract](#the-runner-contract). |

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
| `RecordSource` | `stdout_json`, `artifact_frontmatter`, `command_output`, `document` (the last two added by slice 107) |
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
| `verdicts(project_id, *, node_id=None, judge_invocation_id=None)` | Records in arrival (`recorded_seq`) order. `judge_invocation_id` keeps one invocation's judge samples (slice 107). |
| `observations(verdict_id)` | One review's findings in the reviewer's order. Raises `VerdictNotFoundError`. |
| `findings(project_id, *, node_id=None)` | One summary per content key per node. |
| `finding_changes(verdict_id)` | New, recurring, and gone against the previous comparable round. Raises `VerdictNotFoundError`. |

All reads work through a read-only handle. `verdict_standing`, `parse_verdict`,
`parse_severity`, and `COMPARABLE_STANDINGS` are exported beside them. The
matching rule is `amoeba.store.finding_identity`, importable without a store.

### Retention

Verdicts and observations are never deleted in this slice.

## Change feed and detection ledger

*Added by slice 106. Schema version 6 (migration `006`: `changes`,
`review_watches`, `detected_reviews`).*

The feed itself — the `Change` shape, payloads, coverage, delivery guarantees,
and the follower — is [`feed-contract.md`](feed-contract.md)'s subject. The
detection tenant is [`process-contract.md`](process-contract.md)'s. This
section lists only what the store offers.

### The trigger convention

Changes are emitted by SQLite triggers on the tracked tables (`nodes` insert
and status update, `verdicts` insert, `messages` insert, `detected_reviews`
insert, `check_results` insert), never by writer code, so every write path emits — including ones
added later. Each trigger writes one `changes` row inside the writing
transaction, with `recorded_at` copied from the row's own timestamp. The
`ChangeKind` and `DetectionOutcome` values appear as literals in the
migration's trigger SQL as well as in the enums; the invariant test
(`tests/store/test_feed_invariant.py`) ties them together. **A new tracked
table** needs a new `ChangeKind`, a trigger in a new migration, and a step in
the invariant test, which fails until all three exist.

### Vocabularies

| Vocabulary | Members |
| --- | --- |
| `ChangeKind` | `node_created`, `node_status_changed`, `verdict_recorded`, `message_posted`, `review_detected`, `check_recorded` (slice 107), `cf_project_changed` (slice 108) |
| `DetectionOutcome` | `baseline`, `ingested`, `unattributed`, `unparseable`, `runner_issued` |

`SILENT_OUTCOMES` (`baseline`, `runner_issued`) are the outcomes that emit no
change. `REVIEW_PRODUCING_KINDS` (today `{sq_run}`; initiative 120 adds its
review command kind) are the journal kinds whose unresolved entries defer
detection. `SubmissionKind` gains `watch_reviews`.

### Types

All frozen. `Change` (`seq, project_id, kind, node_id, subject_id, payload,
recorded_at`); `ReviewWatch` (`project_id, reviews_dir, active, registered_at,
baselined_at, updated_at`); `DetectedReview` (`id, project_id, path, digest,
outcome, node_id, verdict_id, record_id, detail, detected_at`);
`DetectionInput` (`project_id, path, digest, outcome`, and optional `node_id,
verdict_id, record_id, detail`); `BaselineEntry` (`path, digest`);
`Attribution` (`node_id`, `candidates`).

### Methods

| Method | Effect |
| --- | --- |
| `changes(project_id, *, after=0, limit)` | Changes with `seq > after`, in order. `limit` is required; below 1 raises `ValueError`. |
| `data_version()` | SQLite's `PRAGMA data_version`: changes only when another connection commits. What `follow()` waits on. |
| `change_head(project_id)` | The project's highest `seq`, or 0 when its feed is empty. *(Slice 109.)* |
| `read_transaction()` | A context manager: a deferred read transaction, so every statement inside sees one WAL snapshot (taken at the first read, not at `BEGIN`). Reads only; not nestable; always ended with `ROLLBACK`, even when a read raises. *(Slice 109.)* |
| `watches(project_id)` | Registered review directories, active or not. |
| `detection(project_id, path, digest)` | One ledger row, or `None`. |
| `detections(project_id, *, outcome=None)` | The ledger in detection order. |
| `record_detection(DetectionInput)` | In-process only. One transaction. Idempotent on `(project_id, path, digest)`: a known key returns the existing row and writes nothing. |
| `baseline_watch(project_id, reviews_dir, entries)` | In-process only. **One transaction:** a `baseline` row per `BaselineEntry` (known keys skipped), then `baselined_at`. An unregistered or already baselined watch raises `StoreIntegrityError` and writes nothing. |
| `record_detected_verdict(verdict, detection)` | In-process only. **One transaction:** `record_verdict`'s body (its retry rule applies), then an `ingested` ledger row carrying the verdict's id and node. A non-`ingested` outcome raises `ValueError`; an existing ledger key raises `StoreIntegrityError`. A new key whose verdict id already exists (a hand-edited file) records one new row pointing at the existing verdict. |
| `record_runner_report(entry_id, verdict, detection, *, result)` | In-process only. **One transaction:** the checks, `record_verdict`'s body (its retry rule applies), a `runner_issued` ledger row carrying the verdict's id and node, and the journal entry resolved `completed` by `issuer` with `result` (which must carry `run_id`). An existing ledger key is kept and the entry still resolves. Refuses, writing nothing: a non-`runner_issued` outcome or a `result` without `run_id` (`ValueError`); an entry that is missing, already resolved, not a review-producing kind, or in another project (`InvalidTransitionError`). Returns the verdict record. The evidence contract's "Point 3" is the rule it serves. |
| `recorded_since(project_id, record_id)` | Whether a verdict with id `record_id` exists in the project, however it got there. A verdict recorded under an overridden id (`amoeba ingest review --id`) is not seen. |
| `has_unresolved_review_entry(project_id)` | Whether an unresolved journal entry of a review-producing kind exists. |

`attribute_review(slice_nodes, slice_name) -> Attribution` is a pure function,
not a method: the one node with `kind == slice` and `cf.slice_name ==
slice_name`, or `None` with every match in `candidates`. The rule is in the
evidence contract. `from amoeba.store import project_store_path` gives
`project_store_path(directory, project_id)`, the one definition of a project's
store file inside a supervisor directory, shared by the process and
out-of-process followers.

### Retention

Nothing is deleted from `changes`, `review_watches`, or `detected_reviews` in
this slice.

## Judge samples, checks, and progress records

*Added by slice 107. Schema version 7 (migration `007`: nullable
`verdicts.judge_invocation_id`, `check_results`, `progress_records`, and the
`changes_check_recorded` trigger).*

What the records mean, the check standing rule, and the calibration report are
[`evidence-contract.md`](evidence-contract.md)'s subject; this section lists
only what the store offers.

### Vocabularies

| Vocabulary | Members |
| --- | --- |
| `CheckOutcome` | `passed`, `failed`, `errored` |
| `CheckStanding` | `errored`, `unattested`, `vacuous`, `passed`, `failed` |
| `ProgressKind` | `task_progress`, `devlog` |

`SubmissionKind` gains `check`.

### Types

`CheckInput`, `CheckRecord`, `ProgressInput`, and `CalibrationRow`, all frozen.
`VerdictInput` gains `judge_invocation_id: str | None = None`. `ProgressInput`
has no record type. `check_standing(outcome, examined_count)` is exported.

### Methods

| Method | Effect |
| --- | --- |
| `record_check(check, *, project_id)` | **One transaction:** retry check (first wins), checks, insert. Raises `NodeNotFoundError` or `ValueError`. The trigger appends a `check_recorded` change. |
| `check(check_id)` | One record, or `None`. |
| `checks(project_id, *, node_id=None)` | Records in arrival order. |
| `record_progress(progress, *, project_id)` | In-process only, **write-only**. A bare insert returning `None`: no content validation, no retry rule, no feed change. A missing node, a node in another project, or a repeated id raises `StoreIntegrityError`. |
| `calibration(project_id)` | `list[CalibrationRow]`, one per `(review_type, model)` over judge samples, ordered by review type then model. Read-only. |

`record_verdict` gains one check for judge samples: a sample must share the node
and review type of its invocation's earliest recorded sample (`ValueError`
naming both; remedy: a new invocation id). `check`, `checks`, and `calibration`
work through a read-only handle.

### Retention

Check results and progress records are never deleted in this slice.

## Context Forge links and snapshots

*Added by slice 108. Schema version 8 (migration `008`: `cf_links`,
`cf_snapshots`, and the `changes_cf_project_changed` trigger).*

What a snapshot means, the outcomes, and the projection are
[`context-forge-contract.md`](context-forge-contract.md)'s subject; this section
lists only what the store offers. The store reads no file, asks nothing of
Context Forge, and imports nothing from `amoeba.upstream`: `state` and `changed`
are plain JSON it stores and returns without interpreting.

### Vocabularies

| Vocabulary | Members |
| --- | --- |
| `CFSnapshotOutcome` | `observed`, `unreadable`, `unrecognized`, `missing` |

`SubmissionKind` gains `link_cf_project`; `ChangeKind` gains `cf_project_changed`.

### Types

`CFLink` (`project_id, cf_project_id, linked_at`), `CFSnapshotInput` and
`CFSnapshot` (`project_id, cf_project_id, outcome, state, changed, detail,
cf_updated_at, cf_version_label, observed_at`; a recorded snapshot adds `id`),
all frozen. `state` and `changed` are set exactly when `outcome` is `observed`,
`detail` exactly when it is not.

### Methods

| Method | Effect |
| --- | --- |
| `cf_links(project_id)` | Links, in the order they were linked. |
| `cf_snapshots(project_id)` | Snapshots in id order. |
| `latest_cf_snapshots(project_id, cf_project_id)` | `(latest, latest observed)`; either may be `None`, and they are the same row when the latest is `observed`. |
| `record_cf_snapshot(CFSnapshotInput)` | In-process only. One insert in one transaction; the trigger appends a `cf_project_changed` change. `observed_at` is the caller's. An outcome that disagrees with its state, changes, and detail raises `ValueError` and writes nothing. |

Links are written only through the `link_cf_project` submission (insert, or no-op
if already linked). `cf_links`, `cf_snapshots`, and `latest_cf_snapshots` work
through a read-only handle.

### Retention

Snapshots are never deleted in this slice. A link is permanent (GitHub issue #7).


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
   under `src/amoeba/` and fails if any module other than
   `process/project_stores.py` calls the read-write `Store.open`.

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

## The Runner contract

*Added by slice 121. Schema version 9 (migration `009`).* The store's side of
the contract the Runner (initiative 120) builds on. What an intent body means,
which faults exist, and how a routing table is read are the Runner's. The store
holds and guards the values below and interprets none of them.

### `done` is terminal

No store write moves a `done` node, and none can leave a done node with work in
flight. Every refusal raises `InvalidTransitionError` naming the node.

| Write | Refused when |
| --- | --- |
| `update_node_status(node_id, status)` | The node is `done`, **for any target status, `done` included**. Also refused: moving *to* `done` while the node has an unresolved journal entry. |
| `block(...)` and any other block (`journal_escalate`'s not-blocked branch, a routing decision's `BlockEffect`) | The node is `done`. |
| `journal_issue(...)` | The node is `done`. |

`create_node(status=DONE)` stays allowed: creating a node as done moves nothing.

Two consequences callers rely on:

- **No unresolved journal entry sits on a done node.** Resolve the node's entry
  first, then mark it done.
- **A done node cannot be blocked.** A fault whose node is done is not escalated
  against the node. Raise a project-scoped escalation naming the node instead.

A store from before `009` that already holds an unresolved entry on a done node
fails explicitly when recovery reaches it: `journal_escalate` raises, naming the
node. Nothing moves the node out of `done`.

### Acknowledgment outcomes and desired state

| Vocabulary | Members |
| --- | --- |
| `AcknowledgmentOutcome` | `applied`, `no_op`, `rejected` |

`Message` gains `acknowledgment_outcome` and `acknowledgment_reason`. A row
acknowledged before `009` reads back with outcome `None`: it was acknowledged
before outcomes were recorded, and the migration does not guess.

| Method | Effect |
| --- | --- |
| `acknowledge_message(message_id, *, acknowledged_by, outcome, reason=None, desired_state=None)` | **One transaction:** the acknowledgment and its outcome, plus the desired-state write if one is given. `outcome` is required; there is no default. `rejected` needs a non-blank `reason`; for the others `reason` is optional but never empty. A `desired_state` is accepted only with `applied`. Raises `ValueError` (before any write), `NodeNotFoundError`, and `InvalidTransitionError` as before (missing, not an intent, or already acknowledged; the first outcome is kept). A failure in the desired-state write leaves the intent unacknowledged. |
| `intent_for_submission(submission_id)` | The intent row a submission created, or `None`. Before the Runner consumes it the row is unacknowledged; afterwards it carries the outcome. Works through a read-only handle. It scans, because `submission_id` has no index (GitHub issue #19). |
| `desired_state(project_id, *, node_id=None)` | The desired state at one target, or `None`. `node_id=None` is the project target. |
| `desired_states(project_id)` | Every desired state in the project: the project target first, then by node id. |

**Desired-state types** (frozen): `SetDesiredState(node_id, drive,
drive_until_step, hold)` replaces the target's whole row; `ClearDesiredState(node_id)`
deletes it, and clearing a target with no row writes nothing. `DesiredState`
holds `id, project_id, node_id, drive, drive_until_step, hold, message_id,
updated_at`, where `message_id` is the intent that last set the row. `drive` and
`hold` are nullable booleans; `None` means "not set at this target". Shape
rules, each a `ValueError`: `drive` and `hold` cannot both be `None` (use clear);
`drive_until_step` needs `drive is True` and non-empty text. A non-null
`node_id` must name a node in the intent's project, else `NodeNotFoundError`.
Merging a new intent with a target's earlier settings is the Runner's job; the
store stores what it is given. A row on an orphaned node is still returned.

### Project-scoped escalation

An `escalation` message for a fault that has no node. It has `fault_kind` set,
`node_id` and `blocked_state_id` null, and `closed_at` / `closed_by` once the
Runner closes it. Node escalations leave `fault_kind`, `closed_at` and
`closed_by` null; their closure is their block's resolution. At most one row is
open per `(project_id, fault_kind)`, enforced by a partial unique index.

| Method | Effect |
| --- | --- |
| `raise_project_escalation(project_id, *, fault_kind, payload)` | Returns the open row for the pair, unchanged and with nothing written, or inserts a new one. `fault_kind` must be non-empty text and `payload` a JSON-serializable mapping (`ValueError` otherwise). The existing `message_posted` trigger puts the insert on the change feed. |
| `open_project_escalations(project_id)` | Open project-scoped rows, in `seq` order. |
| `close_project_escalation(message_id, *, closed_by)` | Records `closed_at` and `closed_by`, and returns the row. Raises `InvalidTransitionError` if the row is missing, is not a project-scoped escalation, or is already closed; `ValueError` for an empty `closed_by`. A later fault of the same kind opens a new row. Only the Runner closes one. |

### Routing decisions, table versions and attempt counts

| Vocabulary | Members |
| --- | --- |
| `Route` | `advance`, `rerun`, `escalate` |

**Types** (frozen): `RoutingDecisionInput` (`project_id, node_id, inputs,
rule_id, table_version, amoeba_version, route, route_parameters,
journal_entry_id`), `RoutingDecision` (the same plus `id, attempt_step,
attempt_count, decided_at`), `RoutingTableVersion` (`version, content,
first_used_at`), and the two effects `StatusEffect(status)` and
`BlockEffect(context, payload)`.

| Method | Effect |
| --- | --- |
| `record_routing_decision(decision, *, table, effect, attempt_step)` | **One transaction:** store `table` if its version is new; insert the decision; if `attempt_step` is given, increment the `(node, step)` counter and record the new count on the decision; apply `effect`. A failure at any step leaves none of them. Returns the stored `RoutingDecision`. |
| `routing_decision(decision_id)` | One decision, or `None`. |
| `routing_decision_for_entry(journal_entry_id)` | The decision that routed a journal entry, or `None`. |
| `routing_decisions(node_id)` | A node's decisions, oldest first; empty when none. |
| `routing_table_version(version)` | The stored table, or `None`. A decision plus this read is everything needed to recompute it. |
| `attempt_count(node_id, step)` | The count. A pair with no row returns `0`, which is the true count. |

`StatusEffect` follows `update_node_status`'s rules, including the done-is-terminal
and unresolved-entry refusals, and refuses a blocked target status. `BlockEffect`
writes a `HUMAN` block and its escalation row (with the decision's
`journal_entry_id`) in the same transaction, and is refused on an already-blocked
node, as `block()` refuses it. Failures: `ValueError` for an empty text field,
`inputs` or `route_parameters` that are not JSON-serializable, an empty
`attempt_step`, a `table.version` that differs from the decision's, or an unknown
route; `NodeNotFoundError` if the node is not in the project;
`InvalidTransitionError` if `journal_entry_id` is missing or in another project,
or the effect is refused; `StoreIntegrityError` for a second decision on one
entry, or a table version stored again with different content (compared byte for
byte). Table versions are write-once, and a version that no decision used is
never stored. The only writer of attempt counts is `record_routing_decision`;
nothing resets them.

### The feed and secrets

This adds no `ChangeKind` and no trigger. A project-scoped escalation's raise
reaches the feed through `message_posted`; its closure, acknowledgments,
decisions and desired-state writes do not. A feed follower learns that a
project-scoped escalation opened but not that it closed, and reads the closure
from `amoeba inspect messages` or `open_project_escalations`.

Decision `inputs` and `route_parameters`, project-escalation payloads, and
routing-table content are stored verbatim and shown by inspection. **Callers
must not place secrets in them.** Nothing here is deleted.

### Lifecycle nodes and the CF index

*Added by slice 123. Schema version 10 (migration `010`).* The store holds a
node's link to Context Forge as an index and enforces that a link is unique. It
interprets neither: the lifecycle vocabulary (steps, predecessors, "ready") and
the rules that project CF's plan into nodes are the Runner's
(`amoeba.runner.lifecycle`).

- **`CFReference.index`** (`int | None`, column `nodes.cf_index`) is the
  initiative's or slice's index within its CF project. `create_node` and
  `update_cf_reference` write it; `update_cf_reference` replaces it with the other
  CF fields, so passing no index clears it. Rows from before `010` read as `None`,
  i.e. not linked.
- **One linked node per link key.** The partial unique index `idx_nodes_cf_link`
  on `(project_id, kind, cf_project, cf_index) WHERE cf_index IS NOT NULL`
  makes a second node with the same key a `StoreIntegrityError`; `create_node`
  rolls the whole insert back. The `kind` is part of the key because an initiative
  and its first slice share an index (initiative 120, slice 120); `cf_project`
  because one Amoeba project may link several CF projects. Nodes with no index
  (step nodes, unlinked nodes) never collide.
- **Step nodes** are `phase_or_artifact` nodes whose `cf.phase` holds the step
  (`architecture`, `slice_plan`, `slice_design`, `tasks`, `implementation`,
  `merge`, `integration`) and whose `cf.index` is `None`; they are linked through
  their parent.
- **Orphaning clears `cf.index` and `cf.slice_name`** and leaves the rest. The
  node is kept, never deleted, and a new node can then take its index.
- **Only the Runner's reconcile creates nodes.** A guard test
  (`tests/test_create_node_guard.py`) walks the AST of `src/amoeba` and fails if
  any module other than `runner/lifecycle/reconcile.py` calls `create_node`.
- **Inspection.** `amoeba inspect nodes` has a `cf_index` column (empty when
  unset); `--json` carries `cf_index` as a number or `null`.

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
| A status write or block on a done node; issuing a journal entry against a done node; marking a node done while it has an unresolved entry | `InvalidTransitionError` |
| Acknowledging a missing, non-intent or already acknowledged row; closing a missing, non-project-scoped or already closed escalation; a routing decision on an entry that is missing or in another project | `InvalidTransitionError` |
| A malformed outcome, reason, desired state, routing-decision field or fault kind | `ValueError` |
| A desired state or routing decision naming a node not in the project | `NodeNotFoundError` |
| A second routing decision for one entry; a table version stored with different content; a second open project escalation for one fault kind inserted directly (`raise_project_escalation` returns the open row instead) | `StoreIntegrityError` |
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

`from amoeba.store import store_dir` resolves the directory
(`store_dir(env=None) -> Path`; `env` defaults to `os.environ`, and the result
is not created). Resolution precedence, highest first:

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

The latest migration is `010` (slice 123, schema version 10: `nodes.cf_index` and
its partial unique link index). Before it, `009` (slice 121, schema version 9)
added the five new `messages` columns, the open-project-escalation index, and the
`routing_table_versions`, `routing_decisions`, `attempt_counts` and
`desired_states` tables. A read-only open of a store stamped older than the
code raises `StoreSchemaError`; only a read-write open migrates.

## Testing against the store

Open a throwaway store; never the central one. `tests/conftest.py` provides
`store_file` (a path under `tmp_path`) and `store` (an open store at that path).
A guard test (`tests/test_store_safety.py`) scans test modules for references to
the central-path resolver and fails on offenders, so the property is checked
mechanically rather than assumed. The scan is AST-based and therefore
multiline-aware.

## Future work

**A closure change kind (slice 121, D9).** A project-scoped escalation's closure
adds no `ChangeKind`, so a feed follower cannot see it close. Add one when a
subscriber needs it.

**Storage engine reversal trigger (PM).** The decision to use raw stdlib
`sqlite3` rather than SQLAlchemy Core + Alembic should be revisited if *either*:

- schema churn across slices 102–110 makes hand-written migrations painful, or
- the hand-rolled layer becomes recurring maintenance — repeated tweaks and bug
  fixes in the store plumbing itself.

Recorded so the switch is a decision made on evidence rather than a drift. The
mitigation that makes raw viable is structural: every SQL statement and every
column name lives in `sql.py`, so a column-name typo is a single-definition
concern.
