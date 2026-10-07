---
docType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
lld: user/slices/105-slice.squadron-review-parser-and-ingest.md
dependencies: [101, 103, 104]
projectState: Slices 101–104 are merged. The store holds verdicts and content-keyed findings (schema 5), the inbox accepts a `verdict` kind, and `amoeba submit verdict` takes about twenty hand-typed flags. Nothing reads Squadron output. 104's tests read fixtures through a test-only helper, `tests/review_fixtures.py`. This slice adds the production parser, `verdict_to_payload`, and `amoeba ingest review`.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

Continuation of `105-tasks.squadron-review-parser-and-ingest-1.md`; read its Context Summary, branch, reading note, and section map first. This file covers **Sections 6–9** (payload inverse, test migration, the command, docs and final validation).

**Commit cadence and fixture paths:** as in file 1. An implementation task that says "committed with Task N.M" is committed together with its test task. Fixture path constants already exist in `tests/review_fixtures.py` (added by Tasks 1.1–1.3); tasks here add none.

---

## Section 6: The Payload Inverse

### Task 6.1: Implement `verdict_to_payload`
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 2
**Objective**: The inverse of `verdict_from_payload`, so ingest can submit a `VerdictInput` through the inbox.

**Steps**:
- [ ] Read `store/verdict_payload.py` first and reuse its key constants; define none
- [ ] Add `verdict_to_payload(verdict: VerdictInput) -> dict[str, object]` containing every `VERDICT_PAYLOAD_KEYS` key and no other; findings are lists of mappings with exactly `FINDING_PAYLOAD_KEYS`; enums by value; `None` stays `None`
- [ ] If the file would pass ~300 lines (it is 213 now), keep the function compact or place it beside its inverse using a shared helper

