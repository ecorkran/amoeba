---
docType: review
layer: project
reviewType: code
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 721e4d8cb34e639786cb90bea048e41f76cd6c6b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 206338
cachedTokens: 15901
cacheWriteTokens: 190433
completionTokens: 3040
durationSeconds: 27.7
costUsd: 0.800314
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: note
    category: structure
    summary: "Statement and parameters in `verdicts()` are chosen, then overwritten"
    location: "src/amoeba/store/verdicts.py:71-82"
  - id: F002
    severity: note
    category: dry
    summary: "Payload coercion helpers duplicate existing ones"
    location: "src/amoeba/store/check_models.py:128-170"
  - id: F003
    severity: note
    category: typing
    summary: "Possible strict-pyright narrowing problem in `_examined_count`"
    location: "src/amoeba/store/check_models.py:140-147"
  - id: F004
    severity: note
    category: style
    summary: "Minor lint and style items in new code and tests"
    location: "tests/store/test_calibration.py:75"
  - id: F005
    severity: note
    category: correctness
    summary: "Retry comparison may warn spuriously for JSON-valued `examined`"
    location: "src/amoeba/store/_check_writer.py:96-104"
  - id: F006
    severity: note
    category: behavior
    summary: "Behavior change in `parse_review_json` applies to all ingests"
    location: "src/amoeba/upstream/squadron/review_json.py:71-80"
---

# Review: code — slice 107

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [NOTE] Statement and parameters in `verdicts()` are chosen, then overwritten

When `judge_invocation_id` is set, the node-based `statement, parameters` tuple is computed and then reassigned. The result is correct, because `SELECT_VERDICTS_FOR_INVOCATION` takes `(project, inv, node, node)`. It would read more clearly as one branch, for example an `if judge_invocation_id is not None:` / `elif` chain, or a small helper that returns the pair.

### [NOTE] Payload coercion helpers duplicate existing ones

`_text`, `_optional_text` and `_malformed` are re-implemented for checks. `_vocabulary` in `sql_checks.py` and `_member` in `check_models.py` are near-duplicates, and `_text` and `_optional_text` also appear in `sql_checks.py`. `verdict_payload.py` and `mapping_evidence.py` likely have equivalents, but I did not open them. The project's DRY rule favors sharing these if the error types can be unified. If the separate `ValueError` and `UnknownVocabularyValueError` types are intentional, a one-line comment saying so would help.

### [NOTE] Possible strict-pyright narrowing problem in `_examined_count`

`value` is `object`. After `if value is not None and (not isinstance(value, int) or isinstance(value, bool)): raise`, `return value` may not narrow to `int | None` under strict pyright. I did not run pyright. Confirm it reports zero errors, or use an explicit `cast` or an `isinstance` return.

### [NOTE] Minor lint and style items in new code and tests

- `V = ReviewVerdict` in `_seed` is an uppercase local, which ruff N806 would flag if N is enabled.
- `{field: column for field, column in CALIBRATION_COLUMNS}` could be `dict(CALIBRATION_COLUMNS)`.
- `src/amoeba/store/calibration.py` uses the single-letter `s` in a generator.
- `inspect_checks.py` imports `argparse` and `Store` at runtime for annotations only, which ruff TC may flag.
- The `"."` separator in `_sample_record_id` (`src/amoeba/cli/ingest.py:99-108`) is an inline literal, while the project prefers constants for such values.

### [NOTE] Retry comparison may warn spuriously for JSON-valued `examined`

The retry check compares `_as_input(existing) != check`. `existing.examined` has been through `json.dumps` and `json.loads`, so a caller who passes tuples or non-string keys will see a "different content" WARNING on an otherwise identical retry. This is only a log message and the first record is kept. Normalizing `check.examined` through the same encoding before comparing would avoid the noise.

### [NOTE] Behavior change in `parse_review_json` applies to all ingests

Stdout JSON with verdict UNKNOWN and a score is now refused for every `--stdout-json` ingest, not only for judge samples. This looks intentional (D4), and it is tested against the real captured pair as well as the edited fixture. The error message tells the user to ingest the saved file. Confirm the project does not use stdout JSON with a score and an UNKNOWN verdict in any non-judge flow.

### Run Digest

- Response length: 3863 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 206338 / 15901 / 190433 / 3040 / not computed
- Duration: 27.7 s
- Cost: $0.80 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
