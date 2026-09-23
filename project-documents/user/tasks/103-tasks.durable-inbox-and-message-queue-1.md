---
docType: tasks
slice: durable-inbox-and-message-queue
project: amoeba
lld: user/slices/103-slice.durable-inbox-and-message-queue.md
dependencies: [101, 102]
projectState: Slices 101 and 102 are merged. The store is at schema version 3 with nodes, blocked states, the command journal, and recovery. The resident process starts, recovers, idles, and stops — with zero tenants registered and no way for anything outside the process to contribute state. This slice adds the inbox, the first real tenant, the messages table, and runtime project creation.
dateCreated: 20260922
dateUpdated: 20260922
status: in_progress
---

## Context Summary

- Working on the **durable-inbox-and-message-queue** slice (103), the third slice of initiative 100.
- **Current state:** slice 102 is merged (`08d2f88`, review fixes at `b8f2b51`). `ResidentProcess`, the `Tenant` protocol, `ProcessSettings`, `Store.open_read_only`, the inspection listing registry, and the AST writer guard all exist. `EXPECTED_SCHEMA_VERSION = 3`. The process registers no tenants, so nothing is applied to any store while it runs. Read-write store opening lives in `process/host.py`, which is 378 lines and over the ~300 guideline.
- **Dependencies:** slices 101 and 102, through their documented contracts. `pydantic` is already a runtime dependency and is used here for the externally-authored submission envelope. **No new third-party dependency.**
- **What this slice delivers:** the `amoeba.inbox` file-drop package, `InboxTenant` (the first real tenant), schema migration `004` with `inbox_submissions` and `messages`, three submission kinds, automatic escalation messages from the store's one block writer, runtime project creation via `host.open_project`, the `amoeba submit` CLI and three inspection listings, `docs/inbox-contract.md`, and a concurrent-submitter load test.
- **Next planned slice:** 104, which adds verdict and judge-sample submission kinds through the seam this slice defines.

**Key design commitments (ratified by the PM on 20260921 — do not revisit them here):** D1 the hand-off is an atomic file drop while SQLite holds everything durable; D2 the submitter generates the submission id and reuse of an id is first-wins; D3 escalation rows are written by the store's one internal block writer, never by callers; D4 authoritative order is receiver-assigned at apply. Runtime project creation is in scope. The design review's F001 was resolved on 20260922 with a bounded attempt counter and an `inbox/failed/` park directory.

**Reading note for the executing developer:** this file does not restate the LLD. Where a task says "per the LLD," open `user/slices/103-slice.durable-inbox-and-message-queue.md` at the named section and follow it. Exact DDL, column names, signatures, and error messages are settled during implementation against that design.

**This file covers Sections 1–5** (the `ProjectStores` extraction, models and migration `004`, the block writer and D3, `apply_submission`, and the `amoeba.inbox` package). Sections 6–10 (runtime project creation and `InboxTenant`, the CLI, guard and public-API tests, the load tier, and documentation) are in `103-tasks.durable-inbox-and-message-queue-2.md`.

---

## Section 1: Extract ProjectStores (Pure Refactor)

Per the LLD's Development Approach, this section is **first and is a pure refactor**. No new behavior, no new tests of new behavior, and slice 102's entire suite passing unchanged. It is committed separately before `open_project` is added on top in Section 6.

### Task 1.1: Extract read-write store opening from host.py into ProjectStores
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Move `_open_stores`, `store_for`, `project_ids`, and `_close_stores` out of `process/host.py` into a new `process/project_stores.py`, with `host.py` delegating. Behavior must not change.

**Steps**:
- [x] Create `src/amoeba/process/project_stores.py` holding a `ProjectStores` class with the four members named above, moved verbatim in behavior
- [x] Change `host.py` to construct a `ProjectStores` and delegate `store_for` and `project_ids` to it; do not leave a second copy of the opening logic behind
- [x] Do **not** add `open_project` in this task — it belongs to Section 6, after this refactor is verified and committed
- [x] Keep both files within the ~300-line guideline; confirm `host.py` is materially smaller than its starting 378 lines

