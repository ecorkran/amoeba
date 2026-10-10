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
reviewedSha: ea7414f62ee393b8077a206939d6927131941c40
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
durationSeconds: 27.5
runId: run-20261010-p6-011bdb45
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Source-flag dispatch relies on truthiness, so an empty path crashes"
    location: "src/amoeba/cli/ingest.py:99-101"
  - id: F002
    severity: concern
    category: design
    summary: "The same review ingested onto another node is silently a no-op"
    location: "src/amoeba/cli/ingest.py:118-132"
  - id: F003
    severity: concern
    category: typing
    summary: "Type-suppression comments in test code under strict pyright"
    location: "tests/upstream/test_review_json.py:27"
  - id: F004
    severity: note
    category: parsing
    summary: "JSON reader is not lenient about text before the object"
    location: "src/amoeba/upstream/squadron/review_json.py:30-38"
  - id: F005
    severity: note
    category: parsing
    summary: "Unterminated code fence is not stripped"
    location: "src/amoeba/upstream/squadron/review_artifact.py:36-38"
  - id: F006
    severity: note
    category: style
    summary: "`str(supplied)` is a typing workaround"
    location: "src/amoeba/upstream/squadron/review.py:_resolve_version"
  - id: F007
    severity: pass
    category: design
    summary: "Single definition of the provider-failure rule"
    location: "src/amoeba/store/evidence_models.py:provider_failure_problem"
  - id: F008
    severity: pass
    category: design
    summary: "Layering, constants and test coverage"
    location: "src/amoeba/upstream/squadron/review_fields.py"
---

# Review: code — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Source-flag dispatch relies on truthiness, so an empty path crashes

`--artifact ""` satisfies the required mutually exclusive group, because the flag is present. After that, `Path(args.artifact or args.stdout_json)` evaluates to `Path(None)`, which raises `TypeError`. `_compose` has the same problem: `parse_review_artifact(text) if args.artifact else parse_review_json(text)` would pick the JSON parser. The `TypeError` is not caught by the `OSError`/`SquadronReviewError` handlers, so the user gets a traceback instead of `REVIEW_UNREADABLE`. Test `args.artifact is not None`, or set a `dest`/mode once and use it in both places. The same condition is also written twice, which breaks the project's rule against scattering comparison values.

### [CONCERN] The same review ingested onto another node is silently a no-op

`review_record_id` excludes the node by design (D5). The submission id is also that digest, so ingesting an identical review for a second node is replayed as a no-op. The command prints the id and exits `OK`, which looks like success. The data for the second node is dropped. It is documented in `--help` and pinned by a test. Even so, a zero exit status for a dropped write invites silent data loss. Consider including the node in the submission id, or at least warning on stderr when the id already exists.

### [CONCERN] Type-suppression comments in test code under strict pyright

The rules require strict pyright with tests included, and zero errors is a merge blocker. `_capture(path=CONCERNS)  # type: ignore[no-untyped-def]` should be annotated (`path: Path = CONCERNS`). Other suppressions are `# type: ignore[arg-type]` in `tests/store/test_verdict_to_payload.py` (`_minimal`) and `# pyright: ignore[reportUnknownMemberType]` in `tests/cli/test_ingest.py`. They can be removed by typing the helpers or by narrowing with `cast`.

### [NOTE] JSON reader is not lenient about text before the object

`_decode_first_object` starts at the first `{`. Trailing text is handled and tested. A captured stdout with a leading log line that contains a brace (for example `{debug}`) would fail as malformed JSON. The project prefers lenient parsing. Consider trying each `{` until one decodes to an object with a `verdict` key.

### [NOTE] Unterminated code fence is not stripped

`_CODE_FENCE_BLOCK` needs a closing fence. A hand-edited file with an unclosed fence that quotes `## Provider Failure` would still be read as a provider failure. This is an edge case and fails loudly if the verdict is not UNKNOWN. It is worth a test or a comment.

### [NOTE] `str(supplied)` is a typing workaround

After the checks, `stamp if stamp is not None else str(supplied)` only exists to satisfy the type checker. Restructuring with early returns (`if stamp is not None: ...; assert/raise for supplied`) would make the invariant explicit.

### [PASS] Single definition of the provider-failure rule

The rule is extracted once and shared by the store writer and the parser. A test checks that each reason text is defined in exactly one place.

### [PASS] Layering, constants and test coverage

Squadron key names are defined once and a test enforces it. Import-direction tests keep the store and inbox independent of the upstream package. `verdict_to_payload` has round-trip tests. The parsers are tested against real captured fixtures, including a pinned id and end-to-end crash-recovery runs in throwaway supervisor directories. No test reads a production database URL.

### Run Digest

- Response length: 4117 chars
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
- Duration: 27.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
