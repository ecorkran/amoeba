---
docType: slice-design
slice: question-record
project: amoeba
parent: user/architecture/140-slices.question-answerer.md
dependencies:
- 127
- 132
interfaces:
- 142
- 143
- 144
dateCreated: 20261101
dateUpdated: 20261102
status: complete
turns: 30
promptTokens: 2591776
cachedTokens: 2452996
cacheWriteTokens: 138728
completionTokens: 33179
durationSeconds: 350.8
costUsd: 2.264542
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.2645417999999995
    completionTokens: 33179
---

# Slice Design: question-record

## Overview

Every agent question becomes a record in the project's store. Today a question exists only as the payload of the `HUMAN` block 132 writes. When the block is resolved, the question and its answer survive only as journal parameters, with nothing linking them. This slice adds a `question_records` table. 132's outcome ingest writes the record in the same transaction as the question's block. The PM's resolution of that block writes the PM's answer onto the record. A new answering stage in the Runner's tick settles every pending question. In this slice it always declines, because nothing answers yet. `amoeba inspect` shows the records.

Nothing the PM does changes. Every question still reaches the blocked list with the same text 132 showed, and the PM answers it the same way. The difference is a record beside each question that says what happened to it and why.

## Value

- **Architectural enablement.** 142 (gate and submission), 143 (source passages: PM answers are precedent) and 144 (answering run) all read and write this record. 141 fixes its states, its transitions and the rule for "answered by the PM" before anything depends on them.
- **For the PM.** `amoeba inspect questions` lists every question with its state, who answered it and the answer or the reason it was declined. `amoeba inspect blocked` shows each question's state beside the block.
- **For 160.** The declined state and the feed change for it give the notification bridge one event to notify on, instead of every question block.

## Technical Scope

Included:

- Migration `013`: the `question_records` table, its indexes, and feed triggers for two new `ChangeKind` members.
- Store vocabulary and models: `QuestionState`, `AnsweredBy`, `DeclineReason`, `QuestionRecord`, `QuestionCatch`, and the legal-transition table.
- Store operations: `record_question` (block and record in one transaction, idempotent per journal entry), `decline_question` (record-only update), the reads, and the PM-answer rule inside `acknowledge_resolution`.
- 132-owned ingest: the `QUESTION` outcome plan carries the question, and ingest writes the block through `record_question` instead of `block_once`.
- The answering stage (`amoeba.runner.answering`): a pure settle function and a store-only tick stage that declines pending questions.
- Project config: an optional `answerer` section. Its presence turns the answerer on. It has no keys in this slice.
- Inspection: a new `questions` listing, and question columns on `blocked`.
- Contract docs: `docs/store-contract.md`, `docs/feed-contract.md`, `docs/process-contract.md`.

Excluded:

- Answering a question, the `answering` transition's writer, and its columns (answering entry id, cited passages, check verdict): 144.
- The gate, the submission operation and the answerer's `answered` writer: 142.
- Configuration keys inside `answerer` (answer limit, reserved terms, rules paths and so on): 142 to 144.
- Backfill of questions already in the journal (arch, Current State).
- Notifications: 160.

## Dependencies

### Prerequisites

- **127 (resolutions and resumption)**, complete: `acknowledge_resolution`, the resolution slot's `decision` and `instructions`, and `pending_resolutions`.
- **132 (pipeline supervisor)**, complete: the `QUESTION` outcome class, `_question_block`, `ingest`, and `block_once`.
- **100's store**, complete: migrations, the block writer, the feed trigger convention and read-only inspection.
- Independent of 140 (answering pipeline). No Squadron or LLM dependency.

### Interfaces Required