**Success Criteria**:
- [x] `process/project_stores.py` is the only module that opens a store read-write; `grep` for the read-write open in `host.py` finds nothing
- [x] `host.py` line count is reduced and both files are near or under 300 lines
- [x] No public behavior change: no signature visible to `ResidentProcess` callers is altered
- [x] `uv run pyright` clean in strict mode

- [x] Commit after this task, e.g. `refactor(process): add ProjectStores and delegate from host`

**Files to Create**: `src/amoeba/process/project_stores.py`
**Files to Modify**: `src/amoeba/process/host.py`

---

### Task 1.2: Move the writer guard's permitted module and verify the refactor
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 1
**Objective**: Point the sole-writer guard at the new module and prove the extraction changed nothing.

**Steps**:
- [x] Change `PERMITTED_MODULES` in `tests/test_writer_guard.py` from `process/host.py` to `process/project_stores.py`
- [x] Update the **five** other places in that file that name `process/host.py` literally, all of which fail or go stale if only the constant changes: the module docstring, the docstring of `test_only_the_host_opens_a_store_read_write`, that test's failure message ("Only process/host.py may do that…"), the `frozenset({"process/host.py"})` assertion in `test_the_permitted_set_is_exactly_the_host`, and the docstring around it. Rename both test functions too — their names say `host`
- [x] Finish by grepping the file for `host` and confirming nothing stale remains; the count above is a guide, the grep is the check
- [x] Confirm the deliberate-widening test still pins a set of **size one** — the guard must not be loosened to allow both modules
- [x] Run slice 102's full suite and the load tier; both must pass with no test modified other than the writer guard's host-naming above
- [x] Investigate any **other** failure as a defect in the extraction, not as a test needing an update

**Success Criteria**:
- [x] The writer guard's permitted set is exactly `{process/project_stores.py}` and no `process/host.py` literal remains in `tests/test_writer_guard.py`
- [x] `uv run pytest` and `uv run pytest tests/load` pass with no slice 102 test modified outside the writer guard
- [x] `uv run ruff check .` and `uv run pyright` clean
- [x] Commit after this task, e.g. `refactor(process): extract ProjectStores from host`

**Files to Modify**: `tests/test_writer_guard.py`

---

## Section 2: Models and Migration 004

### Task 2.1: Define the inbox and message vocabularies and records
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: Create `src/amoeba/store/inbox_models.py` holding every inbox and message vocabulary and both record dataclasses, so no related string literal appears anywhere else.

**Steps**:
- [x] Define `SubmissionKind`, `SubmissionOutcome`, `Channel`, and `QuarantineReason` as `StrEnum`s with exactly the members the LLD's "Closed vocabularies" section lists
- [x] Define the frozen `SubmissionRecord` and `Message` dataclasses with the fields the LLD's API Contracts and schema sections name, following the slice 101 convention in `models.py`
- [x] ~~Define the kind-to-payload-model mapping here~~ — **moved to Task 5.1** (PM decision 20260923). The payload models are pydantic and live in `amoeba.inbox.envelope`; defining the mapping in the store would make `amoeba.store` import `amoeba.inbox`, reversing the LLD's dependency direction
- [x] Treat `submitted_by` and `resolved_by` as free-form data — no enum, and nothing branches on them

**Success Criteria**:
- [x] Every inbox and message vocabulary value is defined exactly once; `grep` for any kind, outcome, channel, or quarantine-reason literal finds it only in this module
- [x] Both records are frozen dataclasses consistent with the existing transfer types
- [x] `uv run pyright` clean in strict mode
- [x] No import of `sqlite3` and no SQL in this module

- [x] Commit after this task, e.g. `feat(store): add inbox and message vocabularies`

**Files to Create**: `src/amoeba/store/inbox_models.py`

---

### Task 2.2: Test the vocabularies, records, and kind mapping
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 1
**Objective**: Pin the vocabularies before any SQL or parsing depends on them.

