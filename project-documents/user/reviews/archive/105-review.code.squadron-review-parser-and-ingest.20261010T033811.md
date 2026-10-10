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
reviewedSha: 9f54f7fcbb685bf2333e7c40ae61d8248e062a39
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
durationSeconds: 47.6
runId: run-20261010-p6-011bdb45
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Re-ingesting a review for a different node is silently a no-op replay"
    location: "src/amoeba/cli/ingest.py:127-136"
  - id: F002
    severity: concern
    category: dry
    summary: "Duplicated test setup and inconsistent import roots"
    location: "tests/cli/test_ingest.py:57-62"
  - id: F003
    severity: concern
    category: typing
    summary: "Tests with weak typing under strict pyright"
    location: "tests/store/test_provider_failure_problem.py:14"
  - id: F004
    severity: concern
    category: typing
    summary: "`typed()` returns `Any`, so none of the field readers are type-checked"
    location: "src/amoeba/upstream/squadron/review_values.py:26-34"
  - id: F005
    severity: concern
    category: parsing
    summary: "Provider-failure and findings-not-parsed detection searches the whole body for headings"
    location: "src/amoeba/upstream/squadron/review_artifact.py:28-37"
  - id: F006
    severity: note
    category: validation
    summary: "Empty `--upstream-version` is accepted"
    location: "src/amoeba/upstream/squadron/review.py:93-102"
  - id: F007
    severity: note
    category: structure
    summary: "`_compose` reports to stderr before the submission is made"
    location: "src/amoeba/cli/ingest.py:77-90"
  - id: F008
    severity: pass
    category: design
    summary: "Shared provider-failure rule and payload inverse"
    location: "src/amoeba/store/evidence_models.py:122-143"
---

# Review: code — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Re-ingesting a review for a different node is silently a no-op replay

The submission id and record id come from `review_record_id`, which deliberately excludes the node, the path and the version label. A second `ingest review` of the same review with a different `--node` produces the same id. That id is then treated as an idempotent replay. `--node` is the operator's unchecked attribution (D7), and the command prints the node on stderr so a wrong one is visible. But correcting it by re-running with the right node can't work, and the success exit code gives no sign that the new attribution was dropped. I did not inspect how the inbox treats a replay whose payload differs from the first, so confirm that it rejects a conflicting payload instead of ignoring it. If it ignores it, add a test for the same review with a different node. The existing e2e test only covers the same node with a different path.

### [CONCERN] Duplicated test setup and inconsistent import roots

`test_ingest.py` redefines `PROJECT`, `PRE_STAMP_LABEL`, `DEMO_SCRIPT` and a `_seed_node` helper (around lines 190-200). `ingest_e2e_harness.py` already provides the same things as `seed_node`, `PROJECT`, `PRE_STAMP_LABEL` and `DEMO_SCRIPT`. The e2e tests also mix `from cli_harness import ...` with `from cli.ingest_e2e_harness import ...`, so two different import roots are in use. That is fragile and depends on how pytest's path is set up. Reuse the harness helpers and pick one import style.

### [CONCERN] Tests with weak typing under strict pyright

`_problem` has no return annotation. `_capture(path=CONCERNS)` in `tests/upstream/test_review_json.py:28` is untyped and uses `# type: ignore[no-untyped-def]`, a mypy-style code. The rules require strict pyright over `tests/` with zero errors. Annotate both functions instead of suppressing.

### [CONCERN] `typed()` returns `Any`, so none of the field readers are type-checked

`typed(raw, key, kind: type, source) -> Any` makes every call site in `ParsedReview(...)` unchecked. A wrong `kind` at a call site, such as `int` where `str` was meant, would not be caught statically. Use a `TypeVar` (`kind: type[T] -> T | None`) so the readers are checked.

### [CONCERN] Provider-failure and findings-not-parsed detection searches the whole body for headings

The `Provider Failure` and `Findings Not Parsed` headings are matched anywhere in the body. That includes text inside fenced code blocks, and text from hand-added sections such as `## Response`, which the tests show are expected. A response that quotes `## Provider Failure` would flip a normal review to `provider_failure=True`. That is loud when the verdict isn't UNKNOWN, but not otherwise. For `Findings Not Parsed` it silently changes `findings_parsed`, and with it the verdict's standing and the record id. This also leans on user-visible text as logical structure, which CLAUDE.md warns against. The headings are centralised and the matching is lenient, which helps. Still, restrict the search to the body before any hand-added section, or at least skip fenced blocks, and add a test for a quoted heading.

### [NOTE] Empty `--upstream-version` is accepted

`_resolve_version` only tests `is None`. `--upstream-version ""` passes through (the `str(supplied)` is redundant) and is rejected later by the store writer as "upstream_version must not be empty". That happens after the CLI has already printed an id and exited 0. Reject a blank label at composition time with `UpstreamVersionError`, as the reader does for blank required keys. Unquoted YAML stamps such as `squadronVersion: 1.0` parse as floats and are rejected with "wrong type". That is loud, so it is acceptable.

### [NOTE] `_compose` reports to stderr before the submission is made

The function is named for composition but prints the "ingest: node ..., slice ..." line, mixing I/O into the compose step. The line also appears even if `submit` then fails. Moving the print next to `submit` would keep `_compose` pure. A leading UTF-8 BOM is also not stripped, because `read_text(encoding="utf-8")` is used rather than `utf-8-sig`, so such a file reports "no frontmatter".

### [PASS] Shared provider-failure rule and payload inverse

The provider-failure rule now has one definition, used by both the store writer and the parser, and a test enforces that. `verdict_to_payload` is verified as an exact inverse of `verdict_from_payload` by round-trip tests. Squadron key names live in one file, also enforced by a test. Parsing is checked against every real captured file, as the project's parsing rules require. The upstream/store import direction is guarded by a test. Exceptions are narrow and chained, with no swallowed errors. `yaml.safe_load` is used, and the command opens no store (D6), which a test checks.

### Run Digest

- Response length: 5381 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 47.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
