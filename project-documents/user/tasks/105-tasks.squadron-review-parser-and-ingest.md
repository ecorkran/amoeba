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

- Working on the **squadron-review-parser-and-ingest** slice (105), the fifth slice of initiative 100.
- **Current state:** `VerdictInput`, `FindingInput`, `parse_verdict`, `parse_severity`, `verdict_from_payload` and the `VERDICT_*` / `FINDING_*` key constants exist (`store/evidence_models.py`, `store/verdict_payload.py`). The provider-failure rule is two inline branches in `store/_verdict_writer.py`. `ExitCode` lives in `cli/main.py`; `submit()` and `InboxSubmitError` are in `amoeba.inbox`. PyYAML is a dev dependency only.
- **Dependencies:** 101 (`store.paths`), 103 (`submit()`, D2 replay no-op), 104 (verdict contract). Read through their documented contracts.
- **What this slice delivers:** `amoeba.upstream.squadron` (pure parser, `ParsedReview`, `to_verdict_input`, `review_record_id`, three errors), `review_fields.py`, `verdict_to_payload`, `provider_failure_problem`, `amoeba ingest review` with `ExitCode.REVIEW_UNREADABLE`, new real fixtures, migration of 104's fixture-reading tests onto the parser, PyYAML as a runtime dependency, and docs.
- **Not in this slice:** `source_document` on `VerdictInput` (106), judge samples (107), detecting reviews on disk (106), store schema changes, checking `--node` against the review's `slice`.
- **Next planned slice:** 106 (detection), which calls this parser in-process.

**Branch:** all implementation happens on `105-slice.squadron-review-parser-and-ingest`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/105-slice.squadron-review-parser-and-ingest.md` at the named section (D3 table, D4, D5, D6, D7, API Contracts). Exact signatures and messages are settled against that design. Keep every new source file near 300 lines.

**Ordering note:** the LLD's step 8 moves PyYAML to runtime last. The parser imports `yaml`, so this file moves it in Task 2.1, before any parser code.

**Section map:** 1 fixtures; 2 shared rule and fields; 3 file reader; 4 stdout reader; 5 composition; 6 payload inverse; 7 test migration; 8 command; 9 docs and final validation.

---

## Section 1: Fixtures

### Task 1.1: Copy the four existing real review files
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Put real inputs in place before any code that is tested against them.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root and create the branch `105-slice.squadron-review-parser-and-ingest` from the target
- [ ] Copy byte for byte with `cp` into `tests/fixtures/sq_reviews/`:
  - From Squadron's `project-documents/user/reviews/archive/` (repo at `../squadron`): `928-review.slice.codex-parity-for-skill-packs-and-provider-access.20260927T212759.md` and `925-review.code.command-install-target-parity-codex-via-the-agents-skill-layout.20260922T145229.md`
  - From Squadron's `project-documents/user/reviews/`: `github.com-ecorkran-squadron-116-review.code.md`
  - From this repo's `project-documents/user/reviews/archive/`: `106-review.slice.outbound-change-feed-and-detection-of-external-work.20260928T175751.md`
- [ ] Before copying each, grep it for `^resolution:`, `^resolvedBy:` and `^## Response`. If any hit, leave the file out and stop to tell the PM
- [ ] Check each file's frontmatter against the LLD's fixture list: 928 has `providerFailure: true` and `runId`; 925 has the *Findings Not Parsed* heading and verdict `UNKNOWN`; the PR file has a nested `pr:` and no `slice`; 106 has `runId` and `squadronVersion`. If any differs, stop and ask the PM
- [ ] Add one README entry per file in `tests/fixtures/README.md` (existing table style): file, verdict, capture date, origin, why it is here. Extend the scan note to say the four files come from another repository, contain review text about Squadron code, and no secrets

**Success Criteria**:
- [ ] `diff` of each copied file against its source is empty
- [ ] The README names all four files with date, origin, and reason
- [ ] No copied file contains `resolution`, `resolvedBy`, or a `## Response` section
- [ ] Commit, e.g. `test: add real squadron review fixtures for slice 105`

**Files to Create**: four files in `tests/fixtures/sq_reviews/`
**Files to Modify**: `tests/fixtures/README.md`

---

