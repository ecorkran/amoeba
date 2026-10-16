---
docType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
lld: user/slices/107-slice.judge-samples-checks-and-calibration.md
dependencies: [101, 102, 103, 104, 105, 106]
projectState: Slices 101–106 are merged (store schema 6, listing registry, inbox kinds `create_project`/`resolution`/`intent`/`verdict`/`watch_reviews`, verdicts and findings, 105's parser and `amoeba ingest review`, 106's change feed). A verdict has no invocation id, no check or progress table exists, and `parse_review_json` accepts a stdout capture that says `UNKNOWN` with a score. This slice adds migration 007, judge samples, calibration, checks, progress records, the `check` kind, and the D4 refusal.
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
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

**Section map.** 1 baseline, judge fixture, and the D4 refusal; 2 check models; 3 migration 007 and check storage; 4 judge samples in the verdict path; 5 calibration; 6 the `check` kind and its feed change; 7 ingest and listings; 8 end-to-end, docs, validation.

---

## Section 1: Baseline, Judge Fixture, and the D4 Refusal

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch from a clean baseline.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `107-slice.judge-samples-checks-and-calibration` from the target; if it exists, switch to it
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [ ] No commit needed

---

### Task 1.2: Confirm the real judge fixtures exist
**Owner**: Junior AI (the capture itself is a PM step)
**Dependencies**: Task 1.1
**Effort**: 1
**Objective**: Have the two real inputs the parser and refusal tests need (LLD Technical Requirements, Development Approach step 1).

**Steps**:
- [ ] Look in `tests/fixtures/sq_reviews/` for (a) a saved judge-template review artifact (`reviewType` starting `judge.`) and (b) a real stdout JSON capture of a judge review, both from a pipeline run on squadron 0.21.9 or later
- [ ] If either is missing, **stop and ask the PM** to capture them (a pipeline run in a throwaway copy of a repository). Do not hand-write them
- [ ] Read `tests/fixtures/README.md` and confirm it records, for each judge fixture, the command, the Squadron version, and the date. If an entry is missing, ask the PM for the values; do not infer them
- [ ] Note the artifact's stated verdict, score, model, and criteria from the file, for Task 1.3

**Success Criteria**:
- [ ] Both fixtures are present and documented in the fixtures README
- [ ] If anything was missing, the PM has been told and has answered before Task 1.3 starts

---

### Task 1.3: Test the judge artifact against 105's parser
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: The real judge artifact parses to its stated values (LLD Functional Requirements).

**Steps**:
- [ ] Add `tests/upstream/test_review_judge_fixture.py`, following the style of `test_review_artifact.py` and the helpers in `tests/review_fixtures.py`
- [ ] Parse the artifact with `parse_review_artifact`; assert review type, verdict, score, model, and criteria equal the values read in Task 1.2
- [ ] Assert `verdict_source` is absent in the parse, so the trust label for the resulting verdict is `unattested`
- [ ] Parse the stdout capture with `parse_review_json` and assert it has a real verdict (not `UNKNOWN`) and a score. This is the "a capture with a real verdict and a score parses" case

**Success Criteria**:
- [ ] New tests pass against the unmodified parser
- [ ] Commit, e.g. `test: add real judge review fixture tests`

**Files to Create**: `tests/upstream/test_review_judge_fixture.py`

---

### Task 1.4: Add the stdout-`UNKNOWN`-with-a-score refusal
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: Per LLD D4, `parse_review_json` refuses a capture that says `verdict: UNKNOWN` and carries a `score`.

**Steps**:
- [ ] Read `upstream/squadron/review_json.py` and `review_values.py`. Add the refusal in `parse_review_json`, raising `SquadronParseError`
- [ ] Message per the LLD: it names the saved review file as the source to ingest instead, and contains no Squadron version and no template name. The rule reads only the JSON's own fields
- [ ] A missing score, or a real verdict with a score, is unchanged. `parse_review_artifact` is unchanged
- [ ] Search existing tests and fixtures for an `UNKNOWN`-with-score stdout case that now fails; update only those, and say so in the commit message

**Success Criteria**:
- [ ] `ruff`, `pyright` pass; full suite passes
- [ ] Committed with Task 1.5

**Files to Modify**: `src/amoeba/upstream/squadron/review_json.py`

---

### Task 1.5: Test the refusal and its CLI exit
**Owner**: Junior AI
**Dependencies**: Task 1.4
**Effort**: 3
**Objective**: Pin D4 at the parser and at `amoeba ingest review` (LLD Functional Requirements, last bullet).

