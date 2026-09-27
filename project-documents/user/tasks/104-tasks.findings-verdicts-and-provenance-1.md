---
docType: tasks
slice: findings-verdicts-and-provenance
project: amoeba
lld: user/slices/104-slice.findings-verdicts-and-provenance.md
dependencies: [101, 102, 103]
projectState: Slices 101–103 are merged. The store is at schema version 4 with nodes, blocked states, the command journal, the inbox, and messages. The resident process runs InboxTenant, which applies create_project, resolution, and intent submissions. The store has no record of what a review said. This slice adds verdict records, content-keyed findings, "what changed since last round", and a trust label.
dateCreated: 20260926
dateUpdated: 20260926
status: not_started
---

## Context Summary

- Working on the **findings-verdicts-and-provenance** slice (104), the fourth slice of initiative 100.
- **Current state:** slice 103 is merged. `EXPECTED_SCHEMA_VERSION = 4`. `Store` is assembled from `NodeOperations`, `BlockingOperations`, `JournalOperations`, `MessageOperations`, and `InboxOperations` (`src/amoeba/store/store.py`, 301 lines). The inbox seam is three parts: a `SubmissionKind` member, a payload model in `KIND_PAYLOAD_MODELS` (`inbox/envelope.py`), and an effect in `KIND_EFFECTS` (`store/inbox.py`, 270 lines). The tenant passes the effect the **validated payload as a plain dict** (`payload.model_dump()`), never a pydantic object.
- **Dependencies:** slices 101–103 through their documented contracts. **PyYAML and `types-PyYAML` become dev-only dependencies** (tests read real review-file frontmatter). No new runtime dependency.
- **What this slice delivers:** migration `005` (`verdicts`, `finding_observations`), the `finding_identity` matching rule, `VerdictOperations` (`record_verdict`, `verdict`, `verdicts`, `observations`, `findings`, `finding_changes`), the trust label, the `verdict` inbox kind, the new `amoeba submit` flag rule, `amoeba inspect verdicts` / `findings`, `docs/evidence-contract.md`, and contract/CHANGELOG updates.
- **Not in this slice:** parsing Squadron output (108), judge samples, calibration, checks, task progress, dev log (109), discovering reviews on disk (105).
- **Next planned slices:** 108 (Squadron-output parser) and 109 (judge and checks), both built on this slice's `VerdictInput` and `evidence-contract.md`.

**Branch:** all implementation happens on `104-slice.findings-verdicts-and-provenance`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. Where a task says "per the LLD", open `user/slices/104-slice.findings-verdicts-and-provenance.md` at the named section. Exact DDL, signatures, and error messages are settled during implementation against that design.

**House naming:** the LLD says "mixin"; the codebase says `…Operations` (e.g. `InboxOperations`). Name the new class `VerdictOperations`.

**This file covers Sections 1–5** (matching rule and fixtures, models and trust label, migration 005, `record_verdict` and reads, `finding_changes`). Sections 6–8 (inbox kind and submit flag rule, listings, demo/end-to-end/docs) are in `104-tasks.findings-verdicts-and-provenance-2.md`.

---

## Section 1: The Matching Rule and Real Fixtures

Per the LLD's Development Approach, this is first: it is the riskiest piece and depends on nothing else.

### Task 1.1: Add PyYAML as a dev dependency and copy the real review fixtures
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Put the test inputs in place before any code that is tested against them.

**Steps**:
- [ ] Add `pyyaml` and `types-PyYAML` to the `dev` dependency group in `pyproject.toml` (`uv add --dev`). Not a runtime dependency — slice 108 promotes it
- [ ] Copy the four captured 102 task-review files named in the LLD's Technical Requirements table from `project-documents/user/reviews/archive/` into `tests/fixtures/sq_reviews/`, **byte for byte** (`cp`, never retyped)
- [ ] Before copying, check each source file's frontmatter against the table (verdict and reviewed commit: round 1 part 1 CONCERNS `bf6d292`, part 2 PASS; round 2 part 1 CONCERNS `20b3d70`, part 2 `UNKNOWN`). If any file is missing or differs, **stop and ask the PM**. Never substitute a hand-built round
- [ ] Survey the other files in `project-documents/user/reviews/` (including `archive/`). Copy only ones that are pure Squadron output and serve a named purpose here. Leave out hand-edited files (any with `resolution:` or `resolvedBy:` keys, e.g. `103-review.code…`) and the one written by hand after a tooling gap
- [ ] Add an `sq_reviews/` section to `tests/fixtures/README.md` in the existing table style: file, verdict, reviewed commit, capture date, why it is here, and a line naming the hand-edited files deliberately left out. Include the two JSON captures already in that directory

