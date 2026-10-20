---
docType: slice-design
slice: store-contract-changes-for-the-runner
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies: []
interfaces:
- 122
- 124
- 126
- 127
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
turns: 29
promptTokens: 1979312
cachedTokens: 1874456
cacheWriteTokens: 104806
completionTokens: 33843
durationSeconds: 361.6
costUsd: 1.890727
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Store Contract Changes for the Runner

## Overview

This slice makes the rest of the 100 contract changes that `120-arch.runner-routing-engine.md` lists under "Contract changes the Runner needs from 100". Slice 120 covers the run-id and observer changes. This slice covers everything else:

1. **`done` is terminal.** No store write moves a `done` node to another status. Today the contract says `done` is terminal, but nothing enforces it.
2. **Acknowledgment outcomes.** An intent's acknowledgment records `applied`, `no_op` or `rejected` (with a reason), and the submitter can read it. An intent is still acknowledged once, and a second acknowledgment still raises.
3. **Project-scoped escalation.** This is an escalation row for a fault that has no node. It is deduplicated on project and fault kind, so at most one is open per pair, and the Runner closes it. The closure is recorded on the row.
4. **Four Runner tables.** Routing decisions, routing-table versions, attempt counts and desired states. They are added through 100's migration mechanism, and each has a documented write and read API.

All of it lands in one migration, `009`. Slice 120 adds no migration, because journal parameters are JSON, so `009` follows build order.

The Runner does not exist yet. Every change here is store code, contract text and contract tests, and the stand-in Runner in `tests/contract/` is updated to use the new acknowledgment signature.

## Value

Architectural enablement. Slices 122–127 code against a store that already holds what they need, and they do not each reopen 100's contract. Two of the changes also close real gaps in 100. A node can no longer leave `done` by accident. A routing decision can no longer be recorded without its effect on the node, or the reverse, because the store writes both in one transaction (D5).

## Technical Scope

**Included**

- No write path moves a `done` node, and none can journal against one or mark a node done while it has an unresolved command (D1).
- `AcknowledgmentOutcome` vocabulary and two new columns on `messages`. `acknowledge_message` gains required `outcome` and optional `reason` and `desired_state` arguments (D2, D3). It also gains a submitter-side read, `intent_for_submission`.
- Project-scoped escalation: three columns on `messages`, a partial unique index, and three methods: raise, list open, close (D4).
- Tables `routing_decisions`, `routing_table_versions`, `attempt_counts` and `desired_states`, with the `Route` vocabulary, their types, and their write and read methods (D5–D8).
- `amoeba inspect messages` shows the new message columns. The network serves the same rows through `/v1/listings/messages`.
- Contract text in `docs/store-contract.md` and `docs/inbox-contract.md`. New tests, plus extensions to 100's contract suite and the public-API list.

**Excluded**

- Every Runner behaviour. This slice does not cover the intent body format or how it is interpreted (124), routing-table grammar and file format (126), fault kinds and when to close an escalation (122), or what counts as runnable (123, 125).
- A PM path to close a project-scoped escalation. Only the Runner closes one in v1 (D4).
- A feed change for decision records, closures or desired-state writes. The arch says "nothing new on the wire" (D9).
- Resetting attempt counts. No consumer needs it in v1.
- Recording merge policy on each dispatch decision. That belongs to 128 (see Integration Points).
- The unrouted-outcome query (resolved entries with no decision record). It is deferred to 125/126, which decide which entries need routing, and is tracked in issue #10.
- Node creation from outside the process. It stays out, as the arch says.

## Dependencies

### Prerequisites

- Initiative 100, complete.
- Slice 120 is not a code prerequisite. The two slices touch different methods in `store/journal.py`. Building this slice after 120 keeps their changes to `docs/store-contract.md` in order and keeps migration numbering simple.

### Interfaces Required

- 100's migration runner (`store/migrations.py`, `EXPECTED_SCHEMA_VERSION`, numbered `.sql` files).
- The one block writer (`store/_block_writer.py`). Every block, including one written as a decision's effect, goes through it, so the HUMAN-block escalation invariant holds.
- The `changes_message_posted` trigger (migration 006). It already emits a `message_posted` change for any `messages` insert, including one with a null `node_id`, so a project-scoped escalation appears on the feed without a new trigger.
- The convention that every SQL statement and column name is defined once in a `sql_*.py` module.

