---
docType: reference
project: amoeba
slice: outbound-change-feed-and-detection-of-external-work
dateCreated: 20261015
dateUpdated: 20261018
status: complete
---

# The Amoeba Change Feed Contract

This document is the contract for `amoeba.feed` and the `amoeba feed` command.
It is written so that a slice design in initiative 160 (the Translator surface,
the notification bridge), or slice 109's network API, can consume the feed
**without reading the implementation**. If you find yourself opening
`follower.py` or migration `006` to answer a design question, that is a gap in
this document — say so.

## What the feed is

Every project store keeps an append-only **change log**. Each state change the
store commits appends one row to it, in the same transaction as the change
itself, so the log can never show a change the store does not have, or miss one
it does. A subscriber reads the log from a cursor it owns and follows it as it
grows.

Rows are written by SQLite triggers on the tracked tables, not by writer code.
A trigger fires for every write to its table, whoever makes it — the inbox,
recovery, review detection, and any path added later.

## What the feed is not

- **Not the source of truth.** The feed says a change happened. The store is
  the truth about current state. Read the store when you need state.
- **Not complete coverage of the store.** See "Coverage" below.
- **Not a network service.** A follower reads the store file directly, on the
  same machine. Slice 109 streams it over the network.
- **Not instant.** See "Latency".

## A change

`amoeba.store.Change` (also one JSON line from `amoeba feed`):

| Field | Type | Meaning |
| --- | --- | --- |
| `seq` | int | The cursor. Per project, strictly increasing, no gaps, commit order. |
| `project_id` | str | The project. |
| `kind` | `ChangeKind` | What changed (table below). |
| `node_id` | str or null | The node the change is about, when there is one. |
| `subject_id` | str | The id of the row that changed. |
| `payload` | object | Small, fixed per kind. Never the whole record. |
| `recorded_at` | ISO-8601 text | Copied from the changed row's own timestamp. |

### Kinds and payloads

`ChangeKind` is a closed vocabulary. An unknown kind on read is an error, never
a default.

| `kind` | `node_id` | `subject_id` | `payload` |
| --- | --- | --- | --- |
| `node_created` | the node | the node | `kind`, `parent_id`, `status` |
| `node_status_changed` | the node | the node | `from`, `to` |
| `verdict_recorded` | the node | verdict id | `verdict`, `review_type`, `provider_failure` (JSON boolean) |
| `message_posted` | the node, or null | message id | `channel` (`intent` or `escalation`) |
| `review_detected` | the node, or null | detection ledger id | `outcome`, `path` |
| `check_recorded` | the node | check id | `name`, `outcome`, `examined_count` (integer or null) |
| `cf_project_changed` | null | snapshot id | `cf_project_id`, `outcome`, `changed` (a list of field changes, or null for a failure) |

- `node_created` carries the initial status, so replaying from `seq` 0 rebuilds
  every node's current status without reading the store.
- `node_status_changed` is emitted only when the status actually changes. Block
  and resolve are status changes (for example `runnable` → `blocked_on_human`
  and back), so a human reply applied through the inbox shows up here.
- `verdict_recorded` carries no trust label: it is computed on read. Read the
  verdict from the store for its standing. It does not carry
  `judge_invocation_id` either; read the record by `subject_id`.
- `check_recorded` carries no standing, for the same reason: `vacuous` is
  computed on read from `examined_count`. Read the check from the store.
