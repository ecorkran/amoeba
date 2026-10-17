---
docType: review
layer: project
reviewType: code
slice: judge-samples-checks-and-calibration
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: b8d767aff1e9bd6cf77676993a553e954d68e49e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 126854
cachedTokens: 0
cacheWriteTokens: 126852
completionTokens: 3201
durationSeconds: 28.5
costUsd: 0.54659
costBasis: provider
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Empty or blank judge invocation id is accepted everywhere"
    location: "src/amoeba/cli/ingest.py:99-109"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`record_progress` skips project and node consistency checks"
    location: "src/amoeba/store/checks.py:61-72"
  - id: F003
    severity: concern
    category: design
    summary: "Duplicated row-mapping and vocabulary helpers"
    location: "src/amoeba/store/sql_checks.py:136-165"
  - id: F004
    severity: note
    category: typing
    summary: "Possible pyright strict error in `_examined_count`"
    location: "src/amoeba/store/check_models.py:131-137"
  - id: F005
    severity: note
    category: design
    summary: "Sample id format `<digest>.<invocation>` is ambiguous"
    location: "src/amoeba/cli/ingest.py:99-109"
  - id: F006
    severity: note
    category: testing
    summary: "Minor test style items"
    location: "tests/store/test_calibration.py:76"
  - id: F007
    severity: pass
    category: sql
    summary: "Schema, SQL and exception handling"
    location: "src/amoeba/store/schema/007_judge_samples_checks_and_progress.sql"
---

# Review: code — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Empty or blank judge invocation id is accepted everywhere

`_sample_record_id` and `to_verdict_input` test `judge_invocation_id is not None`. `--judge-invocation-id ""` therefore makes a record a "judge sample" with id `<digest>.`. The same applies to the `VerdictPayload.judge_invocation_id` field and the store writer (`_invocation_mismatch`). Whitespace-only ids behave the same way. Samples sharing a blank id would be grouped as one invocation. `upstream_version` already gets an explicit non-empty check. This field needs the same guard, ideally in `VerdictWriter._rejection` so the CLI, `record_verdict` and inbox paths all enforce it. It also needs a test.

### [CONCERN] `record_progress` skips project and node consistency checks

`record_progress` inserts with only table constraints. `node_id` is a foreign key on `nodes(id)` alone, so a progress record can be written with a `project_id` that differs from the node's project. An empty `upstream_version` is also accepted. D6 documents this as intentional. Still, silently mis-attributed provenance in a write-only table is hard to repair later. The check is cheap and already exists in `CheckWriter._check_rejection`. Consider reusing it for the node and project and `upstream_version` checks. If the bare insert stays, add a test pinning that cross-project behavior.

### [CONCERN] Duplicated row-mapping and vocabulary helpers

`_text`, `_optional_text`, `_integer` and `_vocabulary` appear to repeat the helpers in `mapping_evidence.py`. `mapping_evidence` already calls `_text` and `_optional_text` with the same signatures. `check_models._member` also overlaps with `sql_checks._vocabulary`. This breaks the DRY rule in the project guidelines. Move the shared helpers into one module, for example a `mapping_common` module next to `mapping_journal`. I did not open `mapping_evidence.py` to confirm the overlap.

### [NOTE] Possible pyright strict error in `_examined_count`

`value` is `object`. Pyright does not reliably narrow it to `int | None` through `value is not None and (not isinstance(...) or isinstance(..., bool))` followed by `return value`. The project requires zero errors under strict mode. If it does flag this, use a positive `isinstance(value, int)` branch or a `cast`.

### [NOTE] Sample id format `<digest>.<invocation>` is ambiguous

Invocation ids may themselves contain `.`. Distinct (digest, invocation) pairs still produce distinct ids because the digest has a fixed form. The id string is not cleanly parseable back into its parts, though, so nothing should split on it. A short comment saying so would help.

### [NOTE] Minor test style items

The local alias `V = ReviewVerdict` is an uppercase local name, which ruff's naming rules may flag. Several store tests reach into `store._connection` with a pyright ignore. That is acceptable for staging and inspection, but a harness helper would centralize it. Otherwise test coverage is strong: parametrized standing table, migration upgrade of populated stores, retry semantics, feed invariants, and an end-to-end crash-restart test.

### [PASS] Schema, SQL and exception handling

All values are bound parameters, and column names are centralized in `sql_checks.py` with tests pinning the migration to them. The new index serves the invocation lookup. The feed trigger writes only the three documented payload keys. The `try/except` blocks catch `ValueError` specifically and re-raise with context, so none swallow errors.

### Run Digest

- Response length: 4220 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 126854 / 0 / 126852 / 3201 / not computed
- Duration: 28.5 s
- Cost: $0.55 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
