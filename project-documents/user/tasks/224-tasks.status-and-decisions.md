---
docType: tasks
slice: status-and-decisions
project: amoeba
lld: user/slices/224-slice.status-and-decisions.md
dependencies:
- 223-slice.pause-handling
projectState: Slices 221 to 223 are merged. `src/amoeba` holds `answering/`, `upstream/`,
  `config/`, `store/` (migrations 001 and 002, `pm_marker` included), `operations/`
  (member resolution, `set_up`, `handle_pause`, `answer`, `Deps`) and the `set_up`,
  `handle_pause` and `answer` CLI commands. No read-side operation exists. Nobody
  has run Amoeba. `ecorkran/squadron#303` (`sq runs list --json`) shipped in `sq` 0.24.24.
dateCreated: 20261107
dateUpdated: 20261111
status: in_progress
turns: 12
promptTokens: 408751
cachedTokens: 350906
cacheWriteTokens: 57829
completionTokens: 12887
durationSeconds: 85.0
costUsd: 0.395605
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.3956055
    completionTokens: 12887
---

# Tasks: Status and Decisions

## Context Summary

- Working on slice 224 (design: `user/slices/224-slice.status-and-decisions.md`; decisions D1 to D10 are cited below by number).
- Adds the read side: `amoeba status`, `amoeba decisions`, `amoeba mark_read --through <seq>`. Moves 223's pause checks into one shared `classify_pause` (D3), and adds the schema test 222 D3 assigned here (D9).
- New modules: `operations/{pause_class,status,decisions,mark_read}.py`, `store/decisions.py`, `upstream/squadron/run_list.py`, `upstream/context_forge/projects.py`. Changed: `operations/handle_pause.py` and its helpers (calls `classify_pause`), `store/questions.py` (+ `open_questions`), `operations/deps.py` (+ `list_runs`, `project_names`), `cli/main.py`. Result and request models go in separate model modules (for example `status_models.py`) if a module nears ~300 lines; the design's public import paths stay valid through re-exports.
- No store migration. Imports stay `cli → operations → store, config, upstream`. No subprocess runs inside a store transaction. Every closed vocabulary (`PauseClass`, unplaced reasons, rejection codes, `mark_read` outcomes, `run_state`) is a `StrEnum` defined once. Request models validate raw input inside the operation. No new packages.
- No silent fallbacks: an unknown `sq` status stays a raw string, a missing field is an error, a member id missing from `cf` names is an error.
- `status` needs `sq runs list --json` from `ecorkran/squadron#303`, shipped in `sq` 0.24.24. Task 3.1 records real output; the proposed-shape stand-ins are used only if the installed `sq` lacks the command, and task 5 then replaces them.
- Read the slice 220 audit (`user/analysis/220-analysis.code-audit.md`: Verdicts for `inspection/`, `program/` and `cli/`; Dependencies rows for `program/members.py`, `cli/main.py` and `process/sq_outcome.py`; Differences from the architecture) and the design's "Audit items" section. Settled there: `status` reports no member readability and `program/` is deleted, `unplaced_runs` lists paused runs only with their checkpoint kind, and every `status` and `decisions` query is new (`inspection/` is deleted; its `questions.py` is only a column reference).
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Take 222 and 223's actual module paths over the design's sketches where they differ.
- Work on branch `224-slice.status-and-decisions`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slices: 225 scenario A trial, 226 MCP server.

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 224-slice.status-and-decisions {target}`
  - [x] Success: `git branch --show-current` prints `224-slice.status-and-decisions`
  - Note: Branch `224-slice.status-and-decisions` already existed (zero commits ahead of `main`, target `main`, tree clean); no new branch created.

- [x] **0.2 Confirm 223 and locate inputs**
  - [x] Confirm `src/amoeba/operations/handle_pause.py`, `answer.py`, `deps.py`, `store/questions.py`, `store/answers.py` and `upstream/squadron/run_file.py` exist and `amoeba handle_pause --help` runs; if not, write `BLOCKED: slice 223 not merged` under this task and stop
  - [x] Find the module and signature of each of: `poll_run` and its checkpoint parser, `read_run_facts`, `RunFacts`, `ExecutionMode`, `RunFileProblem`, `SkipReason`, `QuestionState`, `ResumeOutcome`, `PassageRef`, `AnsweringEvidence`, `Deps`, `answering_dir`, `answering_wait_seconds` (config), `resolve_member`, `project_of`, `members_of`, `programs`, `run_cf`, `CFProjectNotFound`, `CfCallFailed`, the exit-code constants, the typed errors, and the checks inside `pause_eligibility.py` and `pause_existing.py` (note "absent" for any that don't exist); note import paths
  - [x] Read the audit sections named in the Context Summary and the design's "Audit items". Note whether `src/amoeba/program/`, `src/amoeba/inspection/` and `src/amoeba/process/` still exist; if `program/` does, it is deleted in task 3.8 (no member readability). Note where `poll_run`, `SQ_EXECUTABLE` and `run_cf` landed (221 expects `upstream/squadron/run_outcome.py` and `upstream/context_forge/cli_call.py`)
  - [x] Find the columns of `questions`, `answers` and `pm_marker` in the migrations (names of the `seq`, `recorded_at`, `answered_by`, `cited`, `resume_*`, `last_seen_seq` columns)
  - [x] Check whether `sq runs list --json` exists in the installed `sq` (`sq runs list --help`); note the result under this task
  - [x] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [x] Success: a note lists each import path, the column names, the `sq runs list` result and the baseline result
  - Note: Import paths (all exist; `amoeba handle_pause --help` runs): `operations/{handle_pause,answer,deps,pause_eligibility,pause_existing,pause_models,pause_results,pause_claim,members}.py`; `store/{questions,answers,programs,models,vocabulary,question_json,row_values}.py`; `upstream/squadron/{run_file,run_outcome,errors}.py`; `upstream/context_forge/{cli_call,project_of,target_read}.py`. `poll_run`, `SQ_EXECUTABLE`, `RunCheckpoint` (the checkpoint parser; `paused_at_text`), `parse_checkpoint_kind`, `CheckpointKind`, `RunOutcome` in `upstream/squadron/run_outcome.py`; `read_run_facts`, `RunFacts`, `ExecutionMode`, `RunFileProblem` in `upstream/squadron/run_file.py`; `QuestionState`, `ResumeOutcome` in `store/vocabulary.py`; `PassageRef`, `AnsweringEvidence`, `AnsweredBy`, `DeclineReason` in `answering/values.py`; `Deps` (+`production_deps`, `RUN_POLL_TIMEOUT_SECONDS`) in `operations/deps.py`; `answering_dir`, `store_path`, `config_path`, `squadron_runs_dir` in `config/home.py`; `answering_wait_seconds` on `UserConfig` (`config/user_config.py`); `resolve_member`, `ContextForgeError`, `NotAProject`, `NotInProgram` in `operations/members.py`; `project_of`, `CFProject`, `CFProjectNotFound` in `upstream/context_forge/project_of.py`; `run_cf`, `CfCallFailed`, `CfRun`, `output_head` in `upstream/context_forge/cli_call.py` (`CF_*` command words in `target_read.py`, pinned by a defined-once test); `SquadronError` in `upstream/squadron/errors.py`; exit codes `EXIT_OK/REJECTED/USAGE/ERROR` in `cli/main.py`; `StoreError`/`StoreRowError` in `store/errors.py`; `programs`: absent as a function (only `get_program`, `get_member`, `members_of`, `member_settings` in `store/programs.py`; 3.3 adds the list-all read); `project_names`, `list_runs`: absent. Checks formerly in `pause_eligibility.py`/`pause_existing.py`: run/kind/text, answering_run, membership, prompt-only, other_member, and row-state dispatch. `src/amoeba/program/`, `inspection/`, `process/` do not exist (nothing to delete in 3.8). Columns: questions: run_id, paused_at, member_id, question, checkout, state, answering_run_id, waiting_reason, claimed_at, updated_at (001) + slice_label, source_commit, passages, waiting_detail, evidence (002); answers: seq, run_id, paused_at, answered_by, answer, recorded_at, resume_outcome (001) + cited, resume_detail, resume_log, resume_at (002); pm_marker: id, last_seen_seq. `sq` is 0.24.26 and has `sq runs list --json` (so 3.1's stand-ins are skipped; 5.1's recording is done in 3.1). `cf` is 0.19.26. Baseline: format, ruff, pyright clean; 1221 tests pass.

## 1. Extract `classify_pause` (D3)

- [x] **1.1 `PauseClass` and `classify_pause` and tests**
  - [x] Create `operations/pause_class.py` with `PauseClass` (`StrEnum`, the ten D3 classes: `not_paused`, `other_checkpoint`, `no_question_text`, `prompt_only`, `unhandled`, `claim_live`, `claim_stale`, `waiting_on_pm`, `answered_unresumed`, `settled`) and `classify_pause(outcome, question_row, latest_answer, run_facts, claim_age_limit, now) -> PauseClass`
  - [x] Implement from the checks now in `pause_eligibility.py` and `pause_existing.py`, in the D3 table's rules. `run_facts` is passed as a value; the function reads no file, store or process. `not_paused` first, then kind, then question text; with no row, `execution_mode` picks `prompt_only` or `unhandled`; with a row, state and latest answer outcome pick the rest, and claim age against `claim_age_limit` picks `claim_live` or `claim_stale`
  - [x] The module imports nothing from `store` or `upstream.squadron` except value types
  - [x] One test per `PauseClass`, built from the D3 table's "When" column. Include: claim exactly at the limit, `answered` with latest outcome null, `refused`, `resumed` and `not_delivered`, no row with each `execution_mode`
  - [x] Success: module imports; pyright strict clean; tests pass

- [x] **1.2 Wire `handle_pause` to `classify_pause`**
  - [x] Replace the run, row and run-file checks in `handle_pause` and its helpers with a call to `classify_pause`, mapping each class to the action in D3's `handle_pause` column. The `answering_run` and membership checks stay before it. A `RunFileProblem` still raises `SquadronError`. `SkipReason` values do not change. `run_facts` is read only when no row exists and the run is a paused `agent_question`
  - [x] Success: module imports; pyright strict clean
  - [x] Success: 223's `handle_pause` and `answer` tests pass unchanged (no edit to them)
  - Note: Deviation: `check_eligibility` keeps reading `run_facts` after the membership check whatever the row state (as in 223), instead of only when no row exists. Reason: 223's unchanged `test_pause_eligibility` (type-checked by strict pyright) reads `Eligible.run_facts.params` as non-optional, and `restart_dead_claim` needs the facts. `classify_pause` itself still uses `run_facts` only when no row exists, and `status` (3.6) reads them only then. `check_eligibility` uses `classify_run_only`/`classify_no_row` from `pause_class.py`; `handle_pause` calls `classify_pause` and `handle_existing` dispatches on the class (the stale/live claim age now comes from the class).

- [x] **1.3 Pin `waiting_reason` retention**
  - [x] Add a test that `add_pm_answer` and the automatic settle both leave `waiting_reason` and `waiting_detail` in place when they set `answered` (D5). If 223's tests already assert it for both paths, point to them in a note and add nothing
  - [x] Success: the pin exists for both paths and passes
  - Note: Added `tests/store/test_waiting_reason_retained.py` (PM answer path and automatic settle path).

**Commit**: `refactor: extract classify_pause from handle_pause`

## 2. Decisions, `mark_read`, names, schema test (D5, D6, D7, D9)

- [ ] **2.1 Decision reads (D5) and tests**
  - [ ] In `store/decisions.py` add `read_marker(store)` (returns `last_seen_seq`), `answers_since(store, *, after_seq=None, since=None, program=None)` returning each answer joined to its question, member and program, oldest first by `seq`, and `prior_answer_seq` (newest earlier answer to the same question, or null) per row. Exactly one of `after_seq` and `since` is given. The store takes `since` as UTC text; conversion is the operation's job (2.4)
  - [ ] Rows carry the raw columns the record needs: question text, `paused_at`, `slice_label`, `passages`, `waiting_reason`, `waiting_detail`, `evidence`, answer text, `answered_by`, `cited`, `resume_outcome`, `resume_detail`, `resume_at`. JSON columns are parsed with the 223 parsers (`store/question_json.py`)
  - [ ] Two programs, two members, several questions. Cases: `after_seq` filter, `since` filter (boundary inclusive), `program` narrowing, ordering by `seq`, `prior_answer_seq` for a PM answer after an automatic one and null for a first answer, an empty store
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.2 Member names (D6)**
  - [ ] Create `upstream/context_forge/projects.py`: `project_names(run) -> dict[str, str] | CfCallFailed`, one `cf list projects --json` call through `run_cf`, reading only `id` and `name`. Non-JSON output or an entry without `id` or `name` is a `CfCallFailed` quoting the output head
  - [ ] Add `project_names` to `Deps` (production value calls it with the cf runner)
  - [ ] Success: module imports; pyright strict clean

- [ ] **2.3 Record `cf list projects` fixture and tests**
  - [ ] Capture real `cf list projects --json` output into `tests/fixtures/context_forge/list_projects.json` from the installed `cf` (record `cf --version`), keeping an entry that lacks `projectPath` if the output has one; never hand-write. If none lacks it, say so in the fixture README and go on (the reader reads only `id` and `name`)
  - [ ] Tests: the real fixture parses to the right id-to-name map; non-JSON and a missing field each give `CfCallFailed`; a non-zero exit gives `CfCallFailed`
  - [ ] Success: tests pass

- [ ] **2.4 `decisions` request, rejections and tests (D5)**
  - [ ] Create `operations/decisions.py` with `DecisionsRequest(since?, program?)` (validated from a document, unknown fields rejected) and a shared `RejectCode` (`StrEnum`, defined once in `operations/reject_codes.py` for the three operations): `unknown_program`, `malformed`, `beyond_last_record`. `mark_read` (2.6) uses the last
  - [ ] `since` must be ISO-8601 with a UTC offset, converted to the store's UTC text; no offset or unparsable is `rejected / malformed`. Unknown `program` is `rejected / unknown_program` listing known ids. Without `since`, start after the marker
  - [ ] Tests: `since` without offset and garbage are `malformed`; unknown fields are rejected; unknown `program` lists known ids; a valid `since` converts to UTC text
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.5 `decisions` records and `read_through` (D5, D8) and tests**
  - [ ] In `operations/decisions.py` add `DecisionsRecord`, `DecisionsResult` (`outcome` `listed` or `rejected`, `records`, `read_through`, `marker`, `problems`) and `decisions(store, document, *, deps)`, using the request handling from 2.4
  - [ ] Each record has the D5 fields. `based_on` for `answerer`: cited passages (`id`, `kind`, `source`, `date`, from `cited` and the question's `passages`) plus the check verdict and reason from `evidence`; for `pm`: `waiting_reason` and `waiting_detail`, or null if the PM answered first. `resume`: `outcome`, `detail`, `at`
  - [ ] Members as `{id, name}` from one `project_names` call made after the store read. A member id missing from the names is a `ContextForgeError` naming it; `CfCallFailed` is raised as `ContextForgeError`
  - [ ] `read_through` is the last listed `seq` only when the listing started at the marker (no `since`), had no `program`, and is not empty; otherwise null. `marker` is the value read
  - [ ] Cases: default start after marker; `since` start; `program` narrowing; `read_through` null for each of `since`, `program`, empty; record fields for an `answerer` row and for a `pm` row after a waiting question and for a `pm` row with no waiting reason; PM override shows `prior_answer_seq`; member id missing from names raises; names failure raises with no store write
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.6 `mark_read` operation (D7) and tests**
  - [ ] Add `advance_marker(store, through)` to `store/decisions.py`: one `BEGIN IMMEDIATE` transaction; `through` above `MAX(answers.seq)` returns beyond-last-record without writing; otherwise `last_seen_seq = MAX(last_seen_seq, :through)` and returns previous and current. An empty answers table counts as `MAX = 0`
  - [ ] Create `operations/mark_read.py`: `MarkReadRequest(through: int >= 0)`, `MarkReadOutcome` (`StrEnum`: `moved`, `unchanged`, `rejected`), `MarkReadResult` (`outcome`, `previous`, `current`, `problems`), `mark_read(store, document)`. Beyond-last-record is `rejected / beyond_last_record`; negative or non-integer `through` is `rejected / malformed`
  - [ ] Cases: `moved`; `unchanged` for an equal and for a lower `through` (marker never moves back); `beyond_last_record` leaves the marker; `through` 0 on an empty store is `unchanged`; negative and string `through` are `malformed`; two threads advancing to different values leave the higher; a record written after a `decisions` call stays unread after `mark_read` with that call's `read_through`
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.7 Schema holds no mirrored state (D9)**
  - [ ] Add `tests/store/test_schema_holds_no_mirrored_state.py`: migrate a new store, read every `(table, column)` from `PRAGMA table_info`, assert equality with one pinned set. Each pinned column sits in a group by reason: record, membership, settings, marker (a dict of reason to columns, so the doc and test agree)
  - [ ] Update `docs/store-contract.md`: list each column under one reason; state that `questions.checkout` and `questions.slice_label` are record and are never read as current state
  - [ ] Success: tests pass; adding a column in a scratch edit fails the test (verify once, then revert)

**Commit**: `feat: add decisions and mark_read operations and schema test`

## 3. Runs list and `status` (D1, D2, D4, D8)

- [ ] **3.1 Fake `sq runs list` helper and proposed-shape fixtures**
  - [ ] If task 0.2 found `sq runs list --json` installed (`sq` 0.24.24 has it), do task 5.1's fixture recording now, then use the real fixtures in 3.2 to 3.8, skip the proposed-shape fixtures below, and mark 5.2's fixture swap done when 5.1 is. Only if the command is absent, write the stand-ins below
  - [ ] Extend the 223 fake `sq` helper to replay a named fixture for `sq runs list --json` and record its argv (so a test can see whether `--all` was passed)
  - [ ] Write fixtures under `tests/fixtures/squadron/runs_list_proposed/` in #303's proposed shape (fields: run id, pipeline, status, working directory, `checkpoint` as in `sq runs wait --json`): running run, paused agent question, paused other kind, `null` directory, an older paused run, a paused run of another directory. This is the one exception to the never-hand-write rule, because #303 has not landed: start each from the real `sq runs wait --json` fixture from 223 and add only the proposed fields. Add a README stating these are stand-ins for #303, replaced in task 5.1
  - [ ] Success: each fixture parses as JSON; the fake replays it and the argv record shows the call

- [ ] **3.2 `run_list.py` (D1) and tests**
  - [ ] Create `upstream/squadron/run_list.py`: `ListedRun` (`run_id`, `pipeline`, `status` kept as raw string when unknown, `working_directory: Path | None`, `checkpoint: (kind, paused_at, question) | None`), `RunListProblem`, `list_runs(run) -> list[ListedRun] | RunListProblem`. `checkpoint` is parsed by `poll_run`'s checkpoint parser so `paused_at` matches what 223 stores. No other module runs `sq runs list`
  - [ ] Non-zero exit, non-JSON and a missing field are each a `RunListProblem` quoting the output head. The `sq` timeout is the one `deps` passes to `poll_run`
  - [ ] Parse stdout only: a warning on stderr (real `sq` prints one when runs reference unavailable pipelines) is not a problem. Keep only the three checkpoint fields; ignore the rest (`step`, `verdict`, `review_file`, …). Reuse `poll_run`'s `sq` executable constant and checkpoint parser from where task 0.2 found them, and import nothing from `process/`. Test: a fixture with extra checkpoint fields and a stderr warning parses
  - [ ] Add `list_runs` to `Deps`. Where the caller turns a `RunListProblem` into `SquadronError` (exit 3), the message says `status` needs Squadron with #303
  - [ ] Each proposed fixture parses to the right `ListedRun`; the `null` directory gives `working_directory` None; an unknown status stays raw; one test per problem kind; a timeout is a `RunListProblem`; `paused_at` equals the value the checkpoint parser gives for the same checkpoint
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **3.3 Question reads and tests (D4)**
  - [ ] In `store/questions.py` add `open_questions(store, member_ids)`: every `waiting_on_pm` question of those members, with `slice_label`, `waiting_reason`, `waiting_detail`, `claimed_at` (as `since`), oldest first
  - [ ] Add `latest_rows_by_run(store, member_ids)`: for each run id that has a question of those members, the latest question row (by `claimed_at`) and that question's latest answer, keyed by `run_id`. Run ids are not known until `sq` is called, so this reads every run of the members up front; classification (3.6) looks runs up in it, and a run with no entry has no row. Add a read of programs, members and their programs for `status` (reuse `programs` and `members_of` if they fit). All reads happen in one transaction, before any `sq` or `cf` call
  - [ ] Tests: `open_questions` returns only `waiting_on_pm` rows of the given members (claimed, answered and other-member rows excluded), oldest first; `latest_rows_by_run` returns the newer of two questions on one run with its latest answer, and excludes other members' runs
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **3.4 Scope and tests (D2)**
  - [ ] In `operations/status.py` add `resolve_scope(store, directory, program, deps)`: `program` given resolves that program (unknown is `rejected / unknown_program` listing known ids); else inside a member gives that member's program; else every program. A `ContextForgeError` from the directory lookup propagates and never widens scope
  - [ ] Tests: three scopes; unknown program; a failing `cf` while resolving the directory raises; a program with no members is listed with no members
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **3.5 Run placement (D4) and tests**
  - [ ] Create `operations/status_placement.py`: `UnplacedReason` (`StrEnum`: `no_directory`, `directory_missing`, `lookup_failed`), `place_runs(listed, members_in_scope, answering_dir, project_of)`. Rules in order: `None` directory is unplaced `no_directory`; missing directory is unplaced `directory_missing` (before any `cf` call); directory under `answering_dir()` is dropped with no `cf` call; `project_of` gives `CFProjectNotFound` or a project in no program in scope: dropped; `CfCallFailed` or timeout: unplaced `lookup_failed` with the error text; a member in scope: listed under it
  - [ ] Cache `project_of` per directory for the call
  - [ ] `unplaced_runs` entries are kept for `paused` runs only (design "Audit items"): a running, failed or other-status run with no directory, a missing directory or a failed lookup is not listed. Each entry carries `checkpoint_kind` (the checkpoint's kind, raw if unknown). Test with the real fixture's mix: running and failed runs with `null` directories give no entry; a paused `agent_question` run with a `null` directory gives `no_directory` with kind `agent_question`
  - [ ] One test per rule, including a `project_of` timeout giving `lookup_failed`; two worktrees of one repo land on one member with a single `cf` call per directory; `lookup_failed` leaves the other runs placed; the scratch directory makes no `cf` call; a missing directory makes none; unplaced runs are not filtered by program
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **3.6 Classification and `next` (D3, D8) and tests**
  - [ ] Create `operations/status_runs.py`: for each placed paused run, take the question row and latest answer from `latest_rows_by_run` (3.3, read before any `sq` call), read `run_facts` only when no row exists and the run is a paused `agent_question`, call `classify_pause` with `answering_wait_seconds`, and build the run entry (`pause`, `detail`, `next`). A `RunFileProblem` gives `pause: run_file_unreadable` with the problem text and processing goes on. Non-paused runs have `pause` null
  - [ ] `detail`: kind for `other_checkpoint`; reason for `no_question_text`; resume outcome and reason for `answered_unresumed` and `settled`
  - [ ] `next` per D8: `handle_pause` with the run's `working_directory` as `directory` for `unhandled`, `claim_stale` and `answered_unresumed`; otherwise null here
  - [ ] `status` does not poll
  - [ ] One test per `PauseClass` through `status_runs`, plus `run_file_unreadable` with the rest shown; `next` for each of the three handled classes and null for others; non-paused run has no `pause`
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **3.7 Waiting questions and tests (D4, D8)**
  - [ ] Create `operations/status_waiting.py`: `RunState` (`StrEnum`: `at_pause`, `moved_on`, `not_listed`) and a function that builds the `waiting_on_pm` entries. Every `waiting_on_pm` question of a member in scope is listed, never dropped, joined to runs by `run_id` across the whole listing: `at_pause` (`next` is `answer` with `run_id`, `paused_at`), `moved_on` (detail gives the run's state, no `next`) or `not_listed` (no `next`). A claimed or answered question appears only as its run's `pause`
  - [ ] Tests: the three `run_state` values; a waiting question for a run no longer listed is `not_listed`; ordering follows `open_questions`
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **3.8 `status` operation (D2, D4, D8) and tests**
  - [ ] In `operations/status.py` add `StatusRequest(program?)`, `StatusResult` (`outcome` `listed` or `rejected`, `programs`, `unplaced_runs`, `problems`, as `DecisionsResult` does; `unknown_program` from 3.4 gives `rejected`), and `status(store, config, document, *, directory, deps)`. Flow per the design: scope (3.4); one store read (3.3); one `list_runs` call; place (3.5); classify (3.6); waiting questions (3.7); one `project_names` call; build the result
  - [ ] Every member in scope is listed, even with nothing to show. Members as `{id, name}`. `RunListProblem` and names failures are raised as `SquadronError` and `ContextForgeError`
  - [ ] No subprocess inside a store transaction: the store is read first
  - [ ] No member readability and no member checkout in the result (design "Audit items"): delete `src/amoeba/program/` if it still exists, and confirm nothing imports it or `Readable`/`Unreadable`. `unplaced_runs` entries are `{run_id, status, reason, checkpoint_kind}`
  - [ ] Cases: a member with nothing; two members in different programs under the all-programs scope; a `lookup_failed` run beside a waiting question that is still shown; `unplaced_runs` entries; an `sq` failure and a names failure each raise
  - [ ] Cross-check table test (D3): run the same fixtures through `status` and `handle_pause`; every `unhandled` or `claim_stale` run in `status` is one `handle_pause` does not skip
  - [ ] Success: module imports; pyright strict clean; tests pass

**Commit**: `feat: add run list reader and status operation`

## 4. CLI (D8)

- [ ] **4.1 CLI commands and tests**
  - [ ] In `cli/main.py` add `amoeba status [--program <id>]`, `amoeba decisions [--since <iso-8601>] [--program <id>]`, `amoeba mark_read --through <seq>`. Each prints its result model as JSON on stdout. The CLI alone builds `Deps` (the `project_names` and `list_runs` fields were added in 2.2 and 3.2). Only `status` loads the config
  - [ ] Exit codes use 222's constants: 0 result; 1 `rejected`; 2 usage; 3 `SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError` or any `StoreError`, message on stderr. If `cli/main.py` nears ~300 lines, put the three commands in a new `cli/read_side.py` registered from `main.py`
  - [ ] With fake `sq` and `cf` on `PATH` and the autouse `AMOEBA_HOME`: `status` prints JSON and exits 0; `status --program nope` exits 1; an `sq` without `runs list` exits 3 with a message naming `sq runs list --json`; `decisions` exits 0 with and without records; malformed `--since` exits 1; `mark_read --through 999999` exits 1; `mark_read` without `--through` exits 2; no test touches the developer's real home
  - [ ] Success: `uv run amoeba status --help`, `decisions --help` and `mark_read --help` print usage; tests pass

**Commit**: `feat: add status, decisions and mark_read commands`

## 5. After #303: real fixtures and walkthrough (D1, D10)

- [ ] **5.1 Record real `sq runs list` output**
  - [ ] Run `sq runs list --help` and note whether `sq runs list --json` exists. If it does not, write `BLOCKED: waiting on squadron#303` under this task and stop
  - [ ] Capture real `sq runs list --json` into `tests/fixtures/squadron/runs_list/`, producing each case with real `sq`: a running run and a paused agent question (both from 223's `tests/live/pause/asks_question.yaml`); a paused run of another kind (the pipeline recorded for that case in 223 task 2.2); a paused run in another directory (start the same pipeline from a second throwaway worktree); an older paused run (leave one pause unresolved, then capture after a newer run exists). For the `null`-directory run, use a pre-#303 run file already in `~/.config/squadron/runs/` if the listing shows one; otherwise copy a real listing and set that one run's directory to `null`, and mark the file as edited in the README. Record `sq --version` and the date in the README
  - [ ] If a listing prints a stderr warning about runs referencing unavailable pipelines, confirm those runs still appear in the stdout JSON; if any are missing, note which and whether a paused run could be among them (a missed hook on it would be invisible to `status`), and record it in the README
  - [ ] Run `sq runs list --json` with no flag while those runs exist. If the default omits the older paused run or the other-directory run, make `run_list.py` pass `--all` and drop completed runs itself (D1)
  - [ ] Success: each fixture parses; the note records whether `--all` was needed

- [ ] **5.2 Adjust `run_list.py` to the landed names**
  - [ ] Point the `run_list` tests at the real fixtures and delete `tests/fixtures/squadron/runs_list_proposed/`. Differences in field names change only `run_list.py` and its fixtures; if the landed shape differs in kind (not just names), write `BLOCKED: #303 shape differs: <how>` and stop
  - [ ] Success: the parser passes on every real fixture; `status` tests still pass

- [ ] **5.3 Verification walkthrough**
  - [ ] For walkthrough step 6, create `tests/live/pause/asks_unsettled_question.yaml` first: a dispatch whose question concerns a choice no rule file in the test member settles (so `handle_pause` declines to `waiting_on_pm`), modelled on `asks_question.yaml`
  - [ ] Run the design's Verification Walkthrough steps 1 to 7 from a throwaway worktree with a scratch `AMOEBA_HOME` and the wait keys set
  - [ ] Record each step's observed result in a note under this task. An unexpected result is a defect in this slice: fix it, or write `BLOCKED:` with the evidence
  - [ ] Success: the notes show `applied`, `pause: unhandled` with a `handle_pause` `next`, `resumed`, one `answerer` record with `read_through`, `moved` then no records, exit 1 `beyond_last_record`, a `waiting_on_pm` entry then a `pm` record with that `waiting_reason`, all-programs scope and exit 1 `unknown_program`

## 6. Final validation

- [ ] **6.1 Full checks**
  - [ ] Run the checks once; fix failures introduced by this slice
  - [ ] Success: all four pass; 223's tests pass unchanged; `run_list.py` is the only module that runs `sq runs list`; `PauseClass`, `UnplacedReason`, `RunState` and the rejection codes are each defined once

**Commit**: `feat: read real sq runs list output in status`
