---
docType: review
layer: project
reviewType: slice
slice: judge-samples-checks-and-calibration
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: b278eee5d2b1ce1c75d1f315d618a5bb28dff158
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Strong alignment with the architecture's stated scope and principles"
    location: "project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md#Overview"
  - id: F002
    severity: pass
    category: alignment
    summary: "Provenance and vocabulary principles upheld"
    location: "project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md#D5"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes on new write paths are enumerated, not TBD"
    location: "project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md#Error handling"
  - id: F004
    severity: pass
    category: dependencies
    summary: "Dependency directions and integration points are consistent"
    location: "project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md#Dependencies"
  - id: F005
    severity: note
    category: scope
    summary: "106's wording says \"the inbox kind for judge samples\"; 109 reuses the `verdict` kind"
    location: "project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md#Inbox"
  - id: F006
    severity: note
    category: alignment
    summary: "NFR restatement not applicable — no performance targets in the parent"
    location: "unverified"
  - id: F007
    severity: note
    category: under-specification
    summary: "Calibration report's known overcount is documented rather than hidden"
    location: "project-documents/user/slices/109-slice.judge-samples-checks-and-calibration.md#D4"
---

# Review: slice — slice 109

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Strong alignment with the architecture's stated scope and principles

The slice stays inside the parent's scope for this component: judge samples, calibration evidence, the SQ 280 typed artifacts (`task_progress`, `devlog`, with `review_findings`/`checkpoint` correctly deferred to 104 and 101), and the `filesChecked: 0` baseline-health problem called out in the parent's "Baseline, not absolute, health signals" consideration (D5's `vacuous`/`unattested` standings answer it directly). The exclusion list explicitly keeps consensus aggregation, threshold recommendation, and escalated-gate filtering in initiative 140, honoring "No intelligence in the substrate" and the metrology constraint ("never writes outside the project store", "never mutates a threshold").

### [PASS] Provenance and vocabulary principles upheld

Every new record carries `Provenance` with non-empty `upstream_version`; vocabularies are `StrEnum`s defined once (`check_standing`, `WorkRecordKind`, `CheckOutcome`); unknown is a value (`examined_count: None` → `unattested`, no defaults). Column names and provenance columns are defined once and shared rather than repeated.

### [PASS] Failure modes on new write paths are enumerated, not TBD

The D2 cross-node precondition is handled explicitly on both paths (`ValueError` direct; `rejected` with reason through the inbox, via an explicit branch in `_verdict_rejection`, not exception catching). Precondition rejections for checks/work records (negative count, count/examined mismatch, empty name, unknown node, empty `upstream_version`, non-object content) and replay semantics (first-wins, WARNING on content mismatch) are all specified. Success criterion for the inbox rejection names the exact observable. There are no new network/message I/O paths in this slice (checks are in-process by design and the exclusion of inbox kinds for them is justified), so hang/timeout/disconnect handling does not apply here.

### [PASS] Dependency directions and integration points are consistent

Consumes from 104/105/108 as designed; the migration-006 coupling with 105 is explicitly acknowledged with a fallback (this slice takes 006 if 105 slips, and 105 rebases). Provides to 106 match 106's stated expectation (`106-slice.contract-proof-and-hardening.md:70` — judge samples submitted by the out-of-process Judge actor; line 110/124). Writer model is respected: samples arrive via the inbox for the out-of-process Judge; checks/work records are in-process writes by the resident-process Runner, consistent with the parent's writer model. The 105 change-feed extension is deferred, not added speculatively.

### [NOTE] 106's wording says "the inbox kind for judge samples"; 109 reuses the `verdict` kind

106 (line 70) phrases its dependency as "the inbox kind for judge samples and its read method", while 109 deliberately extends the existing `verdict` kind with an optional key rather than adding a kind. Functionally equivalent — 106's actor calls `amoeba submit verdict` (its line 110) — but the two documents use slightly different terminology for the same seam. Cosmetic; no action needed unless doc reconciliation matters.

### [NOTE] NFR restatement not applicable — no performance targets in the parent

The parent architecture states no latency/throughput NFRs for this path; the slice's "pure function, no SQL" rationale for calibration and the indexed D2 lookup are the closest performance-relevant statements and are adequately justified. Nothing to restate.

### [NOTE] Calibration report's known overcount is documented rather than hidden

The `split_invocations` cross-row overcounting is stated in the contract and tested in the success criteria, and per-invocation detail is available via the filter — honest handling of a descriptive-only report.

### Run Digest

- Response length: 4587 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 1501
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
