---
docType: reference
project: amoeba
slice: durable-inbox-and-message-queue
dateCreated: 20260923
dateUpdated: 20260927
status: complete
---

# The Amoeba Inbox Contract

This document is the contract for `amoeba.inbox` and for the messages the store
keeps. It is written so that a slice design in initiative 140 or 160, or a
notification bridge, can proceed **without reading the implementation**. If you
find yourself opening `inbox_tenant.py` to answer a design question, that is a
gap in this document — say so.

## What the inbox is

The **only** way a part outside the resident process contributes state. A
submitter drops a file; the resident process applies it to the project's store,
exactly once per submission id, and records the outcome. Consumers read the
result — and the message channels — through a read-only store handle.

Nothing outside the process ever opens a store read-write. That is what keeps
the store's single-writer model intact while many parts contribute to it.

## What the inbox is not

- **Not a network service.** Submission is a file write into the supervisor
  directory, on the same machine.
- **Not a reply channel.** A submitter learns the outcome by reading, not by
  being told. Push is slice 105.
- **Not a way to create nodes.** The kinds create projects, resolve blocks,
  record intents, and record reviews of existing nodes. Node creation from
  outside the process arrives with initiative 120.

## Submitting

```python
from amoeba.inbox import submit
from amoeba.store import SubmissionKind

submission_id = submit(
    project_id="demo",
    kind=SubmissionKind.RESOLUTION,
    payload={"blocked_state_id": "…", "detail": "approved"},
    submitted_by="notification-bridge",
    submission_id=None,  # pass your own to retry safely; generated when None
    store_dir=None,  # the supervisor directory; resolved like the store's
)
```

`submit()` validates everything **before** writing anything, then writes the
file durably and returns the id. It works whether or not the process is
running, and it opens no store.

The same thing from a shell — subcommands and flags come from the kinds and
their payload fields, so a new kind appears without a second list:

```
amoeba submit create-project --project demo --by operator
amoeba submit resolution --project demo --by operator \
    --blocked-state-id <id> --detail "approved"
amoeba submit intent --project demo --by operator \
    --body '{"want": "a review"}' [--node-id <id>]
```

Each prints the submission id. `--id` reuses an id.

**The flag rule** (slice 104). One flag per payload field. A text or enum
field, or the optional form of either, takes its flag as typed. Every other
field takes JSON: `--score 82.5`, `--fallback-used null`,
`--findings '[...]'`, `--body '{"want": "a review"}'`. A value that is not
valid JSON is a usage error naming the flag. The CLI does no type checking of
its own: the kind's payload model validates the result either way, and an
invalid payload is refused before anything is written.

### The kinds

| Kind | Payload | Effect | Rejected when |
| --- | --- | --- | --- |
| `create_project` | none | The project's store exists. The process creates it at once and it is usable immediately. | Never: a project that already exists is `applied` — the requested state holds. |
| `resolution` | `blocked_state_id`, `detail` | Fills that blocked state's resolution slot and returns its node to `runnable`. `resolved_by` is `submitted_by`. | The blocked state does not exist, belongs to another project, or is already resolved. |
| `intent` | `body` (a JSON object), optional `node_id` | One unacknowledged row on the `intent` channel, carrying the submission id. | `node_id` is given and is not a node of this project. |
| `verdict` | A review result: `VerdictInput`'s fields except `id`, with provenance flattened — see [`evidence-contract.md`](evidence-contract.md#through-the-inbox) | One verdict record, whose id is the submission id, and one observation per finding. | The node is not in this project; a provider failure carries findings or a verdict other than `UNKNOWN`; `upstream_version` is empty. An unknown word in an enum field, or an omitted `derivation`, `fallback_used`, or `findings_parsed`, fails validation and is quarantined instead. |

**A resolution targets a blocked state, never a node.** If a node was resolved
and blocked again since your reply was written, your reply names the old,
resolved block and is `rejected` — it is never redirected to the new one.