### Task 1.2: Capture the 0.15.0 file and stdout pair
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 3
**Objective**: Record one real review as both a saved file and its stdout JSON, so file/stdout equality is tested on real output.

**Steps**:
- [ ] Make a throwaway copy of this repo outside the working tree (`mktemp -d`). Never run the review in the real repo, so nothing lands in the real `reviews/` directory
- [ ] In the copy, run `sq review` for a slice, **with a slice number** (so Squadron saves a file), `--model glmflash --output json`, redirecting stdout and stderr to separate files. Run `sq --version` and record it
- [ ] Confirm the stdout file is one JSON object (parses with `python -m json.tool`) and the `Saved review to` line is in the stderr file, not stdout
- [ ] Confirm the saved review file has no hand edits and that `template_name` in the JSON equals `reviewType` in the frontmatter
- [ ] Copy the saved file and the stdout file into `tests/fixtures/sq_reviews/` with `cp`. Name them so the pair is obvious (e.g. same stem; stdout ends `.stdout.json`)
- [ ] Add a README entry: command, Squadron version, model, capture date, why (pins pure-JSON stdout, `template_name == reviewType`, matching finding keys)
- [ ] If `sq` is unavailable, a provider key is missing, or the stdout is not pure JSON, **stop and ask the PM**. Do not hand-build a pair

**Success Criteria**:
- [ ] Both files exist, are unmodified Squadron output, and are listed in the README with the exact command
- [ ] The stdout file parses as a single JSON object
- [ ] The real `project-documents/user/reviews/` directory gained no files (`git status`)
- [ ] Commit, e.g. `test: capture squadron 0.15.0 review file and stdout pair`

**Files to Create**: two files in `tests/fixtures/sq_reviews/`
**Files to Modify**: `tests/fixtures/README.md`

---

## Section 2: Shared Rule, Field Names, and Dependency

### Task 2.1: Move PyYAML to a runtime dependency
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 1
**Objective**: The parser imports `yaml`, so it must be a runtime dependency (LLD D2).

**Steps**:
- [ ] Move `pyyaml` from the `dev` group to `[project] dependencies` in `pyproject.toml`; keep `types-pyyaml` in `dev`
- [ ] Refresh the lock file with `uv`

**Success Criteria**:
- [ ] `pyyaml` appears under runtime dependencies and `types-pyyaml` under dev only
- [ ] `uv run python -c "import yaml"` works; `uv run pytest` still passes
- [ ] Commit, e.g. `package: make pyyaml a runtime dependency`

**Files to Modify**: `pyproject.toml`, `uv.lock`

---

### Task 2.2: Extract `provider_failure_problem`
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: One definition of the provider-failure rule, shared by the store writer and the parser (LLD D3, first rule). Refactor only; no behavior change.

**Steps**:
- [ ] Add `provider_failure_problem(*, provider_failure, verdict, findings) -> str | None` to `store/evidence_models.py`. It returns the rejection reason or `None`. Reuse the existing two message texts exactly
- [ ] Replace the two inline branches in `_verdict_writer.py::_verdict_rejection` with a call to it, returning its reason as a `VerdictRejection`
- [ ] Do not change any existing test

**Success Criteria**:
- [ ] The provider-failure message texts appear once in `src/` (in `evidence_models.py`)
- [ ] 104's existing rejection tests pass unchanged
- [ ] `uv run ruff check .` and `uv run pyright` clean
- [ ] Commit, e.g. `refactor(store): extract provider_failure_problem`

**Files to Modify**: `src/amoeba/store/evidence_models.py`, `src/amoeba/store/_verdict_writer.py`

---

### Task 2.3: Test `provider_failure_problem` directly
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 1
**Objective**: Pin the pure function, which the parser will now also depend on.

**Steps**:
- [ ] Add a small test module under `tests/store/`: non-failure returns `None`; failure with `UNKNOWN` and no findings returns `None`; failure with another verdict returns the verdict reason; failure with findings returns the findings reason

**Success Criteria**:
- [ ] The four cases pass
- [ ] Commit, e.g. `test(store): pin provider_failure_problem`

**Files to Create**: `tests/store/test_provider_failure_problem.py`

---

### Task 2.4: Create the `amoeba.upstream.squadron` package and `review_fields.py`
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 2
**Objective**: Define every Squadron key name and literal once (LLD Technical Requirements).