- `RunCheckpoint.question` (`amoeba.process.sq_outcome`): the last 400 characters of the agent's reply, or null.
- `OutcomePlan` and `plan_supervised` (`runner/ingest/outcome.py`), and `ingest` (`runner/ingest/record.py`).
- `BlockWriter._write_block` and `_apply_effect`, and `acknowledge_resolution` (`store/blocking.py`).
- `ProjectSettings` (`runner/project_config.py`) and `ProjectTick` (`runner/tick.py`).
- The listing registry (`amoeba.inspection`). The server derives its routes from the registry, so `GET /v1/listings/questions` comes with it at no extra cost.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Question models | `store/question_models.py` | `QuestionState`, `AnsweredBy`, `DeclineReason`, `QUESTION_TRANSITIONS`, `QuestionCatch`, `QuestionRecord` |
| Question SQL and mapping | `store/sql_questions.py`, `store/mapping_questions.py` | Every statement and column name, and row mapping, following the `sql_*` and `mapping_*` pattern |
| Question operations | `store/questions.py` (mixin `QuestionOperations`) | `record_question`, `decline_question`, reads, and the internal `_settle_question_on_acknowledgment` |
| Migration | `store/schema/013_question_records.sql` | Table, indexes, feed triggers |
| Outcome plan | `runner/ingest/outcome.py` (132-owned) | `OutcomePlan.question` on the `QUESTION` branch, and the cut-off flag |
| Ingest | `runner/ingest/record.py` (132-owned) | Routes a question plan's block through `record_question` |
| Settle | `runner/answering/settle.py` | Pure: a pending record and its block's state to `Skip` or `Decline(reason)`, or raises `QuestionInvariantError` for a resolved block that does not await the Runner |
| Answering stage | `runner/answering/stage.py` | Store-only tick stage: reads pending records, applies the settle result |
| Project config | `runner/project_config.py` | `AnswererSettings` (empty in 141) and `ProjectSettings.answerer` |
| Listings | `inspection/questions.py`, `inspection/core.py` | `questions` rows, and question columns on `blocked` |

### Data Flow

**Catch (in ingest, one transaction).**

```
sq_run entry ends -> plan_supervised -> OutcomeClass.QUESTION
  OutcomePlan(block=HUMAN question block, question=QuestionCatch(run_id, step, text, truncated))
ingest -> store.record_question(catch, block_context, block_payload)
  BEGIN IMMEDIATE
    record exists for source_entry_id?  -> no-op (crash retry)
    node not blocked                    -> write HUMAN block + escalation, insert record (pending, blocked_state_id=new block)
    node already blocked                -> insert record (declined, node_already_blocked, blocked_state_id=NULL), no block
  COMMIT
ingest -> store.record_runner_report(...)   (unchanged)
```

**Settle (answering stage, after ingest, same tick).**

```
for record in store.pending_questions(project):            oldest first
  block = store.blocked_state(record.blocked_state_id)
  settle_pending(record, block, configured) ->
    block resolved, awaiting the Runner   -> Skip   (next tick's resolution stage settles it)
    block resolved, not awaiting          -> raise QuestionInvariantError   (unreachable by D2; see D5)
    question null or empty                -> Decline(question_missing)
    no answerer section                   -> Decline(answerer_not_configured)
    otherwise                             -> Decline(no_answer_on_file)     (144 replaces this branch)
  Decline -> store.decline_question(record.id, reason)
```