**Steps**:
- [ ] Create the edited stdout fixture: copy the real stdout capture from Task 1.2, set `verdict` to `UNKNOWN` and keep/add a `score`. Name it with an `-edited` marker like the existing `findings-not-parsed-edited` fixture, and add a README entry saying it is edited and from which capture
- [ ] In `tests/upstream/test_review_json.py` add: the edited capture raises `SquadronParseError`; the message names the saved file and contains no version string; a real-verdict capture with a score parses; `UNKNOWN` without a score still parses
- [ ] Add a case to `tests/cli/test_ingest.py`: `ingest review --stdout-json <edited>` exits 12 (`REVIEW_UNREADABLE`) and leaves `inbox/new/` empty. Use the constant, not a literal 12, where the test module already imports it

**Success Criteria**:
- [ ] New tests pass; full suite passes
- [ ] Commit, e.g. `feat(upstream): refuse stdout UNKNOWN verdict that carries a score`

**Files to Create**: the edited stdout fixture
**Files to Modify**: `tests/fixtures/README.md`, `tests/upstream/test_review_json.py`, `tests/cli/test_ingest.py`

---

## Section 2: Check Models

### Task 2.1: Add `check_models.py`
**Owner**: Junior AI
**Dependencies**: Task 1.5
**Effort**: 3
**Objective**: Define every check word list, record type, and the standing function once (LLD D5, D6, "Word lists", "Inputs").

