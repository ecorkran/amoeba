---
docType: tasks
slice: findings-verdicts-and-provenance
project: amoeba
lld: user/slices/104-slice.findings-verdicts-and-provenance.md
dependencies: [101, 102, 103]
projectState: Continuation of 104-tasks.findings-verdicts-and-provenance-1.md. After Sections 1–5 the store is at schema version 5 with record_verdict, the read methods, finding_changes, and the trust label. Nothing outside the process can record a verdict yet, and nothing displays one.
dateCreated: 20260926
dateUpdated: 20260927
status: complete
---

## Context Summary

- Continues `104-tasks.findings-verdicts-and-provenance-1.md`; see its Context Summary for slice state, dependencies, branch, and house naming.
- **This file covers Sections 6–8:** the `verdict` inbox kind and the new `amoeba submit` flag rule, the two inspection listings with `value_options`, and the demo script, end-to-end CLI test, docs, and final validation.
- **The seam, as it really works:** `validate_envelope` checks the payload with its pydantic model, then hands the store `payload.model_dump()`, a plain dict. So the store-side `verdict` effect turns that dict into a `VerdictInput` itself, using payload key names defined once in `evidence_models.py`, the same way 103's effects read their dicts with `RESOLUTION_*` / `INTENT_*` keys. The store never imports pydantic or `amoeba.inbox`.

---

## Section 6: The Submit Flag Rule and the verdict Inbox Kind

The flag rule comes first. Registering `VerdictPayload` makes `amoeba submit` build a `verdict` subcommand, and today's `_takes_object` raises `TypeError` at parser build on its bool and list fields, which would break every CLI test until the rule changed.

### Task 6.1: Replace the submit flag rule
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 2
**Objective**: Make `amoeba submit` build flags for every payload field type, per the LLD's "`amoeba submit` reads flags by one rule".

**Steps**:
- [x] Replace `_takes_object` in `src/amoeba/cli/submit.py` with a rule: a text field, an enum field, or the optional form of either takes the flag as typed; every other field takes JSON (`--score 82.5`, `--fallback-used null`, `--findings '[…]'`)
- [x] A value that is not valid JSON fails with an argparse error naming the flag
- [x] Pydantic validates the built payload either way; the CLI does no type checking of its own
- [x] Existing `create-project`, `resolution`, and `intent` flags behave exactly as before (a dict field was already JSON; text fields stay as typed)
- [x] No per-kind branch: flags keep coming from each kind's payload model

**Success Criteria**:
- [x] No per-kind branch in `cli/submit.py`
- [x] `uv run pyright` clean
- [x] Commit, e.g. `feat(cli): read submit flags by field type`

**Files to Modify**: `src/amoeba/cli/submit.py`

---

### Task 6.2: Test the flag rule
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: Replace `_takes_object`'s tests with ones for the new rule, before any real payload depends on it.

**Steps**:
- [x] Replace the `_takes_object` tests in `tests/cli/test_submit.py` with a table over annotations: `str`, `str | None`, a `StrEnum`, its optional form → as typed; `bool | None`, `float | None`, `int | None`, `list[…]`, `dict[…]` → JSON
- [x] Using a small pydantic model defined in the test, `null` builds `None`, `false` builds `False`, and `'[…]'` builds a list
- [x] Bad JSON on a JSON flag fails with an error naming the flag
- [x] 103's other submit CLI tests pass unchanged

**Success Criteria**:
- [x] `uv run pytest tests/cli` passes
- [x] Commit, e.g. `test: cover the submit flag rule`

**Files to Modify**: `tests/cli/test_submit.py`

---

### Task 6.3: Add the verdict submission kind
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 3
**Objective**: Add all three parts of 103's seam for `verdict`, reusing Section 4's checks and insert.

**Steps**:
- [x] Add `VERDICT` to `SubmissionKind`
- [x] In `evidence_models.py`, define the payload key names once (one constant per `VerdictInput` field except `id`, with `provenance` flattened to `upstream`, `upstream_version`, `source`, `source_path`, per the LLD's "The inbox `verdict` type"), and a function that builds a `VerdictInput` from a submission id plus a validated payload mapping. The submission id becomes the record id
- [x] Create `src/amoeba/inbox/evidence_payloads.py` with pydantic `FindingPayload` and `VerdictPayload`. Enum fields use the store's `StrEnum`s with case-insensitive verdict/severity (reuse Task 2.1's parse functions in a validator). `derivation`, `fallback_used`, and `findings_parsed` are **required** (the submitter passes `not_reported` or `null`, never omits them)
- [x] Register `VerdictPayload` in `KIND_PAYLOAD_MODELS`
- [x] Write the `verdict` effect: build the `VerdictInput`, run Task 4.1's check helper and return its reason as a rejection (a plain branch, never catching an exception), otherwise run Task 4.1's insert helper inside `apply_submission`'s transaction. Put the effect beside `record_verdict`, not in `store/inbox.py` (270 lines); `KIND_EFFECTS` gains one entry
- [x] A replayed submission id is already a no-op through `apply_submission`'s replay check; do not add a second one