**PM answer (inside `acknowledge_resolution`'s transaction).**

```
resolution stage -> acknowledge_resolution(block B, outcome, effect)
  ... existing writes ...
  record R with blocked_state_id = B, R.state != answered?
    effect wrote a new block B'      -> R.blocked_state_id = B'         (stop, or any rejection; state unchanged)
    applied with no effect            -> R: answered, answered_by=pm, answer=B.resolution_instructions (may be null)
    any other acknowledgment          -> R unchanged
```

### State Management

All state lives in the project's store. Nothing is held in process memory between ticks.

```
            ┌─────────────── answered (pm) ◄───────────────┐
            │                                               │
pending ────┼──► answering ──► answered (answerer | pm)     │
            │        │                                      │
            └────────┴──► declined ─────────────────────────┘
```

| From | To | Writer | Slice |
| --- | --- | --- | --- |
| (insert) | `pending` | `record_question`, block written | 141 |
| (insert) | `declined` | `record_question`, node already blocked | 141 |
| `pending` | `declined` | `decline_question` | 141 |
| `pending`, `declined` | `answered` (pm) | `acknowledge_resolution` | 141 |
| `pending` | `answering` | 144's launch | 144 |
| `answering` | `declined` | `decline_question` | 141 op, 144 caller |
| `answering` | `answered` (pm) | `acknowledge_resolution` | 141 |
| `pending`, `answering` | `answered` (answerer) | 142's submission operation | 142 |

`answered` is terminal. Any other transition raises `InvalidTransitionError`, and the whole transaction rolls back.

## Technical Decisions

### D1 — The record is written in the block's transaction, keyed by its journal entry

Status: decided

- A new store operation, `record_question`, writes the `HUMAN` block (through `_write_block`, so the escalation message is written with it) and inserts the record under one `BEGIN IMMEDIATE`. Ingest calls it in place of `block_once` when the plan carries a question. This satisfies the plan's crash criterion directly: the block and the record land together or not at all.
- `source_entry_id` (the `sq_run` journal entry whose run ended on the question) is `UNIQUE`. When a record already exists for the entry, the operation writes nothing and returns that record. This is ingest's existing retry: a crash after this transaction and before `record_runner_report` leaves the entry unresolved, the next tick polls and ingests again, and nothing is written twice.
- When the node is already blocked, no block is written (as today) and the record is inserted `declined` with `node_already_blocked` and a null `blocked_state_id`. The record is not linked to the other block. If it were, a PM answer to that unrelated block would be recorded as this question's answer.
- **When `record_question` raises, ingest fails the same way it does today.** The errors are `NodeNotFoundError` or `InvalidTransitionError`, the same ones `block_once` raises for the same node states, since both write through `_write_block`. Ingest does not catch them. The exception reaches the Runner's tenant boundary with the node in context. The node has an unresolved `sq_run` entry, so 122's `escalate` raises a per-project escalation, deduplicated on (project, kind). The entry stays unresolved and is ingested again on the next tick, so the question is retried, never dropped. A done node cannot occur here, because the store refuses `done` while the node has an unresolved entry.
- **One behaviour change to 132's path.** Suppose the PM resolves the question's block between the crash and the retry. Today the retry would write a second block. With a record already present for the entry, it writes nothing. The question has already been caught, so this is the intended result.
- **Rejected:** writing the record in `record_runner_report`'s transaction. The block would then precede the record in a separate transaction, and recovery would need a "find blocks without records" scan. Also rejected: a scan of open question blocks every tick. That repairs a gap D1 never leaves.

### D2 — "Answered by the PM" is decided inside `acknowledge_resolution`, from the record

Status: decided

- The PM's answer is recorded when the Runner acknowledges a resolution of the question's block, in the same transaction. It is not recorded when the inbox fills the slot, because a resolution the Runner rejects answered nothing.
- **The rule, using store facts only.** Find the record whose `blocked_state_id` is the acknowledged block. If there is none, or its state is `answered`, do nothing. If the acknowledgment's effect wrote a new block (a `stop`, or any rejection, both of which re-block in 127's design), move the record's `blocked_state_id` to the new block and keep its state. If it is applied with no effect, it is an applied resume that unblocked the node: mark the record `answered`, `answered_by=pm`, `answer=` the slot's `resolution_instructions`. Any other acknowledgment leaves the record unchanged.
- **Following the block keeps the question alive across a typo or a stop.** If the PM's first resolution is rejected (`unknown_decision`) or is a `stop`, the PM's later resume of the new block still answers this question.
- **A resume without instructions** marks the record `answered` by the PM with a null `answer`. A null answer is not precedent; 143 reads only PM answers with text. This keeps "the PM settled it" separate from "the PM gave an answer" without adding a fifth state.
- **The answerer is never mistaken for the PM.** 142's submission operation marks the record `answered` (answerer) in the same transaction that fills the slot, so when the Runner acknowledges, the record is already `answered` and the rule does nothing. The submission's `submitted_by` (`resolved_by`) is never read. The store does not read the decision text either. "Applied with no effect" is structural, so the store does not depend on the Runner's decision vocabulary.
- **The structural rule is exactly the arch's "resolved by a resume".** Since slice 132, `ResolutionDecision` has two members, `resume` and `stop`. The judge's acknowledgments are:
  - an applied `resume`, with no effect, which unblocks the node;
  - an applied `stop`, with a `BlockEffect`, which re-blocks it;
  - a rejection of any decision, with a `BlockEffect`, which re-blocks it.
  So the only acknowledgment that unblocks is an applied `resume`. The judge never produces a `StatusEffect`, and no decision unblocks without resuming. The acknowledgment-shape test (Mitigation Strategies) asserts this list. It also asserts that an applied acknowledgment with a `StatusEffect`, the one non-resume way to unblock that the store accepts, leaves the record unchanged. That is why D2's write is guarded on "applied, no effect".