**Steps**:
- [ ] Create `src/amoeba/store/check_models.py` in the style of `journal_models.py` and `evidence_models.py` (no SQL, no `sqlite3`, no pydantic)
- [ ] `CheckOutcome` (`passed`, `failed`, `errored`), `CheckStanding` (`passed`, `failed`, `errored`, `unattested`, `vacuous`), and `ProgressKind` (`task_progress`, `devlog`) as `StrEnum`s
- [ ] `check_standing(outcome, examined_count) -> CheckStanding`: the one function, evaluated top to bottom exactly as the LLD D5 table orders it
- [ ] Frozen dataclasses `CheckInput` and `ProgressInput` per the LLD "Inputs" (`examined_count` has no default), and `CheckRecord` (the input's fields plus `project_id`, `recorded_seq`, `recorded_at`, and a `standing` property that calls `check_standing`). No `ProgressRecord` (D6)
- [ ] The `check` payload key names as module constants, defined once, as `verdict_payload.py` does for verdicts. The payload-to-`CheckInput` function lives here and reads those keys; an unknown outcome word raises, never maps to a near match
- [ ] Use the existing `Provenance` type unchanged

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 2.2

**Files to Create**: `src/amoeba/store/check_models.py`

---

### Task 2.2: Test the standing function and payload conversion
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Pin every row of the D5 table.

**Steps**:
- [ ] Add `tests/store/test_check_models.py` with a table-driven test over `(outcome, examined_count) → standing`: `errored` with any count (including 0 and null) is `errored`; null count is `unattested` for `passed` and `failed`; count 0 is `vacuous` for `passed` and `failed`; a positive count gives `passed` or `failed`
- [ ] Test payload → `CheckInput`: a full payload converts; an unknown outcome word raises; `examined_count` of null converts to `None`; a missing `examined_count` key raises (no default)
- [ ] Test `CheckRecord.standing` agrees with `check_standing`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add check models and standing`

**Files to Create**: `tests/store/test_check_models.py`

---

### Task 2.3: Add the two `RecordSource` words
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 1
**Objective**: Per LLD D8, one source vocabulary with `command_output` and `document` added.

**Steps**:
- [ ] Add `COMMAND_OUTPUT = "command_output"` and `DOCUMENT = "document"` to `RecordSource` in `store/evidence_models.py`. Add no guard anywhere, and leave 104's verdict rules unchanged
- [ ] Extend `RecordSource`'s docstring: it labels where a record was read from, and is never used as logic
- [ ] Run the existing 104 tests unchanged; add one assertion to `tests/store/test_evidence_models.py` that the enum's members are exactly the four words

**Success Criteria**:
- [ ] 104's tests pass without edits other than the new assertion
- [ ] Commit, e.g. `feat(store): add command_output and document record sources`

**Files to Modify**: `src/amoeba/store/evidence_models.py`, `tests/store/test_evidence_models.py`

---

## Section 3: Migration 007 and Check Storage

### Task 3.1: Write migration 007 tables and `sql_checks.py`
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 3
**Objective**: Create the column and two tables (LLD "Database / Storage Schema") with every name defined once in Python.

**Steps**:
- [ ] Read `005_verdicts_and_findings.sql`, `006_change_feed_and_detection.sql`, `sql_evidence.py` for the pairing convention
- [ ] Create `src/amoeba/store/schema/007_judge_samples_checks_and_progress.sql`: `ALTER TABLE verdicts ADD COLUMN judge_invocation_id TEXT` with an index on `(project_id, judge_invocation_id)`; tables `check_results` and `progress_records` with the columns, FKs, uniqueness, and indexes the LLD lists. No CHECK constraints on vocabulary columns; no `IF NOT EXISTS`. The trigger comes in Task 6.3
- [ ] Create `src/amoeba/store/sql_checks.py` holding the table and column names, the insert and select statements for both tables, and `row → CheckRecord` mapping (raises on an unknown outcome word, like the other `mapping_*.py`). No SQL outside `sql_*.py` and the migration
- [ ] Add `COL_VERDICT_JUDGE_INVOCATION_ID` to `sql_evidence.py`; do not wire it into statements yet (Task 4.1)
- [ ] Set `EXPECTED_SCHEMA_VERSION` to 7. Update only the existing tests that pin version 6 or the table set (search `tests/` for `EXPECTED_SCHEMA_VERSION`, `schema_version`)

**Success Criteria**:
- [ ] A fresh store reaches version 7 with both tables and the new column
- [ ] Full suite passes with the updated pins
- [ ] Committed with Task 3.2

**Files to Create**: `007_judge_samples_checks_and_progress.sql`, `src/amoeba/store/sql_checks.py`
**Files to Modify**: `store/migrations.py`, `store/sql_evidence.py`, version-pinning tests

---

### Task 3.2: Test the 6 → 7 upgrade and the row mapping
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: A version-6 store upgrades intact (LLD Technical Requirements).

**Steps**:
- [ ] Add `tests/store/test_migration_007.py` modeled on `test_migration_006.py`
- [ ] Build a version-6 store holding nodes, verdicts with findings, changes, watches, and detections; migrate to 7
- [ ] Assert every pre-existing row is intact, existing verdicts read back with `judge_invocation_id` null, and `check_results` and `progress_records` exist and are empty
- [ ] Add a mapping test in the same file or `tests/store/test_mapping_checks.py`: a valid row maps to `CheckRecord`; an unknown outcome raises rather than defaulting

**Success Criteria**:
- [ ] New tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): add migration 007 tables`

**Files to Create**: `tests/store/test_migration_007.py` (and `test_mapping_checks.py` if separate)

---

### Task 3.3: Add `CheckWriter`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: One place for the check's checks and insert, shared by `record_check` and the inbox effect (LLD "Data Flow", "Errors").

**Steps**:
- [ ] Read `_verdict_writer.py` and `_block_writer.py`; create `src/amoeba/store/_check_writer.py` with `CheckWriter(StoreBase)` in the same shape
- [ ] A rejection function returns a reason string or `None`, in this order: node exists in this project; `examined_count` is non-negative when given; `upstream_version` is non-empty. Reasons name the offending value
- [ ] An insert that runs inside the caller's transaction and returns the `CheckRecord`
- [ ] A retry lookup: an existing id returns the existing record, with a WARNING (through the module logger) when the new input's content differs. First wins; nothing is written
- [ ] Do not add a method to `Store` yet

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 3.4

**Files to Create**: `src/amoeba/store/_check_writer.py`

---

### Task 3.4: Add `CheckOperations` and test it
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 4
**Objective**: `record_check`, `check`, `checks`, and write-only `record_progress` on `Store` (LLD "API Contracts", D6).

**Steps**:
- [ ] Create `src/amoeba/store/checks.py` with `CheckOperations(CheckWriter)`, add it to `Store`'s bases, and export the new names from `amoeba.store`
- [ ] `record_check(input, *, project_id)`: one transaction using `CheckWriter`; a failed check raises `NodeNotFoundError` for a missing node and `ValueError` for the others
- [ ] `check(check_id)` returns `None` for an unknown id; `checks(project_id, *, node_id=None)` is in arrival order
- [ ] `record_progress(input, *, project_id) -> None`: a bare insert in one transaction, no validation, no retry rule, no feed change. A missing node or repeated id raises from SQLite
- [ ] Add `tests/store/test_checks.py`: round trip; arrival order and the `node_id` filter; unknown id returns `None`; missing node raises `NodeNotFoundError`; negative count raises `ValueError`; empty `upstream_version` raises `ValueError`; retry returns the existing record and writes no second row; a differing retry logs a WARNING and keeps the first; `examined` and `baseline_ref` read back unchanged
- [ ] Add progress tests: `record_progress` writes a row whose `content` reads back unchanged (read through SQL with the column names from `sql_checks.py`); a repeated id raises; a missing node raises; no `changes` row is written for it

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass; the writer-guard test still passes with no new permitted scripts
- [ ] Commit, e.g. `feat(store): add check results and progress records`

**Files to Create**: `src/amoeba/store/checks.py`, `tests/store/test_checks.py`
**Files to Modify**: `store/store.py`, `store/__init__.py`

---

## Section 4: Judge Samples in the Verdict Path

### Task 4.1: Carry `judge_invocation_id` through the verdict record
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: A verdict can carry an optional invocation id from input to row and back (LLD "API Contracts", "Inputs").

**Steps**:
- [ ] Add `judge_invocation_id: str | None = None` to `VerdictInput` (and so `VerdictRecord`) in `evidence_models.py`. The file is at budget: add only the field and one docstring line
- [ ] Add the payload key constant in `verdict_payload.py` (defined once) and read/write it in the payload ↔ `VerdictInput` conversion; absent or null means `None`
- [ ] Write and read the column in the verdict insert and row mapping (`sql_evidence.py`, `mapping_evidence.py`)
- [ ] Add `judge_invocation_id: str | None` to the pydantic verdict payload model in `inbox/evidence_payloads.py` so `amoeba submit verdict --judge-invocation-id` exists from the model (the flag rule: text as typed)
- [ ] Add `judge_invocation_id=None` to `to_verdict_input` in `upstream/squadron/review.py`, passed straight through. It is not in `ParsedReview` and not in the record-id digest

**Success Criteria**:
- [ ] Existing 104/105 tests pass unchanged except pins on the verdict payload's key set or the `verdicts` columns; update only those
- [ ] Committed with Task 4.2

**Files to Modify**: `evidence_models.py`, `verdict_payload.py`, `sql_evidence.py`, `mapping_evidence.py`, `inbox/evidence_payloads.py`, `upstream/squadron/review.py`

---

### Task 4.2: Test the field round trip
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 2
**Objective**: Pin the field at every layer it crosses.

**Steps**:
- [ ] Add `tests/store/test_judge_samples.py`: `record_verdict` with an id reads back the id; without one reads back `None`
- [ ] Test the payload conversion both ways with and without the key (extend `test_verdict_to_payload.py` or `test_verdict_submission.py` where they already cover the neighbouring keys)
- [ ] Test `to_verdict_input(…, judge_invocation_id="j")` sets it, and that `review_record_id` of the same parse is identical with and without it
- [ ] Test `amoeba submit verdict` accepts `--judge-invocation-id` (extend `tests/cli/test_submit.py` in the existing style)

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): carry judge_invocation_id on verdicts`

**Files to Create**: `tests/store/test_judge_samples.py`

---

### Task 4.3: Add the invocation-consistency check (D2)
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: All samples of one invocation share a node and a review type (LLD D2, "Data Flow").

**Steps**:
- [ ] In `_verdict_writer.py`, extend `_verdict_rejection` with the check, placed **last**, after 104's checks, and run only when `judge_invocation_id` is set and the verdict id is new. Look up the invocation's earliest recorded sample through the `(project_id, judge_invocation_id)` index
- [ ] A mismatch on node or review type returns a reason that names the invocation id, both nodes or both review types, and says to use a new invocation id
- [ ] Both paths use it: `record_verdict` raises `ValueError` as it does for 104's other failures; the inbox effect returns the reason as a rejection
- [ ] A rejected sample writes nothing, so it never defines an invocation. Verdicts without an invocation id skip the check entirely

**Success Criteria**:
- [ ] `ruff`, `pyright` pass; 104's tests pass unchanged
- [ ] Committed with Task 4.4

**Files to Modify**: `src/amoeba/store/_verdict_writer.py`

---

### Task 4.4: Test the invocation-consistency check
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 3
**Objective**: Pin D2 on both paths (LLD Functional Requirements, second bullet).

**Steps**:
- [ ] In `tests/store/test_judge_samples.py`: a second sample on another node raises `ValueError`; a second sample of another review type raises; each message names the invocation id and mentions a new invocation id
- [ ] A rejected first sample leaves the invocation undefined: a correct sample afterward is recorded
- [ ] A retry of an already-recorded sample id is a no-op and is not re-checked (replay of a sample after later samples exist)
- [ ] In `tests/store/test_inbox_apply.py` (or `test_verdict_submission.py`): the same mismatches submitted through the inbox end `rejected` with the reason, and write no verdict row
- [ ] A verdict with no invocation id on a node/type where samples exist is unaffected

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): reject judge samples that mix nodes or review types`

