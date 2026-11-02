---
docType: tasks
slice: the-gate-and-answer-submission
project: amoeba
lld: user/slices/142-slice.the-gate-and-answer-submission.md
dependencies:
- 140
- 141
projectState: Slices 120–132 and 141 are merged. 140 (answering pipeline) is built,
  with only its probe needed here. The store is at schema version 13. question_records,
  QUESTION_TRANSITIONS, DeclineReason, decline_question and AnswererSettings (no keys
  yet) exist. Nothing of slice 142 is built.
dateCreated: 20261102
dateUpdated: 20261102
status: in_progress
turns: 33
promptTokens: 1199949
cachedTokens: 1127108
cacheWriteTokens: 72803
completionTokens: 18522
durationSeconds: 133.2
costUsd: 0.589517
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.5895176999999999
    completionTokens: 18522
revision_number: 2
---

## Context Summary

- Working on the **the-gate-and-answer-submission** slice (142) of the question-answerer initiative (140 architecture). Every answer the answerer would submit passes one pure gate (answer limit, PM-reserved screen), and one store operation, `submit_answer`, submits it or declines it in a single transaction.
- **Current state:** see `projectState`.
- **Dependencies:** 141 (question record) and 140 (only `probe_answering_pipeline`), both merged. 127 and 100 supply the resolution slot and the inbox submission row. No Squadron or LLM dependency.
- **What this slice delivers:** the submission-insert extraction; migration `014`; two `DeclineReason` members and the gate types; `evaluate_gate` and `compose_instructions`; `submit_answer`; the two required `answerer` keys; the start-up probe; the `reserved_term` listing column; contract docs. Nothing calls `submit_answer` outside tests.
- **Next planned work:** 143 (source passages), 144 (answering run, the first caller), 145 (walkthrough).

**Branch:** all implementation happens on `142-slice.the-gate-and-answer-submission`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/142-slice.the-gate-and-answer-submission.md` at the named decision (D1–D9), "Architecture", "Implementation Details" or "API Contracts". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/`, `docs/` or `project-documents/`. Keep every new or changed source file near 300 lines and each function near 50.

**Order and dependencies:** work tasks in file order. Each task leaves the full suite passing and the resident process starting.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and run lint and typecheck (`uv run ruff check .`, `uv run pyright`) before the markers that follow source changes.

**Task-level facts** (checked against the code on 20261102; each resolves a placement, not a product decision):
- 141's names match the LLD: `QuestionRecord`, `QuestionState`, `AnsweredBy`, `DeclineReason`, `QUESTION_TRANSITIONS`, `require_transition` (`store/questions.py`), `QuestionOperations` (extends `BlockWriter`), `sql_questions` (`UPDATE_QUESTION_DECLINED`, `UPDATE_QUESTION_ANSWERED`, `SELECT_QUESTION_BY_ID`, `QUESTION_COLUMNS`, `COL_QUESTION_*` constants), `AnswererSettings` (no keys), `decline_question`, and `question_for_block`. `EXPECTED_SCHEMA_VERSION` is 13 in `store/migrations.py`.
- `apply_submission` in `store/inbox.py` inserts the row inline with `sql_inbox.INSERT_SUBMISSION` (9 parameters: id, project, kind, submitted_by, submitted_at, payload JSON, outcome, reason, applied timestamp). `_write_resolution` (`store/_block_writer.py`) returns `False` when no open slot exists. Resolution payload keys are `RESOLUTION_BLOCKED_STATE_ID`, `RESOLUTION_DETAIL`, `RESOLUTION_DECISION`, `RESOLUTION_INSTRUCTIONS` in `store/inbox_models.py`.
- `probe_answering_pipeline(settings, run)` is in `runner/probes.py`; `runner_tenant` (`runner/factory.py`) calls `probe_sq(settings, _now(), poll_run)` and would pass the same `poll_run` runner.
- Tests: store tests in `tests/store/` (`test_migration_013.py` is the migration pattern, `test_inbox_apply.py` the inbox suite, `test_question_acknowledgment.py` and `test_question_records.py` use `tests/question_harness.py`); fault injection is `tests/fault_injection.py::fail_on_statement`; the purity check is `tests/runner/purity.py`; answering tests are in `tests/runner/answering/`; config tests are `tests/runner/test_project_config.py`; factory tests are `tests/runner/test_factory.py`; inspection tests are in `tests/inspection/`.

