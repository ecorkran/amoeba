---
docType: tasks
slice: hold-and-release
project: amoeba
lld: user/slices/242-slice.hold-and-release.md
dependencies:
- 240-slice.requests
- 241-slice.push-and-presence
projectState: Slices 220 to 229 are merged on main. Store schema version 5 (migrations
  001 to 005), state is in ~/.local/state/amoeba. Slice 240 (messages, `get_message`,
  `effective_state`, migration 006) and slice 241 (sessions, migration 007) are designed
  and tasked; this slice is built after both are built and integrated. Slices 243
  and 244 do not read anything this slice adds.
dateCreated: 20261115
dateUpdated: 20261115
status: not_started
turns: 22
promptTokens: 1380144
cachedTokens: 1273563
cacheWriteTokens: 106547
completionTokens: 24512
durationSeconds: 168.3
costUsd: 0.799028
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.7990277000000001
    completionTokens: 24512
---

# Tasks: Hold and Release

## Context Summary

- Working on slice 242 (design: `user/slices/242-slice.hold-and-release.md`; decisions D1 to D10 are cited by number). Effort 4/5. The design's Overview says what it delivers: a run that stops on a question carrying an `amoeba-request: <id>` line is held on that request and carries on by itself when the request is done.
- Paths: a path without a prefix is under `src/amoeba/`; `tests/`, `docs/` and `project-documents/` paths are from the repo root, and `user/` means `project-documents/user/`.
- Module layout is the design's Component Structure. New SQL goes in `store/sql_held.py`, not the 484-line `sql.py`. A module that passes ~300 lines is split by concern.
- Closed values are defined once: the marker words, `MAX_STARTS_PER_CALL`, `START_BOUND_SECONDS`, `START_AFTER_OPERATIONS`, the `request-release` log directory name, the four new `DeclineReason`s, `PassageKind.REQUEST_RESULT`, `QuestionState.WAITING_ON_REQUEST`, `HandlePauseOutcome.HELD`. No silent fallbacks; every swallowed exception names one type and carries a comment saying why (D7 lists the only three).
- Modules already over ~300 lines (`wiring.py` 342, `store/sql.py` 484, `answering/passages.py` 416) get no new logic: new code goes in a new module and the old file gains only a call or a one-line change.
- Import direction stays `cli/mcp → wiring → operations → store, answering, upstream`; `answering` imports nothing from `store`; the store imports nothing from `operations`.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the out-of-area baseline failures noted in 0.1. The live tier is `uv run pytest tests/live/<dir>` (never part of a bare run; LLM spend is pre-authorized).
- Tests use the autouse `AMOEBA_HOME` fixture, the stub `cf` (`tests/cf_stub.py`, `tests/cf_fixtures.py`), the fake `sq` (`tests/sq_stub.py`, `tests/fake_sq.py`), `tests/git_repo.py`, `tests/user_configs.py`, `tests/store/seed.py`, `tests/operations/pause_support.py` and `handle_rig.py`. Destructive SQL only against throwaway stores. No sample id, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), including docs that tests check.
- `tests/test_contract_docs.py` requires every new state, column, JSON field, outcome, kind and reason in the contract docs, so each task that adds one adds its entry then. Task 9 writes the prose.
- No existing test function or assertion in the 223, 228, 240 or 241 suites changes, except the edits tasks 1.1, 1.3, 2.5, 6.1 and 6.5 name. New test functions may be added to these existing files only: `tests/store/test_vocabulary_pinning.py` (1.2); `tests/store/test_questions.py`, `tests/store/test_question_closing.py`, `tests/operations/test_question_sweep.py`, `tests/operations/test_pause_class.py`, `tests/operations/test_rm.py` (1.5); `tests/answering/test_passages.py` (2.4); `tests/operations/test_pause_existing.py` (4.3); `tests/test_wiring.py`, `tests/operations/test_handle_pause.py`, `tests/test_message_timing.py` (6.5); `tests/operations/test_status_runs.py`, `test_status_waiting.py`, `test_status_calls.py`, `test_status.py` (7.2); `tests/operations/test_decisions.py` (7.3); `tests/operations/test_dismiss.py`, `test_answer.py`, `test_every_state_exits.py` (7.4); `tests/test_program_rules_doc.py` and the `INSTRUCTIONS` test in `tests/mcp_server` (9.1). If an existing test fails for a legitimate reason, fix the new code, not the test.
- Production state: tests touch throwaway stores only; no task in sections 0 to 10 writes the live store or config. Task 10.1 rehearses the migration on a copy. The live migration, with backup and the backup's removal, is the Phase 7 hand-off checklist at the end of this file (migrating the live store before the merge would leave the installed tool refusing it). The "Amoeba Design Rules" block of `CLAUDE.md` designates the live store and config for migrations.
- Work on branch `242-slice.hold-and-release`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [ ] **0.1 Branch, prerequisites and baseline**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. The planning documents (design, this file) are committed on the target, with no other uncommitted change: `git checkout -b 242-slice.hold-and-release {target}`
  - [ ] Confirm the prerequisites exist: `store/schema/` holds `001` to `007`, `EXPECTED_SCHEMA_VERSION` is 7, `store/messages.py` has `get_message` and `effective_state`, `operations/names.py` has the `send`, `reply` and `cancel` operations, `wiring.invoke` has arms for them, and 240's test files `tests/store/test_migration_006.py` and `tests/test_message_timing.py` exist. If any is missing write `BLOCKED: <what>` under this task and stop (240 and 241 must be built and integrated first)
  - [ ] Re-check the dated fact D1 relies on: Squadron's `question` is the tail of the agent's reply. Using `tests/live/pause/harness.py` with a pipeline whose reply is longer than Squadron's question-tail length (find the constant with `grep -rn QUESTION_TAIL_CHARS tests src`), read the `question` the installed `sq` (`sq --version`) reports and note whether it starts with `…`. The matcher reads the whole text either way; the note only records the version and what was seen
  - [ ] Find the helpers to reuse and note their paths: `tests/store/test_migration_005.py` and `test_migration_006.py` (models for the migration test), `tests/store/test_vocabulary_pinning.py`, `tests/store/question_support.py`, `tests/operations/pause_support.py`, `tests/operations/handle_rig.py`, `tests/operations/test_pause_existing.py`, `tests/operations/test_every_state_exits.py`, `tests/live/pause/harness.py`, `tests/live/pause/conftest.py`, `tests/live/answering/test_validate.py`, `tests/load/test_report_release_load.py`
  - [ ] Run the checks once and note the baseline. A pre-existing failure in the touched area (a module or test file this slice edits, or a test of one) is fixed in place first, committed on its own as `fix: {summary}` before any slice work; a failure outside the touched area is left and listed by test name in the note
  - [ ] Success: `git branch --show-current` prints `242-slice.hold-and-release`; a note under this task gives the target, the baseline result, the `sq` version and tail observation, and the helper paths