- `_apply_effect` returns the id of the block it wrote, or `None`, so the acknowledgment knows whether a new block exists. This is internal; no public signature changes.
- **"PM answered first" is `answered_by = pm`, not a decline.** When the PM wins a race with the answerer, the acknowledgment has already marked the record `answered` (pm), or will on the next tick if the PM's resolution is still waiting for the Runner. That value is the note the arch and slice plan call "PM answered first". There is no `pm_answered_first` decline reason and no record-only note. When an answering run ends against an `answered` record, 144 discards the result and writes nothing to the record. When 142's submission finds the block already resolved, it rejects and leaves the record for the acknowledgment to settle. `answered` therefore stays terminal.
- **Rejected:** settling in the answering stage when it finds the block resolved, as the arch's step 2 suggested. At that point the stage cannot tell an applied resolution from one the Runner will reject. The stage now skips that record, and the acknowledgment settles it. The arch's outcome holds: the record is marked answered by the PM and no run starts. The arch's steps 2 and 7 are updated to say this.

### D3 — The store owns the question vocabularies, all closed

Status: decided

- `QuestionState` (`pending`, `answering`, `answered`, `declined`), `AnsweredBy` (`answerer`, `pm`) and `DeclineReason` are `StrEnum`s in `store/question_models.py`. An unknown stored value raises `UnknownVocabularyValueError`, as every other store vocabulary does.
- `DeclineReason` in 141: `node_already_blocked`, `question_missing`, `answerer_not_configured`, `no_answer_on_file`. 142 to 144 add their members (answer limit, reserved term, sources too large, the answering-run failures). The store owns the vocabulary because `record_question` itself declines with `node_already_blocked`. One definition site is better than splitting codes between the store and the Runner.
- `QUESTION_TRANSITIONS: Mapping[QuestionState, frozenset[QuestionState]]` is the single statement of D2's state table. Every writer checks it under the write lock.

### D4 — The cut-off flag measures Squadron's tail limit

Status: decided

- Squadron reports `checkpoint.question` as the last 400 characters of the reply. When the text reaches that length, its start was probably cut. `truncated = len(question) >= QUESTION_TAIL_CHARS`, computed on the raw text before 132's byte bound.
- `QUESTION_TAIL_CHARS: Final = 400` is defined once in `amoeba/process/sq_outcome.py`, beside the `question` field, as upstream shape knowledge. The process contract's "Squadron shapes" section records it.
- A reply of exactly 400 characters is a false positive. That is acceptable, because the flag only measures how common truncation is (plan Future Work 1) and nothing branches on it.
- A null question gets `truncated = false`.

### D5 — The 141 answering stage is store-only, settles before the cut-off return, and escalates per project

Status: decided

