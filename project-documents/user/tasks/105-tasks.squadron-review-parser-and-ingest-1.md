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

**Commit cadence:** a commit never holds untested behavior. An implementation task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own.

**Fixture paths:** `tests/review_fixtures.py` is the single home for fixture path constants. Tasks 1.1–1.3 each add the constants for the files they bring in; later tasks import them and add none.

**This file covers Sections 1–5.** Sections 6–9 are in `105-tasks.squadron-review-parser-and-ingest-2.md`.

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
- [ ] Add one path constant per file to `tests/review_fixtures.py` (keep the existing constants)

**Success Criteria**:
- [ ] `diff` of each copied file against its source is empty
- [ ] The README names all four files with date, origin, and reason
- [ ] No copied file contains `resolution`, `resolvedBy`, or a `## Response` section
- [ ] Commit, e.g. `test: add real squadron review fixtures for slice 105`

**Files to Create**: four files in `tests/fixtures/sq_reviews/`
**Files to Modify**: `tests/fixtures/README.md`, `tests/review_fixtures.py`

---

### Task 1.2: Capture a current Squadron file and stdout pair
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 3
**Objective**: Record one real review as both a saved file and its stdout JSON, so file/stdout equality is tested on real output.

**External gate, contained**: this task needs `sq`, a provider key, and network access. Only the "pair-dependent" items below need its output: the pair assertions in Tasks 3.5, 4.2, 5.2 and 8.8, and the captured-file mentions in them. Nothing else depends on it, so Tasks 1.3 and 2.1 onward do not wait for it. If this task is blocked, stop it and ask the PM, then carry on with everything that is not pair-dependent. Leave each pair-dependent item unchecked and marked `blocked on 1.2`. The slice is not complete until they run (Task 9.3 checks this). Never hand-build a pair.