**Files to Modify**: `tests/store/test_judge_samples.py`, `tests/store/test_inbox_apply.py`

---

### Task 4.5: Add the `verdicts` filter and the sample-aware previous round
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: Read an invocation back, and never treat its samples as each other's previous round (LLD "Data Flow", "API Contracts").

**Steps**:
- [ ] Add keyword `judge_invocation_id: str | None = None` to `verdicts()`; when set, return exactly that invocation's samples in arrival order, combinable with `node_id`
- [ ] In `_previous_round` (`store/verdicts.py`) add the one skip from the LLD: when the target is a sample, skip an earlier verdict that is a sample of the same invocation. Everything else, including 104's standing skip, is unchanged
- [ ] Keep `verdicts.py` near 300 lines; it is 203 now

**Success Criteria**:
- [ ] `ruff`, `pyright` pass; 104's `finding_changes` tests pass unchanged
- [ ] Committed with Task 4.6

**Files to Modify**: `src/amoeba/store/verdicts.py`

---

### Task 4.6: Test the filter and the previous-round skip
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 3
**Objective**: Pin the Functional Requirements on reads (LLD first and fourth bullets).

**Steps**:
- [ ] In `tests/store/test_judge_samples.py`: three samples sharing an invocation, different models and run ids, are three records; `verdicts(…, judge_invocation_id=J)` returns exactly those three in arrival order; another invocation's sample and an ordinary review verdict are not returned
- [ ] In `tests/store/test_finding_changes.py` (or a sibling): `finding_changes` on the second sample of an invocation does not name the first sample as the previous round; a sample of invocation 2 does name a sample of invocation 1 as its previous round; an ordinary review's previous round is unchanged even when samples exist between

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): read judge samples by invocation and skip them as rounds`

**Files to Modify**: `tests/store/test_judge_samples.py`, `tests/store/test_finding_changes.py`

---

## Section 5: Calibration

### Task 5.1: Add `calibration.py`
**Owner**: Junior AI
**Dependencies**: Task 4.6
**Effort**: 4
**Objective**: The descriptive, read-only report of LLD D3.

**Steps**:
- [ ] Create `src/amoeba/store/calibration.py` with a frozen `CalibrationRow` (fields exactly as the D3 table: `review_type`, `model`, `samples`, `invocations`, `pass`/`concerns`/`fail`/`unknown` counts, `provider_failures`, `score_min`, `score_mean`, `score_max`) and `CalibrationOperations` with `calibration(project_id) -> list[CalibrationRow]`
- [ ] Python field names cannot be `pass`; pick names such as `pass_count` and define the CLI/JSON column names once next to the row, and record the choice in the commit message
- [ ] Read verdict rows where `judge_invocation_id` is not null; group on the stored `(review_type, model)` as given, never substituting or dropping a row. Order by review type, then model
- [ ] Verdict counts use the stored verdict. `provider_failures` counts samples whose trust label is `provider_failure`, computed with 104's existing trust function, not a second rule. Score statistics ignore samples without a score and are `None` when none has one
- [ ] No agreement metric, no cross-sample comparison, no threshold. Issue only SELECTs. Add the mixin to `Store` and export the row type

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 5.2

**Files to Create**: `src/amoeba/store/calibration.py`
**Files to Modify**: `store/store.py`, `store/__init__.py`, `store/sql_evidence.py` (statement only, if one is needed)

---

### Task 5.2: Test calibration
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Pin the counts and the permanent constraints (LLD Functional Requirements, fifth and sixth bullets).

**Steps**:
- [ ] Add `tests/store/test_calibration.py` with samples across two review types and two models: assert one row per `(review_type, model)`, ordering, `samples`, `invocations` (distinct), per-verdict counts, `provider_failures`, and min/mean/max
- [ ] An `UNKNOWN` sample is counted under `unknown`; a sample with no score is excluded from score statistics; a group with no scored sample has `None` for all three
- [ ] Ordinary review verdicts (no invocation id) never appear
- [ ] No-write test: run `calibration` on a `Store.open_read_only` handle and assert it succeeds and the store file's contents (row counts of every table) are unchanged
- [ ] No-metrology test: scan `src/` (AST or text, in the style of `tests/upstream/test_field_names_defined_once.py`) and assert nothing references Squadron's metrology directory name or its config key. Take the two strings from the LLD and the 104 notes; if you cannot find the exact config key in the repo or LLD, ask the PM rather than guessing
- [ ] The row type has no field comparing samples with each other: assert its field names equal the D3 list exactly

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): add descriptive judge calibration report`

