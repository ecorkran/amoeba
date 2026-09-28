---
docType: review
layer: project
reviewType: slice
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: f3501a12511ec278333820d7b74f469bddc10a4b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Scope and adapter placement match the architecture's explicit slice-108 ownership"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:166"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Dependency directions and the writer model are correct"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:116-121"
  - id: F003
    severity: pass
    category: alignment
    summary: "Architectural principles are carried into concrete rules"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md#patterns-and-conventions"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes for every new I/O path are enumerated with explicit handling"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:249-256"
  - id: F005
    severity: pass
    category: integration-points
    summary: "Cross-slice integration claims are accurate against the sibling designs"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md#integration-points"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Ingest never states whether `--node` is validated against the parsed review's `slice`"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:142-153"
  - id: F007
    severity: note
    category: conventions
    summary: "The file/stdout dual-id tradeoff produces duplicate finding rows and is accepted; make the evidence-contract say so"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:240"
  - id: F008
    severity: note
    category: conventions
    summary: "The provider-failure invariant now exists in two layers; pin their equivalence"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:210"
  - id: F009
    severity: note
    category: alignment
    summary: "Five technical decisions are correctly flagged as pending PM ratification"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:162"
---

# Review: slice — slice 108

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Scope and adapter placement match the architecture's explicit slice-108 ownership

The architecture's Scope paragraph assigns "parsing of Squadron **review output** (`sq review --output json` stdout and review artifacts) into verdict records, as an adapter outside the store" to slice 108, and excludes other SQ/CF parsing (initiative 120). The slice's D1 and its Excluded list match line for line, including keeping run files in `process/observers/sq_runs.py` (a module that exists) and deferring CF MCP results to 120. No scope creep: the `verdict_to_payload` inverse and the PyYAML promotion are the minimum needed for the CLI to write through 103's inbox.

### [PASS] Dependency directions and the writer model are correct

`amoeba.upstream.squadron` imports only store vocabularies/dataclasses (`evidence_models` — verified `FindingInput`, `RecordSource`, `parse_verdict`, `parse_severity` live there); the store never imports upstream; `cli/ingest.py` is the only module that knows both parser and inbox. Ingest writes through 103's inbox as an outside writer, exactly per the architecture's writer model ("the inbox is the one surface that parts *outside* the resident process write to directly"). The import-direction assertions (line 334) make this mechanical. The frontmatter dependency correction (103 added at slice design) is documented, and no dependency cycle exists (105 depends on 108; 108 does not depend on 105).

### [PASS] Architectural principles are carried into concrete rules

Provenance (source, `fallback_used`, provider-failure flag, `sq_run_id`, `reviewed_sha`) is fully mapped per the architecture's "Provenance on every ingested fact." "Unknown is a value, not a default" becomes the explicit raise list (line 215) plus the lenient-parsing rules the project's parsing guidelines require. D4 guarantees a non-empty `upstream_version` on every record, matching the architecture's schema-versioning-against-unversioned-upstreams consideration and 104's published "never compared, only recorded" contract (`docs/evidence-contract.md:143-147`). D5's parsed-content digest is exactly what 105's Interfaces Required demanded (105 lines 72-73), including the raw-bytes-digest rejection rationale.

### [PASS] Failure modes for every new I/O path are enumerated with explicit handling

The data flow maps each step's failure to a specific exit (read → `OSError`/`UnicodeDecodeError` → 12; parse → `SquadronParseError` → 12; version → `UpstreamVersionError` → 12; submit → `InboxSubmitError` → 9), states that nothing reaches `inbox/new/` on any failure, and each raise case has a named test (line 326). `cli/ingest.py` deliberately does not catch plain `ValueError`, so genuine bugs reach the boundary handler as `FAILURE` — consistent with the project exception rules. Every I/O path is local (file read, atomic inbox drop), so hang/timeout/mid-send-disconnect modes from the checklist don't arise; the one subprocess-shaped risk is correctly assigned to 105/120, not here. The architecture states no numeric NFRs (confirmed: 105 records the same), so nothing needed restating.

### [PASS] Cross-slice integration claims are accurate against the sibling designs

105's "From slice 108" requirements (`ParsedReview.slice`, `source_document` exposure, parsed-content digest, `parse_review_artifact`/`to_verdict_input`, error text as the `unparseable` detail) are all delivered or explicitly deferred with 105's agreement (the `source_document` pass-through lands in 105 per its D7; both documents state this identically). The `source_document`-null consequence is even coherent with 105's D7 series grouping (`IS` semantics on null). 106's `run_pruning.py` sibling-module claim is verified in 106's component structure. 109's forward hook (`score`/`criteria` already parsed) matches 104's split.

### [CONCERN] Ingest never states whether `--node` is validated against the parsed review's `slice`

The parser carries `ParsedReview.slice` (line 271), and 105's recovery flow routes unattributed files to `amoeba ingest review --node ID` for the node attribution *would have* chosen. But the ingest data flow and CLI contract take `--node N` purely from the operator and enumerate failures only for read, parse, version, and submit. Nothing says whether ingest cross-checks the parsed `slice` against the target node's `cf.slice_name` (or warns on mismatch). Without a stated rule, a wrong or mistyped node id records a verdict on the wrong node: the store accepts it (104 checks existence only), dedupe cannot help (different digest id), and it silently pollutes that node's review series — exactly the class of quiet mis-record the Risk Assessment section says is "worse than not recording." The fix is cheap: state the rule explicitly — either a mismatch warning/error when both the parsed slice and the node's `cf.slice_name` are known (no-ops for PR reviews, which have no `slice`), or a documented sentence in the API contract explaining why the check is deliberately omitted. The project's own "fail explicitly" principle favors the former.

### [NOTE] The file/stdout dual-id tradeoff produces duplicate finding rows and is accepted; make the evidence-contract say so

D5 correctly accepts that a file and a stdout capture of the same review get different ids, and walkthrough step 7 (line 420-422) deliberately shows each finding key twice in `inspect findings`. The design's justification (105's D5 routes everything through the file) plus 105's D7 `source_document` grouping keeps *series* coherent, but the `findings` listing itself will double-count whenever both paths are used. Consider one sentence in the new "Parsing Squadron output" contract section telling readers that `inspect findings` counts per record id, so a file+stdout pair shows twice.

### [NOTE] The provider-failure invariant now exists in two layers; pin their equivalence

The "provider failure ⇒ verdict UNKNOWN, no findings" rule is enforced at parse time (108, fail-fast with the filename) and again at record time (104's store check, as a rejection). The fail-fast rationale is sound, but this is a duplicated predicate across layers, which the project's DRY rule warns about. Either define the check once and import it (the upstream→store-models import direction already exists) or add a test asserting both implementations agree, so they cannot drift.

### [NOTE] Five technical decisions are correctly flagged as pending PM ratification

D2–D6 are marked pending; D1 carries PM direction from the 104 split. This is the right process posture, not a defect — but the slice cannot move to task breakdown until the PM rules, and D5 (the record-id format) is the one with cross-slice consequences if it changes (105 and 120 both consume it).

### Run Digest

- Response length: 9434 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 37353
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