- **Placement.** In `ProjectTick.run`, the stage runs after `record_finished` and the `shape_error` check, and before the `CUT_OFF` return. So a question caught this tick is settled this tick, even when the probes ran out of budget. It starts no subprocess, so like the resolution stage it takes no budget. 144 adds the budget check for launches.
- **Order.** It reads `pending_questions(project_id)`, oldest first. Each record goes through `settle_pending` (pure), then `decline_question` if the result is `Decline`. A `Skip` writes nothing.
- **Check order inside `settle_pending`.** Block state first: a question the PM is already answering must not be declined and announced, so a resolved block that awaits the Runner is skipped. A resolved block that does not await the Runner cannot happen: an applied resume marks the record `answered` in the acknowledgment's transaction (D2), and a stop or rejection re-points the record to the new open block. If it is ever seen, `settle_pending` raises `QuestionInvariantError` instead of declining, so a broken invariant escalates per project and is not hidden behind a decline reason that 142 to 144 and 160 would inherit. Then a null question. Then configuration. Then `no_answer_on_file`. 144 replaces only the last branch, with the launch.
- **Fault isolation.** The stage leaves the node context cleared. An exception therefore escalates per project, which the store deduplicates. If the context were the node, 122's `escalate` would see a node already blocked on a human and write nothing, and the fault would be lost.
- **Rejected:** declining inside `record_question`. Declining belongs to the stage that 144 grows, and a separate stage keeps the store free of configuration.

### D6 — An `answerer` section, empty in 141, turns the answerer on

Status: decided

- `ProjectSettings.answerer: AnswererSettings | None`. `AnswererSettings` is a frozen pydantic model with `extra="forbid"` and no fields in 141. A project whose entry has `answerer: {}` is configured. A project with no `answerer` key, or not named in the file, is not.
- An explicit `answerer:` with a null value is a load error ("answerer must be a mapping; write `{}`"). Without this, a section written but left empty would quietly turn the answerer off.
- 142 adds the answer limit and reserved terms as required keys, so `answerer: {}` stops loading from 142 on. That is the plan's rule that configuration lands where it is first read. 141 first reads only whether the section exists.
- **Rejected:** treating every project as unconfigured until 142. That would make `no_answer_on_file` unreachable and untested.

### D7 — Question changes are on the feed

Status: decided

- Two `ChangeKind` members, written by triggers in `013` per the trigger convention:
  - `question_recorded` on insert. `node_id` is the slice and `subject_id` the record id. Payload: `state`, `decline_reason`.
  - `question_state_changed` on update, only when `state` changes. Payload: `from`, `to`, `answered_by`, `decline_reason`.
- A re-point (D2) changes no state and emits nothing.
- The plan names 141 as the point 160's notification bridge attaches to. Without these kinds, 160 would need a store change of its own to see a decline. The feed invariant test gains the two steps.

### D8 — Listings: `questions` is new, and `blocked` gains two columns

Status: decided

- `questions` is project-scoped. Columns: `id`, `node_id`, `run_id`, `step`, `state`, `answered_by`, `question`, `outcome`, `truncated`, `created_at`. `outcome` is the answer when the state is `answered` and the decline reason when it is `declined`. Options: `--node`, the shared `NODE_OPTION`, and `--state`, a `ChoiceOption` over `QuestionState`.
- `--json` and the server also carry `blocked_state_id`, `source_entry_id` and `updated_at`.
- `blocked` gains `question_state` and `decline_reason`, joined on `blocked_state_id`. Both are empty for a block with no question. The JSON row also carries `question_id`. The existing columns and `payload` are unchanged, so the question text appears exactly as 132 showed it.

### Technology Choices

- Stdlib `sqlite3` through the existing store plumbing, a hand-written numbered migration, and pydantic for the config section, all as existing slices do. Nothing new is added.

### Patterns and Conventions

- Every SQL statement and column name lives in `sql_questions.py`. The migration's column names match them, and so do the `ChangeKind` literals in the triggers (the invariant test ties them together).
- Store writes are one method, one transaction, `BEGIN IMMEDIATE` before the first read that decides a write.
- `settle_pending` is pure and imports no store write. `tests/runner/purity.py` covers it as it covers the other pure modules.
- Reasons and states are only ever compared through their enums. No literal strings appear in Runner code.

## Implementation Details

### Database / Storage Schema