**Files to Create**: `tests/store/test_calibration.py`

---

## Section 6: The `check` Kind and Its Feed Change

### Task 6.1: Add the `check` payload model and kind member
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 3
**Objective**: Parts one and two of the three-part seam (LLD D7).

**Steps**:
- [ ] Read `inbox/evidence_payloads.py` and `inbox/envelope.py`; create `src/amoeba/inbox/check_payloads.py` with `CheckPayload` (pydantic, `MODEL_CONFIG` like the others) whose field names are the constants defined in `check_models.py`. `examined_count` is required and nullable; `outcome` uses `CheckOutcome`, so an unknown word fails validation; `examined` is an optional opaque mapping; `upstream_version` is required
- [ ] Add `SubmissionKind.CHECK = "check"` and the `KIND_PAYLOAD_MODELS` entry
- [ ] Do not add the effect yet; the 103 completeness test is expected to fail until Task 6.2, so do not commit between

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 6.2

**Files to Create**: `src/amoeba/inbox/check_payloads.py`
**Files to Modify**: `store/inbox_models.py`, `inbox/envelope.py`

---

### Task 6.2: Add the `check` effect and test the kind
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 4
**Objective**: Part three: the effect, inside `apply_submission`'s transaction (LLD D7).

**Steps**:
- [ ] In `store/inbox.py` add `_apply_check`, modeled on `_apply_verdict`: convert the payload through the `check_models.py` function, call `CheckWriter`'s retry lookup, rejection function, and insert; return the rejection reason on failure. The submission id is the record id. Register it in `KIND_EFFECTS`. `inbox.py` is at 308 lines: keep the effect to a few lines by delegating to `CheckWriter`
- [ ] Make `InboxOperations` depend on `CheckWriter`, not on `CheckOperations` (the `BlockWriter`/`VerdictWriter` pattern)
- [ ] Extend `tests/inbox/test_envelope.py` and `tests/store/test_inbox_models.py` where they enumerate kinds, and let 103's completeness tests cover `check`
- [ ] Add inbox tests (in `tests/store/test_inbox_apply.py` or a new `test_check_submission.py`): a valid check is applied and readable; a negative count, a missing node, and an empty `upstream_version` each end `rejected` with a reason and write no row; an unknown outcome word is quarantined at validation; a replay of the same submission is a no-op
- [ ] Add a CLI test in `tests/cli/test_submit.py`: `amoeba submit check` with the flags from `CheckPayload` (`--examined-count null` and `--examined-count 0` parse as JSON per the flag rule)

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(inbox): add check submission kind`

**Files to Modify**: `store/inbox.py`, inbox and store tests as listed

---

### Task 6.3: Add the `check_recorded` trigger and `ChangeKind` member
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 2
**Objective**: One feed change per recorded check (LLD D9).

**Steps**:
- [ ] Add `CHECK_RECORDED = "check_recorded"` to `ChangeKind` in `feed_models.py`
- [ ] Add trigger `changes_check_recorded` (AFTER INSERT ON `check_results`) to migration 007, written as 006 writes its triggers: payload from `json_object` with `name`, `outcome`, `examined_count` only; `recorded_at` copied from the row; `subject_id` the check id, `node_id` its node. No standing in the payload
- [ ] Do not add a trigger for `progress_records`, and do not touch `verdict_recorded`
- [ ] Update `feed_models` tests and any test that enumerates `ChangeKind` or `changes` triggers; expect 106's `test_feed_invariant.py` to fail until Task 6.4

**Success Criteria**:
- [ ] Migration applies cleanly on a fresh store
- [ ] Committed with Task 6.4

**Files to Modify**: `store/feed_models.py`, migration 007

---

### Task 6.4: Test the check change and extend the invariant test
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 3
**Objective**: Hold LLD Functional Requirements (one change per check, none per retry or progress record) and Technical Requirements (invariant test).

**Steps**:
- [ ] In `tests/store/test_feed_triggers.py` add: `record_check` appends exactly one `check_recorded` with the payload keys above; a retried check appends none; `record_progress` appends none; a check rejected through the inbox appends none; the change carries no `standing`
- [ ] Extend `tests/store/test_feed_invariant.py`: its scripted sequence records a check and the sequence covers the new kind; the test fails if the `changes_check_recorded` trigger is missing (prove it by running the test once against a copy of the migration without the trigger, then discard the copy)
- [ ] Check the public feed read (`changes`/`amoeba feed` path) returns the new kind without an unknown-vocabulary error

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): emit check_recorded changes by trigger`

