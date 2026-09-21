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
2. **The apply loop** — the first real `Tenant`. It consumes pending submissions in order and applies each to the right project store. The effect and the record that it was applied commit in **one transaction**, so replay is a no-op.
3. **The channels** — intent (Translator → Runner), escalation (Runner → Translator and bridge), and inbound human reply (bridge → a blocked node's resolution slot), with documented delivery and replay semantics.

Completing it closes the first vertical path through the substrate: an outside writer submits, the process applies, state persists, a restart preserves it.

## Value

Architectural enablement. Without this slice, initiatives 140 and 160 cannot exist: their parts are out-of-process by architecture and the store refuses them. After it:

- The notification bridge and Translator (160) have a one-call `submit()` API and never touch SQLite for writing.
- A human reply becomes a filled resolution slot and a runnable node with no part calling another part.
- The Runner (120) has a durable intent queue to consume and gets escalation delivery for free whenever it blocks a node on a human.
- The ratified claim "inbox submissions land durably while the process is down and are applied on restart" is demonstrated, not asserted.

## Technical Scope

**Included**

- `amoeba.inbox` — the out-of-process-facing package: envelope models, directory layout, `submit()`, and read-only listing of pending and quarantined submissions. It touches the filesystem only; it never opens a store read-write.
- `InboxTenant` — the apply loop, registered by `amoeba start`.
- Store additions: schema migration `004`, `apply_submission`, the submission record, the `messages` table with the `intent` and `escalation` channels, and message read/acknowledge methods.
- Two submission kinds: `resolution` and `intent`, behind a closed vocabulary that later slices extend.
- An escalation message written automatically, in the same transaction, whenever a node is blocked on `HUMAN` (D3).
- `amoeba submit` (an operator- and bridge-usable CLI writer) and inspection listings for the inbox, submissions, and messages.
- `docs/inbox-contract.md` — delivery and replay semantics: what is guaranteed and what is not.
- A load-tier test: concurrent submitters against a kill-looped process.

**Excluded**

- The Translator, the notification bridge, and any message *content* semantics — initiative 160. Payloads are stored opaquely.
- The Runner's consumption of intent and any routing — initiative 120.
- Verdict, finding, and judge-sample submission kinds — slice 104 adds them through the seam this slice defines.
- Push notification that a message or state change exists — slice 105's change feed. Until then consumers poll the read API.
- Creating a project store. A submission for a project with no store is quarantined (see Special Considerations).
- Retention of applied submission records and messages — already Future Work in the slice plan.
- Authentication of submitters. The inbox is protected by filesystem permissions on the supervisor directory, as the stores already are.

## Dependencies

### Prerequisites

- **Slice 101** — `Store`, `block()` / `resolve()`, the migration mechanism, typed failure modes, `amoeba.store.paths`.
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
  validate envelope + payload for the kind      # fail before writing anything
  write inbox/tmp/<name>  → fsync file
  rename → inbox/new/<name>  → fsync directory  # durable once this returns
  return submission_id
```

`<name>` is `{submitted_at_ns:020d}-{submission_id}.json`, so lexical order is submission-time order.

Apply (one `InboxTenant.tick`):

```
for file in sorted(inbox/new/)[: settings.inbox_batch_size]:
    if host.stop_requested: break
    envelope = parse(file)          # unparseable → quarantine
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
| After commit, before delete | file in `new/`, record exists | id hit → no-op → file deleted |

Effects by kind:

| Kind | Payload | Precondition | Effect |
| --- | --- | --- | --- |
| `resolution` | `blocked_state_id`, `resolved_by`, `detail` | that blocked state exists in this project and is the node's **open** one | `resolve()` — slot filled, node flips `runnable` |
| `intent` | opaque mapping, optional `node_id` | `node_id`, if given, exists in this project | a row on the `intent` channel |

A `resolution` targets a **blocked-state id, not a node id**. A node can be blocked again after resolution; a late human reply to the first block must not resolve the second. A stale target is recorded `rejected`, never redirected.

### State Management

- **Durable, supervisor directory:** the inbox files. A file in `new/` is a submission not yet known to be applied — nothing more.
- **Durable, each project store:** `inbox_submissions` (the idempotency and audit record) and `messages`.
- **In memory:** nothing authoritative. The tenant holds no cursor; the directory listing is the queue.

## Technical Decisions

Three choices a reasonable Project Manager could make differently are marked **(PM)**.

### Technology Choices

**D1 — The inbox is an atomic file drop, not a SQLite file. (PM)** The architecture leaves the durability mechanism to this slice, constrained by "accept appends from outside the process while the process is down". Write-to-`tmp`, fsync, rename is atomic on POSIX, needs no lock, has no failure mode in which a submitter's crash corrupts anyone else's submission, and keeps the statement *no process other than the resident one ever opens an Amoeba SQLite file read-write* literally true — so the writer guard stays a simple rule with no exception carved out for an inbox database. It is the same mechanism Squadron uses for its run files, which slice 102 already relies on.
*Rejected:* a shared `inbox.sqlite3` that submitters open read-write. It gives a global sequence number, but submitters then contend on a write lock, a crashed submitter can leave a hot WAL for the process to recover, and the apply step still spans two databases — so it buys ordering and nothing toward idempotency, which the store-side record provides either way. *Also rejected:* submitters writing an inbox table inside the project store; that puts outside writers in contention with the Runner on the very lock sole-writer exists to keep uncontended.

**D2 — Exactly-once effect from a submitter-generated id. (PM)** Delivery of a file to the apply loop is at-least-once; the effect is exactly-once because the submission id is the primary key of `inbox_submissions` and the record commits with the effect. The submitter generates the id (a default is generated if none is passed), which makes `submit()` safely retryable: a bridge unsure whether its call succeeded resubmits with the same id. A second submission reusing an id with *different* content is a no-op — first one wins — logged at WARNING. It is not an error, because the second file may legitimately be a retry whose timestamp differs.

**D3 — Escalation messages are written by `block()`, not by callers. (PM)** Whenever a node is blocked on `BlockedKind.HUMAN`, the store writes one row on the `escalation` channel in the same transaction, carrying `node_id`, `blocked_state_id`, and an optional opaque `payload` (a new keyword-only argument to `block()`, default `None`, stored as NULL). Consequences: a human-blocked node without an escalation cannot exist, including the blocks slice 102's `journal_escalate` writes during recovery; and no caller has to remember a second call. This is deterministic plumbing, not a decision — the substrate does not choose *whether* to escalate, it records that a human block happened on the channel defined for exactly that. `blocked_on_judge` and `blocked_on_sq_checkpoint` write no message; no channel is defined for them and the Runner observes both directly.
*Alternative:* a public `post_message()` the Runner calls after `block()`. Rejected because it reintroduces a two-call window and a way to forget.

**The inbound-reply channel has no message table.** A reply terminates in a resolution slot. Its durable record is the `inbox_submissions` row; materializing it again as a message would duplicate the fact.

### Patterns and Conventions

**Closed vocabularies, `StrEnum`, defined once in `inbox_models.py`:** `SubmissionKind` (`resolution`, `intent`), `SubmissionOutcome` (`applied`, `rejected`), `Channel` (`intent`, `escalation`), and `QuarantineReason` (`unparseable_envelope`, `unknown_envelope_version`, `unknown_kind`, `invalid_payload`, `no_store_for_project`). `submitted_by` and `resolved_by` are free-form data and are never branched on.

**Adding a submission kind** (slice 104 will) is three things, all of them: an enum member, a payload model, and an effect inside `InboxMixin`. The kind-to-payload-model and kind-to-effect tables are each defined once; a kind missing from either fails a test, not a user.

**Rejection is a recorded outcome, not an exception.** Preconditions are checked as explicit branches inside the apply transaction, in the manner of `journal_escalate`'s already-blocked branch. `InvalidTransitionError` is never caught to implement rejection — that would also swallow genuine bugs. A rejected submission is terminal and never retried.

**Quarantine versus rejection.** A submission that can be attributed to an open project store always ends as a store record (`applied` or `rejected`). Only one that *cannot* — unparseable, unknown envelope version or kind, invalid payload, or no store for its project — is quarantined as a file, because there is no store row to write. Quarantine moves the file and writes the sidecar; it never deletes content. An operator requeues by moving the file back to `new/`.

**Envelope versioning.** The envelope carries `envelope_version`. An unknown version is quarantined, never best-effort parsed. Unknown extra fields are ignored.

**Tenant obligation.** `tick()` handles at most `inbox_batch_size` files and checks `stop_requested` between files. Each file is one short transaction, so an abandoned tick is covered by the crash table above. `inbox_batch_size` lives in `ProcessSettings` with a `start` flag, like every other tunable.

**Error handling.** `submit()` raises typed errors (`InboxSubmitError` family) on validation or I/O failure and leaves nothing in `new/`. In the tenant, an unexpected exception from `apply_submission` is logged with `logger.exception` and re-raised — the file stays in `new/`, and the process stops rather than skipping a submission and applying later ones out of order. A `StoreError` is not converted to quarantine: quarantine means "this submission is bad", never "the store is unwell".

## Implementation Details

### API Contracts

**Out-of-process API (`amoeba.inbox`, pinned by a public-API test):**

| Call | Effect |
| --- | --- |
| `submit(*, project_id, kind, payload, submitted_by, submission_id=None, store_dir=None) -> str` | Validates, writes durably, returns the submission id. Works whether or not the process is running. |
| `pending(store_dir=None) -> list[PendingSubmission]` | Files in `new/`, in apply order. |
| `quarantined(store_dir=None) -> list[QuarantinedSubmission]` | Quarantined files with their recorded reason. |

Envelope fields: `envelope_version`, `id`, `project_id`, `kind`, `submitted_by`, `submitted_at`, `payload`.

A submitter learns its outcome by reading, not by reply: `Store.open_read_only(project_id=…).submission(submission_id)` returns `None` until applied, then the record.

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `apply_submission(*, submission_id, kind, submitted_by, submitted_at, payload) -> SubmissionRecord` | One transaction: replay check, precondition, effect, record. Returns the existing record unchanged on replay. |
| `submission(submission_id)` | One record, or `None`. |
| `submissions(project_id, *, outcome=None)` | Oldest first. What inspection consumes. |
| `messages(project_id, *, channel, after_seq=0)` | Rows with `seq > after_seq`, ascending. The replay primitive. |
| `pending_intents(project_id)` | Unacknowledged `intent` rows, ascending. What the Runner consumes. |
| `acknowledge_message(message_id, *, acknowledged_by)` | Marks an `intent` row consumed. Raises `InvalidTransitionError` if already acknowledged or not an intent. |
| `block(node_id, *, kind, context, payload=None)` | Unchanged except D3: a `HUMAN` block also writes the escalation row. |

`SubmissionRecord` and `Message` are frozen dataclasses, consistent with the existing transfer types.

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba submit resolution --project ID --blocked-state ID --by NAME --detail TEXT [--id ID]` | Calls `submit()`; prints the submission id. |
| `amoeba submit intent --project ID --payload-json JSON [--node ID] --by NAME [--id ID]` | Same. |
| `amoeba inspect inbox` | Supervisor-level (like `projects`): pending and quarantined files. |
| `amoeba inspect submissions\|messages --project ID` | Registered into 102's listing registry. `messages` accepts `--channel`. All accept `--json`. |

### Database / Storage Schema

Migration `004_inbox_and_messages.sql`, `EXPECTED_SCHEMA_VERSION` → 4.

`inbox_submissions`: `id` (primary key — the submitter's id), `project_id`, `kind`, `submitted_by`, `submitted_at`, `payload` (JSON text), `outcome`, `reason` (NULL when applied), `applied_at`. Index on `(project_id, applied_at)`.

`messages`: `seq` (INTEGER PRIMARY KEY AUTOINCREMENT — the replay cursor), `id`, `project_id`, `channel`, `node_id` (nullable FK), `blocked_state_id` (nullable FK; set for escalations), `submission_id` (nullable FK; set for intents, as provenance), `payload` (JSON text, nullable), `created_at`, `acknowledged_at`, `acknowledged_by`. Index on `(project_id, channel, seq)`; partial index on unacknowledged intents.

Existing human-blocked states written before this migration have no escalation row. The migration backfills one row per **open** `HUMAN` blocked state so the invariant in D3 holds from version 4 onward; resolved historical blocks are not backfilled.

### Delivery and Replay Semantics

This is the content `docs/inbox-contract.md` must state.

**Guaranteed**

- **Durability on return.** When `submit()` returns, the submission survives a crash of the submitter, the resident process, or the machine's power — process up or down.
- **Exactly-once effect per submission id.** Redelivery, restart, and submitter retry with the same id cannot double-apply.
- **Atomic effect and record.** No state exists in which a slot is filled but the submission is unrecorded, or the reverse.
- **Every submission reaches a terminal, inspectable state:** `applied`, `rejected` (with reason), or quarantined (with reason). None is dropped silently.
- **Per-submitter order**, provided the submitter's clock does not run backwards between its own calls.
- **Messages are replayable.** `messages(after_seq=0)` returns a channel's full history in a stable order, any number of times. Escalation consumers hold their own cursor; an escalation is *outstanding* exactly while its blocked state is open, which is a store query, not consumer bookkeeping.
- **Every human block has exactly one escalation row**, committed with the block.

**Not guaranteed**

- **Ordering across submitters.** Apply order is filename order, which is each submitter's own clock.
- **Latency.** Apply happens on the next tick; bounded below by `idle_interval_seconds` when idle, unbounded while the process is down.
- **Notification of outcome.** Submitters poll `submission(id)`. Push is slice 105.
- **That a valid submission is applied.** A `resolution` whose blocked state was resolved by someone else first is `rejected` as stale. First writer wins; the loser is told why.
- **Retention limits.** Records and messages are never deleted in this slice.

## Integration Points

### Provides to Other Slices

- **104:** the submission-kind seam (enum member + payload model + effect) for verdict and judge-sample submissions from the out-of-process Judge; two more listings already in the registry as precedent.
- **105:** `messages.seq` and `inbox_submissions` as change sources for the feed; the change feed replaces consumer polling without changing `messages()`.
- **106:** the blocked-state-resolved-through-the-inbox step of the end-to-end proof, and `submit` + `kill -9` + `start` as its restart injection.
- **Initiative 120:** `pending_intents` / `acknowledge_message`; escalation delivery as a side effect of `block(kind=HUMAN)`.
- **Initiatives 140, 160, and the notification bridge:** `amoeba.inbox.submit`, `Store.open_read_only(...).messages(...)`, and `submission(id)`.

### Consumes from Other Slices

101 and 102 through their documented contracts only. One additive change to a 101 method (`block()` gains `payload=None`) and one behavioral addition (the escalation row); both are recorded in `docs/store-contract.md` and `CHANGELOG.md`. `amoeba start` changes from zero tenants to registering `InboxTenant` first, so that a backlog accumulated while the process was down is applied before any later tenant (the Runner) ticks for the first time in practice — tenants tick in registration order.

## Success Criteria

### Functional Requirements

- [ ] With the process stopped, `submit()` succeeds and the file is in `inbox/new/`; after `amoeba start` the submission is `applied` and the file is gone.
- [ ] A `resolution` submission fills the targeted blocked state's slot and flips the node `runnable`, in one transaction.
- [ ] Applying the same submission twice (file restored to `new/` after apply) changes nothing and leaves exactly one record.
- [ ] A process killed between the apply commit and the file delete applies nothing twice on restart and removes the file.
- [ ] Resubmitting an existing id with different content is a no-op and logs a WARNING.
- [ ] A `resolution` naming an already-resolved blocked state, a blocked state of another project, or a nonexistent one is recorded `rejected` with a reason; a node re-blocked since is **not** resolved by the stale reply.
- [ ] An `intent` submission produces one unacknowledged `intent` message carrying the submission id; `acknowledge_message` removes it from `pending_intents`; a second acknowledge raises.
- [ ] `block(kind=HUMAN)` writes exactly one escalation row in the same transaction, including when called via `journal_escalate`; `JUDGE` and `SQ_CHECKPOINT` blocks write none.
- [ ] `messages(channel=ESCALATION, after_seq=n)` returns only later rows, in `seq` order, identically on repeated calls, through a read-only handle.
- [ ] Unparseable JSON, an unknown envelope version, an unknown kind, an invalid payload, and an unknown project each end in `quarantine/` with the matching `QuarantineReason`; later valid submissions in the same tick still apply.
- [ ] `submit()` with an invalid payload raises and leaves nothing in `new/` or `tmp/`.
- [ ] A tick handles at most `inbox_batch_size` files and stops early when `stop_requested` is set.
- [ ] `amoeba submit` and the three inspection listings work with the process running and stopped.

### Technical Requirements

- [ ] Vocabularies are `StrEnum`s defined once; directory names and the filename scheme are defined once in `layout.py`; all SQL and column names live in `sql_inbox.py`.
- [ ] The writer guard still passes with **no new permitted module** under `src/amoeba/`: `amoeba.inbox` and `cli/submit.py` open no store read-write. A new test asserts `amoeba.inbox`'s public exports contain no write path other than `submit`.
- [ ] Envelope fixtures include a file produced by the real `submit()` and hand-damaged variants of it (truncated, wrong version, extra fields).
- [ ] A store at schema version 3 with an open human block upgrades to 4 with nodes, blocked states, and journal intact, and gains the backfilled escalation row.
- [ ] `tests/load/` gains a concurrent-submitter test (see Implementation Notes) with asserted exactly-once.
- [ ] `ruff`, `pyright` strict, and the full suite are clean; source files stay near 300 lines.
- [ ] `docs/inbox-contract.md` exists; `store-contract.md`, `process-contract.md`, and `CHANGELOG.md` are updated.

### Integration Requirements

- [ ] End to end through the real CLI as subprocesses: seed a human-blocked node → read its escalation row read-only → `amoeba submit resolution` while stopped → `start` → node is `runnable` → `kill -9` → `start` → state unchanged and no second apply.
- [ ] `docs/inbox-contract.md` is sufficient for an initiative 160 slice design to proceed without reading the implementation.

### Verification Walkthrough

**Draft — to be replaced with captured output when Phase 6 completes.** `amoeba submit`, the `inbox` / `submissions` / `messages` listings, and `scripts/demo_inbox.py` do not exist yet; this slice creates them. The demo script seeds a project `demo` with one node blocked on a human and prints the blocked-state id; it performs a read-write `Store.open` and so is added to `PERMITTED_SCRIPTS` in the writer guard, like `demo_journal.py`.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
uv run python scripts/demo_inbox.py        # prints: node=<NODE>  blocked_state=<BS>
```

**1. The escalation is already there, readable by an outside part**

```bash
uv run amoeba inspect messages --project demo --channel escalation
#   one row: seq=1, node_id=<NODE>, blocked_state_id=<BS>
```

**2. Submit while the process is down**

```bash
uv run amoeba status                        # stopped
uv run amoeba submit resolution --project demo --blocked-state <BS> \
    --by pm --detail "proceed with option B"
#   prints the submission id <SUB>
uv run amoeba inspect inbox                 # one pending file, id <SUB>
uv run amoeba inspect blocked --project demo   # still blocked: nothing applied it
```

**3. Start applies it**

```bash
uv run amoeba start &
uv run amoeba inspect inbox                 # (none)
uv run amoeba inspect submissions --project demo   # <SUB>  resolution  applied
uv run amoeba inspect blocked --project demo       # (none)
uv run amoeba inspect nodes --project demo         # <NODE> is runnable
```

**4. Replay and stale replies do not double-write**

```bash
uv run amoeba submit resolution --project demo --blocked-state <BS> \
    --by pm --detail "proceed with option B" --id <SUB>      # same id: retry
uv run amoeba submit resolution --project demo --blocked-state <BS> \
    --by someone-else --detail "late reply"                  # new id, stale target
uv run amoeba inspect submissions --project demo
#   <SUB>   applied            (exactly one row for <SUB>)
#   <SUB2>  rejected  reason: blocked state already resolved
```

**5. Intent, and survival of a kill**

```bash
uv run amoeba submit intent --project demo --by translator \
    --payload-json '{"request": "pause after slice 104"}'
uv run amoeba inspect messages --project demo --channel intent   # one unacknowledged row
kill -9 "$(python3 -c "import json;print(json.load(open('$AMOEBA_STORE_DIR/amoeba.pid'))['pid'])")"
uv run amoeba start &
uv run amoeba inspect submissions --project demo --json   # identical to before the kill
```

**6. A bad submission is quarantined, not lost and not blocking**

```bash
echo 'not json' > "$AMOEBA_STORE_DIR/inbox/new/00000000000000000000-bad.json"
uv run amoeba inspect inbox      # quarantined: …-bad.json  unparseable_envelope
```

**7. Quality gates**

```bash
uv run pytest && uv run pytest tests/load
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

## Risk Assessment

### Technical Risks

- **Durability of rename is filesystem behavior.** A rename without an fsync of the containing directory can be lost on power failure, and unit tests cannot simulate power loss.
- **A poison submission stalling the queue.** If any class of bad input raised instead of quarantining, every later submission would wait behind it forever.

### Mitigation Strategies

- `submit()` fsyncs the file and then the directory, and a test asserts both calls occur in order (the one place a call-order assertion is the honest test). The contract states the guarantee as "fsync-durable on a POSIX filesystem" rather than overclaiming.
- The quarantine ladder is enumerated as a closed vocabulary and each member has a success criterion, including "later valid submissions in the same tick still apply". The only thing allowed to stop the queue is a `StoreError` or an unexpected exception — a sick store, where stopping is correct.

## Implementation Notes

### Development Approach

Suggested order — each step leaves the suite green:

1. **Models and migration `004`** — vocabularies, records, `sql_inbox.py`, the backfill, migration test from a version-3 store.
2. **`MessagesMixin`** and D3's change to `block()`, with `journal_escalate` covered.
3. **`InboxMixin.apply_submission`** — replay, both kinds, every rejection branch. Pure library work; no files yet.
4. **`amoeba.inbox`** — envelope, layout, `submit()`, `pending()`, `quarantined()`.
5. **`InboxTenant`**, against the real host via `tests/host_harness.py`; registration in `cli/lifecycle.py`; `inbox_batch_size` setting and flag.
6. **CLI** — `amoeba submit`, then the three listings.
7. **Guard and public-API tests**; `scripts/demo_inbox.py` and its allow-listing.
8. **Load tier.** Several submitter processes each submit a few hundred `intent` submissions, a fraction deliberately resubmitted under the same id, while the resident process is `SIGKILL`ed and restarted at random points. Assert: every distinct id has exactly one record and exactly one message; `inbox/new/` drains to empty; no `tmp/` file is ever applied. Bounds on drain time follow slice 102's rule — measure first, assert at roughly twice the observation, record the number.
9. **Docs** — `inbox-contract.md`, contract updates, `CHANGELOG.md`, and the captured walkthrough.

### Special Considerations

**Project Manager decisions.** D1 (file-drop inbox), D2 (submitter-generated id, first-wins on reuse), and D3 (escalation written by `block()`) are recommendations; the design is complete under them and each is cheap to reverse now and expensive after initiative 160 codes against it.

**No store for the project — a gap this slice surfaces but does not own.** The host opens only the stores it discovers at startup, and nothing in slices 101–102 creates a project store inside the resident process. A submission for an unknown project is therefore quarantined with `no_store_for_project`, and requeued by hand once the store exists. How a project comes into existence at runtime belongs to initiative 120 (or to slice 106's hardening, if the PM prefers); it should not be solved implicitly by letting an outside submission create a store.

**Stray `tmp/` files** from a submitter that crashed mid-write are harmless and are not cleaned up in this slice; `amoeba inspect inbox` does not list them. Revisit only if they accumulate in practice.

**Security.** Submission payloads and message payloads are stored verbatim and shown by `amoeba inspect`; the contract repeats 102's rule that callers must not place secrets in them. The inbox directory is created with the user's default permissions: any process running as that user can submit, which is the intended trust boundary and the same one the stores already have.

**Relative effort: 3**, matching the slice plan.
