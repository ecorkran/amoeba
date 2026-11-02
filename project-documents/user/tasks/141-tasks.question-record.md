---
docType: tasks
slice: question-record
project: amoeba
lld: user/slices/141-slice.question-record.md
dependencies:
- 127
- 132
projectState: Slices 120–132 are merged, and 140 (answering pipeline) is built but
  blocked on squadron#284. The store is at schema version 12. Question pauses write
  a HUMAN block through block_once in ingest, and nothing records the question. Nothing
  of slice 141 is built.
dateCreated: 20261101
dateUpdated: 20261102
status: in_progress
turns: 35
promptTokens: 1315332
cachedTokens: 1240107
cacheWriteTokens: 75185
completionTokens: 21108
durationSeconds: 143.6
costUsd: 0.636205
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.6362041
    completionTokens: 21108
revision_number: 2
---

## Context Summary

- Working on the **question-record** slice (141) of the question-answerer initiative (140 architecture). Every agent question becomes a `question_records` row, written in the same transaction as 132's `HUMAN` block. The PM's resume writes the PM's answer onto it. A new store-only answering stage declines every pending question. `amoeba inspect` shows the records.
- **Current state:** see `projectState`.
- **Dependencies:** 127 (`acknowledge_resolution`) and 132 (`QUESTION` outcome, `ingest`, `block_once`), both merged. No Squadron or LLM dependency.
- **What this slice delivers:** migration `013`; question vocabularies and models; `record_question`, `decline_question` and the reads; D2's PM-answer rule inside `acknowledge_resolution`; the `QUESTION` plan carrying the question; `AnswererSettings`; `settle_pending` and the answering stage; two feed kinds; the `questions` listing and two `blocked` columns; contract docs.
- **Next planned work:** 142 (gate and submission), 143 (source passages), 144 (answering run), 160 (notification bridge).

**Branch:** all implementation happens on `141-slice.question-record`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/141-slice.question-record.md` at the named decision (D1–D8), "Architecture", "Implementation Details" or "API Contracts". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/`, `docs/` or `project-documents/`. Keep every new or changed source file near 300 lines and each function near 50.

**Order and dependencies:** work tasks in file order. Each task leaves the full suite passing and the resident process starting.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and run lint and typecheck (`uv run ruff check .`, `uv run pyright`) before the markers that follow source changes.

