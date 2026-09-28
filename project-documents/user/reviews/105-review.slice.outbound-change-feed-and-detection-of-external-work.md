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
reviewedSha: 04522022c31c603814fc5beaf9d3b985b8d2b94e
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "Slice 103's expectation that the feed push submission outcomes (`inbox_submissions.applied_seq`) is dropped without acknowledgment"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:244-250"
  - id: F002
    severity: concern
    category: api-contract
    summary: "`change_head`'s snapshot-then-follow pattern depends on an undeclared store capability and has no test"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:313"
  - id: F003
    severity: concern
    category: error-handling
    summary: "The detection scan introduces the first unbounded external I/O inside the synchronous loop, and hang is the one failure mode not enumerated"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:507"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "The poll-based follower is a defensible reading of \"Push, not poll,\" and the deviation is surfaced rather than hidden"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:192-199"
  - id: F005
    severity: note
    category: scope
    summary: "D7's additive change to completed slice 104's contract is owned, bounded, and tested"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:236-242"
  - id: F006
    severity: note
    category: dependencies
    summary: "The forward dependency on undesigned slice 108 is explicit but is the plan's critical path"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:66-73"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure-mode enumeration for the new I/O paths is explicit and complete on errors"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:145-151"
  - id: F008
    severity: pass
    category: architecture-alignment
    summary: "Dependency directions and layer responsibilities are preserved and mechanically checked"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:393"
  - id: F009
    severity: pass
    category: integration
    summary: "Slice-plan success criteria are fully covered, with the S8 swap requirement met structurally"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:352-357"
---

# Review: slice — slice 105

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Slice 103's expectation that the feed push submission outcomes (`inbox_submissions.applied_seq`) is dropped without acknowledgment

Slice 103's design makes two explicit hand-offs to this slice: its delivery semantics state "Notification of outcome. Submitters poll `submission(id)`. **Push is slice 105**" (103-slice.durable-inbox-and-message-queue.md:309), and its Integration Points name "`messages.seq` and `inbox_submissions.applied_seq` as change sources for the feed" (103-slice.durable-inbox-and-message-queue.md:319). This design delivers the first half — a trigger on `messages` emits `message_posted` — but there is no submission-related `ChangeKind`, no trigger on `inbox_submissions`, and no mention of `applied_seq` anywhere in the tracked-table list, the payload table, the invariant test, or the excluded-scope list. A submitter (initiative 160's bridge, per 103's own doc) that followed 103's contract would expect the feed to carry submission outcomes and finds no kind for it. If omitting submission records from the feed is deliberate (their *effects* — status changes, verdicts, messages — are all on the feed, so arguably nothing actionable is lost), the decision should be stated in this document and reflected back into 103's integration-point text; today it reads as an oversight rather than a decision. Note also that the invariant test's "every tracked table" reconciliation cannot catch this gap, since `inbox_submissions` is not a tracked table.

### [CONCERN] `change_head`'s snapshot-then-follow pattern depends on an undeclared store capability and has no test

The API table specifies `change_head` with "Read it in the same read transaction as a state snapshot, then follow from it" — and the correctness of that pattern genuinely depends on the atomicity: if the snapshot and the head read run in separate implicit read transactions, a commit landing between them is in neither the snapshot nor the follower's stream (the follower starts after head), which silently loses a change — violating the contract's "no gaps" guarantee. Nothing in slices 101–104's documented contracts provides a way to compose multiple read calls into one read transaction; 101's read API is per-call. Yet the "Consumes from Other Slices" section (lines 359-362) declares only triggers, `source_document`, `watch_reviews`, three `ProcessSettings` fields, tenant registration, and two listings — no read-transaction composition primitive. Either the mechanism must be named (e.g., an explicit read-transaction context on the read-only handle, added to the declared contract changes and to `store-contract.md`), or the follower must obtain its starting point differently. Additionally, no functional requirement or walkthrough step exercises this path — the success criteria cover `--after N` resume and process-stopped catch-up, but never the snapshot+head sequence that is `change_head`'s stated purpose.

### [CONCERN] The detection scan introduces the first unbounded external I/O inside the synchronous loop, and hang is the one failure mode not enumerated

The design is thorough on scan failure modes — the baseline table (lines 145-151) and D6's race table (lines 229-234) cover missing directories, unreadable files, files vanishing mid-read, and store failures, and the tick budget (line 507) bounds volume. But 102's standing posture is "no per-tick timeout; the tenant must return promptly," and 102 bounded its own external I/O with `cf_timeout_seconds`. This slice adds directory listing, `stat`, and full-file reads inside that same loop with no bound at all, and its paths are "stored absolute and as given. No symlink resolution" (line 508) — so a watch registered through a symlink to a stalled network mount hangs the tick, and with it the whole synchronous loop including stop handling, with the sole remedy being the operator's `kill -9`. The design explicitly bounds the one subprocess (`sq_timeout_seconds`, no tick ever starts one) but leaves the new filesystem path's latency unaddressed. Even a sentence stating the accepted posture — "watched directories are expected to be local; a hang is the standing 102 remedy" — would close it, and the baseline/detection failure tables are the natural home.

