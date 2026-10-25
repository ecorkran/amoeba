---
docType: reference
project: amoeba
slice: durable-inbox-and-message-queue
dateCreated: 20260923
dateUpdated: 20261022
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
  being told — or by following the change feed
  ([`feed-contract.md`](feed-contract.md)), on which an applied submission's
  effect appears. A rejected submission lands nothing and is not on the feed.
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
amoeba submit resolution --project amoeba --by operator --blocked-state-id <id> \
    --detail "loop is close; one more round" --decision retry \
    --instructions "Address the two schema concerns only."
amoeba submit intent --project demo --by operator \
    --body '{"intent": "drive", "until": "slice_design"}' [--node-id <id>]
amoeba submit check --project demo --by ci --node-id <id> --name <name> \
    --outcome passed --examined-count 412 --upstream <tool> \
    --upstream-version <label> --source command_output [--examined '{…}'] \
    [--baseline-ref <ref>] [--source-path <path>]
```

Each prints the submission id. `--id` reuses an id.

**The flag rule** (slice 104). One flag per payload field. A text or enum
field, or the optional form of either, takes its flag as typed. Every other
field takes JSON: `--score 82.5`, `--fallback-used null`,
`--findings '[...]'`, `--body '{"intent": "pause"}'`. A value that is not
valid JSON is a usage error naming the flag. The CLI does no type checking of
its own: the kind's payload model validates the result either way, and an
invalid payload is refused before anything is written.

### The kinds

| Kind | Payload | Effect | Rejected when |
| --- | --- | --- | --- |
| `create_project` | none | The project's store exists. The process creates it at once and it is usable immediately. | Never: a project that already exists is `applied` — the requested state holds. |
| `resolution` | `blocked_state_id`, `detail`, optional `decision`, optional `instructions` (see [A resolution's decision](#a-resolutions-decision)) | Fills that blocked state's resolution slot and returns its node to `runnable`. `resolved_by` is `submitted_by`. A decision and instructions are stored with it, and the block is flagged for the Runner to answer. | The blocked state does not exist, belongs to another project, or is already resolved. A blank `decision` or `instructions` fails validation and is quarantined instead. |
| `intent` | `body` (a JSON object; see [Intent bodies](#intent-bodies)), optional `node_id` | One unacknowledged row on the `intent` channel, carrying the submission id. | `node_id` is given and is not a node of this project. |
| `verdict` | A review result: `VerdictInput`'s fields except `id`, with provenance flattened — see [`evidence-contract.md`](evidence-contract.md#through-the-inbox) | One verdict record, whose id is the submission id, and one observation per finding. | The node is not in this project; a provider failure carries findings or a verdict other than `UNKNOWN`; `upstream_version` is empty; a judge sample (optional `judge_invocation_id`) is on another node or review type than the invocation's earlier samples. An unknown word in an enum field, or an omitted `derivation`, `fallback_used`, or `findings_parsed`, fails validation and is quarantined instead. |
| `check` | A mechanical check result: `node_id`, `name`, `outcome` (`passed`, `failed`, `errored`), `examined_count` (integer or `null`; **required** — `null` says "not reported"), `upstream`, `upstream_version`, `source` (`RecordSource`), and optional `examined` (JSON object), `baseline_ref`, `source_path` — see [`evidence-contract.md`](evidence-contract.md#checks) | One check record, whose id is the submission id. Its standing (`vacuous` when `examined_count` is 0) is computed on read. | The node is not in this project; `examined_count` is negative; `upstream_version` is empty. An unknown `outcome` or `source`, or an omitted `examined_count`, fails validation and is quarantined instead. |
| `link_cf_project` | `cf_project_id` (a non-empty string) | Links the project to that Context Forge project, so the watch records its pointer moves. Linking again is a no-op; several CF projects per Amoeba project, and several Amoeba projects per CF project, are allowed. The store does not check the id exists in CF: the first check records `missing` if it does not. See [`context-forge-contract.md`](context-forge-contract.md). | Never. An empty `cf_project_id` fails validation and is quarantined. |
| `watch_reviews` | `reviews_dir` (an absolute path), `active` (boolean) | Registers the directory for review detection, or sets whether it is watched. A first registration leaves it un-baselined; the detection tenant takes the baseline, so files already there are never ingested. Deactivating and reactivating never re-baselines: files that arrived while inactive are detected. Paths are stored as given, with no symlink resolution. See [`process-contract.md`](process-contract.md#review-detection). | Never. A relative `reviews_dir` fails validation and is quarantined. |

**A resolution targets a blocked state, never a node.** If a node was resolved
and blocked again since your reply was written, your reply names the old,
resolved block and is `rejected` — it is never redirected to the new one.

### A resolution's decision

*Slice 127.* A resolution of a blocked pipeline step names what the Runner should do
about it. The inbox stores the decision and the instructions as submitted and checks
only their shape; the Runner judges them.

| Field | Rule |
| --- | --- |
| `decision` | Optional text, non-blank when present. `retry`, `accept`, `handled`, `rerun` or `stop`, checked by the Runner, not the inbox. |
| `instructions` | Optional text, non-blank when present. Allowed only with `retry` or `accept`, and passed to Squadron verbatim as one argument. **No secrets**: the text is stored in the store as written and shown in the process list while the resume runs, the same rule as every payload. |

**What each decision does**, by where the step stands:

| Step stands at | Allowed decisions |
| --- | --- |
| A paused run (its latest `sq_run` recorded `paused`) | `retry` (resume with `--decision retry`), `accept` (resume with `--decision accept`; only when the pause is at a loop), `handled` (you dealt with the run yourself; the Runner re-observes it and routes what it finds), `stop` |
| A completed run whose outcome was escalated | `accept` (the step is done; nothing in CF or the review is edited), `rerun`, `stop` |
| A failed, orphaned or vanished run, a launch that never started, a run Squadron no longer has, or no run yet | `rerun`, `stop` |
| A human step | none: a bare resolution only |

`stop` parks the step as a block; resolving that block with any decision allowed for
where it stands starts it again.

**A bare resolution of a pipeline step is rejected `decision_required`.** This is a
change for existing submitters. Before slice 127 a resolution returned the node to
`runnable` and the Runner's dispatch rules then relaunched the step; now the Runner
answers it, and a pipeline step needs a decision. Name `rerun` for the old behavior.

**The Runner's answer** is on the blocked state, not the submission: the submission
record is the inbox's answer and is written once. The Runner answers each flagged
resolution, oldest first, at the start of its next tick, before it reads any node,
so no planner sees a resolved node before its resolution is checked. See
[Learning the outcome](#learning-the-outcome).

| `runner_code` (rejected) | Meaning |
| --- | --- |
| `unresolvable` | The step's latest command is still in flight, or its outcome is not routed yet. Try again after the next tick. |
| `unknown_decision` | The decision is not one of the five words. |
| `decision_required` | A pipeline step was resolved without a decision. |
| `decision_not_applicable` | A decision on a human step, or one not allowed where the step stands. |
| `not_at_loop` | `accept` on a pause that is not at a loop. |
| `usage_limit_pause` | `accept` on a usage-limit pause, whose round never ran. `retry` after the limit resets. |
| `checkpoint_unknown` | `retry` or `accept` on a pause whose kind or time the Runner cannot read. |
| `interactive_checkpoint` | `retry` at an interactive checkpoint, which a non-interactive resume cannot pass. Resume it by hand, then submit `handled`. |
| `instructions_not_applicable` | `instructions` with a decision other than `retry` or `accept`. |

A rejection blocks the step again on a human; its escalation payload lists the
decisions `allowed` where the step stands.

### Intent bodies

*Slice 124.* The inbox stores an intent's `body` without reading it. The Runner
validates it when it applies the intent, and answers every intent with exactly one
acknowledgment. The body is a JSON object with a closed `intent` field and no other
keys except `until`; an unknown key is rejected, so a misspelled `"untill"` cannot
silently drive everything.

| Body | Meaning |
| --- | --- |
| `{"intent": "drive"}` | Advance all work under the target. |
| `{"intent": "drive", "until": "<step>"}` | Advance work under the target up to and including `<step>` (`architecture`, `slice_plan`, `slice_design`, `tasks`, `implementation`, `merge`, `integration`, in that order). |
| `{"intent": "exclude"}` | Do not advance work under the target, unless a narrower target drives it. |
| `{"intent": "pause"}` | Issue nothing new under the target. A narrower target cannot override a pause. |
| `{"intent": "resume"}` | Remove the target's own pause. |
| `{"intent": "clear"}` | Remove all of the target's own settings, so the next one up applies. |

```
# drive initiative 120 through slice design
amoeba submit intent --project amoeba --by operator --node-id <initiative-120-node> \
    --body '{"intent": "drive", "until": "slice_design"}'
