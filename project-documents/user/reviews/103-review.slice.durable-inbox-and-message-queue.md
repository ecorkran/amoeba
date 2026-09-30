---
docType: review
layer: project
reviewType: slice
slice: durable-inbox-and-message-queue
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260921
dateUpdated: 20260922
reviewedSha: ac3a0dec9c7f8a6786a33f9867d7bf4136163447
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "A `create_project` submission that reliably fails `open_project` can crash-loop the process with no recovery strategy"
    location: "project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md#host-addition-docsprocess-contractmd"
    resolution: accepted
    resolvedBy: "bounded attempt counter; park in inbox/failed/ after inbox_max_attempts"
  - id: F002
    severity: pass
    category: architectural-boundaries
    summary: "Sole-writer boundary is preserved and mechanically enforced"
    location: "project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md#technical-scope"
  - id: F003
    severity: pass
    category: dependency-direction
    summary: "Dependency directions are correct and explicit"
    location: "project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md#component-structure"
  - id: F004
    severity: pass
    category: scope-creep
    summary: "Scope matches the slice plan, including the PM-ratified additions"
    location: "project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md#technical-scope"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Delivery, replay, and crash semantics are enumerated rather than implicit"
    location: "project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md#delivery-and-replay-semantics"
  - id: F006
    severity: pass
    category: integration-points
    summary: "The human-reply channel without a message table is a documented, justified deviation"
    location: "project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md#d4-authoritative-order-is-assigned-by-the-receiver-at-apply"
  - id: F007
    severity: note
    category: nfr
    summary: "No NFR restatement required — parent architecture states no quantitative NFRs"
    location: "project-documents/user/architecture/100-arch.substrate-run-state-store.md"
---

# Review: slice — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] A `create_project` submission that reliably fails `open_project` can crash-loop the process with no recovery strategy

The contract says `open_project` "failure raises and stops the process," and the error-handling rule says an unexpected exception from `open_project` leaves the file in `new/` and stops the process. Combined, a *parseable, valid* `create_project` submission whose `open_project` deterministically fails (e.g., a pre-existing corrupt or future-schema-version store file for that project id, permission issue on the store path) produces: stop → file remains in `new/` → restart → apply loop reaches the same file → raise → stop. This is an unbounded crash loop with no quarantine path — and the doc explicitly rules out quarantining it ("quarantine means 'this submission is bad', never 'the store is unwell'"), while also asserting that only a "sick store" may stop the queue. The design should state a strategy for submissions that persistently fail at apply after passing validation (e.g., operator-acknowledged dead-letter, quarantine with a store-unwell reason after N failures, or at minimum documenting the restart behavior). This is the one new I/O path whose failure mode is enumerated but whose *repeated* failure mode is not.

### [PASS] Sole-writer boundary is preserved and mechanically enforced

The architecture's writer model ("the resident process is the sole writer; the inbox is the one externally-writable surface") is honored literally: `amoeba.inbox` touches only the filesystem, the writer guard's permitted set moves to exactly one module, a new test asserts `amoeba.inbox` has no write path other than `submit()`, and success criteria include "no path exists for an external writer to mutate the store except through the inbox" from the slice plan. D1 explicitly preserves "no process other than the resident one ever opens an Amoeba SQLite file read-write" with no carve-out.

### [PASS] Dependency directions are correct and explicit

`amoeba.inbox` imports vocabularies from `amoeba.store` (models only), `amoeba.store` never imports `amoeba.inbox` (`apply_submission` takes plain validated values), and only the tenant knows both. This matches the architecture's "state is the interface" principle and avoids a hidden circular dependency.

### [PASS] Scope matches the slice plan, including the PM-ratified additions

All included items map to slice plan 103's success criteria (durable append while down, idempotent apply loop, human reply fills a resolution slot, documented semantics, runtime project creation). Exclusions correctly defer message content (160), Runner consumption (120), verdict kinds (104), and push notification (106), each with the consuming slice named. The effort change from 3 to 4 is flagged against the slice plan entry.

### [PASS] Delivery, replay, and crash semantics are enumerated rather than implicit

Every new I/O path has an explicit failure story: the submit path (stray tmp file, retry with same id), the apply loop (per-crash-point table covering before-commit, after-commit-before-delete, mid-`open_project`), quarantine ladder as a closed vocabulary with per-reason success criteria, and a "not guaranteed" list (latency, order, notification, validity, retention) that matches the architecture's "unknown is a value, not a default" stance. The load-tier kill-loop test asserts exactly-once rather than asserting it informally.

### [PASS] The human-reply channel without a message table is a documented, justified deviation

The architecture names inbound human reply as one of three channels; the design terminates it in the resolution slot with the `inbox_submissions` row as its durable record, explicitly reasoning why materializing a message would duplicate the fact. The escalations D3 change (block writer emits the row, including recovery and already-blocked branches) matches the architecture's "escalations (Runner → Translator / notification bridge)" channel definition and the "no intelligence in the substrate" principle — it records that a human block happened, it does not decide escalation policy. Both 102-consumer consequences are recorded as contract changes in the Integration Points section.

### [NOTE] No NFR restatement required — parent architecture states no quantitative NFRs

The parent architecture contains no latency/throughput/availability targets; the slice appropriately bounds what it can (apply latency bounded below by `idle_interval_seconds`, unbounded while down) and defers drain-time bounds to slice 102's measure-first rule with a recorded number, so no NFR is silently dropped.

## Response

**F001 — accepted, resolved in the design on 20260922 (PM-ratified).**

The finding is correct. As written, a parseable and valid submission whose apply deterministically fails had no exit: stop → file first in `new/` on restart → stop. The design forbade quarantining it and also held that only a sick store may stop the queue, which left the two rules with no ground between them.

The design now bounds the stop instead of removing it. The tenant keeps a per-submission attempt counter in a `.attempts.json` sidecar next to the file in `new/` — on disk rather than in the store, because the store is what may be broken, and rather than in memory, because every failure crashes the process. The first `inbox_max_attempts - 1` failures behave exactly as before, so an operator still learns immediately that the store is unwell. On the last one the file and its counter move to a new `inbox/failed/` directory, the tenant logs at ERROR and continues to the next file rather than re-raising.

`failed/` is deliberately not `quarantine/`: the review's own F005 credits the quarantine ladder for being a closed vocabulary meaning "this submission is bad", and a submission the store could not apply is a different fact. Its sidecar carries the last exception, so what stopped the process stays inspectable once the process is up again. Nothing is deleted — an operator who has repaired the store requeues by moving the file back to `new/`, and the counter moves with it, so a requeued file resumes at its recorded count rather than earning a fresh set of attempts.

Changed sections: Data Flow (apply pseudocode), Directory layout, State Management, Error handling (new paragraph), API Contracts (`failed()`), CLI (`inspect inbox`), `open_project` contract row, Success Criteria (two new), and the closing rationale on what may stop the queue. `inbox_max_attempts` joins `inbox_batch_size` as a `ProcessSettings` tunable with a `start` flag.

The six PASS findings and the NOTE need no action.

### Run Digest

- Response length: 6302 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 4493
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