**Task-level facts** (checked against the code on 20261101; each resolves a placement, not a product decision):
- `runner/answering/` already exists (140's pipeline artifacts). The settle function and stage are added beside them. Tests go in `tests/runner/answering/`.
- Store tests live in `tests/store/`, with `test_migration_012.py` as the migration-test pattern and `test_feed_invariant.py` and `test_feed_triggers.py` for the feed.
- Inspection tests live in `tests/inspection/`; tick tests in `tests/runner/` (`test_tick*.py`, helpers `tick_support.py`); ingest tests in `tests/runner/ingest/`; the end-to-end and crash tests are `tests/runner/test_end_to_end.py` and `tests/runner/test_crash_recovery.py`.

---

## 1. Branch and baseline

- [x] **1.1 Create the slice branch and record the baseline**
  - [x] Run `cf config get git.integration_branch`. The result (or `main` if empty) is the target. Confirm you are on the target.
  - [x] Run `git checkout -b 141-slice.question-record {target}`.
  - [x] Run `uv run pytest -q`, `uv run ruff check .` and `uv run pyright` once. Note any failures that exist before this slice.
  - [x] Success: on branch `141-slice.question-record`, and the baseline result is known.

---

## 2. Models, migration and store reads

- [x] **2.1 Question vocabularies and models** (`store/question_models.py`)
  - [x] Add `StrEnum`s `QuestionState` (`pending`, `answering`, `answered`, `declined`), `AnsweredBy` (`answerer`, `pm`) and `DeclineReason` (`node_already_blocked`, `question_missing`, `answerer_not_configured`, `no_answer_on_file`), per LLD D3.
  - [x] Add `QUESTION_TRANSITIONS: Mapping[QuestionState, frozenset[QuestionState]]` encoding the LLD State Management table (`answered` terminal; `declined` reaches only `answered`).
  - [x] Add frozen models `QuestionCatch(project_id, node_id, source_entry_id, run_id, step, question, truncated)` and `QuestionRecord` with every column in the LLD schema table.
  - [x] Unknown stored values raise `UnknownVocabularyValueError`, as other store vocabularies do (follow an existing models module for the pattern).
  - [x] Success: module imports, and typecheck passes.

- [x] **2.2 Migration 013** (`store/schema/013_question_records.sql`)
  - [x] Create `question_records` with the LLD columns, the foreign keys and `source_entry_id UNIQUE`.
  - [x] Add the three indexes: unique partial on `blocked_state_id WHERE blocked_state_id IS NOT NULL`; `(project_id, state, created_at)`; `(node_id)`.
  - [x] Register schema version 13 wherever versions are listed (follow how `012` was registered in `store/migrations.py`).
  - [x] Add the feed triggers in the same file, so `013` is written once: `question_recorded` (on insert; `node_id` the slice, `subject_id` the record id; payload `state`, `decline_reason`) and `question_state_changed` (on update only when `state` changes; payload `from`, `to`, `answered_by`, `decline_reason`), per LLD D7. Add both to `ChangeKind`, following the trigger convention of earlier migrations; the literals must match. Payloads carry no question or answer text.
  - [x] Success: a fresh store opens at version 13 and has both triggers.

- [x] **2.3 Store reads and `decline_question`** (`store/sql_questions.py`, `store/mapping_questions.py`, `store/questions.py`, mixin `QuestionOperations`)
  - [x] Follow the `sql_*` and `mapping_*` pattern: every statement and column name in `sql_questions.py`, and row-to-`QuestionRecord` mapping (including `truncated` 0/1 to bool) in `mapping_questions.py`. Later tasks add the statements they need.
  - [x] Add reads `question`, `questions(project_id, *, state=None, node_id=None)`, `pending_questions` and `question_for_block`. All must work on a read-only handle.
  - [x] Add `decline_question(question_id, *, reason)`: one `BEGIN IMMEDIATE` transaction, checks `QUESTION_TRANSITIONS`, raises `InvalidTransitionError` for any other state and writes nothing, sets `decline_reason` and `updated_at`.
  - [x] Add the mixin to the `Store` class.
  - [x] Success: the operations are callable from `Store`, and no SQL text exists outside `sql_questions.py`.

- [x] **2.4 Tests for models, migration, reads and decline**
  - [x] `tests/store/test_migration_013.py`, following `test_migration_012.py`: migrate 12 → 13 on a store that has blocked states; a read-only open of a version-12 store raises `StoreSchemaError`.
  - [x] Add the two new kinds to the feed invariant test (`tests/store/test_feed_invariant.py`) so it passes with the triggers from Task 2.2.
  - [x] `tests/store/test_question_records.py`: unknown vocabulary value raises; `decline_question` from `pending` succeeds and from `answered` raises `InvalidTransitionError` leaving the row unchanged (the full transition walk waits for Task 4.2, when all of 141's writers exist); the reads filter by state and node and return oldest first; a read-only handle can call the reads.
  - [x] Insert test rows through a small helper in the test module (not through `record_question`, which does not exist yet).
  - [x] Success: the new tests pass, and the store suite passes.

**Commit**: `feat: add question_records table, models and store reads`

---

## 3. `record_question`

- [x] **3.1 Implement `record_question`** (`store/questions.py`)
  - [x] Signature per the LLD API Contracts: `record_question(catch, *, block_context, block_payload) -> QuestionRecord`.
  - [x] Under one `BEGIN IMMEDIATE`: if a record exists for `source_entry_id`, return it and write nothing. If the node is not blocked, write the `HUMAN` block through `_write_block` (so the escalation message is written with it) and insert the record `pending` with `blocked_state_id` set to the new block. If the node is already blocked, insert the record `declined` with `node_already_blocked` and a null `blocked_state_id`, writing no block.
  - [x] A missing node raises `NodeNotFoundError`; a done node raises `InvalidTransitionError` (the same errors `block_once` raises). Do not catch them.
  - [x] Success: one method, one transaction, no SQL outside `sql_questions.py`.

- [x] **3.2 Tests for `record_question`** (`tests/store/test_question_record_catch.py`)
  - [x] Unblocked node: one `HUMAN` block, one `pending` record linked to it, and the block's context and payload stored exactly as passed.
  - [x] Already-blocked node: a `declined` record with `node_already_blocked`, null `blocked_state_id`, and no second block.
  - [x] Retry with the same `source_entry_id`: returns the existing record, with no second record and no second block, including after the first block has been resolved.
  - [x] Missing node raises `NodeNotFoundError`; done node raises `InvalidTransitionError`; in both cases nothing is written.
  - [x] Failure inside the transaction (use `tests/fault_injection.py` as other store tests do) leaves neither block nor record.
  - [x] Success: all cases pass.

**Commit**: `feat: add record_question writing block and record in one transaction`

---

## 4. PM answer rule in `acknowledge_resolution`

- [x] **4.1 `_settle_question_on_acknowledgment`** (`store/questions.py`, called from `acknowledge_resolution` inside its existing transaction)
  - [x] Change `_apply_effect` (`store/blocking.py`) to return the id of the block it wrote, or `None`. No public signature changes.
  - [x] Per LLD D2: find the record by `question_for_block`-style lookup on the acknowledged block. No record, or state `answered`: do nothing.
  - [x] If the effect wrote a new block: set the record's `blocked_state_id` to it and keep its state; emit no state change.
  - [x] If the acknowledgment is applied with no effect: set `answered`, `answered_by=pm`, `answer=` the slot's `resolution_instructions` verbatim (may be null). Check `QUESTION_TRANSITIONS`; keep `decline_reason`.
  - [x] Any other acknowledgment (including an applied `StatusEffect`): leave the record unchanged.
  - [x] Never read `submitted_by`/`resolved_by` or the decision text.
  - [x] Success: `acknowledge_resolution` keeps its signature and is still one transaction.

- [x] **4.2 Acknowledgment-shape and transition tests** (`tests/store/test_question_acknowledgment.py`, `tests/store/test_question_records.py`)
  - [x] Applied resume with instructions on a `pending` record and on a `declined` record: `answered`, `pm`, answer verbatim.
  - [x] Applied resume without instructions: `answered`, `pm`, null answer.
  - [x] Applied `stop`: `blocked_state_id` moves to the new block, state unchanged. A rejection (`unknown_decision`) does the same. A later resume with instructions on the new block then answers the question.
  - [x] Applied acknowledgment with a `StatusEffect`: record unchanged.
  - [x] A record already `answered` (answerer) is untouched by an applied resume.
  - [x] A resume submitted with `submitted_by` set to the answerer's name, on a `declined` record, is recorded as `pm`.
  - [x] A block with no record behaves exactly as before.
  - [x] Transition walk (`-k transition`): seed a record in each `QuestionState` through the test helper, then drive every writer 141 provides (`decline_question`, and the acknowledgment's applied resume) from it. Each result either matches `QUESTION_TRANSITIONS` or raises `InvalidTransitionError` and leaves the row unchanged. Pairs whose writers belong to 142 and 144 are covered by asserting the table itself.
  - [x] The list of judge acknowledgment shapes (applied resume, applied stop, rejection) is asserted in one place so a new shape fails the test (LLD Mitigation Strategies).
  - [x] Feed trigger tests (`tests/store/test_feed_triggers.py`, `test_mapping_feed.py`; triggers and `ChangeKind` members from Task 2.2): recording a question emits `question_recorded`; a decline emits one `question_state_changed` (`pending → declined`); a PM answer emits `declined → answered`; a re-point (stop or rejection) emits nothing. Payloads contain no `question` or `answer` keys.
  - [x] Success: all cases pass, and `tests/store/test_resolutions.py`, the resolution tests under `tests/runner/resolutions/` and `tests/feed/` pass unchanged.

**Commit**: `feat: record the PM's answer on the question record at acknowledgment`

---

## 5. Outcome plan and ingest

- [x] **5.1 `QUESTION_TAIL_CHARS` and `OutcomePlan.question`** (`process/sq_outcome.py`, `runner/ingest/outcome.py`)
  - [x] Add `QUESTION_TAIL_CHARS: Final = 400` in `process/sq_outcome.py` beside the `question` field, with a comment that it is Squadron's tail limit (LLD D4). Defined once; no literal `400` for this purpose elsewhere.
  - [x] On the `QUESTION` branch of `plan_supervised`, set `OutcomePlan.question` to a `QuestionCatch`-ready value: `run_id`, `step`, text, and `truncated = len(question) >= QUESTION_TAIL_CHARS` computed on the raw text before 132's byte bound. A null question gives `truncated = false`.
  - [x] Keep the block context and payload byte-identical to today.
  - [x] Success: other outcome classes carry no question.

- [x] **5.2 Tests for the plan** (`tests/runner/ingest/test_plan_supervised.py`, `test_outcome.py`)
  - [x] A question below, at and above 400 characters: `truncated` false, true, true. A null question: `truncated` false and the catch's text null.
  - [x] The block context and payload equal the pre-change values (compare to the existing expected bytes).
  - [x] Non-question outcomes have `question` unset.
  - [x] Success: new and existing outcome tests pass.

- [x] **5.3 Ingest routes a question plan through `record_question`** (`runner/ingest/record.py`)
  - [x] When the plan carries a question, call `store.record_question(...)` with the plan's block context and payload instead of `block_once`. Other plans keep `block_once`. `record_runner_report` is unchanged and still follows.
  - [x] Do not catch `record_question`'s errors (LLD D1).
  - [x] Success: non-question blocks are written exactly as before.

- [x] **5.4 Tests for ingest, end to end and crash** (`tests/runner/ingest/test_record.py`, `tests/runner/test_end_to_end.py`, `tests/runner/test_crash_recovery.py`)
  - [x] Ingest test: a question outcome produces one block and one record; a question on an already-blocked node produces a declined record and no block.
  - [x] Extend the existing `agent_question` end-to-end test: the existing assertions pass unchanged, plus one record found by `question_for_block` on the question's block after the question tick (its state is not asserted here, since Task 7.3 changes it within the same tick), and `answered` (pm) with `answer` equal to the instructions after the resume. (Task 7.4 adds the `declined` (`answerer_not_configured`) assertion between the two.)
  - [x] Crash case (`-k question`): kill between `record_question` and `record_runner_report`; the restarted tick resolves the entry with exactly one block and one record. A kill inside `record_question` leaves neither.
  - [x] Success: the new cases pass, and the runner suite passes.

**Commit**: `feat: write the question record when a question block is ingested`

---

## 6. Project config

- [x] **6.1 `AnswererSettings` and `ProjectSettings.answerer`** (`runner/project_config.py`)
  - [x] Add frozen pydantic `AnswererSettings` with `extra="forbid"` and no fields, and `ProjectSettings.answerer: AnswererSettings | None`, per LLD D6.
  - [x] `answerer: {}` loads as configured. A missing key leaves `None`. An explicit null raises the load error "answerer must be a mapping; write `{}`", naming `projects.<id>.answerer`.
  - [x] Success: a project not named in the file has `answerer` of `None`.

- [x] **6.2 Tests for the section** (`tests/runner/test_project_config.py`)
  - [x] `answerer: {}` configured; absent key `None`; null value fails and the message names the project path; an unknown key inside `answerer` fails (`extra="forbid"`).
  - [x] Parse a fixture in the real `projects.yaml` layout (per CLAUDE.md parsing rule), not only dict literals.
  - [x] Success: tests pass.

**Commit**: `feat: add the optional answerer project config section`

---

## 7. Settle function and answering stage

- [x] **7.1 `settle_pending`** (`runner/answering/settle.py`)
  - [x] Pure function per LLD D5: a pending record, its block's state and whether the answerer is configured, to `Skip` or `Decline(reason)`.
  - [x] Check order: block resolved and awaiting the Runner → `Skip`; block resolved and not awaiting → raise `QuestionInvariantError` (define it in the answering package); question null or empty → `question_missing`; no answerer section → `answerer_not_configured`; otherwise `no_answer_on_file`.
  - [x] Compare only through enums; no literal strings. Import no store write.
  - [x] Success: the module is covered by `tests/runner/purity.py`'s check (add it to that list as other pure modules are).

- [x] **7.2 Tests for `settle_pending`** (`tests/runner/answering/test_settle.py`)
  - [x] One case per branch, plus ordering cases: a resolved-and-awaiting block with a null question skips (does not decline); a resolved, not-awaiting block raises even when the question is null.
  - [x] Success: tests and the purity check pass.

- [x] **7.3 The answering stage and its place in the tick** (`runner/answering/stage.py`, `runner/tick.py`)
  - [x] Store-only stage: read `pending_questions(project_id)`, read each record's block state, call `settle_pending`, and call `decline_question` for a `Decline`. A `Skip` writes nothing.
  - [x] In `ProjectTick.run`, call it after `record_finished` and the `shape_error` check, before the `CUT_OFF` return. It takes no budget.
  - [x] The stage leaves the node context cleared, so an exception escalates per project (LLD D5, Fault isolation).
  - [x] Success: a question caught this tick is declined this tick, including a tick that ends cut off.

- [x] **7.4 Tick tests** (`tests/runner/test_tick_answering.py`, helpers from `tick_support.py`)
  - [x] Each decline reason is written: `question_missing`, `answerer_not_configured`, and `no_answer_on_file` with `answerer: {}`.
  - [x] A PM resolution submitted before the stage runs: the record is skipped, the next resolution stage applies it, and the record is `answered` by pm with no decline written.
  - [x] The invariant case: seed a `pending` record whose linked block is resolved with no resolution awaiting the Runner, using the existing helpers in `tests/store/test_resolutions.py` or `tick_support.py`; if none can express it, write one direct update in a test helper. The stage raises, and the failure escalates per project, once, deduplicated.
  - [x] A question caught in a tick that ends `CUT_OFF` is still declined.
  - [x] In the `agent_question` end-to-end test from Task 5.4, assert the record is `declined` (`answerer_not_configured`) after the question tick, before the resume.
  - [x] Success: tests pass, and the runner suite passes.

**Commit**: `feat: add the answering stage that declines pending questions`

---

## 8. Inspection

- [x] **8.1 `questions` listing** (`inspection/questions.py`, registered in `inspection/core.py`)
  - [x] Project-scoped listing with columns `id`, `node_id`, `run_id`, `step`, `state`, `answered_by`, `question`, `outcome`, `truncated`, `created_at`. `outcome` is the answer when `answered`, the decline reason when `declined`, otherwise empty.
  - [x] Options: `--node` (the shared `NODE_OPTION`) and `--state` (a `ChoiceOption` over `QuestionState`).
  - [x] JSON rows also carry `blocked_state_id`, `source_entry_id` and `updated_at`.
  - [x] Success: `amoeba inspect questions --project P` runs, and `GET /v1/listings/questions?project=P` comes from the registry with no server change.

- [x] **8.2 `blocked` gains `question_state` and `decline_reason`** (`inspection/core.py`)
  - [x] Join on `blocked_state_id`. Both columns are empty for a block with no question. The JSON row also carries `question_id`.
  - [x] Existing columns and `payload` unchanged. Add the columns in `_blocked_rows`, which `blocked_rows` and `all_blocked_rows` share, so no second code path is written.
  - [x] Success: the existing `blocked` tests pass unchanged.

- [x] **8.3 Inspection tests** (`tests/inspection/test_questions.py`, `test_listing.py`, `tests/serve/` for the route)
  - [x] `questions` rows for each state; `--state declined` and `--node` filter; `outcome` rules; `truncated` shown.
  - [x] `blocked` shows `question_state` and `decline_reason` for a question block and empties for another block.
  - [x] The server lists the `questions` listing (follow how other listings are covered in `tests/serve/`).
  - [x] Success: inspection and serve suites pass.

**Commit**: `feat: add the questions listing and question columns on blocked`

---

## 9. Contract docs

- [x] **9.1 Update the contract docs**
  - [x] `docs/store-contract.md`: a new "Question records" section from the LLD API Contracts table, with the states, the transition table, and D2's rule. Move the latest-migration paragraph to `013`.
  - [x] `docs/feed-contract.md`: add both kinds to the kinds table and the coverage list, with payload fields.
  - [x] `docs/process-contract.md`: the `answerer` section under "The project config", with the empty-mapping rule and null-value error; `QUESTION_TAIL_CHARS` in the "Squadron shapes" section.
  - [x] `docs/substrate-guide.md`: the 120 row mentions the question record.
  - [x] Update the answering-stage steps 2 and 7 in `project-documents/user/architecture/140-slices.question-answerer.md` as LLD D2 says (the stage skips a resolved block; the acknowledgment settles it).
  - [x] Add a `CHANGELOG.md` entry under the unreleased heading.
  - [x] Success: every contract statement matches the code; the latest-migration paragraph in `docs/store-contract.md` names `013`, not `012`.

**Commit**: `docs: document question records, the answerer section and the new feed kinds`

---

## 10. Final verification

- [ ] **10.1 Full validation**
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest -q` once each. All pass, apart from failures recorded in Task 1.1 as pre-existing.
  - [ ] Check file sizes: no new or changed source file is far over 300 lines.
  - [ ] Walk LLD Verification Walkthrough steps 5–7 (steps 1–4 are `pytest` runs the full suite above already covers) against a throwaway `AMOEBA_STORE_DIR` with a scratch project and the stub `sq` harness: the `blocked` and `questions` output, the `answerer: {}` and null-value config behaviour, and the PM resume with `amoeba feed` showing `question_recorded` and two `question_state_changed` lines.
  - [ ] Success: all checks pass, and the walkthrough output matches the LLD's expected results.

**Commit**: commit any changes verification required as `fix: {what was wrong}`; if verification changed nothing, there is no commit. If a walkthrough step fails, fix the cause, rerun Task 10.1 from the top, then commit.
