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
reviewedSha: 8688c0235c869e6c61cea8e65151ffb3c13f5bd3
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 477894
cachedTokens: 374469
cacheWriteTokens: 103413
completionTokens: 6202
durationSeconds: 54.4
costUsd: 0.513948
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Contract changes match the architecture and the slice plan"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#Overview"
  - id: F002
    severity: pass
    category: architecture
    summary: "Atomicity requirements are implemented where the architecture demands them"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#D3"
  - id: F003
    severity: pass
    category: nfr
    summary: "Tick-cost NFR is restated with bounds"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#State-Management"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Decision-record API fixes semantics that the slice itself assigns to 126"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#D5"
  - id: F005
    severity: note
    category: scope
    summary: "Acknowledgment signature departs from the plan's wording, and the departure is documented"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#D2"
  - id: F006
    severity: note
    category: integration
    summary: "The unrouted-outcome query is deferred, but the architecture's crash-safety claim depends on it"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#D5"
  - id: F007
    severity: note
    category: error-handling
    summary: "A pre-009 store with an unresolved entry on a done node fails startup"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#D1"
---

# Review: slice — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Contract changes match the architecture and the slice plan

The slice covers every item the architecture assigns to it: `done` enforced as terminal, acknowledgment outcomes, project-scoped escalation deduplicated on project and fault kind, and the four tables added through the migration mechanism. The run-id and observer items stay in slice 120, which matches the plan. The contracts-first ordering is kept, and each new write path is store code that the Runner calls through the public API.

### [PASS] Atomicity requirements are implemented where the architecture demands them

The architecture requires that applying an intent and acknowledging it share one transaction. D3 does this by passing the desired state into `acknowledge_message`. D5 makes the decision record and its node effect one write, so a crash cannot leave a routed node that never advances. Both compound writes have rollback tests, and each new failure condition maps to an explicit exception type.

### [PASS] Tick-cost NFR is restated with bounds

The architecture requires the tick to return promptly. The slice ties each per-tick read to an index or to a bound set by current state: `open_project_escalations`, `desired_states`, and the unresolved-command check. History reads are per node or per id. The slice sets no numeric latency target, but the architecture states none for the store either.

### [CONCERN] Decision-record API fixes semantics that the slice itself assigns to 126

D5 says that which route needs which effect, which routes count attempts, and how the limit is compared "stays with 126". Yet `record_routing_decision(decision, *, table, effect, attempt_step)` already fixes the effect types, the attempt-increment hook, and `route_parameters` as part of the store contract. The slice plan's "Tables before their consumers" note says a table whose shape depends on 125 or 126 should move to its consumer slice. The slice instead keeps the shapes and offers a later forward-only migration as the fix. That leaves two risks:
- A wrong shape can only be corrected by adding another migration.
- 121 absorbs design work that belongs to 126.

What to cut or defer:
- Cut `routing_decision(decision_id)`. The doc names no consumer for it. `routing_decision_for_entry` and `routing_decisions(node_id)` cover the stated needs (126, 127, 129).
- Either drop `StatusEffect` and `BlockEffect` from this slice and keep only the decision, table-version and attempt-increment write, or record in 126's slice entry that it may revise the signature. The `done` guard already lives in `update_node_status`, so 126 can call it. The transaction-sharing argument in D5 is legitimate. Keep the compound write only if 121 also names the minimum 126 needs, and avoid designing the full effect surface now.
- Drop the writer-inventory test (D1) if the existing writer-guard tests already cover new `UPDATE_NODE_STATUS` call sites. As written it duplicates that guard.

### [NOTE] Acknowledgment signature departs from the plan's wording, and the departure is documented

The plan says existing acknowledgment callers are "unaffected". D2 makes `outcome` required, so each caller must change. This follows the no-silent-defaults rule and is called out explicitly. The only callers are the stand-in Runner and the message tests, and both are updated in this slice. The behaviour is unchanged: one acknowledgment per intent, and a second raises. No action is needed.

### [NOTE] The unrouted-outcome query is deferred, but the architecture's crash-safety claim depends on it

The architecture's "a crash between ingestion and routing loses nothing" relies on a store query for ingested outcomes with no decision record. The plan does not assign that query to 121. D5 defers it to 125/126 and tracks it in issue #10, giving a reason: which entries need routing is their call. That is acceptable. Make sure 125's or 126's slice entry carries the query, so it is not dropped when those slices are designed.

### [NOTE] A pre-009 store with an unresolved entry on a done node fails startup

If an older store already holds an unresolved entry pointing at a done node, `_write_block` raises when recovery reaches it. The process then fails at start with an error naming the node. This is explicit and loud, and it avoids a silent move out of `done`. The case should be rare, because the old code never enforced `done` but also had no path that created this state.

### Run Digest

- Response length: 5665 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 477894 / 374469 / 103413 / 6202 / not computed
- Duration: 54.4 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