### Submission ids and retries

The submitter chooses the id, or `submit()` generates one. **The id is the
idempotency key: the first submission with an id wins.** A retry with the same
id is a no-op, so a submitter unsure whether its call succeeded submits again
with the same id. A reuse with *different* content is also a no-op — first wins —
and the process logs a WARNING; it is not an error, because a retry's timestamp
legitimately differs.

Ids and project ids become filenames, so each must be non-empty, contain no
path separator, and be neither `.` nor `..`.

### Errors

`submit()` raises only `InboxSubmitError` subclasses, and after either one
**nothing is left in the inbox**:

| Error | Meaning |
| --- | --- |
| `InvalidSubmissionError` | The project id, id, envelope, or payload is invalid. Its `reason` is the quarantine reason a hand-written file with the same content would receive. |
| `SubmissionWriteError` | The submission was valid but could not be written durably. |

`amoeba submit` exits with `SUBMISSION_REFUSED` (9) for either. A malformed flag —
`--body` that is not a JSON object, a missing required field — is an argparse
usage error instead.

## Learning the outcome

```python
from amoeba.store import Store

with Store.open_read_only(project_id="demo") as store:
    record = store.submission(submission_id)  # None until applied
```

`None` means "not applied yet". Once applied, the record's `outcome` is
`applied` or `rejected`, with a `reason` when rejected. For `create_project`,
the store file not existing yet is the same answer as `None`. The process
builds a new store under a temporary name and renames it into place once
migrated, so a store that exists is always complete.

**Rule for a submitter that creates a project:** wait until
`submission(create_id)` reports `applied` before submitting into that project.
A submission that reaches the process before its project exists is quarantined
as `no_store_for_project`, not held.

## What happens to a file

Every submission reaches exactly one terminal, inspectable place. None is
dropped silently.

| Place | Meaning | Where to look |
| --- | --- | --- |
| `applied` / `rejected` | Attributed to a store and recorded there. The file is deleted. | `store.submissions(project)`, `amoeba inspect submissions --project P` |
| quarantined | The submission is **bad**: it could not be attributed to an open store. Moved to `inbox/quarantine/` beside a `.reason.json`. | `amoeba.inbox.quarantined()`, `amoeba inspect inbox` |
| failed | The submission is **good** but the store could not apply it `inbox_max_attempts` times. Moved to `inbox/failed/` with its `.attempts.json`. | `amoeba.inbox.failed()`, `amoeba inspect inbox` |

Quarantine reasons: `unparseable_envelope`, `unknown_envelope_version`,
`unknown_kind`, `invalid_project_id`, `invalid_payload`, `no_store_for_project`.

**A sick store stops the process — but not forever.** If applying a valid
submission raises (a corrupt store file, a permission problem), the process
records the attempt beside the file and stops, so the operator hears about it.
The first `inbox_max_attempts - 1` failures each stop the process; the next one
parks the file in `failed/`, logs at ERROR, and the process carries on with
the next file. The count lives on disk, so it survives the restarts.

**Requeueing** is moving a file from `quarantine/` or `failed/` back to
`inbox/new/`. Move its `.attempts.json` with it: a requeued file resumes at its
recorded count rather than getting a fresh set of attempts. Nothing in the
inbox is ever deleted except a file that has been recorded.

## Delivery and replay semantics

### Guaranteed

- **Durability on return.** When `submit()` returns, the submission is
  fsync-durable on a POSIX filesystem — whether the process is up or down.
- **Exactly-once effect per submission id.** Redelivery, a process restart, and
  a submitter retry with the same id cannot apply it twice.
- **Atomic effect and record.** No state exists in which a slot is filled but
  the submission is unrecorded, or the reverse.
- **Every submission reaches a terminal, inspectable state:** `applied`,
  `rejected` (with reason), quarantined (with reason), or failed (with attempt
  count and last error).