**Steps**:
- [x] Assert each enum's exact member set — a test that fails if a member is added or renamed without deliberate intent
- [x] Assert both record dataclasses are frozen
- [x] ~~Assert every `SubmissionKind` member has a payload model~~ — **moved to Task 5.1** with the mapping it covers

**Success Criteria**:
- [x] Adding or renaming a vocabulary member fails this suite
- [x] `uv run pytest` passes

- [x] Commit after this task, e.g. `test: pin inbox vocabularies and kind mapping`

**Files to Create**: `tests/store/test_inbox_models.py`

---

### Task 2.3: Write migration 004 and centralize its SQL
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 3
**Objective**: Add the `inbox_submissions` and `messages` tables at schema version 4, with every statement and column name living in one module.

**Steps**:
- [ ] Write `src/amoeba/store/schema/004_inbox_and_messages.sql` creating both tables exactly as the LLD's "Database / Storage Schema" section specifies, including the autoincrement primary keys that carry D4's receiver-assigned order
- [ ] Add the index on `(project_id, channel, seq)` and the partial index on unacknowledged intents
- [ ] Add the backfill: one escalation row per **open** `HUMAN` blocked state, so D3's invariant holds from version 4 onward; do **not** backfill resolved historical blocks
- [ ] Create `src/amoeba/store/sql_inbox.py` holding every statement and column name for both tables, following the slice 101/102 convention
- [ ] Raise `EXPECTED_SCHEMA_VERSION` from 3 to 4

**Success Criteria**:
- [ ] No SQL string and no column name for either table appears outside `sql_inbox.py` and the migration file
- [ ] `EXPECTED_SCHEMA_VERSION` is 4 and the migration runner picks up `004` without modification
- [ ] Both autoincrement keys are declared `INTEGER PRIMARY KEY AUTOINCREMENT` so values are never reassigned after a delete
- [ ] `uv run pyright` clean

- [ ] Commit after this task, e.g. `feat(store): add migration 004 for inbox and messages`

**Files to Create**: `src/amoeba/store/schema/004_inbox_and_messages.sql`, `src/amoeba/store/sql_inbox.py`
**Files to Modify**: the module declaring `EXPECTED_SCHEMA_VERSION`

---

### Task 2.4: Test the migration from a real version-3 store
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 2
**Objective**: Prove the upgrade preserves existing data and performs the escalation backfill.

**Steps**:
- [ ] Build a fixture store at schema version 3 containing nodes, an **open** `HUMAN` blocked state, a resolved `HUMAN` blocked state, and journal entries
- [ ] Assert the upgrade to 4 leaves nodes, blocked states, and journal rows intact
- [ ] Assert exactly one backfilled escalation row exists for the open human block and **none** for the resolved one
- [ ] Assert a store created fresh at version 4 has both tables and both indexes

