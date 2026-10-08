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
- **Migration number:** use the number N recorded in Task 1.1 wherever a migration is named.
- **Order if slice 105 is not merged:** only Section 6 and Tasks 8.3–8.5 (the end-to-end tests) need 105. Sections 5 and 7 and Tasks 8.1–8.2 do not, so run those first and return to Section 6, then 8.3–8.5, then 8.6–8.10. If 105 is merged, run the sections in numeric order.
- **Coverage of file 1's criteria:** judge samples, D2, D3, the filter, and `calibration` are owned by Tasks 4.1–4.12 (file 1); the migration and upgrade test by Tasks 3.1–3.2; `check_standing` and `summarize_judge_samples` by Tasks 2.1–2.4. Task 8.9 re-checks them all against the LLD.
- **Coverage of this file's criteria:** checks and work records: Tasks 5.1–5.7; parser and ingest id and judge fixtures: Tasks 6.1–6.6; listings: Tasks 7.1–7.6; demo script: Tasks 8.1–8.2; end-to-end behavior and crash recovery: Tasks 8.3–8.5; docs: Tasks 8.6–8.7; walkthrough: Task 8.10; widened metrology test: Task 8.8; final validation and requirements trace: Task 8.9.

---

## Section 5: Checks and Work Records

### Task 5.1: Add `mapping_checks.py`
**Owner**: Junior AI
**Dependencies**: Task 3.2
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
- [ ] `ruff` and `pyright` clean; the only change to `store.py` is the base class and its import. If the file is then clearly over ~300 lines, report it to the PM rather than refactoring here

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
- [ ] A node that exists but belongs to another project raises `NodeNotFoundError`
- [ ] `check(check_id)` returns the record with computed standing; an unknown id returns `None`
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
- [ ] Content that is a list, string, or not serializable is rejected; unknown node, a node in another project (`NodeNotFoundError`), and empty `upstream_version` are rejected
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