**Steps**:
- [ ] Create `src/amoeba/upstream/__init__.py` and `src/amoeba/upstream/squadron/__init__.py` (re-exports are added in later tasks)
- [ ] Create `review_fields.py` with named constants for: every stdout JSON key the D3 table reads; every review-file frontmatter key it reads (including the nested finding keys); the two body headings (*Provider Failure*, *Findings Not Parsed*); the `squadron` upstream name; the digest format tag `parsed-review-v1`; the `stated` / `derived` derivation literals Squadron emits if the parser compares them
- [ ] Keys the parser deliberately drops (`location_verified`, `finding_scan`, `diff_chars`, `diff_chars_injected`, `answering_models`, `stop_reason`, `tools_given`) are **not** defined; a comment says they are dropped on purpose
- [ ] Import nothing outside the standard library and `amoeba.store.evidence_models`

**Success Criteria**:
- [ ] Each Squadron key appears as a string literal only in `review_fields.py` (check with grep once Section 3 is done)
- [ ] `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(upstream): add squadron review field names`

**Files to Create**: `src/amoeba/upstream/__init__.py`, `src/amoeba/upstream/squadron/__init__.py`, `src/amoeba/upstream/squadron/review_fields.py`

---

## Section 3: The Review-File Reader

### Task 3.1: Define `ParsedReview` and the errors
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 2
**Objective**: The typed value and error classes every reader returns or raises.

**Steps**:
- [ ] In `review.py`, define `ParsedReview` as a frozen, keyword-only dataclass with the fields listed in the LLD's API Contracts (review fields of `VerdictInput`, `findings: tuple[FindingInput, ...]`, `source: RecordSource`, `upstream_version`, `slice`, `source_document`)
- [ ] Define `SquadronReviewError(ValueError)`, `SquadronParseError(SquadronReviewError)` carrying a `source` and a message that names the key, and `UpstreamVersionError(SquadronReviewError)`
- [ ] Reuse `RecordSource` from the store; if it lacks `stdout_json` / `artifact_frontmatter` members, stop and ask the PM rather than adding strings

**Success Criteria**:
- [ ] `ParsedReview` is frozen and rejects positional construction
- [ ] `except ValueError` would catch all three errors; `UpstreamVersionError` is not a `SquadronParseError`
- [ ] `ruff` and `pyright` clean (no commit yet; Task 3.2 commits)

**Files to Create**: `src/amoeba/upstream/squadron/review.py`

---

### Task 3.2: Implement `parse_review_artifact`
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 4
**Objective**: Turn a review file's text into a `ParsedReview` per the D3 "From a review file" column.

**Steps**:
- [ ] Split frontmatter: a fence is a line of `---` plus optional trailing whitespace; leading blank lines are allowed; no frontmatter raises `SquadronParseError` with the text "no frontmatter"
- [ ] Load with `yaml.safe_load` only; chain the YAML error; a non-mapping result raises
- [ ] Scan the body for the two headings: any level `#`–`######`, any case, whitespace ignored
- [ ] Map every field per D3. Required: `verdict`, `reviewType`, `aiModel` (missing raises, naming the key). Optional keys map to `None`; absent `verdictSource` maps to `not_reported`; absent `findings:` is an empty tuple
- [ ] `provider_failure` is true when `providerFailure: true` **or** the body has the *Provider Failure* heading; `findings_parsed` is false when the body has *Findings Not Parsed*
- [ ] Each finding: must be a mapping with `severity` and `summary`; `id` → `position_id`, severity through `parse_severity`, other fields pass through as written (including `unverified`). Unknown verdict or severity words raise
- [ ] Call `provider_failure_problem`; if it returns a reason, raise `SquadronParseError` with that reason
- [ ] Ignore unknown keys, including `pr:`, `resolution:`, `resolvedBy:`
- [ ] Never default a required value

