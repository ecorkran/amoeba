---
docType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
lld: user/slices/107-slice.judge-samples-checks-and-calibration.md
dependencies: [101, 102, 103, 104, 105, 106]
projectState: Sections 1–4 (file 1) are complete — vocabularies, `summarize_judge_samples`, the migration, judge samples end to end in the store (column, payload key, D2, D3, filter), and `calibration()` exist and are tested. This file holds checks and work records, the parser and ingest changes, listings, the demo script, end-to-end test, docs, and final validation.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **judge-samples-checks-and-calibration** slice (107), continued from `107-tasks.judge-samples-checks-and-calibration-1.md` (Sections 1–4). Read file 1's Context Summary, branch, reading note, PM-ratification note, and commit cadence; they apply here unchanged.
- **Sections in this file:** 5 checks and work records; 6 parser, ingest, fixtures (needs slice 105); 7 listings; 8 proof, docs, final validation.
- **Branch:** still `107-slice.judge-samples-checks-and-calibration`. No task here merges.
- **Migration number:** use the number recorded in Task 1.1 wherever "007" appears.

---

## Section 5: Checks and Work Records

### Task 5.1: Add `mapping_checks.py`
**Owner**: Junior AI
**Dependencies**: Task 4.12
**Effort**: 2
**Objective**: Row ↔ record mapping for the two tables, raising on unknown vocabulary values (LLD "Database / Storage Schema").

**Steps**:
- [ ] Create `src/amoeba/store/mapping_checks.py`: insert-parameter builders and row mappers for `check_results` and `work_records`. `examined` and `content` are JSON text; `examined_count` and `examined` map `NULL` to `None`
- [ ] An unknown `outcome`, `kind`, or `source` value raises (as `mapping_evidence.py` does); no fallback value
- [ ] Reuse provenance mapping helpers from `mapping_evidence.py` if they exist; do not duplicate them

**Success Criteria**:
- [ ] `ruff` and `pyright` clean

**Files to Create**: `src/amoeba/store/mapping_checks.py`

---

### Task 5.2: Test the mapping
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 2
**Objective**: Round-trip fidelity without a store logic layer.

**Steps**:
- [ ] Create `tests/store/test_mapping_checks.py`: parameters then row round trip for a check with `examined` and count, a check with both `None`, and a work record with nested JSON content
- [ ] An unknown outcome, kind, and source each raise

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 5.1, e.g. `feat(store): map check and work-record rows`

---

### Task 5.3: Implement `record_check`, `check`, and `checks`
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 3
**Objective**: Record a check in one transaction with D5's preconditions (LLD "Data Flow", "API Contracts").

**Steps**:
- [ ] Create `src/amoeba/store/checks.py` with a `CheckOperations` mixin (base `StoreBase`). Model transaction handling on `record_verdict`: `BEGIN IMMEDIATE`, replay check first
- [ ] `record_check(check: CheckInput, *, project_id: str) -> CheckRecord`: if the id exists, return the existing record, write nothing, log a WARNING if content differs. Otherwise raise `NodeNotFoundError` for a node not in the project, and `ValueError` for: empty `name`, empty `upstream_version`, negative `examined_count`, or `examined_count` differing from `len(examined)` when `examined` is given. Nothing is written on failure
- [ ] `check(check_id) -> CheckRecord | None`, and `checks(project_id, *, node_id=None)` in `recorded_seq` order. `standing` comes from `check_standing`
- [ ] Add `CheckOperations` to `Store`'s bases in `store/store.py` beside `VerdictOperations`

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; `store.py` stays near 300 lines (it is 303 now: add only the base class and import)

**Files to Create/Modify**: `src/amoeba/store/checks.py`, `src/amoeba/store/store.py`

---

### Task 5.4: Test checks
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 3
**Objective**: Cover every LLD check criterion.