**Success Criteria**:
- [x] Payload key names appear once in `src/amoeba/store/` and match `VerdictPayload`'s field names (pinned by a test in Task 6.4)
- [x] `amoeba.store` imports neither pydantic nor `amoeba.inbox`
- [x] `amoeba submit verdict --help` lists every `VerdictPayload` field, with no change to `cli/submit.py`
- [x] `uv run pyright` clean
- [x] Commit, e.g. `feat(inbox): add verdict submission kind`

**Files to Create**: `src/amoeba/inbox/evidence_payloads.py`
**Files to Modify**: `src/amoeba/store/inbox_models.py`, `src/amoeba/store/evidence_models.py`, `src/amoeba/store/verdicts.py`, `src/amoeba/store/inbox.py` (one `KIND_EFFECTS` entry), `src/amoeba/inbox/envelope.py` (one `KIND_PAYLOAD_MODELS` entry)

---

### Task 6.4: Test the verdict kind through apply_submission, the envelope, and the CLI
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 2
**Objective**: Cover applied, rejected, replayed, and quarantined paths, and extend 103's completeness pins.

**Steps**:
- [x] Extend 103's completeness tests so every `SubmissionKind` has a payload model and an effect, `VERDICT` included
- [x] Add a `VERDICT` entry to `KIND_FLAGS` in `tests/cli/test_submit.py` with a full valid flag set (every required field: node id, verdict, derivation, fallback-used, findings-parsed, provider-failure, review type, model, findings, upstream, upstream version, source). `test_every_kind_has_a_subcommand` and the parametrized write test then cover `verdict`
- [x] `VerdictPayload`'s field names equal the store's payload key set, so the two cannot drift
- [x] A valid verdict submission is `applied`, and the record id equals the submission id
- [x] Applying the same submission again changes nothing
- [x] A provider failure with findings, and one with a non-`UNKNOWN` verdict, are `rejected` with a reason; an unknown node is `rejected`
- [x] An empty `upstream_version` is `rejected` with a reason
- [x] An unrecognized `derivation` fails envelope validation with `INVALID_PAYLOAD` (the file would be quarantined); an omitted `findings_parsed` fails too
- [x] Lowercase `concerns` and uppercase `CONCERN` severity are accepted

**Success Criteria**:
- [x] `uv run pytest` passes
- [x] Commit, e.g. `test: cover the verdict submission kind`

**Files to Create**: `tests/store/test_verdict_submission.py`
**Files to Modify**: 103's completeness tests (`tests/inbox/test_envelope.py`, `tests/store/test_inbox_apply.py`), `tests/cli/test_submit.py` (`KIND_FLAGS`)

---

## Section 7: The Two Listings

### Task 7.1: Add value_options to the listing registry
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 1
**Objective**: Let a listing take options that carry a free value (`--node ID`), per the LLD's CLI section. This is the only change to 102's CLI plumbing, and it is additive.

**Steps**:
- [x] Add `value_options` to `Listing` in `src/amoeba/cli/inspect.py`, defaulting to empty, alongside the existing `choice_options`
- [x] `_add_inspect_parser` in `src/amoeba/cli/main.py` adds them, in the same loop that adds `choice_options` today; the row function receives their values
- [x] Existing listings are unchanged

**Success Criteria**:
- [x] Every existing `tests/test_cli_inspect.py` test passes unchanged
- [x] `cli/main.py` grows by only the few lines of the new option loop
- [x] `uv run pyright` clean
- [x] Commit, e.g. `feat(cli): add value options to the listing registry`

**Files to Modify**: `src/amoeba/cli/inspect.py`, `src/amoeba/cli/main.py`

---

### Task 7.2: Implement inspect verdicts and inspect findings
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 3
**Objective**: Create `src/amoeba/cli/inspect_evidence.py` with both listings, appended to `LISTINGS`, following `inspect_inbox.py`.

**Steps**:
- [x] `verdicts`: `--node` value option; columns exactly `recorded_seq, id, node_id, review_type, model, verdict, standing, upstream_version`. `--json` rows also carry `upstream`, `source`, `source_path`, and `recorded_at` (walkthrough step 6)
- [x] `findings`: `--node` and `--verdict` value options. Without `--verdict`, one row per key from `findings()`. With `--verdict`, a header line naming the previous review (or saying "not comparable"), then that review's findings tagged `new`/`recurring`, then the `gone` keys
- [x] An unknown `--verdict` id is an error with a non-OK exit code, never an empty listing
- [x] Both read through `Store.open_read_only`, so they work whether the process is running or stopped

**Success Criteria**:
- [x] `cli/inspect.py` and `cli/main.py` grow by no more than the registry append and imports
- [x] `uv run pyright` clean
- [x] Commit, e.g. `feat(cli): add verdicts and findings listing rows`

**Files to Create**: `src/amoeba/cli/inspect_evidence.py`
**Files to Modify**: `src/amoeba/cli/inspect.py` (append to `LISTINGS`)

---

### Task 7.3: Test the listings and re-pin the registry
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 2
**Objective**: Cover both listings and replace 102's "not registered here" pins.