- **One authoritative order, assigned by the receiver.** `applied_seq` on
  submission records and `seq` on messages are total, gap-tolerant, and never
  reassigned.
- **Messages are replayable.** `messages(project, channel=…, after_seq=0)`
  returns a channel's full history in a stable order, any number of times.
- **Every human block has an escalation row, committed with it** — and every
  journal entry that recovery escalates has one, whether recovery created the
  block or found the node already blocked.

### Not guaranteed

- **That apply order equals submit order.** It does, except for submissions
  racing within one submitter's timestamp-to-rename window, or across a
  wall-clock step. Anything that needs order reads `applied_seq` or `seq`.
- **Latency.** A file is applied on the next tick — bounded below by
  `idle_interval_seconds` when the process is idle, unbounded while it is down.
- **Notification of the outcome.** Submitters poll `submission(id)`. Push is
  slice 105.
- **That a valid submission is applied.** A `resolution` whose blocked state
  someone else resolved first is `rejected` as stale. First writer wins; the
  loser is told why.
- **That "blocked state still open" means "no human has seen it yet"** — for an
  escalation that recovery attached to a judge or checkpoint block, which that
  block's own owner can resolve. Delivery by cursor is the guarantee; whether
  the block is still open is a convenience query.
- **Retention limits.** Records and messages are never deleted in this slice.

## Reading messages

The store keeps two channels. Both are readable through a **read-only** handle,
so a consumer needs no write access.

| Channel | Written by | A row carries |
| --- | --- | --- |
| `escalation` | The store's block writer, in the same transaction as every `HUMAN` block; and recovery, when it escalates a journal entry | `node_id`, `blocked_state_id`, `journal_entry_id` when recovery raised it, and the block's optional `payload` |
| `intent` | An applied `intent` submission | `submission_id` (provenance), optional `node_id`, and the submission's `body` as `payload` |

```python
with Store.open_read_only(project_id="demo") as store:
    for message in store.messages("demo", channel=Channel.ESCALATION, after_seq=cursor):
        deliver(message)
        cursor = message.seq
```

**A consumer owns its cursor.** Remember the last `seq` handled and ask for what
came after; every row is delivered exactly once by advancing it. The store keeps
no per-consumer state.

`pending_intents(project)` and `acknowledge_message(id, acknowledged_by=…)` are
the **Runner's** side of the `intent` channel (initiative 120): acknowledging
marks an intent consumed, and a second acknowledgement raises.

## Inspection

| Command | Shows |
| --- | --- |
| `amoeba inspect inbox` | Every file pending in `new/`, quarantined, or failed, with attempts, reason, or last error. Opens no store. |
| `amoeba inspect submissions --project P` | Applied and rejected records, in `applied_seq` order. |
| `amoeba inspect messages --project P [--channel intent\|escalation]` | Messages in `seq` order. |

All accept `--json`, and all work with the process running or stopped. The same
listings are in Python as `amoeba.inbox.pending()`, `quarantined()`, and
`failed()`.

## Settings

Both are `ProcessSettings` fields with an `amoeba start` flag:

| Setting | Flag | Default | Meaning |
| --- | --- | --- | --- |
| `inbox_batch_size` | `--inbox-batch-size` | 100 | The most files one tick handles. |
| `inbox_max_attempts` | `--inbox-max-attempts` | 3 | Failed applies of one file before it is parked in `failed/`. |

## Security

- **Payloads are stored verbatim and shown by `amoeba inspect`.** Callers must
  not place secrets in them — the same rule as journal parameters.
- Inbox directories are created with the user's default permissions. Anyone who
  can write to the supervisor directory can submit; there is no authentication
  beyond filesystem permissions.

## Future work

- **Push notification of outcomes and new messages** — slice 105's change feed.
- **Retention** of records, messages, and quarantined or failed files.
- **More kinds.** Adding one is three things: a `SubmissionKind` member, a
  payload model, and an effect. Slice 104 adds verdict and judge-sample kinds.