**Success Criteria**:
- [ ] Full suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat(store): export check, work-record, and calibration API`

**Files to Modify**: `src/amoeba/store/__init__.py`, `tests/test_public_api.py`

---

## Section 6: Parser, Ingest, and Fixtures

*Requires slice 105. If Task 1.1 found `upstream/squadron/review.py` missing, skip to Section 7, then Tasks 8.1–8.2, and ask the PM before returning here.*

*Task 6.2 is where this section's tests for `to_verdict_input` and the `verdict_to_payload` round trip live; they modify 105's test modules, so name the modules in the commit.*

### Task 6.1: Pass `judge_invocation_id` through `to_verdict_input` and `verdict_to_payload`
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 2
**Objective**: 105's parser and its payload inverse carry the id (LLD "105's parser").

**Steps**:
- [ ] In `src/amoeba/upstream/squadron/review.py`, add a `judge_invocation_id: str | None = None` keyword to `to_verdict_input` and set it on the `VerdictInput`. It must **not** enter `review_record_id` (LLD D1: one file is one sample)
- [ ] In `src/amoeba/store/verdict_payload.py`, make `verdict_to_payload` emit `VERDICT_JUDGE_INVOCATION_ID` when the id is set, and omit the key when `None` only if the Task 1.1 notes say `verdict_to_payload` did not exist when Task 4.3 ran; if it existed, Task 4.3 already did this, so only confirm it
- [ ] No tests here; Task 6.2 owns them

**Success Criteria**:
- [ ] Existing 105 tests pass; `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`, `src/amoeba/store/verdict_payload.py`

---

### Task 6.2: Test the parser changes
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 1
**Objective**: Pin the id's pass-through and its absence from the record id.

**Steps**:
- [ ] Add tests next to 105's `to_verdict_input` tests: id set on the result; absent id is `None`; record id identical with and without an id
- [ ] Extend 105's round-trip test (`verdict_to_payload` then `verdict_from_payload`): a record with an id keeps it; a record without one produces a payload without the key
- [ ] The same file converted with two different ids has the same record id

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
- [ ] Capture one fresh judge file: run `sq review` on a judge template with `--model glmflash` in a throwaway copy of this repository, never in this working tree. Copy the saved file byte for byte. If `sq` or its provider key is unavailable, stop this task and ask the PM whether to proceed with the 302 file only. Record the PM's answer under "Fresh judge fixture decision" in the Task 1.1 notes (file 1). Tasks 6.4 onward do not start until that line is filled in; Task 8.9 checks it Likewise, if the 302 file cannot be found, ask the PM for its path and do not recreate it
- [ ] Add README entries for both in `tests/fixtures/README.md` in the existing style: capture date, source, exact command for the fresh file, and what each pins. Record Squadron's version only as a dated observation
- [ ] Check each file with a read-only look: `score` and a `criteria` mapping present; no `verdictSource` key; the 302 file has no stamp

**Success Criteria**:
- [ ] Each copied file is byte-identical to its source and has a README entry; the 302 file is present, and the fresh file is present or the PM's decision to go without it is recorded in the Task 1.1 notes
- [ ] No assumption about the fresh file's content is made before it is read

**Files to Create/Modify**: two files in `tests/fixtures/sq_reviews/`, `tests/fixtures/README.md`

---

### Task 6.4: Test the parser against the judge fixtures
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 2
**Objective**: Real input, per project parsing rules.

**Steps**:
- [ ] For each judge fixture present: `parse_review_artifact` then `to_verdict_input(..., judge_invocation_id="j1")` gives a sample with `score` and `criteria` from the file, `derivation` `not_reported`, and `standing` `unattested`
- [ ] For each fixture, read `score`, `reviewType`, and the verdict from the file's own frontmatter (`read_frontmatter` in `tests/review_fixtures.py`) and assert the parsed sample equals what the file says. Do not type expected values into the test
- [ ] The 302 file's `reviewType` starts with `judge.`; report to the PM if the file's score or verdict differs from the LLD walkthrough's step 1 and 3 text

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
**Dependencies**: Task 5.7
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
- [ ] Works against a stopped process (read-only handle) **and** against a running one (start via `tests/cli_harness.py` as the existing `inspect` tests do)

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
- [ ] In the same task, update the pinned `LISTINGS` registry test (`tests/test_cli_inspect.py` or wherever the names are pinned) to include `calibration`, so the suite is green at this commit

**Success Criteria**:
- [ ] `ruff` and `pyright` clean; the registry test passes

**Files to Modify**: `cli/inspect_evidence.py`, `cli/inspect.py`, registry test

---

### Task 7.4: Test `inspect calibration`
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Columns, JSON extras, and read-only behavior.

**Steps**:
- [ ] Seed a store with the Task 4.12 set; table output has the exact column header and expected counts
- [ ] `--json` rows carry `by_standing` and `scored`; unscored groups show `null` scores
- [ ] Runs with the process stopped and with it running; an unknown project follows the existing listing behavior

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
- [ ] Update the pinned registry test (the one Task 7.3 updated) to add `checks` and `work-records`

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
- [ ] Both work with the process stopped and with it running (same harness as Task 7.2)

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
- [ ] Add `demo_checks.py` to `PERMITTED_SCRIPTS` and to the set asserted in `tests/test_writer_guard.py` that already names `demo_evidence.py` (search for it; do not rely on a line number); update the explanatory comment
- [ ] Use fixed record ids so a re-run is a first-wins no-op; log nothing to stdout besides the id

**Success Criteria**:
- [ ] The writer-guard test passes with the new script named
- [ ] Running the script against a scratch store prints exactly one node id; `ruff` and `pyright` clean

**Files to Create/Modify**: `scripts/demo_checks.py`, `tests/test_writer_guard.py`

---

### Task 8.2: Test `scripts/demo_checks.py`
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 2
**Objective**: The walkthrough's seeding script is itself tested.

**Steps**:
- [ ] Follow `tests/test_demo_evidence_payloads.py` and the existing demo-script subprocess tests: create `tests/test_demo_checks.py`
- [ ] Run the script as a subprocess against a scratch `AMOEBA_STORE_DIR` seeded with a project and a node; assert stdout is exactly one node id, and that id is a second node in the same project
- [ ] Open the store afterward: three checks on the first node with standings `passed`, `vacuous`, `unattested`, and one `task_progress` record
- [ ] Re-running the script leaves the same rows (first wins)
- [ ] The script refuses (non-zero exit) while the instance lock is held

**Success Criteria**:
- [ ] Tests pass; `ruff` and `pyright` clean
- [ ] Commit with Task 8.1, e.g. `feat: add demo_checks seeding script`

**Files to Create**: `tests/test_demo_checks.py`

---

### Task 8.3: End-to-end scenario fixture and the sample/rejection test
**Owner**: Junior AI
**Dependencies**: Task 6.6, Task 7.6, Task 8.2
**Effort**: 3
**Objective**: Build the LLD "Integration Requirements" scenario once, as a reusable fixture, and prove samples and the D2 rejection through the real CLI.

**Steps**:
- [ ] Create `tests/cli/test_judge_end_to_end.py` modeled on `tests/cli/test_evidence_end_to_end.py` (scratch `AMOEBA_STORE_DIR`, empty `--sq-runs-dir`, wait for `running`)
- [ ] Define a **function-scoped** fixture `judge_scenario` in that file: create a project, stop, seed a node with `demo_evidence.py` and a second node with `demo_checks.py`, start; ingest the 302 fixture as a sample of `j1`; submit two built `j1` samples with other models via `amoeba submit verdict --judge-invocation-id j1` (one CONCERNS); submit one `j1` sample on the second node; then wait until settled. It yields the running instance and tears it down (no leftover processes). Each test below gets its own instance and captures what it needs itself; no test depends on another's state
- [ ] **Wait until settled:** poll `amoeba inspect submissions --project ... --json` until every submission is `applied` or `rejected` (bounded timeout, then fail the test); do not use a fixed sleep
- [ ] Test `test_samples_and_rejection`: three `j1` samples in `inspect verdicts --judge-invocation-id j1`; exactly one `rejected` submission, whose reason names the invocation and its node

**Success Criteria**:
- [ ] Test passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: add judge end-to-end scenario and sample rejection proof`

