---
docType: tasks
slice: answering-run
project: amoeba
lld: user/slices/144-slice.answering-run.md
dependencies:
- 140
- 141
- 142
- 143
projectState: Slices 120–132 and 140–143 are merged. The answering stage only settles
  pending records (`settle_pending_questions`, store only, no budget); its last branch
  declines `no_answer_on_file`. Migrations reach 014. No `sq_answer` kind, `begin_answering`,
  decide function or launch code exists. `AnswererSettings` holds four keys (142,
  143).
dateCreated: 20261103
dateUpdated: 20261103
status: complete
turns: 20
promptTokens: 1440889
cachedTokens: 1339771
cacheWriteTokens: 101078
completionTokens: 31148
durationSeconds: 221.9
costUsd: 0.850145
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.850146
    completionTokens: 31148
revision_number: 2
---

## Context Summary

- Working on the **answering-run** slice (144) of the question-answerer initiative (140 architecture). It makes the answerer answer: the stage settles finished answering runs, declines what it cannot answer, and launches one `sq run` of 140's pipeline per pending question, up to a cap. A pure function decides the result; a confirmed answer goes to 142's `submit_answer`, anything else is a distinct decline. Nothing retries.
- **Current state:** see `projectState`.
- **Dependencies:** 140 (pipeline path, `QuestionInput`, `prepare_scratch`, `read_answer`, `read_check`, `ArtifactProblem`), 141 (question record, `decline_question`, `pending_questions`, `settle_pending`), 142 (`submit_answer`, `evaluate_gate`, `compose_instructions`), 143 (`assemble_sources`, `render_passages`, `slice_label`, `PassageSet`, `check_citations`). 132/127/122 code is changed in one place: the supervisor's journal readers.
- **What this slice delivers:** `sq_answer` command kind and `supervision_entries`; done-guard change; migration `015`; `begin_answering`; four `AnswererSettings` keys; `decide.py`; `launch.py`, `finish.py` and the grown stage; the stub `sq` as the answering pipeline; listing columns; contract docs; the live tier.
- **Next planned work:** 145 (live walkthrough).

**Branch:** all implementation happens on `144-slice.answering-run`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/144-slice.answering-run.md` at the named decision (D1–D14), "Architecture", "API Contracts" or "Success Criteria". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/`, `docs/` or `project-documents/`. Keep every new or changed source file near 300 lines and each function near 50. Follow `.claude/rules/python.md`: ruff and strict pyright, `StrEnum` for vocabularies, no silent fallbacks, every `try/except` justified. Read each file you change before editing it, and read the return types of any function you call.

**Order and dependencies:** work tasks in file order. Each task leaves the full suite passing.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before the markers that follow source changes.