## Architecture

### Component Structure

New and changed store modules. They are mixed into `Store` as the existing operation classes are, and each stays under about 300 lines.

| Module | Role |
| --- | --- |
| `store/nodes.py` (changed) | `update_node_status` calls the terminal check and the unresolved-command check. |
| `store/journal.py` (changed) | `journal_issue` refuses a done node. |
| `store/_block_writer.py` (changed) | Adds `_refuse_done(node_id)`, the one terminal check (D1), and calls it in `_write_block`. |
| `store/messages.py` (changed) | `acknowledge_message` with outcome and desired state. Adds `intent_for_submission`. |
| `store/project_escalations.py` (new) | `raise_project_escalation`, `open_project_escalations`, `close_project_escalation`. |
| `store/routing_decisions.py` (new) | `record_routing_decision`, decision and table-version reads, attempt reads. |
| `store/desired_states.py` (new) | Desired-state reads, plus the internal `_write_desired_state_change` that `acknowledge_message` calls inside its transaction. |
| `store/runner_models.py` (new) | `Route`, `AcknowledgmentOutcome`, `RoutingDecision`, `RoutingDecisionInput`, `RoutingTableVersion`, `StatusEffect`, `BlockEffect`, `DesiredState`, `SetDesiredState`, `ClearDesiredState`. |
| `store/sql_runner.py` (new) | Every statement and column name for the four tables and the new message columns. |
| `store/mapping_runner.py` (new) | Row-to-type mapping for the new types. |
| `store/schema/009_runner_contract.sql` (new) | The migration. |
| `inspection/inbox.py` (changed) | Message rows gain the new columns. |

`AcknowledgmentOutcome` lives in `runner_models.py` and `Message` (in `inbox_models.py`) imports it. That way the vocabulary is defined once.

### Data Flow

These are the write paths the Runner will use. None of them runs until 122.

```
intent row ──pending_intents──▶ Runner (124) interprets the body
          ◀─acknowledge_message(outcome, reason, desired_state)── one transaction:
                 messages.acknowledged_* + acknowledgment_*  and  desired_states upsert/delete
submitter ──submission(id)──▶ applied
          ──intent_for_submission(id)──▶ Message with acknowledgment_outcome / reason

sq_run entry resolved (125) ──▶ Runner routes it (126)
          ──record_routing_decision(input, table, effect, attempt_step)── one transaction:
                 routing_table_versions (insert if new) + routing_decisions
                 + attempt_counts increment + node effect (status write or HUMAN block)

fault with no node (122) ──raise_project_escalation──▶ messages row (escalation, fault_kind)
                                                        └─ feed: message_posted
first tick without that fault ──close_project_escalation──▶ closed_at / closed_by set
```

### State Management

All state is in the per-project SQLite store. Nothing is cached in memory. Each public write is one call and one transaction, as in the rest of the store. The two compound writes, `acknowledge_message` with a desired state and `record_routing_decision`, exist so that writes the arch requires to land together cannot land apart.

**Tick cost.** The arch requires the tick to return promptly. The reads this slice adds for the Runner's per-tick path stay bounded by current state, not by history:
- `open_project_escalations` is served by the partial unique index on open rows.
- `desired_states` returns at most one row per target.
- The unresolved-command check in D1 uses the existing partial index on unresolved journal entries.

Reads over history (`routing_decisions(node_id)`, the decision lookups) are per node or per id, and each is backed by an index.

## Technical Decisions

### D1 — `done` is enforced on every write path
Status: decided
- **Inventory of node-status writers.** These are every statement that writes `nodes.status` (`sql.UPDATE_NODE_STATUS`) and every caller that reaches one:

  | Writer | Reached by | Terminal handling |
  | --- | --- | --- |
  | `update_node_status` (`nodes.py`) | public callers | calls `_refuse_done` |
  | `_write_block` (`_block_writer.py`) | `block()`, `journal_escalate`'s not-blocked branch, D5's `BlockEffect` | calls `_refuse_done` |
  | `_write_resolution` (`_block_writer.py`) | `resolve()`, the inbox `resolution` apply | needs none: it acts only on a blocked node, and a done node is never blocked |
  | D5's `StatusEffect` | `record_routing_decision` | uses `update_node_status`'s checks |

  A test asserts that `sql.UPDATE_NODE_STATUS` is referenced only from these modules, so a new writer cannot slip past the check unnoticed.