# stop everything new in the project
amoeba submit intent --project amoeba --by operator --body '{"intent": "pause"}'
```

**The target** is the message's `node_id`. No `node_id` targets the project.
Otherwise the node must be an initiative or a slice that Context Forge reports
(linked); `amoeba inspect nodes` lists node ids with their CF index. Nothing is
driven until an intent says so, so linking a project changes nothing by itself.

**Rejections** are answers, not errors. The intent is acknowledged `rejected` with
the reason `"<code>: <detail>"`; branch on the code, never on the detail (at most
512 characters).

| Code | When |
| --- | --- |
| `malformed_body` | The body is not one of the forms above: unknown key, unknown `intent` or `until`, `until` with anything but `drive`, or not an object. |
| `target_not_initiative_or_slice` | The `node_id` names a step node or any other kind of node. |
| `target_unlinked` | The node is orphaned or otherwise not linked to Context Forge. |
| `until_not_applicable` | `until` on a slice names an initiative-level step (`architecture`, `slice_plan`, `integration`). |

**`no_op`** means the target's settings would not change: the same intent twice,
`resume` with no pause, `clear` with no settings. Nothing is written, and the
stored settings keep the intent that last changed them. Driving to a step already
passed is not special: it is `applied` when it changes the settings (it restricts
work), `no_op` when it does not.

**Reading the answer.** `amoeba inspect messages --project P --channel intent`
shows `acknowledgment_outcome` and `acknowledgment_reason` for each intent; from
code, `intent_for_submission(submission_id)`. What the Runner has stored is
`amoeba inspect desired-states --project P`.

### Submission ids and retries

The submitter chooses the id, or `submit()` generates one. **The id is the
idempotency key: the first submission with an id wins.** A retry with the same
id is a no-op, so a submitter unsure whether its call succeeded submits again
with the same id. A reuse with *different* content is also a no-op — first wins —
and the process logs a WARNING; it is not an error, because a retry's timestamp
legitimately differs.

Ids and project ids become filenames, so each must be non-empty, contain no
path separator, and be neither `.` nor `..`.

**Over the network the id is required** *(slice 109)*. A client whose 202 was
lost cannot retry safely unless it chose the id, so `POST
/v1/projects/{project_id}/submissions` refuses a body without
`submission_id` (422 `submission_id_required`). Everything else is `submit()`
unchanged: the same validation, the same `reason` on refusal, and the same
first-wins rule. See [`network-contract.md`](network-contract.md).

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

**A resolution's own outcome.** *Slice 127.* Once `submission(id)` is `applied`, the
Runner's answer is on the blocked state:

```python
with Store.open_read_only(project_id="demo") as store:
    state = store.blocked_state(blocked_state_id)  # None if no such block
    state.awaits_runner   # True until the Runner has answered
    state.runner_outcome  # ResolutionOutcome.APPLIED or REJECTED, or None
    state.runner_code     # the rejection code above; None when applied
    state.runner_reason   # the detail, for people; branch on runner_code
