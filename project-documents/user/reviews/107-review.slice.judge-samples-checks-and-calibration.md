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
reviewedSha: 47a22f1c1604ac1ba3087c4d04147732c8d69383
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 96795
cachedTokens: 11028
cacheWriteTokens: 85763
completionTokens: 4665
durationSeconds: 39.7
costUsd: 0.391482
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Mechanism is heavier than the slice needs"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D6, D8)"
    resolution: accepted
    resolvedBy: "D8 drops the generic Provenance and ToolSource: RecordSource gains command_output and document. D6's record_progress is a bare insert with no retry rule or extra checks. sql_checks.py and mapping_checks.py merged. Score min/mean/max kept (PM, 20261015): computed on read, nothing stored, cheap, and generally useful"
  - id: F002
    severity: concern
    category: consistency
    summary: "Naming is inconsistent for the concept D1 says must be named consistently"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#API Contracts (CLI table)"
    resolution: accepted
    resolvedBy: "One spelling, --judge-invocation-id, on ingest review, submit verdict, and inspect verdicts; it matches the payload field"
  - id: F003
    severity: note
    category: scope
    summary: "Consensus storage is deferred, while the architecture lists it as store scope"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Scope (Excluded)"
    resolution: no_change_needed
    resolvedBy: "Slice plan entry 107 states consensus records and threshold recommendations are 140's ('Not in 107'), so the deferral is within plan"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "The calibration report stops short of \"surfaces recommendations\""
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D3)"
    resolution: no_change_needed
    resolvedBy: "The deferral is stated and owned by 140, as the reviewer notes"
  - id: F005
    severity: note
    category: architecture-alignment
    summary: "D4 is a stated exception to \"unknown is a value\""
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D4)"
    resolution: no_change_needed
    resolvedBy: "The design already requires evidence-contract.md to state the exception"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction, and writer model hold"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Architecture"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Baseline and vacuous-check requirement is met"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Decisions (D5)"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new write paths"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Data Flow"
---

# Review: slice — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Mechanism is heavier than the slice needs

Several parts have no consumer, or no way to use them, in this slice.

