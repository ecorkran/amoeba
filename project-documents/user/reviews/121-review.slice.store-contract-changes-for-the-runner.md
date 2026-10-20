---
docType: review
layer: project
reviewType: slice
slice: store-contract-changes-for-the-runner
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: fb75bb062786a7049d73516933b6cc89411c902d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 383467
cachedTokens: 282847
cacheWriteTokens: 100610
completionTokens: 7868
durationSeconds: 72.2
costUsd: 0.510229
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "Refusing `block()` on a done node conflicts with the architecture's orphan escalation"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:137-150"
  - id: F002
    severity: concern
    category: scope
    summary: "D1 enforces more than the plan or architecture assigns, and the extra checks add mechanisms to cut or justify"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:137-150"
  - id: F003
    severity: note
    category: integration
    summary: "The unrouted-outcome query has no named owner"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:197-199"
  - id: F004
    severity: note
    category: layering
    summary: "Runner vocabulary sits in a store module that `Message` imports"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:101"
  - id: F005
    severity: pass
    category: alignment
    summary: "Contract changes align with the architecture and the plan"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#Technical Decisions"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Compound writes, failure handling and the tick-cost NFR are covered"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#State Management"
---

# Review: slice — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Refusing `block()` on a done node conflicts with the architecture's orphan escalation

The architecture asks only that `update_node_status` enforce `done` as terminal. D1 goes further. `_write_block` refuses a done node, so `block()`, `journal_escalate` and a `BlockEffect` all raise `InvalidTransitionError` on one.

The architecture has Runner behaviours that escalate against a node, and a done node can be that node:
- "A node whose index CF no longer reports is never deleted; it escalates as orphaned." A renumbered slice that was already `done` leaves exactly this orphan.
- The per-project fault handler records a fault "against the affected node as a `blocked_on_human` escalation".

With D1 as written, the store refuses both. The fault handler's own escalation write would raise inside the handler. The slice does not say which path a fault on a done node takes. It does not point to the project-scoped escalation, and it does not state that 122 and 123 must treat done nodes as non-blockable.

This is a gap in what the slice hands to 122 and 123. The "Provides to Other Slices" section names the done-terminal guarantee for 127 only. Either of two fixes works:
- State that faults and orphan findings on a done node use `raise_project_escalation`, and record that as a contract rule for 122 and 123.
- Narrow D1 to the status writers the architecture names, and drop the `_write_block` refusal.

### [CONCERN] D1 enforces more than the plan or architecture assigns, and the extra checks add mechanisms to cut or justify

The slice plan entry for 121 says "`update_node_status` enforces `done` as terminal." D1 adds three things beyond that:
- a `journal_issue` refusal on a done node;
- a refusal to mark a node `done` while it has an unresolved journal entry;
- a writer-inventory test on `sql.UPDATE_NODE_STATUS`.

The stated reason is so that recovery never meets a done node. That is a real risk, but D1 also states that no shipped code marks a node done and that "no real store holds" such an entry.

The unresolved-entry check also adds a coupling for 125 and 127. Marking a node done through `update_node_status` or a `StatusEffect` now depends on journal state. Both slices must resolve the entry before the status write.

To fit the plan's scope, keep the `update_node_status` guard and the inventory test. Then either defer the journal-coupled refusals, or add them to 125/127's interface notes and add a failure-mode row for them.

### [NOTE] The unrouted-outcome query has no named owner

Deferring the query is consistent with the plan. The 121 plan entry does not assign it. The architecture's crash-safety rule needs it: "an ingested outcome with no decision record is unrouted, and the next tick routes it."

D5 says it "must land in 125 or 126", and issue #10 tracks it. The slice plan gives 125 the success criterion "a crash between ingestion and routing loses nothing". It would help to name 125 as the owner there. The criterion otherwise rests on a query that no slice's design currently commits to build.

### [NOTE] Runner vocabulary sits in a store module that `Message` imports

`AcknowledgmentOutcome` is generic inbox vocabulary, but it lives in `runner_models.py`, and `inbox_models.Message` imports it. The dependency direction is acceptable, because the store stays below the Runner. The module name suggests the inbox depends on the Runner, though. A neutral home for the outcome enum would keep the layering clear. `Route` belongs with the routing tables.

### [PASS] Contract changes align with the architecture and the plan

The following match the architecture's "Contract changes the Runner needs from 100":
- **Acknowledgment outcomes (D2).** The outcomes are `applied`, `no_op` and `rejected` with a reason, and the submitter can read them. Acknowledging stays once per intent, and a second acknowledgment raises. The departure from the plan's "existing callers unaffected" wording is called out and justified.
- **Project-scoped escalation (D4).** It is deduplicated on project and fault kind. The schema enforces at most one open row. The Runner closes it.
- **Desired states (D3, D8).** They are written in the acknowledging transaction, with drive and hold independent. This matches the architecture's intent model.
- **Routing tables (D5–D7).** Table content is stored on first use, so a decision can be recomputed from its record. The decision fields are inputs, rule id, table version, Amoeba version and route.
- **The wire (D9).** Nothing new goes on it, as the architecture says.

Routing semantics stay with 124 and 126, and the store checks none of them.

### [PASS] Compound writes, failure handling and the tick-cost NFR are covered

Every new I/O path is an in-process SQLite write. Each has validation before the transaction, typed exceptions in a failure-modes table, and rollback tests that inject a mid-write failure. `acknowledge_message` with a desired state and `record_routing_decision` with its effect are single transactions. That closes the crash windows the architecture's crash-safety rule would otherwise leave open.

The architecture's "tick returns promptly" requirement is restated as a bound on the per-tick reads. `open_project_escalations` uses the partial index, `desired_states` returns one row per target, and the unresolved-entry check uses the existing partial index. The read-only handle and the schema-version-8 refusal are also specified.

### Run Digest

- Response length: 6665 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 383467 / 282847 / 100610 / 7868 / not computed
- Duration: 72.2 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
