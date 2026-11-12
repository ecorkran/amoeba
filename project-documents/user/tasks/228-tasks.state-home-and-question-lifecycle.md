---
docType: tasks
slice: state-home-and-question-lifecycle
project: amoeba
lld: user/slices/228-slice.state-home-and-question-lifecycle.md
dependencies:
- 223-slice.pause-handling
- 224-slice.status-and-decisions
projectState: Slices 222 to 225 are merged on main (schema version 2, six CLI commands).
  The live store, answering scratch and logs sit in ~/.config/amoeba/. No mcp package
  exists yet; 226 and 227 are designed and tasked, not built. Amoeba issues 34, 36
  and 37 are tracked as open (task 0.2 rechecks).
dateCreated: 20261112
dateUpdated: 20261112
status: not_started
turns: 36
promptTokens: 4262953
cachedTokens: 4063835
cacheWriteTokens: 199050
completionTokens: 81467
durationSeconds: 589.9
costUsd: 2.017688
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 2.017688400000001
    completionTokens: 81467
revision_number: 2
---

# Tasks: State Home and Question Lifecycle

## Context Summary

- Working on slice 228 (design: `user/slices/228-slice.state-home-and-question-lifecycle.md`; decisions D1 to D13 are cited by number). Effort 4/5.
- Delivers: state moves to `~/.local/state/amoeba/` (config stays in `~/.config/amoeba/`); a `closed` question state with `dismiss`, `retract` and an automatic close sweep; the answer limit counted since the PM's last answer; `set_up` `remove`; pruning with `prune_after_days`; the `wrong_checkout` skip and the calls log. Closes amoeba#34, #36 and #37 as task 0.2 finds them open; the final commit body has `Fixes #n` for each.
- New modules are listed in the design's Component Structure. Take the actual module paths and function names of 222 to 225 over the design's sketches where they differ. The behavior in the design is the contract.
- Migration `003` rebuilds `questions` once (the one exception to the `ADD COLUMN` rule, D3). `EXPECTED_SCHEMA_VERSION` becomes 3. No new packages; the move uses `sqlite3.Connection.backup`.
- Closed vocabularies (`ClosedReason`, `QuestionState.CLOSED`, `SkipReason.CLOSED` and `WRONG_CHECKOUT`, `PauseClass.CLOSED`, and the dismiss, retract and `set_up` problem codes) are each a `StrEnum` defined once. No silent fallbacks. A swallowed exception needs a comment saying why. Every racing write is a compare-and-set in one short `BEGIN IMMEDIATE`, with no transaction across a subprocess.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four.
- Tests use the autouse `AMOEBA_HOME` fixture, explicit throwaway paths for the two homes in move tests (never `Path.home`), the stub `sq` and `cf`. Destructive SQL only against throwaway stores. No sample id, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), including in docs that tests check.
- Out of scope: building MCP (226) and Scenario B (227). Task 0.1 makes the design's "Pending Planning Edits" to the 220 architecture and the 226 and 227 plans, on the target before the slice branch exists.
- Production database: tests touch throwaway stores only. Task 13.4 alone changes the live `~/.config/amoeba/amoeba.sqlite3` (the move, then migration `003`'s rebuild). `sql.md` ("Production Database Protection") requires the Project Manager to designate that store explicitly, and this file cannot: 13.4 begins by checking for it and writes `BLOCKED:` if absent.
- Work on branch `228-slice.state-home-and-question-lifecycle`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [x] **0.1 Update the 220, 226 and 227 plans on the target**
  - [x] On the target (read `cf config get git.integration_branch`; the target is its value, or `main` if empty) with a clean working tree, edit the planning documents. These are planning work, so they commit to the target, not the slice branch
  - [x] `user/architecture/220-arch.program-tool.md`: the operation table gains `dismiss` and `retract`; "The question record" gains the `closed` state with its three reasons and says a retracted PM answer is not precedent and a PM answer resets the answer limit; "Where things live" gains the two homes; a note says `status` closes records whose run has gone and prunes old files, is still bounded and adds no `sq` call
  - [x] `user/slices/226-slice.mcp-server.md` and `user/tasks/226-tasks.mcp-server.md`: eight operations, not six (find each count with `grep -n -i six`); the tool table gains `dismiss` and `retract`, in-process; the stdio smoke test lists eight tools; the MCP layer opens the store through `open_state_store`; the task that names who may call `amoeba_home()` names `state_layout()`, `config_home()` and `state_home()` instead, since `amoeba_home()` is removed
  - [x] `user/tasks/227-tasks.program-dependencies.md`: its `projectState` says the CLI and MCP server expose eight operations (225's six plus `dismiss` and `retract`), not six. Update `dateUpdated` in each edited file
  - [x] Success: no 226 or 227 line states a count of six operations or tools, and `amoeba_home` appears in neither 226 file

**Commit**: `docs: update the 220, 226 and 227 plans for slice 228`

- [ ] **0.2 Branch, inputs and baseline**
  - [ ] `git checkout -b 228-slice.state-home-and-question-lifecycle {target}` (the target from 0.1)
  - [ ] Confirm 222 to 225 are merged: `config/home.py`, `store/migrations.py`, `operations/handle_pause.py`, `operations/status.py`, `operations/decisions.py` exist, and `store/schema/` holds `001` and `002` only. If any is missing, write `BLOCKED: slices 222-225 not merged` under this task and stop
  - [ ] Run `gh issue view` for 34, 36 and 37 and note each state. The final commit's `Fixes #n` lines name only issues still open
  - [ ] Confirm `sq --version` is 0.24.24 or later (`working_directory` in schema-5 run files, D10). If it is older, write `BLOCKED: sq older than 0.24.24` under this task and stop
  - [ ] Run `sq runs list --help` and confirm it lists `--all` and `--json` (D4 depends on `--all`). If either is missing, write `BLOCKED: sq runs list lacks --all or --json` under this task and stop
  - [ ] Find the test helpers to reuse: the config builder (`tests/user_configs.py`), the handle and status rigs (`tests/operations/handle_rig.py`, `status_support.py`, `program_rig.py`), `tests/store/seed.py`, the stub `sq` (`tests/sq_stub*.py`), `tests/fixtures/squadron/`, and the AST tests (`tests/test_home_access.py`, `tests/test_import_boundaries.py`, `tests/test_store_safety.py`)
  - [ ] Find 224's schema pin test, the vocabulary pin test (`tests/store/test_vocabulary_pinning.py`) and the contract-doc test (`tests/test_contract_docs.py`); note what each enumerates
  - [ ] Run the checks once and note the baseline. Failures present before this slice are written down, not fixed
  - [ ] Success: `git branch --show-current` prints `228-slice.state-home-and-question-lifecycle`; a note under this task lists the target's name (13.4's restore uses it), each located path and the baseline result

## 1. Homes and `StateLayout` (D1)

- [ ] **1.1 Split the home functions**
  - [ ] In `config/home.py`: add `config_home()`, `state_home()`, `legacy_state_home()`, `calls_log_dir()` (`logs_dir() / "calls"`), and a frozen `StateLayout` (state home, store path, answering dir, logs dir, legacy home or `None`) built by one `state_layout()` function
  - [ ] `state_home()`: `$AMOEBA_HOME` when set (unchanged empty and relative errors), else `~/.local/state/amoeba`. `XDG_STATE_HOME` is not consulted (D1: the hook and the shell may differ in it). Name the path parts as constants
  - [ ] `config_path()` is under `config_home()`; `store_path()`, `answering_dir()`, `logs_dir()` are under `state_home()`. `legacy_state_home()` is `~/.config/amoeba` when `AMOEBA_HOME` is unset and it differs from `state_home()`, else `None`
  - [ ] Remove `amoeba_home()`. Let pyright list the callers, and update each. `cli/main.py` builds the layout once and passes `layout.answering_dir` and `layout.logs_dir` to `production_deps`
  - [ ] `status_placement.py` skips run directories under both `answering_dir` and the legacy `<legacy home>/answering` (D12). Pass the legacy home through `Deps` as an optional path, `None` when there is no legacy home
  - [ ] Success: pyright strict clean; existing tests pass with `AMOEBA_HOME` redirecting both homes

- [ ] **1.2 Home tests**
  - [ ] In `tests/config/test_home.py`: `XDG_STATE_HOME` set in the environment changes nothing; `AMOEBA_HOME` overrides both homes and gives `legacy_state_home()` of `None`; with neither set (a throwaway `HOME`), the state home is `~/.local/state/amoeba` and the config home `~/.config/amoeba`; `calls_log_dir()` is under `logs_dir()`
  - [ ] Confirm `tests/test_home_access.py` still passes: `config/home.py` alone reads `AMOEBA_HOME` and calls `Path.home`
  - [ ] Test: a run directory under the legacy `answering/` is skipped by placement (add to `tests/operations/test_status_placement.py`)
  - [ ] Success: tests pass; checks pass

## 2. Moving the legacy state (D2)

- [ ] **2.1 `store/relocate.copy_store` and `verify_copy`**
  - [ ] Create `store/relocate.py`. `copy_store(old, new, old_prefix, new_prefix, *, after_backup=None)`: `Connection.backup` from the old store into the new path, call `after_backup` if given (the seam for a crash inside the copy; production passes none), rewrite every `answers.resume_log` value that starts with `old_prefix` (the legacy home directory) to start with `new_prefix` (the state home), then `verify_copy`. It imports nothing from `config`
  - [ ] `verify_copy(old, new, old_prefix)` is public and runs the D2 step 3 checks: `PRAGMA integrity_check` is `ok`; schema version, every table's row count and `MAX(answers.seq)` match; no `resume_log` still starts with `old_prefix`
  - [ ] A `sqlite3.Error` or `OSError`, or a failed check, is logged with `logger.exception` at ERROR, deletes the target file, and raises `StoreRelocateError` (new, a `StoreError`, exit 3) naming the cause or check. The old file is never written
  - [ ] Success: module imports; pyright strict clean

- [ ] **2.2 `copy_store` tests**
  - [ ] Test: a seeded store with questions, answers (a `resume_log` under the old prefix, one outside it, one null) and programs copies with every row equal and only the matching `resume_log` values rewritten
  - [ ] Test: call `verify_copy` on a doctored copy for each check (a missing row, a changed version, a different `MAX(seq)`, a `resume_log` still under `old_prefix`, a failing integrity check) and see `StoreRelocateError` naming that check with the target file gone
  - [ ] Test: a copy that raises `OSError` (and one stopped by `after_backup` raising) leaves no target file and an untouched source
  - [ ] Confirm `tests/test_import_boundaries.py` covers `store/relocate.py` under its `store` rule (no `config`, `operations` or `cli` import); add a case there if the scan would skip a new module
  - [ ] Success: tests pass; checks pass

- [ ] **2.3 `operations/state_move.py`: types and the store move (D2 steps 1 to 4)**
  - [ ] Define `MoveStep` (`StrEnum`: `OPENED`, `LOCKED`, `BACKED_UP`, `VERIFIED`, `PLACED`, `LEGACY_DELETED`, `DIRECTORY_MOVED`), `MoveHooks` (frozen: `after_step: Callable[[MoveStep], None]` called after each step, and `move_directory: Callable[[Path, Path], None]`; defaults are a no-op and `shutil.move`) and `MoveReport` (store moved yes or no, entries moved). `prepare_state_home(layout, *, hooks=MoveHooks())` is the crash-test and cross-filesystem seam; production passes none
  - [ ] Step 1: open the legacy store with a `mode=rw` URI (never `Store.open`; an open that fails because the file is gone means another process finished, so go to step 5), hook `OPENED`, then `BEGIN IMMEDIATE`. Re-check that the legacy path still exists after the lock (a lock on a file another process already deleted succeeds): if it is gone, close and go to step 5. Hook `LOCKED`
  - [ ] Steps 2 to 4: delete a stale `amoeba.sqlite3.moving` when the new store is absent; `copy_store` into `.moving` (`after_backup` calls the `BACKED_UP` hook); verify; rename to `amoeba.sqlite3`, commit, close, delete the legacy store with its `-wal` and `-shm`
  - [ ] It does nothing when `layout.legacy_home` is `None` or holds none of `amoeba.sqlite3`, `answering/`, `logs/`. A busy legacy lock is logged with `logger.exception` and raises `StoreBusyError` with nothing written
  - [ ] Success: pyright strict clean

- [ ] **2.4 Store move tests**
  - [ ] Test: a legacy store moves with every row and `resume_log`; the legacy store file is gone and the new one opens
  - [ ] Test: a crash (the test's `after_step` raises a test-local exception) after each of `OPENED`, `LOCKED`, `BACKED_UP`, `VERIFIED`, `PLACED` and `LEGACY_DELETED`, each followed by a clean rerun with default hooks that ends complete and never creates a legacy store
  - [ ] Test: the legacy file deleted by the `OPENED` hook (as a racing process would) is treated as already moved: nothing is created at the legacy path and the call continues to step 5
  - [ ] Test: a copy error leaves the legacy store untouched and the next call moves it
  - [ ] Test: a held legacy write lock (a second connection in `BEGIN IMMEDIATE`) delays the move until released, and raises `StoreBusyError` with nothing written when held past a short busy timeout
  - [ ] Test with two real processes released together by a gate file: both call the move on one legacy home; exactly one move happens and both end with the complete new store
  - [ ] Success: tests pass; checks pass

- [ ] **2.5 State move: directories (step 5), both stores, and the report**
  - [ ] Step 5: move each entry of legacy `answering/`, `logs/answering/`, `logs/resume/` into the same place under the state home: first to `.<name>.moving` with `hooks.move_directory`, then rename (a stale `.<name>.moving` is removed and that entry moved again; `DIRECTORY_MOVED` hook after each entry). Remove emptied legacy directories. With only directories left (no legacy store file), start here. `config.yaml` is never touched
  - [ ] Both stores exist: under the step 1 lock compare as in step 3. Equal: delete the legacy store and continue with step 5. Different: move the legacy store with its `-wal` and `-shm` into the state home as `amoeba.sqlite3.legacy-<UTC stamp>`, never open it again, write one stderr line naming the file and both stores' row counts and `MAX(answers.seq)`, and continue with step 5
  - [ ] Write `MoveReport` to stderr as one line only when something moved
  - [ ] Success: pyright strict clean

- [ ] **2.6 Directory and both-stores tests**
  - [ ] Test: a fresh move leaves only `config.yaml` in the legacy home, every entry is under the state home, and a second call prints no move line
  - [ ] Test: a crash after the first `DIRECTORY_MOVED` and a stale `.<name>.moving`, each followed by a clean rerun that ends complete; a crash with the legacy store already deleted creates no legacy store
  - [ ] Test: the cross-filesystem path, with a `move_directory` that copies then deletes
  - [ ] Test: identical double stores delete the legacy one; differing double stores keep the state-home store, set the legacy one aside with the stderr line, and leave `config.yaml` alone
  - [ ] Success: tests pass; checks pass

- [ ] **2.7 `open_state_store` and every entry point**
  - [ ] `open_state_store(layout)` calls `prepare_state_home` then `Store.open(layout.store_path)`. It is the only caller of `Store.open` under `src/amoeba`. In `cli/main.py` replace every `Store.open(store_path())` with it; `StoreRelocateError` is exit 3 through the existing `StoreError` handler
  - [ ] Add an AST test that no module under `src/amoeba` except `state_move.py` calls `Store.open`
  - [ ] Add a CLI test that runs every subcommand against a legacy home (throwaway `HOME`, `AMOEBA_HOME` unset) and checks the move happened before the command's own work
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: split homes and move legacy state on first use`

## 3. Migration `003` (D3)

- [ ] **3.1 Migration runner: foreign keys around a migration**
  - [ ] In `migrate`, set `PRAGMA foreign_keys = OFF` before `BEGIN IMMEDIATE` (it does nothing inside a transaction); before commit run `PRAGMA foreign_key_check` and raise `StoreCorruptError` (rolling back) on any row; turn foreign keys back on after commit or rollback. Put the pragma SQL in `store/sql.py` with the other constants
  - [ ] Success: pyright strict clean

- [ ] **3.2 Runner tests**
  - [ ] Test: a migration that leaves a dangling foreign key rolls back, raises `StoreCorruptError`, and the store keeps its old version; foreign keys are on again afterward
  - [ ] Test: migrations `001` and `002` still apply to a new store unchanged
  - [ ] Success: tests pass; checks pass

- [ ] **3.3 `003_question_lifecycle.sql` and vocabulary**
  - [ ] Add `QuestionState.CLOSED` and `ClosedReason` (`dismissed`, `run_moved_on`, `run_gone`) to `store/vocabulary.py`
  - [ ] Write `store/schema/003_question_lifecycle.sql` by SQLite's documented rebuild: create `questions_new` with the widened `state` `CHECK`, the existing columns and constraints (keeping `PRIMARY KEY (run_id, paused_at)`, the key `answers` references), and nullable `closed_reason` (`CHECK` in `ClosedReason`), `closed_detail`, `closed_at`; copy rows; drop `questions`; rename. `001` and `002` define no indexes, so none is recreated (check the current files before writing; if one exists, create it once under its old name after the rename). Header comment says why this is the one exception to `ADD COLUMN`. Add `answers.retracted_at`, `answers.retract_reason`, `answers.resume_started_at` and `members.removed_at`
  - [ ] `EXPECTED_SCHEMA_VERSION = 3`. Add the new columns to `QuestionRecord`, `AnswerRecord` and `Member` in `store/models.py`, to the column constants in `store/sql.py`, and to the row mappers
  - [ ] Success: a new store opens at version 3; existing tests pass

- [ ] **3.4 Migration tests**
  - [ ] Test: a version-2 store seeded with every question state, a PM answer, an answerer answer with each `resume_outcome`, members and pairs migrates to 3 with every row and value preserved and `foreign_key_check` clean; the new columns are null
  - [ ] Test: the vocabulary pin covers `ClosedReason` and the widened `QuestionState`; 224's schema pin test lists each new column
  - [ ] Test: inserting a `closed` row with an unknown `closed_reason` fails the `CHECK`
  - [ ] Success: tests pass; checks pass

## 4. Answer limit and precedent (D7, D6 store side)

- [ ] **4.1 Limit counted since the PM's last answer**
  - [ ] Change `COUNT_AUTOMATIC_ANSWERS` so `automatic_answer_count` counts `answerer` answers of the run with `seq` greater than the run's newest `pm` answer `seq`, or all when there is none. A retracted PM answer still counts as the last one
  - [ ] Success: both callers (`pause_claim.start_new_claim`, `answers.settle_answered`) are unchanged

- [ ] **4.2 Limit tests**
  - [ ] Test in `tests/store/test_answers.py`: no PM answer counts all; a PM answer resets to zero; answers after it count; a retracted PM answer (set `retracted_at` directly) still resets; another run's answers never count
  - [ ] Test through `handle_pause` (the rig): a run at `answer_limit` automatic answers gets another automatic answer after a PM answer
  - [ ] Success: tests pass; checks pass

- [ ] **4.3 Precedent leaves out retracted and closed**
  - [ ] In `SELECT_PM_PRECEDENT`: take the newest PM answer per question as now, then drop the question when that answer has `retracted_at` set or the question's `state` is `closed`. An older PM answer is not brought back
  - [ ] Success: pyright strict clean

- [ ] **4.4 Precedent tests**
  - [ ] Test: a retracted newest answer gives no precedent and the older PM answer is not revived; a closed question gives none; a new PM answer after a retraction is the precedent; `answerer` answers are never precedent
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: add migration 003, limit reset and precedent changes`

## 5. Store writes for the lifecycle (D4, D5, D6)

- [ ] **5.1 Close, dismiss, retract and resume-start writes**
  - [ ] In `store/questions.py`: `close_question(transaction, key, reason, detail, expected_state, expected_updated_at, now) -> bool` (compare-and-set on `state` and `updated_at`; row count tells the caller it won) and `dismiss_question` (compare-and-set from `claimed` or `waiting_on_pm`, reason `dismissed`; from `answered` with an unresumed latest answer it also marks that answer `not_delivered` with detail `dismissed`, in the same transaction)
  - [ ] Reads: `open_rows_of_run(transaction, run_id)` and `sweep_candidates(transaction, member_ids)`, each returning the open rows: `claimed` or `waiting_on_pm`, plus `answered` whose latest answer has `resume_outcome` null or `refused`. Add `member_open_questions(transaction, member_id)` (the same open rows, for D8)
  - [ ] In `store/answers.py`: `retract_answer(transaction, seq, reason, now) -> bool` (sets `retracted_at` and `retract_reason` once); `mark_resume_started(transaction, answer_seq, now) -> bool` (compare-and-set on `resume_outcome` null or `refused`; False when the outcome is already final); `mark_not_delivered(transaction, answer_seq, detail, now) -> bool`, a compare-and-set on `resume_outcome` null or `refused`
  - [ ] `answer`'s `add_pm_answer` sets `answered` from `closed` too; the `closed_*` columns stay as history. Re-export the new names from `store/questions.py`'s `__all__` as the existing ones are
  - [ ] Success: pyright strict clean

- [ ] **5.2 Store write tests**
  - [ ] Test: `close_question` closes a matching row and returns True; a changed `updated_at` or `state` returns False and writes nothing; two racing closers, one wins
  - [ ] Test with a second connection (as 2.4 does for the lock): `close_question`, `dismiss_question` and `add_pm_answer` each compare-and-set against one `waiting_on_pm` row; the first write wins, the others return False or leave the state unchanged, and the row stays consistent. Plain `pytest` runs it, so CI gates it
  - [ ] Test: `dismiss_question` works from `claimed`, `waiting_on_pm` and `answered` with an unresumed (null or `refused`) answer, which becomes `not_delivered`; it refuses `answered` with a `resumed` or `not_delivered` answer, and `closed`
  - [ ] Test: the open-row reads include each open state and exclude `closed` and settled answers; `member_open_questions` includes `answered` with an unresumed latest answer and excludes a delivered one
  - [ ] Test: `retract_answer` sets once and returns False on repeat; `mark_not_delivered` never overwrites `resumed`; `mark_resume_started` returns False after `resumed` or `not_delivered`; `add_pm_answer` on a `closed` question sets `answered` and keeps `closed_reason`
  - [ ] Success: tests pass; checks pass

## 6. `dismiss`, `retract` and the `closed` class (D5, D6, D12)

- [ ] **6.1 `PauseClass.CLOSED` and `SkipReason.CLOSED`**
  - [ ] Add both; `classify_pause` returns `CLOSED` for a `closed` row; `handle_pause` and `pause_existing` skip it as `closed`. `status_runs` shows the class as stopped with `closed_reason` and `closed_detail` in `detail`, saying the run is still paused in Squadron, that Amoeba does not resume or end it, and that `sq run --resume` continues it, and `next` null
  - [ ] Success: pyright strict clean

- [ ] **6.2 Class tests**
  - [ ] Add the class to 224's cross-check table test (`tests/operations/test_status_matches_handle_pause.py`) and to `tests/operations/test_pause_class.py`
  - [ ] Test: `handle_pause` on a closed pause returns `skipped / closed` and writes nothing; `status` shows class `closed` and no `next`
  - [ ] Success: tests pass; checks pass

- [ ] **6.3 `operations/dismiss.py`**
  - [ ] `DismissRequest(run_id, paused_at?, reason)` validated inside the operation (222 D7); `dismiss(store, document) -> DismissResult` per D5: find by key or the run's latest `claimed_at` row (`rejected / no_such_question`); reason stripped and non-empty (`rejected / malformed`); `claimed` or `waiting_on_pm` closes with `dismissed`; already `closed` is `unchanged` with the existing reason; `answered` with an unresumed latest answer closes the question and marks the answer `not_delivered` (outcome `dismissed`); `answered` with a delivered answer is `rejected / not_open`: the detail says a `resumed` answer was delivered and that `retract` stops it being precedent, or that a `not_delivered` answer was recorded but never delivered. No subprocess, no resume
  - [ ] Outcome and problem-code `StrEnum`s defined once, in the style of `answer.py`
  - [ ] Success: pyright strict clean

- [ ] **6.4 `dismiss` tests**
  - [ ] Test: closes `claimed`, `waiting_on_pm` and a `waiting_on_pm / answer_limit_reached` row; repeat is `unchanged`; `answered` with a null or `refused` resume is `dismissed` and its answer `not_delivered`; `answered` with a `resumed` answer is `not_open`; unknown run is `no_such_question`; blank reason and a non-mapping document are `malformed`
  - [ ] Test: an in-flight answering run settling after the dismissal writes nothing (223's `WHERE state = 'claimed'`)
  - [ ] Test: the reason is stored and returned as data (a reason with shell metacharacters round-trips)
  - [ ] Success: tests pass; checks pass

- [ ] **6.5 `operations/retract.py`**
  - [ ] `RetractRequest(answer_seq, reason)`; `retract(store, document) -> RetractResult` per D6: `no_such_answer`, `not_a_pm_answer` (an `answerer` answer), `malformed` (blank reason, non-integer seq); outcome `retracted`, or `unchanged` if already retracted
  - [ ] `decisions` records gain `retracted_at` and `retract_reason` (`decisions_models.py`, `store/decisions.py`); retracted answers stay listed; closures are not listed; the marker and `read_through` are unchanged
  - [ ] Success: pyright strict clean

- [ ] **6.6 `retract` tests**
  - [ ] Test: retracts a PM answer and it leaves `pm_precedent`; repeat is `unchanged`; `answerer` answer rejected; unknown seq rejected; blank reason rejected
  - [ ] Test: a non-integer seq is `malformed`; closed questions are not listed by `decisions`, and the marker and `read_through` are unchanged after a retraction
  - [ ] Test: a new PM answer to the same question restores precedent; `decisions` shows `retracted_at` and `retract_reason`
  - [ ] Success: tests pass; checks pass

- [ ] **6.7 CLI commands**
  - [ ] Add `dismiss <run_id> [--paused-at TS] --reason TEXT` and `retract <answer_seq> --reason TEXT` to `cli/main.py` (command-name constants; `answer_seq` is a positional `int`). Exit 0 for `dismissed`, `retracted`, `unchanged`; 1 for `rejected`; 2 usage; 3 errors, as 222 D9
  - [ ] Success: `amoeba dismiss --help` and `amoeba retract --help` print

- [ ] **6.8 CLI tests**
  - [ ] Test in `tests/cli/`: both commands print their result JSON; exit codes 0, 1 and 2; a store error is 3
  - [ ] Create `tests/operations/test_every_state_exits.py`, the one test that walks each state of the design's Integration Requirements to its exit with no file edits. Cases built so far: `claimed` (settle, dismiss), `waiting_on_pm` (answer, dismiss), `closed` (terminal; `answer` reopens it), a retracted answer (terminal; a new answer replaces it), `answered` and settled (terminal). Section 7 adds the sweep exits to this file
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: add question lifecycle store writes, dismiss and retract`

## 7. The automatic close sweep (D4, D12)

- [ ] **7.1 Resume start time and `resume_bound_seconds`**
  - [ ] In `operations/resume.py` define `resume_bound_seconds(config)` once (the poll timeout is the constant, since `deps` holds only the already-bound `poll_run`): `resume_wait_seconds + RESUME_POLL_INTERVAL_SECONDS + 2 × RUN_POLL_TIMEOUT_SECONDS + 2 × TERMINATE_GRACE_SECONDS + BUSY_TIMEOUT_SECONDS`. `resume` calls `mark_resume_started` (own short transaction) just before every spawn, including retries. When it returns False the outcome is already final, so `resume` spawns nothing and returns `not_delivered` with a detail saying so
  - [ ] Success: pyright strict clean

- [ ] **7.2 Resume tests**
  - [ ] Test: `resume_started_at` is set before the spawn on a first resume and on a refused retry; `resume_bound_seconds` equals the sum of its named parts for a given config; a resume whose answer was already made `not_delivered` spawns nothing and reports `not_delivered`
  - [ ] Success: tests pass; checks pass

- [ ] **7.3 `operations/question_sweep.py`: `sweep_run`**
  - [ ] `sweep_run(store, config, run_id, polled, now)` per D4: read `open_rows_of_run`; for rows at any `paused_at` other than the run's current pause (or all, if the run is not paused) apply the table: `waiting_on_pm` closes as `run_moved_on` or `run_gone` (`not_found` poll) with the run's state as detail; `claimed` older than `answering_wait_seconds` closes the same way and a young claim is left; `answered` unresumed whose newest of `recorded_at`, `resume_started_at`, `resume_at` is older than `resume_bound_seconds` gets `not_delivered`. One short write transaction of compare-and-sets. Returns what it closed
  - [ ] A `StoreBusyError` on the sweep write is caught for the sweep only, with a comment saying why (a lost lock must not hide the PM's waiting list), and returned as a `sweep_problem` string. Other `StoreError`s propagate
  - [ ] Success: pyright strict clean

- [ ] **7.4 `sweep_run` tests**
  - [ ] Test, one per table row: `waiting_on_pm` at an older pause closes `run_moved_on` with detail; run `not_found` closes `run_gone`; old claim closes, young claim stays; unresumed answer past the bound becomes `not_delivered`, inside the bound (including a fresh `resume_started_at`) stays
  - [ ] Test: a row at the run's current pause is never touched; a concurrent `answer` or `dismiss` between read and write wins and the sweep skips that row; a busy write returns `sweep_problem` and raises nothing
  - [ ] Success: tests pass; checks pass

- [ ] **7.5 Wire `sweep_run` into `handle_pause`**
  - [ ] `check_eligibility` currently polls inside itself. Change it to take the polled document, and have `handle_pause` poll once, call `sweep_run` right after the poll (before eligibility, and before every skip), then check eligibility. A poll failure raises as before. Update `check_eligibility`'s callers and tests
  - [ ] A sweep problem or closure goes into the call's `detail` (appended to the result detail); no change to the outcome
  - [ ] Success: existing `handle_pause` tests pass unchanged apart from the signature

- [ ] **7.6 `handle_pause` sweep tests**
  - [ ] Test: the hook at a run's later pause closes the open row at the earlier pause as `run_moved_on`, and handles the new pause as before
  - [ ] Test: a skipped call (e.g. `prompt_only`, `not_in_program`) still sweeps; an answering run's id has no rows and sweeps nothing
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: sweep older questions in handle_pause`

- [ ] **7.7 `sweep_scope` and `status` output**
  - [ ] Add `--all` to `RUNS_LIST_FLAGS` in `upstream/squadron/run_list.py` (task 0.2 confirmed `sq runs list` has it); update its module docstring and the stub `sq` and fixtures to honor it. `status` keeps dropping completed runs from its per-member run lists, so its output is unchanged
  - [ ] Add `sweep_scope(store, config, rows, listed, deps, now)`: judge open rows of members in scope from the one `--all` listing `status` already made (state or later pause in the listing means moved on; absent from the listing and with no run file in `deps.squadron_runs_dir` means `run_gone`; absent but with a file is left open, so an incomplete listing closes nothing). Add `run_file_exists(runs_dir, run_id)` to `upstream/squadron/run_file.py` for the file check; same table and compare-and-set write as `sweep_run`; no extra `sq` call
  - [ ] In `status.py` call it after placement and classification, then build the waiting list from what is still open. `StatusResult` gains `closed_now` (`[{program, member, run_id, paused_at, question, closed_reason, closed_detail}]` plus answers marked `not_delivered` with `answer_seq` and `resume_outcome`) and `sweep_problem`. `waiting_on_pm` lists only open questions with `run_state` `at_pause`; `moved_on` and `not_listed` stay only for rows a failed write left open
  - [ ] Success: pyright strict clean

- [ ] **7.8 `status` sweep tests**
  - [ ] Test: a waiting row whose run completed closes (`run_moved_on`, detail `completed`) and one whose run is absent from the listing closes `run_gone`; both appear in `closed_now` once and not in `waiting_on_pm`; a second `status` lists nothing new
  - [ ] Test: a young claim and an answer whose resume may be in flight are never closed; a failed sweep write prints everything with the pre-sweep rows and `sweep_problem`
  - [ ] Test: `list_runs` passes `--all` (assert the stub's recorded argv), and the stub omits completed runs without it
  - [ ] Test: a run absent from the listing but with a run file stays open; a `sq runs list` failure (timeout or bad output) raises as before and closes nothing; `closed_now` lists the answers marked `not_delivered` with `answer_seq` and `resume_outcome`
  - [ ] Test: `status` makes the same one `sq runs list` call as before (assert the stub's call count)
  - [ ] Update the existing 224 `status` tests whose `moved_on` or `not_listed` expectations now close; extend `tests/operations/test_every_state_exits.py` with `claimed` (sweep), `answered` unresumed (sweep, dismiss) and `waiting_on_pm` (sweep)
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: close questions whose run moved on or is gone in status`

## 8. `wrong_checkout` (D10)

- [ ] **8.1 `RunFacts.working_directory` and the check**
  - [ ] In `upstream/squadron/run_file.py`: `RunFacts.working_directory: Path | None`; `_Body` reads it as optional (absent is `None`, no error)
  - [ ] Add `SkipReason.WRONG_CHECKOUT`. In `pause_eligibility._member_checks`, after the `prompt_only` check and before the row checks, compare `realpath(directory)` to `realpath(working_directory)`; a mismatch is `Skip(WRONG_CHECKOUT, "called from <directory>; the run was started in <working_directory>")` and writes no row. When the recorded directory no longer exists, the detail says so and names Squadron's own commands (`sq run --resume`) as the way to continue or leave the run. `None` skips the check. It applies whatever the row state
  - [ ] Success: pyright strict clean

- [ ] **8.2 `wrong_checkout` tests**
  - [ ] Add a recorded schema-5 run file from the installed `sq` (0.24.24 or later, task 0.2) that has `working_directory` to `tests/fixtures/squadron/`, beside the existing one without the key; update the fixtures README
  - [ ] Test: `read_run_facts` returns the directory for the new file and `None` for the old one
  - [ ] Test: `handle_pause` from a second directory skips `wrong_checkout` naming both, writes no row, and never resumes a dead claim or unresumed answer; from the right directory, and with `None`, behaves as before; a recorded directory that does not exist skips with a detail saying so; a symlinked path to the same directory passes
  - [ ] Success: tests pass; checks pass

## 9. The calls log (D11, D12)

- [ ] **9.1 `operations/calls_log.py`**
  - [ ] `append_call(log_dir, entry, now)`, where `log_dir` is `calls_log_dir()` passed in by the CLI (the entry's own `directory` field is the call's working directory): creates `log_dir` and parents, opens `<UTC date>.jsonl` with `O_APPEND`, writes one JSON line `{at, run_id, directory, outcome, reason, detail}` or `{at, run_id, directory, error, detail}`, `detail` through `cut_to_bound` (`upstream/bounded_text.py`) so the line stays under `PIPE_BUF`. An `OSError` writes one stderr line and does not raise, with a comment saying why
  - [ ] `last_call(log_dir, run_id) -> CallEntry | None`: day files newest first, newest line for the run. It never raises: an unreadable file or a non-JSON line is skipped and returned in a `problems` list
  - [ ] Success: pyright strict clean

- [ ] **9.2 Calls log tests**
  - [ ] Test: result and error line shapes; a long `detail` is bounded; the directory is created; a read-only directory gives one stderr line and no exception; two appends interleave whole lines
  - [ ] Test: `last_call` returns the newest line for the run across day files, `None` for an unknown run, and skips a truncated line and an unreadable file with each named in `problems`
  - [ ] Success: tests pass; checks pass

- [ ] **9.3 CLI and `status` use it**
  - [ ] `_run_handle_pause` appends one line for every ending: a result, and an exit-3 error including `ConfigError` before any store opens. An `AmoebaHomeError` about the state home goes to stderr only (no path exists). The line is written after the result prints, so a log failure cannot change the exit code
  - [ ] `status` attaches `last_call` to each `unhandled` and `claim_stale` run; read problems go to a new `file_problems` list, which later carries prune problems too (11.6)
  - [ ] Success: pyright strict clean

- [ ] **9.4 Boundary tests**
  - [ ] Test in `tests/cli/test_pause_cli.py`: a skipped call, a handled call, a `ConfigError` run (bad config, fresh state home) and a store error each add one line; the exit code is unchanged by a failing log write
  - [ ] Test: `status` shows `last_call` for an `unhandled` and a `claim_stale` run, and `file_problems` for a corrupt day file
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: skip wrong-checkout pauses and log every handle_pause call`

## 10. `set_up` removal (D8)

- [ ] **10.1 Active-member predicate**
  - [ ] In `store/programs.py` define the active-member predicate (`removed_at IS NULL`) once as an SQL constant, used by every member and pair read there (`get_member`, `members_of`, `member_settings`, `pairs_of`, `get_pair`). `resolve_member` (`operations/members.py`) and the `member_of_other_program` check (`set_up_checks.check_request`) both call `get_member`, so they inherit it
  - [ ] Add `remove_member` (sets `removed_at`, deletes the member's pairs), `remove_pair`, and `get_member_any` (reads removed rows too, for `set_up` removal to tell a past member from a stranger, and for the upsert). `upsert_member` clears `removed_at`, so a removed member can be re-registered, possibly in another program
  - [ ] `store/sql.py`'s `_SELECT_DECISIONS` joins `members` for `program_id`. It must keep seeing removed members, since their answers are the record. Define that join as the one named exception to "no other module queries `members`", with a comment saying why
  - [ ] Success: pyright strict clean

- [ ] **10.2 Predicate tests**
  - [ ] Test: a removed member is absent from `members_of`, `get_member`, `resolve_member` (`NotInProgram`); the `member_of_other_program` check ignores it; its question, answer and release rows remain; its pairs are gone; `decisions` still lists its answers; re-registering clears `removed_at`
  - [ ] AST test over the SQL constants: no constant outside `store/programs.py` queries `members`, apart from the named `decisions` join (extend `tests/test_store_safety.py` or the read-side test; follow its pattern)
  - [ ] Success: tests pass; checks pass

- [ ] **10.3 `remove` request models**
  - [ ] In `set_up_models.py`: `remove` with `members` (CF names or ids) and `pairs` (`provider`, `consumer`); new problem codes `member_has_open_questions` and `not_a_member`, as `StrEnum` members beside the existing codes
  - [ ] `malformed` also covers a member under both `members` and `remove.members`, a pair under both `depends_on` and `remove.pairs`, and removing a member while naming it as a pair end
  - [ ] Success: pyright strict clean

- [ ] **10.4 Request model tests**
  - [ ] Test: a request without `remove` behaves as before; each of the three `malformed` overlaps is rejected with the path of the offending entry
  - [ ] Success: tests pass; checks pass

- [ ] **10.5 Apply `remove` in `set_up`**
  - [ ] In the resolve, check and apply code (`set_up_resolve.py`, `set_up_checks.py`, `set_up.py`): resolve removals and apply them in the one write transaction. A reference with no member row at all is `not_a_member`; an already removed member or an absent pair is no change. `member_has_open_questions` when `member_open_questions` is non-empty (detail lists the keys and says to `dismiss` or `answer`). `changes` gains `removed member <id>` and `removed pair <provider> -> <consumer>`
  - [ ] `member_has_open_questions` uses `member_open_questions`, so an `answered` question with an unresumed answer blocks removal too, and `dismiss` closes it. Removing the concept member without clearing or moving the concept stays rejected by `concept_member_not_member`
  - [ ] Keep `set_up.py` near the ~300-line target: put removal in a new module if it would exceed it
  - [ ] Success: pyright strict clean

- [ ] **10.6 `set_up` removal tests**
  - [ ] Test: removes a member (soft) and a pair; a second identical request returns `unchanged`; naming a removed member under `members` re-adds it with `rules_paths` required; re-adding in another program works
  - [ ] Test: `member_has_open_questions` lists `claimed` and `waiting_on_pm` keys, and after `dismiss` the removal applies; `not_a_member` for a stranger
  - [ ] Test: a member whose only open question is `answered` with an unresumed answer is rejected with `member_has_open_questions`, and after `dismiss` the removal applies
  - [ ] Test: removing the concept member while the concept stays is rejected with `concept_member_not_member`; `concept: null` in the same request removes the concept and the member
  - [ ] Test: a concurrent removal and `dismiss` (extend `test_set_up_concurrent.py`) never leaves a removed member with an open question undetected
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: add set_up remove for members and pairs`

## 11. Pruning and `prune_after_days` (D9)

- [ ] **11.1 The config key**
  - [ ] Add required `prune_after_days` (strict int, ≥ 1, no default in code) to `UserConfig`; add it to the config builder in `tests/user_configs.py` and every fixture config (live tests included); update `tests/config/test_user_config.py` for missing, zero, float and valid values
  - [ ] Success: tests pass; checks pass

- [ ] **11.2 `operations/prune.py`: scratch and answering and resume logs**
  - [ ] `prune(store, layout, now, after_days) -> PruneReport` (with `problems`). Settled question: `closed`, or `answered` with latest answer `resumed` or `not_delivered`. Remove `answering/<id>/` and `logs/answering/<id>.*` older than the age (mtime) when no question has that `answering_run_id` or its question is settled; remove `logs/resume/<run_id>/` files older than the age whose run has no open question, and the directory when empty. Anything tied to an open question is kept at any age. Store rows are not pruned
  - [ ] An `OSError` on one entry is caught for that entry, with a comment saying why (one locked file must not fail the call that triggered pruning), recorded in `PruneReport.problems`; the other entries still prune
  - [ ] Success: pyright strict clean

- [ ] **11.3 Scratch and log prune tests**
  - [ ] Test, with files set old by `os.utime`: settled scratch and its logs pruned; orphan scratch (no question row) pruned; open-question scratch, answering logs and resume logs kept at any age; young entries kept; an emptied `logs/resume/<run_id>/` goes
  - [ ] Test: an unremovable entry is named in `problems` and the rest still prune; `answers.resume_log` still holds the path after its file is pruned and `decisions` prints it without error
  - [ ] Success: tests pass; checks pass

- [ ] **11.4 `prune`: calls log and other logs**
  - [ ] Extend `prune`: `logs/calls/<date>.jsonl` whose date (from the file name) is older than the age; any other file under `logs/` older than the age (226's `logs/mcp/` included), then emptied directories. Same per-entry `OSError` handling
  - [ ] Success: pyright strict clean

- [ ] **11.5 Other prune tests**
  - [ ] Test: calls-log day files by their date (not mtime), unknown `logs/` files and their emptied directory are pruned when old and kept when young; a file tied to an open question is never touched; an `amoeba.sqlite3.legacy-*` file is never pruned
  - [ ] Success: tests pass; checks pass

- [ ] **11.6 Call `prune` from `handle_pause` and `status`**
  - [ ] Call it at the end of `handle_pause` (after any resume, so it never delays one) and of `status`; `status` prints `PruneReport.problems` in `file_problems`; `handle_pause` puts them in the calls-log `detail`. Pass `layout` and `config.prune_after_days` down, not the environment
  - [ ] Success: pyright strict clean

- [ ] **11.7 Wiring tests**
  - [ ] Test: `status` removes a settled and an orphan answering directory (old by mtime) and keeps an open question's; `handle_pause` prunes after a resume, not before (assert order with a recording fake); prune problems reach `file_problems`
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: prune settled scratch and logs after prune_after_days`

## 12. Contract docs and README (D13)

- [ ] **12.1 Contract docs**
  - [ ] `docs/cli-contract.md`: `dismiss`, `retract`, `set_up` `remove` (including `concept: null` under removal), the new `status` fields (`closed_now`, `last_call`, `sweep_problem`, `file_problems`), skip reasons `closed` and `wrong_checkout`, the new exit-3 `StoreRelocateError`, and the calls-log line format
  - [ ] `docs/config-contract.md`: `prune_after_days` in the key table and the example (value `30`), and the two homes
  - [ ] `docs/store-contract.md`: the migration rule says `ADD COLUMN` stays the default, names `003`'s `questions` rebuild as the one exception and why, and says a new exception needs the same justification; migration `003`; the `closed` state and reasons; which operation writes each new column; the D4/D5/D6 lifecycle table; each new column as "record" except `members.removed_at` ("membership"); `resume_log` may name a pruned file; deleting a set-aside `amoeba.sqlite3.legacy-<stamp>` file is its exit (no process reads it)
  - [ ] `docs/squadron-hook.md`: drop the wrong-checkout warning for runs from `sq` 0.24.24 on, keep it for older runs
  - [ ] `README.md` "where things live": the two homes
  - [ ] Success: docs carry frontmatter where the others do

- [ ] **12.2 Doc tests**
  - [ ] Update `tests/test_contract_docs.py` so it requires every new table and column, command, exit code, result value, skip reason and config key to appear in the docs
  - [ ] Success: tests pass; checks pass

## 13. Validation, walkthrough and the real upgrade (D2, Verification Walkthrough)

- [ ] **13.1 Full checks**
  - [ ] Run the four checks once. All pass, with 222 to 225 tests unchanged apart from the expected `status` output and limit-count changes (D12, D7)
  - [ ] Run `tests/operations/test_every_state_exits.py`; it must have a case for each state in the design's Integration Requirements list: `claimed`, `waiting_on_pm`, `answered` unresumed, `answered` settled, `closed` and a retracted answer
  - [ ] Success: checks pass; the walk test is green

- [ ] **13.2 Back up the real store**
  - [ ] `pgrep -fl "amoeba (handle_pause|answer|status|set_up|dismiss|retract)"` finds nothing. These commands write the store, and an answering or resume child is always started by one of them, so none runs without a parent matched here. If something runs, wait for it to end and recheck; do not kill it
  - [ ] `BACKUP=$(mktemp -d)`; `cp -R ~/.config/amoeba "$BACKUP/amoeba"` (nothing is running, so the store and its `-wal` file are quiet); `sqlite3 ~/.config/amoeba/amoeba.sqlite3 ".backup $BACKUP/store.sqlite3"`. Check `PRAGMA integrity_check` on `$BACKUP/store.sqlite3` prints `ok`. Write the backup path and the walkthrough step 2 counts query result (questions, answers, `MAX(seq)`) on it as a note under this task
  - [ ] Success: the note holds the path, `ok` and the three counts

- [ ] **13.3 Walkthrough steps 1 to 8**
  - [ ] Run the design's walkthrough steps 1 to 8 (throwaway `HOME` and `AMOEBA_HOME`; live `sq` for steps 4 to 7 with the fixtures under `tests/live/pause/`). Step 2 reads the real store only through the backup: use `$BACKUP/amoeba/` wherever the step names `~/.config/amoeba/`. Write nothing under the real `~/.config`
  - [ ] Record each step's result as a note under this task. A step that fails is fixed in this slice, not noted and left
  - [ ] Success: every step matches its stated expectation

- [ ] **13.4 Real upgrade (walkthrough step 9)**
  - [ ] Designation: proceed only if the PM has named `~/.config/amoeba/amoeba.sqlite3` for this upgrade in their own message. If not, write `BLOCKED: the PM has not designated ~/.config/amoeba/amoeba.sqlite3` under this task and stop
  - [ ] Recheck the 13.2 `pgrep` finds nothing, and that the live store's counts still equal 13.2's note. If they differ, repeat 13.2 first
  - [ ] Add `prune_after_days: 30` to `~/.config/amoeba/config.yaml`. Run `uv tool install --force .` from the slice branch, then `amoeba status`
  - [ ] Success: `ls -A ~/.config/amoeba` shows `config.yaml` only; `~/.local/state/amoeba/amoeba.sqlite3` exists, is at version 3, and its question, answer and `MAX(seq)` counts equal the note's; `select count(*) from answers where resume_log like '$HOME/.config/%'` prints `0`; `amoeba decisions` lists the same records as before. Report the results in the reply; a note here would be a commit of notes alone
  - [ ] Restore, only if a success check fails: `rm -f ~/.local/state/amoeba/amoeba.sqlite3*`; `cp -R "$BACKUP/amoeba/." ~/.config/amoeba/`; reinstall the pre-slice tool with `git worktree add "$BACKUP/target-tree" {target}` (the target noted under 0.1) then `uv tool install --force "$BACKUP/target-tree"`; confirm `amoeba decisions` matches the note. Then write the failing check under this task and fix its cause in the slice before retrying. The backup directory stays where it is; its path is in the note

**Commit**: `docs: document the lifecycle contracts and record slice 228 validation`
