---
docType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
lld: user/slices/107-slice.judge-samples-checks-and-calibration.md
dependencies: [101, 102, 103, 104, 105, 106]
projectState: Slices 101–104 are merged (store schema 5, inbox, verdicts and findings). Slices 105 (parser and `amoeba ingest review`) and 106 (change feed, migration 006) are planned with reviewed tasks and may or may not be merged when this file starts. `verdicts` has no `judge_invocation_id`; there is no calibration report, no check or work-record storage. This slice adds one migration (number derived in Task 1.1), judge samples, `calibration`, checks, work records, and their listings.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **judge-samples-checks-and-calibration** slice (107), the seventh slice of initiative 100.
- **Current state:** `Store` is built from mixins (`store/store.py`); SQL lives in `sql_*.py`, row mapping in `mapping_*.py`, vocabularies and transfer objects in `*_models.py`. Verdicts are written by `VerdictWriter` (`_verdict_writer.py`: `_verdict_rejection` returns a reason, `_insert_verdict`, `_apply_verdict_submission`) and read by `VerdictOperations` (`verdicts.py`: `record_verdict`, `verdicts`, `_previous_round`). Inbox payloads are in `inbox/evidence_payloads.py`; payload key names are defined once in `store/verdict_payload.py`. `LISTINGS` in `cli/inspect.py` is the listing registry. Tests use `tests/evidence_harness.py` (`seed_node`, `verdict_input`) and `tests/test_writer_guard.py` (`PERMITTED_SCRIPTS`).
- **Dependencies:** 101–104 through their contracts. **105** supplies `to_verdict_input`, `verdict_to_payload`, `amoeba ingest review` (Section 6 needs them). **106** takes migration 006 and changes `_previous_round` to group by `source_document` (Task 4.9 builds on it).
- **What this slice delivers:** `judge_invocation_id` on verdicts end to end; the D2 same-node rule; the D3 previous-round exclusion; `calibration` and `summarize_judge_samples`; `record_check` / `check` / `checks` with derived standing; `record_work` / `work_records`; the migration; four listings; `scripts/demo_checks.py`; two judge fixtures; docs.
- **Not in this slice:** consensus, thresholds or recommendations, excluding escalated-gate samples, cross-project calibration, inbox kinds or feed events for checks and work records, fields for `task_progress` / `devlog` (LLD "Technical Scope", Excluded). The LLD requires no load test and no CI gate, so none is planned.
- **Next planned slice:** 108.

**Branch:** all implementation happens on `107-slice.judge-samples-checks-and-calibration`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/107-slice.judge-samples-checks-and-calibration.md` at the named section (D1–D6, API Contracts, Database / Storage Schema, Success Criteria). Exact fields, standing tables, and column lists are settled there. Keep every source file near 300 lines. `sql_evidence.py` (204) and `mapping_evidence.py` (293) are near the limit: new-table code goes in the new modules.

**PM ratification:** the LLD marks D2, D3, D4, and D6 as pending PM ratification. Task 1.1 confirms they are ratified before any code depends on them.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own. Commit messages follow the semantic prefixes in the project CLAUDE.md.

**Section map:** this file: 1 branch and prerequisites; 2 vocabularies and pure rules; 3 migration; 4 judge samples. **File 2 (`...-2.md`):** 5 checks and work records; 6 parser, ingest, fixtures; 7 listings; 8 proof, docs, final validation.

**Criteria owned by file 2:** LLD criteria for checks and work records (Section 5), the parser and `amoeba ingest review` id (Section 6), the four listings (Section 7), and the end-to-end, docs, and walkthrough criteria (Section 8) have no task in this file. File 2's Context Summary maps them. Do not treat the slice as complete when this file is.

---

## Section 1: Branch and Prerequisites

### Task 1.1: Create the branch, confirm prerequisites and ratification
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch with a known baseline, and know which prerequisites are merged.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `107-slice.judge-samples-checks-and-calibration` from the target; if it exists, switch to it
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once. If any fail before changes, stop and tell the PM
- [ ] Record, under a heading `## Task 1.1 Notes` appended at the end of this file (later tasks, here and in `-2.md`, read it from there): the value of `EXPECTED_SCHEMA_VERSION` and the highest file in `src/amoeba/store/schema/`; whether `src/amoeba/upstream/squadron/review.py` exists (105); whether a `source_document` column exists in `sql_evidence.py` (106); whether `verdict_to_payload` exists in `store/verdict_payload.py` (105)
- [ ] Derive the new migration number N from what you recorded: N is the highest existing migration number plus one, and `EXPECTED_SCHEMA_VERSION` rises to N. Write N in the Task 1.1 notes. If 106 is not merged, tell the PM, who coordinates 106's rebase (LLD "Dependencies"). Wherever these tasks say "migration N", use that recorded number; never copy a number from an example
- [ ] Ask the PM to confirm D2, D3, D4, and D6 are ratified. If the answer is no or unknown, stop

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, `pyright` clean
- [ ] Migration number and the 105/106 merge state are noted; PM ratification of D2–D4 and D6 is confirmed
- [ ] No commit needed