- `_refuse_done` raises `InvalidTransitionError` naming the node. `update_node_status` calls it for **any** target status, including `done`. A done node takes no status writes at all, which is stricter than "to any other status" and needs no same-status special case. `create_node(status=DONE)` stays allowed, because creating a node as done moves nothing.
- **Recovery never meets a done node.** Two rules guarantee it. `journal_issue` refuses a done node with `InvalidTransitionError`. Moving a node to `done`, through `update_node_status` or a `StatusEffect`, is refused while the node has an unresolved journal entry. So no unresolved entry can point at a done node, and `journal_escalate` needs no new branch or escalation shape. If a store from before `009` already holds such an entry, `_write_block` raises when recovery reaches it. The process then fails at start with an error naming the node, which is an explicit failure rather than a silent move out of `done`. No real store holds one. No shipped code before this slice marks a node done: `src/` has no caller of `update_node_status`, and only tests and the stand-in Runner do.

### D2 — Acknowledgment outcome columns on `messages`
Status: decided
- `AcknowledgmentOutcome` is a `StrEnum` with `applied`, `no_op` and `rejected`. Migration `009` adds `acknowledgment_outcome TEXT` and `acknowledgment_reason TEXT` to `messages`. `Message` gains both fields (`AcknowledgmentOutcome | None`, `str | None`).
- `acknowledge_message(message_id, *, acknowledged_by, outcome, reason=None, desired_state=None)`. `outcome` is **required**. A default of `applied` would be a silent default, and the store's rule is that none exist. **This departs from the plan's wording.** The plan says "existing acknowledgment callers are unaffected", but here each caller must now pass an outcome. What stays unaffected is the behaviour: an intent is acknowledged once, a second acknowledgment raises `InvalidTransitionError`, and nothing else on the intent channel changes. The only callers today are the stand-in Runner and `tests/store/test_messages.py`, and both are updated in this slice.
- Validation happens before anything is written, and each failure raises `ValueError`. `rejected` requires a non-empty `reason`. `applied` and `no_op` accept an optional reason, because a no-op is often worth explaining ("already past step P5"). A `desired_state` is accepted only with `applied`.
- Rows acknowledged before `009` read back with `acknowledgment_outcome` `None`. That value means "acknowledged before outcomes were recorded". The migration does not backfill them, because the store does not know what their outcome was.
- **Submitter read:** `intent_for_submission(submission_id) -> Message | None` returns the intent row that a submission created. `None` means no such row. The sequence for a submitter is `submission(id)` reports `applied`, then `intent_for_submission(id)`. That row is either unacknowledged (the Runner has not consumed it) or carries its outcome. The read works through a read-only handle.
- Rejected: an outcome column on `inbox_submissions`. That record is the inbox's verdict on applying the submission, and it is written once. The acknowledgment is a later event by a different party.

### D3 — Desired state is written inside the acknowledgment
Status: decided
- The arch requires that "applying an intent and acknowledging it happen in one store transaction". The store has no public transaction API, so the compound write is a parameter of `acknowledge_message`: `desired_state: SetDesiredState | ClearDesiredState | None`.
- `SetDesiredState(node_id, drive, drive_until_step, hold)` replaces the target's **whole** row. `node_id=None` is the project target. Merging a new intent with the target's earlier settings (an intent that sets only hold keeps the earlier drive) is 124's interpretation. 124 reads the current row and writes the merged one. The store stores what it is given.
- `ClearDesiredState(node_id)` deletes the target's row. Clearing a target that has no row is allowed and writes nothing, because the state the intent asks for already holds. The intent is still acknowledged with the caller's outcome.
- Shape rules, checked before writing, each raising `ValueError`: `drive` and `hold` cannot both be `None` (use clear for that). `drive_until_step` requires `drive is True`. A step value must be non-empty text. A non-null `node_id` must name a node of the intent's project, otherwise the call raises `NodeNotFoundError`. Whether a node's kind may be a target (initiative or slice only) is 124's rule. The store does not encode the target vocabulary.
- The table design is in D8.

