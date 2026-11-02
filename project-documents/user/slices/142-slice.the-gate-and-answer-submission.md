---
docType: slice-design
slice: the-gate-and-answer-submission
project: amoeba
parent: user/architecture/140-slices.question-answerer.md
dependencies:
- 140
- 141
interfaces:
- 144
dateCreated: 20261101
dateUpdated: 20261102
status: complete
turns: 24
promptTokens: 1662516
cachedTokens: 1562121
cacheWriteTokens: 100351
completionTokens: 22746
durationSeconds: 239.0
costUsd: 1.570663
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.5706626000000001
    completionTokens: 22746
---

# Slice Design: the-gate-and-answer-submission

## Overview

Every answer the answerer would submit passes one gate, and one store operation submits it. The gate is a pure function with two checks: the per-run answer limit, read from the question record, and the PM-reserved screen, which matches the project's configured reserved terms against the question and the answer. The operation, `submit_answer`, lives in 100's store. Under one `BEGIN IMMEDIATE` it reads the record, the question's block and the run's answer count, runs the gate, and then either submits or declines. To submit, it fills the block's resolution slot with a `resume` and instructions, records the inbox submission with the answerer as submitter, and marks the record `answered` with `answered_by=answerer`. To decline, it marks the record `declined` with the reason and any matched term.

The project config's `answerer` section, empty since 141, gains its first two keys: `answer_limit` and `reserved_terms`. Both are required and neither has a default. Start-up runs 140's answering-pipeline probe when any project has an answerer section.

Nothing calls `submit_answer` outside tests in this slice. 141's answering stage still declines every question. 144 is the first caller.

## Value

- **Architectural enablement.** The bounds on the answerer, and the transaction that makes a submission and its record agree, exist and are tested before any model answers. 144 calls one operation and gets one of four outcomes. It never touches the inbox, the record or the limit itself.
- **Safety by construction.** No later code path can submit an answer without passing the gate, because the gate runs inside the only operation that submits one, and that operation can write only a `resume` with the answerer as submitter.

## Technical Scope

Included:

- The gate: `evaluate_gate` (pure) in `runner/answering/gate.py`, with `compose_instructions`, which restates the question in the resume instructions.
- The store operation `submit_answer`, its outcome type, the gate protocol it calls, and `ANSWER_DECISION`, the one decision it can write. The submission-record insert moves out of `apply_submission` into a shared writer, so both paths write the row with one statement.
- Migration `014`: a `reserved_term` column on `question_records`.
- Two `DeclineReason` members: `answer_limit_reached` and `reserved_term`.
- `AnswererSettings` gains `answer_limit` and `reserved_terms`, both required.
- Start-up runs `probe_answering_pipeline` (from 140) when any project has an answerer section.
- The `questions` listing gains a `reserved_term` column.
- Contract docs: `docs/store-contract.md` and `docs/process-contract.md`.

Excluded:

- Calling `submit_answer` from the answering stage, and the `pending → answering` transition: 144.
- The citation check and the decision that an answer is confirmed: 143 and 144.
- Any change to the inbox's own `apply_submission` behavior, to `acknowledge_resolution`, or to the Runner's resolution judge.

## Dependencies

### Prerequisites

- **141 (question record).** Not yet implemented. This design is written against 141's API Contracts and schema: `question_records`, `QUESTION_TRANSITIONS`, `DeclineReason`, `decline_question`'s write, `AnswererSettings`, and D2's acknowledgment rule. Re-check these names against 141's code before 142's task breakdown.
- **140 (answering pipeline), only its probe.** `probe_answering_pipeline(settings, run)` (140, D9). That part of 140 does not wait on Squadron, so this dependency is not blocked by 140's Squadron issue.
- **127 and 100.** The resolution slot (`_write_resolution`, `awaits_runner`), the inbox submission record, and the one-open-block-per-node index.

### Interfaces Required