---

### Task 8.4: End-to-end test, calibration, checks, and work-record listings
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 2
**Objective**: The remaining listings show the right rows on the running scenario.

**Steps**:
- [ ] In the same file, add `test_listings` using `judge_scenario`: `calibration` shows `split_invocations` 1 in every row `j1` touches; `checks` shows `passed`, `vacuous`, `unattested`; `work-records` shows the `task_progress` record

**Success Criteria**:
- [ ] Test passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: add judge end-to-end listing proof`

---

### Task 8.5: End-to-end test, crash and restart
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 2
**Objective**: Every listing returns the same rows after `kill -9`, with nothing applied twice.

**Steps**:
- [ ] In the same file, add `test_crash_and_restart` using `judge_scenario`: first capture the `--json` output of `verdicts` (filtered to `j1`), `submissions`, `calibration`, `checks`, and `work-records`
- [ ] `kill -9` the process, start it again, wait for `running`; re-read every listing with `--json` and assert equality with the captured output (row counts, ids, standings, rejection reason)
- [ ] Stop the process and read again (a read-only handle); assert the same rows

**Success Criteria**:
- [ ] Test passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: add judge end-to-end crash recovery proof`

---

### Task 8.6: Update `docs/evidence-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 8.5
**Effort**: 3
**Objective**: Document the contract (LLD Technical Requirements, last bullet).

**Steps**:
- [ ] Add sections: the D1 names (judge invocation, judge sample, review verdict); D2; D3; D4 (the fields, the overcount note for `split_invocations`, and what the report does not do: no thresholds, no agreement rate, no writes to Squadron); the check standing table; D6's mapping of SQ 280's four types; the judge-standing observation (why a judge sample reads `unattested`, one paragraph, as a dated observation without version pins)
- [ ] Document `RecordSource`'s two new members, the new Store methods, the inbox key, and the CLI listings
- [ ] Frontmatter stays valid per `file-naming-conventions`; update `dateUpdated`