**Files to Modify**: `tests/store/test_feed_triggers.py`, `tests/store/test_feed_invariant.py`

---

## Section 7: Ingest and Listings

### Task 7.1: Add `--judge-invocation-id` and the sample id to `ingest review`
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 3
**Objective**: Judge samples are ingested through 105's command (LLD "Retry", "CLI").

**Steps**:
- [ ] Read `cli/ingest.py` (157 lines) and `add_ingest_parser`. Add `--judge-invocation-id ID`, passed to `to_verdict_input`
- [ ] Without `--id` and with an invocation, the submission/record id is 105's digest id followed by `.` and the invocation id. Without an invocation, or with `--id`, the id is unchanged. Do not change the digest or `RECORD_ID_FORMAT_TAG`
- [ ] Build the suffix in one named helper next to the existing id logic, not inline

**Success Criteria**:
- [ ] `ruff`, `pyright` pass; 105's ingest tests pass unchanged
- [ ] Committed with Task 7.2

**Files to Modify**: `src/amoeba/cli/ingest.py`

---

### Task 7.2: Test sample ingest
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 3
**Objective**: Pin the sample-id rule with the real judge fixture (LLD Functional Requirements, third and tenth bullets).

**Steps**:
- [ ] In `tests/cli/test_ingest.py` (or `test_ingest_end_to_end_modes.py` if it already runs the store): ingest the judge artifact under invocation `j1` and assert a verdict with `judge_invocation_id == "j1"`, the file's review type, verdict, score, and model, and trust label `unattested`
- [ ] Ingest the same file under `j1` and `j2`: two samples. Ingest it twice under `j1`: one sample
- [ ] An ordinary review ingested without the flag keeps 105's id exactly; `--id` overrides the default in both cases
- [ ] If 105's ingest tests run through a harness (`tests/ingest_e2e_harness.py`), reuse it rather than building a second

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(cli): ingest judge samples under an invocation`

**Files to Modify**: ingest tests as listed

---

### Task 7.3: Add the `judge_invocation_id` column and option to `inspect verdicts`
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 2
**Objective**: Per LLD "CLI", the listing shows and filters on the field.

**Steps**:
- [ ] Read `cli/inspect_evidence.py` and the `Listing`/`ValueOption` definitions in `cli/inspect.py`. Add the column after `standing` and a `--judge-invocation-id` value option that passes through to `verdicts(…, judge_invocation_id=)`
- [ ] Update the test that pins the verdicts columns (`tests/cli/test_inspect_evidence.py`, `test_verdicts_table_has_the_pinned_columns`)
- [ ] Add a test: with samples of two invocations, the option returns only the named one; `--json` includes the field

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(cli): show and filter verdicts by judge invocation`