**Success Criteria**:
- [ ] `verdict_from_payload(v.id, verdict_to_payload(v)) == v` for the cases in Task 6.2
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/store/verdict_payload.py`

---

### Task 6.2: Test the round trip
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: Pin the inverse over every field.

**Steps**:
- [ ] Add tests under `tests/store/` (new module or beside existing payload tests): round trip a fully populated `VerdictInput`; one with every optional field `None`; one with several findings including null `category` and `location`
- [ ] Assert the payload key set equals `VERDICT_PAYLOAD_KEYS` exactly and each finding's key set equals `FINDING_PAYLOAD_KEYS`
- [ ] Round trip a `VerdictInput` composed by `to_verdict_input` from a real fixture

**Success Criteria**:
- [ ] All pass; `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(store): add verdict_to_payload`

**Files to Create**: `tests/store/test_verdict_to_payload.py` (or extend the existing payload test module)

---

## Section 7: Migrate 104's Fixture Tests onto the Parser

### Task 7.1: Switch `tests/store/test_finding_identity.py` to the parser
**Owner**: Junior AI
**Dependencies**: Task 5.4 (needs `parse_review_artifact`; independent of Section 6)
**Effort**: 2
**Objective**: 104's matching-rule tests read what production reads (LLD Value and Technical Requirements).

**Steps**:
- [ ] Read the file fully, then replace its `review_findings` / `read_frontmatter` / `has_provider_failure_heading` uses with `parse_review_artifact` on the fixture text and `ParsedReview` fields
- [ ] Where it builds a `VerdictInput` from a fixture, use `to_verdict_input` with an explicit `upstream_version` for pre-stamp files
- [ ] Keep every expected value unchanged. If an assertion fails, report the difference to the PM rather than changing it

**Success Criteria**:
- [ ] `uv run pytest tests/store/test_finding_identity.py` passes with no expected-value changes
- [ ] The file no longer imports `read_frontmatter`, `review_findings`, `CapturedFinding`, or `has_provider_failure_heading`
- [ ] Commit, e.g. `test: read finding-identity fixtures through the parser`

**Files to Modify**: `tests/store/test_finding_identity.py`

---

### Task 7.2: Switch `tests/store/test_finding_changes.py` to the parser
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 2
**Objective**: Same migration for the `finding_changes` tests.

**Steps**:
- [ ] Apply the same replacement and rules as Task 7.1 to this file; it imports `ROUND_1_PART_1`, `ROUND_2_PART_1`, `ROUND_2_PART_2`

**Success Criteria**:
- [ ] `uv run pytest tests/store/test_finding_changes.py` passes with no expected-value changes
- [ ] No import of the four removed helpers
- [ ] Commit, e.g. `test: read finding-changes fixtures through the parser`

**Files to Modify**: `tests/store/test_finding_changes.py`

---

### Task 7.3: Switch `tests/evidence_harness.py` to the parser
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 2
**Objective**: Same migration for the shared evidence harness, which other tests import.

**Steps**:
- [ ] Apply the same replacement and rules as Task 7.1 to this file
- [ ] Run every test module that imports it (`grep -rn evidence_harness tests`), not just one

**Success Criteria**:
- [ ] All tests importing the harness pass with no expected-value changes
- [ ] No import of the four removed helpers
- [ ] Commit, e.g. `test: build evidence harness verdicts through the parser`

**Files to Modify**: `tests/evidence_harness.py`

---

### Task 7.4: Switch `tests/test_demo_evidence_payloads.py` to the parser
**Owner**: Junior AI
**Dependencies**: Task 6.2 (this test compares payloads, so it may use `verdict_to_payload`), Task 5.4
**Effort**: 2
**Objective**: Same migration for the demo payload test.

**Steps**:
- [ ] Apply the same replacement and rules as Task 7.1 to this file. It imports `SQ_REVIEWS` and `review_findings`
- [ ] Do not change `scripts/demo_evidence.py` or the payload files in `scripts/demo_evidence/`

**Success Criteria**:
- [ ] `uv run pytest tests/test_demo_evidence_payloads.py` passes with no expected-value changes
- [ ] No import of the four removed helpers
- [ ] Commit, e.g. `test: check demo payloads through the parser`

**Files to Modify**: `tests/test_demo_evidence_payloads.py`

---

### Task 7.5: Delete the old fixture reader
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 1
**Objective**: Remove the test-only parser; `tests/review_fixtures.py` keeps only fixture paths.

**Steps**:
- [ ] Confirm the four migration tasks above are committed, so nothing still imports the helpers (`grep -rn "review_findings\|read_frontmatter" tests`)
- [ ] Delete the YAML reader, frontmatter regex, heading regex, `CapturedFinding`, and the `yaml` and `re` imports from `tests/review_fixtures.py`. Keep `SQ_REVIEWS` and the four `ROUND_*` paths
- [ ] Update the module docstring to say it holds paths only
- [ ] Run the full suite once

**Success Criteria**:
- [ ] `grep -n "yaml\|re\.compile" tests/review_fixtures.py` finds nothing
- [ ] `uv run pytest`, `ruff`, and `pyright` clean
- [ ] Commit, e.g. `refactor(tests): reduce review_fixtures to fixture paths`

**Files to Modify**: `tests/review_fixtures.py`

---

## Section 8: The `amoeba ingest review` Command

### Task 8.1: Add `ExitCode.REVIEW_UNREADABLE`
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 1
**Objective**: A distinct exit status (`12`) for unreadable reviews.

**Steps**:
- [ ] Read the end of `ExitCode` in `cli/main.py` and add `REVIEW_UNREADABLE = 12` with a doc comment in the existing style: file unreadable, unparseable, or no version label
- [ ] Update any test that pins the full exit-code set (search `tests/` for `ExitCode`)

**Success Criteria**:
- [ ] No bare `12` appears in `src/`; the enum test (if any) passes; `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/cli/main.py`, the exit-code test if one exists

---

### Task 8.2: Implement `cli/ingest.py` and register it
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 4
**Objective**: Parse a file and submit it through the inbox, per the LLD Data Flow and D6/D7.

**Steps**:
- [ ] Read `cli/submit.py` first and follow its parser and boundary conventions, including how it resolves the supervisor directory and reports the submission id
- [ ] Add `add_ingest_parser` and `run_ingest` for `amoeba ingest review --project ID --node NODE_ID --by NAME (--artifact PATH | --stdout-json PATH) [--upstream-version LABEL] [--id ID]`. `--artifact` and `--stdout-json` are mutually exclusive and one is required
- [ ] Order of steps, each failure leaving `inbox/new/` empty: (1) the project's store file (`paths.store_path(project)`) must exist, else print `no store for project '<P>'` and return `SUBMISSION_REFUSED` without opening a store; (2) read the file as UTF-8, `OSError` / `UnicodeDecodeError` → `REVIEW_UNREADABLE`; (3) parse by the chosen flag, `SquadronReviewError` → `REVIEW_UNREADABLE`; (4) `to_verdict_input` with the absolute resolved path as `source_path`, `--id` as `record_id`, `--upstream-version` as the label; `UpstreamVersionError` → `REVIEW_UNREADABLE`; (5) print node, parsed `slice` (`-` if none), and review type on stderr; (6) `submit` with kind `verdict`, `verdict_to_payload(...)`, and `submission_id` = the input's id; (7) print the submission id on stdout, return `OK`
- [ ] Catch `OSError`, `UnicodeDecodeError`, and `SquadronReviewError` in explicit branches only; print the error on stderr. Never catch plain `ValueError` or add a broad `except`. `InboxSubmitError` is left to the boundary handler
- [ ] Do not compare `--node` with the review's `slice` (D7)
- [ ] Register in `cli/main.py` next to `add_submit_parser`

**Success Criteria**:
- [ ] `amoeba ingest review --help` lists every flag
- [ ] No store is opened by the command (no `Store` import in `ingest.py`)
- [ ] `ruff` and `pyright` clean (committed with Task 8.3)

**Files to Create**: `src/amoeba/cli/ingest.py`
**Files to Modify**: `src/amoeba/cli/main.py`

---

### Task 8.3: Test the command with no process running
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 3
**Objective**: Pin ingest's argument handling and failure paths.

**Steps**:
- [ ] Read `tests/cli/test_submit.py` and `tests/cli_harness.py` and reuse their helpers; use a throwaway supervisor directory, never the real one
- [ ] Create `tests/cli/test_ingest.py` with a fixture that makes the "store exists" precondition the way 104's end-to-end test does: in a `tmp_path` supervisor directory, `start_running`, `submit_cli` a `create-project` for project `demo`, `await_condition` until `paths.store_path("demo", env)` exists (use `cli_environment` for `env`), then `stop_running`. The project then has a real store file and the process is stopped. The "no project" case never creates one
- [ ] Failure paths (all with the fixture above, process stopped), each asserting the exit code and an empty `inbox/new/`: missing file, non-UTF-8 file, `# not a review` text (message mentions no frontmatter), a pre-stamp file with no `--upstream-version`, stamp/argument disagreement, project with no store file (`SUBMISSION_REFUSED`, message names the project)
- [ ] Success path, process stopped: a real fixture with `--upstream-version` writes exactly one file to `inbox/new/`; stdout is the digest id; stderr names the node, slice, and review type; `--stdout-json` works on a capture; both flags together or neither is an argument error
- [ ] D7: a review whose `slice` differs from any node's slice name is still submitted
- [ ] `--id` overrides the digest id

