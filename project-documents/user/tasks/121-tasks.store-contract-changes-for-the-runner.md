---
docType: tasks
slice: store-contract-changes-for-the-runner
project: amoeba
lld: user/slices/121-slice.store-contract-changes-for-the-runner.md
dependencies:
- 101
- 102
- 103
- 104
- 105
- 106
- 107
- 108
- 109
- 110
projectState: Initiative 100 (101–110) is merged, and slice 120 is merged. The store
  is at schema version 8 (`EXPECTED_SCHEMA_VERSION` in `store/migrations.py`). `NodeStatus.DONE`
  is documented as terminal but nothing enforces it. `acknowledge_message(message_id,
  *, acknowledged_by)` records no outcome. `messages` has no fault, closure or outcome
  columns. No Runner tables exist. This slice adds migration 009, the Runner contract
  in the store, and contract text.
dateCreated: 20261022
dateUpdated: 20261023
status: in_progress
turns: 46
promptTokens: 2332931
cachedTokens: 2214290
cacheWriteTokens: 118591
completionTokens: 34933
durationSeconds: 238.7
costUsd: 1.045506
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

## Context Summary

- Working on the **store-contract-changes-for-the-runner** slice (121), the second slice of initiative 120 (Runner and Routing Engine). It changes 100's store only. No Runner behaviour is built here.
- **Current state:** the store is `Store`, assembled from operation mixins in `store/store.py`. `MessageOperations` (`store/messages.py`, 75 lines) holds `acknowledge_message`. `BlockWriter` (`store/_block_writer.py`, 172 lines) is the one block writer. `NodeOperations.update_node_status` (`store/nodes.py`) and `JournalOperations.journal_issue` (`store/journal.py`, 334 lines) are the other writers this slice guards. Statements live in `sql*.py` modules. `Message` and `MESSAGE_COLUMNS` (`store/inbox_models.py`, `store/sql_inbox.py`) are positional, and `map_message` checks row width. `amoeba.store.__all__` is pinned by `tests/test_public_api.py`.
- **Dependencies:** 100's migration runner, block writer, change-feed trigger `changes_message_posted` (migration 006), inspection listings and contract suite. Slice 120 is not a code prerequisite.
- **What this slice delivers:** `done` enforced as terminal (D1); acknowledgment outcomes, `intent_for_submission` and the atomic desired-state write (D2, D3, D8); project-scoped escalation (D4); routing decisions, table versions and attempt counts (D5–D7); new columns in `amoeba inspect messages`; contract text. All of it lands in migration `009`.
- **Next planned slice:** 122, which consumes project-scoped escalation and the done rule.