Migration `013_question_records.sql`, schema version 13:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PK | `new_id()` |
| `project_id` | TEXT NOT NULL | |
| `node_id` | TEXT NOT NULL → `nodes(id)` | The slice node of the `sq_run` entry |
| `source_entry_id` | TEXT NOT NULL UNIQUE → `command_journal(id)` | D1's idempotency key |
| `run_id` | TEXT NOT NULL | The paused Squadron run |
| `step` | TEXT | Bounded, as in the block payload |
| `question` | TEXT | Bounded; null when Squadron sent none |
| `truncated` | INTEGER NOT NULL | `0` or `1` (D4) |
| `blocked_state_id` | TEXT → `blocked_states(id)` | Null only when declined `node_already_blocked`; moved by D2 |
| `state` | TEXT NOT NULL | `QuestionState` |
| `answered_by` | TEXT | `AnsweredBy`; set exactly when `state = answered` |
| `answer` | TEXT | The PM's instructions, or the answerer's answer (142); may be null for a PM answer |
| `decline_reason` | TEXT | `DeclineReason`; set when declined, and kept if the PM answers afterwards |
| `created_at`, `updated_at` | TEXT NOT NULL | ISO-8601, as elsewhere |

Indexes:

- A unique partial index on `blocked_state_id WHERE blocked_state_id IS NOT NULL`: a block carries at most one question.
- `(project_id, state, created_at)`, which serves `pending_questions`.
- `(node_id)`.

Triggers per D7. No backfill. 144 adds its own columns by a later migration.

### API Contracts

Store (`docs/store-contract.md`, a new section "Question records"):

| Method | Effect |
| --- | --- |
| `record_question(catch, *, block_context, block_payload) -> QuestionRecord` | In-process only. **One transaction** (D1). `catch: QuestionCatch(project_id, node_id, source_entry_id, run_id, step, question, truncated)`. The block kind is always `HUMAN`. An existing record for `source_entry_id` is returned unchanged. A missing node raises `NodeNotFoundError`; a done node raises `InvalidTransitionError`. |
| `decline_question(question_id, *, reason) -> QuestionRecord` | In-process only. Record-only. `pending` or `answering` → `declined`. Any other state raises `InvalidTransitionError`. |
| `question(question_id)` | One record, or `None`. |
| `questions(project_id, *, state=None, node_id=None)` | Records, oldest first. |
| `pending_questions(project_id)` | `questions(state=pending)`, through the state index. |
| `question_for_block(blocked_state_id)` | The record linked to a block, or `None`. |
| `acknowledge_resolution(...)` | Unchanged signature. Adds D2's settle in its existing transaction. |

All reads work through a read-only handle.

Project config (`docs/process-contract.md`, "The project config"):

```yaml
projects:
  amoeba:
    pipeline: p456
    answerer: {}        # on; keys arrive with 142-144
```

Inspection: `amoeba inspect questions --project P [--node ID] [--state STATE] [--json]`, and `GET /v1/listings/questions?project=P` through the registry.

## Integration Points

### Provides to Other Slices

- **142 (gate and submission):** the record, `QUESTION_TRANSITIONS`, and the run's questions and answers, read from `questions(node_id=…)` filtered on `run_id`, for the answer limit. 142's operation must set `answered` (answerer) in the transaction that fills the slot, which is what makes D2 skip it. 142 also decides what an `answered` (answerer) record means when the Runner later rejects that resolution. 141's rule leaves such a record unchanged. A block already resolved is rejected with the record left to the acknowledgment (D2). The matched reserved term goes in a column 142 adds by its own migration; 141 stores only the reason code.
- **143 (source passages):** PM precedent is `answered_by = pm AND answer IS NOT NULL`, with `node_id` for the slice and `updated_at` for the passage date.
- **144 (answering run):** the `pending → answering` transition (144 adds its writer and columns), `decline_question` for every failure, a discard that writes nothing when the run ends against an `answered` record (D2), `settle_pending`'s last branch to replace, and the stage's place in the tick.
- **160 (notification bridge):** `question_recorded` and `question_state_changed` on the feed, and `decline_reason` on `blocked` rows.

### Consumes from Other Slices

- **132:** the `QUESTION` outcome and its block. The block's context and payload are unchanged. If a future change to 132 stops blocking questions as `HUMAN`, D1's operation must change with it. The arch fixes `HUMAN`.
- **127:** `acknowledge_resolution` and the rule that every rejection and every `stop` re-blocks. A future acknowledgment that neither re-blocks nor unblocks would fall outside D2. The store test that lists the acknowledgment shapes would catch it.