**Steps**:
- [x] Replace `test_slice_104_listings_are_not_registered_here` with a test pinning the full set, `verdicts` and `findings` included
- [x] Replace the nearby test asserting `inspect findings` fails as unregistered (in `tests/test_cli_inspect.py`)
- [x] `verdicts` shows the pinned columns and filters by `--node`; `--json` carries the provenance fields
- [x] `findings --verdict` prints the previous-review header and correct tags; "not comparable" for a provider failure; an unknown id exits non-OK
- [x] Both listings run with the process stopped and running (use the existing inspect-test harness)

**Success Criteria**:
- [x] `uv run pytest` passes
- [x] Commit, e.g. `feat(cli): add verdicts and findings listings`

**Files to Create**: `tests/cli/test_inspect_evidence.py`
**Files to Modify**: `tests/test_cli_inspect.py`

---

## Section 8: Demo, End to End, and Docs

### Task 8.1: Add the demo script and review payloads
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Build what the LLD's Verification Walkthrough needs, following `scripts/demo_inbox.py`.

**Steps**:
- [x] `scripts/demo_evidence.py` seeds one node in the `demo` project and prints only its id. It runs with the process stopped and takes the instance lock, like `demo_inbox.py`
- [x] Add `demo_evidence.py` to `PERMITTED_SCRIPTS` in `tests/test_writer_guard.py`, and update the pinned-set assertion and its comment. The guard is otherwise unchanged
- [x] `scripts/demo_evidence/round1.json` and `round2.json`: findings arrays using **real finding text from the captured 102 rounds**, arranged so round 2 has one finding back at a new position with a moved line range, one dropped, and one new
- [x] Add a one-finding payload for walkthrough step 4

**Success Criteria**:
- [x] `uv run pytest tests/test_writer_guard.py` passes with the permitted set widened by exactly this script
- [x] Every finding summary in the payload files can be traced to a fixture in `tests/fixtures/sq_reviews/`
- [x] Commit, e.g. `feat: add evidence demo script and payloads`

**Files to Create**: `scripts/demo_evidence.py`, `scripts/demo_evidence/*.json`
**Files to Modify**: `tests/test_writer_guard.py`

---

### Task 8.2: Test end to end through the real CLI
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 3
**Objective**: Prove the LLD's Integration Requirement, following `tests/cli/test_inbox_end_to_end.py`.

**Steps**:
- [x] Create a project, seed a node with the demo script, start the process
- [x] Submit round 1, round 2, and a provider failure with `amoeba submit verdict`
- [x] Resubmit round 1 with the same `--id`, `kill -9` the process, `amoeba start`
- [x] Read-only inspection shows three verdicts, the right tags on round 2, "not comparable" on the failure, and no submission applied twice

**Success Criteria**:
- [x] The test passes repeatedly (run it 5 times); if it flakes, get the failure output before changing anything
- [x] `uv run pytest` passes
- [x] Commit, e.g. `test: add evidence end-to-end cli test`

**Files to Create**: `tests/cli/test_evidence_end_to_end.py`

---

### Task 8.3: Write the evidence contract and update the other docs
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 2
**Objective**: Make `docs/evidence-contract.md` enough for slice 108's and initiative 140's designs without reading the code.

**Steps**:
- [x] `docs/evidence-contract.md`: the matching rule (version 1, each step), what it does **not** match (rewording, citing the captured rounds), the trust labels and their order, the "CONCERNS, zero findings, parsed" note from the LLD, how the previous round is chosen and why failures are never a baseline, the provenance fields and that versions are never compared, the retry rule, and `VerdictInput`'s fields including the null-until-SQ-927 `diff_truncated` and `requested_model`
- [x] `docs/store-contract.md`: drop the "not a findings store" line; add the new operations and `VerdictNotFoundError`
- [x] `docs/inbox-contract.md`: the `verdict` kind and the new submit flag rule
- [x] `CHANGELOG.md`: one entry for the slice, including `value_options` and schema version 5

**Success Criteria**:
- [x] Every item in the LLD's Technical Requirements docs bullet is covered
- [x] Commit, e.g. `docs: add evidence contract and update store and inbox contracts`

**Files to Create**: `docs/evidence-contract.md`
**Files to Modify**: `docs/store-contract.md`, `docs/inbox-contract.md`, `CHANGELOG.md`

---

### Task 8.4: Final validation and the walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 2
**Objective**: Run everything, and fill in the LLD's Verification Walkthrough with real output.

**Steps**:
- [x] `uv run ruff check .`, `uv run pyright`, `uv run pytest`, and `uv run pytest tests/load` all clean
- [x] Check new source files are near 300 lines (`wc -l`); split any that are well over
- [x] Run the LLD's Verification Walkthrough steps 1–7 by hand and replace its draft note with the real commands and trimmed output
- [x] If any walkthrough step does not behave as the LLD says, stop and report to the PM; do not edit the LLD to match

**Success Criteria**:
- [x] All four checks clean
- [x] The walkthrough in the LLD shows real output
- [x] Commit on the slice branch, e.g. `docs: record slice 104 verification walkthrough`

**Files to Modify**: `project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md`