---

## Section 2: Vocabularies and Pure Rules

### Task 2.1: Extend `RecordSource` and add `check_models.py` vocabularies
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: Define the check and work-record vocabularies once (LLD D5, D6, "Component Structure").

**Steps**:
- [ ] In `evidence_models.py`, add `judge_invocation_id: str | None = None` to `VerdictRecord` only (the read model; Task 2.3's function reads it, so it must exist first). Do **not** add it to `VerdictInput` yet: until Task 4.1 wires storage, an input field would be accepted and silently dropped
- [ ] In `evidence_models.py`, add `command_output` and `document` to `RecordSource`; update that enum's docstring (describes what the caller read the record from; not restricted per record type)
- [ ] Create `src/amoeba/store/check_models.py`, no SQL, no `sqlite3`, following `evidence_models.py` style
- [ ] `CheckOutcome` (`passed`, `failed`, `errored`), `CheckStanding` (`errored`, `unattested`, `vacuous`, `passed`, `failed`), and `WorkRecordKind` (`task_progress`, `devlog`) as `StrEnum`s
- [ ] `check_standing(outcome, examined_count) -> CheckStanding`, the one definition, applying the D5 rule top to bottom
- [ ] Frozen dataclasses `CheckInput` and `WorkRecordInput` (fields per the LLD; `examined_count` has no default; reuse `Provenance` from `evidence_models.py`), and `CheckRecord` / `WorkRecordRecord` adding `project_id`, `recorded_seq`, `recorded_at`. `CheckRecord.standing` is computed from `check_standing`, not stored

**Success Criteria**:
- [ ] Module imports; `ruff` and `pyright` clean
- [ ] `check_standing` is defined in exactly one place

**Files to Create/Modify**: `src/amoeba/store/check_models.py`, `src/amoeba/store/evidence_models.py`

---

### Task 2.2: Test the vocabularies and `check_standing`
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Every standing row is produced by a record built for it (LLD Functional Requirements).

**Steps**:
- [ ] Create `tests/store/test_check_models.py`
- [ ] Vocabularies have exactly the LLD members and string values; the dataclasses are frozen
- [ ] Table-driven `check_standing` cases: `errored` with count 12, 0, and `None` is `errored`; `passed` with `None` is `unattested`; `failed` with `None` is `unattested`; `passed` with 0 and `failed` with 0 are both `vacuous`; `passed` with 12 is `passed`; `failed` with 3 is `failed`
- [ ] `RecordSource` has the two new members and keeps the old ones
- [ ] `VerdictRecord` accepts `judge_invocation_id`, and it is `None` when omitted (existing constructions unchanged)

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 2.1, e.g. `feat(store): add check and work-record vocabularies`

**Files to Create**: `tests/store/test_check_models.py`

---

### Task 2.3: Add `CalibrationRow` and `summarize_judge_samples`
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 3
**Objective**: The D4 aggregation as a pure function over `VerdictRecord`s, with no SQL.

**Steps**:
- [ ] Add frozen dataclass `CalibrationRow` to `check_models.py` with the D4 fields exactly (`by_verdict` and `by_standing` are mappings keyed by `ReviewVerdict` / `VerdictStanding`, with every member present, zero when absent)
- [ ] Create `src/amoeba/store/calibration.py` with `summarize_judge_samples(records: Sequence[VerdictRecord]) -> tuple[CalibrationRow, ...]`. Input is judge samples only; a record with no `judge_invocation_id` raises `ValueError` (do not silently skip)
- [ ] Group by `(review_type, model)`; sort rows by `review_type`, then `model`
- [ ] `split_invocations`: for each invocation, collect verdicts across all models, leaving out samples whose standing is `provider_failure` or `unparsed`; the invocation is split if more than one distinct verdict remains. A row counts the split invocations among those it has a sample in
- [ ] `score_*` are over scored samples; `None` when `scored` is 0. Mean is the plain arithmetic mean, unrounded
- [ ] Use the `VerdictStanding` names and the `standing` property already on `VerdictRecord`; do not recompute standing

**Success Criteria**:
- [ ] Imports; `ruff` and `pyright` clean
- [ ] The module has no `sqlite3` or SQL import

**Files to Create/Modify**: `src/amoeba/store/calibration.py`, `src/amoeba/store/check_models.py`

---

### Task 2.4: Test `summarize_judge_samples` on built records
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 3
**Objective**: Pin every D4 field with no store involved.

**Steps**:
- [ ] Create `tests/store/test_calibration.py` building `VerdictRecord`s directly (no `Store`)
- [ ] One invocation with samples from three models (PASS, CONCERNS, CONCERNS): three rows, each with `invocations` 1 and `split_invocations` 1
- [ ] An invocation whose samples all agree: `split_invocations` 0
- [ ] A `provider_failure` sample and an `unparsed` sample alongside one PASS: not split
- [ ] A sample with no score: `scored` excludes it; a group with none scored has `score_min`, `score_mean`, `score_max` all `None`
- [ ] Distinct-invocation counting: two samples of the same invocation and model give `samples` 2 and `invocations` 1; the same invocation id under two models counts once in each model's row
- [ ] Numeric aggregation: scores 71, 80, 98 in one group give `scored` 3, `score_min` 71, `score_mean` 83.0, `score_max` 98 (computed by hand, not by the code under test)
- [ ] `by_verdict` and `by_standing` counts, including zero-filled members; row ordering; empty input gives `()`
- [ ] A record without `judge_invocation_id` raises `ValueError`

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 2.3, e.g. `feat(store): add judge-sample calibration summary`

**Files to Create**: `tests/store/test_calibration.py`

---

## Section 3: Migration

### Task 3.1: Write the migration and `sql_checks.py`
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 3
**Objective**: Create the schema (LLD "Database / Storage Schema") with every name defined once in Python.

**Steps**:
- [ ] Create `src/amoeba/store/schema/{N}_judge_samples_checks_and_work.sql` (N, zero-padded like its neighbors, from Task 1.1): `ALTER TABLE verdicts ADD COLUMN judge_invocation_id TEXT`, the `(project_id, judge_invocation_id)` index, and the `check_results` and `work_records` tables with their indexes, columns exactly as in the LLD. No `CHECK` constraints on vocabulary columns; no backfill
- [ ] Set `EXPECTED_SCHEMA_VERSION` to N in `store/migrations.py`
- [ ] Create `src/amoeba/store/sql_checks.py`: column-name tuples and statements (insert, select by id, select by project/node, select work records with optional kind) for both tables. Import the provenance column names from `sql_evidence.py` (move them to a shared constant there if they are not already importable; do not repeat them)
- [ ] Do not edit the `verdicts` statements yet (Task 4.1)

**Success Criteria**:
- [ ] A fresh store migrates to the new version; `ruff` and `pyright` clean
- [ ] Existing suites still pass (the pinned schema-version assertions in `tests/test_migrations.py` are updated to the new number and nothing else changes)

**Files to Create/Modify**: the migration, `sql_checks.py`, `migrations.py`, `sql_evidence.py` (shared constant only), `tests/test_migrations.py`

---

### Task 3.2: Test the migration and the upgrade path
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 3
**Objective**: Prove the schema and that an upgrade keeps data (LLD Technical Requirements).

**Steps**:
- [ ] In `tests/test_migrations.py`, following the existing version-two-to-three test: build a store at the previous version holding a node, a journal entry, an inbox submission, a message, a verdict, and a finding observation; upgrade; assert all rows intact and every verdict's `judge_invocation_id` is `NULL`
- [ ] Assert the three tables/columns and the indexes exist after migration
- [ ] Assert the column lists in `check_results` and `work_records` equal the names in `sql_checks.py` (as `test_journal_columns_match_the_single_definition_site` does for the journal)

**Success Criteria**:
- [ ] Tests pass; full suite, `ruff`, `pyright` clean
- [ ] Commit with Task 3.1, e.g. `feat(store): add migration for judge samples, checks, work records`

**Files to Modify**: `tests/test_migrations.py`

---

## Section 4: Judge Samples

### Task 4.1: Carry `judge_invocation_id` through the verdict models, SQL, and mapping
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: A verdict can be written and read back with its invocation id (LLD D1).

**Steps**:
- [ ] `VerdictRecord` already has `judge_invocation_id` (Task 2.1). Add `judge_invocation_id: str | None = None` to `VerdictInput` in `evidence_models.py` now, together with the storage wiring below, so the field is never accepted without being stored. Update `_INPUT_FIELDS` / `_as_input` in `verdicts.py` so a replay comparison includes it
- [ ] Add the column to the verdict column list and `INSERT_VERDICT` in `sql_evidence.py`; update `verdict_parameters` and `map_verdict` in `mapping_evidence.py`. `mapping_evidence.py` is 293 lines and the change should add only a few. If it ends well over ~300 lines, do not split it here; report the length to the PM
- [ ] Extend `tests/evidence_harness.py` `verdict_input` with an optional `judge_invocation_id` argument (default `None`; existing callers unchanged)

**Success Criteria**:
- [ ] Existing verdict tests pass unchanged; `ruff` and `pyright` clean

**Files to Modify**: `sql_evidence.py`, `mapping_evidence.py`, `verdicts.py`, `tests/evidence_harness.py`

---

### Task 4.2: Test round trip of the id
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 2
**Objective**: The new column is written and read faithfully.

**Steps**:
- [ ] Create `tests/store/test_judge_samples.py`
- [ ] Record a verdict with `judge_invocation_id="j1"`: `verdict(id)` and `verdicts(...)` return it; a verdict without one returns `None`
- [ ] Replaying the same id with a different invocation id returns the first record and logs a WARNING (use `caplog`)
- [ ] `VerdictInput` accepts `judge_invocation_id` and it is `None` when omitted (existing constructions unchanged)

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 4.1, e.g. `feat(store): record judge_invocation_id on verdicts`

**Files to Create**: `tests/store/test_judge_samples.py`

---

### Task 4.3: Add the `judge_invocation_id` payload key and `VerdictPayload` field
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 2
**Objective**: The inbox `verdict` kind carries the id (LLD "Inbox").

**Steps**:
- [ ] Add `VERDICT_JUDGE_INVOCATION_ID` to `verdict_payload.py`, and read it (optional key) in `verdict_from_payload`
- [ ] Add `judge_invocation_id: str | None = None` to `VerdictPayload` in `inbox/evidence_payloads.py`; payload validation refuses an empty string
- [ ] `VERDICT_JUDGE_INVOCATION_ID` and `VerdictPayload.judge_invocation_id` must agree by name; Task 4.4 owns the test that pins this
- [ ] `verdict_to_payload` is 105's function. Read the Task 1.1 notes. If it exists, update it **in this task** so it emits the key when the id is set and omits it when `None`, then run 105's tests for it; they must pass (adding a payload field must not break a test that compares payload fields to the emitted keys). If it does not exist, leave it; Task 6.1 does it. Task 6.1 repeats this condition

**Success Criteria**:
- [ ] A payload with the key becomes a `VerdictInput` with the id; one without it has `None`
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `store/verdict_payload.py`, `inbox/evidence_payloads.py`

---

### Task 4.4: Test the payload key through the inbox and `amoeba submit`
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 2
**Objective**: Judge samples arrive through the existing path with no new CLI code.

**Steps**:
- [ ] Find the existing test that pins payload field names against `verdict_payload.py` and extend it so the new key is covered; if no such test exists, add one that fails when `VerdictPayload`'s field names and the `verdict_payload.py` constants diverge
- [ ] Add inbox-apply tests (follow `tests/store/test_inbox_apply.py` style): a submission with the key records a sample; an empty-string key is refused by payload validation (quarantined as the existing invalid-payload tests show)
- [ ] Add a CLI flag test (follow the existing `amoeba submit verdict` tests): `--judge-invocation-id J` appears in `amoeba submit verdict --help` and is written into the submission

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 4.3, e.g. `feat(inbox): accept judge_invocation_id on the verdict kind`

---

### Task 4.5: Enforce the D2 same-node rule and the empty-id precondition on both paths
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: A sample whose invocation already has a sample on another node is refused (LLD D2, "Error handling").

**Steps**:
- [ ] Add a statement to `sql_evidence.py` (or the new module): one indexed lookup for a sample of `(project_id, judge_invocation_id)` whose node differs from the new node
- [ ] In `_verdict_rejection`, after the provider-failure rules, add an explicit branch returning a `VerdictRejection` whose reason names the invocation id and the node it is already on. Applies only when `judge_invocation_id` is set. Do not catch exceptions to do this
- [ ] In the same function, an empty-string `judge_invocation_id` returns a `VerdictRejection` too (a `ValueError` on the direct path), not a silent `None`. This guards the direct `record_verdict` path; the inbox never reaches it with an empty id, because payload validation (Task 4.3) refuses it first
- [ ] No change to `record_verdict`: its existing raise-on-rejection covers the direct path; the inbox returns the reason as `rejected`

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; existing tests pass

**Files to Modify**: `_verdict_writer.py`, `sql_evidence.py`

---

### Task 4.6: Test D2 on both paths
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 2
**Objective**: Prove the rule and that review verdicts are never affected.

**Steps**:
- [ ] Direct call: second sample of `j1` on another node raises `ValueError` naming `j1` and the first node; nothing written
- [ ] Inbox: the same submission is `rejected` with that reason; the first sample is untouched
- [ ] Samples of one invocation on the same node may differ in model, review type, and verdict; all are recorded
- [ ] Two different invocations on different nodes are fine; review verdicts (no id) on any node are fine
- [ ] An empty-string `judge_invocation_id` raises `ValueError` on the direct path; nothing written. (The inbox case is covered once, in Task 4.4: payload validation quarantines it)
- [ ] A sample on a node outside the project still raises `NodeNotFoundError` (precedence is unchanged)

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 4.5, e.g. `feat(store): keep a judge invocation on one node`

---

### Task 4.7: Add the `judge_invocation_id` filter to `verdicts`
**Owner**: Junior AI
**Dependencies**: Task 4.6
**Effort**: 2
**Objective**: Read one invocation's samples back (LLD "API Contracts").

**Steps**:
- [ ] Change the signature to `verdicts(project_id, *, node_id=None, judge_invocation_id=None)`; both filters combine
- [ ] Prefer one statement builder over adding a third near-duplicate `SELECT_VERDICTS_*` constant: keep SQL text in `sql_evidence.py`; results stay in `recorded_seq` order

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; 104's verdict-read tests pass unchanged

**Files to Modify**: `verdicts.py`, `sql_evidence.py`

---

### Task 4.8: Test the filter
**Owner**: Junior AI
**Dependencies**: Task 4.7
**Effort**: 2
**Objective**: Three samples of one invocation stay three records, in arrival order.

**Steps**:
- [ ] Record three samples of `j1` (three models, differing score and verdict, each with its own run id and `criteria`) and one of `j2`, plus one review verdict, on one node
- [ ] `verdicts(project, judge_invocation_id="j1")` returns exactly the three, in arrival order, each with its own fields; none merged
- [ ] Filter combined with `node_id`; an unknown id returns `[]`

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 4.7, e.g. `feat(store): filter verdicts by judge invocation`

---

### Task 4.9: Apply the D3 exclusion to the previous-round query
**Owner**: Junior AI
**Dependencies**: Task 4.8
**Effort**: 3
**Objective**: A judge sample never takes a sample of its own invocation as its previous round (LLD D3).

**Steps**:
- [ ] Open the current `SELECT_EARLIER_ROUNDS` and `_previous_round`. If 106 is merged, they already group by `source_document`; build on that version and keep that behavior
- [ ] When the target has a `judge_invocation_id`, the query also excludes rows with that same id. Rows with a different id, or none, remain candidates. When the target has none, the query is exactly as before
- [ ] Express this as a statement parameter or a second statement chosen by the target, not by post-filtering in Python after a limit

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; 104's (and 106's) `finding_changes` tests pass as they are

