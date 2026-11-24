---
docType: tasks
slice: local-work-through-the-hub
project: amoeba
lld: user/slices/262-slice.local-work-through-the-hub.md
dependencies:
- 260-slice.hub-and-door
- 261-slice.members-by-name
projectState: Slices 220 to 244, 260 and 261 are merged on main. Package version 0.2.9,
  store schema 12 (migrations 001 to 012). The door serves 261's operations; handle-pause
  and wake-run refuse on a joined machine with NotServedError; held questions are
  started by request_release through wiring_release.start_after after seven operations.
  sq 0.24.38 and cf 0.19.28, read with `sq --version` and `cf --version` on 20261123 and again at the second revision the same day.
dateCreated: 20261123
dateUpdated: 20261124
status: not_started
turns: 49
promptTokens: 6201502
cachedTokens: 5998458
cacheWriteTokens: 202952
completionTokens: 67278
durationSeconds: 598.5
costUsd: 4.169533
usageRounds: 2
pricedRounds: 2
usageByModel:
  claude-opus-5-5:
    rounds: 2
    costUsd: 4.1695329999999995
    completionTokens: 67278
revision_number: 1
---

# Tasks: Local Work Through the Hub

## Context Summary

- Working on slice 262 (design: `user/slices/262-slice.local-work-through-the-hub.md`; decisions D1 to D16 are cited by number, success criteria by their text). Every store transaction that `handle-pause`, the resume and the wake wrapper make becomes one **step**: a plain function in `operations.steps`, run in process on the local store (`LocalSteps`) or as one door call (`DoorSteps`). Every done reply carries a **work flag**; a client that sees it calls `claim_work` and starts what it gets detached. `answer` and `send` with waking are served. Next slice: 263 (`amoeba-mcp` as a client, its tick).
- **Precondition: 260 and 261 are merged on the target.** Checked at breakdown on 20261123: schema 12, and every name below exists. This file uses their names: `wire.protocol` (`SERVED_OPERATIONS`, `WRITING_CALLS`, `UNKNOWN_ADVICE`, `HELLO_CALL`, `MAX_CALL_BYTES`), `wire.times` (`DOOR_VERSION`, `CALL_BOUND_SECONDS`), `operations/served.py` (`run_served`), `operations/served_types.py` (`ServedEdges`), `operations/errors.py` (`OPERATION_ERRORS`, `CallRefused`), `operations/caller.py` (`find_caller`, `find_member`), `operations/here.py`, `operations/run_gather.py`, `operations/runs_document.py`, `operations/wake_door.py` (261's wake refusal, deleted in 5.1), `hub/calls.py` (`handle_call`, `DoorHooks`), `hub/admin.py` (`rm_machine`), `store/store.py` (`call_scope`, `act_as`), `operations/state_move.py` (`open_state_store`), `hub/store_open.py` (`open_hub_store`), `wiring_door.py` (`refuse_if_joined`, `NotServedError`, `route`), `client/errors.py` (`ClientFileError`, `HubUnreachableError`, `HubRefusedError`), `tests/hub/in_process_hub.py`, `tests/hub_fixture.py` (`two_machine_hub`), `tests/load/test_door_load.py`.
- Paths: no prefix means under `src/amoeba/`. `tests/`, `docs/`, `scripts/` are from the repo root; `user/` means `project-documents/user/`.
- New modules (Component Structure): `operations/steps/` (`__init__`, `models`, `limits`, `pause`, `resume`, `wake`, `open_runs`, `work`, `dispatch`), `operations/store_steps.py`, `operations/work_start.py`, `operations/resume_run.py`, `wiring_steps.py`, `cli/resume_command.py`, `store/schema/013_local_work.sql`. Added by this breakdown: `operations/resume_attempt.py` (the attempt file, 3.3), `hub/call_work.py` (the flag in a done reply, 7.2), `store/sql_local_work.py` (1.2), `tests/store/schema_12.py` (1.4). Renamed: `tests/test_wiring_release.py` to `tests/test_after_step.py` (6.6). Deleted: `operations/request_release.py`, `wiring_release.py` (6.6), `operations/wake_door.py` (5.1).
- Size: `store/sql.py` (543 lines) gets edits to existing statements only (the inserts that bind a machine, `RECORD_RESUME` clearing the claim id; `MARK_RESUME_STARTED` is deleted in 2.3); new statements on questions and answers go in `store/sql_local_work.py`, on wakes in `sql_wakes.py`, on held rows in `sql_held.py`. `store/answers.py` (296) gets only the claim-id clause in `record_resume`; `claim_resume` lives in `steps/resume.py`. `hub/calls.py` (326) and `wiring.py` (297) get call sites only; the logic goes in `hub/call_work.py` and `wiring_steps.py`.
- Order: each commit leaves the suite passing on the local store. Until section 7 only `LocalSteps` exists, and `handle-pause` and `wake-run` keep `refuse_if_joined`; 7.4 removes it.
- Closed values are defined once and imported: `pause_claim_seconds`, `resume_claim_seconds`, `MAX_AUTOMATIC_STARTS` (3), `MAX_WORK_PER_CLAIM` (5) in `steps.limits`; step names, writing flags and config needs in `STEP_MODELS`, the names and writing flags mirrored as strings in `wire.protocol.STEP_CALLS` and `WRITING_STEPS` with a test that they agree; body keys `via`, `logs_dir`; reply keys `work`, `work_problem`; the `runs` document's `absent_runs`; the new enum values.
- Clocks (D2): a step takes the clock it is given and passes it to the store functions, whose signatures stay. No step request carries a date or time field. The client's clock only names files and measures its own waits.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.2.
- Tests use the autouse `AMOEBA_HOME` fixture, `tests/store/seed.py`, `tests/store_open.py`, `tests/cf_stub.py`, `tests/sq_stub.py` with `tests/sq_stub_resume.py`, `tests/fault_injection.py`, `tests/hub/in_process_hub.py` (`DoorHooks`, the rig's settable clock) and `tests/hub_fixture.py`. Destructive SQL runs only against throwaway stores.
- **Existing tests.** In the task that makes a change, update mechanically every test that builds a changed type, calls a changed signature, patches a moved or deleted name, or pins a set, count or text the change alters, without changing what it asserts; note the modules touched under the task. A test that built a `Store` for a client-run function builds `LocalSteps` on it. Beyond that, two groups of tests change what they assert, each named in its task: the design's five kinds of edit (Migration Plan): the stale age and resume bound (2.2, 4.5), `start_after`'s seven operations (6.6), the sweep split (4.5), and the answering-run skip (4.6); and the tests that pin a behavior this slice reverses by design: the first-poll refusal (3.4), the send timing figure (6.5), a refusal or version (5.1, 7.1, 7.4). If any other test fails, fix the code, not the test.
- `tests/test_contract_docs.py` requires each new column, value, flag and field in the contract docs, so the task that adds one adds its entry; 9.2 writes the prose.
- Production state: no task writes the live store or config. Migration 013 rides the next release through `scripts/update_live.py update` (D14); 9.3 tests the script on copies.
- Work on branch `262-slice.local-work-through-the-hub` (0.2). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup (effort 1)

- [ ] **0.1 Target and prerequisites**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`. The design and this task file are committed there, with no other uncommitted change
  - [ ] Confirm 260 and 261 are merged: `store/schema/012_members_by_name.sql` exists, `EXPECTED_SCHEMA_VERSION` is 12, and each name in the Context Summary's precondition exists (`grep -rn`)
  - [ ] Confirm the files this slice edits exist: the modules in Component Structure's "Change" rows, `scripts/update_live.py`, `tests/scripts/test_update_live.py`, `tests/store/test_vocabulary_pinning.py`, `tests/test_import_boundaries.py`, `tests/test_wiring_release.py`, `tests/operations/test_question_sweep.py`, `tests/operations/test_pause_eligibility.py`, `tests/operations/test_pause_claim_held.py`, `tests/live/hold/`, `tests/live/waking/`
  - [ ] Run `sq --version` and `cf --version` and note both
  - [ ] Success: the target is checked out and clean; a note gives the target and both versions
  - If a prerequisite is missing, write `BLOCKED: <what is missing>` under this task and stop.
- [ ] **0.2 Branch and baseline**
  - [ ] `git checkout -b 262-slice.local-work-through-the-hub {target}`; if it exists, `git checkout 262-slice.local-work-through-the-hub`
  - [ ] Run the checks once; list any failure present before this slice by test name, unfixed
  - [ ] Success: `git branch --show-current` prints the slice branch; the baseline is noted

## 1. Migration 013 and the machine on rows (D14; effort 4)

- [ ] **1.1 `store/schema/013_local_work.sql` and the new values**
  - [ ] `store/vocabulary.py`: `ClosedReason.MACHINE_REMOVED` and `WakeOutcome.MACHINE_REMOVED` (`machine_removed`). `answering/values.py`: `DeclineReason.STARTS_EXHAUSTED` (`starts_exhausted`). Each with its display text where the enum has one
  - [ ] Rebuild `questions` and `wakes` (SQLite cannot widen a `CHECK`), carrying every column, index and trigger each has at schema 12, 260's owner column and trigger included. Order: create the new table, copy, drop, rename, then the machine triggers (a trigger fires on `INSERT ... SELECT`)
  - [ ] `questions.machine_id` and `wakes.machine_id`, nullable, referencing `machines`; `closed_reason` and `outcome` `CHECK` lists gain `machine_removed`; an index on `questions(machine_id, state)` and on `wakes(machine_id)`
  - [ ] `answers.resume_claim_id TEXT` (null) and `answers.resume_start_count INTEGER NOT NULL DEFAULT 0`; `questions.start_count INTEGER NOT NULL DEFAULT 0`; `messages.wake_wanted_at` timestamp, null
  - [ ] A `BEFORE INSERT` trigger on `questions` and on `wakes` that aborts when `machine_id` is null, worded like 260's owner triggers
  - [ ] `EXPECTED_SCHEMA_VERSION` becomes 13. Update the schema-version pins, `tests/store/test_migration_012.py`'s `== 12` among them
  - [ ] `COLUMN_REASONS` in `tests/store/test_schema_holds_no_mirrored_state.py`, using its existing reasons: `questions.machine_id`, `questions.start_count`, `answers.resume_claim_id`, `answers.resume_start_count` under `record` (beside `questions.start_attempted_at` and `answers.resume_started_at`); `wakes.machine_id` under `waking`; `messages.wake_wanted_at` under `messages`. Add each to the same reason's bullet in `docs/store-contract.md`
  - [ ] `docs/store-contract.md`: the six columns, two indexes, two triggers and the three new values
- [ ] **1.2 Store inserts bind the acting machine**
  - [ ] `insert_question`, `insert_held` (`store/questions.py`, `store/held_questions.py`) and `claim_wake` (`store/wakes.py`) bind `machine_id` from the store's acting machine (260 D12), with no new parameter
  - [ ] Reads by machine: open questions on a machine and a question's machine name in the new `store/sql_local_work.py`; wakes on a machine in `sql_wakes.py`; held rows on a machine in `sql_held.py`. Statements only; callers come in later tasks
- [ ] **1.3 The opener gives old rows `local`**
  - [ ] `open_state_store`, after `act_as_local`, reads for one question or wake with a null machine and, when there is one, sets all of them to `local` in one write. `open_hub_store` does not (D14)
- [ ] **1.4 Migration tests** (`tests/store/test_migration_013.py`, helper `tests/store/schema_12.py` modeled on `schema_11.py`)
  - [ ] A schema-12 store holding question, answer and wake rows migrates: row counts unchanged; every column, index and trigger of both rebuilt tables present (compare `sqlite_master` before and after)
  - [ ] An insert with a null machine is refused on both tables; `machine_removed` accepted in both `CHECK`s; `tests/store/test_vocabulary_pinning.py` passes with the new values
  - [ ] Opening the migrated store with `open_state_store` gives old rows `local`; a second open writes nothing (the read finds no row)
  - [ ] Tests that raw-insert into `questions` or `wakes` after migrating to the latest version (`tests/store/test_migrations.py`, and any other `grep -rn "INSERT INTO questions\|INSERT INTO wakes" tests` finds) insert a `machines` row first where none exists and bind its `machine_id`; inserts made before the store reaches 13 are unchanged
  - [ ] Inserts through the store functions carry the acting machine; a stored question and wake carry `local`
  - [ ] Success: checks pass

**Commit**: `feat: add migration 013 with the machine on questions and wakes`

## 2. Limits, the resume claim and the wake rule (D5, D6, D8; effort 3)

- [ ] **2.1 `operations/steps/limits.py`**
  - [ ] `pause_claim_seconds(config)` = `answering_wait_seconds + 2 * CALL_BOUND_SECONDS`; `resume_claim_seconds(config)` = today's `resume_bound_seconds` with `2 * CALL_BOUND_SECONDS` in place of its one store wait; `MAX_AUTOMATIC_STARTS = 3`; `MAX_WORK_PER_CLAIM = 5` (replaces `MAX_STARTS_PER_CALL`, which 6.6 deletes)
  - [ ] Every place that judges a claim stale at `answering_wait_seconds` uses `pause_claim_seconds`: the limit `handle_pause` passes to `pause_class.classify_pause`, the limit `status` passes to `status_runs.classify_runs`, and `question_sweep._judge`'s claimed-row age. `answering_wait_seconds` stays the answering run's own wait (`pause_claim`, `pause_existing`) and the least time between two starts of one row
  - [ ] `docs/config-contract.md`: the two limits and what they are worked out from; the `answering_wait_seconds` row no longer says it is the dead-claim age
- [ ] **2.2 Limit tests**
  - [ ] With the starter config, `resume_claim_seconds` is 216.5 and `pause_claim_seconds` is `answering_wait_seconds + 86`
  - [ ] Design-allowed edit: the tests that pin the stale age at `answering_wait_seconds` use `pause_claim_seconds`: `tests/operations/test_every_state_exits.py::test_claimed_exits_by_the_sweep_once_it_is_old_enough` and `tests/operations/test_question_sweep.py::test_an_old_claim_closes_and_a_young_one_stays`. `test_pause_class.py` and `test_status_runs.py` pass their own `LIMIT` and are unchanged here (4.6 moves the `classify_pause` ones). The resume-bound pins change with the close sweep (4.5)
  - [ ] A claim at `pause_claim_seconds - 1` is young; at `pause_claim_seconds` it is stale, in `classify_pause`, `classify_runs` and the sweep
- [ ] **2.3 `steps/resume.claim_resume` and `record_resume`**
  - [ ] `claim_resume(transaction, answer, now, limit)`: one `UPDATE` that sets `resume_started_at` to `now` and `resume_claim_id` to a new `uuid4().hex`, applied only when the outcome is not final (`resumed`, `not_delivered`) and the claim id is null or `resume_started_at` is older than `resume_claim_seconds`; returns the claim id or why it lost (in flight, final outcome stored)
  - [ ] `record_resume` writes the outcome unless one is final (as today), clears `resume_claim_id` only when it equals the caller's, and returns what the store holds
  - [ ] `mark_resume_started` and `MARK_RESUME_STARTED` are deleted; `claim_resume` replaces them at every caller: `operations/resume.py` (moved onto steps in 3.3), the re-export in `store/questions.py`, and the tests `tests/operations/test_question_sweep.py`, `tests/operations/test_dismiss.py`, `tests/store/test_question_closing.py` (its `test_mark_resume_started_is_refused_once_the_outcome_is_final` becomes 2.4's final-outcome case)
- [ ] **2.4 Resume-claim tests**, one per row of D6's rules
  - [ ] Free claim taken; a claim in flight refused; a claim older than `resume_claim_seconds` retaken, and not one second before; a final outcome never claimed; a `refused` outcome claimable
  - [ ] A late `record_resume` from a claim that ran out records its outcome and does not clear the newer claim
  - [ ] Three threads claim one answer at once on a throwaway store: one wins
- [ ] **2.5 The wake mark and `wake_due`**
  - [ ] `send` (local way, today's code path) sets `messages.wake_wanted_at` to its clock when the request is `open` after the call and today's three conditions hold (D8 rule 1); a send while a session is live sets none
  - [ ] `wake_due(transaction, member, now, limits, scope)` in `store/wakes.py`, replacing `can_wake` and keeping its `WakeScope` parameter (`ACTING_MACHINE` for a claim here, `ALL_MACHINES` for 5.1's "due elsewhere"). It lives in the store, not `steps/wake.py`, because `claim_wake` must call it and `store` may not import `operations` (`tests/test_import_boundaries.py`); steps import it from there. Update D8's `steps.wake.wake_due` to `store.wakes.wake_due` in the design under the small-conflict rule, noted here. Rules 1 to 3 of D8. Rule 2 counts any wake of the member claimed at or after the mark (the mark's own time included), and any row with a pid; an unended row with no pid past its deadline does not count. Rule 3 is 244's check, reading every `sessions` row of the member whatever its machine
  - [ ] `claim_wake` calls `wake_due` in its own transaction; `can_wake` is replaced by `wake_due` at every caller
- [ ] **2.6 Wake-rule tests**, one per rule and per D8 case
  - [ ] No mark, not due; mark and no wake since, due; a wake claimed at the mark's own time is that mark's wake; a row with a pid, unended past its deadline, does not hold off a newer mark and is still its own mark's wake; an unended no-pid row past its deadline lets the mark be due again
  - [ ] A live session row for the member on another machine: not due. A `start_failed` wake: not due again for that mark. Sent again unchanged once the session is stale: a new mark, due
  - [ ] Existing 244 wake tests pass unchanged apart from the renamed function
  - [ ] Success: checks pass

**Commit**: `feat: add the claim limits, the resume claim and the wake-due rule`

## 3. Steps, `LocalSteps`, the resume and `answer` (D3, D6, D7; effort 4)

- [ ] **3.1 The step machinery**
  - [ ] `steps/models.py`: a frozen Pydantic request and reply model per step and `STEP_MODELS`, the one table from step name to its request model, reply model, whether it writes, and whether it needs the config (false for `resume_record`, `wake_set_pid`, `wake_finish`, D10). Rows are added as each step is written
  - [ ] `steps/dispatch.run_step(name, store, document, edges)`: validates the document against the request model, runs the step function in its own transaction (`store.write()` for a writing step, `store.read()` otherwise), returns the reply model. `edges` carries config, clock and the acting machine
  - [ ] `operations/store_steps.py`: the `Steps` protocol (`run(step, request) -> reply`) and `LocalSteps`, which calls `run_step` on the local store
  - [ ] `tests/test_import_boundaries.py`: the client-run modules (`handle_pause`, the `pause_*` modules, `claim_waiting`, `answering_settle`, `resume`, `resume_run`, `wake_run`, `prune`, `work_start`) import no `amoeba.store.store`; `operations.steps` imports no module that runs `cf`, `sq` or `git`, and nothing from `amoeba.answering` that reads a file. Rules for modules not yet moved are added in the task that moves them
- [ ] **3.2 Machinery tests**
  - [ ] A test walks every request model in `STEP_MODELS` and asserts no field is a date or time type (criterion: no step request model has a date or time field)
  - [ ] `run_step` refuses a document that does not validate; a writing step commits, a read step writes nothing
- [ ] **3.3 The resume on steps**
  - [ ] Steps `resume_claim`, `resume_read`, `resume_record` (D4) in `steps/resume.py` with their models
  - [ ] `operations/resume_attempt.py`: `logs/resume/<run id>/<answer seq>.attempt`, written to a temporary name and renamed; `started` before `sq run --resume`, then the judged outcome (outcome, detail, log path) before `resume_record`. A failed write is logged at error level and the attempt goes on
  - [ ] `operations/resume.resume(steps, claimed, deps)` takes the claim payload (question, answer text, claim id, `resume_wait_seconds`) and follows D6's attempt-file table: a final outcome in the file is recorded with no poll; `started` with the run gone is recorded `resumed` with the earlier-attempt detail; `refused` or no file is a new attempt. First poll unreadable: `refused` with the reason, unless the file holds `started`, which records nothing and raises. Add the import-boundary rule for `resume` and `resume_attempt`
- [ ] **3.4 Resume tests** (on `LocalSteps`)
  - [ ] Existing resume tests pass with `LocalSteps`
  - [ ] Each row of the attempt-file table: final outcome replayed with no second `sq run --resume`; `started` and run gone records `resumed`; `started` and run still paused starts `sq` again; `refused` in the file is never replayed (a refused resume retried starts `sq` again)
  - [ ] Design-required edit: `tests/operations/test_resume.py::test_an_unreadable_first_poll_raises_and_writes_nothing` (D6 reverses it) now asserts that with no file an unreadable first poll records `refused` with the reason, frees the claim (a new `resume_claim` succeeds at once) and starts no `sq`
  - [ ] `started` and an unreadable first poll: nothing recorded, file unchanged, the next attempt records `resumed`
  - [ ] A failed attempt-file write logs at error level and the resume still records its outcome
- [ ] **3.5 `answer` split into client and hub parts**
  - [ ] The hub part records the answer in today's one transaction and then, in it, reads the question's machine (D7 table): the calling machine takes the resume claim and returns its payload; another machine returns its name and `last_called_at`; a null machine marks the answer `not_delivered` with the detail that the run's machine was removed
  - [ ] The client part runs the resume on a returned claim, or returns `AnswerResult` with `resume` null and the new `waiting_on_machine` (name, `last_called_at`). The CLI text for that case is D7's sentence. Placement in `wiring._dispatch` runs the hub part in process for now
  - [ ] `docs/cli-contract.md` and `docs/mcp-server.md`: `waiting_on_machine`
- [ ] **3.6 `answer` tests**
  - [ ] Existing `answer` tests pass on the local store (machine always `local`)
  - [ ] A question with another machine's id returns `waiting_on_machine` and starts nothing; a question with a null machine is recorded and marked `not_delivered`
  - [ ] An unreadable first poll returns the refused result
  - [ ] Success: checks pass

**Commit**: `refactor: run the resume and answer on steps with an attempt file`

## 4. The pause path on steps (D1, D4, D5, D9; effort 5)

- [ ] **4.1 The question claim steps** (`steps/pause.py`, `steps/models.py`)
  - [ ] `question_insert`, `question_hold`, `question_claim_held`, `question_replace_claim`, `question_wait` per D4: each wraps today's store call and its compare-and-set; `question_insert` and `question_hold` write the acting machine; `question_hold` returns its request's effective state; `question_claim_held` says on loss whether a claim or an answer won; `question_replace_claim` applies only when the row is claimed by the answering run id in the request; `question_wait` takes the reason, detail and evidence for a named claim or a held row
- [ ] **4.2 Claim-step tests**, one per row of D4's "what each claim step matches" table on a throwaway store: the winning case and the losing case of each
  - [ ] Two `question_replace_claim` calls for one stale claim: one applies, the other loses as `already_claimed`
- [ ] **4.3 `question_settle` and `pause_sources`**
  - [ ] `question_settle`: the hub builds the gate (reserved-term screen and answer limit) from its own config and the member's settings and runs `settle_answered` with it in the transaction. Answered: writes the answer and takes the resume claim (`claim_resume`), returned in the reply. Gate refused: `waiting_on_pm` with the reason (today's `_wait_on_pm`). Claim gone: superseded
  - [ ] `pause_sources`: what `pause_context._read_store` and `pause_claim._read_request` read today: the member's program, its members with each one's checkout path and Context Forge id on the calling machine, the PM precedent, the standing answers, and a named request's result or that it is no longer stored
  - [ ] Tests: answered settle returns a claim; a gate refusal waits; a superseded settle starts no resume; two settles for one run at once with one answer left under the limit: one answered, the other `answer_limit_reached`. `pause_sources` returns the calling machine's checkout ids, never member ids
- [ ] **4.4 `pause_begin`**
  - [ ] Request: the caller (`here`) or none, the run id, the poll facts, the run's fate or none. In one transaction, D4's steps 1 to 7: close the run's older open questions on the calling machine; the message sweep when due; stop on `classify_run_only` or an answering run; refuse a caller-less request past that as `malformed_call`; `find_caller`; the row and latest answer (another machine's row returned with its name); no row: link and limit; held row: request state, result and limit
  - [ ] Reply: what was closed, then the skip or the member, answering settings, `answering_wait_seconds`, `resume_wait_seconds`, the row with `claim_stale` (from `pause_claim_seconds`), latest answer, link, limit result and request state
  - [ ] Tests: each `pause_begin` reply shape; only the calling machine's rows are swept; `claim_stale` is false at `pause_claim_seconds - 1` and true at `pause_claim_seconds`
- [ ] **4.5 The close sweep change** (D9)
  - [ ] In both sweeps (`question_sweep` and the hub part of `status`): an answer with no outcome is left; a `refused` one is marked `not_delivered` once its newest sign of life is `resume_claim_seconds` old
  - [ ] Design-allowed edits, the tests D9 reverses: `tests/operations/test_question_sweep.py::test_an_unresumed_answer_past_the_bound_becomes_not_delivered` is split (no outcome left; refused marked); in the same file `test_an_answer_inside_the_bound_stays_including_one_with_a_fresh_resume_start` and `test_a_refused_answer_is_judged_from_its_newest_sign_of_life` use `resume_claim_seconds` and `claim_resume`; `tests/operations/test_status_sweep.py::test_an_old_unresumed_answer_is_marked_not_delivered_and_reported` records the answer `refused` first, and its `BOUND` is `resume_claim_seconds`; `tests/operations/test_every_state_exits.py::test_answered_unresumed_exits_by_the_sweep` becomes a `refused` answer exiting by the sweep at `resume_claim_seconds` (6.3 adds the no-outcome answer's exit)
  - [ ] Tests: a refused answer is not marked one second before `resume_claim_seconds`; a no-outcome answer whose run left the pause stays open
- [ ] **4.6 The pause entry takes `Steps`**
  - [ ] `handle_pause`, `pause_eligibility` and `pause_class` take `Steps` in place of a store and a config, in D5's steps 1 to 4: poll, `classify_run_only`, the `cf` gather, `pause_begin`, the run-file checks. `classify_pause` takes `claim_stale` in place of a limit and a time; `tests/operations/test_pause_class.py`'s three limit tests become `claim_stale` flag tests, and the at-limit and just-under cases move to 4.4's `claim_stale` test
  - [ ] "Not in a program": gather the checkout, call the new `register` callable (built in `wiring` from the placement `amoeba add` uses), call `pause_begin` again; a rejected `add` is today's skip
  - [ ] New skip `SkipReason.OTHER_MACHINE`. `cli.commands.run_handle_pause` no longer calls `load_config` or `open_store`: it builds `LocalSteps(layout)`, which opens the store and loads the config only for a step whose `STEP_MODELS` row needs it (7.4 switches to `steps_for`)
  - [ ] Design-allowed edit: `tests/operations/test_pause_eligibility.py`'s answering-run skip test asserts the skip with `cf` answering and exit 3 with `cf` failing
- [ ] **4.7 The claim paths take `Steps`**
  - [ ] `pause_claim`, `pause_held`, `pause_existing`, `pause_results`, `claim_waiting`, `answering_settle` and `pause_context` take `Steps`, in D5's step 5 paths: each store call becomes the step D4 names. A held claim at the limit waits as `answer_limit_reached` with nothing gathered. The settle's claim drives the resume; `resume_claim` that loses is the new skip `SkipReason.RESUME_IN_PROGRESS`
  - [ ] Add the import-boundary rule for every module of 4.6 and 4.7. `docs/cli-contract.md`: the two skips
- [ ] **4.8 Pause-path tests** (on `LocalSteps`)
  - [ ] Every existing pause, hold and settle test passes; `test_pause_claim_held.py` needs no edit beyond `LocalSteps`
  - [ ] `handle-pause` for a run that is not paused makes no `cf` call; an answering run's own pause is skipped as `answering_run`
  - [ ] Two `handle-pause` calls that both read one stale claim: one replaces it and runs the answering run, the other is skipped as `already_claimed` and runs nothing
  - [ ] A question on another machine is skipped as `other_machine`, and that machine's rows are not swept; a resume claim in flight is skipped as `resume_in_progress` and starts nothing
  - [ ] A held question whose request is done, at its answer limit, waits as `answer_limit_reached`: nothing gathered, no answering run. The same for a question held and released in one call
  - [ ] An answered question whose resume's first poll is unreadable makes `handle-pause` raise `SquadronError`
  - [ ] Success: checks pass

**Commit**: `refactor: run handle-pause on steps, ending with pause_begin`

## 5. Wakes, the sweeps and the prune on steps (D8, D9, D12; effort 4)

- [ ] **5.1 `send`'s hub part wakes**
  - [ ] The hub part takes a `logs_dir` argument, writes the request, sets the mark (2.5), then: a due wake with a wakeable checkout on the calling machine is claimed and returned with `log_stem` `<logs_dir>/wake/<wake id>`; due with wakeable checkouts only elsewhere returns `SendResult.wake_waiting_on` (each machine's name and `last_called_at`); else nothing. The in-process placement passes the layout's logs directory; 7.1 adds the door's body key
  - [ ] The client part starts `amoeba wake-run <wake id>` detached on a returned claim, as today; a failed start is `wake_finish` as `start_failed`
  - [ ] Delete `operations/wake_door.py` and its call; `not_served` for `send` no longer exists
  - [ ] Design-required edit: `tests/hub/test_door_operations.py`'s `test_a_send_to_a_member_a_wake_is_due_for_is_not_served_and_writes_nothing` is deleted; 5.2's tests take its place. `test_a_hub_part_refusal_keeps_no_result_for_a_repeat` provokes its refusal with another hub part's `CallRefused` (a `status` call whose `runs` document `operations/runs_document.py` refuses) and keeps its assertion that a repeat is refused again. The `RefusalCode(NOT_SERVED)` identity assertion stays
  - [ ] `docs/cli-contract.md`: `wake_waiting_on`, the machine on wake entries
- [ ] **5.2 `send` tests**
  - [ ] `send` from the machine with the wakeable checkout starts the wake in that call; a wake `send` claims in the call that set the mark is that mark's wake, and after it ends no second wake is due
  - [ ] Only another machine wakeable: `wake_waiting_on` names it; nothing claimed
  - [ ] A send while the recipient has a live session is not woken, then or later; sent again unchanged once stale, it is
- [ ] **5.3 `wake-run` on steps**
  - [ ] Steps `wake_read` (directory, command, `seconds_left`, only for this machine's unended row with no pid), `wake_set_pid`, `wake_finish` in `steps/wake.py`. `wake_set_pid` and `wake_finish` load no config
  - [ ] `wake_run` takes `Steps`; waits `seconds_left` on its own monotonic clock; D11's rows: `wake_read` no reply or refused, exit 3 and nothing started; `wake_set_pid` no reply, a warning and the wake goes on; `wake_set_pid` refused, stop the process group and exit 3; `wake_finish` failing, exit 3. `run_wake_run` builds `LocalSteps`. Add its import-boundary rule
  - [ ] Tests: existing wake-wrapper tests pass on `LocalSteps`; each D11 row with a `Steps` double that raises `HubUnreachableError` or `HubRefusedError`
- [ ] **5.4 `open_runs` and the `status` sweep**
  - [ ] Step `open_runs`: the calling machine's open questions' run ids and open answering run ids, and `prune_after_days`
  - [ ] `status` and `list` with no subject: the client part calls `open_runs`, checks the file of each open run the listing does not show, and adds `absent_runs` to the `runs` document (`runs_document.py`). The hub part judges each of the calling machine's open rows from the document (D9). `open_runs` failing: exit 3, no further call
  - [ ] Question entries in `status` and `list` gain `machine`; an answer or wake waiting for another machine shows it with `last_called_at`. `docs/cli-contract.md`
  - [ ] Tests: `status` from machine A closes A's question whose run is gone and leaves B's open; an absent run is gone only when its file is absent too; a no-outcome answer whose run left the pause is left by the sweep
- [ ] **5.5 The prune on `open_runs`**
  - [ ] `prune` takes `Steps` and reads open runs and `prune_after_days` from `open_runs` when a walk is due; a failed `open_runs` leaves the marker untouched. `status`'s client part prunes after its hub call with the `open_runs` reply it has (one call). The walk covers wake logs, resume logs, attempt files and `logs/resume-run/`. Add the import-boundary rule for `prune`
  - [ ] Tests: logs past `prune_after_days` removed and those of an open question on this machine kept; a failed `open_runs` leaves the marker; a prune problem is in `handle-pause`'s `detail` and `status`'s `file_problems`
  - [ ] Success: checks pass

**Commit**: `refactor: run wakes, the status sweep and the prune on steps`

## 6. Work that belongs to a machine (D10; effort 5)

- [ ] **6.1 `steps/work.work_waiting`**
  - [ ] `work_waiting(transaction, machine, config, now)`: the four existence queries of D10's table, stopping at the first hit. The resume row uses `claim_resume`'s predicate; the dead-claim row uses `pause_claim_seconds`; held and dead-claim rows need no start in the last `answering_wait_seconds`; the wake row uses `wake_due` for members with a wakeable checkout on the machine
  - [ ] Tests: one per table row, true and false; a `refused` resume is not work; another machine's rows are not this machine's work
- [ ] **6.2 `claim_work`**
  - [ ] Step `claim_work` (request: `logs_dir`): up to `MAX_WORK_PER_CLAIM` items in one transaction, resumes first, then held questions never started, then the oldest starts, then wakes. Resume: `claim_resume`, adds one to `resume_start_count`. `handle-pause`: `mark_start_attempted`, which gains a required `expected_state` (`waiting_on_request` for a held row, `claimed` for a stale claim) so it still refuses a row that left the state its caller read (`tests/store/test_held_questions.py::test_mark_start_attempted_refuses_a_row_no_longer_held` passes `waiting_on_request`, assertion unchanged); adds one to `start_count`. Wake: `claim_wake` with `<logs_dir>/wake/<id>`
  - [ ] At `MAX_AUTOMATIC_STARTS`: a due question moves to `waiting_on_pm` as `starts_exhausted` with a detail giving the count and pointing at that machine's calls log; a due answer is recorded `refused` with the count and that no attempt recorded an outcome. Neither is returned
  - [ ] `docs/store-contract.md`: `starts_exhausted`
- [ ] **6.3 `claim_work` tests**
  - [ ] Seven resumes waiting: one call returns five, then two; the order of kinds
  - [ ] A dead claim is started three times; the fourth is `starts_exhausted` and no fourth start. A resume handed out three times with no outcome is then `refused` with the count; a `refused` one is never returned
  - [ ] Hand-out again only after the limit, on the test clock: a resume after `resume_claim_seconds` (not one second before), a start mark after `answering_wait_seconds`, a wake after its deadline
  - [ ] Three threads call `claim_work` with one resume waiting: one gets it. The same for a held question whose request ended, a stale claim and a wake
  - [ ] Hook or hand-run `handle-pause` is not counted
  - [ ] After a `refused` resume, a new `answer` for that question on another machine is returned by that machine's `claim_work`
  - [ ] `tests/operations/test_every_state_exits.py` gains: an answered question with no resume outcome exits by the resume `claim_work` hands out
- [ ] **6.4 `work_start`, `resume-run` and `amoeba resume-run`**
  - [ ] `operations/work_start.start_claimed(items, deps)`: each item started detached in its own session, never waiting: `amoeba resume-run <seq> <claim id>` with stdout and stderr in `logs/resume-run/<seq>-<stamp>.stdout.log` and `.stderr.log`; `amoeba handle-pause <run id>` in the row's checkout, as `request_release` does today; `amoeba wake-run <wake id>`. A failed start: logged and in the calls log (`handle-pause`), `resume_record` `refused` (resume), `wake_finish` `start_failed` (wake). Never raises
  - [ ] `operations/resume_run.py`: `resume_read` with the claim id, then `resume` (3.3). `cli/resume_command.py` registers `amoeba resume-run ANSWER_SEQ CLAIM_ID`, CLI only, beside `wake-run`, building `LocalSteps`. It runs no after-step. Add the import-boundary rule for `resume_run` and `work_start`
  - [ ] Tests: each kind started with the right argv, directory and log paths; each failed start recorded as listed; `resume-run` with a claim id no longer the answer's starts nothing; `docs/cli-contract.md`: the command and its logs
- [ ] **6.5 `wiring_steps` and the after-step's call sites**
  - [ ] `wiring_steps.py`: `steps_for(layout)` returns `LocalSteps` until 7.4. `after_call(...)` runs the prune when due (except after `handle-pause` and `status`), then, if the last reply had the flag, one `claim_work` and `start_claimed`. On `HubUnreachableError` it makes no call. Never raises, never changes the result. With `LocalSteps` the flag is one read of `work_waiting`
  - [ ] `AFTER_STEP_BOUND_SECONDS` in `wiring_steps`, replacing `START_BOUND_SECONDS`: one busy timeout per store transaction the after-step makes on the local way (the flag read, `open_runs` when a prune is due, `claim_work`). Design-required edit: `tests/test_message_timing.py`'s `_with_start` adds it for every message operation (the after-step now follows each), `test_the_start_bound_is_one_read_and_one_write_per_start` pins the new bound, and `test_sends_worst_case_with_the_start_and_the_wake_is_the_design_figure` still passes `check_below_deadline`; the figure in `docs/mcp-server.md` follows
  - [ ] `wiring.invoke` calls `after_call` on both of its paths, the door path that returns `route`'s result and the local path, after every operation on the CLI door and after every operation but `answer` on the MCP door. `run_handle_pause` calls it at the end on every path, a raise included
- [ ] **6.6 Delete `request_release` and `wiring_release`**
  - [ ] Delete `operations/request_release.py` and `wiring_release.py`; remove their references, docstrings and comments included, in `operations/handle_pause.py`, `operations/status_runs.py` and `store/models.py` (the applied `008_waiting_on_request.sql` is never edited)
  - [ ] Move or delete the tests that import them, one by one: `tests/operations/test_request_release.py`, `test_request_release_child.py`, `test_held_question_exits.py`, `test_handle_pause.py`, `test_status_calls.py`, `tests/test_message_timing.py`, `tests/test_import_boundaries.py`, `tests/load/test_start_ended_held_load.py` and its helper `tests/release_child_wait.py`. A test of behavior the after-step keeps (which rows start, the cap, the start-mark spacing, the child's wait) is moved onto `after_call` or `claim_work` with its assertion unchanged; a test of the deleted function's own signature is deleted. Note each under this task
  - [ ] Design-allowed edit: tests of `start_after`'s seven operations assert the after-step for any operation. `git mv tests/test_wiring_release.py tests/test_after_step.py`; its `START_AFTER_OPERATIONS` import goes, and its MCP `reply` and `cancel` test stays and passes against the after-step
- [ ] **6.7 After-step tests**
  - [ ] With no client file, a `reply` and a `cancel` through the MCP door each start the released held question's `handle-pause`; an MCP `answer` runs no after-step
  - [ ] On a machine that runs only `send` and `inbox`, wake and resume logs past `prune_after_days` are removed
  - [ ] A prune problem after `send` is a log line, not in the result
  - [ ] A `handle-pause` child runs the after-step, so a batch over the cap drains
  - [ ] Success: checks pass

**Commit**: `feat: start a machine's waiting work from the work flag and claim_work`

## 7. The door serves the steps (D3, D7, D10, D11, D15; effort 4)

- [ ] **7.1 Step names and the door version in `wire`**
  - [ ] `wire.protocol`: `STEP_CALLS` (the sixteen names of D4), `WRITING_STEPS`, reply keys `work` and `work_problem`, body keys `via` and `logs_dir`. `answer` joins `SERVED_OPERATIONS` and `WRITING_CALLS`. `UNKNOWN_ADVICE` gains `answer` (run `amoeba list` and look at the question before answering again) and one text for every writing step (D11)
  - [ ] `wire.times.DOOR_VERSION` becomes 2
  - [ ] Design-required edits: `tests/wire/test_times.py`'s pinned tuple starts with 2; in place of `answer`, a name that is in no served or step list, in `tests/hub/test_handle_call.py::test_an_unserved_name_is_not_served`, `test_hello_with_an_empty_document_keeps_no_result_and_answer_is_not_served` (renamed to match) and its other `rig.call("answer", ...)` refusal, and the `not_served` cases in `tests/hub/test_app.py` (`grep -n '"answer"' tests/hub` finds them)
  - [ ] Tests: `STEP_CALLS` and `WRITING_STEPS` equal the names and writing rows of `STEP_MODELS`; every writing step has advice
- [ ] **7.2 The hub routes steps and adds the flag**
  - [ ] `handle_call` accepts a name in `SERVED_OPERATIONS`, `HELLO_CALL` or `STEP_CALLS` and refuses others as `not_served`; a step runs `run_step` inside the call scope. A document that does not validate is `malformed_call`; an `OPERATION_ERRORS` failure is `hub_error`
  - [ ] Writing steps are writing calls on every path: the keep after the operation and the kept-result lookup in `hub/calls.py` (today `WRITING_CALLS` only) also take `WRITING_STEPS`, so a step and its kept result commit together and a repeat returns it; `_needs_config` reads a step's config need from `STEP_MODELS`; `client/call.py` gives a writing step's unknown outcome its `UNKNOWN_ADVICE` text
  - [ ] `hub/call_work.py`: after the operation, inside the call scope, `work_waiting` for the acting machine into every done reply, fresh on a kept-result repeat. If the hub's `config.yaml` cannot load: no `work`, and `work_problem` with the error's text. Refused replies carry neither. A call whose own work needs the config is refused `hub_error` as today
  - [ ] `served.py`: the `answer` case, and `send` with `logs_dir`
  - [ ] Tests: an unknown name refused `not_served`; a malformed step `malformed_call`; a writing step repeated with its call id returns the kept reply and applies once; a done reply carries `work`; a repeat gets a fresh flag; with a broken config, `mark_read` and `wake_finish` succeed with `work_problem` and no `work`
- [ ] **7.3 `DoorSteps` and `StepReplyError`**
  - [ ] `DoorSteps` in `wiring_steps.py`: reads the client file on each call (gone: `ClientFileError` naming it, never a local store), posts the request model as `document` to `POST /call/<step>`, validates the reply against the step's model. A reply that does not fit raises `StepReplyError` (new, in `wiring.OPERATIONAL_ERRORS`, not `OPERATION_ERRORS`), naming the step and field and, for a writing step, that the hub applied it. Keeps the last reply's flag for the after-step and prints `work_problem` as one stderr line
  - [ ] `steps_for(layout)` returns `DoorSteps` when a client file exists, `LocalSteps` otherwise, once per command
  - [ ] Tests: every step through `DoorSteps` against the in-process hub (each reply runs through its model); a reply missing a field raises `StepReplyError` and exit 3; a client at door version 1 calling `send` is refused `door_version` and no request or wake row is written
  - [ ] Tests of D3's two remaining rules: a command that started with `LocalSteps` on a machine that joins meanwhile fails its next step with `LocalStoreClosedError`; a step that raises one of `OPERATION_ERRORS` on the hub is refused `hub_error` and the command exits 3
- [ ] **7.4 Joined machines run the commands**
  - [ ] Remove `refuse_if_joined` for `handle-pause` and `wake-run` in `cli/main.py`; `run_handle_pause`, `run_wake_run`, `resume-run` and the after-step use `steps_for`. `amoeba-mcp` start stays refused on a joined machine
  - [ ] `handle-pause` passes the `register` callable that places `add` through the door when joined
  - [ ] Design-required edit: `tests/hub/test_joined_entry_points.py`'s lists of unserved operations and CLI commands drop `answer`, `handle-pause` and `wake-run`; its `amoeba-mcp` test stays
  - [ ] Update 260's entry-point table in `docs/cli-contract.md` (or where it lives) and `docs/squadron-hook.md`: `handle-pause` on a joined machine and what a down hub leaves behind
  - [ ] Tests: `handle-pause` on a joined fixture machine passes with no local `config.yaml`; a client file removed partway fails the next step with `ClientFileError` and opens no local store, with a set-aside store put back in place; a `handle-pause` failing at `pause_begin` with the hub stopped returns after one call bound and its after-step makes no `open_runs` or `claim_work`, including when a prune is due; a served `list` on a joined machine whose reply has `work: true` makes one `claim_work` and starts what it returns
- [ ] **7.5 Each fixture machine has its own home for `sq`**
  - [ ] `tests/hub_fixture.py` `env_for`: a client's `HOME` is that client's own home directory, not the shared `root` (the hub home keeps `root`). Its `PATH` already puts its own `sq` stub first, so the stub's state (`$HOME/.sq-stub/runs`) and the Squadron runs directory (`$HOME/.config/squadron/runs`) are then per machine. Fix any fixture test that relied on the shared `HOME`, noted under this task
  - [ ] Test: a run created on `alpha` is not visible on `beta`
- [ ] **7.6 One body, two ways**
  - [ ] A parametrized subset of the pause, resume and wake tests, one per path in D5, runs on `DoorSteps` against the in-process hub as well as `LocalSteps`
  - [ ] Success: checks pass

**Commit**: `feat: serve the steps, answer and waking send through the door`

## 8. Across machines, faults, clock and load (D2, D11, D16; effort 4)

- [ ] **8.1 Two-machine tests** (`tests/hub/`, on `two_machine_hub`)
  - [ ] A fixture pipeline paused on `alpha`, answered from `beta`: `answer` names `alpha` and its `last_called_at`; `alpha`'s next call resumes it; `beta` ran no resume
  - [ ] A request whose only wakeable checkout is on a machine that is not calling waits: `send` and `list` name the machine; the request expires on time
  - [ ] With a live session row for the member on `beta`, a `send` from `alpha` starts no wake and `claim_work` from `alpha` hands none out
  - [ ] Each machine's scratch and logs past `prune_after_days` are removed by that machine's prune through the door, and those of an open question on that machine are kept
- [ ] **8.2 Fault tests** (`DoorHooks` drops a reply after commit; the rig's clock)
  - [ ] A dropped `claim_work` reply: the same resume handed out again after `resume_claim_seconds` and not one second before; the same for a start mark and a wake
  - [ ] `resume_record` retried across a hub stop and restart is recorded once, and no other client is handed that resume meanwhile
  - [ ] Hub stopped after `question_insert`: exit 3 with the error in the calls log; once back and the claim is stale, the next call from that machine starts `handle-pause`, which settles from the scratch or restarts
  - [ ] A resume judged `resumed` whose `resume_record` got no reply is recorded `resumed` by the next attempt from the attempt file, with no second `sq run --resume`
  - [ ] A resume attempt killed after starting `sq run --resume`, the run moved on, the claim run out: in three separate tests the next call is `list`, `status`, and `handle-pause` for the next pause; each sweep leaves the answer, the after-step hands it out, and it is recorded `resumed`. The same three after a `resumed` record that got no reply
  - [ ] A resume that never started, run left the pause: the sweep leaves it and the attempt records `not_delivered`. Every attempt dying before it records: third hand-out then `refused`, then the sweep marks `not_delivered`
  - [ ] A `question_settle` over `MAX_CALL_BYTES` is refused; `handle-pause` exits 3; after three automatic starts the question is `starts_exhausted` and no second answering run started
  - [ ] `wake_set_pid` with no reply leaves the command running to its exit or deadline and `wake_finish` ends the row; `wake_read` with no reply starts nothing
  - [ ] With the hub's config broken, the client prints `work_problem`; `status` whose `open_runs` fails exits 3 and makes no further call
- [ ] **8.3 The clock test**
  - [ ] A client whose clock is an hour ahead runs a pause, an answer, a held question and a wake against the in-process hub: every stored time is the hub's, and no expiry, age or claim differs from a run with a correct clock
- [ ] **8.4 The load test** (`tests/load/test_door_load.py`)
  - [ ] Seed with `hub.seed` while the hub is stopped, as `_seed_answers` does: 500 questions, half with `FIRST`'s and half with `SECOND`'s `machine_id` read from `machines`, and 500 open requests to members with a wakeable checkout on each machine; add `claim_work` callers; keep both bounds (every call inside 2 s with 16 clients; idle median under 200 ms); the idle case also times each step once with the same median. Record the figures for the slice notes (10.1)
  - [ ] The test stays under `tests/load`, which CI's bare `uv run pytest` step collects, so CI gates it; `tests/test_ci_gates_load.py` passes
- [ ] **8.5 Live variants**
  - [ ] `tests/live/hold` and `tests/live/waking` each gain a variant on the two-machine fixture with the repos split across machines; run both once (they spend on models) and note the result
  - [ ] Success: checks pass; both live tiers pass

**Commit**: `test: run the pause, resume and wake paths across two machines`

## 9. `rm-machine`, documents and the live update (D13, D14, D15; effort 3)

- [ ] **9.1 `rm-machine` closes what waits on the machine**
  - [ ] `store/machines.remove_machine`, which `hub/admin.rm_machine` calls inside its one transaction, before the machine row is deleted: close every open question on the machine as `machine_removed` with the machine's name; mark each such answered question's latest answer `not_delivered` with the same detail and clear its claim; end every unended wake as `machine_removed` naming the machine; null `machine_id` on its question and wake rows and `log_stem` on its wake rows
  - [ ] Tests: no open question, no answer without a final outcome and no unended wake left on the machine; the wakes it ended name the machine in their detail; no `log_stem`; a later `answer` to one of those questions is recorded and marked `not_delivered`; a wake wrapper whose machine was removed stops its command's process group at its next step
- [ ] **9.2 Documents** (D15)
  - [ ] `docs/store-contract.md` (every store time is the store's own clock), `docs/cli-contract.md` (work starts after any call but an MCP `answer`), `docs/config-contract.md`, `docs/squadron-hook.md`, `docs/mcp-server.md`: complete the prose for every item D15 lists; `tests/test_contract_docs.py` passes
- [ ] **9.3 `scripts/update_live.py`**
  - [ ] The read-back gains one check after `amoeba list`: no question or wake has a null machine; a failure restores by itself, as the other checks do
  - [ ] `tests/scripts/test_update_live.py`: `update` and `restore` against a copy of a schema-12 store with question and wake rows; the opener gives old rows `local`; a row written between the two is gone after the restore
  - [ ] Success: checks pass

**Commit**: `feat: close a removed machine's work and update the contracts`

## 10. Verification and close (effort 2)

- [ ] **10.1 Verification walkthrough**
  - [ ] Run the design's two `pytest` commands (Verification Walkthrough) and the by-hand pass on the fixture's hub with `alpha` and `beta`; on a throwaway schema-12 home, `amoeba list` migrates it and shows machine `local`, and the 242 and 244 walkthroughs (each design's Verification Walkthrough) behave as before
  - [ ] Record the output, the load figures (8.4) and any departure under a dated "Implementation Notes as built" in the design; fix any dead end found and note it
- [ ] **10.2 Final checks**
  - [ ] Checks pass. Every new source file is near 300 lines (`wc -l`); files over it are noted with why. `rg "request_release|wiring_release|start_after|start_ended_held|wake_door|MAX_STARTS_PER_CALL|START_BOUND_SECONDS" src tests --glob '!src/amoeba/store/schema/*'` finds nothing (applied migrations are never edited)
  - [ ] The design's Migration Plan lists the test edits made; the design's and this file's `status` are `complete`
  - [ ] Success: the slice branch holds every commit; the working tree is clean

**Commit**: `docs: record the slice 262 walkthrough and notes`