**Success Criteria**:
- [ ] A version-3 store with an open human block upgrades to 4 with all prior data intact and gains exactly one backfilled row
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(store): add inbox and messages schema at version 4`

**Files to Create**: `tests/store/test_migration_004.py`

---

## Section 3: One Block Writer and D3 Escalations

This section implements D3. Per the LLD, the consolidation is required for correctness: without it, recovery blocks would silently miss their escalation row.

### Task 3.1: Consolidate block writing into one internal writer
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 3
**Objective**: Make `block()` and `journal_escalate` write their blocks through a single internal writer, removing `_block_for_entry` as a separate write path.

**Steps**:
- [ ] Identify the two current paths: the public `block()` and `journal_escalate`'s private `_block_for_entry`
- [ ] Introduce one internal block writer both call, preserving each caller's existing public signature and behavior
- [ ] Delete `_block_for_entry` as a separate write path — it must not survive as a second way to write a block
- [ ] Add the keyword-only `payload=None` argument to `block()`, stored as NULL when absent
- [ ] Do **not** write escalation rows yet — that is Task 3.3, so this task stays a behavior-preserving consolidation

**Success Criteria**:
- [ ] Exactly one internal function writes a blocked state; `grep` confirms no second write path
- [ ] `_block_for_entry` no longer exists
- [ ] All slice 101 and 102 block, resolve, and recovery tests pass unchanged
- [ ] `uv run pyright` clean

- [ ] Commit after this task, e.g. `refactor(store): route block writing through one writer`

**Files to Modify**: the store modules holding `block()` and `journal_escalate`

---

### Task 3.2: Test the consolidation before behavior is added
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 1
**Objective**: Confirm the consolidation changed nothing, so any later failure is attributable to D3 rather than to the refactor.

**Steps**:
- [ ] Run the full slice 101 and 102 suites plus the load tier; all must pass with no test modified
- [ ] Assert `block(payload=…)` **accepts** the argument without error; do not assert it round-trips — migration 004 adds no payload column to `blocked_states`, and the payload only becomes readable on the escalation row in Task 3.3. The round-trip assertion lives in Task 3.4

**Success Criteria**:
- [ ] `uv run pytest` and `uv run pytest tests/load` pass with no slice 101/102 test modified
- [ ] Commit after this task, e.g. `refactor(store): consolidate block writing into one writer`

**Files to Modify**: the store block/resolve test module

---

### Task 3.3: Implement MessageOperations and the automatic escalation row
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: Create `store/messages.py` with the message read and acknowledge methods, and make the block writer emit one escalation row for every `HUMAN` block in the same transaction.

**Steps**:
- [ ] Create the message operations class in `src/amoeba/store/messages.py` with `messages`, `pending_intents`, and `acknowledge_message` per the LLD's API Contracts table, using only `sql_inbox.py` statements
- [ ] **Name it `MessageOperations`, not `MessagesMixin`.** The LLD says "mixin", but the assembled class is `Store(NodeOperations, BlockingOperations, JournalOperations)` — follow the house convention. The same applies to `InboxOperations` in Task 4.1
- [ ] Have `acknowledge_message` raise `InvalidTransitionError` when the row is already acknowledged or is not an intent
- [ ] In the internal block writer, write exactly one `escalation` row **in the same transaction** whenever the kind is `HUMAN`, carrying `node_id`, `blocked_state_id`, and the optional opaque payload
- [ ] Write **no** message for `JUDGE` or `SQ_CHECKPOINT` blocks — no channel is defined for them
- [ ] Wire `MessageOperations` into the `Store` class alongside the existing operations classes

**Success Criteria**:
- [ ] A human-blocked node without an escalation row cannot exist — the row commits with the block or neither does
- [ ] `messages(after_seq=n)` returns only rows with `seq > n`, ascending, and is stable across repeated calls
- [ ] `acknowledge_message` raises on a second acknowledge and on a non-intent row
- [ ] `uv run pyright` clean

- [ ] Commit after this task, e.g. `feat(store): add message operations and escalation on human block`

**Files to Create**: `src/amoeba/store/messages.py`
**Files to Modify**: the store class assembly, the internal block writer

---

### Task 3.4: Test escalation-on-block and the message read API
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 2
**Objective**: Cover the D3 invariant and the replay primitive.

**Steps**:
- [ ] Assert `block(kind=HUMAN)` writes exactly one escalation row in the same transaction, and that `JUDGE` and `SQ_CHECKPOINT` blocks write none
- [ ] Assert the escalation row carries the correct `node_id` and `blocked_state_id`
- [ ] Assert `block(payload=…)` round-trips the payload onto the escalation row, and that omitting it stores NULL — this is the first point where the payload is readable (moved here from Task 3.2)
- [ ] Assert `messages(channel=ESCALATION, after_seq=n)` returns only later rows in `seq` order, identically on repeated calls, **through a read-only handle**
- [ ] Assert `pending_intents` excludes acknowledged rows and that a second `acknowledge_message` raises

**Success Criteria**:
- [ ] All four assertions above pass
- [ ] A read-only handle can read messages, confirming outside consumers need no write access
- [ ] `uv run pytest` passes

- [ ] Commit after this task, e.g. `test: cover escalation rows and the message read api`

**Files to Create**: `tests/store/test_messages.py`

---

### Task 3.5: Implement and test D3's already-blocked escalation branch
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 2
**Objective**: Make `journal_escalate` escalate on its already-blocked branch, where today it writes nothing.

**Steps**:
- [ ] On the branch where the entry's node is **already blocked**, write an escalation row pointing at the node's **existing open blocked state**, with `journal_entry_id` set — whatever kind that existing block is
- [ ] Keep `journal_escalate`'s signature unchanged; it must still write no second block on this branch
- [ ] Ensure the unblocked path also carries `journal_entry_id` on its escalation row

**Success Criteria**:
- [ ] `journal_escalate` on an unblocked node writes the block and one escalation row carrying `journal_entry_id`
- [ ] On an already-blocked node — tested with **both** a `HUMAN` and a `JUDGE` existing block — it writes no second block and exactly one escalation row pointing at the existing open blocked state
- [ ] Slice 102's recovery tests pass, updated only where they asserted that nothing else happened on escalation
- [ ] Commit after this task, e.g. `feat(store): write escalation messages from the block writer`

**Files to Modify**: the journal/recovery store module, `tests/store/test_messages.py` or the recovery test module

---

## Section 4: apply_submission

Pure library work — no files and no tenant yet, per the LLD's Development Approach.

### Task 4.1: Implement InboxOperations.apply_submission with the replay check
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 3
**Objective**: Create `store/inbox.py` with the single-transaction apply, starting with idempotency.

**Steps**:
- [ ] Create `InboxOperations` in `src/amoeba/store/inbox.py` with `apply_submission`, `submission`, and `submissions` per the LLD's API Contracts table (house naming, per Task 3.3 — the LLD calls it `InboxMixin`)
- [ ] Structure `apply_submission` as **one transaction**: replay check by submission id, then precondition, then effect, then record
- [ ] On replay, return the existing record unchanged and perform no effect
- [ ] Define the kind-to-effect mapping as a single table, per the LLD's "Adding a submission kind" rule
- [ ] Wire `InboxOperations` into the `Store` class

**Success Criteria**:
- [ ] Applying the same submission id twice leaves exactly one record and performs the effect once
- [ ] The effect and the record commit together — no state exists where one is present without the other
- [ ] Every `SubmissionKind` member has an entry in the kind-to-effect mapping, enforced by a test
- [ ] `uv run pyright` clean

- [ ] Commit after this task, e.g. `feat(store): add apply_submission with replay check`

**Files to Create**: `src/amoeba/store/inbox.py`
**Files to Modify**: the store class assembly

---

### Task 4.2: Implement the three submission kinds and their rejection branches
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Implement `create_project`, `resolution`, and `intent` effects with preconditions checked as explicit branches.

**Steps**:
- [ ] `create_project`: no precondition; naming a project that already exists records `applied`, not rejected — the requested state holds
- [ ] `resolution`: precondition is that the targeted **blocked state** exists in this project and is the node's **open** one; effect is `resolve()`
- [ ] `intent`: precondition is that `node_id`, if given, exists in this project; effect is one row on the `intent` channel carrying the submission id as provenance
- [ ] Record `rejected` with a reason on every failed precondition — never raise to signal rejection, and never catch `InvalidTransitionError` to implement it
- [ ] Target a blocked-state id, **never** a node id, and never redirect a stale target to a newer block

**Success Criteria**:
- [ ] A `resolution` fills the targeted slot and flips the node `runnable`, in one transaction
- [ ] A `resolution` naming an already-resolved blocked state, a blocked state of another project, or a nonexistent one is recorded `rejected` with a reason
- [ ] A node re-blocked since the original block is **not** resolved by a stale reply
- [ ] An `intent` produces one unacknowledged message carrying the submission id
- [ ] `InvalidTransitionError` is nowhere caught to implement a rejection

- [ ] Commit after this task, e.g. `feat(store): add the three submission kind effects`

**Files to Modify**: `src/amoeba/store/inbox.py`

---

### Task 4.3: Test apply_submission across every kind and branch
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: Cover replay, all three kinds, every rejection branch, and D4's ordering.

**Steps**:
- [ ] Test replay: the same id applied twice changes nothing and leaves one record
- [ ] Test each kind's applied path and each rejection branch named in Task 4.2
- [ ] Test that `applied_seq` and `messages.seq` increase in **apply order regardless of the `submitted_at` values** in the envelopes — construct envelopes with out-of-order timestamps
- [ ] Test `submissions(outcome=…)` filtering and `applied_seq` ordering
- [ ] Test that a `create_project` for an existing project is `applied` and changes nothing

**Success Criteria**:
- [ ] Every branch in Task 4.2's table has a test
- [ ] Ordering is proven independent of `submitted_at`, pinning D4
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(store): add apply_submission with three submission kinds`