**Steps**:
- [ ] Create `tests/store/test_checks.py` (use `seed_node` from the evidence harness)
- [ ] Each `CheckStanding` row produced by a recorded check: `passed` (count 12), `failed`, `vacuous` (count 0, passed), `vacuous` (count 0, failed), `unattested` (`None`), `errored` (outcome errored with count 0)
- [ ] Rejections: negative count, count not equal to `len(examined)`, empty name, unknown node, empty `upstream_version`; each leaves the table unchanged
- [ ] Replay: same id returns the existing record, writes nothing; differing content logs a WARNING (`caplog`)
- [ ] `checks` ordering and `node_id` filter; another project's checks excluded; `examined` round-trips as a tuple

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 5.3, e.g. `feat(store): record checks with derived standing`

---

### Task 5.5: Implement `record_work` and `work_records`
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 2
**Objective**: Store `task_progress` and `devlog` records with opaque content (LLD D6).

**Steps**:
- [ ] Add to `CheckOperations` in `checks.py`: `record_work(work: WorkRecordInput, *, project_id: str) -> WorkRecordRecord` and `work_records(project_id, *, node_id=None, kind=None)` in `recorded_seq` order
- [ ] Same transaction and replay pattern as `record_check`. Rejections: unknown node (`NodeNotFoundError`); empty `upstream_version`, or `content` that is not a JSON object / not JSON-serializable (`ValueError`). The store checks nothing else about `content`
- [ ] If `checks.py` approaches 300 lines, move the shared replay/transaction scaffolding into a helper rather than duplicating it

**Success Criteria**:
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/store/checks.py`

---

### Task 5.6: Test work records
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 2
**Objective**: Cover the LLD work-record criteria.

**Steps**:
- [ ] Add to `tests/store/test_checks.py` (or a new `test_work_records.py` if it would pass ~300 lines)
- [ ] Content with nested values is stored and returned as given
- [ ] Content that is a list, string, or not serializable is rejected; unknown node and empty `upstream_version` are rejected
- [ ] `work_records(kind=...)` filters; node filter; order; replay returns the first and warns on differing content

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 5.5, e.g. `feat(store): record task_progress and devlog work records`

---

### Task 5.7: Export the new API and update the public-API test
**Owner**: Junior AI
**Dependencies**: Task 5.6
**Effort**: 1
**Objective**: Export the new names from `amoeba.store` (LLD Technical Requirements).

**Steps**:
- [ ] Export from `amoeba.store`: `CheckOutcome`, `CheckStanding`, `check_standing`, `CheckInput`, `CheckRecord`, `WorkRecordKind`, `WorkRecordInput`, `WorkRecordRecord`, `CalibrationRow`
- [ ] Update the pinned export set in `tests/test_public_api.py` to match, and nothing else
- [ ] Extend 104's metrology-reference test, if it enumerates modules, to include `check_models.py`, `calibration.py`, `checks.py`, `sql_checks.py`, `mapping_checks.py`

**Success Criteria**:
- [ ] Full suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat(store): export check, work-record, and calibration API`

**Files to Modify**: `src/amoeba/store/__init__.py`, `tests/test_public_api.py`

---

## Section 6: Parser, Ingest, and Fixtures

*Requires slice 105. If Task 1.1 found `upstream/squadron/review.py` missing, stop and ask the PM before this section.*

### Task 6.1: Pass `judge_invocation_id` through `to_verdict_input` and `verdict_to_payload`
**Owner**: Junior AI
**Dependencies**: Task 5.7
**Effort**: 2
**Objective**: 105's parser and its payload inverse carry the id (LLD "105's parser").

**Steps**:
- [ ] Add a `judge_invocation_id: str | None = None` keyword to `to_verdict_input` and set it on the `VerdictInput`. It must **not** enter `review_record_id` (LLD D1: one file is one sample)
- [ ] Make `verdict_to_payload` emit `VERDICT_JUDGE_INVOCATION_ID` when the id is set, and omit the key when `None`
- [ ] Extend 105's round-trip test (`verdict_to_payload` then `verdict_from_payload`) with a record that has an id

**Success Criteria**:
- [ ] The same file ingested with two different ids has the same record id
- [ ] Existing 105 tests pass; `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/upstream/squadron/review.py` (and its payload module), 105's round-trip test

---

### Task 6.2: Test the parser changes
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 1
**Objective**: Pin the id's pass-through and its absence from the record id.