## 1. Vocabulary, migration 8, question fields (D2, D3, D8, D10; Development Approach step 1)

- [ ] **1.1 `QuestionState.WAITING_ON_REQUEST` and `008_waiting_on_request.sql`**
  - [ ] `store/vocabulary.py`: add `QuestionState.WAITING_ON_REQUEST = "waiting_on_request"` with a one-line comment
  - [ ] `store/schema/008_waiting_on_request.sql`: rebuild `questions` as `003_question_lifecycle.sql` did (create new, copy every row, drop, rename; read 003 first and follow its form). The `state` `CHECK` list is the five states in D2's order; new nullable columns `request_id` (with `CHECK (state <> 'waiting_on_request' OR request_id IS NOT NULL)`) and `start_attempted_at`; no foreign key from `request_id`; every other column, key and constraint copied unchanged, so `answers` keeps its references. The file's header comment carries D2's justification for the rebuild. `EXPECTED_SCHEMA_VERSION` becomes 8
  - [ ] `docs/store-contract.md`: the state, the two columns, who writes each (`handle_pause` writes `request_id` with the held insert and never changes it; `start_ended_held` writes `start_attempted_at`), the four new `waiting_reason` values, version 8, and the rebuild's justification. Update stale-version assertions in `tests/store/test_migrations.py` and the schema pin in `tests/store/test_schema_holds_no_mirrored_state.py`; these and the pinning test are the only existing tests this task edits
  - [ ] Success: pyright shows only the non-exhaustive `match` errors that 1.4 fixes (list them in a note); existing store tests pass
- [ ] **1.2 Migration test**
  - [ ] `tests/store/test_migration_008.py` (model on `test_migration_006.py`): a version-7 database with a `claimed`, an `answered` and a `waiting_on_pm` question, each with `answers` rows, migrates to 8 with every `questions` and `answers` row field-for-field equal, `request_id` and `start_attempted_at` null, `foreign_key_check` empty; the `CHECK` list equals the `QuestionState` members (extend `test_vocabulary_pinning.py` for the new member); inserting `waiting_on_request` with a null `request_id` fails the `CHECK`; inserting it with one succeeds; a store stamped 9 is refused and left untouched
  - [ ] Success: checks pass except the pyright errors noted in 1.1
- [ ] **1.3 `QuestionRecord` fields**
  - [ ] `store/models.py`: `QuestionRecord` gains `request_id: str | None` and `start_attempted_at: datetime | None`. `store/sql.py` `QUESTION_COLUMNS` gains the two columns at the end; `store/question_rows.py` maps them (`optional_text`, `optional_timestamp`). Every place that builds a `QuestionRecord` by hand (tests, `question_support.py`) gets the new fields
  - [ ] Success: pyright shows the same errors as 1.1 and no new ones
