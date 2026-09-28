---
docType: review
layer: project
reviewType: slice
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: c4c6d2c9dc1f4c1683ceab8cdf90e1685f134b19
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Dependency set and integration points match the slice plan and prior slices"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#dependencies"
  - id: F002
    severity: pass
    category: coverage
    summary: "All five plan-level success criteria for 105 are covered by functional requirements"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#success-criteria"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "D2's transport is polling, against the architecture's \"Push, not poll\" goal, and awaits PM ratification"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#d2--subscribers-follow-the-log-themselves-the-process-runs-no-server"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Detection's error handling claims to follow InboxTenant but drops 103's bounded-failure mechanism"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#errors"
  - id: F005
    severity: note
    category: scope
    summary: "D7 modifies completed slice 104's contract"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#d7--a-review-series-is-node-review-type-and-reviewed-document"
  - id: F006
    severity: note
    category: error-handling
    summary: "File vanishing between listing and read is not enumerated"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#d6--one-interface-for-where-reviews-come-from"
  - id: F007
    severity: note
    category: under-specification
    summary: "Runner/detection ordering in D5 rests on an unstated sequencing assumption"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#d5--the-runner-owns-the-reviews-it-launches-detection-defers-then-skips"
  - id: F008
    severity: note
    category: nfr
    summary: "Parent architecture states no numeric NFRs; slice sets its own bounds"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#settings"
---

# Review: slice — slice 105

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Dependency set and integration points match the slice plan and prior slices

The declared dependencies `[101, 102, 103, 104, 108]` match the slice plan's entry for 105 (including both "added at slice design" additions, 103 and 108, each with a stated reason). Consumption claims check out against the consumed designs: the `Tenant` seam and listing registry from 102, the submission-kind seam (enum member + payload model + effect) from 103, `record_verdict` with its retry/idempotency rule from 104, and `EXPECTED_SCHEMA_VERSION` 5 → 6 continuing 101's migration mechanism. The changes to consumed slices are additive and each has a named contract doc and CHANGELOG entry.

### [PASS] All five plan-level success criteria for 105 are covered by functional requirements

Plan criteria — subscriber notified on status change; external review ingested with correct provenance; provider-failure artifact detected as a failure; detection replaceable by an upstream event without changing the subscriber contract (D6's `ReviewSource`); disconnect/reconnect not corrupting feed state (cursor resume, killed-follower test) — each maps to an explicit functional or integration requirement, including the replay-invariant test that catches a write path missing its emission.

### [CONCERN] D2's transport is polling, against the architecture's "Push, not poll" goal, and awaits PM ratification

The architecture's Design Goals state "Push, not poll — the resident process learns … by subscription," and the event seam is described as "publish/subscribe … state-change notifications to subscribers." D2 implements the outbound half as a subscriber-side blocking iterator that wakes on `PRAGMA data_version` checked every 0.25 s — a poll behind a push-shaped API. The design honestly self-flags this ("PM pending — this is the architecture's 'push, not poll' goal, met from the subscriber's side"), states the latency bound in the contract, and shows the socket alternative was considered and rejected for sound reasons (synchronous loop, 102 D2). The rejection reasoning is strong, but the deviation from a stated architectural goal is a PM decision that must actually be made, not left implicit — the same is true of D1, D4, D5, and D7, all marked "(PM pending)". Ratify or reject D2 (and the others) before implementation begins.

### [CONCERN] Detection's error handling claims to follow InboxTenant but drops 103's bounded-failure mechanism

"An exception from the store during detection is re-raised, as `InboxTenant` does." Slice 103's final design does not simply re-raise: a validated submission whose apply fails deterministically re-raises for `inbox_max_attempts - 1` starts (with an on-disk attempt counter) and is then parked in `inbox/failed/`, precisely so "a store that cannot be fixed by restarting cannot hold the process down forever." Under 102's semantics, re-raising from a tenant tick stops the process; a deterministic store failure inside `ReviewDetectionTenant.tick` (e.g. a corrupt or future-schema project store) would therefore crash-loop the process on every start with no bound and no park, the exact failure 103 engineered away. Either justify why the detection path cannot hit a deterministic store failure (and say why the 103 mechanism doesn't apply), or adopt the same attempt-counter/park treatment for the detection tenant.

### [NOTE] D7 modifies completed slice 104's contract

D7 adds `source_document` to `VerdictInput` and the `verdicts` table, regroups `finding_changes` by it, changes the previous-round index, and extends the `verdict` inbox payload — changes to slice 104, which is complete. The change is additive, null-safe for all pre-existing verdicts, justified by the real captured multi-part series, included in migration 006, and routed through `evidence-contract.md` updates. Acceptable, but it is cross-slice scope inside 105 and shares D7's pending-PM status; it should be ratified as one decision.

### [NOTE] File vanishing between listing and read is not enumerated

`DirectoryReviewSource.poll()` returns `DetectedFile(path, bytes, observed_at)`. The design covers half-written files (settle rule), missing/unreadable directories (`unreachable`), and parse failures (`unparseable`), but not the TOCTOU case where a file is deleted or renamed (e.g. PM archiving a round) between the directory listing and the read. One sentence on whether that yields a skipped file, an outcome, or a retry next tick would close the enumeration.

### [NOTE] Runner/detection ordering in D5 rests on an unstated sequencing assumption

D5's defer rule holds while a review-producing journal entry is unresolved, and the skip rule relies on the Runner writing `record_detection(outcome=runner_issued)` for the file. The argument that the Runner's verdict recording "always finishes before detection looks again" assumes the Runner records the verdict (and the ledger row) before resolving the journal entry. That ordering is 120's obligation and is not stated as a requirement anywhere in this doc; it should be named in `evidence-contract.md` alongside the attribution rule, or the window acknowledged.

### [NOTE] Parent architecture states no numeric NFRs; slice sets its own bounds

The architecture document states no latency/throughput targets for the seam, so there is nothing to restate. The slice usefully introduces its own — `follow_interval_seconds = 0.25`, `review_scan_interval_seconds = 2.0`, "detection latency is about two scan intervals," "within a second" for a resolution-driven status change — and commits the follower bound to the contract. Good practice; keep the walkthrough's "within about 5 seconds" consistent with the stated two-interval bound when refining in Phase 6.

### Run Digest

- Response length: 7983 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 17469
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