### [NOTE] The poll-based follower is a defensible reading of "Push, not poll," and the deviation is surfaced rather than hidden

The architecture's "Push, not poll" goal (100-arch.substrate-run-state-store.md, Design Goals) targets inbound signals — the resident process learning of CF changes, SQ completions, human replies — and the arch doc's event-seam description itself anticipates "filesystem watching" until Squadron's S8 event lands. D2 meets the goal for both inbound signals this slice owns, and for the outbound surface it states plainly that `follow()` polls `PRAGMA data_version` rather than calling it push, quantifies the cost (`follow_interval_seconds`), scopes the PM decision, and sketches the smallest socket-based upgrade as one that fits behind `follow()` with no subscriber change. This is the right way to handle a tension with a stated goal; it only needs the PM decision recorded when ratified.

### [NOTE] D7's additive change to completed slice 104's contract is owned, bounded, and tested

Modifying a merged slice's schema (`verdicts.source_document`) and query semantics (`finding_changes` series key) is scope beyond 105's plan entry, but the justification is real (multi-part task reviews would corrupt "previous round" without it), the change is additive (nulls preserve every existing series), 104's design document is deliberately left unedited as the record of what shipped, the ownership and CHANGELOG obligations are named, and 104's suite must pass unchanged. The `IS` comparison for null-matching and the rebuilt previous-round index are both specified. This is the correct way to change a finished contract; it stays a NOTE because it is PM-pending and touches 104's consumers (initiative 140's payload gains an optional field, also additive).

### [NOTE] The forward dependency on undesigned slice 108 is explicit but is the plan's critical path

108 has no design yet, yet 105's detection is unimplementable without `parse_review_artifact` and the two recorded requirements (the `ParsedReview.slice` field, and the parsed-content digest as the default record id — the latter load-bearing for idempotency across `amoeba ingest review`, detection, and the Runner). The requirements are stated precisely enough to paste into 108's design, and Development Approach steps 1–4 are correctly decoupled from 108, but step 5 and every end-to-end criterion block on it. Since the slice plan orders 108 before 105, the residual risk is 108's design landing without these two requirements; both should be confirmed present when it is written.

### [PASS] Failure-mode enumeration for the new I/O paths is explicit and complete on errors

Both new I/O paths enumerate their failure modes with handling strategies rather than TBDs: the baseline table covers five registration/scan failure cases including the all-or-nothing rationale (a partial baseline would mis-order `recorded_seq`, which 104's previous-round lookup reads), and D6's table covers the four file-level races with the digest-taken-from-bytes-actually-read rule keeping ledger and parse consistent. The bounded-failure rule correctly adapts 103's crash-loop insight to detection, keys the sidecar under the supervisor directory (never writing into the PM's watched directory), and handles the crash-between-commit-and-sidecar-delete window via ledger idempotency. This exceeds the stated criterion.

### [PASS] Dependency directions and layer responsibilities are preserved and mechanically checked

The store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`; emission lives in triggers rather than writer code, so no writer method changes and no import is needed; the tenant is the only module knowing both parser and store write path, mirroring `InboxTenant`; `follow()` opens read-only so the writer guard survives with only the established demo-script carve-out. D8's choice of triggers over an `_emit_change` call per writer is well argued (recovery's out-of-inbox escalation writes are the case writer-code emission would miss) and the invariant test closes the loop on literal drift between frozen migration SQL and the Python enums.

### [PASS] Slice-plan success criteria are fully covered, with the S8 swap requirement met structurally

Every criterion from the plan's 105 entry maps to a design element: status-change notification (trigger + `node_status_changed`), external review detected with provenance (`record_verdict` via 108, `source: artifact_frontmatter`), provider failure as a failure (trust label passthrough, `review_detected` suppressed for `baseline`/`runner_issued` only), replaceable detection (D6's one-method `ReviewSource` with the ledger key unchanged for S8), and disconnect/reconnect safety (cursor ownership, at-least-once/at-most-once semantics stated with the save-after-acting recommendation). Downstream hand-offs to 106, 107, 120, and 160 match what those entries in the plan and in 103/104 expect — with the single exception noted in the first CONCERN above.

### Run Digest

- Response length: 11685 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 52625
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