### D4 — Project-scoped escalation is a `messages` row with a fault kind
Status: decided
- Migration `009` adds `fault_kind TEXT`, `closed_at TEXT` and `closed_by TEXT` to `messages`. A project-scoped escalation is a row on `escalation` with `node_id` and `blocked_state_id` null and `fault_kind` set. Node escalations keep `fault_kind`, `closed_at` and `closed_by` null. A node escalation's closure is its block's resolution.
- A partial unique index on `(project_id, fault_kind)`, filtered to `channel = 'escalation' AND fault_kind IS NOT NULL AND closed_at IS NULL`, enforces "at most one open per project and fault kind" in the schema, not just in code.
- `raise_project_escalation(project_id, *, fault_kind, payload) -> Message`. If one is already open for the pair, the store returns it unchanged and writes nothing, so a fault that recurs every tick cannot storm. Otherwise it writes the row, and the existing trigger emits `message_posted`. `payload` is required. It is the opaque mapping the Runner fills with the error, the same way a block's payload is opaque. `fault_kind` must be non-empty. Its vocabulary belongs to 122 and the store holds it as text, the same way it holds CF references.
- `open_project_escalations(project_id) -> list[Message]` returns open rows in `seq` order. 122 uses it to find, each tick, which open faults did not recur.
- `close_project_escalation(message_id, *, closed_by) -> Message` sets `closed_at` and `closed_by`. It raises `InvalidTransitionError` when the row does not exist, is not a project-scoped escalation, or is already closed. A later fault of the same kind then opens a new row.
- Rejected: a separate `project_escalations` table. Consumers already follow escalations by `seq` on one channel, and a second table would give them two places to look.

### D5 — A routing decision and its effect are one write
Status: decided
- `record_routing_decision(decision: RoutingDecisionInput, *, table: RoutingTableVersion, effect: StatusEffect | BlockEffect | None, attempt_step: str | None) -> RoutingDecision`. In one transaction it:
  1. inserts `table` into `routing_table_versions` if the version is new. If the version exists with different content, it raises `StoreIntegrityError` and writes nothing.
  2. inserts the decision row.
  3. when `attempt_step` is given, increments `attempt_counts` for `(node_id, attempt_step)` and records the new count on the decision.
  4. applies `effect`. `StatusEffect(status)` follows `update_node_status`'s rules (D1, no blocked statuses). `BlockEffect(context, payload)` writes a `HUMAN` block through `_write_block`, so its escalation row lands too.
- Why the effect is part of the call: a crash between "decision recorded" and "node marked done" would leave a node that is routed but never advanced. Its outcome has a decision record, so nothing would route it again. Taking the effect as a parameter makes that state impossible. It also adds no route semantics to the store. Which route needs which effect stays with 126.
- `RoutingDecisionInput` fields: `project_id`, `node_id`, `journal_entry_id` (optional), `inputs` (a JSON object, the routing inputs as 126 reduced them), `rule_id`, `table_version`, `amoeba_version`, `route: Route` and `route_parameters` (a JSON object: attempt limit, judge-eligible, and so on). Text fields must be non-empty. The node must exist in the project.
- When `journal_entry_id` is given, the entry must exist in the same project, otherwise the call raises `InvalidTransitionError`. A unique index allows at most one decision per entry, so an outcome cannot be routed twice. A second decision for the same entry raises `StoreIntegrityError`.
- **What the store fixes, and what 126 owns.** The store fixes four storage invariants:
  - the decision, its version, its counter increment and its effect land together;
  - table versions are write-once;
  - there is at most one decision per entry;
  - references must exist.

  Every routing meaning belongs to 126. That includes which entries are routed and in what state, which node a decision is recorded on, which route takes which effect, and when an attempt counts. The store checks none of these.
- `Route` is a store `StrEnum` with `advance`, `rerun` and `escalate`. It is the one definition 126 imports. 140 adds `judge` as a member.
- Reads: `routing_decision(decision_id)`, `routing_decision_for_entry(journal_entry_id)` and `routing_decisions(node_id)` (oldest first). Missing returns `None` or an empty list.
- The query for unrouted outcomes ("an ingested outcome with no decision record is unrouted") is not part of this slice. It runs every tick, and its bound depends on which entries need routing, which 125 and 126 decide. Issue #10 tracks it. The arch's crash-safety claim needs two things:
  - **A decision record that lands atomically with its effect.** This slice provides it.
  - **A query that finds outcomes without one.** Nothing routes before 126, so that query must land in 125 or 126, before the first route is taken. Issue #10 records that it blocks 126.