- [ ] **1.4 The open clause and every `match` arm**
  - [ ] `store/sql.py` `_OPEN_QUESTION_CLAUSE` and `store/question_closing.py` `_OPEN_PARAMETERS` gain `waiting_on_request` (update the clause's parameter comment). `store/question_closing.py` `dismiss_question`: `WAITING_ON_REQUEST` joins the `CLAIMED | WAITING_ON_PM` arm (D8)
  - [ ] `operations/question_sweep.py` `_judge`: `WAITING_ON_REQUEST` is treated as `WAITING_ON_PM` (D8). `operations/pause_class.py`: add `PauseClass.WAITING_ON_REQUEST`, returned by `classify_pause` for that state. `operations/pause_existing.py` `handle_existing` needs no arm yet: its `case _` already raises `ValueError` for a class it does not handle, and task 5.2 adds the real arm
  - [ ] Add `pause_class` consumers the new class reaches: find them with `grep -rn "PauseClass\." src/amoeba` and give each exhaustive `match` or set an explicit arm (status code is task 7)
  - [ ] `docs/cli-contract.md`: the `waiting_on_request` pause-class entry (`tests/test_contract_docs.py` requires every `PauseClass` value but `NOT_PAUSED` backticked there, so section 1's commit fails without it)
  - [ ] Success: pyright clean
- [ ] **1.5 Tests for 1.3 and 1.4**
  - [ ] `tests/store/test_questions.py` and `test_question_closing.py`: a `waiting_on_request` row round-trips its two fields; it is returned by the open-question reads (`open_questions`, `member_open_questions`, the run and member open reads, the answering-run and run-id sets); `dismiss_question` closes it `dismissed` and compare-and-set refuses a stale `updated_at`
  - [ ] `tests/operations/test_question_sweep.py`: a held row of a run that moved on closes `run_moved_on`, and `run_gone` for a gone run; a held row of a run still paused is left. `tests/operations/test_pause_class.py`: the state classifies as `WAITING_ON_REQUEST`
  - [ ] `tests/operations/test_rm.py` (or the `member_open_questions` test): `rm` of a sender with a held question refuses until the question is dismissed
  - [ ] Success: checks pass; no existing 223 or 228 test function or assertion changed (Context)

**Commit**: `feat: add waiting_on_request question state in migration 008`

## 2. Pure pieces: link, passage, vocabulary (D1, D5, D10; step 2)

- [ ] **2.1 `operations/request_link.py`**
  - [ ] `find_request_link(question, resolve) -> LinkResult`, pure: `resolve` is a callable from a candidate id to whether it is a `request` row from the question's member (supplied by the caller, so the module reads no store; the design's one-argument `find_request_link(question)` cannot resolve ids while staying pure, and 9.3 amends it). The marker words, the id-character pattern and the `NoLink` / `Link(request_id)` / `BadLink(detail)` types are defined here once. Matching exactly as D1: every `amoeba-request` (case-insensitive; `-`, `_` or a space between the words), then `:` or `=`, optional spaces and quote or bracket characters, then a run of `[A-Za-z0-9._-]`; a trailing `.` is tried with and without; each candidate compared for equality with `resolve`. One distinct resolved id is `Link`; a marker that resolves to none, or two or more distinct ids, is `BadLink` with a detail naming what was found; no marker is `NoLink`
  - [ ] Success: pyright clean
- [ ] **2.2 Link tests on real shapes**
  - [ ] `tests/operations/test_request_link.py`: a question ending with the marker line; one starting with Squadron's `…`; the id followed by a sentence-ending `.` (resolves with the dot removed) and an id that itself ends in `.` (resolves with it); quotes and brackets around the id; upper and mixed case; `amoeba_request=` and `amoeba request:`; the same id twice (one id, `Link`); two different resolved ids (`BadLink`); a marker whose id does not resolve, one that resolves only for another member (the callable says no), one for a note (callable says no); no marker, and a question naming a request only in words (`NoLink`)
  - [ ] Success: checks pass
- [ ] **2.3 `answering/request_passage.py` and the passage kind**
  - [ ] `answering/passages.py`: `PassageKind.REQUEST_RESULT = "request_result"`. `answering/request_passage.py`: `request_passage(request_id, replied_by, done_at, result, commit, version) -> Passage` (plain fields, pure; kind `request_result`, `source` the request id, `member` the replying project, `date` `done_at`, text the result followed by `commit:` and `version:` lines when present, as D5)
  - [ ] `passages.py` is 416 lines, so it gains no logic: the placement and any rendering for the request passage live in `answering/request_passage.py`. `add_request_passage(kept, request)` there appends the request passage after the rules, plan and program passages, numbered as the others are, never trimmed. `assemble` (keyword arguments `program_sources`, `max_chars`, `source_commit`) gains an optional keyword `request` (a `Passage`) and exactly one call, to `add_request_passage`, before its size check, so the whole set over `passages_max_chars` stays the existing `sources_too_large`. `render_passages` is unchanged (it renders any passage by its fields; if 2.4's rendering test shows the request passage needs its own shape, that code goes in `request_passage.py`). `passage_refs` records it with the request id as `source`
  - [ ] Success: pyright clean
- [ ] **2.4 Passage tests**
  - [ ] `tests/answering/test_passages.py` and a new `tests/answering/test_request_passage.py`: the passage's fields and text with and without `commit` and `version`; `assemble` places it after the program passages; it survives when PM answers are trimmed (the Technical Requirements line); an oversized set is `sources_too_large`; `passage_refs` gives the request id as source; rendering shows kind, member and date
  - [ ] Success: checks pass
- [ ] **2.5 Prompt sentence in both steps**
  - [ ] `answering/answering.yaml`: both steps' kinds lists (the lines naming the passage kinds) gain `request_result`, plus the one sentence of D5 (a `request_result` passage is the reply another project in the program gave to a request this project sent; its member line names that project). Nothing else in either prompt changes
  - [ ] Update `tests/answering/test_pipeline_yaml.py`'s constants test for the new word and sentence; run `sq run --validate` on the edited file through the existing `tests/live/answering/test_validate.py` (`uv run pytest tests/live/answering/test_validate.py`)
  - [ ] Success: the YAML-constants test and the live validate test pass
- [ ] **2.6 Vocabulary: reasons, outcome, result field**
  - [ ] `answering/values.py` `DeclineReason` adds `request_declined`, `request_cancelled`, `request_expired`, `request_unknown`. `operations/pause_models.py`: `HandlePauseOutcome.HELD = "held"`; `HandlePauseResult` gains `request_id: str | None = None`. The CLI and MCP render `held` as exit 0 and print the new field wherever the result's other fields print (find with `grep -rn "answering_run_id" src/amoeba/cli src/amoeba/mcp`)
  - [ ] `docs/cli-contract.md`: the `held` outcome, the `request_id` field and the four reasons under `handle-pause`
  - [ ] Success: pyright clean; `tests/cli` tests for `handle-pause` output pass; any exhaustive `match` on `HandlePauseOutcome` has an arm for `HELD`

**Commit**: `feat: add the request link, request_result passage and hold vocabulary`

## 3. Held-question store (D2, D3, D4, D7; step 3)

- [ ] **3.1 `store/sql_held.py` and `store/held_questions.py`**
  - [ ] `sql_held.py` holds the statements; `held_questions.py` holds the functions, each taking a transaction: `insert_held(transaction, new, request_id, now) -> bool` (one `INSERT … ON CONFLICT (run_id, paused_at) DO NOTHING`, state `waiting_on_request`, `request_id` set, `claimed_at` and `updated_at` now; False on conflict, as `insert_question`). A `BadLink` row is inserted by `hold_new` through the existing `insert_question` (`waiting_on_pm`, `request_unknown`), so no second insert function is added
  - [ ] `held_rows(transaction) -> list[QuestionRecord]` (every `waiting_on_request` row, oldest first); `claim_held(transaction, key, *, answering_run_id, passages, slice_label, source_commit, now) -> bool` (compare-and-set `WHERE state = 'waiting_on_request'`; sets `claimed`, those columns, and `claimed_at` and `updated_at` to now, D3); `settle_held_waiting(transaction, key, *, reason, detail, now) -> bool` (compare-and-set from `waiting_on_request` to `waiting_on_pm`; leaves `claimed_at`, D3; `updated_at` now); `mark_start_attempted(transaction, key, now) -> None` (a plain write of `start_attempted_at` only, not touching `updated_at`)
  - [ ] Success: pyright clean
- [ ] **3.2 Store tests**
  - [ ] `tests/store/test_held_questions.py`: insert stores `request_id` and returns False on a repeat; `claim_held` moves the row to `claimed` with the new fields and resets `claimed_at` and `updated_at`, keeps `request_id`; it returns False for a row not held (claimed, answered, closed, missing); `settle_held_waiting` sets reason and detail, keeps `claimed_at`, returns False for a row no longer held; two claims on one row: exactly one returns True; `mark_start_attempted` changes `start_attempted_at` and leaves `updated_at` equal; `held_rows` returns only held rows, oldest first; `tests/store/test_members_queried_in_one_place.py` still passes
  - [ ] Success: checks pass

**Commit**: `feat: add the held-question store functions`

## 4. The held claim (D5, D6; step 3)

- [ ] **4.1 Shared answer-limit helper and `_prepare`'s request**
  - [ ] `operations/pause_claim.py`: extract the answer-limit check in `start_new_claim` into one helper both claim paths call, returning the `_Failed` or nothing; behavior of `start_new_claim` unchanged. `_prepare` gains an optional `request` (a small frozen dataclass of the plain fields `request_passage` takes, defined beside `_Prepared`); with one it builds the `Passage` with `request_passage(...)` and passes it as a new optional `request` argument of `operations/pause_context.py` `gather` (signature `store, checkout, member, run_facts, settings, run`), which hands it to `assemble`; no second gather
  - [ ] Success: pyright clean; the existing tests of the two claim paths pass unchanged: `tests/operations/test_handle_pause.py` (exercises `start_new_claim`; `test_an_answer_limit_already_met_waits_and_starts_nothing` and `test_a_pm_answer_gives_a_run_at_its_limit_another_automatic_answer` cover the shared limit helper), `tests/operations/test_pause_existing.py` (exercises `restart_dead_claim`, e.g. `test_a_run_that_does_not_exist_and_an_old_claim_is_restarted_under_a_new_id`) and `tests/operations/test_every_state_exits.py` (`test_claimed_exits_by_the_dead_claim_path`)
- [ ] **4.2 `start_held_claim` and `restart_dead_claim`'s `request_id`**
  - [ ] `pause_claim.start_held_claim(store, config, deps, target, request)`: the D6 steps in order: limit (at the limit `settle_held_waiting` with `answer_limit_reached`, no run starts, result `waiting_on_pm`); `_prepare` with the request (`SourcesProblem` or `ScratchFailure`: `settle_held_waiting` with the existing reason, scratch discarded); `claim_held` (lost compare-and-set discards the scratch and returns `skipped / already_claimed`, or `superseded` when the row is no longer held); `_run`. Each result built with the existing `waiting_result`, `skipped`, `superseded_result` helpers, carrying `request_id`
  - [ ] `restart_dead_claim` gains an optional `request_id`; with one it reads the request with `get_message` (own read transaction), passes it to `_prepare`, and a request no longer found is `_Failed(request_unknown)` which `_settle_dead_claim_waiting` records. `pause_existing._claimed` passes `existing.request_id`; nothing else in it changes
  - [ ] Size: `pause_claim.py` is 233 lines; 4.1 and 4.2 add about 85 (limit helper, request dataclass, `_prepare`'s request, `start_held_claim`, `restart_dead_claim`'s read), about 320 in all. The design keeps `start_held_claim` beside `_prepare` and `_run`, so the split moves the waiting-settle helpers instead: `_record_waiting` and `_settle_dead_claim_waiting` (and the held path's `settle_held_waiting` call wrapper) go to a new `operations/claim_waiting.py`, leaving `pause_claim.py` near 275. `tests/test_import_boundaries.py` still passes
  - [ ] Success: pyright clean
- [ ] **4.3 Held-claim tests**
  - [ ] `tests/operations/test_pause_claim_held.py` (with the fake `sq`, stub `cf`, `pause_support.py`): a held row and a `done` request: the row is `claimed` with `request_id` kept, one answering run started, its scratch `passages.md` contains the `request_result` passage with the result and version, and the answer settles and resumes; at `answer_limit` the row goes to `waiting_on_pm / answer_limit_reached` and the fake `sq` shows no run started; a sources problem and a scratch failure each settle `waiting_on_pm` with the existing reason; a second call after the first claimed returns `skipped / already_claimed`; a row dismissed between prepare and claim returns `superseded` and the scratch is gone; no store transaction is open while the answering run and the resume run (the fake `sq` start, poll and resume hooks each take a write transaction on the same store)
  - [ ] `tests/operations/test_pause_existing.py`: a dead held claim (`not_found`, old) restarts through `restart_dead_claim` with the request passage in the new scratch; one whose request was pruned settles `waiting_on_pm / request_unknown`; a young held claim is `skipped / already_claimed`
  - [ ] Success: checks pass

**Commit**: `feat: claim and run an answering run for a held question`

## 5. Hold and evaluate (D1, D3, D4; step 3)

- [ ] **5.1 `operations/pause_held.py`**
  - [ ] `hold_new(store, config, deps, target, link)`: for a `BadLink` insert the row `waiting_on_pm` with `request_unknown` and the link's detail through `insert_question` (no model, no claim; `skipped / already_claimed` on conflict); for a `Link` insert the held row with `insert_held` (conflict is `skipped / already_claimed`), then call `handle_held`. A `StoreError` propagates (exit 3, row as it was)
  - [ ] `handle_held(store, config, deps, target, row)`: reads the request with `get_message` and `effective_state` in one read transaction, then acts by D4's table: `open` or `accepted` stays held, outcome `held` with `request_id` and the request's state in `detail`; `done` goes to `pause_claim.start_held_claim` with the request's plain fields; `declined`, `cancelled`, `expired` and no row each `settle_held_waiting` with the table's reason. `waiting_detail` is the request's `reason` cut by `cut_to_bound`, or "the request ended with no reason"; for a missing row, the pruned text of D4. A lost compare-and-set is `superseded`. No claim, scratch or dead-claim logic here
  - [ ] Success: pyright clean
- [ ] **5.2 Wire into `handle_pause` and `handle_existing`**
  - [ ] `operations/handle_pause.py` `_handle_polled`: with no row and an `UNHANDLED` class, call `find_request_link` (its `resolve` reads `get_message` and compares `kind` and `from_member`, in one read transaction) and take `hold_new` for `Link` and `BadLink`, `start_new_claim` for `NoLink`. `pause_existing.handle_existing`: add the `PauseClass.WAITING_ON_REQUEST` arm calling `handle_held`
  - [ ] Success: pyright clean; a held row reaching `handle_existing` no longer hits its `case _` `ValueError`
- [ ] **5.3 Hold and evaluation tests**
  - [ ] `tests/operations/test_pause_held.py`, holding: a question with a marker for an `accepted` request returns `held`, row `waiting_on_request`, run still paused, no answering run; a second `handle_pause` re-reads and stays held; a request already `done` at the first call resumes the run in that call; a question naming a request only in words takes the ordinary answering path
  - [ ] Same file, request ends: `declined`, `cancelled`, `expired` (an `open` request past its TTL, no sweep run) and a pruned request each give `waiting_on_pm` with the matching reason and the request's reason in `waiting_detail` (and the no-reason text)
  - [ ] Same file, bad links: a marker for an unknown id, another member's request, a note, or two requests gives `waiting_on_pm / request_unknown` with a detail and no `sq` run
  - [ ] Same file, races and errors: two `handle_pause` calls racing on a `done` request (`tests/operations/test_state_move_concurrent.py` is the model): one claims, the other returns `already_claimed`, one answering run exists; a `StoreError` on the request read is exit 3 with the row unchanged
  - [ ] Success: checks pass

**Commit**: `feat: hold a paused run on a request and settle it by the request's state`

## 6. The start trigger (D7; step 4)

- [ ] **6.1 Move `resolve_amoeba_script` and add `Deps.amoeba_script`**
  - [ ] New `amoeba_script.py` at the package root: `resolve_amoeba_script` and `AmoebaScriptMissing` moved from `mcp/detached.py` (which imports them, so its callers and tests are unchanged). `operations/deps.py`: `Deps` gains `amoeba_script: Callable[[], Path]`, which `production_deps` sets to `resolve_amoeba_script`; every test `Deps` builder (find with `grep -rn "Deps(" tests`) supplies a fake
  - [ ] Success: pyright clean; `tests/mcp_server` and `tests/test_import_boundaries.py` pass unchanged
- [ ] **6.2 `operations/request_release.py`**
  - [ ] `start_ended_held(store, config, deps)` as D7: read the held rows and each request's `effective_state` in one read transaction; a row qualifies when its request is terminal or gone and `start_attempted_at` is null or at least `answering_wait_seconds` old; never-attempted first, then oldest attempt; at most `MAX_STARTS_PER_CALL` (5); for each, `mark_start_attempted` (own write transaction), then `deps.spawn` of `[script, "handle-pause", "--json", "--", run_id]` in the row's `checkout`, logs `logs/request-release/<run id>-<UTC stamp>.{stdout,stderr}.log` (directory name a constant, built under `deps.logs_dir` with `LOG_STAMP_FORMAT` from `operations/resume.py` and the stdout and stderr suffix constants `wiring.detached_logs` uses). The caller never waits. `START_BOUND_SECONDS = BUSY_TIMEOUT_SECONDS × (1 + MAX_STARTS_PER_CALL)` defined here
  - [ ] Failures as D7: a returned `LaunchError` appends `result_entry(run_id, Path(row.checkout), "start_failed", None, detail, now)` (and `error_entry(run_id, Path(row.checkout), error, now)` below) and logs `logger.error`; `AmoebaScriptMissing` is caught by that type, appends an `error_entry` for each row it would have started, logs `logger.exception`; a `StoreError` from this function's own reads or writes is caught by that type and logged `logger.exception`. None is re-raised, each with a comment saying why (the operation's own work has committed; the rows are found again by the next call)
  - [ ] Success: pyright clean
- [ ] **6.3 `start_ended_held` tests**
  - [ ] `tests/operations/test_request_release.py` (fake `spawn`, fake `amoeba_script`, seeded held rows and messages): a held row whose request is `done`, `declined`, `cancelled`, `expired` by TTL with no sweep, and gone is started with the exact argv and cwd; `open` and `accepted` are not; a row attempted less than `answering_wait_seconds` ago is not started and one attempted longer ago is; never-attempted rows start before attempted ones; with `MAX_STARTS_PER_CALL` + 2 rows only 5 start and the rest are untouched; a `LaunchError` writes a `start_failed` calls-log line and leaves the row held and `start_attempted_at` set; a missing script writes an error line per row and does not raise; a `StoreError` during the read is logged and does not raise; no store transaction is open during `spawn` (the fake spawn asserts it can take a write transaction)
  - [ ] Success: checks pass
- [ ] **6.4 Call sites: `wiring.invoke` and `handle_pause`**
  - [ ] New `wiring_release.py` holds the constant `START_AFTER_OPERATIONS` (the `OperationName`s `send`, `reply`, `cancel`, `add`, `rm`, `status`, `list`) and `start_after(name, store, config, deps)`, which calls `start_ended_held` for those names only. In `wiring.py` (342 lines, so no logic added) rename `invoke`'s existing `match` body to a private `_dispatch` with the same arguments and have `invoke` call it, then `start_after` once after the operation's transaction has closed, and return the operation's result unchanged: one call for all arms, not seven. `operations/handle_pause.py` calls it last, beside `_prune_note`, after any resume. `inbox` stays a read. Neither call can change a result or raise
  - [ ] Success: pyright clean
- [ ] **6.5 Wiring tests and the timing bound**
  - [ ] `tests/test_wiring.py` and `tests/operations/test_handle_pause.py`: after each operation in `START_AFTER_OPERATIONS` an ended held row is started, through both `wiring.invoke` doors (CLI and MCP `call_tool`); after `inbox` it is not; the operation's result is identical with and without held rows; a request ended by each of `reply`, `cancel`, TTL expiry and the `rm` of its addressee gets its held question started by the next such operation; for the `rm` case the started `handle_pause` is run to the end and the question is `waiting_on_pm / request_cancelled` with `waiting_detail` `member_removed` (D8); a child started by `handle_pause` runs `start_ended_held` at its end (a batch over the cap drains in two rounds)
  - [ ] `tests/test_message_timing.py` (240's test): add `START_BOUND_SECONDS` to the worst case of `send`, `reply` and `cancel` (240's task comment says this slice does it), still asserting the total is below `MCP_CALL_DEADLINE_SECONDS` and that the failing-bound test still fails; also assert `START_BOUND_SECONDS` equals `BUSY_TIMEOUT_SECONDS × (1 + MAX_STARTS_PER_CALL)`. `run_in_process` (`mcp/in_process.py`) applies `MCP_CALL_DEADLINE_SECONDS` to `status` and `list` too, so the test also covers them: their worst case (count their `cf` lookups and store waits by reading the operations, as 240's test does for the message operations) plus `START_BOUND_SECONDS` is asserted below `MCP_CALL_DEADLINE_SECONDS`; if it reaches it, write `BLOCKED:` with the computed numbers under this task (the design's start bound would have to change)
  - [ ] `tests/operations/test_request_release_child.py`, the one non-live test of the real detached child: `production_deps()`'s real `amoeba_script` (`resolve_amoeba_script`) and real `deps.spawn`, against a throwaway `AMOEBA_HOME` fixture store, with the stub `sq` (`tests/sq_stub.py`) first on the child's `PATH` and a seeded held row whose request is open. `wiring.invoke` of `reply` marks the request `done`; the test then polls, every `CHILD_POLL_INTERVAL_SECONDS` up to `CHILD_WAIT_SECONDS` (named constants in the test), until the child's `logs/request-release/` stdout log exists, the child has exited and the question row has left `waiting_on_request`; at the bound it fails with the last row state and the child's log text. Nothing calls `handle_pause` by hand
  - [ ] Success: checks pass; 240's other tests pass unchanged
- [ ] **6.6 Load test for the start trigger**
  - [ ] `tests/load/test_start_ended_held_load.py` (model: `tests/load/test_report_release_load.py`): `3 × MAX_STARTS_PER_CALL` seeded held rows with ended requests (more than `MAX_STARTS_PER_CALL`); several threads, each with its own `Store`, call `start_ended_held` with a counting fake `spawn` while one more thread holds the store busy with repeated short write transactions. Assert: each call returns within `START_BOUND_SECONDS`, no call starts more than `MAX_STARTS_PER_CALL` rows, no row is started twice within `answering_wait_seconds`, and after enough rounds every row has `start_attempted_at` set
  - [ ] No CI wiring task: a bare `uv run pytest` (what CI runs) collects `tests/load`, since `pyproject.toml` ignores only `tests/live`
  - [ ] Success: checks pass

**Commit**: `feat: start handle-pause for held questions whose request has ended`

## 7. `status`, `decisions`, `dismiss`, `answer` (D8, D9; step 5)

- [ ] **7.1 `status` and `list`**
  - [ ] `operations/status_runs.py` takes the request states of the held rows as one more input (read once in the status transaction, through `get_message` and `effective_state`) and shows `waiting on request <id> (<state>)`, followed by `; handle_pause last started <start_attempted_at>` when set; a held row whose request is gone shows `(gone)`. `PauseClass.WAITING_ON_REQUEST` joins `MISSED_HOOK_CLASSES` in `operations/status_calls.py`. It gives no `next`. `operations/status_models.py`: `WaitingEntry` gains `request_id` (filled for rows whose reason is a `request_*` one); `status_waiting.py` fills it. `StatusResult` carries the quoted-data notice (240's constant, 240 D11) when any shown entry came from a request, including a `waiting_detail` from a request's reason
  - [ ] `docs/cli-contract.md`: the new `request_id` field and the held run line
  - [ ] Success: pyright clean
- [ ] **7.2 `status` tests**
  - [ ] `tests/operations/test_status_runs.py`, `test_status_waiting.py`, `test_status_calls.py`, `test_status.py`: a held run shows the text with the request's state; the start-attempt suffix appears only when set; the run's newest calls-log line appears as `last_call`, including a `start_failed` line; no `next`; a `waiting_on_pm / request_declined` entry carries `request_id` and the notice; a held question is not listed under "waiting on you"; `list -j` still equals `status`; `tests/test_read_side_defined_once.py` passes
  - [ ] Success: checks pass
- [ ] **7.3 `decisions`**
  - [ ] `operations/decisions_models.py`: `DecisionsRecord` gains `request_id`; `operations/decisions.py` fills it from the question row and shows the cited `request_result` passage in `based_on` with the request id as its source; `DecisionsResult` carries the quoted-data notice when any entry came from a request. `docs/cli-contract.md`: the `request_id` field, and in the `based_on` paragraph (the one that says `kind` is `pm_answer` for a PM precedent and null for the others) that a cited `request_result` passage has the request id as its `source` and a null `kind`, being a passage the store records no kind for
  - [ ] `tests/operations/test_decisions.py`: an answered held question shows `request_id`, the `request_result` citation with the request id, the check verdict and the resume outcome; an ordinary answer has `request_id` null and no notice
  - [ ] Success: checks pass
- [ ] **7.4 `dismiss`, PM `answer` and the exits of a held question**
  - [ ] `operations/dismiss.py`: no code change beyond 1.4 is expected; confirm `dismiss` of a `waiting_on_request` row closes it `dismissed` and the open-question rules let it through. `answer` on a held question works unchanged (`add_pm_answer` sets `answered`, then the resume)
  - [ ] `tests/operations/test_dismiss.py`, `test_answer.py` and `test_every_state_exits.py`: a held question has each exit and each is tested: resume (task 5.3 test cited by name), `waiting_on_pm` (declined), PM `answer` (answered, run resumed, the request no longer matters: a later `done` starts nothing for it), `dismiss` (closed `dismissed`, the request keeps its own state), `run_moved_on`, `run_gone`; after `dismiss` or `answer` a later `start_ended_held` does not start the run
  - [ ] Same files, refused resume: a held question that passed the check and screen but whose resume was refused shows `answered_unresumed` with `next = handle_pause` in `status`; calling `handle_pause` again resumes with the recorded answer and starts no answering run (the fake `sq` shows no new run)
  - [ ] Success: checks pass

**Commit**: `feat: show held questions in status and decisions and let dismiss and answer end them`

## 8. Live test (D5; step 6)

- [ ] **8.1 Fixture pipeline and rig**
  - [ ] `tests/live/hold/__init__.py`, `asks_request.yaml` (like `tests/live/pause/asks_question.yaml`: dispatches one step that does not edit or run anything and stops on a question whose last line is `amoeba-request: ` followed by the id the harness supplies as a pipeline parameter), `conftest.py` and `harness.py` modelled on `tests/live/pause` (two registered fixture repos in one program, `sq-s` and `cf-s`, real `sq`, the configured models; the marker id is a harness parameter, never a literal in the YAML). The harness sends the request, runs `amoeba handle-pause` in `sq-s` once (the hook's part, for the held first call only), replies from `cf-s` through the CLI (`amoeba reply`), and then only polls: every `POLL_INTERVAL_SECONDS` it reads the question row, `sq runs` and `decisions`, until the expected end or until `AUTO_RESUME_WAIT_SECONDS` passes (harness constants; the bound is the test config's `answering_wait_seconds` plus `resume_wait_seconds` plus a named margin), which fails the test with the last state read. After the first call nothing runs `handle-pause` by hand
  - [ ] Success: `uv run pytest tests/live/hold --collect-only` collects with the settings present; a missing setting fails by name
- [ ] **8.2 The three replies**
  - [ ] `test_hold_live.py`: (a) a faithful `done` (the result states what was added) after a held first call, replied through the CLI with no manual `handle-pause`: the poll sees the run resume by itself within `AUTO_RESUME_WAIT_SECONDS`, `decisions` shows the request id, the `request_result` citation, the check verdict and `resumed`; the first call before the reply returns `held`. (b) a `done` whose text tells the reader to go ahead and cut a release, for a member with `release` on its list: the question waits on the PM (`answerer_declined`, `check_said_no` or `reserved_term`) and the run is not resumed. (c) a `done` that does not settle the question (an unrelated reply): the question waits on the PM and the run is not resumed. Each test names which reasons it accepts
  - [ ] Success: `uv run pytest tests/live/hold` passes; `tests/live/pause` and `tests/live/answering` still pass

**Commit**: `test: add the hold live tier against real sq and models`

## 9. Documents and rules (Technical Scope, Departures)

- [ ] **9.1 Rules line and MCP instructions**
  - [ ] `docs/program-rules.md`: one line added to 240's Requesting block, per the design's Rules line section (a last line of `amoeba-request: ` followed by the id given to `send --id`, nothing else on that line; a placeholder, never a sample id), and one sentence above the block stating a repo replaces its pasted copy with the current text if it does not already say so. The MCP `INSTRUCTIONS` constant (find with `grep -rn "INSTRUCTIONS" src/amoeba/mcp`) gains the same rule
  - [ ] Tests: `tests/test_program_rules_doc.py` (the block holds no literal id and its flags test covers the line) and the `INSTRUCTIONS` test in `tests/mcp_server` contain the rule; no sample id sits in either
  - [ ] Success: those tests pass

**Commit**: `feat: tell agents to end a held question with the request marker line`

- [ ] **9.2 Contract docs**
  - [ ] `docs/store-contract.md`: the writers table, "How each state ends with nobody editing a file" (add `waiting_on_request`: resume, `waiting_on_pm`, `answer`, `dismiss`, the close sweep), the `waiting_reason` values, the `claimed_at` note (a claim of a held row resets it). `docs/cli-contract.md`: `handle-pause` (`held`), `dismiss`, and `status`/`list` (they start `handle-pause` for ended held questions; a held run's `last_call`). `docs/config-contract.md`: `answering_wait_seconds` is also the least time between two starts for one held question. `docs/squadron-hook.md`: a held question needs no further hook call. `docs/mcp-server.md`: the `status` and `list` rows
  - [ ] Success: `tests/test_contract_docs.py` passes
- [ ] **9.3 Parent documents and the design**
  - [ ] Amend `user/architecture/240-arch.agent-messaging.md` and `user/architecture/240-slices.agent-messaging.md` to match the design's Departures section (the five bullets), each in the document that holds the sentence: `request_unknown` for a marker that resolves to nothing (architecture and plan); the result given to the answering pipeline as a passage (in the plan's 242 entry, reword "makes its result the candidate answer"; in the architecture, reword "the result is recorded as the answer" at its `handle_pause` paragraph, as the design's Departures says); every request end starts the held run (the architecture's "When `reply` marks a request done, or the sweep expires it"); the question moves in the started `handle_pause` (the architecture's Expiry paragraph); the plan's 242 "Independent of 241" reworded to name the migration order
  - [ ] Amend `user/slices/242-slice.hold-and-release.md`: Development Approach step 6 ends at the live test and the live-store migration is the Phase 7 hand-off; Special Considerations' Live store paragraph installs from the target (not from the slice branch), at the Phase 7 hand-off, deletes the backup once the read-back passes (not "after the review passes"), and takes "the previous build" as the target commit recorded in 10.2; `find_request_link` shown with its `resolve` argument (2.1)
  - [ ] Success: `grep -n "waiting_on_request" docs/store-contract.md` finds the new rows; checks pass

**Commit**: `docs: document hold and release and amend the 240 parents`

## 10. Final verification

- [ ] **10.1 Rehearse the live migration on a copy**
  - [ ] Nothing live is written. `TMP=$(mktemp -d)`; `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup $TMP/amoeba.sqlite3"`; `cp ~/.config/amoeba/config.yaml $TMP/config.yaml`; `export AMOEBA_HOME=$TMP`
  - [ ] Record `SELECT version FROM schema_meta WHERE id = 1`, `SELECT count(*) FROM questions` and `SELECT count(*) FROM answers` on the copy. Expected version: the number of the last migration file before `008_waiting_on_request.sql`. If the live store is behind that (240 or 241 not yet migrated live), the one `uv run amoeba list` migrates the copy through every missing migration, so first add to the copy's config any keys 240 and 241 require, with values from `docs/config-contract.md`'s example. An empty or unreadable result is `BLOCKED:` with the raw query output, and the rehearsal stops
  - [ ] Read back: version equal to `EXPECTED_SCHEMA_VERSION`, the two row counts equal to the copy's, `PRAGMA integrity_check` ok, `PRAGMA foreign_key_check` empty, `uv run amoeba status` exits 0
  - [ ] Success: a note under this task gives the before and after version and the counts. `unset AMOEBA_HOME` and `rm -r $TMP` after
- [ ] **10.2 Final verification**
  - [ ] Run Verification Walkthrough steps 1 to 8 (all four checks; steps 2 to 7 under a throwaway `AMOEBA_HOME`; `uv run pytest tests/live/hold`); step 9 is the Phase 7 checklist below. Confirm `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py`, `tests/test_read_side_defined_once.py` and `tests/store/test_vocabulary_pinning.py` pass by name
  - [ ] Confirm 223, 228, 240 and 241 are unchanged apart from what the design names: `git diff {target}` shows no change to a 240 or 241 function's signature or body; the edits to existing code are only the files named in tasks 1 to 7 and 9.1; no existing test function or assertion in the 223, 228, 240 or 241 suites changed except the edits tasks 1.1, 1.3, 2.5, 6.1 and 6.5 name (`git diff {target} -- tests | grep '^-[^-]'` lists only lines in those files); every other change to an existing test file is an added test function in a file the Context lists
  - [ ] In `user/slices/242-slice.hold-and-release.md`: update the Verification Walkthrough where Phase 6 changed it (it says it is refined when Phase 6 is complete)
  - [ ] Success: all checks pass; every Success Criteria line in the design maps to a passing test named in a note under this task

**Commit**: `docs: refine the 242 walkthrough after final verification`

### Phase 7 hand-off (not tasks; nothing here is checked off in this file)

Phase 6 is complete when sections 0 to 10 are checked. These items are not tasks; the implementing agent does them in Phase 7, after the code review passes and the slice is merged (the merge is Phase 7's, not a task). Designated by `CLAUDE.md`.

**P7.0 No claim in flight**

`sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 "SELECT count(*) FROM questions WHERE state = 'claimed'"` must print 0 (a running `handle_pause` is old code and would fail on the new schema). A claim whose process is alive ends by itself within `answering_wait_seconds`; one whose process died is listed by `amoeba status` as `claim_stale` with `next = handle_pause`, and `amoeba handle-pause <run id>` in the run's directory settles it. Repeat until the count is 0; any other output, including an empty one, is `BLOCKED:` with the raw output

**P7.1 Update the live install**

From the target checkout: `uv run python scripts/update_live.py update`. It backs up the live store and config to `~/.local/state/amoeba/backups/<stamp>/`, appends any config key the new code requires (value from the config contract's example), installs the target, migrates the store through `amoeba list`, and checks the schema version, integrity, foreign keys, the member count and the installed `amoeba-mcp` tool list. If any check fails it restores the backup and reinstalls the previous commit itself, and exits 1. It needs `--previous <commit>` only when no earlier run has recorded the installed commit. Paste its output into the slice notes, and restart the client sessions it lists (they run the old `amoeba-mcp` until restarted). `uv run python scripts/update_live.py restore` puts the newest backup back later; a successful update deletes the older backup set