```

`amoeba inspect blocked` shows each blocked node's `blocked_state_id`, the id a
resolution names.

**An intent's own outcome.** `submission(id)` reports only whether the inbox
applied the submission. For an `intent`, the Runner's later verdict is on the
message row: once `submission(id)` is `applied`, read it with

```python
with Store.open_read_only(project_id="demo") as store:
    intent = store.intent_for_submission(submission_id)  # None if no such row
```

The row is either unacknowledged (the Runner has not consumed it yet) or carries
`acknowledgment_outcome` (`applied`, `no_op` or `rejected`) and, when given, an
`acknowledgment_reason`; a `rejected` outcome always has one. An acknowledged
row whose outcome is `None` was acknowledged before outcomes were recorded
(schema version 9). See [`store-contract.md`](store-contract.md#acknowledgment-outcomes-and-desired-state).

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
  slice 106.
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
| `escalation`, project-scoped | The Runner, through `raise_project_escalation`, for a fault that has no node | `fault_kind` and the fault's `payload`; `closed_at` and `closed_by` once the Runner closes it. **`node_id` and `blocked_state_id` are null.** At most one is open per project and fault kind |

```python
with Store.open_read_only(project_id="demo") as store:
    for message in store.messages("demo", channel=Channel.ESCALATION, after_seq=cursor):
        deliver(message)
        cursor = message.seq
```

**A consumer owns its cursor.** Remember the last `seq` handled and ask for what
came after; every row is delivered exactly once by advancing it. The store keeps
no per-consumer state.

`pending_intents(project)` and `acknowledge_message(id, acknowledged_by=…,
outcome=…, reason=…, desired_state=…)` are the **Runner's** side of the `intent`
channel (initiative 120): acknowledging marks an intent consumed and records
its outcome, and a second acknowledgement raises. When the intent sets or clears
a desired state, that write happens in the **same transaction** as the
acknowledgment, so an intent cannot be acknowledged without its effect or the
reverse. A consumer that follows the `escalation` channel must expect rows with
no `node_id` or `blocked_state_id`. Details are in
[`store-contract.md`](store-contract.md#the-runner-contract).

## Inspection

| Command | Shows |
| --- | --- |
| `amoeba inspect inbox` | Every file pending in `new/`, quarantined, or failed, with attempts, reason, or last error. Opens no store. |
| `amoeba inspect submissions --project P` | Applied and rejected records, in `applied_seq` order. |
| `amoeba inspect messages --project P [--channel intent\|escalation]` | Messages in `seq` order, with `acknowledgment_outcome`, `acknowledgment_reason`, `fault_kind` and `closed_at` (each empty when unset). |

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

- **Push notification of outcomes and new messages** — slice 106's change feed.
- **Retention** of records, messages, and quarantined or failed files.
- **More kinds.** Adding one is three things: a `SubmissionKind` member, a
  payload model, and an effect. Slice 104 added `verdict` (judge samples use it,
with `judge_invocation_id`) and slice 107 added `check`. Progress records have
no kind yet.
