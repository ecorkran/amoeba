---
docType: slice-design
slice: durable-inbox-and-message-queue
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102]
interfaces: [104, 105, 106]
dateCreated: 20260921
dateUpdated: 20260921
status: not_started
---

# Slice Design: durable-inbox-and-message-queue

## Overview

Slice 102 made the sole-writer model mechanical: one resident process, one lock, and a guard test that nothing else opens a store read-write. That leaves the parts that run *outside* the process — the Judge, the Translator, the notification bridge — with no way to contribute state. This slice is where the sole-writer decision is paid for. It adds:

1. **The inbox** — a durable, append-only drop directory inside the supervisor directory. Any process can submit to it at any time, including while the resident process is down. A submission is a small JSON envelope written atomically.
2. **The apply loop** — the first real `Tenant`. It consumes pending submissions and applies each to the right project store. The effect and the record that it was applied commit in **one transaction**, so replay is a no-op.
3. **The channels** — intent (Translator → Runner), escalation (Runner → Translator and bridge), and inbound human reply (bridge → a blocked node's resolution slot), with documented delivery and replay semantics.
4. **Runtime project creation** — a `create_project` submission makes the resident process create and open a new project store while running. Until now nothing inside the process could bring a project into existence.

Completing it closes the first vertical path through the substrate: an outside writer creates a project and submits to it, the process applies, state persists, a restart preserves it.

## Value

Architectural enablement. Without this slice, initiatives 140 and 160 cannot exist: their parts are out-of-process by architecture and the store refuses them. After it:

- The notification bridge and Translator (160) have a one-call `submit()` API and never touch SQLite for writing. The submit side is "write a file, rename it", so a submitter written in another language needs no SQLite binding.
- A human reply becomes a filled resolution slot and a runnable node with no part calling another part.
- The Runner (120) has a durable intent queue to consume and gets escalation delivery for free whenever a node is blocked on a human — including the blocks recovery writes.
- A project can be brought under supervision without stopping the process or running a script that opens a store read-write.
- The ratified claim "inbox submissions land durably while the process is down and are applied on restart" is demonstrated, not asserted.

## Technical Scope

**Included**

- `amoeba.inbox` — the out-of-process-facing package: envelope models, directory layout, `submit()`, and read-only listing of pending and quarantined submissions. It touches the filesystem only; it never opens a store read-write.
- `InboxTenant` — the apply loop, registered by `amoeba start`.
- Store additions: schema migration `004`, `apply_submission`, the submission record with a receiver-assigned sequence, the `messages` table with the `intent` and `escalation` channels, and message read/acknowledge methods.
- Three submission kinds — `create_project`, `resolution`, `intent` — behind a closed vocabulary that later slices extend.
- Runtime store creation: `host.open_project()`, with store opening extracted from `host.py` into one module that remains the single permitted read-write opener.
- An escalation message written automatically, in the same transaction, whenever a node is blocked on `HUMAN`, and whenever recovery escalates a journal entry onto a node that is already blocked (D3).
- `amoeba submit` (an operator- and bridge-usable CLI writer) and inspection listings for the inbox, submissions, and messages.
- `docs/inbox-contract.md` — delivery and replay semantics: what is guaranteed and what is not.
- A load-tier test: concurrent submitters against a kill-looped process.

**Excluded**

- The Translator, the notification bridge, and any message *content* semantics — initiative 160. Payloads are stored opaquely.
- The Runner's consumption of intent and any routing — initiative 120.
- Populating a new project's node tree. `create_project` yields an empty store; building the tree from CF is the Runner's job (120).
- Verdict, finding, and judge-sample submission kinds — slice 104 adds them through the seam this slice defines.
- Push notification that a message or state change exists — slice 105's change feed. Until then consumers poll the read API.
- Removing or archiving a project.
- Retention of applied submission records and messages — already Future Work in the slice plan.
- Authentication of submitters. The inbox is protected by filesystem permissions on the supervisor directory, as the stores already are.

## Dependencies

### Prerequisites

- **Slice 101** — `Store`, `block()` / `resolve()`, the migration mechanism, typed failure modes, `amoeba.store.paths` including its project-id validation.
- **Slice 102 (merged at `08d2f88`, review fixes at `b8f2b51`)** — `ResidentProcess`, the `Tenant` protocol and its obligation, `ProcessSettings`, `Store.open_read_only`, the inspection listing registry, the writer guard test, `EXPECTED_SCHEMA_VERSION = 3`.
- **`pydantic`** — already a runtime dependency; used here for the submission envelope, which is externally-authored data.

No new third-party dependency.

### Interfaces Required

From 102's process contract: `Tenant` (`name`, `tick(host) -> bool`), `host.store_for()`, `host.project_ids`, `host.stop_requested`, `host.settings`, and the supervisor directory as the home for the inbox's files. From 101's store contract: `block`, `resolve`, `blocked_state_for`, `get_node`, and the single-transaction composition pattern `journal_escalate` already uses.

## Architecture

### Component Structure

```
src/amoeba/
  inbox/
    envelope.py        Submission envelope + per-kind payload models (pydantic)
    layout.py          directory names and the filename scheme, defined once
    submit.py          submit() — the only write path open to outside parts
    pending.py         read-only listing of pending and quarantined files
  process/
    inbox_tenant.py    InboxTenant — the apply loop
    project_stores.py  ProjectStores — open all, open one at runtime, close all
  store/
    inbox.py           InboxMixin: apply_submission, submission, submissions
    messages.py        MessagesMixin: messages, pending_intents, acknowledge_message
    inbox_models.py    SubmissionKind, SubmissionOutcome, Channel, records
    sql_inbox.py       every statement and column name for both tables
    schema/004_inbox_and_messages.sql
  cli/
    submit.py          `amoeba submit …`
```

**Dependency direction.** `amoeba.inbox` imports vocabularies from `amoeba.store` (models only) and never imports `Store` for writing. `amoeba.store` does not import `amoeba.inbox`: `apply_submission` takes plain, already-validated values. The tenant is the only module that knows both.

**`ProjectStores`** takes over the read-write opening that lives in `host.py` today (`_open_stores`, `store_for`, `project_ids`, `_close_stores`) and adds `open_project(project_id)`. `host.py` delegates to it. The writer guard's `PERMITTED_MODULES` changes from `process/host.py` to `process/project_stores.py` — still exactly one module, and the guard's deliberate-widening test still pins a set of size one. This also brings `host.py` (378 lines) back toward budget, which slice 102 left open.

**Inbox directory**, under the supervisor directory:

| Path | Holds |
| --- | --- |
| `inbox/tmp/` | Files being written. Never read by the apply loop. |
| `inbox/new/` | Complete submissions awaiting apply. |
| `inbox/quarantine/` | Submissions that could not be attributed to an open project store, each with a `.reason.json` sidecar. |

### Data Flow

Submit (any process, any time):

```
submit(project_id, kind, payload, submitted_by, submission_id=None)
  validate project id, envelope, and payload for the kind   # fail before writing
  write inbox/tmp/<name>  → fsync file
  rename → inbox/new/<name>  → fsync directory  # durable once this returns
  return submission_id
```

`<name>` is `{submitted_at_ns:020d}-{submission_id}.json`. The timestamp only orders the drain; it is not the authoritative order (see D4).

Apply (one `InboxTenant.tick`):

```
for file in sorted(inbox/new/)[: settings.inbox_batch_size]:
    if host.stop_requested: break
    envelope = parse(file)          # unparseable → quarantine
    if envelope.kind is CREATE_PROJECT:
        host.open_project(envelope.project_id)     # idempotent: create-or-open
    store = host store for envelope.project_id     # absent → quarantine
    store.apply_submission(envelope…)              # ONE transaction:
        id already recorded?  → no-op (replay)
        kind's precondition holds? → effect + record(outcome=applied)
        otherwise                  → record(outcome=rejected, reason)
    delete file
return whether any file was handled
```

Crash analysis — the file delete is deliberately *after* the commit:

| Crash point | Disk | Next start |
| --- | --- | --- |
| During `submit`, before rename | stray file in `tmp/` | ignored; submitter saw no success and retries with the same id |
| Before the apply transaction commits | file in `new/`, no record | applied normally |
| After `open_project`, before the record commits | new empty store, file in `new/`, no record | store is discovered and opened at start; `open_project` finds it open; record written |
| After commit, before delete | file in `new/`, record exists | id hit → no-op → file deleted |

Effects by kind:

| Kind | Payload | Precondition | Effect |
| --- | --- | --- | --- |
| `create_project` | none | none | the store exists and is open; the record is its first row. Naming a project that already exists is `applied`, not rejected — the requested state holds |
| `resolution` | `blocked_state_id`, `resolved_by`, `detail` | that blocked state exists in this project and is the node's **open** one | `resolve()` — slot filled, node flips `runnable` |
| `intent` | opaque mapping, optional `node_id` | `node_id`, if given, exists in this project | a row on the `intent` channel |

A `resolution` targets a **blocked-state id, not a node id**. A node can be blocked again after resolution; a late human reply to the first block must not resolve the second. A stale target is recorded `rejected`, never redirected.

### State Management

- **Durable, supervisor directory:** the inbox files. A file in `new/` is a submission not yet known to be applied — nothing more. Its lifetime is from `submit()` to apply.
- **Durable, each project store:** `inbox_submissions` (the idempotency and audit record) and `messages`. SQLite remains the home of everything durable and queryable.
- **In memory:** the open-store map, which now grows at runtime. Nothing authoritative: it is rebuilt from the directory at every start. The tenant holds no cursor; the directory listing is the queue.

## Technical Decisions

D1–D4 are choices a reasonable Project Manager could make differently. **All four, and the project-creation scope, were ratified by the PM on 20260921.**

### Technology Choices

**D1 — The inbox hand-off is an atomic file drop; SQLite holds everything durable. (PM — ratified 20260921)** The architecture leaves the inbox's durability mechanism to this slice, constrained by "accept appends from outside the process while the process is down". Write-to-`tmp`, fsync, rename is atomic on POSIX and needs no lock. The reasons that carry the decision:

- *No process other than the resident one ever opens an Amoeba SQLite file read-write* stays literally true, so the writer guard remains one rule with no carve-out.
- Submitters never contend with the Runner for a write lock.
- The submit side has no SQLite dependency, so a bridge in another language can submit.
- The inbox is supervisor-level rather than inside any one project's store, which is what lets a `create_project` submission exist before its store does.

What it gives up: a transactional global sequence at submit time (answered by D4), and SQL queries over *pending* submissions (a directory listing instead). The rejected alternative, a shared `inbox.sqlite3` that submitters open read-write, is workable — SQLite recovers a dead writer's WAL routinely and contention at this volume is mild — so this is a judgment on the sole-writer principle and submitter portability, not a claim that the alternative is broken. *Also rejected:* submitters writing an inbox table inside the project store, which puts outside writers on the very lock sole-writer exists to keep uncontended.

*Context recorded at ratification:* Squadron will not build its daemon, server, or multi-agent communication layer; Amoeba absorbs whatever of that is useful as it goes. That makes a fast, queryable local store the long-term foundation, which is why every durable record — submissions, messages, and whatever is absorbed later — lands in SQLite and only the hand-off is a file.

**D2 — Exactly-once effect from a submitter-generated id. (PM — ratified 20260921)** Delivery of a file to the apply loop is at-least-once; the effect is exactly-once because the submission id is unique in `inbox_submissions` and the record commits with the effect. The submitter generates the id (a default is generated if none is passed), which makes `submit()` safely retryable: a bridge unsure whether its call succeeded resubmits with the same id. A second submission reusing an id with *different* content is a no-op — first one wins — logged at WARNING. It is not an error, because the second file may legitimately be a retry whose timestamp differs.

**D3 — Escalation messages are written by the store's one block writer, not by callers. (PM — ratified 20260921)** Whenever a node is blocked on `BlockedKind.HUMAN`, the store writes one row on the `escalation` channel in the same transaction, carrying `node_id`, `blocked_state_id`, and an optional opaque `payload` (a new keyword-only argument to `block()`, default `None`, stored as NULL). A human-blocked node without an escalation cannot exist, and no caller has to remember a second call. This is deterministic plumbing, not a decision — the substrate does not choose *whether* to escalate; it records that a human block happened on the channel defined for exactly that. `blocked_on_judge` and `blocked_on_sq_checkpoint` write no message; no channel is defined for them and the Runner observes both directly.

Two consequences for slice 102's recovery, both intended:

- *Recovery blocks now notify.* Today `journal_escalate` blocks a node on `HUMAN` and nothing else happens; a person finds out only by running `amoeba inspect blocked`. Under D3 that block also produces an escalation row, so an ambiguous Squadron match after a crash reaches the human through the bridge. `journal_escalate` currently writes its block through a private `_block_for_entry` rather than through `block()`, so the two paths are consolidated into **one internal block writer** that both call, and the escalation row is written there. Without that consolidation recovery blocks would silently miss the row.
- *The already-blocked branch also notifies.* When the entry's node is already blocked, `journal_escalate` writes no second block — and would therefore write no message, leaving an ambiguous command visible only through `inspect journal`. It now writes an escalation row pointing at the node's **existing open blocked state**, with `journal_entry_id` set. This holds whatever the existing block's kind is: the node may be waiting on the Judge, but the unexplained command still needs a person.

*Alternative:* a public `post_message()` the Runner calls after `block()`. Rejected because it reintroduces a two-call window and a way to forget.

**D4 — Authoritative order is assigned by the receiver at apply. (PM — ratified 20260921)** Every submitter writes to a local directory, so all filename timestamps come from the same system clock as the resident process; there is no cross-machine skew. But the process may be down when a file lands, so it cannot stamp arrival, and a submitter takes its timestamp slightly before its rename completes. Filename order is therefore a drain order that is right except for submissions racing within that window or across a wall-clock step. The order that anything may *rely* on is assigned by the receiver: `inbox_submissions.applied_seq` and `messages.seq` are autoincrement integers written inside the apply transaction. "Which came first" is answered from those, never from `submitted_at`, which is kept as data.

**The inbound-reply channel has no message table.** A reply terminates in a resolution slot. Its durable record is the `inbox_submissions` row; materializing it again as a message would duplicate the fact.

### Patterns and Conventions

**Closed vocabularies, `StrEnum`, defined once in `inbox_models.py`:** `SubmissionKind` (`create_project`, `resolution`, `intent`), `SubmissionOutcome` (`applied`, `rejected`), `Channel` (`intent`, `escalation`), and `QuarantineReason` (`unparseable_envelope`, `unknown_envelope_version`, `unknown_kind`, `invalid_project_id`, `invalid_payload`, `no_store_for_project`). `submitted_by` and `resolved_by` are free-form data and are never branched on.

**Adding a submission kind** (slice 104 will) is three things, all of them: an enum member, a payload model, and an effect inside `InboxMixin`. The kind-to-payload-model and kind-to-effect tables are each defined once; a kind missing from either fails a test, not a user.

**Project ids become filenames.** The one validation rule already in `amoeba.store.paths` (non-empty, no path separator, not `.` or `..`) is reused by `submit()`, by the tenant before `open_project`, and nowhere re-implemented. `submit()` raises on an invalid id; a hand-written file carrying one is quarantined as `invalid_project_id` and never reaches the filesystem path computation for a store.

**Rejection is a recorded outcome, not an exception.** Preconditions are checked as explicit branches inside the apply transaction, in the manner of `journal_escalate`'s already-blocked branch. `InvalidTransitionError` is never caught to implement rejection — that would also swallow genuine bugs. A rejected submission is terminal and never retried.

**Quarantine versus rejection.** A submission that can be attributed to an open project store always ends as a store record (`applied` or `rejected`). Only one that *cannot* — unparseable, unknown envelope version or kind, invalid project id or payload, or no store for its project — is quarantined as a file, because there is no store row to write. Quarantine moves the file and writes the sidecar; it never deletes content. An operator requeues by moving the file back to `new/`. With `create_project` available, `no_store_for_project` is the abnormal case — a submission that raced ahead of, or was never preceded by, its project's creation — not the normal path.

**Envelope versioning.** The envelope carries `envelope_version`. An unknown version is quarantined, never best-effort parsed. Unknown extra fields are ignored.

**Tenant obligation.** `tick()` handles at most `inbox_batch_size` files and checks `stop_requested` between files. Each file is one short transaction, so an abandoned tick is covered by the crash table above. `inbox_batch_size` lives in `ProcessSettings` with a `start` flag, like every other tunable.

**Error handling.** `submit()` raises typed errors (`InboxSubmitError` family) on validation or I/O failure and leaves nothing in `new/`. In the tenant, an unexpected exception from `apply_submission` or `open_project` is logged with `logger.exception` and re-raised — the file stays in `new/`, and the process stops rather than skipping a submission and applying later ones out of order. A `StoreError` is not converted to quarantine: quarantine means "this submission is bad", never "the store is unwell".

## Implementation Details

### API Contracts

**Out-of-process API (`amoeba.inbox`, pinned by a public-API test):**

| Call | Effect |
| --- | --- |
| `submit(*, project_id, kind, payload, submitted_by, submission_id=None, store_dir=None) -> str` | Validates, writes durably, returns the submission id. Works whether or not the process is running. |
| `pending(store_dir=None) -> list[PendingSubmission]` | Files in `new/`, in drain order. |
| `quarantined(store_dir=None) -> list[QuarantinedSubmission]` | Quarantined files with their recorded reason. |

Envelope fields: `envelope_version`, `id`, `project_id`, `kind`, `submitted_by`, `submitted_at`, `payload`.

A submitter learns its outcome by reading, not by reply: `Store.open_read_only(project_id=…).submission(submission_id)` returns `None` until applied, then the record. For `create_project`, the store file not existing yet is the same answer as `None`.

**Host addition (`docs/process-contract.md`):**

| Member | Meaning |
| --- | --- |
| `open_project(project_id) -> Store` | Create-or-open the project's store read-write and add it to the open set. Idempotent. A new store is migrated to the current schema by `Store.open` as usual; its journal is empty, so there is nothing to recover. `project_ids` reflects it immediately. A failure raises and stops the process, consistent with "never run blind to a project". |

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `apply_submission(*, submission_id, kind, submitted_by, submitted_at, payload) -> SubmissionRecord` | One transaction: replay check, precondition, effect, record. Returns the existing record unchanged on replay. |
| `submission(submission_id)` | One record, or `None`. |
| `submissions(project_id, *, outcome=None)` | In `applied_seq` order. What inspection consumes. |
| `messages(project_id, *, channel, after_seq=0)` | Rows with `seq > after_seq`, ascending. The replay primitive. |
| `pending_intents(project_id)` | Unacknowledged `intent` rows, ascending. What the Runner consumes. |
| `acknowledge_message(message_id, *, acknowledged_by)` | Marks an `intent` row consumed. Raises `InvalidTransitionError` if already acknowledged or not an intent. |
| `block(node_id, *, kind, context, payload=None)` | Unchanged except D3: a `HUMAN` block also writes the escalation row. |
| `journal_escalate(entry_id, *, reason)` | Unchanged signature. Per D3: its block goes through the shared block writer, and its already-blocked branch writes an escalation row against the existing open blocked state. |

`SubmissionRecord` and `Message` are frozen dataclasses, consistent with the existing transfer types.

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba submit create-project --project ID --by NAME [--id ID]` | Calls `submit()`; prints the submission id. |
| `amoeba submit resolution --project ID --blocked-state ID --by NAME --detail TEXT [--id ID]` | Same. |
| `amoeba submit intent --project ID --payload-json JSON [--node ID] --by NAME [--id ID]` | Same. |
| `amoeba inspect inbox` | Supervisor-level (like `projects`): pending and quarantined files. |
| `amoeba inspect submissions\|messages --project ID` | Registered into 102's listing registry. `messages` accepts `--channel`. All accept `--json`. |

`submit` subcommand names derive from `SubmissionKind`, as `inspect` names derive from the listing registry — never the reverse.

### Database / Storage Schema

Migration `004_inbox_and_messages.sql`, `EXPECTED_SCHEMA_VERSION` → 4.

`inbox_submissions`: `applied_seq` (INTEGER PRIMARY KEY AUTOINCREMENT — the receiver-assigned order, D4), `id` (UNIQUE — the submitter's id and the idempotency key), `project_id`, `kind`, `submitted_by`, `submitted_at`, `payload` (JSON text), `outcome`, `reason` (NULL when applied), `applied_at`.

`messages`: `seq` (INTEGER PRIMARY KEY AUTOINCREMENT — the replay cursor), `id`, `project_id`, `channel`, `node_id` (nullable FK), `blocked_state_id` (nullable FK; set for escalations), `journal_entry_id` (nullable FK; set when recovery raised the escalation), `submission_id` (nullable; set for intents, as provenance), `payload` (JSON text, nullable), `created_at`, `acknowledged_at`, `acknowledged_by`. Index on `(project_id, channel, seq)`; partial index on unacknowledged intents.

Existing human-blocked states written before this migration have no escalation row. The migration backfills one row per **open** `HUMAN` blocked state so D3's invariant holds from version 4 onward; resolved historical blocks are not backfilled.

### Delivery and Replay Semantics

This is the content `docs/inbox-contract.md` must state.

**Guaranteed**

- **Durability on return.** When `submit()` returns, the submission is fsync-durable on a POSIX filesystem — process up or down.
- **Exactly-once effect per submission id.** Redelivery, restart, and submitter retry with the same id cannot double-apply.
- **Atomic effect and record.** No state exists in which a slot is filled but the submission is unrecorded, or the reverse.
- **Every submission reaches a terminal, inspectable state:** `applied`, `rejected` (with reason), or quarantined (with reason). None is dropped silently.
- **One authoritative order, assigned by the receiver.** `applied_seq` and `messages.seq` are total, gap-tolerant, and never reassigned.
- **Messages are replayable.** `messages(after_seq=0)` returns a channel's full history in a stable order, any number of times. Escalation consumers hold their own cursor and are delivered every row once by advancing it.
- **Every human block has an escalation row committed with it**, and every journal entry recovery escalates has one — whether it created the block or landed on an existing one.

**Not guaranteed**

- **That apply order equals submit order.** It does except for submissions racing within one submitter's timestamp-to-rename window, or across a wall-clock step. Anything that needs order reads `applied_seq` / `seq`.
- **Latency.** Apply happens on the next tick; bounded below by `idle_interval_seconds` when idle, unbounded while the process is down.
- **Notification of outcome.** Submitters poll `submission(id)`. Push is slice 105.
- **That a valid submission is applied.** A `resolution` whose blocked state was resolved by someone else first is `rejected` as stale. First writer wins; the loser is told why.
- **That "blocked state still open" means "a human has not yet seen it"** for an escalation that recovery attached to a Judge or checkpoint block: that block can be resolved by its own owner. Delivery by cursor is the guarantee; open-ness is a convenience query.
- **Retention limits.** Records and messages are never deleted in this slice.

## Integration Points

### Provides to Other Slices

- **104:** the submission-kind seam (enum member + payload model + effect) for verdict and judge-sample submissions from the out-of-process Judge; two more listings already in the registry as precedent.
- **105:** `messages.seq` and `inbox_submissions.applied_seq` as change sources for the feed; the change feed replaces consumer polling without changing `messages()`.
- **106:** project creation, the blocked-state-resolved-through-the-inbox step of the end-to-end proof, and `submit` + `kill -9` + `start` as its restart injection — all through public surfaces, with no script opening a store read-write.
- **Initiative 120:** `pending_intents` / `acknowledge_message`; escalation delivery as a side effect of `block(kind=HUMAN)`; `host.open_project` and a `project_ids` that grows at runtime, which the Runner must not cache.
- **Initiatives 140, 160, and the notification bridge:** `amoeba.inbox.submit`, `Store.open_read_only(...).messages(...)`, and `submission(id)`.

### Consumes from Other Slices

101 and 102 through their documented contracts, with these recorded changes to them (`docs/store-contract.md`, `docs/process-contract.md`, `CHANGELOG.md`):

- `block()` gains `payload=None`, and a `HUMAN` block writes an escalation row.
- `journal_escalate` shares the block writer and escalates on its already-blocked branch.
- Read-write store opening moves from `host.py` to `process/project_stores.py`; the writer guard's permitted module changes accordingly.
- `host.project_ids` is no longer fixed at startup.
- `amoeba start` changes from zero tenants to registering `InboxTenant` first, so a backlog accumulated while the process was down drains ahead of any later tenant's work — tenants tick in registration order.

## Success Criteria

### Functional Requirements

- [ ] With the process stopped, `submit()` succeeds and the file is in `inbox/new/`; after `amoeba start` the submission is `applied` and the file is gone.
- [ ] A `create_project` submission applied by a **running** process creates the store, and the next submission for that project — in the same tick or a later one — applies without a restart. `amoeba inspect projects` lists it.
- [ ] A `create_project` for an existing project is `applied` and changes nothing; a process killed between store creation and the record commit writes the record on restart.
- [ ] A project id containing a path separator, or equal to `.` or `..`, is refused by `submit()` and, if hand-written into `new/`, quarantined as `invalid_project_id` with no store file created anywhere.
- [ ] A `resolution` submission fills the targeted blocked state's slot and flips the node `runnable`, in one transaction.
- [ ] Applying the same submission twice (file restored to `new/` after apply) changes nothing and leaves exactly one record.
- [ ] A process killed between the apply commit and the file delete applies nothing twice on restart and removes the file.
- [ ] Resubmitting an existing id with different content is a no-op and logs a WARNING.
- [ ] A `resolution` naming an already-resolved blocked state, a blocked state of another project, or a nonexistent one is recorded `rejected` with a reason; a node re-blocked since is **not** resolved by the stale reply.
- [ ] An `intent` submission produces one unacknowledged `intent` message carrying the submission id; `acknowledge_message` removes it from `pending_intents`; a second acknowledge raises.
- [ ] `block(kind=HUMAN)` writes exactly one escalation row in the same transaction; `JUDGE` and `SQ_CHECKPOINT` blocks write none.
- [ ] `journal_escalate` on an unblocked node writes the block and one escalation row carrying `journal_entry_id`; on an already-blocked node — tested with a `HUMAN` and a `JUDGE` block — it writes no second block and one escalation row pointing at the existing open blocked state.
- [ ] `applied_seq` and `seq` increase in apply order regardless of the `submitted_at` values in the envelopes.
- [ ] `messages(channel=ESCALATION, after_seq=n)` returns only later rows, in `seq` order, identically on repeated calls, through a read-only handle.
- [ ] Unparseable JSON, an unknown envelope version, an unknown kind, an invalid payload, and an unknown project each end in `quarantine/` with the matching `QuarantineReason`; later valid submissions in the same tick still apply.
- [ ] `submit()` with an invalid payload raises and leaves nothing in `new/` or `tmp/`.
- [ ] A tick handles at most `inbox_batch_size` files and stops early when `stop_requested` is set.
- [ ] `amoeba submit` and the three inspection listings work with the process running and stopped.

### Technical Requirements

- [ ] Vocabularies are `StrEnum`s defined once; directory names and the filename scheme are defined once in `layout.py`; all SQL and column names live in `sql_inbox.py`; project-id validation has one definition.
- [ ] There is one internal block writer; `block()` and `journal_escalate` both use it, and `_block_for_entry` no longer exists as a separate write path.
- [ ] The writer guard's permitted set is exactly `{process/project_stores.py}`. `amoeba.inbox` and `cli/submit.py` open no store read-write. A new test asserts `amoeba.inbox`'s public exports contain no write path other than `submit`.
- [ ] All slice 102 host, lifecycle, recovery, and load tests pass unchanged after the `ProjectStores` extraction.
- [ ] Envelope fixtures include a file produced by the real `submit()` and hand-damaged variants of it (truncated, wrong version, extra fields).
- [ ] A store at schema version 3 with an open human block upgrades to 4 with nodes, blocked states, and journal intact, and gains the backfilled escalation row.
- [ ] `tests/load/` gains a concurrent-submitter test (see Implementation Notes) with asserted exactly-once.
- [ ] `ruff`, `pyright` strict, and the full suite are clean; source files stay near 300 lines, `host.py` included.
- [ ] `docs/inbox-contract.md` exists; `store-contract.md`, `process-contract.md`, and `CHANGELOG.md` are updated.

### Integration Requirements

- [ ] End to end through the real CLI as subprocesses, starting from an **empty** supervisor directory: `start` → `submit create-project` → seed a human-blocked node → read its escalation row read-only → `stop` → `submit resolution` → `start` → node is `runnable` → `kill -9` → `start` → state unchanged and no second apply.
- [ ] `docs/inbox-contract.md` is sufficient for an initiative 160 slice design to proceed without reading the implementation.

### Verification Walkthrough

**Draft — to be replaced with captured output when Phase 6 completes.** `amoeba submit`, the `inbox` / `submissions` / `messages` listings, and `scripts/demo_inbox.py` do not exist yet; this slice creates them. Nothing outside the process can create nodes until initiative 120, so the demo script seeds one node blocked on a human in the `demo` project and prints the blocked-state id. It performs a read-write `Store.open`, runs only while the process is stopped, and is added to `PERMITTED_SCRIPTS` in the writer guard, like `demo_journal.py`.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
```

**1. Create a project in a running process**

```bash
uv run amoeba start &
uv run amoeba inspect projects              # (none)
uv run amoeba submit create-project --project demo --by pm
uv run amoeba inspect projects              # demo
uv run amoeba inspect submissions --project demo   # applied_seq=1  create_project  applied
uv run amoeba stop
```

**2. Seed a blocked node; the escalation is already there for an outside reader**

```bash
uv run python scripts/demo_inbox.py        # prints: node=<NODE>  blocked_state=<BS>
uv run amoeba inspect messages --project demo --channel escalation
#   one row: node_id=<NODE>, blocked_state_id=<BS>
```

**3. Submit while the process is down**

```bash
uv run amoeba status                        # stopped
uv run amoeba submit resolution --project demo --blocked-state <BS> \
    --by pm --detail "proceed with option B"
#   prints the submission id <SUB>
uv run amoeba inspect inbox                 # one pending file, id <SUB>
uv run amoeba inspect blocked --project demo   # still blocked: nothing applied it
```

**4. Start applies it**

```bash
uv run amoeba start &
uv run amoeba inspect inbox                 # (none)
uv run amoeba inspect submissions --project demo   # <SUB>  resolution  applied
uv run amoeba inspect blocked --project demo       # (none)
uv run amoeba inspect nodes --project demo         # <NODE> is runnable
```

**5. Replay and stale replies do not double-write**

```bash
uv run amoeba submit resolution --project demo --blocked-state <BS> \
    --by pm --detail "proceed with option B" --id <SUB>      # same id: retry
uv run amoeba submit resolution --project demo --blocked-state <BS> \
    --by someone-else --detail "late reply"                  # new id, stale target
uv run amoeba inspect submissions --project demo
#   <SUB>   applied            (exactly one row for <SUB>)
#   <SUB2>  rejected  reason: blocked state already resolved
```

**6. Intent, and survival of a kill**

```bash
uv run amoeba submit intent --project demo --by translator \
    --payload-json '{"request": "pause after slice 104"}'
uv run amoeba inspect messages --project demo --channel intent   # one unacknowledged row
kill -9 "$(python3 -c "import json;print(json.load(open('$AMOEBA_STORE_DIR/amoeba.pid'))['pid'])")"
uv run amoeba start &
uv run amoeba inspect submissions --project demo --json   # identical to before the kill
```

**7. Bad submissions are quarantined, not lost and not blocking**

```bash
echo 'not json' > "$AMOEBA_STORE_DIR/inbox/new/00000000000000000000-bad.json"
uv run amoeba submit intent --project nosuch --by pm --payload-json '{}'
uv run amoeba inspect inbox
#   quarantined: …-bad.json   unparseable_envelope
#   quarantined: …            no_store_for_project
```

**8. Quality gates**

```bash
uv run pytest && uv run pytest tests/load
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

## Risk Assessment

### Technical Risks

- **Durability of rename is filesystem behavior.** A rename without an fsync of the containing directory can be lost on power failure, and unit tests cannot simulate power loss.
- **A poison submission stalling the queue.** If any class of bad input raised instead of quarantining, every later submission would wait behind it forever.
- **The `ProjectStores` extraction touches slice 102's highest-risk module** and changes what the writer guard permits.

### Mitigation Strategies

- `submit()` fsyncs the file and then the directory, and a test asserts both calls occur in order (the one place a call-order assertion is the honest test). The contract states the guarantee as "fsync-durable on a POSIX filesystem" rather than overclaiming.
- The quarantine ladder is enumerated as a closed vocabulary and each member has a success criterion, including "later valid submissions in the same tick still apply". The only thing allowed to stop the queue is a `StoreError` or an unexpected exception — a sick store, where stopping is correct.
- The extraction is its own step, done first and as a pure refactor: no behavior change, slice 102's suite and load tier passing unchanged, committed separately before `open_project` is added on top.

## Implementation Notes

### Development Approach

Suggested order — each step leaves the suite green:

1. **Extract `ProjectStores`** from `host.py` as a pure refactor; move the writer guard's permitted module. No new behavior.
2. **Models and migration `004`** — vocabularies, records, `sql_inbox.py`, the backfill, migration test from a version-3 store.
3. **One block writer, `MessagesMixin`, and D3** — consolidate `_block_for_entry` into the shared writer, add the escalation row, then the already-blocked branch.
4. **`InboxMixin.apply_submission`** — replay, all three kinds, every rejection branch. Pure library work; no files yet.
5. **`amoeba.inbox`** — envelope, layout, `submit()`, `pending()`, `quarantined()`.
6. **`open_project`**, then **`InboxTenant`** against the real host via `tests/host_harness.py`; registration in `cli/lifecycle.py`; `inbox_batch_size` setting and flag.
7. **CLI** — `amoeba submit`, then the three listings.
8. **Guard and public-API tests**; `scripts/demo_inbox.py` and its allow-listing.
9. **Load tier.** Several submitter processes each submit a few hundred `intent` submissions to projects created through the inbox during the run, a fraction deliberately resubmitted under the same id, while the resident process is `SIGKILL`ed and restarted at random points. Assert: every distinct id has exactly one record and exactly one message; `applied_seq` has no duplicates; `inbox/new/` drains to empty; no `tmp/` file is ever applied. Bounds on drain time follow slice 102's rule — measure first, assert at roughly twice the observation, record the number.
10. **Docs** — `inbox-contract.md`, contract updates, `CHANGELOG.md`, and the captured walkthrough.

### Special Considerations

**Project Manager decisions.** Ratified 20260921: D1 (file-drop hand-off, SQLite for everything durable), D2 (submitter-generated id, first-wins on reuse), D3 (escalation written by the block writer, including both recovery consequences), D4 (receiver-assigned order), and folding runtime project creation into this slice. Nothing awaits ratification.

**A submission that races ahead of its project's creation is quarantined, not held.** Holding would mean an unbounded set of files the loop re-examines every tick waiting for a project that may never come. Submitters that create a project wait for `submission(id)` to report `applied` before submitting into it; the contract says so.

**Stray `tmp/` files** from a submitter that crashed mid-write are harmless and are not cleaned up in this slice; `amoeba inspect inbox` does not list them. Revisit only if they accumulate in practice.

**Security.** Submission payloads and message payloads are stored verbatim and shown by `amoeba inspect`; the contract repeats 102's rule that callers must not place secrets in them. The inbox directory is created with the user's default permissions: any process running as that user can submit — and can now create a project — which is the intended trust boundary and the same one the stores already have. Project ids are validated before they reach a path.

**Relative effort: 4.** The slice plan said 3; runtime project creation, the `ProjectStores` extraction, and the block-writer consolidation account for the difference. The slice plan entry is updated to match.