**Success Criteria**:
- [ ] Every file in `tests/fixtures/sq_reviews/*.md` parses (verified in Task 3.3)
- [ ] No Squadron key literal appears outside `review_fields.py`
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`

---

### Task 3.3: Test the review-file reader against every fixture
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: Pin the reader on real files and on every listed failure.

**Steps**:
- [ ] Create `tests/upstream/__init__.py` if the other test packages use one, and `tests/upstream/test_review_artifact.py`
- [ ] Table-driven test: for each file fixture, assert the expected verdict, derivation, `findings_parsed`, `provider_failure`, review type, finding count, and for each finding its order, severity, summary, location, and positional id. Take the expected values from reading each file, not from the parser's output
- [ ] Named cases from the LLD's Functional Requirements: both provider-failure files (0.14.0 heading-only; 928 with `providerFailure: true`, `runId`, stamp) give `provider_failure=True`, no findings; the 925 file gives `findings_parsed=False`; the PR file gives `slice=None` and ignores `pr:`; the 0.15.0 files give `sq_run_id` and `upstream_version`
- [ ] Copy-with-heading test: a copy of a real CONCERNS file with the *Findings Not Parsed* heading added gives `findings_parsed=False` (the LLD's known gap; the README already labels this as edited — add the label to the README if Task 1.1 did not)
- [ ] Error cases, each its own test, each asserting `SquadronParseError` and that the message names the key: missing `verdict`, missing review type, missing model, unknown severity, finding that is not a mapping, frontmatter that is not a mapping, malformed YAML (with chained cause), no frontmatter, provider failure with a non-`UNKNOWN` verdict, provider failure with findings
- [ ] Leniency cases: leading blank lines before the fence, trailing spaces on a fence, heading in a different level and case
- [ ] Add the real-input guard (project parsing rule): the test for each fixture must fail if the parser returned empty defaults

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(upstream): parse squadron review files`

**Files to Create**: `tests/upstream/test_review_artifact.py`

---

## Section 4: The Stdout Reader

### Task 4.1: Implement `parse_review_json`
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Turn `sq review … --output json` stdout into a `ParsedReview` per the D3 "From stdout JSON" column.

**Steps**:
- [ ] Find the first `{` and `json.JSONDecoder().raw_decode` from there; ignore everything after the object. No `{` raises `SquadronParseError` ("no JSON object")
- [ ] A decoded object without a `verdict` key raises, naming the key (the provider-error-body case). Chain JSON errors
- [ ] Map per D3: `derivation` from `verdictSource` (`not_reported` if null or absent); `fallback_used` as is (`None` if absent); `findings_parsed` by the D3 rule (false when `fallback_used` is true and derivation is `stated` or `not_reported`; `None` when `fallback_used` absent; else true); `provider_failure` always false; `requested_model` only when `model_substituted` is true; `reviewed_sha`, `slice`, `source_document` always `None`; `sq_run_id` from `run_id`; stamp from `squadron_version`; findings from `structured_findings[]`
- [ ] Reuse the finding mapper from Task 3.2 (do not duplicate it); extract it to a shared helper in the same module if needed
- [ ] If `review.py` is now past ~300 lines, split into `review_json.py` and `review_artifact.py`, keeping `ParsedReview` and composition in `review.py` (per the LLD)

**Success Criteria**:
- [ ] The three stdout captures plus the new pair's JSON parse
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/upstream/squadron/review.py` (and the split files if needed)

---

### Task 4.2: Test the stdout reader
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Pin the stdout reader on real captures and on the derived rules.

**Steps**:
- [ ] Create `tests/upstream/test_review_json.py`
- [ ] Real captures: the clean PASS gives `findings_parsed=True` and standing `stated`; the CONCERNS capture gives ten findings in order; the 0.14.0 captures (with a trailing stdout line, if any) parse the same as pure JSON
- [ ] Synthetic variants built by editing a real capture's dict: `fallback_used: true` + `verdictSource: stated` → `findings_parsed=False`; same with `derived` → `True` and standing `derived`; `requested_model` kept only when `model_substituted` is true; `verdictSource` null → `not_reported`
- [ ] Appended text after the object (a `Saved review to …` line) is ignored
- [ ] Errors: text with no JSON object; a JSON object with no `verdict`; malformed JSON; unknown severity
- [ ] On the new 0.15.0 pair: file and stdout agree on verdict, review type, model, and **finding keys** (`finding_identity` over each finding) in the same order; `template_name` equals `reviewType`

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(upstream): parse squadron stdout json`

**Files to Create**: `tests/upstream/test_review_json.py`