**Branch:** all implementation happens on `121-slice.store-contract-changes-for-the-runner`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/121-slice.store-contract-changes-for-the-runner.md` at the named decision (D1–D9), "Database / Storage Schema", or "API Contracts". Keep every new or changed source file near 300 lines. `store/journal.py` is at 334 already, so do not add logic to it beyond the one guard call in Task 3.3.

**Commit cadence:** one commit per task unless the task says it is committed with the next. A commit never holds untested behavior. Run `uv run ruff format .` before each commit.

**Task-level additions to the LLD:**
- **Public API pin.** Any task that adds a public name or method updates `amoeba/store/__init__.py` (`__all__`) and `tests/test_public_api.py` (`EXPECTED_EXPORTS`, `CONTRACT_METHODS`) in the same commit. Task 9.2 only verifies the final list.
- **Version-pin test.** `tests/store/test_migration_008.py` asserts `EXPECTED_SCHEMA_VERSION == CF_SCHEMA_VERSION` (line ~100). Task 2.3 changes it to assert the version is at least `CF_SCHEMA_VERSION`, since `009` raises the version to 9.
- **Rollback tests.** The LLD says existing store tests patch `_execute` to inject a failure. Find a working example with `grep -n "_execute" tests/store/*.py tests/test_failure_modes.py` before writing the first rollback test (Task 5.2) and follow it.
- **Write-lock rule.** Compound writes use `with self._connection:` as `acknowledge_message` does today, and validate before opening it.

**Section map.** 1 baseline; 2 migration 009, SQL and types; 3 terminal `done`; 4 acknowledgment outcome; 5 desired state; 6 project-scoped escalation; 7 routing decisions; 8 inspection columns; 9 contract text and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Create `121-slice.store-contract-changes-for-the-runner` from the target. If it exists, switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each. Record the passed-test count in this task. Baseline: 2017 passed
- **Success Criteria**:
  - [x] On the slice branch. Baseline suite, `ruff` and `pyright` are clean. If not, write `BLOCKED:` with the failure and stop. No commit needed

---

## Section 2: Migration 009, SQL and types

### Task 2.1: Write migration 009 and bump the schema version
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

Create `src/amoeba/store/schema/009_runner_contract.sql`. Follow the comment-header style of `004_inbox_and_messages.sql`: the file states that column names must match `sql_runner.py`. The LLD's "Database / Storage Schema" is a shape sketch. Write the real DDL from D2, D4–D8.

- [x] `messages`: five `ALTER TABLE ... ADD COLUMN` statements: `acknowledgment_outcome`, `acknowledgment_reason`, `fault_kind`, `closed_at`, `closed_by`. All nullable text, no default
- [x] Partial unique index `idx_messages_open_project_escalation` on `(project_id, fault_kind)` with the D4 `WHERE` clause
- [x] `routing_table_versions`: `version TEXT PRIMARY KEY`, `content TEXT NOT NULL`, `first_used_at TEXT NOT NULL`
- [x] `routing_decisions`: every D5 field with `NOT NULL` except `journal_entry_id`, `attempt_step` and `attempt_count`. Foreign keys to `nodes`, `command_journal` and `routing_table_versions`. JSON columns are `TEXT NOT NULL`, stored verbatim, as migration 004 does for payloads. Unique index on `(journal_entry_id)` where not null. Index on `(node_id, decided_at)`
- [x] `attempt_counts`: `node_id` (FK to `nodes`), `step`, `count INTEGER NOT NULL`, `updated_at`, primary key `(node_id, step)`
- [x] `desired_states`: D8 columns, `drive` and `hold` as nullable `INTEGER`, `message_id` as `NOT NULL` FK to `messages(id)`. Two partial unique indexes, one on `(project_id) WHERE node_id IS NULL` and one on `(node_id) WHERE node_id IS NOT NULL`. Check how migration 004 refers to `messages(id)` and match it
- [x] Set `EXPECTED_SCHEMA_VERSION` to 9 in `store/migrations.py`. Update its module docstring only if it names version 8
- **Success Criteria**:
  - [x] `Store.open_temporary()` succeeds and `read_schema_version` returns 9
  - [x] The migration file contains every column and index in D2, D4–D8 and no statement the LLD does not call for
  - [x] Committed with Task 2.3 (the tests below are what makes it safe)

### Task 2.2: Create `sql_runner.py`, `runner_models.py` and the mapping, and widen `Message`
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 4

- [x] `store/inbox_models.py`: add `AcknowledgmentOutcome` (`StrEnum`: `applied`, `no_op`, `rejected`). Add five fields to `Message` after `acknowledged_by`: `acknowledgment_outcome`, `acknowledgment_reason`, `fault_kind`, `closed_at`, `closed_by`, all defaulting to `None`. Update the docstring
- [x] `store/sql_runner.py` (new): table names, column names and index names for the four tables and the five message columns, each defined once. Define the column-order tuples used for SELECTs. Statements are added by the tasks that need them, in this module. Note: the five messages column constants are defined in sql_inbox.py (to avoid an import cycle); sql_runner imports nothing from them yet.
- [x] `store/sql_inbox.py`: append the five new message column constants to `MESSAGE_COLUMNS` in the same order as the `Message` fields. They may be imported from, or defined in, `sql_runner.py`. Pick one site and note it in the module docstring so each name is defined once
- [x] `store/mapping_inbox.py`: `map_message` reads the five new columns. `acknowledgment_outcome` goes through the closed-vocabulary coercion and raises `UnknownVocabularyValueError` for an unknown stored value. `closed_at` uses `decode_timestamp`. Add `AcknowledgmentOutcome` to the `_vocabulary` type constraint
- [x] `store/runner_models.py` (new): `Route` (`StrEnum`: `advance`, `rerun`, `escalate`), `RoutingDecisionInput`, `RoutingDecision`, `RoutingTableVersion`, `StatusEffect`, `BlockEffect`, `DesiredState`, `SetDesiredState`, `ClearDesiredState`. Frozen dataclasses with the fields in D3, D5, D6 and D8. `RoutingDecision` adds `id`, `attempt_step`, `attempt_count` and `decided_at` to the input's fields
- [x] `store/mapping_runner.py` (new): row-to-type mapping for `DesiredState`, `RoutingDecision` and `RoutingTableVersion`, in the style of `mapping_inbox.py`. Include a width check and vocabulary coercion for `Route`. JSON columns decode with `decode_mapping`
- [x] Export `AcknowledgmentOutcome`, `Route`, `RoutingDecision`, `RoutingDecisionInput`, `RoutingTableVersion`, `StatusEffect`, `BlockEffect`, `DesiredState`, `SetDesiredState` and `ClearDesiredState` from `amoeba/store/__init__.py`, and add them to `EXPECTED_EXPORTS` in `tests/test_public_api.py`. Later tasks add methods to `CONTRACT_METHODS` only
- **Success Criteria**:
  - [x] `uv run pyright` and `uv run ruff check .` are clean
  - [x] The existing message tests still pass (`uv run pytest tests/store tests/test_public_api.py -q`), with `tests/store/test_inbox_models.py` updated only if it constructs `Message` positionally
  - [x] No SQL string or column name literal appears outside `sql*.py` and the migration
  - [x] Committed with Task 2.3

### Task 2.3: Migration 009 and mapping tests
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 3

New `tests/store/test_migration_009.py`, modeled on `tests/store/test_migration_008.py` (stage a version-8 store by `migrate(connection, expected_version=8)`, insert rows through the store's own statements, then upgrade).

- [x] Fixture: a version-8 store holding a node, an acknowledged intent, an unacknowledged intent and a node escalation (use `sql_inbox.INSERT_MESSAGE` and the existing acknowledge statement)
- [x] After `migrate`, the stamp reads 9. Existing rows read back unchanged through `Store.open`. The five new columns read `None`. The four new tables exist and are empty
- [x] The partial unique index refuses a second open row with the same `(project_id, fault_kind)`, inserted by direct SQL. It allows a second row once the first has `closed_at` set. It ignores rows whose `fault_kind` is null
- [x] The `desired_states` indexes allow one project-target row and one row per node, and refuse a second of either
- [x] `routing_decisions` refuses a second row with the same `journal_entry_id`, and allows many rows with a null `journal_entry_id`
- [x] A read-only open of the version-8 file raises `StoreSchemaError`
- [x] `map_message` raises `UnknownVocabularyValueError` for a stored outcome outside `AcknowledgmentOutcome`, and for a row of the wrong width
- [x] Update `tests/store/test_migration_008.py` as the task-level addition above says
- **Success Criteria**:
  - [x] `uv run pytest tests/store tests/test_migrations.py tests/test_cli_inspect.py -q` passes
  - [x] Full `uv run pytest -q`, `ruff` and `pyright` are clean
  - [x] Tasks 2.1–2.3 committed as `feat: add migration 009 and runner contract types`

---

## Section 3: Terminal `done` (D1)

### Task 3.1: Add `_refuse_done` and guard `_write_block`
**Owner**: Junior AI | **Dependencies**: 2.3 | **Effort**: 2

- [x] `store/_block_writer.py`: add `_refuse_done(node_id)`. It reads the node's status and raises `InvalidTransitionError` naming the node when it is `done`. It is the one terminal check. Reuse an existing node-status read from `sql.py` if one exists. Otherwise add a statement
- [x] Call it at the top of `_write_block`, before any write. Update the docstring ("The caller has already checked that the node exists and is not blocked", plus "and is not done")
- [x] Do not add it to `_write_resolution`. D1 explains why none is needed. Note that in that method's docstring in one line
- [x] Tests in new `tests/store/test_terminal_done.py`: `block()` of each `BlockedKind` on a done node raises and leaves the node, blocked states and messages unchanged. `journal_escalate` on an unresolved entry of a done node (staged with raw SQL, as a pre-009 store would hold it) raises `InvalidTransitionError` naming the node and does not change the node (D1's explicit failure)
- **Success Criteria**:
  - [x] The tests above pass. `uv run pytest tests/store/test_terminal_done.py tests/test_journal.py tests/test_recovery.py -q` passes
  - [x] Committed as `feat: refuse blocking a done node`

### Task 3.2: Guard `update_node_status`, including the unresolved-command refusal
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 3

- [x] `store/_block_writer.py`: add `_write_status(node_id, status, timestamp)`, which runs inside the caller's transaction and never commits. It reads the node's current status and applies the blocked-status refusals `update_node_status` has today (a blocked node cannot be moved, and a blocked status cannot be a target). Move `_refuse_blocked_status` from `nodes.py` into `_block_writer.py` for this, and import it back. It calls `_refuse_done` for **any** target status, including `done`. When the target is `NodeStatus.DONE` it also refuses with `InvalidTransitionError` while the node has an unresolved journal entry. Then it runs `sql.UPDATE_NODE_STATUS`. Use the existing statement for unresolved entries by node if `sql_journal.py` has one. If it has none, add one there that uses the existing partial index on unresolved entries, and name the index in a comment. This is the one status write that Task 7.3's `StatusEffect` reuses
- [x] `store/nodes.py` `update_node_status`: still raise `NodeNotFoundError` for a missing node, and call `_write_status` inside its existing transaction, with the blocked-status checks now living in the helper, in place of the direct `sql.UPDATE_NODE_STATUS` execute. `NodeOperations` must be able to reach the helper. If it does not inherit `BlockWriter`, move the helper to a shared base the way `BlockingOperations` and `JournalOperations` reach `_write_block`, and do not duplicate it. Note: NodeOperations now inherits BlockWriter; refuse_blocked_status (renamed from _refuse_blocked_status to avoid a private cross-module import) lives in _block_writer.py.
- [x] Update the method docstring's `Raises`. `create_node(status=DONE)` stays allowed
- [x] Tests in `tests/store/test_terminal_done.py`: parametrize over every `NodeStatus` so `update_node_status` on a done node raises, naming the node, and leaves it unchanged. A node with an unresolved entry refuses `done`, and after `journal_resolve` `done` is accepted. `create_node(status=DONE)` still works
- **Success Criteria**:
  - [x] The tests above pass. Full `uv run pytest -q` passes. Fix any existing test that marked a node done and then moved it, since D1 makes that illegal. Do not weaken the guard
  - [x] Committed as `feat: refuse status writes on a done node`

### Task 3.3: Guard `journal_issue`
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 1

- [x] `store/journal.py` `journal_issue`: call `_refuse_done` after the parameter-key check and `_require_node`, before the transaction. Add one `Raises` line. No other change to this 334-line file
- [x] Test in `tests/store/test_terminal_done.py`: `journal_issue` on a done node raises `InvalidTransitionError` and the journal is empty
- **Success Criteria**:
  - [x] The test passes. Committed as `feat: refuse journaling against a done node`

### Task 3.4: Writer-inventory test
**Owner**: Junior AI | **Dependencies**: 3.3 | **Effort**: 2

- [x] In `tests/store/test_terminal_done.py`, parse every module under `src/amoeba/` with `ast`, as `tests/test_writer_guard.py` does, and assert `UPDATE_NODE_STATUS` is referenced only from `store/_block_writer.py`, `store/nodes.py` and `store/sql.py`. Have the failure message name D1's table. Note: nodes.py no longer names UPDATE_NODE_STATUS (it goes through BlockWriter._write_status), so the allowed set is _block_writer.py and sql.py only.
- [x] Update `tests/test_failure_modes.py` only if its raw tamper (line ~263, direct SQL on a separate connection) now trips a guard. It should not
- **Success Criteria**:
  - [x] `uv run pytest tests/store/test_terminal_done.py tests/test_failure_modes.py -q` passes. Full suite, `ruff` and `pyright` clean
  - [x] Committed as `test: guard the node-status writer inventory`

---

## Section 4: Acknowledgment outcome (D2)

### Task 4.1: Validate and record the outcome in `acknowledge_message`
**Owner**: Junior AI | **Dependencies**: 3.4 | **Effort**: 3

- [x] `store/messages.py`: change the signature to `acknowledge_message(message_id, *, acknowledged_by, outcome, reason=None)`. `outcome` is required, with no default. Leave `desired_state` for Task 5.2
- [x] Validate before opening the transaction, each raising `ValueError`: `rejected` needs a non-empty, non-whitespace `reason`. `reason`, when given for any outcome, must be a non-empty string. Coerce `outcome` through `AcknowledgmentOutcome(outcome)`
- [x] `store/sql_inbox.py` or `sql_runner.py`: extend `ACKNOWLEDGE_MESSAGE` to set the two new columns. Keep the `IS NULL` and channel guards, so a second acknowledgment still raises `InvalidTransitionError`
- [x] Update the docstring: Args, Raises, and the pre-009 note ("a `None` outcome means acknowledged before outcomes were recorded")
- **Success Criteria**:
  - [x] Each of the three outcomes is stored and read back on the returned `Message`
  - [x] `rejected` without a reason raises `ValueError` and the row stays unacknowledged
  - [x] A second acknowledgment still raises `InvalidTransitionError` and the first outcome is kept

### Task 4.2: Add `intent_for_submission`
**Owner**: Junior AI | **Dependencies**: 4.1 | **Effort**: 2

- [x] `store/sql_inbox.py`: add a select by `submission_id` restricted to the intent channel. `messages.submission_id` has no index and the design adds none, so the lookup scans the project's messages. That is accepted for now. Issue #19 tracks adding the index
- [x] `store/messages.py`: `intent_for_submission(submission_id) -> Message | None`. Add it to `amoeba.store`'s `CONTRACT_METHODS` pin
- **Success Criteria**:
  - [x] Returns the intent row a submission created, `None` for an unknown id, and works on a handle from `Store.open_read_only`

### Task 4.3: Update callers and test the acknowledgment
**Owner**: Junior AI | **Dependencies**: 4.2 | **Effort**: 3

- [x] `tests/store/test_messages.py`: every `acknowledge_message` call passes an `outcome`. Add: the three outcomes round-trip; `rejected` with no reason and with a blank reason raises `ValueError` and writes nothing; `applied` and `no_op` accept a reason; `outcome` omitted is a `TypeError`; a pre-009-style row (raw SQL, outcome null) reads back with `acknowledgment_outcome` `None`; `intent_for_submission` after `apply_submission` of an intent returns the row both before and after acknowledgment, and through a read-only handle
- [x] `tests/contract/runner_tenant.py` (line ~122): the stand-in acknowledges with `outcome=AcknowledgmentOutcome.APPLIED`. Import it from `amoeba.store` (contract-suite imports must be public exports, per `tests/contract/test_public_api_rule.py`). (Task 2.2 exported it)
- [x] `tests/contract/oracle.py`: make `message_fact` distinguish outcomes (for example `acknowledged:applied`), update `read_state`, and update the expected fact in every scenario that declares an acknowledged intent. Find them with `grep -rn "acknowledged" tests/contract`
- **Success Criteria**:
  - [x] `uv run pytest tests/store/test_messages.py tests/contract tests/test_public_api.py -q` passes
  - [x] Full suite, `ruff` and `pyright` are clean
  - [x] Tasks 4.1–4.3 committed as `feat: record acknowledgment outcomes and add intent_for_submission`

---

## Section 5: Desired state (D3, D8)

### Task 5.1: Desired-state statements and reads
**Owner**: Junior AI | **Dependencies**: 4.3 | **Effort**: 3

- [x] `store/sql_runner.py`: statements to select one target's row (project target and node target are two statements, because `node_id IS NULL` cannot be bound), select all for a project, upsert (replace the whole row), and delete by target. Note: replace is delete-then-insert in one transaction (ON CONFLICT cannot name a partial index predicate portably). MessageOperations now inherits DesiredStateOperations so acknowledge_message reaches the write.
- [x] `store/desired_states.py` (new, mixed into `Store` after `MessageOperations`): `desired_state(project_id, *, node_id=None) -> DesiredState | None` and `desired_states(project_id) -> list[DesiredState]`. Both work through a read-only handle. Order `desired_states` deterministically (project target first, then by node id)
- [x] The same module holds the internal `_write_desired_state_change(intent, change, timestamp)`. It runs inside the caller's transaction and never commits. For `SetDesiredState` it applies the D3 shape checks, then upserts. For `ClearDesiredState` it deletes, and a missing row writes nothing. Shape checks, each `ValueError`: `drive` and `hold` both `None`; `drive_until_step` with `drive` not `True`; a step value that is empty text. A non-null `node_id` must name a node in the intent's project, else `NodeNotFoundError`
- [x] Register `DesiredStateOperations` in the `Store` bases. Pin the two read methods in `CONTRACT_METHODS`
- **Success Criteria**:
  - [x] Reads return `None` or an empty list on a fresh store
  - [x] `pyright` is clean. The module is under about 300 lines
  - [x] Committed with Task 5.2

### Task 5.2: Atomic desired state in `acknowledge_message`
**Owner**: Junior AI | **Dependencies**: 5.1 | **Effort**: 3

- [x] `store/messages.py`: add `desired_state: SetDesiredState | ClearDesiredState | None = None` to `acknowledge_message`. Reject a desired state with any outcome other than `applied` (`ValueError`), before opening the transaction
- [x] Inside the one transaction, acknowledge the row first (so a non-intent or already acknowledged row raises before any desired-state write), then call `_write_desired_state_change`. If it raises, the `with self._connection:` block rolls the acknowledgment back
- [x] Load the intent's `project_id` for the node-in-project check from the row being acknowledged. The row's `id` is the `message_id` provenance
- **Success Criteria**:
  - [x] An `applied` acknowledgment with `SetDesiredState` writes the row and the acknowledgment together
  - [x] Replacing a target's row replaces all of it (drive-only after hold-only leaves hold `None`)

### Task 5.3: Desired-state tests
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 3

New `tests/store/test_desired_state.py`.

- [x] Set at the project target and at a node target. Both reads return the row with `message_id` equal to the intent
- [x] Replace semantics; `ClearDesiredState` deletes; clearing a target with no row acknowledges and writes nothing
- [x] Each shape rule raises `ValueError`, the intent stays unacknowledged, and no row exists afterwards
- [x] A node outside the project, and a missing node, raise `NodeNotFoundError` and leave the intent unacknowledged
- [x] A desired state with `no_op` or `rejected` raises `ValueError`
- [x] **Rollback:** patch `_write_desired_state_change` (or `_execute` for the upsert statement) to raise after the acknowledgment statement ran. Assert the intent is still unacknowledged and still in `pending_intents`. Note: failure injected by tests/fault_injection.py (fail_on_statement), since no existing test patched _execute.
- [x] A desired state on an already-acknowledged intent raises `InvalidTransitionError` and does not change the existing row
- **Success Criteria**:
  - [x] `uv run pytest tests/store/test_desired_state.py tests/store/test_messages.py -q` passes. Full suite, `ruff` and `pyright` clean
  - [x] Tasks 5.1–5.3 committed as `feat: write desired state inside the intent acknowledgment`

---

## Section 6: Project-scoped escalation (D4)

### Task 6.1: Raise, list and close
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

- [x] `store/sql_runner.py`: statements to select the open row for `(project_id, fault_kind)`, select open project-scoped rows by `seq`, insert a project-scoped escalation (reuse `INSERT_MESSAGE` if it can carry `fault_kind`. If it cannot, add a statement that does and do not duplicate the base column list), and close by id (guarded by `closed_at IS NULL`, the escalation channel and `fault_kind IS NOT NULL`). Note: INSERT_MESSAGE is now built by sql_inbox.insert_message_statement from MESSAGE_INSERT_COLUMNS; the project-escalation insert extends it with fault_kind. _require_message moved to StoreBase.
- [x] `store/project_escalations.py` (new, mixed into `Store`): `raise_project_escalation(project_id, *, fault_kind, payload) -> Message`, `open_project_escalations(project_id) -> list[Message]`, `close_project_escalation(message_id, *, closed_by) -> Message`
- [x] Raise: `fault_kind` must be non-empty text (`ValueError`). `payload` is required and JSON-encoded like a block's payload. An open row for the pair is returned unchanged with nothing written. Otherwise insert with `node_id`, `blocked_state_id` and `journal_entry_id` null, inside one transaction. The existing trigger emits `message_posted`
- [x] Close: zero rows changed raises `InvalidTransitionError` (missing, not project-scoped, or already closed). `closed_by` must be non-empty (`ValueError`). Return the closed row
- [x] Export no new names (the methods are on `Store`). Pin the three methods in `CONTRACT_METHODS`
- **Success Criteria**:
  - [x] `pyright` clean. Open-row reads use the partial index (the select repeats the index's `WHERE` literally, as `SELECT_PENDING_INTENTS` does. Note this in a comment)
  - [x] Committed with Task 6.2

### Task 6.2: Project-scoped escalation tests
**Owner**: Junior AI | **Dependencies**: 6.1 | **Effort**: 3

New `tests/store/test_project_escalation.py`.

- [x] Raising twice for one `(project, kind)` returns the same id and leaves one row. A second kind yields a second row. A second project with the same kind yields a separate row
- [x] After close, raising again yields a new row and `open_project_escalations` shows only it
- [x] `open_project_escalations` returns rows in `seq` order and excludes closed rows and node escalations
- [x] Close raises `InvalidTransitionError` for a missing id, a node escalation, an intent row and an already closed row. Closing records `closed_at` and `closed_by`
- [x] Empty `fault_kind` and empty `closed_by` raise `ValueError`. Nothing is written
- [x] The feed carries a `message_posted` change for the raise (use the feed read the existing trigger tests use, `tests/store/test_feed_triggers.py`). Closing adds no change (D9)
- [x] A node escalation's `pending_intents` and `messages(channel=ESCALATION)` behavior is unchanged
- **Success Criteria**:
  - [x] `uv run pytest tests/store/test_project_escalation.py tests/store/test_feed_triggers.py -q` passes. Full suite, `ruff` and `pyright` clean
  - [x] Tasks 6.1–6.2 committed as `feat: add project-scoped escalation`

---

## Section 7: Routing decisions (D5–D7)

### Task 7.1: Statements and reads
**Owner**: Junior AI | **Dependencies**: 6.2 | **Effort**: 3

- [ ] `store/sql_runner.py`: insert and select statements for `routing_table_versions`, `routing_decisions` (by id, by journal entry, by node oldest first), and `attempt_counts` (select, upsert-increment returning the new count; use SQLite upsert and read back inside the transaction)
- [ ] `store/routing_decisions.py` (new, mixed into `Store`): the reads `routing_decision`, `routing_decision_for_entry`, `routing_decisions(node_id)`, `routing_table_version` and `attempt_count`. Missing returns `None` or an empty list. `attempt_count` returns `0` for a pair with no row, and its docstring says that is the true count
- [ ] Pin the five read methods in `CONTRACT_METHODS`
- [ ] Tests in new `tests/store/test_routing_reads.py`: on a fresh store each read returns `None`, an empty list or `0`. With rows inserted by the `sql_runner.py` statements, each read returns the mapped row, `routing_decisions` is oldest first, and every read works through `Store.open_read_only`
- **Success Criteria**:
  - [ ] The tests pass. Full suite, `ruff` and `pyright` clean
  - [ ] Committed as `feat: add routing decision and attempt-count reads`

### Task 7.2: `record_routing_decision` validation
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 3

Keep this in `store/routing_decisions.py`. If the module nears 300 lines, move the validation into `store/_routing_validation.py`.

- [ ] Validate before opening the transaction. `ValueError`: any text field in `RoutingDecisionInput` empty (project, rule id, table version, Amoeba version), `inputs` or `route_parameters` not JSON-serializable, `attempt_step` given but empty, `table.version` not equal to `decision.table_version`. `NodeNotFoundError`: the node is not in the project. `InvalidTransitionError`: `journal_entry_id` names an entry that is missing or in another project
- [ ] Coerce `route` through `Route`. A `StatusEffect` whose status is a blocked status is refused as `update_node_status` refuses it
- [ ] Write the validation as a private function with no public method yet (`record_routing_decision` is introduced in Task 7.3, so no public method ships that validates but does not write). Test it directly in new `tests/store/test_routing_validation.py`: each failure raises its exception, and a valid input passes. Task 7.4 asserts that the public method writes nothing on failure
- **Success Criteria**:
  - [ ] The tests pass. Full suite, `ruff` and `pyright` clean
  - [ ] Committed as `feat: validate routing decisions`

### Task 7.3: The one-transaction write
**Owner**: Junior AI | **Dependencies**: 7.2 | **Effort**: 4

- [ ] In one `with self._connection:` block, in D5's order: insert the table version if new (same version with different content raises `StoreIntegrityError`, compared byte for byte); insert the decision row; if `attempt_step` is given, increment the counter and store the new count on the decision; apply `effect`
- [ ] `StatusEffect(status)` calls Task 3.2's `_write_status(node_id, status, timestamp)` inside the transaction. That gives it the done-is-terminal and unresolved-entry refusals without copying them. It cannot call `update_node_status`, which opens its own transaction
- [ ] Pin `record_routing_decision` in `CONTRACT_METHODS` in `tests/test_public_api.py`
- [ ] A `BlockEffect` on a node that is already blocked raises the same exception `block()` raises for an already-blocked node, before anything is written. Read `store/blocking.py` for that check and reuse it rather than copying it. `_write_block` assumes its caller has made this check
- [ ] `BlockEffect(context, payload)` writes a `HUMAN` block through `_write_block`, with `journal_entry_id` from the decision, so the escalation row lands in the same transaction
- [ ] A duplicate decision for one `journal_entry_id` surfaces as `StoreIntegrityError`, converted from the unique-index violation the way other store writes convert `sqlite3.IntegrityError`. Find the existing conversion with `grep -rn "IntegrityError" src/amoeba/store`
- [ ] Return the stored `RoutingDecision`, read back inside the transaction
- **Success Criteria**:
  - [ ] All four effects of D5 land together. An injected failure at any step leaves none of them
  - [ ] Module sizes stay near 300 lines
  - [ ] Committed with Task 7.4, its immediate test task

### Task 7.4: Routing decision tests
**Owner**: Junior AI | **Dependencies**: 7.3 | **Effort**: 4

New `tests/store/test_routing_decisions.py`. If it nears 300 lines, split the rollback cases into `test_routing_decisions_atomic.py`.

- [ ] Happy path: a decision with a new table version, an attempt step and a `StatusEffect`. Assert the version, decision, count and node status, and that `routing_decision_for_entry` and `routing_table_version` return what was written (the LLD walkthrough step 5)
- [ ] A second decision with the same table version and same content stores one version row. Same version with different content raises `StoreIntegrityError` and writes nothing, including no decision
- [ ] `attempt_count` is `0` before, `1` after, `2` after a second decision on another entry with the same `(node, step)`. A decision without `attempt_step` leaves counts alone and stores a null `attempt_count`. Two steps on one node count separately
- [ ] A second decision for one entry raises `StoreIntegrityError`. Decisions with no entry may repeat
- [ ] `BlockEffect` writes a HUMAN block and its escalation row. `StatusEffect(done)` on a done node raises and nothing is recorded. `StatusEffect(done)` with an unresolved entry raises and nothing is recorded
- [ ] `BlockEffect` on an already-blocked node raises and nothing is recorded. `StatusEffect` on a blocked node, and with a blocked target status, raises and nothing is recorded
- [ ] `effect=None` records the decision and counter only
- [ ] `routing_decisions(node_id)` returns oldest first, and an empty list for a node with none
- [ ] **Rollback:** inject a failure at each of the four steps in turn (patch `_execute` for the matching statement, per the task-level note). After each, assert no version row, no decision, no count change and the node unchanged
- [ ] Each Task 7.2 validation failure writes nothing
- **Success Criteria**:
  - [ ] `uv run pytest tests/store/test_routing_decisions.py -q` passes. Full suite, `ruff` and `pyright` clean
  - [ ] Tasks 7.3–7.4 committed as `feat: record routing decisions with their effects`

---

## Section 8: Inspection columns

### Task 8.1: Add the columns to `amoeba inspect messages`
**Owner**: Junior AI | **Dependencies**: 7.4 | **Effort**: 2

- [ ] `inspection/inbox.py` `message_rows`: add `acknowledgment_outcome`, `acknowledgment_reason`, `fault_kind` and `closed_at`, each an empty string when unset and the outcome rendered as its `.value`. `closed_at` is isoformat, as `acknowledged_at` is. The network serves the same rows through the listings registry, so no network code changes
- [ ] Find the existing tests that pin the messages row shape: `grep -rn "acknowledged_at" tests/inspection tests/test_cli_inspect.py tests/serve tests/cli`. Update any that compare the whole key set
- **Success Criteria**:
  - [ ] Existing inspection and serve tests pass after updating exact-shape expectations

### Task 8.2: Inspection tests
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 2

- [ ] In the test module that covers the messages listing (found in 8.1), add: an acknowledged intent row shows its outcome and reason; an unacknowledged intent shows empty strings; an open project-scoped escalation shows its `fault_kind` and empty `closed_at`; after close, `closed_at` is set
- [ ] One test through the network read (`tests/serve/test_reads.py` pattern) shows the same four keys on `/v1/listings/messages`
- **Success Criteria**:
  - [ ] `uv run pytest tests/inspection tests/serve tests/test_cli_inspect.py -q` passes. Full suite, `ruff` and `pyright` clean
  - [ ] Tasks 8.1–8.2 committed as `feat: show outcome, fault and closure columns in message listings`

---

## Section 9: Contract text and final validation

### Task 9.1: Update `docs/store-contract.md`
**Owner**: Junior AI | **Dependencies**: 8.2 | **Effort**: 3

The file is 738 lines. Add a new `## The Runner contract` section after the Context Forge section (before "Read-only access"), and edit the existing sections named below. Do not restate the LLD. Document the behavior.

- [ ] `NodeStatus` table: the "Terminal" entry states that terminal status is now enforced, and which writes refuse a done node
- [ ] `## The Runner contract`: subsections for the done rule (D1, including the two extra refusals and what a caller does instead of blocking a done node), acknowledgment outcomes and desired state (D2, D3, D8), project-scoped escalation (D4), routing decisions, table versions and attempt counts (D5–D7), and the feed note (D9)
- [ ] Each subsection lists its vocabularies, types and methods in the form the file already uses, and repeats the "callers must not place secrets in them" rule for decision `inputs`, `route_parameters`, escalation payloads and table content
- [ ] "Failure modes" table: add the five rows from the LLD's "Patterns and Conventions" table
- [ ] "Migrations": add `009` to the list, and update any sentence that names version 8
- [ ] "Future work": add the closure change kind from D9
- **Success Criteria**:
  - [ ] Every public method and type in the LLD's "API Contracts" table appears in the file. Check with a grep for each name
  - [ ] Frontmatter `dateUpdated` is current
  - [ ] Committed as `docs: document the Runner contract in the store contract`

### Task 9.2: Update `docs/inbox-contract.md` and verify the public API pin
**Owner**: Junior AI | **Dependencies**: 9.1 | **Effort**: 2

- [ ] "Learning the outcome": add `intent_for_submission` and what the row's `acknowledgment_outcome` means, including `None` for rows acknowledged before outcomes existed
- [ ] "Reading messages": add the project-scoped escalation row shape and note `blocked_state_id` is null on it. Add the four new inspection columns
- [ ] The acknowledgment paragraph: add the outcome and the desired-state transaction
- [ ] Check `tests/test_public_api.py` against the LLD's "API Contracts" table. Every new public name and method is pinned and none are missing
- **Success Criteria**:
  - [ ] The three documented places are updated and cross-link to `store-contract.md`
  - [ ] `uv run pytest tests/test_public_api.py tests/test_process_public_api.py -q` passes
  - [ ] Committed as `docs: document acknowledgment outcomes and project escalations in the inbox contract`

### Task 9.3: Final validation
**Owner**: Junior AI | **Dependencies**: 9.2 | **Effort**: 2

- [ ] Run `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright` once each
- [ ] Check file sizes: `wc -l` on every new or changed source file under `src/amoeba/store/` and `inspection/inbox.py`. Anything above about 330 lines must be split or justified in a comment on this task. `journal.py` was already over, so it must have grown by no more than the Task 3.3 lines
- [ ] Confirm every new SQL statement and column name appears only in `sql*.py` and the migration: grep the new column names across `src/amoeba/` outside those files
- [ ] Walk the LLD's "Verification Walkthrough" steps 1, 2, 4, 5 and 6. Step 3 uses the contract suite, which Task 4.3 covered. Record any difference between the walkthrough text and actual behaviour in this task, and correct the LLD example if it is wrong
- [ ] Re-read the LLD's "Success Criteria" and tick each against a passing test
- **Success Criteria**:
  - [ ] All checks pass and the walkthrough runs as written
  - [ ] Work is committed on the slice branch. No merge is performed here
