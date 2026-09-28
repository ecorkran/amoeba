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
reviewedSha: a15951619db092c0a14fbb8906bc47d31423489d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: concern
    category: specification
    summary: "Delivery-guarantee sentence inverts the at-least-once condition"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:296"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure modes for first-activation baseline are not enumerated"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:300"
  - id: F003
    severity: concern
    category: documentation
    summary: "Settings count inconsistent: \"two fields\" vs. three listed for ProcessSettings"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:331"
  - id: F004
    severity: pass
    category: architecture-alignment
    summary: "Ownership and defer/skip rule matches the architecture's detection-ownership principle"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:198-214"
  - id: F005
    severity: pass
    category: error-handling
    summary: "New I/O path failure modes carry explicit handling strategies"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:216-221"
  - id: F006
    severity: pass
    category: nfr
    summary: "NFR treatment: targets stated where the parent sets none"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:265-272"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "D7's additive change to completed slice 104's contract is owned and safe"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:223-229"
  - id: F008
    severity: note
    category: architecture-alignment
    summary: "\"Push, not poll\" deviation for the outbound surface is documented but unratified"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:182"
  - id: F009
    severity: note
    category: under-specification
    summary: "Unattributed reviews are terminal in detection; the recovery path is only implied"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:191-196"
---

# Review: slice — slice 105

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Delivery-guarantee sentence inverts the at-least-once condition

The line reads: "Delivery to a subscriber is therefore at-least-once only if the subscriber saves its cursor before acting; the contract says to save after." This is backwards and self-contradictory: saving the cursor *before* acting gives at-most-once (a crash between save and act loses the change); saving *after* acting gives at-least-once (a crash after acting but before saving redelivers). The trailing clause states the actual recommendation, so intent is recoverable, but this bullet sits in `docs/feed-contract.md`'s source material, and the slice's own Integration Requirements demand that document be sufficient "for initiative 160's slice design to consume the feed without reading the code." The slice plan's success criterion "Subscribers that disconnect and reconnect do not corrupt feed state" depends on this paragraph being unambiguous. Rewrite to state both outcomes explicitly: save-after yields at-least-once with possible duplicate effects; save-before yields at-most-once with possible loss.

### [CONCERN] Failure modes for first-activation baseline are not enumerated

The D6 table (lines 216–221) thoroughly covers scan-time races, and line 252 covers an *established* watch becoming missing/unreadable (`unreachable`, process keeps running). Unspecified is the case where the directory is missing, unreadable, or not a directory at the moment `watch_reviews` is *first applied*: "First activation baselines existing files inside the same transaction" (line 300; data flow at lines 133–139). Because the watch upsert and baseline share one transaction, a listing failure rolls back the registration too — so does a nonexistent directory (a) quarantine as invalid payload (only "relative path" is named invalid), (b) fail the apply and ride 103's attempts ladder until parked — leaving the watch permanently unregistered and requiring sidecar surgery to retry, or (c) register a watch that immediately reports `unreachable`? Each has a different operator-recovery story, and only (c) matches the lenient behavior the scan path already chose. Enumerate these cases the way D6 does.

### [CONCERN] Settings count inconsistent: "two fields" vs. three listed for ProcessSettings

The Consumes section says "`ProcessSettings` gains two fields," but the Settings section (line 263) adds three to `ProcessSettings` with CLI flags: `review_scan_interval_seconds`, `sq_timeout_seconds`, and `detection_max_attempts` (only `follow_interval_seconds` and `feed_batch_size` live in `FeedSettings`). This line is what 102's owners read when updating their contract; correct it to three.

### [PASS] Ownership and defer/skip rule matches the architecture's detection-ownership principle

D5 implements the architecture's rule — "the Runner owns the control surface... the seam owns detection only of things nobody in Amoeba issued" — via defer (open review-producing journal entry → skip the project) then skip (`runner_issued` ledger mark). The five stated preconditions check out against 102's actual design: synchronous host loop (102:169), journal-before-issue, and recovery running before any tenant ticks (102:514). The residual hole (recovery resolves an entry by observation without the Runner's mark) is acknowledged and made benign by the parsed-content digest, which turns the overlap into a `record_verdict` retry — consistent with the architecture's "Unknown is a value" and command-before-result principles.

### [PASS] New I/O path failure modes carry explicit handling strategies

The D6 table gives each scan-time race a named outcome (file gone before read → dropped, no ledger row; changed between settle and read → digest of bytes actually read; `PermissionError` → WARNING and skip; non-regular/non-md → ignored). Store-recording failures reuse 103's bounded-failure machinery — attempts sidecar written before the transaction, re-raise below the limit, park and continue at the limit, sidecar delete on success, including the crash-between-commit-and-delete window (lines 252–262). The `sq --version` subprocess has a timeout and an explicit unavailable marker, verified against 102's `cf --version` pattern (102:196). A parse failure is an outcome, not an exception. The only gap is the registration-time case above.

### [PASS] NFR treatment: targets stated where the parent sets none

The architecture document states no numeric targets, and the slice says so explicitly rather than inventing inherited ones. It then sets specific targets with reasoning (scan 2 s → detection within ~5 s; follow 0.25 s; `sq --version` timeout 10 s matching `cf_timeout_seconds`; attempts 3 matching `inbox_max_attempts`) and marks exactly which one is contractual ("within `follow_interval_seconds` of the commit, plus the time to read the new rows") — the right shape when the parent sets no NFR.

### [PASS] D7's additive change to completed slice 104's contract is owned and safe

Changing `finding_changes`' grouping on a shipped slice is scope this slice must justify, and it does: 104's design document stays untouched as the historical record; migration 006 adds a nullable column; `IS` comparison means two nulls match, so every pre-105 verdict keeps 104's behavior and 104's suite passes unchanged; the rebuilt previous-round index `(project_id, node_id, review_type, source_document, recorded_seq)` matches 104's actual index (104:288) plus one column; and a `CHANGELOG` entry names the contract change. The motivating multi-part case is drawn from the captured 102 fixtures, not hypothetical.

### [NOTE] "Push, not poll" deviation for the outbound surface is documented but unratified

The design's reading — the goal governs *inbound* signals the resident process learns, all three of which this slice or its predecessors cover — is defensible, and the interval wake on `PRAGMA data_version` is labeled polling rather than dressed up as push, with a costed push sketch (datagram sockets) that fits behind `follow()` and 102's D2 reversal note. Keep in mind that five decisions sit at "(PM pending)" (D1, D2, D4, D5, D7) with no consolidated ratification list, unlike 103's "Project Manager decisions" summary; record the outcomes there so the pending set is auditable.

### [NOTE] Unattributed reviews are terminal in detection; the recovery path is only implied

Because the ledger skips any known `(project, path, digest)` (line 151), a review detected before its slice node exists is recorded `unattributed` and never re-examined even after the node appears — correct under "never guessed," and visible on the feed and in `inspect detections`. Recovery exists (a hand edit produces a new digest, per walkthrough step 8, or `amoeba ingest review`), but the doc states the retry rule only for the `unparseable` outcome (line 335). One sentence making the unattributed recovery path explicit would close the asymmetry.

### Run Digest

- Response length: 9383 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 66090
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