---

## Section 5: Composition

### Task 5.1: Implement `review_record_id`
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: A record id that is a digest of the parsed review (LLD D5).

**Steps**:
- [ ] Build a canonical JSON encoding of every `ParsedReview` field (including `source`, `slice`, `source_document`; findings in order), with sorted keys, compact separators, and the `parsed-review-v1` tag from `review_fields.py` as the first element
- [ ] Return `sq-review-` plus the first 32 hex characters of its SHA-256
- [ ] Enum fields encode by their value, not by repr
- [ ] Add a code comment: changing the covered fields changes every id, so it needs a new tag and a CHANGELOG entry

**Success Criteria**:
- [ ] Same `ParsedReview` always gives the same id; `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`

---

### Task 5.2: Implement `to_verdict_input`
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Compose the store input from a `ParsedReview` and caller-supplied values (LLD D4, API Contracts).

**Steps**:
- [ ] Signature per the LLD: `to_verdict_input(parsed, *, node_id, record_id=None, upstream_version=None, journal_entry_id=None, source_path=None) -> VerdictInput`
- [ ] Id defaults to `review_record_id(parsed)`; `upstream` is the `squadron` constant
- [ ] Version: stamp when present; argument when no stamp; neither raises `UpstreamVersionError`; both and different raises `UpstreamVersionError` naming both labels. Both and equal is fine. Never compare the label beyond this equality
- [ ] Do **not** pass `source_document` or `slice` to `VerdictInput` (106 adds the field)
- [ ] Re-export the public names from `amoeba/upstream/squadron/__init__.py`: `parse_review_json`, `parse_review_artifact`, `ParsedReview`, `to_verdict_input`, `review_record_id`, `SquadronReviewError`, `SquadronParseError`, `UpstreamVersionError`

**Success Criteria**:
- [ ] `from amoeba.upstream.squadron import …` works for all eight names
- [ ] `ruff` and `pyright` clean

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`, `src/amoeba/upstream/squadron/__init__.py`

---

### Task 5.3: Test composition and the dependency direction
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 3
**Objective**: Pin id stability and D4, and enforce the import rules.

**Steps**:
- [ ] Create `tests/upstream/test_review_compose.py`
- [ ] Id: matches `sq-review-` + 32 hex; unchanged after adding `resolution:` and `resolvedBy:` keys and a `## Response` section to a fixture's text; changes when a finding's summary changes; file and stdout parses of the same review differ (D5)
- [ ] `record_id` override is used when supplied; `source_path` and `journal_entry_id` pass through
- [ ] D4 cases: stamp only; argument only (a pre-stamp file); neither raises `UpstreamVersionError`; stamp and a different argument raises and the message contains both labels; equal both is accepted
- [ ] `source_document` does not reach `VerdictInput`
- [ ] Import-direction test: `amoeba.upstream` source files import nothing from `amoeba.inbox`, `amoeba.process`, or `Store`; no file under `amoeba/store` imports `amoeba.upstream` (scan with `ast` or grep in the test; follow any existing import-rule test style in `tests/`)

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(upstream): add review record id and verdict composition`

**Files to Create**: `tests/upstream/test_review_compose.py`

---

## Section 6: The Payload Inverse

### Task 6.1: Implement `verdict_to_payload`
**Owner**: Junior AI
**Dependencies**: Task 5.3
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

### Task 7.1: Switch the four users to `parse_review_artifact`
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 3
**Objective**: 104's matching tests read what production reads (LLD Value and Technical Requirements).

**Steps**:
- [ ] Read each of the four users before editing: `tests/store/test_finding_identity.py`, `tests/store/test_finding_changes.py`, `tests/evidence_harness.py`, `tests/test_demo_evidence_payloads.py`. Edit one file at a time and run its tests after each
- [ ] Replace `review_findings` / `read_frontmatter` / `has_provider_failure_heading` calls with `parse_review_artifact` on the file text and use `ParsedReview.findings` and fields
- [ ] Where a test builds a `VerdictInput` from a fixture, use `to_verdict_input` with an explicit `upstream_version` for pre-stamp files
- [ ] Keep every assertion's expected values unchanged. If one fails, report the difference to the PM rather than changing the expected value

**Success Criteria**:
- [ ] All four files pass with no expected-value changes
- [ ] No test imports `read_frontmatter`, `review_findings`, `CapturedFinding`, or `has_provider_failure_heading`
- [ ] Commit, e.g. `test: read review fixtures through the production parser`

**Files to Modify**: the four files above

---

### Task 7.2: Delete the old fixture reader
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 1
**Objective**: Remove the test-only parser; `tests/review_fixtures.py` keeps only fixture paths.

**Steps**:
- [ ] Delete the YAML reader, frontmatter regex, heading regex, `CapturedFinding`, and the `yaml` and `re` imports from `tests/review_fixtures.py`. Keep `SQ_REVIEWS` and the four `ROUND_*` paths, and add path constants for the new fixtures that later tests need
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
**Dependencies**: Task 7.2
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
- [ ] Create `tests/cli/test_ingest.py`
- [ ] Failure paths, each asserting the exit code and an empty `inbox/new/`: missing file, non-UTF-8 file, `# not a review` text (message mentions no frontmatter), a pre-stamp file with no `--upstream-version`, stamp/argument disagreement, project with no store file (`SUBMISSION_REFUSED`, message names the project)
- [ ] Success path, process stopped: a real fixture with `--upstream-version` writes exactly one file to `inbox/new/`; stdout is the digest id; stderr names the node, slice, and review type; `--stdout-json` works on a capture; both flags together or neither is an argument error
- [ ] D7: a review whose `slice` differs from any node's slice name is still submitted
- [ ] `--id` overrides the digest id