**Files to Create**: `tests/store/test_inbox_apply.py`

---

## Section 5: The amoeba.inbox Package

### Task 5.1: Define the layout and the envelope models
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 2
**Objective**: Create the directory/filename scheme and the pydantic envelope, each defined exactly once.

**Steps**:
- [ ] Create `src/amoeba/inbox/layout.py` defining the four directory names (`tmp`, `new`, `quarantine`, `failed`), the sidecar suffixes, and the filename scheme `{submitted_at_ns:020d}-{submission_id}.json` — each in exactly one place
- [ ] Create `src/amoeba/inbox/envelope.py` with the pydantic envelope carrying `envelope_version`, `id`, `project_id`, `kind`, `submitted_by`, `submitted_at`, `payload`, plus the per-kind payload models
- [ ] Define the kind-to-payload-model mapping here as a single module-level constant (moved from Task 2.1), and add a test in `tests/inbox/` asserting every `SubmissionKind` member has an entry — adding a kind without its payload model must fail that test
- [ ] Configure the envelope to **ignore unknown extra fields** and to reject an unknown `envelope_version` rather than best-effort parsing it
- [ ] Import vocabularies from `amoeba.store` (models only); do **not** import `Store` — the dependency direction in the LLD's Component Structure is one-way
- [ ] **Extract** the project-id rule in `amoeba.store.paths` into a standalone `validate_project_id(project_id)`: today the three checks (non-empty, no path separator, not `.` or `..`) are inline inside `store_path()`, so there is no way to validate an id *without* computing a path — which `submit()` and `open_project` both need. Have `store_path()` call the extracted function so the rule still has exactly one definition
- [ ] Reuse that function from the envelope; do not re-implement the rule