**Success Criteria**:
- [ ] `uv run pytest tests/cli/test_ingest.py` passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(cli): add amoeba ingest review`

**Files to Create**: `tests/cli/test_ingest.py`

---

### Task 8.4: End to end, running process, two rounds and a provider failure
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 3
**Objective**: Prove the LLD's main Integration Requirement with real subprocesses.

**Steps**:
- [ ] Create `tests/cli/test_ingest_end_to_end.py`, modelled on `tests/cli/test_evidence_end_to_end.py`: from an empty supervisor directory, start, create the project, stop, seed a node with `scripts/demo_evidence.py`, start
- [ ] Ingest round 1 part 1, round 2 part 1 (`102-…part-1.md`), and the round 2 part 2 provider-failure file, each with `--upstream-version` (all three predate the stamp). Ingest round 1 again from a different path, a copy with a `resolution:` key added
- [ ] `kill -9` the process; start again
- [ ] Read-only inspection shows exactly three verdicts with the expected standings (`stated`, `stated`, `provider_failure`), round 1's `source_path` is the first ingest's absolute path, `source` is `artifact_frontmatter`, and `inspect changes` on round 2 names round 1 as previous with every round-1 finding `gone`

**Success Criteria**:
- [ ] The test passes and leaves no stray processes or files outside `tmp_path`; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: end-to-end review ingest with a running process`

**Files to Create**: `tests/cli/test_ingest_end_to_end.py`

---

### Task 8.5: End to end, stopped process and unknown project
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 2
**Objective**: Cover D6 with the process both stopped and running.

