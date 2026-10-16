---
docType: review
layer: project
reviewType: judge.slice-vs-arch
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba-jcap
verdict: PASS
sourceDocument: project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 6a95b0f16bb0e71e2c002c6641f1dc9798174324
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 96538
cachedTokens: 8619
cacheWriteTokens: 87915
completionTokens: 3552
durationSeconds: 30.3
costUsd: 0.388723
costBasis: provider
runId: run-20261016-judge-cycle-01714217
squadronVersion: 0.22.0
score: 86.0
criteria:
  Architectural goal alignment: 90.0
  Boundaries and layer responsibilities: 88.0
  Scope discipline: 82.0
  Dependency direction and integration points: 90.0
  Failure modes and error handling: 78.0
  NFR restatement: 85.0
  Antipatterns and specification quality: 83.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Progress records skip the provenance guarantee the architecture requires"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Data Flow"
  - id: F002
    severity: concern
    category: scope
    summary: "Consensus and judge-invocation records are deferred relative to the architecture's envisioned state"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Technical Scope"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "Calibration report could be mistaken for admissible agreement evidence"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#D3"
  - id: F004
    severity: note
    category: documentation
    summary: "Architecture's Current State is stale on the stdout `UNKNOWN` bug"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md#Current State"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Metrology and sole-writer constraints are honored"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Special Considerations"
  - id: F006
    severity: pass
    category: integration
    summary: "Contract changes to earlier slices are enumerated and test-backed"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Consumes from Other Slices"
---

# Review: judge.slice-vs-arch — slice 107

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Progress records skip the provenance guarantee the architecture requires

The architecture says "every ingested record stores the upstream version it was parsed from" and requires provenance on every ingested fact. `record_check` rejects an empty `upstream_version`. `record_progress` is "a bare insert" with no validation beyond table constraints. Because `ProgressInput` carries `Provenance`, an empty or blank version could land in the table. The doc should either validate it in the dataclass or state why this table is exempt.

### [CONCERN] Consensus and judge-invocation records are deferred relative to the architecture's envisioned state

The architecture's envisioned state says "Judge invocations record every sample … and the consensus result the Judge computed". The slice stores samples as verdicts keyed by an opaque `judge_invocation_id`. It has no invocation entity and no consensus record, and 140 is expected to add the consensus record later. The deferral is reasonable and explicit, but the architecture document is not updated to match. The two documents now disagree about where the consensus result lives.

### [CONCERN] Calibration report could be mistaken for admissible agreement evidence

The architecture says escalated-gate verdicts are inadmissible as agreement data and that the store exposes calibration evidence as a report. The slice avoids agreement metrics, so it has no escalated-gate attribute and no filter. The report sums over all samples, including ones that may later be known to be escalated-gate. The mitigation is documentation only (`evidence-contract.md`, issue #4). That is acceptable for now, but nothing in the report output marks it as non-agreement data, so a consumer reading `inspect calibration` alone has no warning.

### [NOTE] Architecture's Current State is stale on the stdout `UNKNOWN` bug

The architecture still says stdout JSON "currently reports `verdict: UNKNOWN` for judge templates (bug filed)". The slice records that squadron#140 was fixed in 0.21.9. The architecture should be refreshed. The D4 refusal handles old captures without relying on a version comparison, which matches the "never compared" rule.

### [PASS] Metrology and sole-writer constraints are honored

Calibration is read-only, nothing reads or writes Squadron's metrology store, a test asserts that, and the writer guard is not weakened. All external producers go through the inbox, so the sole-writer and crash-recovery guarantees from the architecture are unchanged.

### [PASS] Contract changes to earlier slices are enumerated and test-backed

Each change to the 102–106 contracts is listed with its test impact: the pinned listing registry, the column test, the feed invariant, and the kind completeness tests. The migration is additive, and a 6→7 upgrade test is required. This leaves little room for hidden coupling.

### Run Digest

- Response length: 7243 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 96538 / 8619 / 87915 / 3552 / not computed
- Duration: 30.3 s
- Cost: $0.39 (provider)
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