**Files to Modify**: `cli/inspect_evidence.py`, `tests/cli/test_inspect_evidence.py`

---

### Task 7.4: Add the `checks` and `calibration` listings
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 3
**Objective**: Two read-only listings registered through the registry (LLD "CLI", "Component Structure").

**Steps**:
- [ ] Create `src/amoeba/cli/inspect_checks.py` as a sibling of `inspect_evidence.py`, exposing the two `Listing`s; append them to `LISTINGS` from there, not inline in `inspect.py`
- [ ] `checks`: `--project`, optional `--node`; columns `recorded_seq, id, node_id, name, outcome, examined_count, standing, baseline_ref, upstream_version`, with `standing` computed through `check_standing` (the one function)
- [ ] `calibration`: `--project`; one row per `(review_type, model)` with the D3 columns under the names fixed in Task 5.1
- [ ] Both work on a read-only store and accept `--json`
- [ ] Update the pinned-registry test (`tests/inbox/test_listings.py` or wherever `LISTINGS` names are pinned) and add `inspect_checks.py` to the module list in `tests/test_import_boundaries.py` if that list exists for string-constant checks

**Success Criteria**:
- [ ] `inspect checks` and `inspect calibration` appear in `amoeba inspect --help`
- [ ] Committed with Task 7.5

**Files to Create**: `src/amoeba/cli/inspect_checks.py`
**Files to Modify**: `cli/inspect.py` (registration only), listing registry tests

---

### Task 7.5: Test the two listings
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 3
**Objective**: Pin the column sets and the key behaviors (LLD Functional Requirements, check standings).