**Steps**:
- [ ] Add tests next to 105's `to_verdict_input` tests: id set on the result; absent id is `None`; record id identical with and without an id
- [ ] Round trip keeps the id; a record without one produces a payload without the key

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 6.1, e.g. `feat(upstream): carry judge_invocation_id through the review parser`

---

### Task 6.3: Add the judge fixtures and README entries
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 3
**Objective**: Real judge output pins `score`, `criteria`, and the absent `verdictSource` (LLD Technical Requirements, Fixtures).

**Steps**:
- [ ] Locate Squadron's `302-review.judge.slice-vs-arch.design-phase-judge-templates.md` in the Squadron repository (ask the PM for the path if it is not found; do not recreate it). Copy it byte for byte (`cp`) into `tests/fixtures/sq_reviews/`
- [ ] Capture one fresh judge file: run `sq review` on a judge template with `--model glmflash` in a throwaway copy of this repository, never in this working tree. Copy the saved file byte for byte. If `sq` or its provider key is unavailable, stop and ask the PM
- [ ] Add README entries for both in `tests/fixtures/README.md` in the existing style: capture date, source, exact command for the fresh file, and what each pins. Record Squadron's version only as a dated observation
- [ ] Check each file with a read-only look: `score` and a `criteria` mapping present; no `verdictSource` key; the 302 file has no stamp

**Success Criteria**:
- [ ] Both files are byte-identical to their source; README entries exist
- [ ] No assumption about the fresh file's content is made before it is read

**Files to Create/Modify**: two files in `tests/fixtures/sq_reviews/`, `tests/fixtures/README.md`

---

### Task 6.4: Test the parser against the judge fixtures
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 2
**Objective**: Real input, per project parsing rules.

**Steps**:
- [ ] For each judge fixture: `parse_review_artifact` then `to_verdict_input(..., judge_invocation_id="j1")` gives a sample with `score` and `criteria` from the file, `derivation` `not_reported`, and `standing` `unattested`
- [ ] For the 302 file: `review_type` is `judge.slice-vs-arch`, verdict PASS, score 98.0 (the LLD walkthrough value; assert what the file actually says, and report to the PM if it differs)

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 6.3, e.g. `test: add judge review fixtures`

---

### Task 6.5: Add `--judge-invocation-id` to `amoeba ingest review`
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 2
**Objective**: Ingest can record a judge sample (LLD "CLI").

**Steps**:
- [ ] Add the optional option to `cli/ingest.py` and pass it to `to_verdict_input`; an empty string is a usage error with the existing usage exit code
- [ ] Update the command's `--help` text

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; 105's ingest tests pass unchanged

**Files to Modify**: `src/amoeba/cli/ingest.py`

---

### Task 6.6: Test ingest with the id
**Owner**: Junior AI
**Dependencies**: Task 6.5
**Effort**: 2
**Objective**: Judge file to recorded sample through the real command.

**Steps**:
- [ ] Follow 105's ingest success-path test style (real process or its established harness): ingest the 302 fixture with `--judge-invocation-id j1`; the resulting verdict has the id, `score`, `criteria`, and standing `unattested`
- [ ] Ingesting the same file again into `j2` is a no-op that keeps the first (first wins); `--id` makes it a second record
- [ ] An empty `--judge-invocation-id` exits with the usage code and writes nothing

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 6.5, e.g. `feat(cli): add --judge-invocation-id to ingest review`

---

## Section 7: Listings

### Task 7.1: Add the judge column and filter to `inspect verdicts`
**Owner**: Junior AI
**Dependencies**: Task 6.6
**Effort**: 2
**Objective**: `inspect verdicts` shows and filters by invocation (LLD "CLI").

**Steps**:
- [ ] In `cli/inspect_evidence.py`, add a `judge_invocation_id` column to verdict rows (blank for review verdicts in table output; `null`/absent handling in `--json` as the other nullable columns do)
- [ ] Register the `--judge-invocation-id` option for `verdicts` in `cli/inspect.py`'s `LISTINGS` entry, using the registry's `value_options` mechanism; pass it to `verdicts(...)`

**Success Criteria**:
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `cli/inspect_evidence.py`, `cli/inspect.py`

---

### Task 7.2: Test the verdicts listing change
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 2
**Objective**: Existing output stays compatible; the new column and filter work.

