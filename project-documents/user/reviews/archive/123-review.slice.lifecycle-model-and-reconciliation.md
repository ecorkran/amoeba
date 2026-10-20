---
docType: review
layer: project
reviewType: slice
slice: lifecycle-model-and-reconciliation
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 4d7f2e499f70f2de29b55a4394965568437dc259
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 403804
cachedTokens: 298029
cacheWriteTokens: 105765
completionTokens: 6318
durationSeconds: 58.0
costUsd: 0.516869
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Departures from the arch and plan that the slice does not record"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D11 — 122's `cf` probe set changes"
  - id: F002
    severity: concern
    category: failure-modes
    summary: "Plan reads can crowd out run polling, and a read that never fits is not handled"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#Data Flow"
  - id: F003
    severity: concern
    category: dependency-semantics
    summary: "The predecessor order silently skips a slice that has escalated as unknown"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D4 — The predecessor function"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Some mechanisms nothing in the slice needs yet"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#Technical Scope"
  - id: F005
    severity: note
    category: dependency-direction
    summary: "Store contract changes live in this slice, consistent with the plan"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#Database / Storage Schema"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layering, single node creator and failure handling for plan reads"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D5 — Reconciliation applies a complete read, in a fixed order"
---

# Review: slice — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Departures from the arch and plan that the slice does not record

The slice's list of arch and plan edits (Special Considerations) omits three departures, each of which contradicts text that is still in the arch or plan.
- **Probe set (D11).**
  - The arch's shape list (the "Unknown escalates" principle) still says `cf list slices --json` "must parse for a linked project" at start.
  - D11 drops that probe.
  - It is replaced by a per-read check, which D8 uses to tell a missing plan from a failure.
  - The arch's probe statement should be edited, as the slice does for its other departures.
- **Done nodes that leave the plan (D5.1).**
  - The arch says a node whose index CF no longer reports "escalates as orphaned".
  - The slice does not escalate a `done` node and only logs INFO.
  - That is a reasonable rule, because 121 refuses to block a done node. But it narrows the arch's reconciliation rule and is not recorded.
- **Plan success criterion.**
  - Plan entry 4 still says a new slice "appears on the next tick".
  - The slice delivers it on the first read after `plan_read_interval_seconds` (default 30 s) or on a snapshot-triggered early read.
  - The plan criterion should be reworded in the same pass as the other entry 4 edits.

### [CONCERN] Plan reads can crowd out run polling, and a read that never fits is not handled

The plan read runs at the start of Observe, before in-flight run observation.
- A link's read costs one `cf list initiatives` call plus one `cf list slices` call per initiative, each checked against `TickBudget`. A cut-off read applies nothing and restarts next tick.
- The arch's tick principle makes in-flight run polling and the "work not reached goes first on the next tick" rule central. The slice does not say which of the two has priority when the budget is tight.
- If a link's full read cannot finish inside one tick's budget, for example with many initiatives or many linked projects, it is cut off on every tick. It never reconciles, and no fault is raised, because a budget cut-off is not a `plan_read_failed`.
- State the priority, for example run polls first, or plan reads resume at the link where the last tick stopped. State what surfaces a link that is cut off repeatedly. Add a test for it.

### [CONCERN] The predecessor order silently skips a slice that has escalated as unknown

D4 defines an eligible slice as one with step children, and `implementation` waits only on the previous eligible slice's `merge`.
- D6 gives a `degraded` or unknown-status slice no steps and blocks it on a human, so it is not eligible.
- The next slice's `implementation` can therefore become ready ahead of an unresolved slice.
- The arch says unknown escalates and is never defaulted away. Skipping deferred and deprecated slices in the order is deliberate. Skipping an unknown-status slice contradicts that principle.
- Either keep the unknown-status slice in the order as an unmet predecessor, or document why the successor may proceed.

### [CONCERN] Some mechanisms nothing in the slice needs yet

The design is large for a 3/5 slice. These items can be cut or deferred without leaving a requirement unmet:
- **Skipping slice reads for `done` initiatives (D7).** It saves about 0.1 s per initiative every 30 s. It also adds a "skipped read orphans nothing" rule and a path that reconcile tests must cover. Read every initiative until measurement shows a need.
- **Separate `lifecycle_orphan` fault kind (D8).** It exists only to name a payload. The payload `fault_kind` could use an existing vocabulary, or the kind could be added when something consumes it.
- **`--plan-read-interval` flag.** The setting is required. The CLI flag has no consumer in the slice or the plan, and the walkthrough and tests do not use it. Keep the setting and cut the flag, unless 122's settings pattern requires one flag per setting.
- **Restated material.**
  - The Interfaces Required table repeats CF shapes that also go into `context-forge-contract.md`.
  - D3 and D9 repeat arch text.
  - The slice-plan edit list is long.
  - Each could point to its contract document instead.

### [NOTE] Store contract changes live in this slice, consistent with the plan

The arch says store contract changes land ahead of the Runner. The slice plan's Notes allow a table or column that depends on slice-design detail to land in its consumer slice. Migration `010`, `CFReference.index` and `update_node_title` fit that allowance. The slice updates `store-contract.md` in the same slice, so the contract-first rule holds.

### [PASS] Layering, single node creator and failure handling for plan reads

- **Layering and dependency direction.**
  - Observe, decide and act stay separate: reconcile is the only plan-driven writer, `LifecycleTree` is pure, and the planner is pure.
  - Upstream CF models sit in `upstream/context_forge` and the lifecycle code in `runner/lifecycle`, so dependencies point inward.
- **Predecessor function.** It is the single place for dependencies, as the arch requires so that 180 can widen it.
- **Failure modes.** Failure modes for the new CF reads are enumerated with explicit handling:
  - timeout, non-zero exit, parse failure, and a cut-off read;
  - the no-plan error document, an empty list, and a duplicate index;
  - store failure and unexpected exceptions mid-reconcile.
- **Fault closure.** The closure rule for `plan_read_failed` is restated against 122's closure behavior.
- **Idempotence and node creation.** Reconcile is idempotent and crash-repairable. The `create_node` guard test enforces that only the Runner creates nodes.
- **NFR targets.** The per-call timeout and tick budget from the arch are used with specific settings.

### Run Digest

- Response length: 7088 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 403804 / 298029 / 105765 / 6318 / not computed
- Duration: 58.0 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