---

## 1. Branch and baseline

- [x] **1.1 Create the slice branch and record the baseline**
  - [x] Run `cf config get git.integration_branch`. The result (or `main` if empty) is the target. Confirm you are on the target.
  - [x] Run `git checkout -b 142-slice.the-gate-and-answer-submission {target}`.
  - [x] Run `uv run pytest -q`, `uv run ruff check .` and `uv run pyright` once. Note any failures that exist before this slice.
  - [x] Success: on branch `142-slice.the-gate-and-answer-submission`, and the baseline result is known.

---

## 2. Extract the submission insert

- [x] **2.1 `SubmissionWriter._insert_submission`** (`store/_submission_writer.py`, new)
  - [x] Create base class `SubmissionWriter(StoreBase)` (follow `BlockWriter`'s shape) with `_insert_submission(...)` taking the 9 values the inline statement binds and executing `sql_inbox.INSERT_SUBMISSION`. It opens no transaction; the caller's does.
  - [x] Make `InboxOperations` also inherit `SubmissionWriter`, and replace the inline `INSERT_SUBMISSION` execute in `apply_submission` with `self._insert_submission(...)`. Per LLD "Component Structure".
  - [x] Change no behavior: the payload JSON, outcome and reason are written exactly as before.
  - [x] Success: module imports; typecheck passes.

- [x] **2.2 Run the inbox suite unchanged**
  - [x] Run `uv run pytest tests/store tests/inbox -q`. `test_inbox_apply.py` and every other existing test pass with no edits (replay and rejection cases included).
  - [x] Success: all pass; no existing test was modified.

**Commit**: `refactor: extract the inbox submission insert into a shared writer`

---

## 3. Migration, decline reasons and gate types

- [x] **3.1 Migration 014** (`store/schema/014_answer_submission.sql`)
  - [x] Add `reserved_term TEXT` to `question_records` (nullable, no default), per LLD D9.
  - [x] Set `EXPECTED_SCHEMA_VERSION` to 14 and register `014` the way `013` was registered in `store/migrations.py`.
  - [x] Add `COL_QUESTION_RESERVED_TERM` to `sql_questions.py` and append it to `QUESTION_COLUMNS`; update `INSERT_QUESTION` only if it depends on the column list (the new column is null on insert).
  - [x] Success: a fresh store opens at version 14; existing 13 → 14 upgrade works.

- [x] **3.2 `DeclineReason` members and record field** (`store/question_models.py`, `store/mapping_questions.py`)
  - [x] Add `ANSWER_LIMIT_REACHED = "answer_limit_reached"` and `RESERVED_TERM = "reserved_term"` to `DeclineReason`.
  - [x] Add `reserved_term: str | None` to `QuestionRecord` and map it in `map_question_record`.
  - [x] Update `UPDATE_QUESTION_DECLINED` to also set `reserved_term`, and make `decline_question` pass `None` for it (existing callers unchanged).
  - [x] Success: existing question tests pass; typecheck passes.

- [x] **3.3 Gate types and `ANSWER_DECISION`** (`store/question_models.py`)
  - [x] Add frozen `GateRefusal(reason: DeclineReason, reserved_term: str | None)`.
  - [x] Add `AnswerGate = Callable[[str, int], GateRefusal | None]`.
  - [x] Add `AnswerOutcome` `StrEnum` (`submitted`, `declined`, `block_resolved`, `settled`) and frozen `AnswerSubmission(outcome, record)`.
  - [x] Add `ANSWER_DECISION: Final = "resume"` beside `AnsweredBy`, with a comment that the store defines the string because no store module imports the Runner (LLD D5).
  - [x] Success: imports; typecheck passes.

- [x] **3.4 Tests for migration and models** (`tests/store/test_migration_014.py`, `tests/store/test_question_records.py`)
  - [x] Migration test following `test_migration_013.py`: 13 → 14 adds the nullable `reserved_term` column and keeps existing rows.
  - [x] A `declined` record written with a `DeclineReason.RESERVED_TERM` reads back with the new reason; an unknown reason value still raises `UnknownVocabularyValueError`.
  - [x] Any existing test pinning the schema version, column list or `DeclineReason` members is updated to match.
  - [x] Success: `uv run pytest tests/store -q` passes.

- [x] **3.5 `AnswererSettings` keys** (`runner/project_config.py`)
  - [x] Add `answer_limit: StrictInt` (at least 1) and `reserved_terms: list[str]` (each stripped and non-blank), both required, no defaults; keep `extra="forbid"` (LLD D7). The gate in Task 4 reads them.
  - [x] Update the class docstring (it says "no keys yet").
  - [x] In the same task, update every existing test or fixture that wrote `answerer: {}` to carry both keys, so the suite keeps passing.
  - [x] Success: `answerer: {}` fails at load naming both missing keys with their paths; `reserved_terms: []` loads; `uv run pytest -q` passes.

- [x] **3.6 Config tests** (`tests/runner/test_project_config.py`)
  - [x] `answerer: {}`, a missing `answer_limit`, a missing `reserved_terms`, `answer_limit: 0`, a negative or non-integer limit and a blank term each fail with the key path.
  - [x] `reserved_terms: []` with a valid limit loads; no `answerer` section still loads as before.
  - [x] Success: `uv run pytest tests/runner -q` passes.

**Commit**: `feat: add migration 014, answer decline reasons, gate types and answerer keys`

---

## 4. The gate

- [x] **4.1 `evaluate_gate` and `compose_instructions`** (`runner/answering/gate.py`)
  - [x] `evaluate_gate(question, prior_answers, *, answer, settings: AnswererSettings) -> GateRefusal | None`, pure (no I/O, no clock, no store), per LLD D1/D2.
  - [x] Check 1: `prior_answers >= settings.answer_limit` returns `GateRefusal(ANSWER_LIMIT_REACHED, None)`.
  - [x] Check 2: for each term in configured order, test the question then the answer; first hit returns `GateRefusal(RESERVED_TERM, <term as configured>)`.
  - [x] Matching: casefold both sides, collapse every run of whitespace to one space, substring match with no word boundaries. Define the normalizer once in the module.
  - [x] `compose_instructions(question, answer) -> str` returns exactly two lines: `You asked: {question}` then `Answer: {answer}` (LLD D5).
  - [x] Success: module imports; typecheck passes.

- [x] **4.2 Gate tests** (`tests/runner/test_answer_gate.py`; purity registration in `tests/runner/purity.py`)
  - [x] Limit: below, at and above `answer_limit`; the limit wins over a reserved hit when both apply.
  - [x] Reserved: a term in the question; a term in the answer; a mixed-case, newline-split variant of a multi-word term (for example `Drop\n Table` against the term `drop table`); `pushed` against `push`; configured order decides which term is reported; the returned term is as configured (case preserved).
  - [x] An empty `reserved_terms` list never refuses on terms.
  - [x] `compose_instructions` returns the exact two-line text.
  - [x] Add `gate.py` to the purity check and confirm it passes.
    - Note: purity.py has no registry; the check is the `io_use(gate) == []` test in `tests/runner/test_answer_gate.py`, which passes.
  - [x] Success: `uv run pytest tests/runner/test_answer_gate.py -v` passes.

**Commit**: `feat: add the pure answer gate and instruction composer`

---

## 5. `submit_answer`

- [x] **5.1 SQL for the new reads and writes** (`store/sql_questions.py`)
  - [x] Add a count statement: records with the same `project_id` and `run_id`, `state = answered`, `answered_by = answerer`, excluding a given record id (LLD D3).
  - [x] Reuse `UPDATE_QUESTION_ANSWERED` for the answerer's `answered` write if its columns already cover state, answered_by, answer and updated_at; otherwise add `UPDATE_QUESTION_ANSWERED_BY_ANSWERER`. The declined update already carries `reserved_term` (Task 3.2).
  - [x] Add a statement to read whether a block is resolved (reuse an existing `sql` constant if one already selects a blocked state by id).
  - [x] Success: all SQL and column names live in `sql_questions.py` or `sql_inbox.py`; typecheck passes.

- [x] **5.2 `submit_answer`: validation, early outcomes and decline** (`store/answer_submission.py`, new; mixin `AnswerSubmissionOperations` on `QuestionOperations` and `SubmissionWriter`; not yet added to `Store`)
  - [x] Signature `submit_answer(question_id, *, answer, instructions, detail, gate) -> AnswerSubmission`. No `decision` or submitter parameter.
  - [x] Validate before the transaction: blank `answer`, `instructions` or `detail` raise `ValueError`; unknown id raises `QuestionNotFoundError` (add it next to the other store errors if absent; keep 141's `InvalidTransitionError` for `decline_question` unchanged); a record with no question text raises `ValueError`.
  - [x] Under one `BEGIN IMMEDIATE`, in this order: read the record; state not `pending`/`answering` → `settled`; block already resolved → `block_resolved`; count prior answers (record excluded); call `gate(record.question, prior)` once.
  - [x] Refusal: `require_transition` to `declined`, then execute `UPDATE_QUESTION_DECLINED` (extended in Task 3.2) directly with the refusal's reason and `reserved_term` inside this transaction. Do not call `decline_question`; it opens its own transaction. Return `declined`.
  - [x] Do not catch exceptions from `gate`; the `with self._connection` block rolls back and they propagate (LLD D4).
  - [x] Success: imports; typecheck passes.

- [x] **5.3 `submit_answer`: the submitted path and `Store` wiring** (`store/answer_submission.py`, `store/store.py`)
  - [x] Pass (gate returned `None`): `_write_resolution` with `ANSWER_DECISION`, `instructions`, `detail`, `resolved_by = AnsweredBy.ANSWERER.value`, `awaits_runner=True`; `_insert_submission` with kind `resolution`, outcome `applied`, new id, `submitted_by = AnsweredBy.ANSWERER.value` and the same payload keys a PM resolution carries; `require_transition` to `answered`, write `answered_by = answerer` and `answer`; return `submitted`. If `_write_resolution` returns `False`, treat as `block_resolved` and write nothing (roll back).
  - [x] Add `AnswerSubmissionOperations` to `Store`'s bases in `store/store.py`.
  - [x] Return the record as it stands after the transaction.
  - [x] Success: imports; typecheck passes; file near 300 lines.

- [x] **5.4 Outcome tests** (`tests/store/test_answer_submission.py`)
  - [x] `submitted`: asserts together the slot (`ANSWER_DECISION`, instructions, `resolved_by = answerer`, awaits the Runner), one `applied` resolution submission row with `submitted_by = answerer` and the caller's `detail`, and the record `answered`, `answered_by = answerer`, `answer` set.
  - [x] `declined` for each reason (a fake gate returning each `GateRefusal`): record `declined` with reason, `reserved_term` set only for the term decline, slot still open, no submission row.
  - [x] `block_resolved`: PM resolution submitted first → nothing written, record unchanged.
  - [x] `settled`: records already `answered`, already `declined` with `node_already_blocked` (no linked block) and in a terminal state return `settled` and write nothing.
  - [x] Errors: unknown id, blank `answer`/`instructions`/`detail`, no question text; signature has no `decision` or submitter parameter (inspect the signature).
  - [x] A test asserts `ANSWER_DECISION == ResolutionDecision.RESUME.value`.
  - [x] Success: `uv run pytest tests/store/test_answer_submission.py -v` passes.

- [x] **5.5 Race, count and Runner-rejection tests** (`tests/store/test_answer_submission.py`, names containing `race`, `count`, `rejected`)
  - [x] PM first: after `block_resolved`, run the Runner's acknowledgment of the PM resume; the record is `answered` with `answered_by = pm` and the PM's instructions as `answer`.
  - [x] Answerer first: `submitted`, then a PM resolution via `apply_submission` is rejected as already resolved; the record keeps `answered_by = answerer`.
  - [x] Count: two records on one run submitted one after the other give prior counts 0 then 1 (capture via a recording gate); a replay of the first returns `settled` and the count stays 2; a PM-answered record, a declined record and a pending record do not count.
  - [x] Limit scenario (LLD Success Criteria): with `answer_limit: 2` bound through `evaluate_gate` and two answerer-answered records on a run, a third returns `declined` with `answer_limit_reached`, no slot is filled, and the node's existing `HUMAN` block stays open.
  - [x] Runner rejects the answerer's resolution: drive `acknowledge_resolution` to reject it; the record stays `answered` (answerer), still counts toward the limit, the node's new `HUMAN` block carries the rejection code, and a PM resume of that block is not recorded as precedent (LLD D6).
  - [x] Success: `uv run pytest tests/store/test_answer_submission.py -k "race or count or rejected" -v` passes.

- [x] **5.6 Crash-safety tests** (`tests/store/test_answer_submission.py`, names containing `crash`)
  - [x] With `fail_on_statement`, fail in turn the slot write, the submission insert and the record update; each run leaves the slot open, no submission row and the record unchanged.
  - [x] A gate that raises leaves the same state and its exception reaches the caller.
  - [x] Success: `uv run pytest tests/store/test_answer_submission.py -k crash -v` passes.

**Commit**: `feat: add submit_answer, the one gated answer submission`

---

## 6. Start-up probe

- [x] **6.1 Start-up probe wiring** (`runner/factory.py`)
  - [x] In `runner_tenant`, after `probe_sq`: if any configured project has `answerer` set, call `probe_answering_pipeline(settings, poll_run)` and log that it passed. With none, do not call it (LLD D8).
    - Note: the probe takes a subprocess.run-style runner (CfRun), so runner_tenant passes subprocess.run, not poll_run.
  - [x] A failure surfaces as `StartupFailedError`, so `start` exits `STARTUP_FAILED` as for `probe_sq`.
  - [x] Update the stale "Start-up wiring is slice 142's" note in `probe_answering_pipeline`'s docstring.
  - [x] Success: imports; typecheck passes.

- [x] **6.2 Factory tests** (`tests/runner/test_factory.py`)
  - [x] With an answerer section the probe is called once; a failing probe raises `StartupFailedError`.
  - [x] With no answerer section the probe is not called.
  - [x] Success: `uv run pytest tests/runner -q` passes.

**Commit**: `feat: run the answering pipeline probe at start when an answerer is configured`

---

## 7. Listing and contract docs

- [x] **7.1 `reserved_term` in the `questions` listing** (`inspection/questions.py`)
  - [x] Add the `reserved_term` column to the row, following how `decline_reason` is shown.
  - [x] Success: imports; typecheck passes.

- [x] **7.2 Listing tests** (`tests/inspection/`, the existing questions listing tests; `tests/serve/` if the route's shape is pinned)
  - [x] A `reserved_term` decline shows the term as configured; other rows show it empty.
  - [x] With three records on one node (two answered by the answerer, one declined), `inspect questions --node` lists all three and both answers.
  - [x] Success: `uv run pytest tests/inspection tests/serve -q` passes.

- [x] **7.3 Update the contract docs**
  - [x] `docs/store-contract.md`: add the "Submitting an answer" subsection under "Question records" with the `submit_answer` row and outcomes from the LLD API Contracts; move the latest-migration paragraph to `014` and describe `reserved_term`.
  - [x] `docs/process-contract.md`, "The project config": the `answerer` section with `answer_limit` and `reserved_terms`, the load errors from D7, the example config, and the probe condition.
  - [x] Success: both docs match the code names; no stale "no keys yet" text remains.

**Commit**: `feat: list the reserved term and document answer submission and the answerer keys`

---

## 8. Final validation

- [ ] **8.1 Full validation**
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest -q` once each. All pass.
  - [ ] LLD Verification Walkthrough steps 1–4 (the new test modules) pass as written.
  - [ ] Walkthrough step 5 with a throwaway `AMOEBA_STORE_DIR` and scratch `projects.yaml`: `answerer: {}` fails naming both keys; `answer_limit: 0` fails; `answer_limit: 2` runs the answering probe or fails `STARTUP_FAILED` naming `sq run … --validate`; with the section removed the probe does not run.
  - [ ] Walkthrough step 6: with the stub-driven scratch slice from 141's walkthrough, `amoeba inspect questions --project scratch` still shows `declined` with `no_answer_on_file`.
  - [ ] Confirm no source file added or changed exceeds about 300 lines.
  - [ ] Success: all checks pass; the branch holds the committed work and is not merged.

**Commit**: commit any changes verification required as `fix: {what was wrong}`; if verification changed nothing, there is no commit. If a walkthrough step fails, fix the cause, rerun Task 8.1 from the top, then commit.