- **Shapes ahead of consumers.** This shape, and D7's, are the minimum the arch names: inputs, rule id, table version, Amoeba version and route. If 125's or 126's design needs a different shape, the plan's "Tables before their consumers" note applies. The change goes into 100's contract in that slice, through a new migration, as D8 says for desired states.

### D6 — Table versions are write-once, keyed by version
Status: decided
- `routing_table_versions(version TEXT PRIMARY KEY, content TEXT NOT NULL, first_used_at TEXT NOT NULL)`. `content` is the table file's text, verbatim. Its format is 126's.
- A version is stored the first time a decision uses it (D5 step 1). A version that is not used is not stored, as the arch says. The store compares content byte-for-byte, so editing a table without changing its version label fails loudly at the first decision. It does not silently record decisions that cannot be recomputed. How a version label is formed, for example from a digest of the content, is 126's choice.
- Read: `routing_table_version(version) -> RoutingTableVersion | None`. A decision plus this read is everything needed to recompute the decision.

### D7 — Attempt counts are incremented only by routing decisions
Status: decided
- `attempt_counts(node_id, step, count, updated_at)` has primary key `(node_id, step)`. `step` is opaque text from 123's step map. The arch counts attempts "per node and step", and this key holds that whichever way 123 lays out step nodes.
- The store increments the counter for a pair when a decision passes `attempt_step`, and does nothing else with it. The only writer is `record_routing_decision`, so a count and the decision that raised it cannot disagree. The decision row stores `attempt_count`, the value after its increment, or null when it did not count. What an attempt means, which decisions count one, and how the limit is compared are 126's choices.
- Read: `attempt_count(node_id, step) -> int`. A pair with no row returns `0`. That is the true count, not a fallback, and the docstring says so.
- No reset method exists. A renumbered slice gets a new node and therefore new counts, as the arch accepts.

### D8 — Desired-state table shape
Status: decided
- `desired_states(id, project_id, node_id NULL REFERENCES nodes, drive INTEGER NULL, drive_until_step TEXT NULL, hold INTEGER NULL, message_id TEXT NOT NULL REFERENCES messages, updated_at)`. `drive` and `hold` are nullable booleans, and null means "not set at this target". The project target has `node_id` null. Two partial unique indexes enforce one row per target: `(project_id) WHERE node_id IS NULL` and `(node_id) WHERE node_id IS NOT NULL`. SQLite treats nulls as distinct, so a plain unique index cannot do this. `message_id` is the intent that last set the row, kept as provenance.
- Reads: `desired_state(project_id, *, node_id=None) -> DesiredState | None` and `desired_states(project_id) -> list[DesiredState]`. Resolving drive from the nearest target and hold from any target, up a node's path, is 124's lookup over these reads. A row on an orphaned node is still returned. Ignoring it is 124's rule.
- If 124's design finds the shape needs a field this table lacks, the plan's "Tables before their consumers" note applies. The change goes into 100's contract in 124, through a new migration.

### D9 — Nothing new on the feed
Status: decided
- Decision records, table versions, attempt counts, desired states, acknowledgments and closures add no `ChangeKind` or trigger. The arch says "nothing new on the wire". Node status changes and HUMAN-block escalations that a decision causes already reach the feed through the existing triggers. A project-scoped escalation's insert reaches it through `message_posted`.
- Consequence: a feed follower learns that a project-scoped escalation opened, but not that it closed. It reads the closure from `amoeba inspect messages` or `open_project_escalations`. Future Work records a closure change kind for when a subscriber needs it.

### Technology Choices

- No new dependencies. The store uses raw stdlib `sqlite3` and a hand-written numbered migration, as the 100 decision says.
- `ALTER TABLE messages ADD COLUMN` (five columns) is additive. Every column is nullable with no default, so existing rows read as "not set". SQLite applies it in place inside the migration's transaction.