## Success Criteria

### Functional Requirements

- A question-paused run produces one `HUMAN` block, with context and payload byte-identical to 132's, and one `pending` record linked to its project, slice, run, step, entry and block. In the same tick the answering stage declines it, and the blocked list shows the same text 132 showed.
- A question on an already-blocked node produces a record declined `node_already_blocked`, with no block and no link.
- A null question is declined `question_missing`.
- A project with no `answerer` section declines every question `answerer_not_configured`. One with `answerer: {}` declines `no_answer_on_file`. `answerer:` set to null fails at load.
- A PM resolution submitted before the stage runs: the stage skips the record, the next resolution stage applies the resolution, and the record becomes `answered` by the PM. No decline is written.
- A PM resume with instructions on a question's block, pending or declined, marks the record `answered`, `answered_by=pm`, `answer=` the instructions verbatim. A resume without instructions marks it answered by the PM with a null answer.
- A rejected PM resolution, or a `stop`, moves the record to the new block with its state unchanged. A later resume with instructions on that block answers the question.
- A record already `answered` (answerer) is left untouched by an applied PM-shaped resume. A resume submitted with `submitted_by` set to the answerer's name, on a declined record, is recorded as the PM's. Both cases show that the rule reads the record, not the string.
- `amoeba inspect questions` lists records with state, question, answerer and outcome. `--state declined` filters. `amoeba inspect blocked` shows `question_state` and `decline_reason`.

### Technical Requirements

- `QUESTION_TRANSITIONS` is the only statement of legal transitions. A test walks every (from, to) pair through the writers, and every illegal transition raises `InvalidTransitionError` and writes nothing.
- Crash safety: the crash harness kills between `record_question` and `record_runner_report`. The retry writes no second record and no second block, and the entry resolves. A kill inside `record_question` leaves neither the block nor the record.
- The feed invariant test covers both new kinds. A re-point emits nothing.
- The migration test covers 12 → 13 on a store with existing blocked states. A read-only open of a version-12 store raises `StoreSchemaError`.
- `settle_pending` passes the purity check. Format, lint, typecheck and the store, runner, inspection and serve suites pass.
- Docs: a "Question records" section in the store contract, and the latest-migration paragraph moved to `013`. Two kinds in the feed contract's table and coverage list. The `answerer` section and `QUESTION_TAIL_CHARS` in the process contract. The substrate guide's 120 row mentions the record.

### Integration Requirements

- 142 and 143 can be designed against the API Contracts table without reading 141's code.
- After 141, a PM who never uses `inspect questions` sees no difference: the same block, the same payload, the same resolution path and the same run behaviour.

### Verification Walkthrough

Steps 1–4 use the stub `sq` harness in `tests/`. Steps 5–7 run against a throwaway `AMOEBA_STORE_DIR` with a scratch project, as in 132's walkthrough. The `questions` listing, the `-k question` crash case and the `tests/store/test_question_*.py` modules are new in this slice. `test_end_to_end.py` and `test_crash_recovery.py` exist today.

1. **Catch and decline (stub).** `pytest tests/runner/test_end_to_end.py -k agent_question`. Expected: the existing test passes unchanged (the block, then the resume with instructions verbatim). The extended assertions show one record that goes `pending → declined (answerer_not_configured) → answered (pm)` with `answer` equal to the instructions.
2. **Crash retry (stub).** `pytest tests/runner/test_crash_recovery.py -k question`. Expected: after the kill between the record and the report, the restarted tick resolves the entry with one block and one record.
3. **Rule from the record.** `pytest tests/store/test_question_acknowledgment.py`. Expected: cases for an applied resume with instructions, an applied resume without instructions, a stop, a rejection, an already-`answered` record and a resume submitted as the answerer's name, each passing.
4. **Transitions.** `pytest tests/store/test_question_records.py -k transition`. Expected: every illegal pair raises.
5. **Real store: a question appears.** Drive a stub-run question-paused slice into a throwaway `AMOEBA_STORE_DIR` (the `Scenario` rig in `tests/runner/test_end_to_end.py` does this: stub `sq` and `cf`, a 430-character question, `tick_until` the node blocks). Then, with `AMOEBA_STORE_DIR` set to that directory:

   ```
   amoeba inspect blocked --project demo
   ```

   Observed: one row, `blocked_on human`, `reason agent_question`, `context question at design-0, run <id>`, `question_state declined`, `decline_reason answerer_not_configured`.

   ```
   amoeba inspect questions --project demo
   ```

   Observed: one row, `step design-0`, `state declined`, `answered_by` empty, `question` the full text, `outcome answerer_not_configured`, `truncated true` (the question is over 400 characters).