**Steps**:
- [ ] Add `tests/cli/test_inspect_checks.py` following `test_inspect_evidence.py`: `checks` has the pinned columns; a check with count 12/passed shows `passed`, count 0/passed shows `vacuous`, count 0/failed shows `vacuous`, count null shows `unattested`, errored shows `errored`; `--node` filters; `--json` includes the same fields
- [ ] `calibration` has the pinned columns, one row per group, and an empty project gives zero rows and a clean exit
- [ ] Both run against a store while the process lock is held elsewhere (read-only open), as the other listing tests do

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(cli): add checks and calibration listings`

**Files to Create**: `tests/cli/test_inspect_checks.py`

---

## Section 8: End-to-End, Docs, Validation

### Task 8.1: End-to-end test through the real CLI
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 4
**Objective**: LLD Integration Requirements, first bullet.

**Steps**:
- [ ] Read `tests/cli/test_evidence_end_to_end.py` and `tests/ingest_e2e_harness.py`; add `tests/cli/test_judge_end_to_end.py` using the same subprocess harness. Seed the node the way those tests do
- [ ] Flow: create a project, seed a node, ingest the judge artifact under `j1`, submit two more samples and a check with count 0 through `amoeba submit`, `kill -9` the process, `start` again
- [ ] Assert via read-only inspection: three samples under `j1`, a calibration row with the expected counts, the check `vacuous`, nothing applied twice, and `amoeba feed` shows exactly one `verdict_recorded` per sample and one `check_recorded`
- [ ] Add one wrong-review-type sample submission and assert `inspect submissions` shows it `rejected` with a reason naming the invocation
- [ ] Add a stdout-refusal step: `ingest review --stdout-json` with the edited fixture exits 12 and leaves `inbox/new/` empty

**Success Criteria**:
- [ ] The test passes and does not use the production store directory
- [ ] Commit, e.g. `test: add judge samples and checks end-to-end`

**Files to Create**: `tests/cli/test_judge_end_to_end.py`

---

### Task 8.2: Update the contract docs
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 3
**Objective**: LLD Technical Requirements, last bullet: 140 can design without reading code.

**Steps**:
- [ ] Every doc keeps its existing YAML frontmatter conventions; update `dateUpdated`
- [ ] `docs/evidence-contract.md`: add sections on judge samples (the three names from D1, D2 and its new-invocation remedy, the previous-round skip, sample ids and retry), calibration (D3, what it does not do, and that it **must not be consumed as agreement evidence**, citing issues #4 and #6), checks (D5 standing table; `vacuous` is not `passed`), progress records (D6, write-only, citing issue #5), and the D4 refusal as a stated exception to "unknown is a value". State that judge samples are `unattested` because Squadron omits `verdictSource`, so 140 does not read it as untrustworthy
- [ ] `docs/inbox-contract.md`: the `check` kind and its payload. `docs/feed-contract.md`: the `check_recorded` change kind and its payload. `docs/store-contract.md`: `record_check`, `check`, `checks`, `record_progress`, `calibration`, and the new `verdicts` filter
- [ ] Add a `CHANGELOG.md` entry covering the changes to earlier contracts listed in the LLD "Consumes from Other Slices" (104, 105, 106, 103, 102)

**Success Criteria**:
- [ ] Every name and flag in the docs matches the code (grep each)
- [ ] Commit, e.g. `docs: document judge samples, calibration, and checks`

**Files to Modify**: the four docs under `docs/`, `CHANGELOG.md`

---

### Task 8.3: Full validation and walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 3
**Objective**: Hold LLD Technical Requirements and the Verification Walkthrough.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; fix and re-run only what failed
- [ ] Check no new source file exceeds ~300 lines (`wc -l` on the files this slice created or edited) and that `tests/test_writer_guard.py` shows no new permitted scripts
- [ ] Run the LLD Verification Walkthrough steps 1–7 in bash against a throwaway `AMOEBA_STORE_DIR` with the real judge fixture. Where its `<judge fixture>` and `<edited judge stdout>` placeholders appear, use the filenames from Tasks 1.2 and 1.5. Compare each result with the walkthrough's expected output
- [ ] Update the LLD walkthrough with the real output and fixture names (its header says it is refined when Phase 6 completes). Edit the walkthrough section only
- [ ] Close GitHub issue #2 with a pointer to D4 **only if the PM has instructed it**; otherwise list it as pending for the PM

**Success Criteria**:
- [ ] Suite, `ruff`, `pyright` clean; every walkthrough step matches
- [ ] Commit, e.g. `docs: record 107 walkthrough output`
- [ ] The slice branch holds all commits; nothing is merged (Phase 7 follows the code review)

**Files to Modify**: `project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md` (walkthrough only)