**Steps**:
- [ ] In the same test module, with the same setup as Task 8.4: ingest with the process **stopped**, then start it; the verdict is applied and appears in `inspect verdicts`
- [ ] Ingest into the nonexistent project `nosuch`, once with the process running and once stopped: exit `SUBMISSION_REFUSED`, stderr names the project, `inbox/new/` stays empty, and `inspect inbox` shows nothing quarantined

**Success Criteria**:
- [ ] Both tests pass; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: ingest with a stopped process and an unknown project`

**Files to Modify**: `tests/cli/test_ingest_end_to_end.py`

---

### Task 8.6: End to end, stdout JSON against the saved file
**Owner**: Junior AI
**Dependencies**: Task 8.5
**Effort**: 2
**Objective**: Pin D5's accepted consequence on the real 0.15.0 pair.

**Steps**:
- [ ] With a running process and a seeded node, ingest the pair's stdout file with `--stdout-json` and its saved `.md` with `--artifact` (no `--upstream-version`; both carry a stamp)
- [ ] Assert two different ids; the JSON row has `source: stdout_json` and `reviewed_sha` null; `inspect findings` for the node shows each of the pair's finding keys seen twice

**Success Criteria**:
- [ ] The test passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: ingest a stdout capture and its saved file`

**Files to Modify**: `tests/cli/test_ingest_end_to_end.py`

---

## Section 9: Documentation and Final Validation

### Task 9.1: Write the "Parsing Squadron output" section
**Owner**: Junior AI
**Dependencies**: Task 8.6
**Effort**: 3
**Objective**: Replace 104's "Mapping Squadron's flags (for slice 105)" notes with the parser's contract.

**Steps**:
- [ ] In `docs/evidence-contract.md`, replace the subsection "Mapping Squadron's flags (for slice 105)" with "Parsing Squadron output", covering: the D3 table, D4 (version rule), D5 (what changes an id; the consequence of ingesting both a file and its stdout, namely two records and doubled counts; the rule to ingest the file whenever it exists), D7, the dropped keys, and the dated observation (20260928, squadron `373217ab`, 0.15.0, labelled as an observation not a version pin)
- [ ] Fix any other references in the repo to the removed subsection title (grep `docs/` and `project-documents/user/`, excluding the LLD itself)
- [ ] Do not copy long passages from the LLD; summarize and link by section name

**Success Criteria**:
- [ ] The old subsection title no longer appears in `docs/`
- [ ] The new section covers each item above
- [ ] Commit, e.g. `docs: add parsing squadron output to the evidence contract`

**Files to Modify**: `docs/evidence-contract.md`

---

### Task 9.2: Update the process contract and CHANGELOG
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 2
**Objective**: Document the command, the exit code, and the slice.

**Steps**:
- [ ] In `docs/process-contract.md` (section "The CLI"), add `amoeba ingest review` with its flags and outputs, and exit code 12 with its cause; note that it submits and does not wait, and refuses a project with no store (D6), with the outcome table location (`inspect submissions`, `inspect inbox`)
- [ ] Add a `CHANGELOG.md` entry under `[Unreleased]` / `Added` in the existing style, one to two lines each: the parser package, `ingest review` and exit code 12, `verdict_to_payload` and `provider_failure_problem`, PyYAML now a runtime dependency, and the digest format tag as a contract

**Success Criteria**:
- [ ] Both documents mention `ingest review` and exit code 12
- [ ] Commit, e.g. `docs: document ingest review and update changelog`

**Files to Modify**: `docs/process-contract.md`, `CHANGELOG.md`

---

### Task 9.3: Final validation and the walkthrough
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 2
**Objective**: Run everything and replace the LLD's draft walkthrough note with real output.

**Steps**:
- [ ] `uv run ruff check .`, `uv run pyright`, `uv run pytest`, and `uv run pytest tests/load` all clean (the slice has no performance requirement and adds no load test; this run only checks for regressions)
- [ ] `wc -l` the new source files; split any well over ~300 lines
- [ ] Run the LLD's Verification Walkthrough steps 1–9 by hand (with the real filenames for the captured pair) and replace its draft note with the real commands and trimmed output
- [ ] If any step does not behave as the LLD says, stop and report to the PM; do not edit the LLD to match

**Success Criteria**:
- [ ] All four checks clean (the import rules are enforced by Task 5.5's test)
- [ ] The walkthrough in the LLD shows real output
- [ ] Commit on the slice branch, e.g. `docs: record slice 105 verification walkthrough`

**Files to Modify**: `project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md`