- `cf_project_changed` is emitted for every Context Forge snapshot, including a
  failure (`changed` null; read `detail` by `subject_id`) and a recovery with
  `changed: []`. Its payload is defined in
  [`context-forge-contract.md`](context-forge-contract.md#the-feed-entry).
- `review_detected` is emitted for the `ingested`, `unattributed`, and
  `unparseable` outcomes. `baseline` and `runner_issued` ledger rows emit
  nothing.
- A retried write that inserts nothing (a `record_verdict` retry, a replayed
  submission) emits nothing.

## Coverage

The feed announces node, verdict, message, detection, check, and Context Forge
snapshot changes only. It does
**not** announce:

- progress records (write-only; no reader yet);

- blocked-state rows themselves (their effect, the node status, is announced);
- finding status or finding observations;
- journal entries;
- submission outcomes. Every applied submission resolves into a row on a
  tracked table, which emits its own change. A **rejected** submission lands
  nothing, so it is not on the feed; read `submission(id)` (inbox contract) to
  learn of it. Slice 103's design named `inbox_submissions.applied_seq` as a
  possible feed source; that is superseded by this paragraph.

## Reading the feed

### `amoeba feed`

```bash
amoeba feed --project ID [--after SEQ] [--follow]
```

- Prints one JSON object per line, keys as in `Change`, flushed per line.
- `--after SEQ` (default 0) prints only changes with `seq > SEQ`.
- Without `--follow`: prints what exists, exits 0.
- With `--follow`: keeps printing new changes until interrupted. `SIGTERM` and
  Ctrl-C exit 0.
- Read-only, takes no lock, and works with the resident process running or
  stopped. A follower started while the process is stopped prints new changes
  once the process starts and writes.
- A missing project store, or a store at another schema version, exits through
  the CLI's store-error mapping (the same exit status `amoeba inspect` uses)
  and prints nothing on stdout.

### `follow()`

```python
from amoeba.feed import FeedSettings, follow

for change in follow(store_dir, project_id, after=last_seq, settings=FeedSettings()):
    handle(change)
    save_cursor(change.seq)
```

`follow(store_dir, project_id, *, after, settings, stop=None) -> Iterator[Change]`

- Opens the project store read-only and never writes.
- Yields every change after `after`, in order, then blocks waiting for new
  ones. It reads in batches of `feed_batch_size`; when none are left it checks
  SQLite's `PRAGMA data_version` every `follow_interval_seconds`, which changes
  only when another connection commits.
- `stop`: an optional callable checked between waits and between yielded
  changes. Returning true ends the iterator cleanly and closes the store.

`FeedSettings` (frozen dataclass, defined in `amoeba.feed`):

| Field | Default | Meaning |
| --- | --- | --- |
| `follow_interval_seconds` | 0.25 | How often an idle follower checks for a commit. |
| `feed_batch_size` | 500 | The most changes one read returns. |

### Follower failures

| Case | Behavior |
| --- | --- |
| Busy or locked read during a writer commit | Retried after one interval; never surfaces. |
| Store at a schema version other than the follower's | Raises `StoreSchemaError` before yielding. No retry: an upgrade needs the process. |
| Unknown project (no store file), or the store directory gone — at start or mid-follow | Raises `StorePermissionError` (a `StoreError`). |
| `stop` raises | The exception propagates. |
| `stop` returns true | The iterator ends cleanly. |

## Delivery guarantees

- Every committed change appears exactly once in the log, in commit order, with
  no gaps in `seq`.
- A follower that resumes with its last seen `seq` gets every later change
  once.
- Whether a subscriber *acts* on each change once depends on when it saves its
  cursor. **Save the cursor after acting, and make handling safe to repeat.**
  That gives at-least-once handling; saving before acting gives at-most-once.
- The store keeps no record of subscribers. The subscriber owns its cursor.
- Nothing is ever deleted from the change log in this slice. Retention and
  compaction are future work.
- Reading the feed never changes it.

## "Current state, then follow"

*Slice 109.* A read reports the feed `seq` it is current as of. Inside one
`Store.read_transaction()`, the listing's rows and `change_head(project_id)` are
read from one WAL snapshot; `amoeba.inspection.read_listing` returns both, as
`rows` and `as_of_seq`. A subscriber that needs current state and then
everything after it reads a listing, then follows with `after=as_of_seq`: no
change is missed and none the snapshot already reflects is repeated. Over the
network, every project listing response carries `as_of_seq`
([`network-contract.md`](network-contract.md)).

## Latency

A committed change reaches a follower within `follow_interval_seconds` of the
commit, plus the time to read the new rows. This is the only numeric promise
in the contract. The follower checks a counter on an interval; it does not
re-read or recompute state to find out whether anything changed.

## Trust boundary

The feed is readable by anyone who can read the store file — the same boundary
as the store. No payload carries review text, only ids, statuses, outcomes, and
file paths.