**Success Criteria**:
- [ ] `diff` between each copied file and its source is empty
- [ ] The README says why each `sq_reviews/` file is present and which review files were excluded as hand-edited
- [ ] `uv run python -c "import yaml"` works in the dev environment; `pyproject.toml` runtime dependencies are unchanged
- [ ] Commit, e.g. `test: add captured squadron review fixtures for slice 104`

**Files to Create**: `tests/fixtures/sq_reviews/*.md`
**Files to Modify**: `pyproject.toml`, `uv.lock`, `tests/fixtures/README.md`

---

### Task 1.2: Implement the matching rule
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: Create `src/amoeba/store/finding_identity.py` with `normalize_summary`, `normalize_location`, `finding_identity`, and `RULE_VERSION`, exactly per the LLD's "The matching rule" table.

**Steps**:
- [ ] Define `RULE_VERSION = 1` and Squadron's `unverified` location text as module constants — each defined once, here
- [ ] `normalize_summary`: the five summary steps in the table, in order
- [ ] `normalize_location`: the four location steps in the table, in order. Line-reference removal covers every listed form (`:12`, `:12-30`, `:12:4`, `#L12`, `#L12-L30`, `, line 12`) **anywhere** in the string. Keep case
- [ ] `finding_identity(location, summary) -> str`: hex SHA-256 of `"v1"`, the normalized location, and the normalized summary, joined by one separator character that cannot appear in normalized text (e.g. `\x1f`); build the `"v1"` prefix from `RULE_VERSION`
- [ ] Import nothing from `amoeba.store` (standard library only)

**Success Criteria**:
- [ ] `grep -n "import" src/amoeba/store/finding_identity.py` shows only standard-library imports
- [ ] The string `unverified` appears in `src/` only in this module
- [ ] `uv run pyright` and `uv run ruff check .` clean

**Files to Create**: `src/amoeba/store/finding_identity.py`

---

### Task 1.3: Test the matching rule with a case table and the captured rounds
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: Pin what the rule catches and, on real data, what it does not.

**Steps**:
- [ ] Parametrized case table for each normalizer: whitespace runs, backticks, casefold, trailing `.`/`;`/`:`, NFKC, every line-reference form, `\` → `/`, leading `./`, `unverified` in any case, missing and empty location, and that location **case is kept**
- [ ] Key tests from the LLD's Functional Requirements: a changed line reference (`:119-163` → `:218-240`, `#L12` → none) or a formatting-only summary change keeps the key; a different path or different words change it
- [ ] A small test helper reads a review file's YAML frontmatter with PyYAML and returns its `findings` list. It lives under `tests/` (it is **not** the slice 108 parser)
- [ ] Captured-rounds test: compute keys for every finding in round 1 part 1 and round 2 part 1; assert the two sets share **no** keys. The docstring names this as the rewording limit and cites one real pair (the `GRACE_EXPIRED` example in the LLD)
- [ ] Fixture guard test: each of the four captured files exists and its frontmatter verdict and reviewed commit match the LLD table; a mismatch fails with a message naming the file

**Success Criteria**:
- [ ] Round 1 part 1 yields 9 findings, round 2 part 1 yields 7, and zero keys are shared (the counts measured during design review; if they differ, stop and ask the PM rather than adjusting the assertion)
- [ ] `uv run pytest tests/store/test_finding_identity.py` passes
- [ ] Commit, e.g. `feat(store): add versioned finding identity rule`

**Files to Create**: `tests/store/test_finding_identity.py`, a frontmatter helper under `tests/` (e.g. `tests/review_fixtures.py`)