**Success Criteria**:
- [ ] Directory names and the filename scheme appear only in `layout.py`
- [ ] `amoeba.inbox` imports no write path from `amoeba.store`
- [ ] Project-id validation has exactly one definition, callable without computing a path
- [ ] `store_path()` behavior is unchanged — slice 101's path tests pass untouched
- [ ] `uv run pyright` clean

- [ ] Commit after this task, e.g. `feat(inbox): add layout, envelope, and project id validation`

**Files to Create**: `src/amoeba/inbox/layout.py`, `src/amoeba/inbox/envelope.py`, `src/amoeba/inbox/__init__.py`
**Files to Modify**: `src/amoeba/store/paths.py`

---

### Task 5.2: Implement submit() with fsync-ordered durability
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Implement the only write path open to outside parts, per the LLD's Data Flow "Submit" block.

**Steps**:
- [ ] Implement `submit(*, project_id, kind, payload, submitted_by, submission_id=None, store_dir=None) -> str` in `src/amoeba/inbox/submit.py`
- [ ] Validate the project id, envelope, and payload for the kind **before writing anything**
- [ ] Write to `inbox/tmp/`, **fsync the file**, rename into `inbox/new/`, then **fsync the directory** — in that order
- [ ] Generate a submission id when none is passed, so a retrying submitter can pass the same one back (D2)
- [ ] Raise typed `InboxSubmitError`-family errors on validation or I/O failure, leaving nothing in `new/`
- [ ] Create the inbox directories on demand with the user's default permissions, per the LLD's Security note

**Success Criteria**:
- [ ] `submit()` returns only after the file is fsync-durable in `new/`
- [ ] An invalid payload or project id raises and leaves nothing in `new/` **or** `tmp/`
- [ ] `submit()` works whether or not the resident process is running
- [ ] `submit()` opens no store, read-write or otherwise