### Patterns and Conventions

- Each statement and column is defined once, in `sql_runner.py`, and the migration's column names match it. The comment header follows migration 004's style.
- Types are frozen dataclasses, and vocabularies are `StrEnum`. A stored value outside a vocabulary raises `UnknownVocabularyValueError` on read.
- Writes that can be invalid validate before opening the transaction and raise typed errors. The new conditions, all added as rows to the "Failure modes" table in `docs/store-contract.md`:

  | Condition | Exception |
  | --- | --- |
  | A status write or block on a done node; issuing a journal entry against a done node; marking a node done while it has an unresolved entry (D1) | `InvalidTransitionError` |
  | Acknowledging a missing, non-intent or already acknowledged row; closing a missing, non-project or already closed escalation; a decision on an entry that is missing or in another project (D2, D4, D5) | `InvalidTransitionError` |
  | A malformed outcome, reason, desired state, decision field or fault kind (D2–D5) | `ValueError` |
  | A desired state or decision naming a node not in the project | `NodeNotFoundError` |
  | A second decision for one entry; a version stored with different content; a second open project escalation for one fault kind (D4–D6) | `StoreIntegrityError` |
- New public methods are in-process only: the read-write `Store`, which only `process/project_stores.py` opens. Every read also works through `Store.open_read_only`.

## Implementation Details

### Database / Storage Schema

Migration `009_runner_contract.sql`, with `EXPECTED_SCHEMA_VERSION` set to 9:

```sql
ALTER TABLE messages ADD COLUMN acknowledgment_outcome TEXT;
ALTER TABLE messages ADD COLUMN acknowledgment_reason TEXT;
ALTER TABLE messages ADD COLUMN fault_kind TEXT;
ALTER TABLE messages ADD COLUMN closed_at TEXT;
ALTER TABLE messages ADD COLUMN closed_by TEXT;

CREATE UNIQUE INDEX idx_messages_open_project_escalation
    ON messages (project_id, fault_kind)
    WHERE channel = 'escalation' AND fault_kind IS NOT NULL AND closed_at IS NULL;

CREATE TABLE routing_table_versions (version PK, content, first_used_at);
CREATE TABLE routing_decisions (
    id PK, project_id, node_id → nodes, journal_entry_id → command_journal NULL,
    inputs JSON, rule_id, table_version → routing_table_versions, amoeba_version,
    route, route_parameters JSON, attempt_step NULL, attempt_count NULL, decided_at);
CREATE UNIQUE INDEX ... ON routing_decisions (journal_entry_id) WHERE journal_entry_id IS NOT NULL;
CREATE INDEX ... ON routing_decisions (node_id, decided_at);
CREATE TABLE attempt_counts (node_id → nodes, step, count, updated_at, PK (node_id, step));
CREATE TABLE desired_states (... as D8 ...);
```

This sketch shows shape only. The task breakdown writes the real DDL with `NOT NULL` constraints and comments.

### API Contracts

Summary of the public store surface added or changed. These methods are added to `docs/store-contract.md` and the public-API list in `tests/test_public_api.py`.

| Method | Effect | Raises |
| --- | --- | --- |
| `update_node_status(node_id, status)` *(changed)* | As before, plus refuses a done node, and refuses `done` while the node has an unresolved entry. | `InvalidTransitionError` |
| `block(...)` *(changed)* | As before, plus a done node is refused. | `InvalidTransitionError` on a done node |
| `journal_issue(...)` *(changed)* | As before, plus a done node is refused. | `InvalidTransitionError` on a done node |
| `acknowledge_message(message_id, *, acknowledged_by, outcome, reason=None, desired_state=None)` *(changed)* | One transaction: acknowledgment and its outcome, plus the desired-state write. | `InvalidTransitionError` (as before), `ValueError` (D2, D3), `NodeNotFoundError` |
| `intent_for_submission(submission_id)` | The intent row a submission created, or `None`. | — |
| `raise_project_escalation(project_id, *, fault_kind, payload)` | The open row for the pair, existing or new. | `ValueError` on empty kind |
| `open_project_escalations(project_id)` | Open project-scoped rows, by `seq`. | — |
| `close_project_escalation(message_id, *, closed_by)` | Records the closure. | `InvalidTransitionError` |
| `desired_state(project_id, *, node_id=None)` / `desired_states(project_id)` | Current desired states. | — |
| `record_routing_decision(decision, *, table, effect, attempt_step)` | D5's single transaction. | `ValueError`, `NodeNotFoundError`, `InvalidTransitionError`, `StoreIntegrityError` |
| `routing_decision(id)` / `routing_decision_for_entry(entry_id)` / `routing_decisions(node_id)` | Decision reads. | — |
| `routing_table_version(version)` | The stored table, or `None`. | — |
| `attempt_count(node_id, step)` | The count, `0` when there is no row. | — |

