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
reviewedSha: 4dfe945332f65cb752f5c548d6a07f1923368381
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 298590
cachedTokens: 195698
cacheWriteTokens: 102884
completionTokens: 6291
durationSeconds: 54.9
costUsd: 0.494835
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Table-only routing and auditability match the architecture"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Technical Decisions"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Tick ordering, failure handling and NFR carry-over are consistent"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D5, #D8, #Data Flow"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "Attempt count is demoted from an input, but the planned architecture edits omit it"
    location: "project-documents/user/slices/126-slice.routing-engine.md:185-190, 454-458"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Overrun is a stated, bounded exception to \"no route outside the table\""
    location: "project-documents/user/slices/126-slice.routing-engine.md#D7"
  - id: F005
    severity: note
    category: integration
    summary: "Resume entries must carry `pipeline`, a constraint placed on 127"
    location: "project-documents/user/slices/126-slice.routing-engine.md:283, 351"
  - id: F006
    severity: note
    category: auditability
    summary: "Recompute covers table application, not evidence reduction"
    location: "project-documents/user/slices/126-slice.routing-engine.md#D6"
  - id: F007
    severity: pass
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/slices/126-slice.routing-engine.md#Technical Scope"
---

# Review: slice — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Table-only routing and auditability match the architecture

- **Where routes are chosen:** The table decides routes. Code defines only the inputs and the eligibility predicates (D1, D4). Eligibility only restricts a route and never picks one, so the attempt limit falls through to the next matching rule. A source test checks that `Route` members are compared only in `engine.py`.
- **Unknown handling:** `unknown` matches only a condition that names it, as the architecture's grammar requires.
- **Catch-all and recompute:** Load validation enforces the catch-all escalate. Each decision records the table version and Amoeba version, and the table content is stored on first use.
- **Slice plan:** This covers every success criterion of the slice plan entry.

### [PASS] Tick ordering, failure handling and NFR carry-over are consistent

- **Tick order:** D8 builds the view before routing, so a successor made runnable by routing is decided on the next tick. This matches the architecture's tick description.
- **Tick deadline:** The route stage and overrun check do only store reads and pure computation, so the tick's worst case stays at 122's deadline plus one call timeout. The doc restates this.
- **Failure modes:** The new I/O paths each have an explicit strategy:
  - A missing or unparseable verdict makes the review inputs `unknown`.
  - A store write failure re-raises and the process exits.
  - Any other exception faults the project and leaves the entry unrouted.
  - A crash before the decision transaction leaves the entry in `unrouted_outcomes`.
  - A bad table, a missing file or a malformed file stops `amoeba start` with `StartupFailedError`.

### [CONCERN] Attempt count is demoted from an input, but the planned architecture edits omit it

- **The conflict:** The architecture's "What the routing table matches on" still lists `attempt count` among the closed inputs (arch line 151). Slice D1 makes it recorded but not matchable, with the limit expressed as `max_attempts` instead. The architecture is internally consistent with this, since its grammar lists "attempt limit" as a route parameter. A reader of the architecture would still expect a table to be able to match on attempts.
- **What the doc does about it:** The doc names this departure in D1. The "Plan and arch edits" list under Special Considerations covers node kind, gate state, check standing and recurrence, but not attempt count. The listed edits would therefore leave the architecture and the slice in conflict.
- **Fix:** Add attempt count to the architecture edit list so the architecture drops it from the input list.
- **Cut:** The departure is stated twice, in the fourth bullet (190) and under "Attempts" (185). Keep one.

### [NOTE] Overrun is a stated, bounded exception to "no route outside the table"

- **The exception:** The architecture's "One edit point for routing" already carries this exception. The table sets the bound, and the response is always a project-scoped escalation.
- **Why it is consistent:** An in-flight run has no outcome to advance or rerun, and a decision record would use up the entry's single decision slot. The design never kills a run, which matches the architecture.
- **Dedup limit:** The design carries 125's D11 dedup limit forward explicitly.

### [NOTE] Resume entries must carry `pipeline`, a constraint placed on 127

- **The constraint:** A resume entry without a `pipeline` key raises `ValueError` in 126's overrun check, which faults the project on every tick. The requirement appears only here, under 126's D7 and "Provides to Other Slices".
- **Where to record it:** If 127's slice design does not pick it up, the failure shows up at 127's integration. Consider recording it in 127's plan entry.
- **Not a blocker:** The failure is loud, not silent, so this does not block 126.

### [NOTE] Recompute covers table application, not evidence reduction

- **What recompute covers:** `recompute` replays the stored table on the recorded inputs. The reduction from raw evidence is covered only by the reducer's own tests.
- **Why it is acceptable:** This meets the slice plan's criterion ("from its record and its stored table version alone"). Evidence stays reachable through `journal_entry_id`, and the doc states the limit openly.

### [PASS] Proportionality is acceptable

- **Deferred or excluded scope:** The design defers per-project tables, the standalone `routing-table check` command and gate/check inputs. None of these is assigned to this slice by the slice plan.
- **What remains:** The remaining mechanisms are each tied to a named requirement:
  - The `format` field protects old tables from grammar changes, which is the plan's named risk.
  - `--routing-table` is needed for tests and the proof.
  - The recompute column serves the slice plan's recompute criterion.
- **Unused inputs:** Several inputs are unused by the shipped table, but the architecture requires them.

### Run Digest

- Response length: 6060 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 298590 / 195698 / 102884 / 6291 / not computed
- Duration: 54.9 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