- **D8 (generic `Provenance` and `ToolSource`).** This changes a shipped type from 104 and needs a second source enum. It protects against a verdict being tagged with a tool source. Adding `command_output` and `document` to the existing vocabulary would meet the requirement with no refactor. If the PM wants the types kept apart, the design should justify that against the 104 churn. Right now it only asserts that no guard is needed.
- **D6 (`progress_records`).** The table is write-only, has no record type, and has no inbox kind or listing. Its only test reads rows back through raw SQL. The slice plan assigns the table, so it stays. The surrounding machinery can shrink to a bare insert. `ProgressInput` with node and `upstream_version` checks, `INSERT OR IGNORE` retry semantics, and a `ToolSource` provenance requirement are all speculative until issue #5 defines a reader.
- **Module count.** The design adds seven new modules plus edits to seven existing files: `check_models`, `calibration`, `sql_checks`, `mapping_checks`, `_check_writer`, `checks`, `inspect_checks`, `check_payloads`, and more. The split is justified for the two required ones (pydantic isolation and the writer base). `mapping_checks.py` and a separate `sql_checks.py` for two small tables could merge.
- **Calibration columns.** D3 defines nine columns with no named consumer. 140 is the only one, and it is not designed yet. The score min, mean, and max could be cut or deferred, as the per-criterion means already were (issue #6).

Name for cutting or deferring: D8's generic `Provenance`, the `ProgressInput` validation and retry semantics, and the score statistics in `calibration`.

### [CONCERN] Naming is inconsistent for the concept D1 says must be named consistently

D1 records PM ratification "on condition of clear naming", with the names used "the same way in code, docs, and CLI". The CLI table then gives two flag spellings for one concept: `amoeba ingest review --judge-invocation ID` and `amoeba submit verdict --judge-invocation-id ID`. `inspect verdicts` uses `--judge-invocation`. The submit flag is derived from the payload field name, which explains it but does not meet the condition. Either pick one spelling for all three commands, or state why `submit` must differ and record that the PM accepted it.

### [NOTE] Consensus storage is deferred, while the architecture lists it as store scope

The architecture's Scope and Envisioned State #2 say the store holds "judge invocations and consensus results". The same document puts consensus *aggregation* in 140. This slice stores samples and excludes any consensus record, and it says 140 adds one through the kind seam. That is consistent with the architecture's split between storing and computing. I did not read the slice plan entry, so I cannot confirm the deferral is within what the plan assigns this slice. Please check it against that entry. If the plan assigns consensus records here, dropping them would be a CONCERN.

### [NOTE] The calibration report stops short of "surfaces recommendations"

The architecture's design goal says the store "accumulates calibration evidence and surfaces recommendations". The slice makes the report purely descriptive and gives threshold recommendations to 140. This respects the permanent metrology constraints: no write-back, no live metrology queries, and escalated-gate verdicts inadmissible as agreement data. The report carries no agreement metric, and `evidence-contract.md` warns against consuming it as one. I see no violation. The deferral should stay visible so the "recommendations" half of the goal has an owner, and the slice does name 140.

### [NOTE] D4 is a stated exception to "unknown is a value"

The slice refuses stdout JSON that reports `UNKNOWN` with a score. This conflicts with the architecture principle "Unknown is a value, not a default". The slice owns the conflict openly. It argues that a possibly wrong verdict is worse than a refusal, that the refusal is loud (exit 12 with a reason), and that the unknown case is still recorded through the saved file. It also avoids using template names as logic. squadron#140 is now fixed, so the affected population is shrinking. The exception is acceptable if `evidence-contract.md` states it, which the slice requires.

### [PASS] Boundaries, dependency direction, and writer model hold

- **Storage and layering.** The store never imports pydantic; `CheckPayload` lives in `amoeba.inbox`. `CheckWriter` is a base class so the inbox effect does not import a sibling operations class. Calibration reads `verdicts` only, issues no writes, and never touches Squadron's metrology store.
- **Inbox and writer model.** The `check` kind goes through 103's three-part seam and applies inside `apply_submission`'s transaction. This preserves the sole-writer and inbox-only external write model.
- **Feed.** The feed invariant gets a new `ChangeKind`, and 106's convention is followed.
- **Derived state and provenance.** Check standing and calibration are computed on read, so no data fixes are needed if the rules change. Provenance and `upstream_version` are required on every new record, which matches "provenance on every ingested fact".

### [PASS] Baseline and vacuous-check requirement is met

The architecture requires that a mechanical check carry what was examined and a baseline reference, because validators have exited 0 with `filesChecked: 0`. `CheckInput` stores `examined_count`, `examined`, and `baseline_ref`. The standing function marks `examined_count` 0 as `vacuous` whatever the outcome, and `unattested` when the count is unreported. Diffing against the baseline is correctly left to the Runner (120).

### [PASS] Failure modes are enumerated for the new write paths

The new paths each have explicit handling.

- **Direct writes.** `record_check` and the verdict writer raise `NodeNotFoundError` or `ValueError`. The inbox effects return rejection reasons. Retries of an existing id return the existing record, with a WARNING on differing content.
- **Samples.** The D2 invocation mismatch is rejected with a reason naming both sides and the new-invocation-id remedy. A rejected sample writes nothing, so it cannot define an invocation.
- **Ingest.** A refused stdout capture exits 12 and leaves nothing in `inbox/new/`.
- **Crashes.** The end-to-end proof uses `kill -9` and restart, which covers the architecture's restart-survival requirement.

I found no NFR in the architecture for these paths beyond restart survival and the sole-writer guarantee, and the success criteria cover both.

### Run Digest

- Response length: 8145 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 96795 / 11028 / 85763 / 4665 / not computed
- Duration: 39.7 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