`docs/inbox-contract.md` changes three places:
- **Learning the outcome:** add the intent acknowledgment read.
- **Reading messages:** add the project-scoped escalation row shape, and a note that `blocked_state_id` is null on a project-scoped escalation.
- The acknowledgment paragraph: add the outcome, and the desired-state transaction.

`amoeba inspect messages` rows gain `acknowledgment_outcome`, `acknowledgment_reason`, `fault_kind` and `closed_at`, each an empty string when unset, matching the existing columns.

## Integration Points

### Provides to Other Slices

- **122:** project-scoped escalation (raise, list open, close) for faults that have no node.
- **124:** `acknowledge_message` with an outcome and an atomic desired-state write, plus the desired-state reads that its path lookup walks.
- **125 / 126:** `record_routing_decision` with its node effect and attempt increment, `Route`, the table-version store, and `attempt_count`.
- **126 / 129:** the decision and table-version reads that make any decision recomputable.
- **127:** the done-terminal guarantee, and decision reads for the node it acts on. Store-only accept can use `record_routing_decision` with `route=advance` and a `StatusEffect(done)`. Whether it does is 127's choice.
- **128:** nothing dispatch-specific. The arch says the merge policy "is recorded on each dispatch decision". 128's design decides where that record lives: a routing decision record's `inputs` or `route_parameters`, or the `sq_run` journal parameters. Both are JSON and need no new field from this slice.
- **160 / notification bridge (later):** acknowledgment outcomes and open project escalations through `amoeba inspect messages` and `/v1/listings/messages`.

### Consumes from Other Slices

- 100's store, journal, block writer, migrations, inspection listings and contract suite, all unchanged in shape except as listed above.
- Nothing from 120. If 120 lands first, its contract text and this slice's sit in different sections of `docs/store-contract.md`.

## Success Criteria

### Functional Requirements

- `update_node_status` on a `done` node raises `InvalidTransitionError` for every `NodeStatus`. `block()` on a done node raises, and so does a `record_routing_decision` effect on a done node. The node is unchanged afterwards.
- `journal_issue` against a done node raises and writes nothing. Moving a node with an unresolved journal entry to `done` raises. The writer-inventory test fails if a module outside D1's table references `sql.UPDATE_NODE_STATUS`.
- `acknowledge_message` records each of the three outcomes. `rejected` without a reason raises and writes nothing. A second acknowledgment raises as before. `intent_for_submission` returns the acknowledged row with its outcome through a read-only handle.
- An `applied` acknowledgment with `SetDesiredState` writes the row in the same transaction. A forced failure of the desired-state write leaves the intent unacknowledged. `ClearDesiredState` deletes the row. A desired state with `no_op` or `rejected` raises.
- Raising a project-scoped escalation twice for the same project and fault kind yields one row. Raising it for a second fault kind yields a second row. After closing, raising again yields a new row. The schema's partial unique index refuses a second open row inserted by direct SQL in a test.
- `record_routing_decision` writes the version (first use only), the decision, the attempt increment and the effect together. An injected failure in any step leaves none of them. A second decision for the same journal entry raises. The same version with different content raises.
### Technical Requirements

- Migration `009` applies to a store stamped 8 that holds data from every earlier migration, and existing rows read back unchanged. A read-only open of a store at version 8 raises `StoreSchemaError`, as it does today.
- Every new statement and column name is defined once in `sql_runner.py`.
- `ruff check`, `ruff format --check` and `pyright` (strict) pass. New and changed modules stay under about 300 lines.
- `tests/test_public_api.py` lists the new public names, and the writer guard and store-safety tests pass unchanged.

