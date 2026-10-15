---
docType: review
layer: project
reviewType: slice
slice: squadron-review-parser-and-ingest
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 0c8a499b4df3639cbd9c2af1f6201c5cf920bdc2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 40.7
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Judge-template stdout verdict is ingested as UNKNOWN with no handling"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md#Interfaces Required"
  - id: F002
    severity: concern
    category: project-conventions
    summary: "Body headings are used as logical structure for `provider_failure` and `findings_parsed`"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md#D3"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design weight: sections restate other documents or add machinery nothing yet consumes"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md#Technical Decisions"
  - id: F004
    severity: note
    category: data-integrity
    summary: "File and stdout ids diverge by design, so double-ingest inflates counts, and an id-format change has no migration path"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md#D5"
  - id: F005
    severity: note
    category: error-handling
    summary: "Failure modes for the new I/O path are enumerated"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md#Data Flow"
  - id: F006
    severity: note
    category: integration
    summary: "Dependencies and interfaces frontmatter are slightly inconsistent with the body"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:6-7"
---

# Review: slice — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Judge-template stdout verdict is ingested as UNKNOWN with no handling

The architecture (Technical Considerations, "Verdict provenance") says that for judge templates the store must hold the score-derived verdict read from the artifact, not stdout, until squadron#140 is fixed. The slice notes that stdout JSON still reports `verdict: UNKNOWN` for judge templates (the "Judge templates" bullet). But D3 maps `verdict` straight from stdout through `parse_verdict`, and no behavior is defined for that case. `--stdout-json` on a judge-template capture would silently record an UNKNOWN verdict with a populated `score`. Choose one of three options:
- Refuse with `SquadronParseError` when a JSON capture carries `score`/`criteria` and `UNKNOWN`.
- Mark the record's standing explicitly.
- State that 107 owns this, and add a documented caller rule like the "prefer the file" one.

The success criteria do not cover it either way.

### [CONCERN] Body headings are used as logical structure for `provider_failure` and `findings_parsed`

The project rule says "NEVER use user-accessible labels as logical structure." D3 sets `provider_failure` and `findings_parsed` from the presence of the `## Provider Failure` and `## Findings Not Parsed` headings. Headings are free text in a file the PM hand-edits (for example, by appending a `## Response`). The matching is deliberately lenient: any level, any case. The slice does not say what part of the body is scanned, or whether a heading inside a code fence or quoted finding text counts. A false positive flips a review to `provider_failure`, which is a trust-relevant provenance flag. The heading is the only signal in pre-#139 files, so the exception may be justified. If so:
- Record it explicitly as a scoped legacy exception.
- Prefer frontmatter whenever it is present.
- Define the scan scope, for example top-level headings only, outside fences.
- Add a test with a `## Response` section that mentions the heading text.

### [CONCERN] Design weight: sections restate other documents or add machinery nothing yet consumes

The core deliverable is a pure parser plus one CLI command. Several parts can be cut or deferred:
- **D6 outcome table.** The four-outcome table restates 103's submission lifecycle. Replace it with a pointer to 103.
- **Verification Walkthrough.** Nine steps, with a bash harness, restate what the Success Criteria and the e2e test already pin. Keep two or three steps.
- **Parse-time provider-failure check.** The `provider_failure_problem` extraction touches slice 104's writer purely to fail earlier at the CLI. The same contradiction already ends as a visible `rejected` submission. The refactor is defensible against drift, but it is the heavier option. A lighter one is to call the check only from the parser and leave the writer alone until a second caller exists.
- **`--id` and `record_id=` overrides.** Their only named consumer is the 120 Runner, which does not exist yet. D7's recovery path is the one in-slice use. The digest-format-tag governance paragraph could also move to the contract doc.

### [NOTE] File and stdout ids diverge by design, so double-ingest inflates counts, and an id-format change has no migration path

The slice documents the consequences honestly: two records, `times_seen` doubled, and findings reported as `recurring` against themselves. Mitigation is only a caller rule ("ingest the file when it exists"), and nothing enforces it. The architecture wants cross-run questions answerable from the store alone, so the overcount is a known fidelity gap. Separately, D5 says any change to the digest's covered fields, including adding a `ParsedReview` field, changes every id. Records already stored under the old id would then be re-recorded as duplicates. The slice requires a new format tag and a CHANGELOG entry but gives no reconciliation story. That is acceptable now, but 106's ledger should be aware of it.

### [NOTE] Failure modes for the new I/O path are enumerated

The slice maps unreadable file, parse failure, version conflict, refused submission, missing store, and the residual check-versus-drain race to explicit exit codes. For each it states that nothing reaches `inbox/new/`. Exception handling follows the project rule: narrow catches, with no catch of plain `ValueError`. The architecture states no NFR numbers for this path, so none need restating.

### [NOTE] Dependencies and interfaces frontmatter are slightly inconsistent with the body

The slice adds 103 and 101 as dependencies beyond the slice plan and says so, which is fine. The body lists Initiative 120 as a consumer under "Provides to Other Slices", but `interfaces` names only 106, 107, and 110. Align them, or state that 120 is outside slice indexing.

### Run Digest

- Response length: 6026 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 40.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