**Success Criteria**:
- [ ] Each LLD-required topic has a heading or paragraph; no statement contradicts the LLD or the code
- [ ] Commit, e.g. `docs: document judge samples, calibration, checks, and work records`

**Files to Modify**: `docs/evidence-contract.md`

---

### Task 8.7: Update the other docs and CHANGELOG
**Owner**: Junior AI
**Dependencies**: Task 8.6
**Effort**: 2
**Objective**: Correct the stale line and record the change.

**Steps**:
- [ ] `docs/inbox-contract.md`: correct the line "Slice 104 adds verdict and judge-sample kinds" (judge samples use the `verdict` kind with the optional `judge_invocation_id` key; document the key and D2's rejection reason)
- [ ] `docs/store-contract.md`: new schema version, the new column and two tables, the new Store methods
- [ ] `CHANGELOG.md`: add concise `Slice 107:` lines under `[Unreleased]` → Added, in the existing style (1–2 lines each)

**Success Criteria**:
- [ ] The stale line is gone; the three files are consistent with the code
- [ ] Commit, e.g. `docs: update inbox and store contracts and changelog for slice 107`

**Files to Modify**: `docs/inbox-contract.md`, `docs/store-contract.md`, `CHANGELOG.md`

---

### Task 8.8: Widen the metrology-reference test
**Owner**: Junior AI
**Dependencies**: Task 8.7
**Effort**: 1
**Objective**: One change, covering every new or edited module.

**Steps**:
- [ ] Widen 104's metrology-reference test (the one place for this change), if it does not already scan all of `src/amoeba/`, to cover `store/check_models.py`, `calibration.py`, `checks.py`, `sql_checks.py`, `mapping_checks.py`, and `cli/inspect_evidence.py`, `cli/inspect_checks.py`, `cli/ingest.py`
- [ ] Check source file lengths for new and edited files; anything well over ~300 lines is reported to the PM

**Success Criteria**:
- [ ] The test passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: extend metrology-reference scan to slice 107 modules`

---

### Task 8.9: Final validation and requirements trace
**Owner**: Junior AI
**Dependencies**: Task 8.8
**Effort**: 2
**Objective**: Confirm the suite and trace the LLD requirements to tests.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; all clean
- [ ] Check "Fresh judge fixture decision" in the Task 1.1 notes (file 1): the fresh fixture exists with its README entry, or the PM's decision to go without it is recorded; otherwise report it to the PM as an open item
- [ ] Walk the LLD Functional and Technical Requirements lists and tick each against a named test

**Success Criteria**:
- [ ] Full suite, `ruff`, `pyright` clean; every requirement names a test, or the gap is reported
- [ ] No commit needed unless a gap fix is made

---

### Task 8.10: Run the LLD verification walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.9
**Effort**: 2
**Objective**: Run the walkthrough by hand and report differences.

**Steps**:
- [ ] Run the LLD Verification Walkthrough steps 1–7 with a scratch `AMOEBA_STORE_DIR`. The LLD's commands are not trusted as written: before each step, check its flags against `--help` (it mixes `--node` and `--node-id`, step 4 says "as in step 2" without naming the model, step 1 names a `--json` listing without the id filter, and step 3 names a "minimax" row whose model comes from the fixture file). Use the real flags and the model read from the fixture's frontmatter, compare each result with the LLD's expected text, and list every command or expectation that differed for the PM
- [ ] Update the LLD's walkthrough section with captured output only if the PM asks

**Success Criteria**:
- [ ] Walkthrough output matches the LLD or differences are reported
- [ ] Committed on the slice branch (e.g. `docs: finalize slice 107 verification`). Do not merge; merging happens in Phase 7 after the code review