- `BlockWriter._write_resolution` (`store/_block_writer.py`) fills the open slot and flags it for the Runner.
- `sql_inbox.INSERT_SUBMISSION` and `SubmissionKind.RESOLUTION`, with the resolution payload keys in `inbox_models`.
- From 141: `QuestionRecord`, `QuestionState`, `AnsweredBy`, `DeclineReason`, `QUESTION_TRANSITIONS`, `sql_questions`, `mapping_questions`, and `ProjectSettings.answerer`.
- `ResolutionDecision.RESUME` (`runner/resolutions/vocabulary.py`), the decision value the Runner's judge applies. Only a test imports it, to check `ANSWER_DECISION` against it.
- `runner_tenant` (`runner/factory.py`), where `probe_sq` runs today.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Gate | `runner/answering/gate.py` | Pure. `evaluate_gate(question, answer, prior_answers, settings) -> GateRefusal \| None`, and `compose_instructions(question, answer) -> str` |
| Gate types | `store/question_models.py` (extended) | `GateRefusal(reason, reserved_term)`, the `AnswerGate` protocol, `AnswerOutcome`, `AnswerSubmission`, `ANSWER_DECISION` |
| Submission writer | `store/_submission_writer.py` (new, extracted) | `SubmissionWriter._insert_submission(...)`: the one insert of an inbox submission row, used by `apply_submission` and `submit_answer` |
| Answer submission | `store/answer_submission.py` (mixin `AnswerSubmissionOperations`) | `submit_answer`: the one transaction |
| Migration | `store/schema/014_answer_submission.sql` | One column |
| SQL | `store/sql_questions.py` (extended) | Count of the answerer's answers on a run, the `answered` and `declined` updates with the new columns |
| Settings | `runner/project_config.py` | `AnswererSettings.answer_limit`, `AnswererSettings.reserved_terms` |
| Start-up | `runner/factory.py` | Runs the answering probe behind the answerer-section condition |
| Listing | `inspection/questions.py` | `reserved_term` column in the row |

`store.py` adds `AnswerSubmissionOperations` to `Store`'s bases. `InboxOperations` gains `SubmissionWriter` as a base, and `apply_submission` calls `_insert_submission` in place of its inline `INSERT_SUBMISSION`.

### Data Flow

144 is the caller. 142 tests drive the same path directly.

```
caller (144; tests in 142)
  record   = store.question(question_id)                       question text is immutable
  instr    = compose_instructions(record.question, answer)
  gate     = partial(evaluate_gate, answer=answer, settings=project.answerer)
  result   = store.submit_answer(question_id, answer=answer, instructions=instr,
                                 detail=<144's provenance text>, gate=gate)

store.submit_answer — one transaction
  BEGIN IMMEDIATE
    record state not pending/answering     -> SETTLED     (writes nothing)
    block resolved                         -> BLOCK_RESOLVED (writes nothing; 141 D2 settles it)
    prior = answerer answers on (project, run_id), this record excluded
    refusal = gate(record.question, prior)
      refusal                              -> record declined (reason, reserved_term) -> DECLINED
      none                                 -> slot filled: ANSWER_DECISION + instructions, resolved_by=answerer, awaits_runner
                                              submission row inserted (kind resolution, outcome applied)
                                              record answered, answered_by=answerer, answer -> SUBMITTED
  COMMIT
```

The Runner applies the resolution on a later tick, through the same judge and `sq run --resume <id> --instructions` path as the PM's. Its acknowledgment finds the record already `answered`, so 141's rule leaves the record alone.

### State Management

142 adds no state outside the store. It writes two of the transitions in 141's table:

| From | To | Writer |
| --- | --- | --- |
| `pending`, `answering` | `answered` (answerer) | `submit_answer`, gate passed |
| `pending`, `answering` | `declined` (`answer_limit_reached`, `reserved_term`) | `submit_answer`, gate refused |

Both go through `QUESTION_TRANSITIONS`, as every writer does.

## Technical Decisions

### D1 — The gate runs inside the submission transaction, passed in as a pure function

Status: decided