**Files to Modify**: `sql_evidence.py`, `verdicts.py`

---

### Task 4.10: Test D3
**Owner**: Junior AI
**Dependencies**: Task 4.9
**Effort**: 3
**Objective**: Prove the exclusion and that review verdicts are unaffected.

**Steps**:
- [ ] Two samples of `j1` with the same finding: `finding_changes` on the second has no previous round (not `recurring`)
- [ ] An earlier invocation `j0` (same node and review type) is present: the second `j1` sample compares against `j0`'s latest comparable sample
- [ ] Cross-type: on one node, a review verdict (no invocation id, review type `tasks`) and a judge sample (review type `judge.tasks-vs-slice`) carry the same finding. The judge sample has no previous round, and the review verdict's previous round is never the judge sample. Both hold because review types differ; no other mechanism is needed
- [ ] An existing multi-round review-verdict case gives the same result as before

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 4.9, e.g. `feat(store): exclude own invocation from judge previous round`

---

### Task 4.11: Implement `Store.calibration`
**Owner**: Junior AI
**Dependencies**: Task 4.10, Task 2.4
**Effort**: 2
**Objective**: Wire the pure summary to the store (LLD D4, Data Flow).

**Steps**:
- [ ] Add `calibration(project_id) -> tuple[CalibrationRow, ...]` to `VerdictOperations`: select verdicts with a non-null `judge_invocation_id` for the project in `recorded_seq` order (one statement in `sql_evidence.py`), map to records with findings as `_record_from_row` does, call `summarize_judge_samples`
- [ ] Read-only: no transaction, no write. It must work on a handle from `Store.open_read_only`
- [ ] Parameters: the project id only

**Success Criteria**:
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `verdicts.py`, `sql_evidence.py`

---

### Task 4.12: Test `calibration` against a store
**Owner**: Junior AI
**Dependencies**: Task 4.11
**Effort**: 2
**Objective**: Store-level proof of the D4 cases, including read-only use.

**Steps**:
- [ ] A built set: one invocation across two models (PASS vs CONCERNS) counts in both rows with `split_invocations` 1 in each; a provider-failure sample does not make an invocation split; no scored samples gives `None` scores; review verdicts are not counted
- [ ] Calling `calibration` on a `Store.open_read_only` handle (follow `tests/test_read_only_open.py`) returns the same rows
- [ ] A project with no judge samples returns `()`; another project's samples are not included

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 4.11, e.g. `feat(store): add calibration report`

---

## Task 1.1 Notes

*Task 1.1 fills this in. Nothing below is known until then.*

- EXPECTED_SCHEMA_VERSION:
- Highest existing migration file:
- Migration number N:
- 105 merged (`upstream/squadron/review.py` exists):
- `verdict_to_payload` exists:
- 106 merged (`source_document` column exists):
- PM ratification of D2, D3, D4, D6:
- Fresh judge fixture decision (Task 6.3):