- [ ] Commit after this task, e.g. `feat(inbox): add submit with fsync-ordered durability`

**Files to Create**: `src/amoeba/inbox/submit.py`

---

### Task 5.3: Test submit() including the fsync call order
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 2
**Objective**: Cover durability mechanics and validation failure, per the LLD's Mitigation Strategies.

**Steps**:
- [ ] Assert both fsync calls occur **in order** (file, then directory) — the LLD names this the one place a call-order assertion is the honest test, because unit tests cannot simulate power loss
- [ ] Assert an invalid payload, an invalid project id, and a project id containing a path separator or equal to `.` or `..` each raise and leave `new/` and `tmp/` empty
- [ ] Assert the returned id is the one passed when `submission_id` is supplied, and is generated otherwise
- [ ] Assert the filename matches the scheme in `layout.py`

**Success Criteria**:
- [ ] The fsync order assertion fails if either call is removed or reordered
- [ ] No test asserts durability beyond "fsync-durable on a POSIX filesystem" — the contract does not overclaim
- [ ] `uv run pytest` passes

- [ ] Commit after this task, e.g. `test: cover submit durability and validation failures`

**Files to Create**: `tests/inbox/test_submit.py`

---

### Task 5.4: Implement the read-only listings
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 2
**Objective**: Implement `pending()`, `quarantined()`, and `failed()` in `src/amoeba/inbox/pending.py`.

**Steps**:
- [ ] `pending(store_dir=None)` lists files in `new/` in drain order (filename order — which the LLD is explicit is *not* authoritative order)
- [ ] `quarantined(store_dir=None)` lists quarantined files with the reason from each `.reason.json` sidecar
- [ ] `failed(store_dir=None)` lists parked files with the attempt count and last error from each `.attempts.json` sidecar
- [ ] Do **not** list stray `tmp/` files — per the LLD they are harmless and out of scope for this slice
- [ ] Return the frozen transfer types the LLD's API Contracts table names

**Success Criteria**:
- [ ] All three listings work with the process running and stopped, and open no store
- [ ] A stray `tmp/` file appears in no listing
- [ ] A sidecar-less file in `quarantine/` or `failed/` is reported rather than crashing the listing

- [ ] Commit after this task, e.g. `feat(inbox): add pending, quarantined, and failed listings`

**Files to Create**: `src/amoeba/inbox/pending.py`

---

### Task 5.5: Test the listings against real submit() output and damaged files
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 2
**Objective**: Build the envelope fixtures the LLD's Technical Requirements demand and cover the listings.

**Steps**:
- [ ] Create fixtures that include **a file produced by the real `submit()`** and hand-damaged variants of it: truncated, wrong `envelope_version`, and extra unknown fields
- [ ] Assert the extra-fields variant parses (unknown fields ignored) while the truncated and wrong-version variants do not
- [ ] Assert `pending()` returns files in drain order and that `quarantined()` and `failed()` surface their sidecar contents
- [ ] Put the shared envelope fixtures in the **root `tests/conftest.py`**, not in `tests/inbox/conftest.py` — Section 6's tenant tests live in `tests/process/` and conftest fixtures only apply downward, so a sibling directory cannot see them
- [ ] Add `__init__.py` to every new test package created in this slice (`tests/store/`, `tests/inbox/`, `tests/process/`, `tests/cli/`), matching the one precedent in `tests/load/`. Without it, pytest's import mode fails collection on duplicate test-file basenames

**Success Criteria**:
- [ ] Fixtures derive from real `submit()` output, not hand-written approximations of it
- [ ] Tenant tests in `tests/process/` can use the envelope fixtures
- [ ] Every new test directory has an `__init__.py`
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(inbox): add submit, listings, and envelope models`

**Files to Create**: `tests/inbox/test_listings.py`, `__init__.py` in each new test package
**Files to Modify**: `tests/conftest.py`

---

**Continued in `103-tasks.durable-inbox-and-message-queue-2.md`** — Sections 6–10.
