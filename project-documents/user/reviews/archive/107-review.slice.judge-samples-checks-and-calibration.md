---
docType: review
layer: project
reviewType: slice
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 02fb20c74023d7ac2731c4c99a977b241e6c409b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 179639
cachedTokens: 91180
cacheWriteTokens: 88453
completionTokens: 3977
durationSeconds: 35.6
costUsd: 0.40338
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: architectural-constraint
    summary: "Calibration report knowingly includes data the architecture calls inadmissible"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D3)"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Footprint is heavy for a Low-risk, effort-3 slice; duplicated provenance and speculative table"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Component Structure"
  - id: F003
    severity: note
    category: under-specification
    summary: "Calibration grouping when `model` is not reported"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D3)"
  - id: F004
    severity: note
    category: integration
    summary: "Judge-stdout refusal scope"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D4)"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for the new write paths"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Data Flow"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction, and writer model"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Architecture"
---

# Review: slice — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Calibration report knowingly includes data the architecture calls inadmissible

The architecture lists "escalated-gate verdicts are inadmissible as agreement data" under its permanent metrology constraints. D3 ships a report that includes `split_invocations`, an agreement-style metric, with no filter. Its only mitigation is help text and a doc note, with the fix deferred to issue #4 and initiative 140.

The slice plan's success criteria do not require this filter, so deferral is allowed. Two problems remain:
- A permanent constraint is breached, and the design does not record that the PM has accepted the breach.
- The deferred fix is a schema change. Migration 007 is open now and already alters `verdicts`, so a nullable opaque attribute for gate or invocation context could be added at near-zero cost. Doing it later costs a further migration on a shipped table.

Either add the nullable column now, without filter logic, or record the PM's explicit acceptance of the deviation. Also say whether the unfiltered report may be consumed as agreement evidence in the meantime. D3 is currently marked "pending ratification" only for the columns.

### [CONCERN] Footprint is heavy for a Low-risk, effort-3 slice; duplicated provenance and speculative table

The slice adds about 10 new modules, two tables, a trigger, an inbox kind, and a parallel provenance vocabulary. Parts of that can be cut or deferred:
- **D8 `ToolSource` and `ToolProvenance`.** This duplicates `Provenance` with the same four fields and only a different source enum. A single `Provenance` generic over its source enum, or a shared base, avoids a second type that must be kept in step. The design should justify the duplication against the repo's DRY rule, or drop it.
- **`progress_records` plus `record_progress`, `progress_records()`, `ProgressInput/Record`, and mapping and SQL for the table.** The slice plan assigns "a small record table", so the table is in scope. The in-process writer, reader, and record types have no consumer until issue #5. The table could be created with only the minimal writer, or the reader and tests deferred to the consumer slice. The design should name what it cuts.
- **`criteria_means` in calibration.** The criteria keys vary by template and appear in `--json` only. No consumer is named, so it is a candidate to defer.
- **Separate `_check_writer.py`, `check_payload.py` and `check_payloads.py`.** One module covers payload keys defined once and another the pydantic model. Confirm that both are needed, or merge them.

### [NOTE] Calibration grouping when `model` is not reported

D3 groups by `(review_type, model)`, but the design does not say how a sample with a null or absent model is grouped. The architecture says "unknown is a value" and the repo bans silent fallbacks. State that such samples form an explicit "model not reported" group, not an empty-string or dropped row.

### [NOTE] Judge-stdout refusal scope

The D4 rule is stated on JSON content (`UNKNOWN` plus a score), not on whether the review is a judge template. That is consistent with "never compare the version label". Confirm that no non-judge review legitimately reports `UNKNOWN` with a score, since the refusal would then block it from ingest.

### [PASS] Failure modes for the new write paths

- **Direct calls** raise `NodeNotFoundError` or `ValueError`.
- **The `check` kind** returns a rejection reason, and an unknown vocabulary word is quarantined.
- **Retries** use 104's first-wins rule, with a WARNING when content differs.
- **D2 rejections** write nothing, so a rejected sample never defines an invocation.
- **Crash mid-apply** is covered by `apply_submission`'s single transaction, and the end-to-end `kill -9` test exercises it.

### [PASS] Layering, dependency direction, and writer model

- **Store.** The store stays free of pydantic and of Squadron parsing.
- **Adapter.** The Squadron adapter changes stay in `upstream/squadron`.
- **Check kind.** Writes use the inbox kind seam, so the sole-writer model holds.
- **Calibration.** It is read-only and never touches Squadron's metrology store, and a test asserts this.
- **Consensus.** Consensus is excluded, as the slice plan's "Not in 107" note directs.

### Run Digest

- Response length: 5491 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 179639 / 91180 / 88453 / 3977 / not computed
- Duration: 35.6 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
