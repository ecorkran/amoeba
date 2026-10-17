---
docType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
lld: user/slices/107-slice.judge-samples-checks-and-calibration.md
dependencies: [101, 102, 103, 104, 105, 106]
projectState: Slices 101–106 are merged (store schema 6, listing registry, inbox kinds `create_project`/`resolution`/`intent`/`verdict`/`watch_reviews`, verdicts and findings, 105's parser and `amoeba ingest review`, 106's change feed). A verdict has no invocation id, no check or progress table exists, and `parse_review_json` accepts a stdout capture that says `UNKNOWN` with a score. This slice adds migration 007, judge samples, calibration, checks, progress records, the `check` kind, and the D4 refusal.
dateCreated: 20261015
dateUpdated: 20261016
status: complete
---

## Context Summary

- Working on the **judge-samples-checks-and-calibration** slice (107), the seventh slice of initiative 100.
- **Current state:** `Store` is built from mixins (`store/store.py`); SQL lives in `sql_*.py`, row mapping in `mapping_*.py`, word lists in `*_models.py`. `EXPECTED_SCHEMA_VERSION` is 6. A verdict's payload keys are defined once in `store/verdict_payload.py`; its pydantic model is in `inbox/evidence_payloads.py`. An inbox kind is a `SubmissionKind` member (`store/inbox_models.py`), a payload model in `KIND_PAYLOAD_MODELS` (`inbox/envelope.py`), and an effect in `KIND_EFFECTS` (`store/inbox.py`). `VerdictWriter` is in `store/_verdict_writer.py`, `VerdictOperations` (with `_previous_round`) in `store/verdicts.py`. Listings are registered in `LISTINGS` (`cli/inspect.py`), with siblings `inspect_evidence.py` and `inspect_feed.py`. 106's `tests/store/test_feed_invariant.py` ties triggers to `ChangeKind`.
- **Dependencies:** 101–106 through their documented contracts.
- **What this slice delivers:** judge samples (a verdict with `judge_invocation_id`), the descriptive calibration report, check results with a derived standing, write-only progress records, the `check` inbox kind, and the D4 refusal (GitHub issue #2). See the LLD "Technical Scope".
- **Next planned slice:** 108 (Context Forge event seam), which adds migration 008.

**Branch:** all implementation happens on `107-slice.judge-samples-checks-and-calibration`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges; merging follows the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/107-slice.judge-samples-checks-and-calibration.md` at the named section (D1–D9, "API Contracts", "Database / Storage Schema"). Exact fields, word lists, standing table, and rejection rules are settled there. Keep every new source file near 300 lines; `evidence_models.py`, `mapping_evidence.py`, and `cli/inspect.py` are at budget, so new concerns go in the new modules the LLD names.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own.

**Migration 007 grows in place.** It is unreleased until this slice merges, so Tasks 3.1 and 6.3 add to the one file. Never create an 008.

**Task-level additions to the LLD** (named by no LLD table): none beyond the LLD's own names. Anything a task needs that the LLD does not settle is a question for the PM, not a guess.

**Section map.** This file: 1–4. File 2: 5–8. In full: 1 baseline and the D4 refusal; 2 check models; 3 migration 007 and check storage; 4 judge samples in the verdict path; 5 calibration; 6 the `check` kind and its feed change; 7 ingest, the real judge fixture test, and listings; 8 end-to-end, docs, validation.

---

## Section 1: Baseline and the D4 Refusal

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch from a clean baseline.

**Steps**:
- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Create `107-slice.judge-samples-checks-and-calibration` from the target; if it exists, switch to it
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM
- [x] Check `tests/fixtures/sq_reviews/` for a saved judge-template review artifact (`reviewType` starting `judge.`, squadron 0.21.9 or later). If none, ask the PM now to capture one (a pipeline run in a throwaway copy of a repository), so it exists by Task 7.2. Work continues meanwhile (checked, none found, PM asked)

**Success Criteria**:
- [x] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [x] No commit needed

---

### Task 1.2: Add the stdout-`UNKNOWN`-with-a-score refusal
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: Per LLD D4, `parse_review_json` refuses a capture that says `verdict: UNKNOWN` and carries a `score`.

**Steps**:
- [x] Read `upstream/squadron/review_json.py` and `review_values.py`. Add the refusal in `parse_review_json`, raising `SquadronParseError`
- [x] Message per the LLD: it names the saved review file as the source to ingest instead, and contains no Squadron version and no template name. The rule reads only the JSON's own fields
- [x] A missing score, or a real verdict with a score, is unchanged. `parse_review_artifact` is unchanged
- [x] Search existing tests and fixtures for an `UNKNOWN`-with-score stdout case that now fails; update only those, and say so in the commit message

**Success Criteria**:
- [x] `ruff`, `pyright` pass; full suite passes
- [x] Committed with Task 1.3

**Files to Modify**: `src/amoeba/upstream/squadron/review_json.py`

---

### Task 1.3: Test the refusal and its CLI exit
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: Pin D4 at the parser and at `amoeba ingest review` (LLD Functional Requirements, last bullet). The rule is not judge-aware (D4), so an existing real stdout capture serves; no new capture is needed here.

**Steps**:
- [x] Create the edited stdout fixture: copy `tests/fixtures/sq_reviews/105-review.slice.squadron-review-parser-and-ingest.20261015T041112.stdout.json`, set `verdict` to `UNKNOWN` and keep/add a `score`. Name it with an `-edited` marker like the existing `findings-not-parsed-edited` fixture, and add a README entry saying it is edited and from which capture
- [x] In `tests/upstream/test_review_json.py` add: the edited capture raises `SquadronParseError`; the message names the saved file and contains no version string; the unedited capture (real verdict, with a score if it has one) parses; `UNKNOWN` without a score still parses
- [x] Add a case to `tests/cli/test_ingest.py`: `ingest review --stdout-json <edited>` exits 12 (`REVIEW_UNREADABLE`) and leaves `inbox/new/` empty. Use the constant, not a literal 12, where the test module already imports it

**Success Criteria**:
- [x] New tests pass; full suite passes
- [x] Commit, e.g. `feat(upstream): refuse stdout UNKNOWN verdict that carries a score`

**Files to Create**: the edited stdout fixture
**Files to Modify**: `tests/fixtures/README.md`, `tests/upstream/test_review_json.py`, `tests/cli/test_ingest.py`

---

## Section 2: Check Models

### Task 2.1: Add `check_models.py`
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 3
**Objective**: Define every check word list, record type, and the standing function once (LLD D5, D6, "Word lists", "Inputs").

**Steps**:
- [x] Create `src/amoeba/store/check_models.py` in the style of `journal_models.py` and `evidence_models.py` (no SQL, no `sqlite3`, no pydantic)
- [x] `CheckOutcome` (`passed`, `failed`, `errored`), `CheckStanding` (`passed`, `failed`, `errored`, `unattested`, `vacuous`), and `ProgressKind` (`task_progress`, `devlog`) as `StrEnum`s
- [x] `check_standing(outcome, examined_count) -> CheckStanding`: the one function, evaluated top to bottom exactly as the LLD D5 table orders it
- [x] Frozen dataclasses `CheckInput` and `ProgressInput` per the LLD "Inputs" (`examined_count` has no default), and `CheckRecord` (the input's fields plus `project_id`, `recorded_seq`, `recorded_at`, and a `standing` property that calls `check_standing`). No `ProgressRecord` (D6)
- [x] The `check` payload key names as module constants, defined once, as `verdict_payload.py` does for verdicts. The payload-to-`CheckInput` function lives here and reads those keys; an unknown outcome word raises, never maps to a near match
- [x] Use the existing `Provenance` type unchanged

**Success Criteria**:
- [x] `ruff`, `pyright` pass
- [x] Committed with Task 2.2

**Files to Create**: `src/amoeba/store/check_models.py`

---

### Task 2.2: Test the standing function and payload conversion
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Pin every row of the D5 table.

**Steps**:
- [x] Add `tests/store/test_check_models.py` with a table-driven test over `(outcome, examined_count) → standing`: `errored` with any count (including 0 and null) is `errored`; null count is `unattested` for `passed` and `failed`; count 0 is `vacuous` for `passed` and `failed`; a positive count gives `passed` or `failed`
- [x] Test payload → `CheckInput`: a full payload converts; an unknown outcome word raises; `examined_count` of null converts to `None`; a missing `examined_count` key raises (no default)
- [x] Test `CheckRecord.standing` agrees with `check_standing`

**Success Criteria**:
- [x] Tests pass
- [x] Commit, e.g. `feat(store): add check models and standing`

**Files to Create**: `tests/store/test_check_models.py`

---

### Task 2.3: Add the two `RecordSource` words
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 1
**Objective**: Per LLD D8, one source vocabulary with `command_output` and `document` added.

**Steps**:
- [x] Add `COMMAND_OUTPUT = "command_output"` and `DOCUMENT = "document"` to `RecordSource` in `store/evidence_models.py`. Add no guard anywhere, and leave 104's verdict rules unchanged
- [x] Extend `RecordSource`'s docstring: it labels where a record was read from, and is never used as logic
- [x] Run the existing 104 tests unchanged; add one assertion to `tests/store/test_evidence_models.py` that the enum's members are exactly the four words

**Success Criteria**:
- [x] 104's tests pass without edits other than the new assertion
- [x] Commit, e.g. `feat(store): add command_output and document record sources`

**Note**: Committed in 223c2e9, before 2.1/2.2 (the tests need the new RecordSource words). The existing parametrized member test in test_evidence_models.py was updated instead of adding a new assertion.

**Files to Modify**: `src/amoeba/store/evidence_models.py`, `tests/store/test_evidence_models.py`

---

## Section 3: Migration 007 and Check Storage

### Task 3.1: Write migration 007 tables and `sql_checks.py`
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 3
**Objective**: Create the column and two tables (LLD "Database / Storage Schema") with every name defined once in Python.

**Steps**:
- [x] Read `005_verdicts_and_findings.sql`, `006_change_feed_and_detection.sql`, `sql_evidence.py` for the pairing convention
- [x] Create `src/amoeba/store/schema/007_judge_samples_checks_and_progress.sql`: `ALTER TABLE verdicts ADD COLUMN judge_invocation_id TEXT` with an index on `(project_id, judge_invocation_id)`; tables `check_results` and `progress_records` with the columns, FKs, uniqueness, and indexes the LLD lists. No CHECK constraints on vocabulary columns; no `IF NOT EXISTS`. The trigger comes in Task 6.3
- [x] Create `src/amoeba/store/sql_checks.py` holding the table and column names, the insert and select statements for both tables, and `row → CheckRecord` mapping (raises on an unknown outcome word, like the other `mapping_*.py`). No SQL outside `sql_*.py` and the migration
- [x] Add `COL_VERDICT_JUDGE_INVOCATION_ID` to `sql_evidence.py`; do not wire it into statements yet (Task 4.1)
- [x] Set `EXPECTED_SCHEMA_VERSION` to 7. Update only the existing tests that pin version 6 or the table set (search `tests/` for `EXPECTED_SCHEMA_VERSION`, `schema_version`)

**Success Criteria**:
- [x] A fresh store reaches version 7 with both tables and the new column
- [x] Full suite passes with the updated pins
- [x] Committed with Task 3.2

**Note**: Migration 005 and 006 tests now stage their own version (`expected_version`) instead of pinning the latest version, so they stay valid as later migrations land.

**Files to Create**: `007_judge_samples_checks_and_progress.sql`, `src/amoeba/store/sql_checks.py`
**Files to Modify**: `store/migrations.py`, `store/sql_evidence.py`, version-pinning tests

---

### Task 3.2: Test the 6 → 7 upgrade and the row mapping
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: A version-6 store upgrades intact (LLD Technical Requirements).

**Steps**:
- [x] Add `tests/store/test_migration_007.py` modeled on `test_migration_006.py`
- [x] Build a version-6 store holding nodes, verdicts with findings, changes, watches, and detections; migrate to 7
- [x] Assert every pre-existing row is intact, existing verdicts read back with `judge_invocation_id` null, and `check_results` and `progress_records` exist and are empty
- [x] Add a mapping test in the same file or `tests/store/test_mapping_checks.py`: a valid row maps to `CheckRecord`; an unknown outcome raises rather than defaulting

**Success Criteria**:
- [x] New tests pass; full suite passes
- [x] Commit, e.g. `feat(store): add migration 007 tables`

**Note**: The row mapping tests are in `tests/store/test_migration_007.py`.

**Files to Create**: `tests/store/test_migration_007.py` (and `test_mapping_checks.py` if separate)

---

### Task 3.3: Add `CheckWriter` and `CheckOperations`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 4
**Objective**: One place for the check's checks and insert, shared by `record_check` and the inbox effect, plus the four store methods (LLD "Data Flow", "Errors", "API Contracts", D6). The two are one logical unit and are tested together in Task 3.4.

**Steps**:
- [x] Read `_verdict_writer.py` and `_block_writer.py`; create `src/amoeba/store/_check_writer.py` with `CheckWriter(StoreBase)` in the same shape
- [x] A rejection function returns a reason string or `None`, in this order: node exists in this project; `examined_count` is non-negative when given; `upstream_version` is non-empty. Reasons name the offending value
- [x] An insert that runs inside the caller's transaction and returns the `CheckRecord`
- [x] A retry lookup: an existing id returns the existing record, with a WARNING (through the module logger) when the new input's content differs. First wins; nothing is written
- [x] Create `src/amoeba/store/checks.py` with `CheckOperations(CheckWriter)`, add it to `Store`'s bases, and export the new names from `amoeba.store`
- [x] `record_check(input, *, project_id)`: one transaction using `CheckWriter`; a failed check raises `NodeNotFoundError` for a missing node and `ValueError` for the others
- [x] `check(check_id)` returns `None` for an unknown id; `checks(project_id, *, node_id=None)` is in arrival order
- [x] `record_progress(input, *, project_id) -> None`: a bare insert in one transaction, no validation, no retry rule, no feed change. A missing node or repeated id raises from SQLite

**Success Criteria**:
- [x] `ruff`, `pyright` pass; full suite passes
- [x] Committed with Task 3.4

**Files to Create**: `src/amoeba/store/_check_writer.py`, `src/amoeba/store/checks.py`
**Files to Modify**: `store/store.py`, `store/__init__.py`

---

### Task 3.4: Test the check writer and operations
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Pin the check and progress behavior in the LLD Functional Requirements.

**Steps**:
- [x] Add `tests/store/test_checks.py`: round trip; arrival order and the `node_id` filter; unknown id returns `None`; missing node raises `NodeNotFoundError`; negative count raises `ValueError`; empty `upstream_version` raises `ValueError`; retry returns the existing record and writes no second row; a differing retry logs a WARNING and keeps the first; `examined` and `baseline_ref` read back unchanged
- [x] Add progress tests: `record_progress` writes a row whose `content` reads back unchanged (read through SQL with the column names from `sql_checks.py`); a repeated id raises; a missing node raises; no `changes` row is written for it

**Success Criteria**:
- [x] Tests, `ruff`, `pyright` pass; the writer-guard test still passes with no new permitted scripts
- [x] Commit, e.g. `feat(store): add check results and progress records`

**Files to Create**: `tests/store/test_checks.py`

---

## Section 4: Judge Samples in the Verdict Path

### Task 4.1: Carry `judge_invocation_id` through the verdict record
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: A verdict can carry an optional invocation id from input to row and back (LLD "API Contracts", "Inputs").

**Steps**:
- [x] Add `judge_invocation_id: str | None = None` to `VerdictInput` (and so `VerdictRecord`) in `evidence_models.py`. The file is at budget: add only the field and one docstring line
- [x] Add the payload key constant in `verdict_payload.py` (defined once) and read/write it in the payload ↔ `VerdictInput` conversion; absent or null means `None`
- [x] Write and read the column in the verdict insert and row mapping (`sql_evidence.py`, `mapping_evidence.py`)
- [x] Add `judge_invocation_id: str | None` to the pydantic verdict payload model in `inbox/evidence_payloads.py` so `amoeba submit verdict --judge-invocation-id` exists from the model (the flag rule: text as typed)
- [x] Add `judge_invocation_id=None` to `to_verdict_input` in `upstream/squadron/review.py`, passed straight through. It is not in `ParsedReview` and not in the record-id digest

**Success Criteria**:
- [x] Existing 104/105 tests pass unchanged except pins on the verdict payload's key set or the `verdicts` columns; update only those
- [x] Committed with Task 4.2

**Note**: Added the harness helper `pre_judge_verdict_insert` in `tests/evidence_harness.py` so the migration 005/006/007 tests can stage pre-007 stores.

**Files to Modify**: `evidence_models.py`, `verdict_payload.py`, `sql_evidence.py`, `mapping_evidence.py`, `inbox/evidence_payloads.py`, `upstream/squadron/review.py`

---

### Task 4.2: Test the field round trip
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 2
**Objective**: Pin the field at every layer it crosses.

**Steps**:
- [x] Add `tests/store/test_judge_samples.py`: `record_verdict` with an id reads back the id; without one reads back `None`
- [x] Test the payload conversion both ways with and without the key (extend `test_verdict_to_payload.py` or `test_verdict_submission.py` where they already cover the neighbouring keys)
- [x] Test `to_verdict_input(…, judge_invocation_id="j")` sets it, and that `review_record_id` of the same parse is identical with and without it
- [x] Test `amoeba submit verdict` accepts `--judge-invocation-id` (extend `tests/cli/test_submit.py` in the existing style)

**Success Criteria**:
- [x] Tests pass; full suite passes
- [x] Commit, e.g. `feat(store): carry judge_invocation_id on verdicts`

**Files to Create**: `tests/store/test_judge_samples.py`

---

### Task 4.3: Add the invocation-consistency check (D2)
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: All samples of one invocation share a node and a review type (LLD D2, "Data Flow").

**Steps**:
- [x] In `_verdict_writer.py`, extend `_verdict_rejection` with the check, placed **last**, after 104's checks, and run only when `judge_invocation_id` is set and the verdict id is new. Look up the invocation's earliest recorded sample through the `(project_id, judge_invocation_id)` index
- [x] A mismatch on node or review type returns a reason that names the invocation id, both nodes or both review types, and says to use a new invocation id
- [x] Both paths use it: `record_verdict` raises `ValueError` as it does for 104's other failures; the inbox effect returns the reason as a rejection
- [x] A rejected sample writes nothing, so it never defines an invocation. Verdicts without an invocation id skip the check entirely

**Success Criteria**:
- [x] `ruff`, `pyright` pass; 104's tests pass unchanged
- [x] Committed with Task 4.4

**Files to Modify**: `src/amoeba/store/_verdict_writer.py`

---

### Task 4.4: Test the invocation-consistency check
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 3
**Objective**: Pin D2 on both paths (LLD Functional Requirements, second bullet).

**Steps**:
- [x] In `tests/store/test_judge_samples.py`: a second sample on another node raises `ValueError`; a second sample of another review type raises; each message names the invocation id and mentions a new invocation id
- [x] A rejected first sample leaves the invocation undefined: a correct sample afterward is recorded
- [x] A retry of an already-recorded sample id is a no-op and is not re-checked (replay of a sample after later samples exist)
- [x] In `tests/store/test_inbox_apply.py` (or `test_verdict_submission.py`): the same mismatches submitted through the inbox end `rejected` with the reason, and write no verdict row
- [x] A verdict with no invocation id on a node/type where samples exist is unaffected

**Success Criteria**:
- [x] Tests pass; full suite passes
- [x] Commit, e.g. `feat(store): reject judge samples that mix nodes or review types`

**Note**: The inbox D2 test is in `tests/store/test_verdict_submission.py`.

**Files to Modify**: `tests/store/test_judge_samples.py`, `tests/store/test_inbox_apply.py`

---

### Task 4.5: Add the `verdicts` filter and the sample-aware previous round
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: Read an invocation back, and never treat its samples as each other's previous round (LLD "Data Flow", "API Contracts").

**Steps**:
- [x] Add keyword `judge_invocation_id: str | None = None` to `verdicts()`; when set, return exactly that invocation's samples in arrival order, combinable with `node_id`
- [x] In `_previous_round` (`store/verdicts.py`) add the one skip from the LLD: when the target is a sample, skip an earlier verdict that is a sample of the same invocation. Everything else, including 104's standing skip, is unchanged
- [x] Keep `verdicts.py` near 300 lines; it is 203 now

**Success Criteria**:
- [x] `ruff`, `pyright` pass; 104's `finding_changes` tests pass unchanged
- [x] Committed with Task 4.6

**Files to Modify**: `src/amoeba/store/verdicts.py`

---

### Task 4.6: Test the filter and the previous-round skip
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 3
**Objective**: Pin the Functional Requirements on reads (LLD first and fourth bullets).

**Steps**:
- [x] In `tests/store/test_judge_samples.py`: three samples sharing an invocation, different models and run ids, are three records; `verdicts(…, judge_invocation_id=J)` returns exactly those three in arrival order; another invocation's sample and an ordinary review verdict are not returned
- [x] In `tests/store/test_finding_changes.py` (or a sibling): `finding_changes` on the second sample of an invocation does not name the first sample as the previous round; a sample of invocation 2 does name a sample of invocation 1 as its previous round; an ordinary review's previous round is unchanged even when samples exist between

**Success Criteria**:
- [x] Tests pass; full suite passes
- [x] Commit, e.g. `feat(store): read judge samples by invocation and skip them as rounds`

**Files to Modify**: `tests/store/test_judge_samples.py`, `tests/store/test_finding_changes.py`

---