### Integration Requirements

- 100's contract suite passes. The stand-in Runner acknowledges with `outcome=APPLIED`, and the oracle asserts the acknowledged intent's outcome.
- `docs/store-contract.md` and `docs/inbox-contract.md` document every method, vocabulary and row shape above. The `NodeStatus` table's "Terminal" entry states that terminal status is enforced.
- `amoeba inspect messages --json` shows the new columns.

### Verification Walkthrough

The Runner does not exist yet, so the demo exercises the store directly and through the existing CLI. Commands run from the project root.

1. **Suite and checks.**
   ```bash
   uv run pytest
   uv run ruff check && uv run ruff format --check && uv run pyright
   ```
   All pass. The new tests are in `tests/store/` (one module per area: terminal, acknowledgment, project escalation, routing decisions, desired state, migration 009) and in the extended contract suite.

2. **Terminal `done`, in a REPL** (`uv run python`):
   ```python
   from amoeba.store import Store, NodeKind, NodeStatus
   s = Store.open_temporary()
   n = s.create_node(project_id="demo", kind=NodeKind.SLICE, title="x")
   s.update_node_status(n.id, NodeStatus.DONE)
   s.update_node_status(n.id, NodeStatus.RUNNABLE)  # InvalidTransitionError naming the node
   ```

3. **Acknowledgment outcome, end to end through the inbox.** With a throwaway supervisor directory (`export AMOEBA_STORE_DIR=$(mktemp -d)`), start the process (`amoeba start`), then run `amoeba submit create-project --project demo --by operator` and `amoeba submit intent --project demo --by operator --body '{"hold": true}'`. Nothing in the shipped process acknowledges intents until 124, so the acknowledgment step is shown by the contract suite's stand-in Runner. Run `uv run pytest tests/contract -k acknowledg`. Then `amoeba inspect messages --project demo --json` against the temporary store shows the intent row with `acknowledgment_outcome` empty, which means not yet consumed.

4. **Project-scoped escalation dedup, in a REPL:**
   ```python
   m1 = s.raise_project_escalation("demo", fault_kind="plan_read_failed", payload={"error": "…"})
   m2 = s.raise_project_escalation("demo", fault_kind="plan_read_failed", payload={"error": "…"})
   assert m1.id == m2.id and len(s.open_project_escalations("demo")) == 1
   s.close_project_escalation(m1.id, closed_by="runner")
   assert s.open_project_escalations("demo") == []
   ```

5. **Recomputable decision:** `uv run pytest tests/store/test_routing_decisions.py -v`. This shows a decision recorded with its table version, read back by `routing_decision_for_entry`, and its table content retrieved by `routing_table_version`. It also shows the rollback cases.

6. **Migration on a real store:** copy an existing version-8 store file into a temporary directory and open it read-write with `Store.open(path=...)`. `amoeba inspect messages --project <id> --json` then shows the new columns empty on old rows, and the schema version reads 9. Do not point this at the central store.

## Implementation Notes

### Development Approach

Relative effort: 3/5. Suggested order, one commit per step:

1. Migration `009`, `sql_runner.py`, `runner_models.py`, mapping, and migration tests (applies on a populated v8 store, and the partial unique indexes behave).
2. Terminal `done` (D1): the checks in `_write_block`, `update_node_status` and `journal_issue`, and the writer-inventory test.
3. Acknowledgment outcome and `intent_for_submission` (D2). Update the stand-in Runner, oracle and message tests.
4. Desired state inside the acknowledgment (D3, D8).
5. Project-scoped escalation (D4).
6. Routing decisions, table versions and attempt counts (D5–D7).
7. Inspection columns. Contract documents. Public-API list.

Rollback tests inject a failure partway through a compound write. Existing store tests patch `_execute` to do this, and these tests follow the same pattern. They assert that nothing from the transaction landed.

### Special Considerations

- **Secrets.** Decision `inputs`, `route_parameters`, escalation payloads and table content are stored verbatim and shown by inspection. The contract text repeats the existing "callers must not place secrets in them" rule for each.
- **Sequencing with 120.** Both slices edit `docs/store-contract.md` and `store/journal.py`. 120 changes recovery's observers, and this slice changes `journal_issue`. Build after 120 merges, as the plan orders.