**Steps**:
- [ ] Extend 104's `inspect verdicts` tests: the column exists; filter returns exactly one invocation's rows; review verdicts show a blank id; the filter and `--node` combine
- [ ] Works against a stopped process (read-only handle)

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 7.1, e.g. `feat(cli): show and filter judge invocation in inspect verdicts`

---

### Task 7.3: Add `inspect calibration`
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 2
**Objective**: The report as a read-only listing (LLD "CLI").

**Steps**:
- [ ] In `cli/inspect_evidence.py`, add `calibration_rows` with columns exactly: `review_type, model, samples, invocations, split_invocations, pass, concerns, fail, unknown, score_min, score_mean, score_max`; `--json` rows also carry `by_standing` and `scored`
- [ ] Register `calibration` in `LISTINGS` (project-scoped, no other options); use the `ReviewVerdict` members to build the verdict count columns rather than repeating literals where practical

**Success Criteria**:
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `cli/inspect_evidence.py`, `cli/inspect.py`

---

### Task 7.4: Test `inspect calibration`
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Columns, JSON extras, and read-only behavior.

**Steps**:
- [ ] Seed a store with the Task 4.12 set; table output has the exact column header and expected counts
- [ ] `--json` rows carry `by_standing` and `scored`; unscored groups show `null` scores
- [ ] Runs with the process stopped; an unknown project follows the existing listing behavior

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 7.3, e.g. `feat(cli): add inspect calibration`

---

### Task 7.5: Add `inspect checks` and `inspect work-records`
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 3
**Objective**: The two remaining listings (LLD "CLI"), each its own row function.

**Steps**:
- [ ] Create `src/amoeba/cli/inspect_checks.py` with `check_rows` (columns `recorded_seq, id, node_id, name, outcome, examined_count, standing, upstream_version`; `--json` adds `examined` and the provenance fields) and `work_record_rows` (columns `recorded_seq, id, node_id, kind, upstream_version, recorded_at`; `--json` adds `content`)
- [ ] Register `checks` (option `--node`) and `work-records` (options `--node`, `--kind` restricted to `WorkRecordKind` values via `value_options`) in `LISTINGS`
- [ ] Update the pinned registry test (`tests/test_cli_inspect.py` or wherever `LISTINGS` names are pinned) to include `calibration`, `checks`, `work-records`

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; an invalid `--kind` follows the existing invalid-option exit behavior

**Files to Create/Modify**: `cli/inspect_checks.py`, `cli/inspect.py`, registry test

---

### Task 7.6: Test the checks and work-records listings
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 2
**Objective**: Columns, filters, and JSON extras.

**Steps**:
- [ ] Seed checks of standing `passed`, `vacuous`, `unattested` and one `task_progress` and one `devlog` record
- [ ] `checks` table shows the standing column; `--node` filters; `--json` has `examined` and provenance
- [ ] `work-records` table columns; `--kind task_progress` filters; `--json` shows `content` as recorded; an invalid `--kind` is refused
- [ ] Both work with the process stopped

**Success Criteria**:
- [ ] Tests pass; full suite, `ruff`, `pyright` clean
- [ ] Commit with Task 7.5, e.g. `feat(cli): add inspect checks and work-records`

---

## Section 8: Proof, Docs, and Final Validation

### Task 8.1: Add `scripts/demo_checks.py` and update the writer guard
**Owner**: Junior AI
**Dependencies**: Task 7.6
**Effort**: 3
**Objective**: Seed checks and work records for the walkthrough (LLD "Verification Walkthrough").

**Steps**:
- [ ] Create `scripts/demo_checks.py` modeled on `scripts/demo_evidence.py`: takes the instance lock and refuses while the process runs; requires `--node NODE`; records on that node three checks (12 examined and passed; 0 examined and passed; no count) and one `task_progress` work record; seeds a second node in the same project; **prints only that second node's id** to stdout
- [ ] Add `demo_checks.py` to `PERMITTED_SCRIPTS` and to the set asserted near line 290 in `tests/test_writer_guard.py`; update the explanatory comment
- [ ] Use fixed record ids so a re-run is a first-wins no-op; log nothing to stdout besides the id