---

## Section 2: Word Lists, Records, and the Trust Label

### Task 2.1: Define the evidence vocabularies and transfer types
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 3
**Objective**: Create `src/amoeba/store/evidence_models.py` holding every word list, input/record dataclass, and the trust-label function.

**Steps**:
- [ ] `StrEnum`s with exactly the members in the LLD's "Word lists": `ReviewVerdict`, `FindingSeverity`, `VerdictDerivation`, `RecordSource`, `FindingChange`, `VerdictStanding` (members: the seven labels in the trust-label table)
- [ ] One parse function each for verdict and severity that accepts any letter case and raises `ValueError` on an unknown word. Never map to a near match
- [ ] Frozen dataclasses: `Provenance` (`upstream`, `upstream_version`, `source`, `source_path`), `FindingInput`, `VerdictInput` (fields per the LLD's API Contracts), and `VerdictRecord` (the input's fields plus `project_id`, `recorded_seq`, `recorded_at`, and a `standing` property)
- [ ] Frozen read types for `observations`, `findings`, and `finding_changes` results: an observation row (raw and normalized text, key, rule version, ordinal), a per-key finding summary (node, latest severity and summary, first/last verdict ids, times seen), and `FindingChanges` (comparable flag, previous verdict id or `None`, target findings each tagged `new`/`recurring`, and the `gone` keys)
- [ ] `verdict_standing(...) -> VerdictStanding`: the one trust-label function, reading `provider_failure`, `verdict`, `findings_parsed`, and `derivation` top to bottom per the table. It never reads `fallback_used`. `unattested` is `derivation == not_reported`
- [ ] A `COMPARABLE_STANDINGS` constant (`stated`, `derived`, `imposed`, `unattested`), defined once, for Section 5
- [ ] Add `VerdictNotFoundError(StoreError)` to `src/amoeba/store/models.py`, next to `NodeNotFoundError`
- [ ] No `sqlite3` import and no SQL here

