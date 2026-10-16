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

## Context Summary (File 2 of 2)

Continues `107-tasks.judge-samples-checks-and-calibration-1.md`; read its Context Summary, reading note, commit cadence, and section map first. This file holds Sections 5–8: calibration, the `check` kind and feed change, ingest and listings, and end-to-end/docs/validation. Branch: `107-slice.judge-samples-checks-and-calibration`. No task here merges.

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
- [ ] No-metrology test: scan every file under `src/` (text, in the style of `tests/upstream/test_field_names_defined_once.py`) and assert none contains the substring `metrology`, case-insensitively. This needs no Squadron strings: the LLD requires only that `src/` never references that store
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
- [ ] Extend `tests/store/test_feed_invariant.py`: its scripted sequence records a check, so the invariant test covers `check_recorded` and fails if that trigger is missing. Note: the LLD's Technical Requirements say "two new kinds", but D9 defines exactly one (`check_recorded`); follow D9
- [ ] Check the public feed read (`changes`/`amoeba feed` path) returns the new kind without an unknown-vocabulary error

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): emit check_recorded changes by trigger`

**Files to Modify**: `tests/store/test_feed_triggers.py`, `tests/store/test_feed_invariant.py`

---

### Task 6.5: Confirm the real judge artifact and test it against 105's parser
**Owner**: Junior AI (the capture itself is a PM step)
**Dependencies**: Task 6.4
**Effort**: 2
**Objective**: The real judge artifact parses to its stated values (LLD Functional Requirements, Technical Requirements on the fixture). It sits here, not at the start, so the PM's capture does not block earlier work.

**Steps**:
- [ ] Look in `tests/fixtures/sq_reviews/` for a saved judge-template review artifact (`reviewType` starting `judge.`) from a pipeline run on squadron 0.21.9 or later. If it is missing, **stop and ask the PM** to capture it (a pipeline run in a throwaway copy of a repository). Do not hand-write it. Tasks 7.2, 8.1, and 8.3 need it; no earlier task does
- [ ] Confirm `tests/fixtures/README.md` records its command, Squadron version, and date. If an entry is missing, ask the PM; do not infer
- [ ] Add a path constant to `tests/review_fixtures.py` and `tests/upstream/test_review_judge_fixture.py`, in the style of `test_review_artifact.py`: assert review type, verdict, score, model, and criteria equal the values stated in the file, and that `verdict_source` is absent, so the resulting trust label is `unattested`

**Success Criteria**:
- [ ] The fixture is present, documented, and its tests pass against the unmodified parser
- [ ] Commit, e.g. `test: add real judge review fixture tests`

**Files to Create**: `tests/upstream/test_review_judge_fixture.py`
**Files to Modify**: `tests/review_fixtures.py`, `tests/fixtures/README.md` (if the PM's capture lacks an entry)

---

## Section 7: Ingest and Listings

### Task 7.1: Add `--judge-invocation-id` and the sample id to `ingest review`
**Owner**: Junior AI
**Dependencies**: Task 6.5
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
- [ ] Update the pinned-registry test (`tests/inbox/test_listings.py`, where `LISTINGS` names are pinned)

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
**Objective**: LLD Integration Requirements, first bullet. The wrong-review-type rejection and the stdout refusal are already pinned (Tasks 4.4 and 1.3) and are not repeated here.

**Steps**:
- [ ] Read `tests/cli/test_evidence_end_to_end.py` and `tests/ingest_e2e_harness.py`; add `tests/cli/test_judge_end_to_end.py` using the same subprocess harness. Seed the node the way those tests do
- [ ] Flow: create a project, seed a node, ingest the judge artifact under `j1`, submit two more samples and a check with count 0 through `amoeba submit`, `kill -9` the process, `start` again
- [ ] Assert via read-only inspection: three samples under `j1`, a calibration row with the expected counts, the check `vacuous`, nothing applied twice, and `amoeba feed` shows exactly one `verdict_recorded` per sample and one `check_recorded`

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
- [ ] Run the LLD Verification Walkthrough steps 1–7 in bash against a throwaway `AMOEBA_STORE_DIR` with the real judge fixture. Where its `<judge fixture>` and `<edited judge stdout>` placeholders appear, use the judge fixture from Task 6.5 and the edited stdout fixture from Task 1.3. Compare each result with the walkthrough's expected output
- [ ] Update the LLD walkthrough with the real output and fixture names (its header says it is refined when Phase 6 completes). Edit the walkthrough section only
- [ ] Close GitHub issue #2 after the commit above: `gh issue close 2 --comment "Fixed by D4 (slice 107): judge stdout reporting UNKNOWN with a score is refused; ingest the saved review file instead. Commit <sha>."` using the real commit sha. If `gh` fails, report the error to the PM

**Success Criteria**:
- [ ] Suite, `ruff`, `pyright` clean; every walkthrough step matches
- [ ] Commit, e.g. `docs: record 107 walkthrough output`
- [ ] The slice branch holds all commits; nothing is merged (Phase 7 follows the code review)

**Files to Modify**: `project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md` (walkthrough only)
