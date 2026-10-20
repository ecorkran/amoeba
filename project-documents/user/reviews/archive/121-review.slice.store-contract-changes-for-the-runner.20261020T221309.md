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
reviewedSha: 947ff954cf1e11c64c0f99053ec8949e9d74d54f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 285483
cachedTokens: 187213
cacheWriteTokens: 98262
completionTokens: 8607
durationSeconds: 74.7
costUsd: 0.498657
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Contract changes line up with the architecture and the plan entry"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#Technical Decisions"
  - id: F002
    severity: concern
    category: proportionality
    summary: "The `done`-node branch in recovery adds a new escalation shape for a case the slice calls unreachable"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:135"
  - id: F003
    severity: concern
    category: boundaries
    summary: "\"No store write moves a `done` node\" is enforced at three call sites with no inventory of the others"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:133-136"
  - id: F004
    severity: concern
    category: performance
    summary: "`entries_without_decision` runs on the per-tick path with no index or bound, and the tick NFR is not restated"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:175"
  - id: F005
    severity: note
    category: alignment
    summary: "Required `outcome` departs from the plan's \"existing callers are unaffected\""
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:141"
  - id: F006
    severity: note
    category: integration
    summary: "Merge-policy recording is moved to 128 and no longer matches the architecture's wording"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:281"
  - id: F007
    severity: note
    category: error-handling
    summary: "Failure-mode coverage is spread across decisions, and one reference is dangling"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:211"
  - id: F008
    severity: note
    category: scope
    summary: "D5 and D8 fix shapes ahead of their consumers"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md#D5 — A routing decision and its effect are one write"
---

# Review: slice — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Contract changes line up with the architecture and the plan entry

- **Acknowledgment and desired state (D2, D3):** the outcome is `applied`, `no_op` or `rejected` with a reason. Desired state is written in the same transaction as the acknowledgment, as the architecture requires.
- **Project-scoped escalation (D4):** it is a `messages` row with no blocked state. It is deduplicated by a partial unique index and closed by the Runner, as the architecture describes.
- **Tables and the wire (D5–D8, D9):** the four tables are added through a migration, and decision records are recoverable from the stored table version. Nothing is added to the feed, matching "nothing new on the wire".
- **Dependency direction and boundaries:** the slice is store-only and adds no Runner behaviour. Routing-table grammar, fault kinds, the intent body and runnability are explicitly left to 122–126. The slice carves out the run-id and observer work for 120.

### [CONCERN] The `done`-node branch in recovery adds a new escalation shape for a case the slice calls unreachable

D1 adds a third branch to `journal_escalate` and a new `_write_node_escalation` helper. The helper writes an escalation row that has a `node_id` but no blocked-state id.
- The design says the branch "should not be reachable" in v1.
- The branch breaks the invariant that every node escalation goes through the one block writer.
- Because the row has no blocked state, it also sits outside the architecture's "one open blocked state per node" dedup.
- It adds a row shape that `docs/inbox-contract.md` and every escalation consumer must now handle. The doc admits this at line 267.

The plan's criterion is only "Moving a `done` node to any other status raises." Enforcing that in `update_node_status` and `block()` meets it.

Cut `_write_node_escalation` and the contract text for the new row shape. Defer the recovery branch until a path to it exists. If recovery must not raise, the smallest option is to mark the entry `unknown`, log at ERROR, and leave the node unchanged. If the branch stays, say which concrete requirement it meets that the lighter option does not.

### [CONCERN] "No store write moves a `done` node" is enforced at three call sites with no inventory of the others

D1 rejects putting the check inside `_write_block` and instead has `update_node_status`, `block()`, `StatusEffect`/`BlockEffect` and the recovery branch each call `_refuse_done`.
- The goal and the architecture say `done` is terminal on every write path. The design never lists every writer of node status or every `_write_block` caller. Examples are recovery paths other than `journal_escalate`, observers that mark a paused run `blocked_on_sq_checkpoint`, and attribution.
- A path that forgets the call silently reopens the gap.
- Success Criteria test only the paths named above.

Add an explicit inventory of status writers to the design. Add a test that fails when a new status-writing statement exists without the terminal check. Alternatively, put the check in the shared writer layer and keep the recovery exception as the explicit special case.

### [CONCERN] `entries_without_decision` runs on the per-tick path with no index or bound, and the tick NFR is not restated

The architecture says "The tick never waits": `tick()` returns promptly and has a deadline. It also says routing works by finding "an ingested outcome with no decision record". `entries_without_decision` is that query, and the Runner will call it every tick for every project.
- Over time it scans all resolved entries of a kind and anti-joins them against `routing_decisions`.
- The only index the DDL sketch names for this path is the unique index on `routing_decisions(journal_entry_id)`.
- No index on `command_journal` for project, kind and status is mentioned.
- The result is unbounded in size and has no limit.
- The slice does not restate the tick NFR or any target for this read.

State the NFR: the read must not grow with history. Specify the supporting index and either a `limit` or an ordering that lets the Runner take a bounded batch per tick. Add a test that checks the query plan or runs on a store with a large resolved history.

### [NOTE] Required `outcome` departs from the plan's "existing callers are unaffected"

The architecture calls the acknowledgment change additive. The plan's criterion says existing callers are unaffected. D2 makes `outcome` a required argument, which changes the signature, and updates the stand-in Runner and tests. The reasoning is sound: it avoids a silent default and keeps the once-only semantics. Update the plan wording so the documents agree. The claim that the only callers are the stand-in and the message tests should be backed by a search at task time.

### [NOTE] Merge-policy recording is moved to 128 and no longer matches the architecture's wording

The architecture says the merge policy is "recorded on each dispatch decision". The slice says a dispatch is not a routing decision and puts the policy in the `sq_run` journal parameters, which 128 would own. This is a reasonable reading. 128's design should confirm it, and the architecture wording should be reconciled so 128 does not hit the same ambiguity.

### [NOTE] Failure-mode coverage is spread across decisions, and one reference is dangling

The Patterns section says errors "match the failure-modes table", but no such table exists. The API table's Raises column and the per-decision validation do cover the new write paths. Rollback tests cover the compound writes, and the single-writer design removes the race on dedup. Remove the reference or add the table.

### [NOTE] D5 and D8 fix shapes ahead of their consumers

The plan permits this ("Tables before their consumers") and the slice cites the rule. The `RoutingDecisionInput` fields and the `StatusEffect | BlockEffect | None` parameter are the parts most likely to change when 126 fixes the grammar. Keep the new reads to what the named consumers need. `routing_decisions(node_id)` and `desired_states(project_id)` are the ones to check for use before they ship.

### Run Digest

- Response length: 7346 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 285483 / 187213 / 98262 / 8607 / not computed
- Duration: 74.7 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
