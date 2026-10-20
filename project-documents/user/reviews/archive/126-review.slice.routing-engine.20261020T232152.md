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
reviewedSha: 2d3c695d8b3bac0bc9ff0db01c32f5b03766cbe7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 488953
cachedTokens: 383916
cacheWriteTokens: 105025
completionTokens: 6495
durationSeconds: 58.7
costUsd: 0.524268
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Core routing contract matches the architecture"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Technical Decisions"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "Recurrence vocabulary departs from the architecture without being declared"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D1"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "Overrun handling departs from the architecture's \"the node escalates\" and is not in the arch edit list"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D7"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure handling for the new read and recompute paths is only implicit"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D5, #D6, #Patterns and Conventions"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Some scope can be cut or deferred (proportionality)"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Technical Scope"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "Attempt count is recorded but not matchable"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D1"
  - id: F007
    severity: note
    category: nfr
    summary: "The tick NFR is respected but not restated"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Data Flow"
---

# Review: slice — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core routing contract matches the architecture

The slice keeps the architecture's contract:
- Rules are ordered and first match wins.
- The table ends in a catch-all escalate.
- `unknown` matches only conditions that name it.
- Routes are advance, rerun and escalate, with `judge_eligible` for 140.
- Each decision is a recorded row that stores the table version and the Amoeba version.
- The table is static and versioned by digest.
- Routing works from `unrouted_outcomes`, so a crash between ingestion and routing loses nothing.

Rerun is limited to `outcome: completed`. Paused runs are never rerun or advanced. Rerun carries no instructions. Dependency directions are correct: the slice consumes 121 and 125 and provides to 127, 128, 129 and 140. Store changes are excluded, and the table is the only place a route is chosen. D8 moves the view ahead of routing, which matches the architecture's tick order ("decided on the next tick").

### [CONCERN] Recurrence vocabulary departs from the architecture without being declared

The architecture's input list gives recurrence as `new / recurring / gone`. D1 uses `recurring / new / clear / none`. The two are not the same thing. In 104's contract, `gone` is the list of previous-round findings the target lacks. D1's `clear` means no `concern` or `fail` finding is present. D1's "Departures" list names `node_kind`, severity and gate/check inputs, but not this change. The "Plan and arch edits" list doesn't include it either. Declare the rename and its new meaning in D1, and add it to the arch edit. The alternative is to adopt `gone` where it fits.

### [CONCERN] Overrun handling departs from the architecture's "the node escalates" and is not in the arch edit list

The architecture says a run past its time bound "escalates" the node, enforced by the routing engine. D7 raises a project-scoped `run_overrun` fault instead. It writes no decision record, and the response is fixed in code rather than chosen by a rule. The reasoning holds up: 122 D8 never blocks a node mid-run, and a decision record would take the entry's one slot. Even so, this is a route-like behavior chosen outside the table, and it contradicts the architecture's wording. "Plan and arch edits" should record it, so the architecture's "No route is chosen in a code branch outside the table" has a stated exception for this case.

### [CONCERN] Failure handling for the new read and recompute paths is only implicit

The route stage's store reads are left to "122's one catch". The slice does not say what happens in each of these cases:
- **Evidence reads that raise.** `finding_changes` and `observations` raise `VerdictNotFoundError` for an unknown id (evidence contract). Does a dangling `verdict_id` reduce to `unknown`, or fault the project every tick?
- **Store write failure.** The architecture says an unwritable store is a process failure, not a project fault. The slice should state that a failed `record_routing_decision` write follows that rule.
- **Recompute with a stored version that won't parse.** Examples are an unsupported `format` or a missing version row. `recompute` and the `recomputes` column need a defined result, such as `error` instead of `no`. Without one, an unparseable stored version looks like a mismatched decision.
- **The CLI opening a live store read-only.** This path is not covered at all.

Each needs one line of explicit handling.

### [CONCERN] Some scope can be cut or deferred (proportionality)

The slice has nine decisions, about eight new modules and two new CLI commands, for a 3/5 slice. Three items go beyond what the plan entry and the arch assign:
- **The standalone `amoeba routing-table check` command** and `amoeba/cli/routing.py`. `amoeba start` already refuses an invalid table with the same message, and `parse_table` can be tested directly. The command is not in plan entry 7's criteria. Fold the check into `amoeba start`, or defer the command.
- **The test that checks `docs/routing-table.md` against `inputs.py`**, and the separate operator document itself. Document the format in `process-contract.md`, or generate the doc from the code.
- **The `--routing-table` flag and setting.** Keep only if the test-table and proof workflow need them, which D2 suggests they do.

Keep `format`, since it mitigates the plan's named risk.

### [NOTE] Attempt count is recorded but not matchable

The architecture lists "attempt count" among the inputs. D1 records it but bounds it only through `max_attempts` plus eligibility. The architecture's rule grammar lists the attempt limit as a route parameter, so this matches. The behavior (the limit falls through to the next rule) fits plan criterion 3. The exclusion is explained in D1, though it isn't in the departures list.

### [NOTE] The tick NFR is respected but not restated

The architecture's "tick never waits" rule is met. The route stage and overrun check do store reads and pure computation only, with no subprocess. The slice never says so. One sentence would let a reader confirm no new subprocess or deadline check is introduced.

### Run Digest

- Response length: 5949 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 488953 / 383916 / 105025 / 6495 / not computed
- Duration: 58.7 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
