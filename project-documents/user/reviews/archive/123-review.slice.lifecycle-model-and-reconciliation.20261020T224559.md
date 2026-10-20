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
reviewedSha: 987dd7e91ab5b5f0894d7a909966ea752e214fc5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 399143
cachedTokens: 295102
cacheWriteTokens: 104031
completionTokens: 4736
durationSeconds: 42.6
costUsd: 0.49382
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Human-step blocking is deferred to 124 but the plan and 124's entry don't record it"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D9 — Human steps are blocked by a planner, as a store-only action"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "The \"CF write\" executor is dropped, and the arch edit list doesn't cover it"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D3 — The v1 step map"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Worktree status reads and `ProjectView.worktrees` are built for consumers that don't exist yet"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D7 — When the plan is read"
  - id: F004
    severity: concern
    category: error-handling
    summary: "The new ProjectView and store write paths have no timeout or mid-write failure handling"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D5 — Reconciliation applies a complete read, in a fixed order"
  - id: F005
    severity: note
    category: architecture-alignment
    summary: "Departures from the architecture are explicit and justified"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D3, D7, D9"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Identity, orphaning and bad-read safety match the architecture's reconciliation rules"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D1, D5"
  - id: F007
    severity: pass
    category: dependency-direction
    summary: "Dependency directions and the `create_node` guard are correct"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D10, Dependencies"
---

# Review: slice — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Human-step blocking is deferred to 124 but the plan and 124's entry don't record it

The slice plan's 123 entry has this success criterion: "Human steps (P2, P3, P7, host cutover) are `blocked_on_human` from the moment they become current." The slice redefines "current" as "ready and driven". `HumanStepPlanner` is not registered in production, and a "Not in the production planners until 124" paragraph says the planner runs only under tests in 123. The reasoning holds: registering it now would escalate every unstarted initiative the moment a project is linked. But the criterion is only met under a test planner. A grep of `project-documents/user/architecture` finds no mention of `HumanStepPlanner` or `BlockHumanStep`. The planner registration is therefore not written down in 124's plan entry.
- Reword the 123 plan criterion to say production blocking arrives with drive in 124.
- Add the registration to 124's plan entry. The slice's Special Considerations list the arch and plan edits but omit this one.

### [CONCERN] The "CF write" executor is dropped, and the arch edit list doesn't cover it

The arch says "Every lifecycle step maps to exactly one of: a Squadron pipeline the Runner may run, a CF write it may make, or a human step". The 123 plan entry repeats the three-way split. D3 restricts `Executor` to `pipeline` and `human`, on the grounds that a pointer write is part of dispatch (125). This is consistent with the arch's pointer-write paragraph and with the arch's step-map table, which has no CF-write row. But it contradicts that sentence, and Special Considerations lists only three arch edits: no gate nodes, Observe scope, and unjournaled store-only actions. Add a fourth edit to reword the arch sentence and the plan entry, so later slices don't reintroduce the executor.

### [CONCERN] Worktree status reads and `ProjectView.worktrees` are built for consumers that don't exist yet

123 reads `cf status --worktree <id>` for every worktree on every due read. It parses the full `CFStatus`, including `gateInfo` and `pendingDecisions`. It builds `WorktreeObservation` and puts `ProjectView.worktrees` into the view. It also adds a project-level fallback read and the "no snapshot yet, empty view" rule. 123 itself uses only `activeSlice.name` (D2). The rest is passed to 125 and 128. The Overview says this directly.
- **What to cut or defer:** the `ProjectView.worktrees` plumbing, the retained observations, and their fallback and empty-snapshot rules can move to 125, the first consumer. 123 can read status only to the extent D2 needs.
- **What to keep:** the full `CFStatus` model is also needed by D11's probe, so keep it.
- **Effect on 125:** this may complicate 125, so weigh it before cutting.

The same question applies to `HumanStepPlanner` and `BlockHumanStep`: they ship in 123 but run only in tests until 124. Keep them only if the plan entry assigns them to 123 (see the first finding).

### [CONCERN] The new ProjectView and store write paths have no timeout or mid-write failure handling

Failure handling for the CF reads is thorough:
- timeouts and budget cut-offs
- non-zero exit
- parse failures
- empty lists and duplicate indexes
- the error document from `cf list slices`

Two paths are less explicit.
- **Partial reconcile:** D5 says each rule checks the store before it writes and the next read repairs a crash. For a failed `store` write partway through a reconcile, the doc says only that the store failure is a process failure under 122. It never says a reconcile killed by that failure leaves a read marked "complete" in memory. A failed reconcile must not record the link's last-complete-read time, or the repair waits a full interval. The doc should state the time is recorded only after reconcile succeeds.
- **Unreadable snapshot:** the early-read trigger consumes `latest_cf_snapshots`. If the `worktrees` projection is malformed or missing, the status read falls back silently. D7 says a snapshot with no worktrees falls back to a project-level read. A malformed projection should be an explicit `plan_read_failed`, in line with "unknown escalates".

### [NOTE] Departures from the architecture are explicit and justified

The slice names three departures and proposes an arch edit for each. The arch text already carries them (the Observe paragraph, the "store-only action" sentence, and the step-map note on gate nodes), so the documents agree.
- No gate nodes in v1. Gates are a dispatch check, with a path to add a row later.
- Plan reads for every linked project on an interval, so that 124's intents have target nodes.
- Store-only actions are not journaled.

All three are consistent with the arch's stated goals.

### [PASS] Identity, orphaning and bad-read safety match the architecture's reconciliation rules

The slice follows the arch's four reconciliation rules:
- **Linking:** nodes link by stored index, and display data is never matched. A partial unique index enforces the link.
- **Renames:** a renamed slice keeps its node.
- **Orphans:** an orphan is never deleted, history is kept, and a renumber yields one orphan escalation and one new node.
- **Bad reads:** a failed, partial, empty or duplicate-index read never orphans anything.

The "unknown escalates" principle is applied to unknown CF status values. The `plan_read_failed` closure rule follows 122's pattern for failed probe links.

### [PASS] Dependency directions and the `create_node` guard are correct

The slice depends on 121, 122 and 108 and provides to 124–129 and 180. Store changes go through the migration mechanism (`010`) and the public API. An AST guard test limits `create_node` to the reconcile module. Predecessor lookup goes through one function, as the arch's "do not foreclose programs" item requires. Each timing value is a setting (`plan_read_interval_seconds`), and CF calls run under `TickBudget` and the per-call timeout, as the tick-never-waits principle requires.

### Run Digest

- Response length: 7491 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 399143 / 295102 / 104031 / 4736 / not computed
- Duration: 42.6 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
