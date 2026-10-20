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
reviewedSha: 96e362270ffe61d38264b71e1d5beadd0823bf14
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 308808
cachedTokens: 202703
cacheWriteTokens: 106097
completionTokens: 6107
durationSeconds: 51.7
costUsd: 0.506551
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "Plan success criterion \"appears on the next tick\" no longer matches the slice"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D7 — When the plan is read"
  - id: F002
    severity: concern
    category: architecture-boundary
    summary: "Reconcile makes escalation decisions in Observe, which D9 says is the planner's job"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D5 and #D9"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`plan_read_failed` is used both project-scoped and node-scoped, with different closure rules"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D6, #D8"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "`merge` and the other steps clear on CF's checkbox, which the arch says is not authoritative for merges"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D3, #D4"
  - id: F005
    severity: concern
    category: scope
    summary: "Proportionality: components that nothing uses in production yet, and mechanisms that could be lighter"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D9, #D7, #D8"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Identity, orphaning and reconciliation order match the arch"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D1, #D5"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Failure modes and the tick NFR are handled explicitly"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D5, #D7, #D8"
  - id: F008
    severity: note
    category: uncategorized
    summary: "Dependency direction and the single-predecessor function are correct"
    location: "project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md#D4, #Component Structure"
---

# Review: slice — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Plan success criterion "appears on the next tick" no longer matches the slice

Plan entry 4 (`120-slices.runner-routing-engine.md:81`) still says a slice added to a plan document "appears on the next tick". D7 and Functional Requirements instead say it appears on the first read after `plan_read_interval_seconds` (default 30 s). Only a changed snapshot gives an early read, and a plan edit does not touch `projects.json`. The plan edits listed under Special Considerations reword the snapshot criterion (line 83) but not line 81. Either reword line 81 to "on the next plan read" or add it to the edit list, so the acceptance criteria agree.

### [CONCERN] Reconcile makes escalation decisions in Observe, which D9 says is the planner's job

The arch says Observe "never chooses anything" and Decide chooses. D9 puts human-step blocking in a planner because "choosing to put a person on a step is a decision", and says reconcile "only projects what CF says". But reconcile also blocks nodes: orphans (D5.1) and nodes with an unknown status (D6). Those are also store-only writes that put a person on a node.
- **Orphan blocks** are arguably fault escalations, which the arch lets Observe raise.
- **The unknown-status block** is a routing judgment, not a fault.
- Neither is journaled or goes through Act.

State which category each falls under, and put the reconcile-time blocks under the fault rule so D9's rationale is not contradicted by D5.

### [CONCERN] `plan_read_failed` is used both project-scoped and node-scoped, with different closure rules

D8 defines `plan_read_failed` as project-scoped. It is deduplicated per project and kind, and it stays open while the link's last read failed. D6 reuses the same kind as the payload of a node-level `HUMAN` block on a slice with an unknown status. That is a different scope and a different lifecycle: it clears only when a person resolves it, and it re-blocks on the next read. Two behaviours under one kind will confuse dedup, closure and anyone reading the escalation. Use a distinct kind, for example `plan_status_unknown`, or state the scoping rule explicitly.

### [CONCERN] `merge` and the other steps clear on CF's checkbox, which the arch says is not authoritative for merges

The arch says git, not CF's checkboxes, shows that a slice is merged. D3 marks `merge` done when CF reports the slice complete (`status == complete` or `isChecked`). D4 uses that `done` to release the next slice's `implementation`. The deferral to 128 is stated. But the design should say what happens in the interim: 124 and 125 can drive `implementation` on slice n+1 once the PM ticks slice n in CF without merging. Either note that the clean-tree check in 128 is the backstop and 125 must not dispatch `implementation` before it, or state that this window is accepted.

### [CONCERN] Proportionality: components that nothing uses in production yet, and mechanisms that could be lighter

The slice is rated 3/5 but carries a lot:
- **`HumanStepPlanner` and `BlockHumanStep`** are not in the production planners until 124. They run only under tests. Plan entry 4 assigns the human-step criterion to this slice, so keep it, but a small test-only implementation is enough. Don't build further abstraction around it before 124's drive filter exists.
- **Starved-read escalation** (D7) needs its own timer, its own "how many calls the read needs" message and its own closure. The design measures reads at about 0.1 s each against a 5 s deadline, and polling runs first. Defer this until a read is observed to starve, or reuse the existing "failed link counts as recurrence" rule. A cut-off read could simply repeat without a separate escalation.
- **Executor and level vocabulary.** `StepLevel`, `Executor` and `StepSpec` with a `pipeline` field are fine, but `NodeKind.GATE` handling and the "unknown status" block add paths with no first-proof use. The `degraded` path is cheaper if it only logs and leaves the slice without steps.

Cut or defer the starved-read escalation first. It adds the most state for the least demonstrated need.

### [PASS] Identity, orphaning and reconciliation order match the arch

The link is the stored CF index, keyed with kind and CF project and enforced by a partial unique index. Display data is never matched. Orphans are never deleted. Bad, empty or duplicate reads orphan nothing. A renumber gives one orphan and one new node, as the arch states. Each rule checks before it writes, so a crash is repaired by the next read.

### [PASS] Failure modes and the tick NFR are handled explicitly

The design covers:
- the CF read timeout and a non-zero exit with or without an error document;
- parse failure;
- a cut-off read applying nothing;
- a store failure (process exit);
- an unexpected exception (project-scoped `unexpected_fault`).

Every CF call goes through `TickBudget` and `tick_call_timeout_seconds`, and polling runs before plan reads. This meets the arch's "the tick never waits" requirement. The 5 s deadline appears only in passing in D7. Restate it, with the per-call timeout, in Technical Requirements.

### [NOTE] Dependency direction and the single-predecessor function are correct

The CF models live in `upstream`. Lifecycle, probes and reconcile live in `runner`, and the commands are defined once. `predecessors` is the one place 180 widens, as the arch requires. `ready_steps` is pure over the tree, which keeps Decide free of I/O.

### Run Digest

- Response length: 6960 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 308808 / 202703 / 106097 / 6107 / not computed
- Duration: 51.7 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