**Task-level facts** (checked against the code on 20261103):
- `store/journal_models.py`: `CommandKind`, `latest_run_entry(entries)` (line ~148). `store/journal.py`: `journal_issue` (line ~76). `store/sql_journal.py`: `SELECT_UNRESOLVED_ENTRY_FOR_NODE`.
- Readers to filter: `runner/resolutions/classify.py::classify`, `runner/supervise.py::run_to_resume`, `runner/dispatch/build_view.py::_facts_for`, `runner/dispatch/hold.py::checkout_holders`, `runner/ingest/record.py::_resume_count`. The resolution stage's `_answer` calls `classify`. `runner/dispatch/state.py::dispatch_state` receives what `_facts_for` passes.
- `process/supervisor.py::build_observer_registry(settings, claimed_run_ids, claimed_run_nodes)` returns `{CommandKind.SQ_RUN: …, CommandKind.CF_WRITE: …}`; the `SquadronRunIdObserver(...)` built inside `SquadronRunObserver` is the model for `SQ_ANSWER`.
- Questions: `store/questions.py::decline_question` (~165), `store/answer_submission.py::submit_answer` (~51), `store/question_models.py` (`DeclineReason`, `QUESTION_TRANSITIONS`), `store/sql_questions.py`, `store/mapping_questions.py`. Migrations are `store/schema/NNN_*.sql`, latest `014_answer_submission.sql`; `tests/test_migrations.py` covers them.
- Answering code: `runner/answering/{settle,stage,gate,inputs,artifacts,sources,passages,pipeline_file}.py`. `stage.py::settle_pending_questions(store, project_id, *, configured)` is called from `runner/tick.py` (~line 210) and from `tests/runner/test_tick_answering.py`. `settle.py::settle_pending` returns `Skip | Decline`; its last branch declines `NO_ANSWER_ON_FILE`.
- Scratch directories sit under the supervisor directory, outside any Context Forge project. That works only on squadron 0.24.16 or later (ecorkran/squadron#288: `sq run` checks Context Forge only when a step needs it). Earlier versions exit 1 from `cf get`. Verified 20261103 by running `answering.yaml` from an unregistered directory.
- Launch code to reuse: `runner/launch.py` (`spawn`, `build_argv`, `mint_run_id`, `log_paths`, `LaunchTracker`, `LaunchError`) and `runner/observe*.py` (`RunObserver`, `Finished`). Read them before Task 9.
- Tests: `tests/question_harness.py` (`seed_question`, `make_slice`), `tests/sq_stub.py` + `tests/sq_stub_scripts.py` (stub `sq`), `tests/runner/test_end_to_end.py`, `tests/runner/purity.py::io_use(module)`, `tests/runner/answering/` (sources repo fixture `sources_repo.py`), `tests/live/answering/` (`harness.py`, `conftest.py`, `test_precedence.py`).

---

## 1. Branch and baseline

- [x] **1.1 Create the slice branch and record the baseline**
  - [x] Run `cf config get git.integration_branch`. The result (or `main` if empty) is the target. Confirm you are on the target.
  - [x] Run `git checkout -b 144-slice.answering-run {target}`.
  - [x] Run `uv run pytest -q`, `uv run ruff check .` and `uv run pyright` once. Note any failures that exist before this slice.
  - [x] Success: on branch `144-slice.answering-run`, and the baseline result is known.

---

## 2. The `sq_answer` kind and the shared reader (D2, D3)

- [x] **2.1 `SQ_ANSWER` and `supervision_entries`** (`store/journal_models.py`)
  - [x] Add `CommandKind.SQ_ANSWER = "sq_answer"`. Add its required parameter keys `run_id`, `pipeline`, `params`, `scratch` wherever the other kinds' required keys are defined (follow how `sq_run` does it); add a `PARAM_SCRATCH` constant if the other keys have constants.
  - [x] Add `supervision_entries(entries) -> list[JournalEntry]`: the entries, in order, without `sq_answer`. Docstring: the single statement that answerer entries are not the slice's commands. Do not add `SQ_ANSWER` to `REVIEW_PRODUCING_KINDS`.
  - [x] Success: imports; typecheck passes.

- [x] **2.2 Switch the five readers to `supervision_entries`** (D3)
  - [x] `classify`: filter in the resolution stage's `_answer`, where it builds the `classify` input (D3). Deviate (filter inside `classify`) only if you find another `classify` caller, and say so in the commit message. Then `run_to_resume`, `_facts_for` (filter before `dispatch_state` and `latest_run_entry`), `checkout_holders`, `_resume_count`. One line each.
  - [x] Success: no other code changes; the existing suites for these readers pass unchanged (`uv run pytest tests/runner -q`).
  - Note: `checkout_holders` and `_resume_count` already filter by `kind == SQ_RUN`, so they needed no change; both are covered by assertions in `tests/runner/test_sq_answer_readers.py`.

- [x] **2.3 D3 acceptance test: reader cases** (`tests/runner/test_sq_answer_readers.py`)
  - [x] Build one slice journal: a paused `sq_run` with an open question block, plus an `sq_answer` in flight; then the same `sq_answer` resolved. For each of the two cases assert: `classify` is `RUN_TO_RESUME`; `run_to_resume` returns the `sq_run`; the checkout is held by that node; `dispatch_state` with an applied resume is `RESUME`; the resume count is unchanged.
  - [x] Add a test that an issuer's resolution of an `sq_answer` entry sets no `awaits_routing`, and that `tests/runner` code that builds `_run_entries` ignores `sq_answer` (never reaches `record_finished`).
    - Note: the `awaits_routing` half is done (`test_an_sq_answer_resolution_awaits_no_routing`). The `_run_entries` half is covered by `test_an_sq_answer_entry_never_reaches_record_finished` in `tests/runner/test_tick_answering.py`.
  - [x] Add a test of `supervision_entries` itself (order kept, only `sq_answer` removed, empty input).
  - [x] Each reader has its own assertion, so a missing filter in any one reader fails a test that names that reader.
  - [x] Success: tests pass.

- [x] **2.4 Done-guard ignores `sq_answer`** (D4, `store/sql_journal.py`)
  - [x] `SELECT_UNRESOLVED_ENTRY_FOR_NODE` gains `AND kind != '<sq_answer value>'`, with the value taken from `CommandKind` (build the SQL from the enum value, as neighbouring statements do for other kinds).
  - [x] Success: imports; existing journal tests pass.

- [x] **2.5 Tests for the done-guard** (`tests/test_journal.py` or the file that tests the guard today)
  - [x] Unresolved `sq_answer` on a node: `update_node_status(done)` succeeds and `record_runner_report(complete_node_id=…)` succeeds. Unresolved `sq_run` on the same node still refuses (existing behaviour kept).
  - [x] Success: tests pass.

- [x] **2.6 Recovery observer** (D2, `process/supervisor.py`)
  - [x] Register `CommandKind.SQ_ANSWER: SquadronRunIdObserver(...)` in `build_observer_registry` with the same settings as the `sq_run` one and no legacy matcher.
  - [x] Success: imports; typecheck passes.

- [x] **2.7 Tests for recovery** (`tests/test_recovery.py` or a new `tests/test_recovery_sq_answer.py`)
  - [x] An `sq_answer` entry whose run state is any in-flight state stays unresolved; `not_found` past the launch grace resolves it `not_applied`; an unreadable answer escalates `unknown` and writes no second block. Use the stub `sq` modes the existing `sq_run` recovery tests use.
  - [x] Success: tests pass; `uv run pytest -q` passes.

**Commit**: `feat: add sq_answer kind, shared supervision reader and recovery observer`

---

## 3. Migration `015` and the store types (D5, D8, D11, D14)

- [x] **3.1 Migration `015_answering_run.sql`** (`store/schema/`)
  - [x] Add the nine `question_records` columns of D11 (`answering_entry_id` referencing `command_journal(id)`, `source_commit`, `passage_index`, `dropped_pm_answers`, `proposed_answer`, `cited_passages`, `check_verdict`, `check_reason`, `decline_detail`), and the unique partial index on `answering_entry_id WHERE answering_entry_id IS NOT NULL`. No backfill. Bump the schema version wherever it is declared (follow how 014 was registered).
  - [x] Read `013_question_records.sql` and `014_answer_submission.sql` for a CHECK constraint or lookup table that lists decline reasons. If one exists, 015 must rebuild or extend it with the Task 3.3 reasons (SQLite cannot alter a CHECK in place; follow how earlier migrations rebuilt tables). If none exists, say so in the migration's header comment.
  - [x] Success: a fresh store opens at version 15.

- [x] **3.2 Migration test** (`tests/store/test_migration_015.py`, beside the 014 one)
  - [x] A 14 → 15 case: a store at 14 with a question record migrates; old rows hold nulls; a second record with the same non-null `answering_entry_id` is refused; two nulls are allowed.
  - [x] Success: tests pass; the feed invariant test still passes.

- [x] **3.3 Types** (`store/question_models.py`, `store/mapping_questions.py`, `store/sql_questions.py`)
  - [x] Add `DeclineReason` members from D8's table (`sources_too_large`, `sources_missing`, `sources_unreadable`, `answering_launch_failed`, `answering_run_failed`, `answering_run_stalled`, `answering_cost_cap`, `answering_run_orphaned`, `answer_discarded`, `artifact_missing`, `artifact_malformed`, `answerer_declined`, `uncited`, `unknown_citation`, `check_said_no`). Keep `no_answer_on_file`. Check each new value against any enum or CHECK constraint that lists reasons.
  - [x] Add frozen dataclasses `PassageRef(id, source, question_id, date)`, `AnsweringLaunch(node_id, run_id, parameters, source_commit, passages, dropped_pm_answers)`, `AnsweringEvidence(proposed_answer, cited, verdict, reason)` (all optional except what D7 always has), and `BeginOutcome` (`begun` with entry and record, `block_resolved`, `settled`) per the LLD's API Contracts.
  - [x] Add the nine new fields to `QuestionRecord` and its row mapping; JSON keys of `passage_index` are constants in `sql_questions.py`.
  - [x] Export the new names from `store/__init__.py`.
  - [x] Success: existing question tests pass with the wider record.

- [x] **3.4 Tests for the types** (`tests/store/`, beside the existing question tests)
  - [x] Round-trip a record holding all nine fields; a pre-015 record maps with `None`s; every new `DeclineReason` value is accepted by `decline_question`.
  - [x] Success: tests pass.

**Commit**: `feat: add migration 015 and answering types on the question record`

---

## 4. Store operations (D5, D9, D14)

- [x] **4.1 Extract `_insert_entry_within`** (`store/journal.py`)
  - [x] Pull the insert and required-key check out of `journal_issue` into `_insert_entry_within(connection, …)`, called by `journal_issue` unchanged in behaviour.
  - [x] Success: the journal suite passes unchanged.

- [x] **4.2 `begin_answering` and `question_for_answering_entry`** (new `store/answering.py`, mixin `AnsweringOperations`, wired into `Store`)
  - [x] `begin_answering(question_id, launch)`: one `BEGIN IMMEDIATE`. Read the record and its block. Not `pending` → `settled`; block resolved → `block_resolved`; both write nothing. Otherwise insert the `sq_answer` entry via `_insert_entry_within` and move the record to `answering` (checked against `QUESTION_TRANSITIONS`), setting `answering_entry_id`, `source_commit`, `passage_index`, `dropped_pm_answers`. Emit the same feed event the other transitions emit. Raises `QuestionNotFoundError`; a missing required parameter key raises `ValueError` before any write.
  - [x] `question_for_answering_entry(entry_id) -> QuestionRecord | None`.
  - [x] Success: imports; typecheck passes.

- [x] **4.3 Tests for the answering operations** (`tests/store/test_begin_answering.py`)
  - [x] `begun`: entry journaled with the four required keys, record `answering` and linked, feed event present, passage index stored without text.
  - [x] `settled` (record already answered by the PM) and `block_resolved`: nothing written, no entry.
  - [x] Missing parameter key: `ValueError`, nothing written. Unknown id: `QuestionNotFoundError`.
  - [x] Crash safety: inject a failure after the entry insert and before the state update; afterwards no entry exists and the record is `pending`.
  - [x] `question_for_answering_entry` returns the record, `None` for an unrelated entry.
  - [x] Success: tests pass.

- [x] **4.4 `evidence` and `detail` on the writers** (D9, D14)
  - [x] `decline_question(..., detail=None, evidence=None)` and `submit_answer(..., evidence=None)`: write `decline_detail` (bounded by the existing 132 bound; find it, do not invent one), `proposed_answer`, `cited_passages` (JSON), `check_verdict`, `check_reason` inside the operation's own transaction, on `submitted` and `declined` for `submit_answer`. Both keywords optional.
  - [x] Success: 141's and 142's suites pass unchanged.
  - Note: Deviation from the bound above. The store does not cut `detail` to the 132 bound. That bound (`STDERR_TAIL_LIMIT_BYTES` / `cut_to_bound`) is a Runner constant, and no store module imports the Runner. The store writes `detail` as given, and the Runner callers (`decide.py`, Task 6) cut it. The over-long-detail assertion moves to Task 6.2.

- [x] **4.5 Tests for the extended writers** (beside the 141/142 tests)
  - [x] Decline with detail and evidence stores all fields in one transaction; no evidence leaves the columns null.
  - [x] An over-long detail is cut to the bound. The cut happens in the Runner, not the store (see the 4.4 note); asserted in `test_a_detail_is_cut_to_the_bound` (Task 6.2).
  - [x] `submit_answer` with evidence on `submitted` stores `cited_passages` and the verdict while `answer` holds what was submitted; on the gate's `declined` outcome the evidence is also stored.
  - [x] A PM answer to an `answering` or `declined` record leaves the D11 columns as they were.
  - [x] Success: tests pass; `uv run pytest -q` passes.

**Commit**: `feat: add begin_answering and evidence on answer and decline writes`

---

## 5. Settings (D12)

- [x] **5.1 Four keys on `AnswererSettings`** (`runner/project_config.py`)
  - [x] Add required, default-free `answer_model` and `check_model` (stripped, non-blank, no `,`), `max_concurrent_runs` (`StrictInt`, ≥ 1) and `max_cost_usd` (positive number). Load errors name the key path. Update the class docstring ("eight keys").
  - [x] Success: imports; typecheck passes.

- [x] **5.2 Update fixtures and add config tests** (`tests/runner/test_project_config.py` and every test or helper that builds an `answerer` section; find them with `grep -rn "rules_paths" tests`)
  - [x] Add the four keys to every existing answerer fixture so existing suites pass.
  - [x] New cases: each key missing fails naming its path; blank model, model with a comma, `max_concurrent_runs` 0 or a float, `max_cost_usd` 0 or negative all fail; a valid section loads.
  - [x] Success: tests pass; `uv run pytest -q` passes.

**Commit**: `feat: require answer_model, check_model, max_concurrent_runs and max_cost_usd`

---

## 6. The decide function (D7, D8)

- [x] **6.1 `decide.py`** (new `runner/answering/decide.py`, pure)
  - [x] `RunSummary` built from a `Finished` value: launch failed, vanished, or ended with an outcome and its failure or checkpoint kind. Read `Finished` and `FailureKind` first; compare kinds only through the enums; an `UnknownKind` maps to `answering_run_failed` with the raw kind in the detail.
  - [x] `Confirmed(answer, cited, evidence)` and `Declined(reason, detail, evidence)`.
  - [x] `decide_answer(run, answer, check, passage_ids)` applies D7's six checks in order, first failure decides; every result carries the `AnsweringEvidence` gathered so far. Citations use 143's `check_citations(cited, passage_ids)`. The problem-to-reason maps (`ArtifactProblem` kinds, `CitationProblem` kinds, `SourcesProblemKind`, run outcomes) are each defined once, here. Details are cut to the bound from Task 4.4.
  - [x] Success: imports; typecheck passes.

- [x] **6.2 Table test and purity** (`tests/runner/answering/test_decide.py`)
  - [x] One parametrized row per D7 check and per D8 reason that `decide.py` produces: completed + all passes → `Confirmed`; failed with each failure kind (`provider_error`, `stall`, `cost_cap`, `artifact_missing`, unknown, absent); `paused`; `orphaned`; vanished; launch failed; each `ArtifactProblem` kind for each of the two files; answerer decline (even when the check said yes); `uncited`; `unknown_citation`; check `no`.
  - [x] Evidence is populated as far as the run got. Add `decide` to the purity check (`io_use` finds nothing).
  - [x] Success: tests pass.

**Commit**: `feat: add decide_answer`

---

## 7. The stub `sq` as the answering pipeline (D13)

- [x] **7.1 Teach the stub** (`tests/sq_stub.py`, `tests/sq_stub_scripts.py`)
  - [x] Read both files and the existing run modes. Add an answering mode: on `sq run <answering.yaml>` it writes scripted `answer.json` and `check.json` (or none, or malformed text) into its working directory, and reports a scripted outcome (completed, failed with a failure kind, paused, orphaned, never appearing) to `sq runs wait`. Reply shapes come from 140's parsers (`read_answer`, `read_check`); read `artifacts.py` for the exact file names and fields. Scripts are selectable per test without changing existing modes.
  - [x] Success: existing stub tests (`tests/test_sq_stub_run.py`, `tests/test_sq_stub_resume.py`) pass unchanged. The stub has no tests of its own: Tasks 8–11 drive it, and it commits with Task 8's tests.

---

## 8. Finish (D9)

- [x] **8.1 Record settlement** (new `runner/answering/finish.py`)
  - [x] `settle_run_result(record, entry, finished, …) -> question_outcome`: record not `answering`, or linked to another entry → `discarded`, record untouched. `answering` → read the reply files only if the run completed (`read_answer`, `read_check`), `decide_answer(..., record's passage ids)`. `Confirmed` → `submit_answer(..., instructions=compose_instructions(record.question, answer), detail=ANSWERER_DETAIL, evidence=…, gate=partial(evaluate_gate, answer=answer, settings=project.answerer))`; read 142's signature first. `Declined` → `decline_question(id, reason, detail, evidence)`. `submit_answer` outcomes `settled` and `block_resolved` write nothing further to the record. `ANSWERER_DETAIL` is a module constant; `question_outcome` values (`submitted`, `declined`, `block_resolved`, `settled`, `discarded`) are an enum.
  - [x] Success: imports; typecheck passes.
    Note: when a record is already settled for this very entry (crash re-entry), `settle_run_result` reports the earlier outcome (`submitted` or `declined`) instead of `discarded`. `discarded` is for a PM answer or for another entry.

- [x] **8.2 Tests for record settlement** (`tests/runner/answering/test_finish_answering.py`; seed an `answering` record through `begin_answering`, with the stub's paused run)
  - [x] Confirmed → record `answered` by the answerer with answer, `cited_passages`, verdict; the paused run is resumed (stub).
    Note: this task asserts the record, answer and evidence. The paused slice run actually being resumed is the Runner's later tick, asserted end-to-end in Task 11.1.
  - [x] Gate decline (answer limit / reserved term) → record `declined` with the gate's reason and evidence kept.
  - [x] One `Declined` case (check `no`) proves reason, `decline_detail` and evidence are stored. The reason mapping is covered by Task 6.2.
  - [x] PM answered first → record unchanged (`answered` by PM), outcome `discarded`. `block_resolved` and `settled` outcomes leave the record as the LLD says.
  - [x] Success: tests pass.

- [x] **8.3 `finish_answering`** (same module)
  - [x] `finish_answering(entry, finished, …)`: call `settle_run_result`, then `journal_resolve` with the result: run outcome, decision (`confirmed` or the decline reason) and `question_outcome`; `JournalOutcome` is `completed` when the run completed, else `failed`. Result keys are constants. Settle the record first, then resolve the entry.
  - [x] Success: imports; typecheck passes.

- [x] **8.4 Tests for `finish_answering`** (same test file)
  - [x] Entry resolved with the expected outcome and result keys for a submitted, a declined and a discarded case.
  - [x] Crash between settling and `journal_resolve`: finish again → no second submission or decline, entry resolved.
  - [x] Success: tests pass.

**Commit**: `feat: finish an answering run into a submission or a decline` (includes the stub `sq` answering mode from Task 7)

---

## 9. Launch (D6, D8, D10)

- [x] **9.1 Pre-journal steps** (new `runner/answering/launch.py`)
  - [x] `prepare_launch(record, …)` per the LLD data flow: `assemble_sources` (a budget refusal returns "stop launching this tick"; a `SourcesProblem` → `decline_question(reason=sources_*, detail)`), mint the run id, make `<supervisor_dir>/answering/<run_id>/` (exclusive `mkdir`), `prepare_scratch(scratch, QuestionInput(slice_label, question), render_passages, max_cost_usd)`, build the argv with `build_argv(str(answering_pipeline_path()), run_id, {answer-model, check-model})` using 140's param-name constants. `OSError` from `mkdir` or `prepare_scratch` is caught at those two calls, with a comment saying why, and declines `answering_launch_failed` with the error as detail on the still-`pending` record. `prepare_scratch`'s `ValueError` is not caught.
  - [x] Success: imports; typecheck passes.

- [x] **9.2 Tests for the pre-journal steps** (`tests/runner/answering/test_launch_prepare.py`, with a real throwaway store and 143's sources repo fixture)
  - [x] Scratch directory exists under the supervisor directory and holds the prepared inputs; `.squadron.toml` carries the configured `max_cost_usd`; argv has the pipeline path, run id and both models and no positional slice.
    Note: there is no `slice` key and no positional slice. The argv is `sq run <pipeline> <answer-model> --run-id <id> -p check-model=<alias>`: the answer model is the positional target (see the next note).
    Note: the real `sq` rejects a required param given by `-p`, so the answer model is the positional target of the answering run and the check model stays `-p check-model=…` (fix commit "fix: pass the answer model as the positional target of the answering run"). The "no positional slice" text above still holds: the positional is the answer model, not a slice.
  - [x] Each `SourcesProblemKind` → matching decline reason, no directory, no entry. A budget refusal → record stays `pending`, no directory.
  - [x] `OSError` on `mkdir` and on `prepare_scratch` (read-only parent / monkeypatched) → `answering_launch_failed`, no entry, no relaunch on a second call.
    Note: "no relaunch on a second call" is asserted as the declined question no longer being in `pending_questions`, which is what the stage iterates, rather than by calling launch twice with a stale record.
  - [x] Success: tests pass.

- [x] **9.3 `launch_answering`** (same module)
  - [x] `launch_answering(record, …)`: `prepare_launch`, then `begin_answering`; outcomes `block_resolved` and `settled` write nothing and end this record's launch. Then `spawn(argv, scratch, log_paths(supervisor_dir, entry.id), popen)` with no checkout lookup, branch check or hold. A `LaunchError` from `spawn` goes to Task 8's `finish_answering` with a launch-failed value (use the `Finished` form the observer already has for a failed launch). On success, `tracker.track(entry.id, child)`.
  - [x] Success: imports; typecheck passes.

- [x] **9.4 Tests for `launch_answering`** (`tests/runner/answering/test_launch_answering.py`)
  - [x] Happy path: one `sq_answer` entry with the four keys; record `answering` and linked; the spawn's cwd is the scratch directory; the child is tracked.
  - [x] Spawn failure → entry resolved and question declined `answering_launch_failed`, never relaunched.
  - [x] Block resolved between the read and `begin_answering` → no entry, no process, record unchanged.
  - [x] Success: tests pass.

**Commit**: `feat: launch an answering run from a scratch directory`

---

## 10. The stage and the tick (D10)

- [x] **10.1 Observe pass** (`runner/answering/stage.py`, grown; put the passes in a second module if the file passes ~300 lines)
  - [x] Add one helper, `unresolved_answering_entries(store, project_id)`, in `runner/answering/stage.py`: `Store.unresolved_journal_entries(project_id)` (`store/journal.py` ~line 289) filtered to `CommandKind.SQ_ANSWER`. The observe pass (here) and the concurrency cap (10.5) both call it, so the cap always counts the set being observed.
  - [x] `AnsweringStage` with the observe pass: unresolved `sq_answer` entries go to `RunObserver.observe` (polls take the budget; node context set per entry); each finished → `finish_answering`. Returns whether it was cut off. Nothing calls it yet; `settle_pending_questions` stays in place.
  - [x] Success: imports; typecheck passes.

- [x] **10.2 Tests for the observe pass** (`tests/runner/answering/test_stage_observe.py`, stub `sq`)
  - [x] A finished run is finished; an in-flight run is left; budget spent → no poll, `CUT_OFF` reported, but an already-observed finished run is still finished; a poll fault is raised against its node.
  - [x] Success: tests pass.

- [x] **10.3 Stranded pass** (same module)
  - [x] `answering` records whose entry is resolved and whose block does not await the Runner are declined by the entry's outcome: `not_applied`/`unknown` → `answering_run_failed` with the outcome in the detail; stage-resolved/discarded → `answer_discarded`. A block awaiting the Runner is skipped. Runs with the node context cleared (141 D5; read how `tick.py` sets this up).
  - [x] Success: imports; typecheck passes.

- [x] **10.4 Tests for the stranded pass** (`tests/runner/answering/test_stage_stranded.py`)
  - [x] Entry resolved `not_applied` → `answering_run_failed`; entry resolved by the stage → `answer_discarded`; block awaiting the Runner → skipped.
  - [x] Success: tests pass.

- [x] **10.5 Pending pass, `Launch` branch and tick wiring** (`runner/answering/settle.py`, `stage.py`, `runner/tick.py` ~line 210). These change together so the suite stays green.
  - [x] `settle.py`: add a `Launch` dataclass; the last branch returns `Launch()` instead of `Decline(NO_ANSWER_ON_FILE)` (D14). Update the docstring. Keep `no_answer_on_file` in the enum. Update 141's settle tests in `tests/runner/answering/test_settle.py`.
  - [x] `stage.py`: the pending pass replaces `settle_pending_questions`. For each pending record, oldest first, `settle_pending` → `Skip` | `Decline` | `Launch`. A `Launch` runs `launch_answering` only while unresolved `sq_answer` entries < `max_concurrent_runs` and the budget allows; a budget refusal stops the pass. Store-only declines run even when the budget is spent. Settling and launching run with the node context cleared. Stage order: observe, stranded, pending. Returns whether it cut off and whether it wrote.
  - [x] `tick.py`: call the stage where `settle_pending_questions` was called (after `record_finished` and the `shape_error` check). The tick returns `CUT_OFF` if the probes or the stage cut off. Update `tests/runner/test_tick_answering.py`'s import, call and any `no_answer_on_file` expectation.
  - Note: test_tick_answering's `no_answer_on_file` test became a configured-answerer question-missing test, since an empty answerer section now launches. It is `test_a_configured_answerer_still_declines_a_question_with_no_text`.
  - [x] Success: imports; typecheck passes; `uv run pytest -q` passes.

- [x] **10.6 Tests for the pending pass** (`tests/runner/answering/test_stage_pending.py`, stub `sq`)
  - [x] Cap: three pending questions, `max_concurrent_runs` 2 → two `sq_answer` entries, one record still `pending`; once a run finishes, the third launches on a later tick (in the same tick if the observe pass frees the slot first).
  - [x] Order: oldest first. Budget spent: no spawn, a declinable pending record is still declined, `CUT_OFF` reported. A finish fault or launch fault escalates per project, not per node.
  - [x] Success: tests pass.

- [x] **10.7 Tick-level tests** (`tests/runner/test_tick_answering.py`)
  - [x] Stage runs after `record_finished`; `CUT_OFF` propagates; a project with no `answerer` section still declines `answerer_not_configured` and journals no `sq_answer`; `sq_answer` is never passed to `record_finished`.
  - [x] Success: tests pass; `uv run pytest -q` passes.

**Commit**: `feat: run the answering stage in the tick with a concurrency cap`

---

## 11. End to end on the stub tier (D3, D13)

- [x] **11.1 Answered and decline cases** (`tests/runner/test_end_to_end_answering.py`, `-k answering`)
  - [x] A question-paused slice gets one `sq_answer` and a resume with `sq run --resume` whose instructions restate the question; the record is `answered` by the answerer with `cited_passages`, `passage_index`, `source_commit`, `check_verdict yes`, `answering_entry_id`; the entry's `run_id` is the launched run.
  - [x] One decline (check `no`) end to end: declined once, never relaunched on a later tick, and the block shows `question_state declined` and the reason. Other reasons are covered by Tasks 6.2, 8.2 and 9.2.
  - [x] Success: tests pass.

- [x] **11.2 Race and recovery cases** (same file)
  - [x] PM answers while the run is in flight → PM's resolution accepted (D3), the run resumes by the PM's answer; the run's later result resolves the entry and the record stays `answered` by the PM. Answerer's resolution accepted after the run ends. PM answers before `begin_answering` → no run starts. PM answers between the read and `begin_answering` → no run starts.
  - [x] A resumed run completes while the slice's `sq_answer` is still in flight → node marked done without a fault (D4).
  - [x] Restart with a run in flight → adopted by run id, polled to its end, no second launch. Crash between `begin_answering` and the spawn → after recovery the question is declined `answering_run_failed`.
  - [x] No answerer section → no `sq_answer` ever journaled.
  - [x] Success: tests pass; 132's, 127's and 141–143's suites pass.

  Note: the tests live in `tests/runner/test_end_to_end_answering.py` rather than `tests/runner/test_end_to_end.py`, which is already over 300 lines. Select them with `-k answering`.
  Note: the e2e fixture commits a rules file and a plan file into the world checkout, because the sources reader needs `project-documents/user` at the target commit.
  Note: stable over three repeated runs; full suite 4343 passed; ruff and pyright clean.

**Commit**: `test: add answering end-to-end, race and recovery cases on the stub`

---

## 12. Inspection and contracts (D11)

- [x] **12.1 Listing columns** (`inspection/questions.py`, and the server route if it shares the model)
  - [x] `questions` gains `answering_run_id` (joined through the entry), `check_verdict`, `decline_detail`; `--json` and the server carry every D11 column. Read the module first and follow how current columns are added.
  - [x] Success: imports; typecheck passes.

- [x] **12.2 Tests for the listing** (`tests/inspection/`, beside the existing questions tests)
  - [x] An answered record shows the run id, verdict and citations; a declined record shows `decline_detail` and `proposed_answer`; a pre-015 record lists with empty values; `--json` holds the passage index with source and date.
  - [x] The server's questions response (beside the existing tests in `tests/serve/`) carries the same columns for an answered and a declined record.
  - [x] Success: tests pass.

**Commit**: `feat: add answering columns to the question listing`

- [x] **12.3 Docs** (`docs/store-contract.md`, `docs/process-contract.md`)
  - [x] Store contract: new "Answering runs" subsection under "Question records" (the methods table from the LLD), the `sq_answer` kind and its required keys in the journal section, the done-guard exclusion, and the latest migration moved to `015`.
  - [x] Process contract: the `sq_answer` kind, the scratch layout under the supervisor directory, the four answerer keys with their example values (and the note that existing answerer sections fail at load until they add them), and the stage's place in the tick. Remove or amend text saying the answering stage starts no subprocess.
  - [x] Amend the architecture's "Cost and configuration" and the slice plan's 144 entry per D1 (the pipeline is not a configuration key): edit `user/architecture/140-slices.question-answerer.md` and the slice plan file that lists 144, changing only that sentence.
    Note: the architecture's "Cost and configuration" (`user/architecture/140-arch.question-answerer.md`, line ~126) and the slice plan's 144 entry (`user/architecture/140-slices.question-answerer.md`, line ~106) already carried the D1 sentence (the pipeline is not a configuration key), so no edit was needed there.
  - [x] Success: the docs describe the shipped behaviour; `uv run pytest -q` passes (including any docs/contract tests).

**Commit**: `docs: document answering runs`

---

## 13. Final validation

- [x] **13.1 Full validation pass**
  - [x] Run `uv run ruff format .`, then `uv run ruff check .`, `uv run pyright` and `uv run pytest -q` once each and read the output.
  - [x] Confirm against the LLD's Success Criteria: the purity check covers `decide` and `settle`; the migration test covers 14 → 15; the feed invariant test passes; no source file is far over 300 lines.
  - [x] Walk the LLD's Verification Walkthrough steps 1, 3 and 4 with the stub (step 2 waits on Task 14).
  - [x] Success: all checks pass.

**Commit**: `fix: resolve issues found in slice 144 validation` (only if the pass changed files; otherwise no commit)

---

## 14. Live tier (D13)

- [x] **14.1 Inline question tails** (`tests/live/answering/question_tails.py`)
  - [x] The question text for each live case is written inline, shaped like Squadron's tail (at most `QUESTION_TAIL_CHARS`, which may start mid-sentence). The live tier tests what the models make of the wording, not where the wording came from, so no capture from a real question-paused run is needed.
  - [x] Success: a test in the normal suite (`tests/runner/answering/test_live_tier_rules.py`) asserts every tail fits the bound.
  - Note: this task first required copying real `checkpoint.question` values from `sq runs wait` output. That was a step for the Project Manager and was removed.

- [x] **14.2 Live cases** (`tests/live/answering/test_answering_run.py`, using `stage_harness.py` and 140's opt-in variables `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL`, `AMOEBA_LIVE_MAX_COST_USD`)
  - [x] Plan passage: a question answered from a rules passage is answered by the answerer, and its block holds the resolution.
  - [x] PM precedent: a question repeating a PM answer in other words is answered on the same slice; another slice with the same meaning (the PM's answer given as a convention for every slice) is answered; asked for a slice where the answer differs (a PM answer reserved for one slice) it is declined.
  - [x] Each case runs the real stage from `assemble_sources` (against 143's fixture repository, `cf` faked and git real) through the real `sq` and real models to the record's final state in a throwaway store; runs once; a wrong result fails the test, nothing retries.
  - [x] Success: with the variables, a squadron 0.24.16 install and provider keys, all four pass (20261103: glm-flash and deepseek4-flash, 59 seconds). Without the variables a bare `uv run pytest` ignores `tests/live`, and `uv run pytest tests/live` fails at collection naming the variable, as 140's live-tier rules require.
  - Note: the first cross-slice case reused the PM answer "Yes. Use ISO 8601 in UTC on every line." and the answerer correctly declined to carry a one-slice answer to another slice. The case now uses an answer given for every slice.

**Commit**: `test: add live answering-run cases`