6. **Turn it on.** `answerer: {}` under the project in `projects.yaml` loads as configured (`load_project_config(...).for_project("demo").answerer` is an `AnswererSettings`); the tick test `test_an_empty_answerer_section_declines_no_answer_on_file` (`tests/runner/test_tick_answering.py`) shows the record's `outcome no_answer_on_file`. With `answerer:` and no value, `amoeba start --project-config projects.yaml` exits 7 and prints `projects.demo.answerer: Value error, answerer must be a mapping; write `{}` (got None)`. Do not run `amoeba start` with a valid config in this walkthrough: it starts the resident process and does not return.
7. **PM answers.** Submit the PM's resolution of the question's block, then let the Runner tick. The resolution is applied through `store.apply_submission` (the call the inbox makes), because `amoeba submit resolution` only writes an inbox file and needs the resident process running to apply it. With a running process, the same effect comes from:

   ```
   amoeba submit resolution --project demo --by pm --blocked-state-id <id> \
     --detail answered --decision resume --instructions "Use the target branch."
   ```

   After the next tick, `amoeba inspect questions --project demo --json` shows `state answered`, `answered_by pm`, `outcome "Use the target branch."`. (The listing's `outcome` carries the answer; the `answer` column of the store is the same text.) `amoeba feed --project demo` shows, in order: `question_recorded` (`state pending`), `question_state_changed` (`pending` to `declined`, `decline_reason answerer_not_configured`), then `question_state_changed` (`declined` to `answered`, `answered_by pm`, `decline_reason` kept).

## Risk Assessment

### Technical Risks

- **Two edits to transactions other slices own.** Ingest's block write moves into `record_question`, and `acknowledge_resolution` gains a step. A mistake in either can block a slice wrongly or refuse a PM's resolution.
- **D2 relies on 127's acknowledgment shapes.** Today the only acknowledgment that unblocks is an applied `resume`. A later decision that unblocks without resuming would need its own rule.

### Mitigation Strategies

- 132's and 127's existing tests run unchanged, and the block payload is compared byte for byte.
- A store test lists every acknowledgment shape the judge produces (applied `resume`, applied `stop`, a rejection) and asserts D2's result for each. It also covers an applied `StatusEffect`, which leaves the record unchanged. A new shape fails it.

## Implementation Notes

### Development Approach

1. Models, migration `013`, the SQL and mapping modules, reads, `decline_question` and the transition table, with store tests and the migration test.
2. `record_question`, with store tests for the three branches and the retry.
3. The D2 settle in `acknowledge_resolution` and the `_apply_effect` return value, with the acknowledgment-shape test.
4. The outcome plan's `question`, `QUESTION_TAIL_CHARS`, and ingest's routing, with the end-to-end and crash tests.
5. `AnswererSettings`, `settle_pending`, the stage and its place in the tick, with tick tests for each decline, for the skip, and for the invariant error (a resolved block that does not await the Runner raises, and the stage escalates per project).
6. Feed kinds and triggers, with the invariant test.
7. Listings, then the contract docs.

Relative effort: 3.

### Special Considerations

- Question text is agent output. It is stored bounded, as 132 bounds it, and is never interpreted. The feed payloads carry no question or answer text, so the feed stays small and keeps its rule that payloads are never the whole record.
- The question record is per project, like every other table. No query crosses projects.