**Success Criteria**:
- [ ] Each word-list value is defined once; `grep` for any member literal in `src/` finds only this module (the migration's CHECK constraints, if any, excepted)
- [ ] `uv run pyright` clean in strict mode

**Files to Create**: `src/amoeba/store/evidence_models.py`
**Files to Modify**: `src/amoeba/store/models.py`

---

### Task 2.2: Test the vocabularies and the trust label table
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Pin the word lists and cover every trust-label row before anything stores them.

**Steps**:
- [ ] Assert each enum's exact member set
- [ ] Assert verdict and severity parse in any case (`pass`, `PASS`, `Pass`) and that an unknown word raises
- [ ] Table-driven test of `verdict_standing` with one row per label, including each case in the LLD's Success Criteria: `derived`, `findings_unparsed`, `imposed`, CONCERNS with zero findings and `findings_parsed=true` → `stated` (comment: table coverage only; Squadron cannot produce it), `provider_failure`, `unparsed`, `unattested`
- [ ] Assert precedence: a provider failure whose other fields also match a later row still gives `provider_failure`
- [ ] Assert every dataclass is frozen

**Success Criteria**:
- [ ] Every `VerdictStanding` member is produced by at least one row
- [ ] `uv run pytest` passes
- [ ] Commit, e.g. `feat(store): add verdict vocabularies and trust label`

**Files to Create**: `tests/store/test_evidence_models.py`

---

## Section 3: Migration 005, SQL, and Mapping

### Task 3.1: Write migration 005 and centralize its SQL
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 3
**Objective**: Add `verdicts` and `finding_observations` at schema version 5, with every statement and column name in one module.

**Steps**:
- [ ] Write `src/amoeba/store/schema/005_verdicts_and_findings.sql` with both tables exactly per the LLD's "Database / Storage Schema", including `recorded_seq INTEGER PRIMARY KEY AUTOINCREMENT`, `id UNIQUE`, the node and journal-entry foreign keys, the `(project_id, node_id, review_type, recorded_seq)` index, the `(verdict_id, ordinal)` primary key, and the `identity` index
- [ ] Nothing to backfill
- [ ] Create `src/amoeba/store/sql_evidence.py` with every statement and column name for both tables, following `sql_inbox.py`
- [ ] Raise `EXPECTED_SCHEMA_VERSION` from 4 to 5

**Success Criteria**:
- [ ] No SQL or column name for either table outside `sql_evidence.py` and the migration file
- [ ] The migration runner picks up `005` without modification
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/store/schema/005_verdicts_and_findings.sql`, `src/amoeba/store/sql_evidence.py`
**Files to Modify**: the module declaring `EXPECTED_SCHEMA_VERSION`

---

### Task 3.2: Map rows to records
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: Create `src/amoeba/store/mapping_evidence.py`, following `mapping_inbox.py`.

**Steps**:
- [ ] Row → `VerdictRecord` and row → observation record. Integer booleans map back to `bool | None`; `criteria` JSON text maps back to a mapping or `None`
- [ ] An unknown enum value in a row **raises**. It is never defaulted or skipped

**Success Criteria**:
- [ ] Column names come only from `sql_evidence.py`
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/store/mapping_evidence.py`

---

### Task 3.3: Test the 4 → 5 upgrade and the mapping
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 2
**Objective**: Prove the upgrade keeps existing data and the mapping refuses bad rows.

**Steps**:
- [ ] Following `tests/store/test_migration_004.py`, build a version-4 store with nodes, journal entries, inbox submissions, and messages; upgrade to 5; assert every row is intact
- [ ] Assert a fresh version-5 store has both tables and all three indexes
- [ ] Assert a row with an unknown `derivation` (written with raw SQL in the test) makes the mapping raise

**Success Criteria**:
- [ ] A populated version-4 store upgrades to 5 with all prior data intact
- [ ] `uv run pytest` passes
- [ ] Commit, e.g. `feat(store): add verdicts and findings schema at version 5`

**Files to Create**: `tests/store/test_migration_005.py`

---

## Section 4: record_verdict and the Read Methods

### Task 4.1: Implement record_verdict
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Create `VerdictOperations` in `src/amoeba/store/verdicts.py` with `record_verdict`, per the LLD's "Recording a review" flow.

**Steps**:
- [ ] One transaction, in the LLD's order: id already recorded → return the existing record and write nothing (log a WARNING if the content differs; first wins); node exists in this project; journal entry, if given, is on the same node; provider failure ⇒ verdict `UNKNOWN` and no findings; `upstream_version` is non-empty; insert the verdict row; insert one observation row per finding, in order, with raw text, normalized text, key, and `RULE_VERSION`
- [ ] Split the checks into a helper that **returns a reason string or `None`**, so Section 6's inbox effect reuses the same checks as plain branches. `record_verdict` raises on a reason (`NodeNotFoundError` for a missing node, `ValueError` or an existing `StoreError` subclass otherwise — match how `block()` raises)
- [ ] Split the insert into a helper that runs inside a caller's transaction, so Section 6 can call it from `apply_submission`
- [ ] Add `VerdictOperations` to the `Store` bases and export the new public names from `amoeba.store`; update `tests/test_public_api.py`
- [ ] Keep `verdicts.py` near 300 lines. If the read methods in Task 4.3 push it over, put them in a second module

**Success Criteria**:
- [ ] One transaction: a failed check or a failing finding insert leaves no verdict row
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/store/verdicts.py`
**Files to Modify**: `src/amoeba/store/store.py`, `src/amoeba/store/__init__.py`, `tests/test_public_api.py`

---

### Task 4.2: Test record_verdict
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 2
**Objective**: Cover every check and the retry rule.

**Steps**:
- [ ] Records a verdict with findings; observations carry the order given, raw and normalized text, key, and rule version
- [ ] Each failing check raises and writes nothing: unknown node, node in another project, journal entry on another node, provider failure with findings, provider failure with a verdict other than `UNKNOWN`, empty `upstream_version`
- [ ] Retry: same id and same content returns the existing record with no WARNING; same id and different content returns the **first** record, writes nothing, and logs a WARNING (`caplog`)
- [ ] `recorded_seq` follows arrival order

**Success Criteria**:
- [ ] Every check in Task 4.1 has a test
- [ ] `uv run pytest` passes
- [ ] Commit, e.g. `feat(store): add record_verdict with retry rule`

**Files to Create**: `tests/store/test_verdicts.py`

---

### Task 4.3: Implement the read methods
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 2
**Objective**: Add `verdict`, `verdicts`, `observations`, and `findings` per the LLD's API Contracts.

**Steps**:
- [ ] `verdict(verdict_id)` returns `None` for an unknown id
- [ ] `verdicts(project_id, *, node_id=None)` in `recorded_seq` order
- [ ] `observations(verdict_id)` in ordinal order; raises `VerdictNotFoundError` for an unknown id
- [ ] `findings(project_id, *, node_id=None)`: one row per key, with node, latest severity and summary, first and last verdict ids, times seen
- [ ] All four work through `Store.open_read_only`

**Success Criteria**:
- [ ] `uv run pyright` clean

**Files to Modify**: `src/amoeba/store/verdicts.py` (or its read-side sibling)

---

### Task 4.4: Test the read methods
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 2
**Objective**: Cover ordering, filtering, the per-key summary, and unknown ids.

**Steps**:
- [ ] `verdict` returns `None`, and `observations` raises `VerdictNotFoundError`, on an unknown id
- [ ] `verdicts` orders by arrival and filters by node
- [ ] `findings` merges the same key across two verdicts (times seen 2, latest severity from the later one) and keeps keys on different nodes apart
- [ ] A repeated key within one review is stored twice in `observations` and shows as one `findings` row
- [ ] Every read works through a read-only handle

**Success Criteria**:
- [ ] `uv run pytest` passes
- [ ] Commit, e.g. `feat(store): add verdict and finding read methods`

**Files to Modify**: `tests/store/test_verdicts.py`

---

## Section 5: finding_changes

### Task 5.1: Implement finding_changes
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 2
**Objective**: Work out new/recurring/gone at call time, per the LLD's "What changed since the last round" flow.

**Steps**:
- [ ] Unknown verdict id raises `VerdictNotFoundError`
- [ ] A target whose standing is not in `COMPARABLE_STANDINGS` returns "not comparable" with empty lists
- [ ] Previous round: the latest earlier verdict (by `recorded_seq`) on the same node and `review_type` whose standing is comparable. Standing is computed with `verdict_standing`, not stored
- [ ] Compare keys only within the same `identity_version`
- [ ] Tag each target finding `recurring` or `new`; `gone` is the previous keys not in the target. No previous round means every finding is `new`
- [ ] Store nothing

**Success Criteria**:
- [ ] The comparable set comes only from `COMPARABLE_STANDINGS`; the trust label only from `verdict_standing`
- [ ] `uv run pyright` clean

**Files to Modify**: `src/amoeba/store/verdicts.py` (or its read-side sibling)

---

### Task 5.2: Test finding_changes, including the captured rounds
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Cover each branch, and run the real 102 rounds through the store.

**Steps**:
- [ ] The same finding text at a different list position, with a moved line range, is `recurring`
- [ ] Round 2 names round 1 as previous and tags new, recurring, and gone correctly (hand-built `FindingInput`s)
- [ ] A provider failure is "not comparable"; one recorded between two real rounds is skipped when choosing the previous round
- [ ] A `findings_unparsed` verdict is never chosen as previous, and a different `review_type` on the same node is never chosen
- [ ] Captured rounds through the store: build `VerdictInput`s from round 1 part 1 and round 2 part 1 via the Task 1.3 frontmatter helper; record both; `finding_changes` on round 2 names round 1, tags every finding `new`, and lists every round 1 key as `gone`
- [ ] Record round 2 part 2 (the real provider failure) as a provider failure; it is labelled `provider_failure` and is "not comparable"

**Success Criteria**:
- [ ] Every branch in Task 5.1 has a test, and the real provider failure is one of the inputs
- [ ] `uv run pytest` passes
- [ ] Commit, e.g. `feat(store): add finding_changes across review rounds`

**Files to Create**: `tests/store/test_finding_changes.py`

---

**Continued in `104-tasks.findings-verdicts-and-provenance-2.md`**: Sections 6–8.