**Success Criteria**:
- [ ] `uv run pytest tests/cli/test_ingest.py` passes; `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(cli): add amoeba ingest review`

**Files to Create**: `tests/cli/test_ingest.py`

---

### Task 8.4: Test end to end through the real CLI
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 4
**Objective**: Prove the LLD's Integration Requirement with real subprocesses.

**Steps**:
- [ ] Model it on `tests/cli/test_evidence_end_to_end.py`: from an empty supervisor directory, start, create the project, stop, seed a node with `scripts/demo_evidence.py`, start
- [ ] Ingest round 1 part 1, round 2 part 1, and a provider-failure file (each with `--upstream-version` where it has no stamp); ingest round 1 again from a different path with a `resolution:` key added; `kill -9` the process; start again
- [ ] Read-only inspection then shows exactly three verdicts with the expected standings, the first ingest's `source_path` (absolute) on round 1, `source: artifact_frontmatter`, and round 2's `inspect changes` naming round 1 as previous with every round-1 finding `gone`
- [ ] A second test: ingest with the process **stopped**; the submission is applied at the next start
- [ ] A third test: ingest into a nonexistent project, with the process running and again stopped, exits `SUBMISSION_REFUSED`, leaves `inbox/new/` empty, and `inspect inbox` shows nothing quarantined
- [ ] A fourth: `--stdout-json` and `--artifact` of the new 0.15.0 pair store two records with different ids (D5)

**Success Criteria**:
- [ ] All pass and leave no stray processes or files outside `tmp_path`; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: end-to-end review ingest through the real CLI`

**Files to Create**: `tests/cli/test_ingest_end_to_end.py`

---

## Section 9: Documentation and Final Validation

### Task 9.1: Write the "Parsing Squadron output" section
**Owner**: Junior AI
**Dependencies**: Task 8.4
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
- [ ] `uv run ruff check .`, `uv run pyright`, `uv run pytest`, and `uv run pytest tests/load` all clean
- [ ] `wc -l` the new source files; split any well over ~300 lines
- [ ] Confirm the import rules by grep: no `amoeba.inbox`, `amoeba.process`, or `Store` import under `src/amoeba/upstream`; no `amoeba.upstream` import under `src/amoeba/store`
- [ ] Run the LLD's Verification Walkthrough steps 1–9 by hand (with the real filenames for the captured pair) and replace its draft note with the real commands and trimmed output
- [ ] If any step does not behave as the LLD says, stop and report to the PM; do not edit the LLD to match

**Success Criteria**:
- [ ] All four checks clean; import rules hold
- [ ] The walkthrough in the LLD shows real output
- [ ] Commit on the slice branch, e.g. `docs: record slice 105 verification walkthrough`

**Files to Modify**: `project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md`