**Success Criteria**:
- [ ] The writer-guard test passes with the new script named
- [ ] Running the script against a scratch store prints exactly one node id; `ruff` and `pyright` clean

**Files to Create/Modify**: `scripts/demo_checks.py`, `tests/test_writer_guard.py`

---

### Task 8.2: End-to-end test through the real CLI
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 4
**Objective**: Prove the LLD "Integration Requirements" scenario with subprocesses.

**Steps**:
- [ ] Create `tests/cli/test_judge_end_to_end.py` modeled on `tests/cli/test_evidence_end_to_end.py` (scratch `AMOEBA_STORE_DIR`, empty `--sq-runs-dir`, wait for `running`)
- [ ] Create a project, stop, seed a node with `demo_evidence.py` and a second node with `demo_checks.py`, start
- [ ] Ingest the 302 fixture as a sample of `j1`; submit two built `j1` samples with other models via `amoeba submit verdict --judge-invocation-id j1` (one CONCERNS); submit one `j1` sample on the second node
- [ ] `kill -9` the process, start it again, then read only with `inspect`: three `j1` samples; one `rejected` submission whose reason names D2's invocation and node; `calibration` shows `split_invocations` 1 in every row `j1` touches; `checks` shows `passed`, `vacuous`, `unattested`; `work-records` shows the `task_progress` record
- [ ] Nothing is applied twice after the crash (row counts unchanged)

**Success Criteria**:
- [ ] Test passes; no leftover processes; `ruff` and `pyright` clean
- [ ] Commit with Task 8.1, e.g. `test: add judge sample and check end-to-end proof`

---

### Task 8.3: Update `docs/evidence-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 3
**Objective**: Document the contract (LLD Technical Requirements, last bullet).

**Steps**:
- [ ] Add sections: the D1 names (judge invocation, judge sample, review verdict); D2; D3; D4 (the fields, the overcount note for `split_invocations`, and what the report does not do: no thresholds, no agreement rate, no writes to Squadron); the check standing table; D6's mapping of SQ 280's four types; the judge-standing observation (why a judge sample reads `unattested`, one paragraph, as a dated observation without version pins)
- [ ] Document `RecordSource`'s two new members, the new Store methods, the inbox key, and the CLI listings
- [ ] Frontmatter stays valid per `file-naming-conventions`; update `dateUpdated`

**Success Criteria**:
- [ ] Each LLD-required topic has a heading or paragraph; no statement contradicts the LLD or the code

**Files to Modify**: `docs/evidence-contract.md`

---

### Task 8.4: Update the other docs and CHANGELOG
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 2
**Objective**: Correct the stale line and record the change.

**Steps**:
- [ ] `docs/inbox-contract.md`: correct the line "Slice 104 adds verdict and judge-sample kinds" (judge samples use the `verdict` kind with the optional `judge_invocation_id` key; document the key and D2's rejection reason)
- [ ] `docs/store-contract.md`: new schema version, the new column and two tables, the new Store methods
- [ ] `CHANGELOG.md`: add concise `Slice 107:` lines under `[Unreleased]` → Added, in the existing style (1–2 lines each)

**Success Criteria**:
- [ ] The stale line is gone; the three files are consistent with the code

**Files to Modify**: `docs/inbox-contract.md`, `docs/store-contract.md`, `CHANGELOG.md`

---

### Task 8.5: Final validation and walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 3
**Objective**: Confirm the slice against the LLD Success Criteria.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; all clean
- [ ] Check source file lengths for new and edited files; anything well over ~300 lines is split
- [ ] Run the LLD Verification Walkthrough steps 1–7 with a scratch `AMOEBA_STORE_DIR`; compare each result with the expected text in the LLD and note any difference for the PM
- [ ] Walk the LLD Functional and Technical Requirements lists and tick each against a named test
- [ ] Update the LLD's walkthrough section with captured output only if the PM asks

**Success Criteria**:
- [ ] Full suite, `ruff`, `pyright` clean; walkthrough output matches the LLD or differences are reported
- [ ] Committed on the slice branch (e.g. `docs: finalize slice 107 verification`). Do not merge; merging happens in Phase 7 after the code review
