---
docType: review
layer: project
reviewType: slice
slice: intent-vocabulary
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/124-slice.intent-vocabulary.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 540f611a093df09eab8d8bd2b57cc09debf62842
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106297
cachedTokens: 11266
cacheWriteTokens: 95027
completionTokens: 5519
durationSeconds: 47.3
costUsd: 0.437238
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Intent semantics and resolution rules match the architecture"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D6 — Governance is a pure lookup up the path"
  - id: F002
    severity: pass
    category: boundaries
    summary: "Tick ordering and atomic apply-and-acknowledge are respected"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#Data Flow"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O path are enumerated"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D9 — Applying intents: one stage, store-only, before observe"
  - id: F004
    severity: note
    category: error-handling
    summary: "A faulting intent halts Observe for its project"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#Special Considerations"
  - id: F005
    severity: note
    category: contract
    summary: "Rejection code is parsed out of free-text `reason`"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D3 — Rejections are answers, never exceptions, and the inbox stays unchanged"
  - id: F006
    severity: note
    category: scope
    summary: "Orphan rows can keep `drives_anything()` true permanently"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D6 — Governance is a pure lookup up the path"
  - id: F007
    severity: note
    category: consistency
    summary: "Prerequisite list and frontmatter `dependencies` differ"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md:6-8"
  - id: F008
    severity: note
    category: nfr
    summary: "The tick NFR is addressed by reasoning, not restated"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D9 — Applying intents: one stage, store-only, before observe"
---

# Review: slice — slice 124

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Intent semantics and resolution rules match the architecture

Drive resolves from the nearest target that sets it. Hold is true if any target on the path holds. Both are read from stored rows, with no message replay, and orphaned state has no effect. Hold does not stop observation or ingestion (D7). The architecture's intent paragraph already carries the two D5 departures: resume removes the hold, and a drive to a passed step is applied when it changes settings. The slice and architecture therefore agree.

### [PASS] Tick ordering and atomic apply-and-acknowledge are respected

- Intents are applied first in the tick.
- Each acknowledgment and its desired-state write share one transaction, with intents taken in `seq` order.
- The index is built before Observe, which supports the architecture's Observe-scope rule (a project is read only if an intent says to drive it or a run is in flight).
- Decide stays pure, and the guard is a programming-error `ValueError` that goes through the existing project fault boundary.

### [PASS] Failure modes for the new I/O path are enumerated

D9 covers four cases:
- A store failure exits the process, and the intent is replayed after restart because its acknowledgment and write are one transaction.
- A bug becomes a deduplicated `unexpected_fault`, and the failing intent stays pending.
- Every body or target error is an explicit `rejected` answer (D3).
- A failure injected inside `acknowledge_message` is a stated success criterion.

### [NOTE] A faulting intent halts Observe for its project

An unexpected exception in apply skips the rest of that project's tick. That includes ingestion and checkout release, which the architecture otherwise wants to keep running for in-flight runs. The design acknowledges this, notes that every body and target error is already a rejection so only a code bug can cause it, and defers the fix to issue #12. This is acceptable for the first proof. If the first proof shows it matters, give apply its own fault scope.

### [NOTE] Rejection code is parsed out of free-text `reason`

The doc says the reason is display data and also says submitters branch on the code prefix. 121's acknowledgment carries only a string, so the prefix is the only structured channel. Document the `<code>: ` grammar as normative in `inbox-contract.md` and test it against the real stored format. 160 will depend on it.

### [NOTE] Orphan rows can keep `drives_anything()` true permanently

Intents targeting an unlinked node are rejected (D2), so a PM cannot clear a driving row left on a node that later becomes orphaned. That row makes the Observe-scope predicate true, so the project's CF status reads continue every tick. The design accepts this as cost only, never an action. It is bounded and becomes moot when relink arrives (slice plan Future Work item 3).

### [NOTE] Prerequisite list and frontmatter `dependencies` differ

The Dependencies section lists 121, 122 and 123 as prerequisites. The frontmatter `dependencies` lists only 121 and 123. 122 is reachable through 123, but the frontmatter should match the prose.

### [NOTE] The tick NFR is addressed by reasoning, not restated

The architecture's tick-never-waits obligation and tick deadline are not restated as a target. D9 reasons correctly that apply runs no subprocess and is exempt from the deadline check. A single sentence stating that apply is store-only and does not consume the tick budget would make the compliance explicit. No design change is needed.

### Run Digest

- Response length: 4976 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 106297 / 11266 / 95027 / 5519 / not computed
- Duration: 47.3 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