**Steps**:
- [ ] Make a throwaway copy of this repo outside the working tree (`mktemp -d`). Never run the review in the real repo, so nothing lands in the real `reviews/` directory
- [ ] In the copy, `cd` into it and run `sq review slice 105 --model glmflash --output json > <stdout file> 2> <stderr file>` (the slice **number** form is what makes Squadron save a review file; a path would not). Slice 105's design is the input. If `sq` cannot resolve the number, stop and ask the PM rather than substituting another command
- [ ] Run `sq --version` and record the actual value. It may be newer than 0.15.0 (the LLD's observation date version); use the file names, README text, and test names below with the version you actually got. If the output has keys the LLD's D3 table does not list, note them in the README; the parser ignores unknown keys
- [ ] Confirm the stdout file is one JSON object (parses with `python -m json.tool`) and the `Saved review to` line is in the stderr file, not stdout
- [ ] Confirm the saved review file has no hand edits, note whether it has a `runId` (a CLI run normally does not, and its JSON `run_id` is null), and that `template_name` in the JSON equals `reviewType` in the frontmatter
- [ ] Copy the saved file and the stdout file into `tests/fixtures/sq_reviews/` with `cp`. Name them so the pair is obvious (e.g. same stem; stdout ends `.stdout.json`)
- [ ] Add a README entry: command, Squadron version, model, capture date, why (pins pure-JSON stdout, `template_name == reviewType`, matching finding keys)
- [ ] Add path constants for both files to `tests/review_fixtures.py`
- [ ] If `sq` is unavailable, a provider key is missing, or the stdout is not pure JSON, **stop and ask the PM**. Do not hand-build a pair

**Success Criteria**:
- [ ] Both files exist, are unmodified Squadron output, and are listed in the README with the exact command
- [ ] The stdout file parses as a single JSON object
- [ ] The real `project-documents/user/reviews/` directory gained no files (`git status`)
- [ ] Commit, e.g. `test: capture squadron review file and stdout pair`

**Files to Create**: two files in `tests/fixtures/sq_reviews/`
**Files to Modify**: `tests/fixtures/README.md`, `tests/review_fixtures.py`

---

### Task 1.3: Create the edited-copy fixture and record the known gap
**Owner**: Junior AI
**Dependencies**: Task 1.1 (not 1.2; see the gate note there)
**Effort**: 1
**Objective**: Give the *Findings Not Parsed* + CONCERNS branch a fixture, and say plainly that it is edited (LLD Technical Requirements, "A known gap").

**Steps**:
- [ ] `cp` the round 1 part 1 file (`102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md`, verdict CONCERNS) to a new name ending `.findings-not-parsed-edited.md` in `tests/fixtures/sq_reviews/`
- [ ] In the copy only, add one body heading line `## Findings Not Parsed` (no other change). Never edit the original
- [ ] Add a README section "Known gap": no real review file has a *Findings Not Parsed* heading together with a CONCERNS or FAIL verdict; this edited copy stands in for it. Mark the copy **edited** in the file table, naming the one line added and its source file
- [ ] Add a path constant to `tests/review_fixtures.py`

**Success Criteria**:
- [ ] `diff` between the copy and its source shows exactly the one added heading (plus any blank line around it)
- [ ] The README labels the copy as edited and records the gap as missing real data
- [ ] Commit, e.g. `test: add edited findings-not-parsed fixture and record the gap`

**Files to Create**: one file in `tests/fixtures/sq_reviews/`
**Files to Modify**: `tests/fixtures/README.md`, `tests/review_fixtures.py`

---


## Section 2: Shared Rule, Field Names, and Dependency

### Task 2.1: Move PyYAML to a runtime dependency
**Owner**: Junior AI
**Dependencies**: None (branch from Task 1.1 exists)
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
- [ ] Create `src/amoeba/upstream/__init__.py` and `src/amoeba/upstream/squadron/__init__.py` (re-exports are added in Task 5.3)
- [ ] Create `review_fields.py` with one named constant per string below, grouped under three comment headers. Constant names are yours; the values are exactly these
  - **Stdout JSON top-level keys**: `verdict`, `verdictSource`, `fallback_used`, `structured_findings`, `template_name`, `model`, `requested_model`, `model_substituted`, `diff_truncated`, `score`, `criteria`, `tool_calls_made`, `run_id`, `squadron_version`
  - **Review-file frontmatter keys**: `reviewType`, `verdict`, `verdictSource`, `aiModel`, `requestedModel`, `diffTruncated`, `reviewedSha`, `toolCallsMade`, `score`, `criteria`, `runId`, `squadronVersion`, `slice`, `sourceDocument`, `providerFailure`, `findings`
  - **Finding keys (both sources)**: `id`, `severity`, `category`, `summary`, `location`
  - **Body headings (text only, no `#`)**: `Provider Failure`, `Findings Not Parsed`
  - **Other**: the upstream name `squadron`, and the digest format tag `parsed-review-v1`
- [ ] Do not define derivation or source literals: use `VerdictDerivation` and `RecordSource` from `store/evidence_models.py`
- [ ] A comment lists the keys dropped on purpose (`location_verified`, `finding_scan`, `diff_chars`, `diff_chars_injected`, `answering_models`, `stop_reason`, `tools_given`) and says they have no constant
- [ ] Import only the standard library

**Success Criteria**:
- [ ] Every value listed above has exactly one constant
- [ ] `ruff` and `pyright` clean
- [ ] Commit, e.g. `feat(upstream): add squadron review field names`. (The "defined once" test is Task 5.5, after every reader exists.)

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
- [ ] Add `tests/upstream/test_review_types.py`: `ParsedReview` is frozen and rejects positional construction; all three errors are `ValueError`; `UpstreamVersionError` is not a `SquadronParseError`

**Success Criteria**:
- [ ] The new tests, `ruff`, and `pyright` pass
- [ ] Commit, e.g. `feat(upstream): add ParsedReview and review errors`

**Files to Create**: `src/amoeba/upstream/squadron/review.py`, `tests/upstream/__init__.py` (if other test packages use one), `tests/upstream/test_review_types.py`

---

### Task 3.2: Implement frontmatter splitting and body-heading detection
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: The first half of `parse_review_artifact`: raw frontmatter mapping plus the two heading flags.

**Steps**:
- [ ] Add three private helpers in `review.py`: split frontmatter, load it, detect headings. If Task 4.1 later splits the file, they move into `review_artifact.py` with the artifact reader
- [ ] Fence: a line of `---` plus optional trailing whitespace; leading blank lines allowed; no frontmatter raises `SquadronParseError` containing "no frontmatter"
- [ ] Load with `yaml.safe_load` only; chain the YAML error; a non-mapping result raises
- [ ] Headings: *Provider Failure* and *Findings Not Parsed* at any level `#`–`######`, any case, surrounding whitespace ignored, using the constants from `review_fields.py`

**Success Criteria**:
- [ ] `ruff` and `pyright` clean (committed with Task 3.3)

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`

---

### Task 3.3: Test splitting and headings
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 2
**Objective**: Pin the helpers on real files and format variations.

**Steps**:
- [ ] Create `tests/upstream/test_review_frontmatter.py`
- [ ] Real input: each `.md` file in `tests/fixtures/sq_reviews/` yields a non-empty mapping containing `verdict`
- [ ] Heading flags: the 928 file and `102-…part-2.md` (round 2) have *Provider Failure*; the 925 file and the edited-copy fixture have *Findings Not Parsed*; the round 1 part 1 file has neither
- [ ] Leniency: leading blank lines before the fence; trailing spaces on a fence; heading at another level and in another case
- [ ] Errors, each a `SquadronParseError` naming the problem: no frontmatter (text `# not a review`), malformed YAML (cause is chained), frontmatter that is not a mapping

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit (covers Tasks 3.2 and 3.3), e.g. `feat(upstream): split review frontmatter and detect headings`

**Files to Create**: `tests/upstream/test_review_frontmatter.py`

---

### Task 3.4: Implement `parse_review_artifact` field mapping
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Map the frontmatter and heading flags to a `ParsedReview` per the D3 "From a review file" column.

**Steps**:
- [ ] Required keys: `verdict`, `reviewType`, `aiModel`. A missing one raises `SquadronParseError` naming the key. Never default a required value
- [ ] Optional keys map to `None` when absent; absent `verdictSource` maps to `VerdictDerivation.NOT_REPORTED`; absent `findings:` is an empty tuple; `fallback_used` is always `None`; `source` is `RecordSource.ARTIFACT_FRONTMATTER`
- [ ] `provider_failure` is true when `providerFailure: true` **or** the *Provider Failure* heading is present; `findings_parsed` is false when the *Findings Not Parsed* heading is present, else true
- [ ] Each finding is built by one shared helper (reused by Task 4.1): it must be a mapping with `severity` and `summary`; `id` → `position_id`; severity through `parse_severity`; `category` and `location` pass through as written (including `unverified`). A non-mapping finding, a missing `severity` or `summary`, or an unknown severity or verdict word raises, naming the key
- [ ] Call `provider_failure_problem`; if it returns a reason, raise `SquadronParseError` with that reason
- [ ] Ignore unknown keys, including `pr:`, `resolution:`, `resolvedBy:`

**Success Criteria**:
- [ ] Every `.md` fixture parses without error
- [ ] `ruff` and `pyright` clean (committed with Task 3.5)

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`

---

### Task 3.5: Test the review-file reader against every fixture
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: Pin the reader on real files and on every listed failure.

**Steps**:
- [ ] Create `tests/upstream/test_review_artifact.py`
- [ ] Table-driven test over every `.md` fixture: expected verdict, derivation, `findings_parsed`, `provider_failure`, review type, finding count, and for each finding its order, severity, summary, location, and positional id. Write the expected values by reading each file, not by printing the parser's output. Each row also asserts `findings` or another field is non-default where the file has data (catches silent empty results)
- [ ] Named cases: both provider-failure files (the 0.14.0 `102-…part-2.md` heading-only; the 928 file with `providerFailure: true`, `runId`, stamp) give `provider_failure=True` and no findings; the 925 file gives `findings_parsed=False`; the edited-copy fixture (CONCERNS + heading) gives `findings_parsed=False`; the PR file gives `slice=None` and ignores `pr:`; the 106 file gives `sq_run_id` (`run-20260928-slices-plan-a04bdb07`) and its `upstream_version` stamp; pair-dependent (`blocked on 1.2` if Task 1.2 is blocked): the new captured file gives its stamp, and `sq_run_id` equal to its `runId` if it has one and `None` if it does not
- [ ] Missing-key errors, each its own test: no `verdict`, no `reviewType`, no `aiModel`; each message names the key
- [ ] Finding errors, each its own test (mutate a copy of a real file's text): a finding that is not a mapping; a finding without `severity`; a finding without `summary`; an unknown severity word; an unknown verdict word
- [ ] Provider-failure errors: a failure with a verdict other than `UNKNOWN`; a failure with findings
- [ ] Unknown keys such as `resolution:` do not change the result

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit (covers Tasks 3.4 and 3.5), e.g. `feat(upstream): parse squadron review files`

**Files to Create**: `tests/upstream/test_review_artifact.py`

---

## Section 4: The Stdout Reader

### Task 4.1: Implement `parse_review_json`
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 3
**Objective**: Turn `sq review … --output json` stdout into a `ParsedReview` per the D3 "From stdout JSON" column.

**Steps**:
- [ ] Find the first `{` and `json.JSONDecoder().raw_decode` from there; ignore everything after the object. No `{` raises `SquadronParseError` ("no JSON object")
- [ ] A decoded object without a `verdict` key raises, naming the key (the provider-error-body case). Chain JSON errors
- [ ] Map per D3: `derivation` from `verdictSource` (`not_reported` if null or absent); `fallback_used` as is (`None` if absent); `findings_parsed` by the D3 rule (false when `fallback_used` is true and derivation is `stated` or `not_reported`; `None` when `fallback_used` absent; else true); `provider_failure` always false; `requested_model` only when `model_substituted` is true; `reviewed_sha`, `slice`, `source_document` always `None`; `sq_run_id` from `run_id`; stamp from `squadron_version`; findings from `structured_findings[]`
- [ ] Reuse the finding helper from Task 3.4 (do not duplicate it)
- [ ] If `review.py` is now past ~300 lines, split into `review_json.py` and `review_artifact.py`, keeping `ParsedReview` and composition in `review.py` (per the LLD)

**Success Criteria**:
- [ ] `stdout-slice-927-clean-pass.json`, and `stdout-slice-104-concerns-glmflash.json` parse (plus the new pair's stdout file, once Task 1.2 has produced it)
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
- [ ] Real captures: `stdout-slice-927-clean-pass.json` gives `findings_parsed=True` and standing `stated`; `stdout-slice-104-concerns-glmflash.json` gives ten findings in order (check the count and order against the file)
- [ ] Trailing-line tolerance: append a `Saved review to <path>` line to the text of a real capture; the result equals the pure-JSON parse. This is synthetic on purpose: the fixtures README confirms neither existing capture carries the line (the LLD's success criterion says the 0.14.0 captures do; that wording is stale, so test the behavior it describes and note the difference in the commit message)
- [ ] `findings_parsed` rule, one test per branch, built by editing a real capture's dict:
  - `fallback_used: true` with `verdictSource: stated` → `False`
  - `fallback_used: true` with `verdictSource` null → `False` (derivation `not_reported`)
  - `fallback_used: true` with `verdictSource: derived` → `True`, standing `derived`
  - `fallback_used: false` → `True`
  - `fallback_used` key absent → `None`
- [ ] `requested_model` is kept only when `model_substituted` is true; `verdictSource` null → derivation `not_reported`
- [ ] Errors: text with no JSON object; a JSON object with no `verdict`; malformed JSON; unknown severity; a finding without `severity`; a finding without `summary`
- [ ] Pair-dependent (`blocked on 1.2` if Task 1.2 is blocked): on the new captured pair (stdout file and saved `.md` from Task 1.2): file and stdout agree on verdict, review type, model, and **finding keys** (`finding_identity` over each finding) in the same order; `template_name` equals `reviewType`

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
- [ ] Same `ParsedReview` always gives the same id; `ruff` and `pyright` clean (committed with Task 5.2)

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`

---

### Task 5.2: Test `review_record_id`
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 2
**Objective**: Pin id stability (LLD D5).

**Steps**:
- [ ] Create `tests/upstream/test_review_record_id.py`
- [ ] The id matches `sq-review-` + 32 hex characters
- [ ] Unchanged after adding `resolution:` and `resolvedBy:` keys and a `## Response` section to a fixture's text
- [ ] Changes when one finding's summary changes, and when the verdict changes
- [ ] Pair-dependent (`blocked on 1.2` if Task 1.2 is blocked): the file parse and the stdout parse of the newly captured pair get different ids

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit (covers Tasks 5.1 and 5.2), e.g. `feat(upstream): add parsed-content review record id`

**Files to Create**: `tests/upstream/test_review_record_id.py`

---

### Task 5.3: Implement `to_verdict_input`
**Owner**: Junior AI
**Dependencies**: Task 5.2
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
- [ ] `ruff` and `pyright` clean (committed with Task 5.4)

**Files to Modify**: `src/amoeba/upstream/squadron/review.py`, `src/amoeba/upstream/squadron/__init__.py`

---

### Task 5.4: Test `to_verdict_input`
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 2
**Objective**: Pin composition and the D4 version rule.

**Steps**:
- [ ] Create `tests/upstream/test_review_compose.py`
- [ ] Defaults and overrides: the id defaults to the digest; `record_id` overrides it; `source_path` and `journal_entry_id` pass through; `upstream` is `squadron`; `source_document` and `slice` do not reach `VerdictInput`
- [ ] D4 cases: stamp only; argument only (a pre-stamp file such as the round 1 files); neither raises `UpstreamVersionError`; stamp and a different argument raises and the message contains both labels; equal stamp and argument is accepted
- [ ] The public-names import works for all eight names

**Success Criteria**:
- [ ] `uv run pytest tests/upstream` passes; `ruff` and `pyright` clean
- [ ] Commit (covers Tasks 5.3 and 5.4), e.g. `feat(upstream): compose verdict input from a parsed review`

**Files to Create**: `tests/upstream/test_review_compose.py`

---

### Task 5.5: Test the dependency direction and single definition of Squadron keys
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 1
**Objective**: Enforce the LLD's import rules and its "each key defined once" rule with tests, so Task 9.3 does not need to repeat them by hand.

**Steps**:
- [ ] Create `tests/upstream/test_import_direction.py`. Scan the source files (use `ast`; follow any existing import-rule test style in `tests/`): nothing under `src/amoeba/upstream` imports `amoeba.inbox`, `amoeba.process`, or `Store`; nothing under `src/amoeba/store` imports `amoeba.upstream`
- [ ] Create `tests/upstream/test_field_names_defined_once.py`. Using `ast`, collect every string constant in `src/amoeba/upstream/squadron/` modules other than `review_fields.py`, excluding docstrings; fail if any equals a Squadron key, heading, or tag value from `review_fields.py`. Import the values from `review_fields`; do not retype them. If it flags a hit, fix the source to use the constant; do not loosen the test

**Success Criteria**:
- [ ] Both tests pass; `ruff` and `pyright` clean
- [ ] Commit, e.g. `test: enforce upstream import direction and single key definitions`

**Files to Create**: `tests/upstream/test_import_direction.py`, `tests/upstream/test_field_names_defined_once.py`