- The arch requires the gate to read the run's answer count inside the transaction that submits, so two submissions cannot both see a count below the limit. The reserved screen needs configuration that the store must not read. So `submit_answer` takes `gate: AnswerGate`, a callable `(question: str, prior_answers: int) -> GateRefusal | None`. The store reads the count under the write lock and calls the gate once. The caller binds the answer and the project's `AnswererSettings` into it with `functools.partial` over `evaluate_gate`.
- The gate stays one function in one place (the arch's "one gate for every resolution"). The store knows no terms and no limit, and the Runner never reads the count outside the lock.
- `evaluate_gate` is pure: no I/O, no clock, no store. It is safe to call while holding the write lock. `tests/runner/purity.py` covers `gate.py`.
- **Rejected:** passing `answer_limit: int` to the store and running the reserved screen before the call. That splits the gate in two, and a later caller could run one half without the other. **Also rejected:** reading the count before the call and passing it in. Two submissions could then both pass the limit.

### D2 — The gate's checks, in order

Status: decided

1. **Answer limit.** If `prior_answers >= settings.answer_limit`, it returns `answer_limit_reached`.
2. **Reserved screen.** Each configured term is checked, in configured order, first against the question and then against the answer. The first hit returns `GateRefusal(reserved_term, reserved_term=<the term as configured>)`.

Matching casefolds both sides and collapses every run of whitespace to one space, so `Merge to\n main` matches the term `merge to main`. It is a substring match with no word boundaries, so `push` also matches `pushed`. Over-matching costs one PM answer. A miss could cost a run. The screen is a net, as the arch says, and the check step is told to refuse reserved actions too.

The instructions are not screened separately: `compose_instructions` builds them only from the question and the answer, which are both screened.

### D3 — What counts toward the answer limit

Status: decided

- `prior_answers` is the number of records with the same `project_id` and `run_id`, `state = answered` and `answered_by = answerer`, excluding the record being submitted. It is read inside the transaction.
- Only the answerer's answers count. A PM answer, a decline and a pending question do not. The limit bounds how often the answerer may steer one run. It does not bound how often a run may ask.
- An answer counts once it is submitted, even if the Runner later rejects the resolution (D6). The spend and the steering already happened.
- Replays cannot count twice. A record already `answered` returns `SETTLED` before the count is read. The count is recomputed from records in every transaction, so two answers submitted in the same tick count once each.
- `answer_limit` is a positive integer. `0` is a load error: to turn the answerer off, remove the section.

### D4 — `submit_answer`'s outcomes, and why a lost race writes nothing

Status: decided

`AnswerOutcome` is a closed `StrEnum`. `AnswerSubmission(outcome, record)` carries the record as it stands after the transaction.

| Outcome | When | Writes |
| --- | --- | --- |
| `submitted` | Gate passed, slot was open | Slot, submission row, record `answered` (answerer) |
| `declined` | Gate refused | Record `declined` with reason and term |
| `block_resolved` | The question's block already has a resolution | Nothing |
| `settled` | The record is not `pending` or `answering` | Nothing |

- **`block_resolved` is the arch's "PM answered first".** 141 (D2) moved that note to the acknowledgment: when the Runner applies the PM's resume, the record becomes `answered` with `answered_by = pm`, and that value is the note. The slice plan's "the record is marked 'PM answered first'" is met that way, and the PM's answer is the one recorded as precedent. Writing a decline here instead would be wrong. The PM's resolution might still be rejected by the Runner, and a declined record would then hide a question that is still open.
- **The other race order.** If the answerer submits first, the slot is filled. A PM submission that arrives afterwards is rejected by the inbox's existing check ("already resolved"), and the PM sees that rejection on the submission. Whichever applies first wins, as the slice plan requires.
- **`block_resolved` is checked before the gate.** An answer that cannot be submitted is not declined, and does not use up a limit slot.
- **A record with no linked block** (`node_already_blocked`) is always `declined`, so it returns `settled`. No separate branch is needed.
- `submit_answer` raises only on programming errors: an unknown question id (`QuestionNotFoundError`), a blank `answer`, `instructions` or `detail`, or a record with no question text (`ValueError`). 141's settle step declines a question with no text before any run, so a caller never reaches here with one. Expected situations are outcomes.
- **A gate that raises is a programming error too** (a bad `partial` binding, say). The store does not catch it: the exception leaves the `with` block, the transaction rolls back, nothing is written, and the exception propagates to the caller, as any other failure inside the transaction does.
- **A busy store.** `BEGIN IMMEDIATE` waits up to the store's busy timeout, as every store write does. If the timeout is exhausted, the store's existing handling raises `StoreBusyError` before anything is read or written. The caller sees that exception and nothing has changed, so the question is still `pending` or `answering` and can be submitted on a later tick.

### D5 — The answerer's submission is an ordinary resolution with a submission record

Status: decided

- The slot is filled through `_write_resolution` with the store's own `ANSWER_DECISION`, the caller's `instructions` and `detail`, `resolved_by = AnsweredBy.ANSWERER.value`, and `awaits_runner = true`. The caller passes `compose_instructions(...)` and its own provenance text. To the Runner it is the same as a PM resume with instructions.
- **The decision is the store's, not the caller's.** The arch's hard bound is that the answerer can only resume a paused step with instructions. `ANSWER_DECISION` is a constant `"resume"` in `store/question_models.py`, beside `AnsweredBy`. `submit_answer` has no `decision` parameter, so no caller can get another decision through the gate. The store defines the string itself because no store module imports the Runner. A test asserts `ANSWER_DECISION == ResolutionDecision.RESUME.value`, so the two cannot drift apart. This differs from the PM path on purpose: the PM's inbox path is human-authored and allows any decision, while this operation is the answerer's only submission path.
- **The submitter is the store's, not the caller's.** The slot's `resolved_by` and the submission row's `submitted_by` are both `AnsweredBy.ANSWERER.value`, defined once beside the enum member that `answered_by` uses. The submissions listing therefore shows one answerer identity, and 142's tests verify it. `detail` stays the caller's text.
- An inbox submission row is written in the same transaction with `kind = resolution`, outcome `applied`, a new id, `submitted_by = answerer`, and the same payload a PM's resolution carries. So "who submitted" provenance is the same for both, and the submissions listing shows the answerer's answers beside the PM's. `apply_submission` is not called: it opens its own transaction (arch, "The record is the memory"). The row's insert is extracted into `SubmissionWriter._insert_submission` so both paths share one statement.
- **Which validations it shares with the inbox.** `apply_submission` makes three checks on a resolution: the blocked state exists, it belongs to the submission's project, and it is not yet resolved. The envelope also rejects a blank `decision` or `instructions`. `submit_answer` makes the same checks. The block comes from the record's `blocked_state_id`, so it exists and is in the record's project, because 141's schema links them. It checks that the block is unresolved (`block_resolved`), and it rejects blank strings (D4). Neither path checks the decision vocabulary or that a `resume` carries instructions in the store. The Runner's judge does that when it acknowledges, for both (slice 127, D1). The answerer's decision is always `ANSWER_DECISION`, so the judge's decision check never fails for it, but the judge stays the one validator the arch names.
- The detail text is provenance, not gate logic, so it is defined with the caller in 144, not in `gate.py`. It is never read to decide anything. 141's rule decides "answered by the PM" from the record (141, D2), never from `resolved_by`, `submitted_by` or `detail`. 142's tests pass their own detail strings.
- `compose_instructions` returns two labelled lines, the question and then the answer: `You asked: {question}` and `Answer: {answer}`. The rerun may not see the earlier conversation (arch), so the question is restated.

### D6 — An answerer resolution the Runner rejects

Status: decided

141 left this to 142. The record stays `answered` (answerer), and the answer counts toward the limit. 127's rejection already re-blocks the node with a `HUMAN` block that carries the rejection code, so the PM sees the run on the blocked list and the rejection says why. A PM resume of that new block is not recorded as precedent, because 141's rule finds no unanswered record linked to it. 142 proves this behavior itself, with a test that has the Runner's acknowledgment reject an answerer resolution (see Success Criteria), so this decision does not wait on any later slice. The path is narrow: the answerer's decision is always `resume` (D5), and 144's shared journal reader removes the one known way the Runner could reject it (`instructions_not_applicable` while an `sq_answer` entry is latest). 144 carries that closure as its own obligation (Provides to Other Slices). **Rejected:** a new record state for "answered, then rejected". It would make `answered` non-terminal to cover a path that 144 closes.

### D7 — Two required configuration keys, no defaults

Status: decided

```yaml
projects:
  amoeba:
    pipeline: p456      # 132's slice pipeline, unchanged
    answerer:
      answer_limit: 3
      reserved_terms: [push, merge to main, release, DROP, TRUNCATE, policy]
```

- `answer_limit` is a `StrictInt` of at least 1. `reserved_terms` is a list of strings, each stripped and non-blank. Both fields are required, with no defaults (`extra="forbid"`, as 141 set).
- `reserved_terms: []` loads. A missing `reserved_terms` key fails. This is the plan's rule that an empty list is accepted only when written explicitly. `answerer: {}` now fails at load, naming both missing keys. 141 (D6) foresaw this.
- The example values above appear only in the process contract's example config. No code holds them.

### D8 — The answering probe runs at start only when a project has an answerer section

Status: decided

- **Placement.** The slice plan gives this wiring to 142, because 142 is the first slice that loads keys in the answerer section.
- **What it validates.** The probe takes no configuration. It validates the answering pipeline that ships inside Amoeba as package data, `answering.yaml`, found through `answering_pipeline_path()` (140, D9). No project key names a pipeline in this slice. If 144 makes the answering pipeline configurable per project, 144 decides what the probe validates.
- In `runner_tenant`, after `probe_sq`: if any configured project has `answerer` set, call `probe_answering_pipeline(settings, …)` from 140 and log that it passed. A failure raises `StartupFailedError`, and `start` exits `STARTUP_FAILED` as for `probe_sq` (140, D9).
- With no answerer section anywhere, the probe does not run, and an install that does not use the answerer behaves as it does today. An install that adds an answerer section before 144 gets a probe whose result nothing uses yet. A failure there still means the installed `sq` cannot run the pipeline 144 will launch, so stopping start-up is the intended result.

### D9 — One column by migration `014`

Status: decided

- `reserved_term TEXT` is set only on a `reserved_term` decline. 141 deferred it here.
- No new feed kind is needed. 141's `question_state_changed` trigger already fires for both transitions. Its payload carries `decline_reason`, not the term, which keeps feed payloads small (141, Special Considerations).

### Technology Choices

- Stdlib `sqlite3` through the store's plumbing, pydantic for the settings, and `functools.partial` to bind the gate. Nothing new is added.

### Patterns and Conventions

- One store method, one transaction, with `BEGIN IMMEDIATE` before the first read that decides a write. This is the same rule `apply_submission` and `acknowledge_resolution` follow.
- Outcomes and reasons are compared only through their enums.
- Every SQL statement and column name lives in `sql_questions.py` or `sql_inbox.py`.

## Implementation Details

### Database / Storage Schema

Migration `014_answer_submission.sql`, schema version 14:

| Column | Type | Notes |
| --- | --- | --- |
| `reserved_term` | TEXT | The matched term, as configured. Null unless `decline_reason = reserved_term` |

### API Contracts

Store (`docs/store-contract.md`, "Question records", new subsection "Submitting an answer"):

| Method | Effect |
| --- | --- |
| `submit_answer(question_id, *, answer, instructions, detail, gate) -> AnswerSubmission` | In-process only. **One transaction** (D4). The store writes `ANSWER_DECISION` as the decision and `AnsweredBy.ANSWERER.value` as `resolved_by` and `submitted_by` (D5); the caller supplies neither. `instructions` and `detail` are plain strings written to the slot and the submission row as given, and the store reads neither. `gate: AnswerGate` is called once, under the write lock, with the record's question and the run's prior answerer answers. Outcomes: `submitted`, `declined`, `block_resolved`, `settled`. Raises `QuestionNotFoundError` for an unknown id, `ValueError` for a blank `answer`, `instructions` or `detail` or a record with no question text, and `StoreBusyError` when the busy timeout is exhausted. An exception from `gate` rolls the transaction back and propagates. |

Types (`store/question_models.py`):

- `GateRefusal(reason: DeclineReason, reserved_term: str | None)`
- `AnswerGate = Callable[[str, int], GateRefusal | None]`
- `AnswerOutcome` and `AnswerSubmission(outcome, record)`
- `ANSWER_DECISION: Final = "resume"`, the only decision `submit_answer` writes (D5)

Runner (`runner/answering/gate.py`):

- `evaluate_gate(question, prior_answers, *, answer, settings: AnswererSettings) -> GateRefusal | None`. Keyword-only `answer` and `settings`, so `partial` binds them.
- `compose_instructions(question: str, answer: str) -> str`

Project config (`docs/process-contract.md`, "The project config"): the `answerer` section with the two keys and the load errors from D7.

Inspection: `questions` rows gain `reserved_term`.

## Integration Points

### Provides to Other Slices

- **144 (answering run):** `submit_answer`, `evaluate_gate` and `compose_instructions`. 144 replaces 141's `no_answer_on_file` branch: a confirmed answer goes to `submit_answer`, and a non-confirmed one goes to `decline_question`. 144 handles each outcome as follows. `submitted` and `declined` are done. `block_resolved` and `settled` mean the run's result is discarded, as 141's D2 and the arch's step 7 require. 144 must not read the answer count or the inbox itself. 144 passes no decision and no submitter. It must keep a test that the answerer's resume is accepted by the Runner after an `sq_answer` resolves, because D6 treats a Runner rejection of the answerer's resume as closed by that test's path.
- **145 (walkthrough):** the reserved screen is what declines the "merge to `main`" question.

### Consumes from Other Slices

- **141:** the record, its transition table and its acknowledgment rule. If 141's implementation changes the names in its API Contracts table, 142's tasks follow them. The behavior 142 relies on is that an `answered` record is left alone by the acknowledgment.
- **140:** `probe_answering_pipeline`. Start-up only calls it, and the probe's own failure handling is 140's.
- **127:** a resolution whose slot is filled with `awaits_runner` is judged and acknowledged on a later tick, whoever filled it.

## Success Criteria

### Functional Requirements

- With `answer_limit: 2` and two answerer-answered records on run R, a third question on R returns `declined` with `answer_limit_reached`. No slot is filled, the node's existing `HUMAN` block stays open for the PM, and `inspect questions --node` lists R's three questions and both answers from the record.
- An answer whose question or answer contains a configured term, in any case or whitespace, returns `declined` with `reserved_term`, and the record's `reserved_term` is the term as configured. The listing's `reserved_term` column shows it.
- A passing answer returns `submitted`. The block's slot holds `ANSWER_DECISION` (equal to `ResolutionDecision.RESUME.value`), the instructions restating the question, and `resolved_by = answerer`. One `applied` resolution submission row exists with `submitted_by = answerer` and the caller's `detail`, and the record is `answered`, `answered_by = answerer`, with `answer` set. `submit_answer` accepts no decision or submitter argument.
- PM first: the PM's resolution is submitted, then `submit_answer` returns `block_resolved` and writes nothing. After the next resolution stage, the record is `answered` with `answered_by = pm` and the PM's instructions as `answer`.
- Answerer first: `submit_answer` returns `submitted`, and a PM resolution submitted afterwards is rejected by the inbox as already resolved. The record keeps `answered_by = answerer`.
- Runner rejects the answerer's resolution (D6): the test has the Runner's acknowledgment reject it. The record stays `answered` (answerer) and still counts toward the limit. The node's new `HUMAN` block carries the rejection code, and a PM resume of that block is not recorded as precedent.
- Two records on the same run, submitted one after the other in one tick, give a count of 0 for the first and 1 for the second. A replay of the first returns `settled` and the count stays 2.
- `answerer: {}`, a missing key, `answer_limit: 0`, or a blank term each fail at load with the key path. `reserved_terms: []` loads.
- With an answerer section configured, start-up runs the answering probe, and a failing probe stops start with `STARTUP_FAILED`. With none configured, the probe is not run.

### Technical Requirements

- Crash safety: `fail_on_statement` (`tests/fault_injection.py`) fails, in turn, the slot write, the submission insert and the record update inside `submit_answer`. Each run leaves the slot open, no submission row and the record unchanged. A gate that raises leaves the same, and its exception reaches the caller.
- `evaluate_gate` and `compose_instructions` pass the purity check. A table test covers every gate branch, plus the case and whitespace variants.
- A test asserts `ANSWER_DECISION == ResolutionDecision.RESUME.value`.
- `apply_submission`'s existing tests pass unchanged after the insert is extracted.
- The migration test covers 13 → 14. Format, lint, typecheck and the store, inbox, runner, inspection and process suites pass.
- Docs: the store contract's "Submitting an answer" subsection and the latest-migration paragraph moved to `014`. In the process contract, the `answerer` keys and the probe condition.

### Integration Requirements

- 144 can be designed against the API Contracts above without reading 142's code.
- After 142, a project with no answerer section behaves exactly as after 141. A project with one behaves the same except that its config must carry both keys and start-up runs the probe.

### Verification Walkthrough

Nothing calls `submit_answer` outside tests in this slice, so steps 1–4 are test runs. Steps 5–6 use a throwaway `AMOEBA_STORE_DIR` and a scratch `projects.yaml`, as in 141's walkthrough. Every test module named here is new in this slice.

1. **The gate.**

   ```
   uv run pytest tests/runner/test_answer_gate.py -v
   ```

   Expected: cases for the limit (below, at and above), a term in the question, a term in the answer, `Merge To\n main` against `merge to main`, `pushed` against `push`, an empty term list, and `compose_instructions`. All pass.

2. **Submission outcomes.**

   ```
   uv run pytest tests/store/test_answer_submission.py -v
   ```

   Expected: `submitted`, `declined` (both reasons), `block_resolved` and `settled` cases. The `submitted` case asserts the slot, the submission row and the record together.

3. **Races and counting.**

   ```
   uv run pytest tests/store/test_answer_submission.py -k "race or count or rejected" -v
   ```

   Expected: PM first, then a resolution stage, gives `answered` by the PM. Answerer first gives a rejected PM submission. A Runner-rejected answerer resolution leaves the record `answered` and counted. Two records on one run count 0, then 1. A replay is `settled`.

4. **Crash mid-way.**

   ```
   uv run pytest tests/store/test_answer_submission.py -k crash -v
   ```

   Expected: for each injected failure point, and for a gate that raises, neither the slot, the submission row nor the record change remains.

5. **Configuration.** Set `AMOEBA_STORE_DIR` to a throwaway directory. With a scratch `projects.yaml` whose project has `answerer: {}`:

   ```
   amoeba start --project-config ./projects.yaml
   ```

   Observed (exit 7, `STARTUP_FAILED`):

   ```
   amoeba: project config <path> is invalid:
     - projects.scratch.answerer.answer_limit: Field required (got {})
     - projects.scratch.answerer.reserved_terms: Field required (got {})
   ```

   With `answer_limit: 0` and `reserved_terms: []`, the same command exits 7 with `projects.scratch.answerer.answer_limit: Input should be greater than or equal to 1 (got 0)`.

   **Do not run `amoeba start` with a valid config here:** it starts the resident process and does not return. Build the Runner through the factory instead, with `answer_limit: 2` and then with the `answerer` section removed (`build.py` sets `project_config_path` and calls `runner_tenant(settings, supervisor_dir)` with INFO logging on):

   ```
   uv run python build.py with.yaml ./sup1      # answer_limit: 2, reserved_terms: [merge to main]
   uv run python build.py without.yaml ./sup2   # no answerer section
   ```

   Observed with the installed `sq`: the first logs `sq probe passed: ...`, then `answering pipeline probe passed: `sq run --validate` exited 0`, then prints `BUILT`. The second logs only the `sq probe passed` line and prints `BUILT`: the answering probe does not run. If `sq` refuses the pipeline, the first prints `STARTUP_FAILED: answering pipeline probe failed: ...` instead.

6. **Nothing visible changed.** `tests/runner/test_tick_answering.py` (which now configures `answer_limit: 3`) shows a tick still declines an asked question `no_answer_on_file`, as after 141; 142's operation has no caller yet. To see the listing, seed two declined records in a throwaway store (a `no_answer_on_file` decline and a `reserved_term` decline with term `merge to main`, through `tests/question_harness.py`) and run:

   ```
   amoeba inspect questions --project demo
   ```

   Observed: both rows `state declined`. The first has `outcome no_answer_on_file` and an empty `reserved_term`; the second has `outcome reserved_term` and `reserved_term merge to main`. `--json` carries `"reserved_term": ""` and `"reserved_term": "merge to main"`.

## Risk Assessment

### Technical Risks

- **A second writer of the resolution slot.** If `submit_answer` filled the slot differently from `_apply_resolution`, the Runner would see two kinds of resume.
- **Extracting the submission insert** touches `apply_submission`, the inbox's one transaction.

### Mitigation Strategies

- Both writers call `_write_resolution` and `_insert_submission`, so the slot and the row are written by the same code.
- `apply_submission`'s existing suite, including its replay and rejection tests, must pass unchanged.

## Implementation Notes

### Development Approach

1. Extract `SubmissionWriter._insert_submission` and run the inbox suite.
2. Migration `014`, the two `DeclineReason` members, `GateRefusal`, `AnswerGate`, `AnswerOutcome` and `AnswerSubmission`, with the migration test.
3. `evaluate_gate` and `compose_instructions`, with the table test and the purity check.
4. `submit_answer`, with the outcome, race, count and crash tests.
5. `AnswererSettings` keys and load errors, then the probe wiring in `runner_tenant`.
6. The listing's `reserved_term`, then the contract docs.

Relative effort: 3.

### Special Considerations

- The answer is model output. It is stored and passed to `sq run --resume --instructions` as data, and never interpreted. It goes through the same argv path as the PM's instructions, which already handles arbitrary text.
- The reserved screen is not a security boundary. The hard bounds are the limit and the fact that the answerer can only resume a paused step with instructions (arch, "Recognising PM-reserved questions").
