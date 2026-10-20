---
docType: review
layer: project
reviewType: slice
slice: routing-engine
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/126-slice.routing-engine.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: e5c12b4ee1920fb62131344e0437ec252a85563a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 296468
cachedTokens: 194122
cacheWriteTokens: 102338
completionTokens: 6138
durationSeconds: 50.0
costUsd: 0.490962
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Rerun attempt bound is undefined when `step` is unknown"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D4 — Matching, route eligibility, and the catch-all (and D5, \"Every decision on a step counts one attempt\")"
  - id: F002
    severity: note
    category: error-handling
    summary: "Table file read failures are not enumerated"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D4 — Load-time validation"
  - id: F003
    severity: note
    category: architecture-alignment
    summary: "The overrun escalation has no decision record"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D7 — Per-pipeline time bounds raise a project-scoped escalation"
  - id: F004
    severity: pass
    category: architecture-alignment
    summary: "Fixed response for overrun is a stated, bounded exception"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D7 — Per-pipeline time bounds raise a project-scoped escalation"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Input vocabulary and grammar match the architecture and the plan"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D1 — The routing inputs, and what `unknown` and `none` mean"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and the tick contract hold"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Data Flow"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes for the route stage are enumerated"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D5 — Each route's effect on the node, and attempt counting"
  - id: F008
    severity: pass
    category: scope
    summary: "Scope matches the plan entry and stays proportionate"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Technical Scope"
---

# Review: slice — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Rerun attempt bound is undefined when `step` is unknown

D5 sets `attempt_step` to null when `step` is `unknown`. D1 defines `attempt` as `attempt_count(node, step) + 1`, which cannot be computed without a step.
- D4's `rerun` predicate (`attempt < max_attempts`) has no stated behavior when `attempt` can't be counted.
- If `attempt` defaults to 1 in that case, a rule that doesn't name `step` can match the outcome. Every decision then records no attempt, so the limit never trips.
- That is the one route that launches paid runs without a PM, and the design's Spend note relies on `max_attempts` to bound it.
- The architecture requires the attempt limit to be counted per node and step, and unknown to escalate rather than be defaulted.

Fix: make `rerun` ineligible when `step` is `unknown`, so the next rule or the catch-all applies. State this in the predicate list and add it to the table-driven eligibility tests. If `unknown` never occurs for a step node, say that and make it a `ValueError`.

### [NOTE] Table file read failures are not enumerated

The design lists validation problems in detail and routes them to `StartupFailedError` with exit `STARTUP_FAILED`. It does not name the I/O-level failures of `load_table(path)`: a `--routing-table` path that is missing or unreadable, and malformed YAML. Both reach the same boundary and sit under "Failures raise `StartupFailedError`" in Technical Scope. One sentence in D4, plus a load-refusal test case, would remove any ambiguity.

### [NOTE] The overrun escalation has no decision record

The architecture says every routing application writes a decision record, and its goals say any decision can be recomputed. D7 deliberately writes no record for an overrun. The reasons are sound: the entry's single decision slot belongs to its eventual outcome, and an in-flight run has no outcome to route. The escalation payload carries `table_version` and `bound_minutes`, which keeps the evidence. The architecture's edits cover the fixed response but don't say that no decision record exists for it. Add that to the architecture edit in "Special Considerations" so the two documents agree.

### [PASS] Fixed response for overrun is a stated, bounded exception

D7 departs from the architecture's "no route is chosen in a code branch outside the table". It names the departure and justifies it: an in-flight run can only be escalated, because a rerun would start a second pipeline in a held checkout. It confines the exception to the one case, where the table sets the bound and code sets the response. The architecture text already carries the matching edit, and the plan's criterion "escalates, without being killed" is met.

### [PASS] Input vocabulary and grammar match the architecture and the plan

Plan entry 7 and the architecture's "What the routing table matches on" paragraph both carry the departures D1 lists: no node kind, recurrence folded to `new` / `recurring` / `clear`, and gate state and check standing deferred to 128. D3 and plan entry 9 register those two inputs with 128.
- The attempt limit is a route parameter enforced by eligibility predicates, not a matchable input, which fits the architecture's rule grammar.
- `unknown` matches only a condition that names it, as the architecture requires.

### [PASS] Layering, dependency direction and the tick contract hold

- The evaluator, reducer, recompute and overrun check are pure. Store reads and the single atomic write through 121's `record_routing_decision` are isolated in `evidence.py` and `stage.py`.
- Dependencies point downward onto the store, 121, 125 and 122. No store migration is added.
- The route stage and overrun check start no subprocess, so no `TickBudget` check is needed. The doc restates the tick NFR: deadline plus one call timeout.
- Moving the view before the route stage (D8) implements the architecture's "successor decided on the next tick" rule, and the slice flags it as a change to 125's data flow.

### [PASS] Failure modes for the route stage are enumerated

D5 handles each failure explicitly:
- An unreadable verdict makes the review inputs `unknown`, so the outcome is routed rather than faulting the project every tick.
- A store write failure is re-raised, the process exits, and recovery routes the outcome after restart.
- Any other exception reaches 122's single catch.
- A crash before or after the decision transaction is safe because the flag is cleared in the same transaction.

D6 shows an unreadable stored table as `error: <reason>`, not as a mismatch. D7 treats a missing pipeline bound as a `ValueError`.

### [PASS] Scope matches the plan entry and stays proportionate

- Every item in plan entry 7 is delivered: the static table, closed inputs, three routes, decision records, version storage, the catch-all, the time bound and recompute.
- The exclusions are 127, 128, 131, 140 and per-project tables. Per-project tables are recorded as plan Future Work item 10.
- The standalone `routing-table check` command is deferred to issue #13, and `amoeba start` already refuses an invalid table with every problem listed.
- The grammar is deliberately small. The `format` field costs one integer and protects the plan's named risk, that old decisions must still recompute.
- Minor trimming is possible. The "Departures" list in D1 states the attempt-count departure twice, and the Provides section restates D7's resume-entry note.

### Run Digest

- Response length: 7035 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 296468 / 194122 / 102338 / 6138 / not computed
- Duration: 50.0 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
