---
docType: review
layer: project
reviewType: code
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261009
dateUpdated: 20261009
reviewedSha: bc63f3548d7d6cd5857b2815ae962e8de78fbaaf
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
durationSeconds: 27.1
runId: run-20261010-p6-011bdb45
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Non-JSON-serializable YAML values crash the review-id digest and submission"
    location: "src/amoeba/upstream/squadron/review.py:review_record_id"
  - id: F002
    severity: concern
    category: correctness
    summary: "Scalar fields that YAML auto-types are rejected as \"wrong type\""
    location: "src/amoeba/upstream/squadron/review_values.py:typed"
  - id: F003
    severity: note
    category: design
    summary: "Source selection is decided in two places"
    location: "src/amoeba/cli/ingest.py:_compose"
  - id: F004
    severity: note
    category: ux
    summary: "Fixed informational note is printed on every successful ingest"
    location: "src/amoeba/cli/ingest.py:NODE_NOT_IN_ID_NOTE"
  - id: F005
    severity: pass
    category: design
    summary: "Single definition of the provider-failure rule"
    location: "src/amoeba/store/evidence_models.py:provider_failure_problem"
  - id: F006
    severity: pass
    category: style
    summary: "Exception handling, typing, and tooling conform to the Python rules"
    location: "src/amoeba/cli/ingest.py:run_ingest"
  - id: F007
    severity: pass
    category: testing
    summary: "Test coverage uses real fixtures and subprocess-level checks"
    location: "tests/upstream/test_review_artifact.py"
---

# Review: code — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Non-JSON-serializable YAML values crash the review-id digest and submission

`parse_review_artifact` passes `criteria` through from `yaml.safe_load` unchanged (`read_criteria` returns the raw dict). `safe_load` can produce `datetime.date`, `datetime.datetime`, or `bytes` values, for example from an unquoted `2026-09-21` or a `!!binary` tag. `review_record_id` then calls `json.dumps(asdict(parsed))` without a `default`, so it raises `TypeError`. `verdict_to_payload` and `submit` serialize the same data and have the same exposure. `_compose` and `run_ingest` catch only `OSError`, `UnicodeDecodeError`, and `SquadronReviewError`, so a hand-edited review file would produce a raw traceback instead of exit code 12. Validate that `criteria` is JSON-compatible at parse time and raise `SquadronParseError`, or catch `TypeError` at the boundary.

### [CONCERN] Scalar fields that YAML auto-types are rejected as "wrong type"

`typed(raw, key, str, ...)` is used for `reviewedSha`, `runId`, `squadronVersion`, `slice`, and `sourceDocument` in the frontmatter reader. YAML resolves some plausible values to non-strings. An abbreviated SHA that is all digits (`1234567`) or like `1e10345` becomes an int or float. A version written as `0.15` becomes a float. A slice named `2026-09-21` becomes a date. These files then fail with "has the wrong type", and exit code 12 gives the operator little help. CLAUDE.md prefers lenient parsing of format variations. Consider coercing scalar int/float/date values to `str` for fields that are textual by contract, or at least make the error say "quote the value".

### [NOTE] Source selection is decided in two places

`args.artifact is not None` is evaluated in `run_ingest`, to pick the path, and again in `_compose`, to pick the parser. Deriving a single `(path, parser)` pair once would remove the duplication and any chance of the two checks drifting apart.

### [NOTE] Fixed informational note is printed on every successful ingest

The "id does not include the node" note goes to stderr on every run. This is a deliberate choice, per D6 and the comment, and the tests pin it. It will become noise in scripted use, though. Consider printing it only when a second ingest is likely, or put it in the `--help` text only. The `--id` help already documents it.

### [PASS] Single definition of the provider-failure rule

The rule is extracted once and shared by `_verdict_writer.py` and the artifact parser. A test enforces that the reason text is defined in only one place. This follows the DRY and single-source-of-truth guidance.

### [PASS] Exception handling, typing, and tooling conform to the Python rules

Every `except` maps a specific exception type to an explicit exit code with an ERROR-level message. There are no silent swallows, and errors chain with `from error`. `pyproject.toml` has the required ruff `select` list and the strict pyright block. Squadron literals are centralized in `review_fields.py` and enforced by a test.

### [PASS] Test coverage uses real fixtures and subprocess-level checks

Parsers are tested against every real captured review file, with a guard that the table covers all of them. Error cases are built by mutating real text. The CLI tests run as subprocesses against throwaway supervisor directories and never read a production URL variable. The inbox is checked to be empty after each failure, and an import-direction test guards layering.

### Run Digest

- Response length: 3984 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 27.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
