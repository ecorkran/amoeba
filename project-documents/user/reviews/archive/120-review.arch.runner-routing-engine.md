---
docType: review
layer: project
reviewType: arch
slice: runner-routing-engine
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/120-arch.runner-routing-engine.md
aiModel: claude-haiku-4-5-20251001
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: ccc340eb3b63f4a193d4cc85627be61f0bb038e3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 137957
cachedTokens: 57930
cacheWriteTokens: 80001
completionTokens: 18070
durationSeconds: 199.2
costUsd: 0.256841
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Routing table format and persistence not specified"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F002
    severity: concern
    category: completeness
    summary: "Lifecycle steps and phase-to-step mapping incomplete"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F003
    severity: concern
    category: completeness
    summary: "Fault escalation with no attributed node lacks specified mechanism"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F004
    severity: concern
    category: completeness
    summary: "Critical startup dependency shapes not enumerated"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F005
    severity: concern
    category: completeness
    summary: "Multi-project tick fairness and deadline strategy not specified"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F006
    severity: concern
    category: completeness
    summary: "Tier-1 predicate list not enumerated; identification deferred to first proof"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#tier-inference-after-the-first-proof"
  - id: F007
    severity: concern
    category: extension-points
    summary: "Cross-project predecessor discovery mechanism not specified"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F008
    severity: note
    category: feasibility
    summary: "Concurrency per checkout creates single-project bottleneck acknowledged but not mitigated"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
---

# Review: arch — initiative 120

**Verdict:** CONCERNS
**Model:** claude-haiku-4-5-20251001

## Findings

### [CONCERN] Routing table format and persistence not specified

The document describes routing inputs, outputs, and rule semantics (ordered rules, first match, catch-all escalate) but defers "The table format, and where it lives (per supervisor, with per-project overrides or not), are slice design's." For a system where the routing table is "the only place routing behavior is defined" and "auditable" to support "build by inducing failure," the table format is critical. The document should specify whether it's YAML, JSON, Python code, or another format. Slice design should refine implementation details, not basic representation.

### [CONCERN] Lifecycle steps and phase-to-step mapping incomplete

The document illustrates some lifecycle steps (design, tasks, implementation) and maps them to "a Squadron pipeline the Runner may run, a CF write it may make, or a human step." However, it never enumerates the complete set of lifecycle steps for a slice, or which phases (P2, P3, P4, P5, P6, P7) map to which steps. The document mentions "P3, P7, merges, host cutovers have no automated executor, so they are human steps for now" but doesn't specify whether these are lifecycle steps or phases, and how they fit into the node tree structure.

### [CONCERN] Fault escalation with no attributed node lacks specified mechanism

The document states: "Where a fault has no node, such as a failed plan read, slice design decides what it attaches to." This defers the mechanism entirely. The architecture should specify: Are such faults attached to the project node? The initiative node? An out-of-band escalation message? The document says "the case left to slice design above" but doesn't bound what slice design must decide.

### [CONCERN] Critical startup dependency shapes not enumerated

The document states: "A few shapes it cannot work without at all… These are probed once at start from the tools themselves." It names one (`sq run --run-id`, dependency S9) but says "A missing one refuses to start the Runner tenant with an error naming it." The architecture should enumerate all mandatory shapes (e.g., `sq runs wait --json`, `cf status --json` with which fields, `cf list slices --json` structure). Deployment cannot be cleared without knowing exactly what will cause startup refusal.

### [CONCERN] Multi-project tick fairness and deadline strategy not specified

The document says: "A deadline. Projects it does not reach before the deadline go first on the next tick, so worst-case tick length is bounded by the deadline, not by projects × calls × timeout." It also says: "A global limit on in-flight runs across projects waits until real multi-project use shows it is needed." These raise unanswered questions: What is the deadline (milliseconds? configurable per pool?)? When a project is deferred mid-tick, is it FIFO on the next tick, or does it cut in front of new work? How many projects in the supervision directory is this design expected to handle per tick? These matter for forecasting v1 performance and capacity.

### [CONCERN] Tier-1 predicate list not enumerated; identification deferred to first proof

The document lists two Tier-1 predicates: ungate hatches and "the validator examined more than zero files," then says "The first checks are the ones the first proof needs." It defers the full list to what "the first proof's wrong stops then show which findings need a tier." For a system designed to be auditable and table-driven, the Tier-1 predicates should be listed and justified in the architecture (even if marked "v1 initial set"), not discovered during a proof. This creates a gap: what does the routing table in v1 actually check for? A reader cannot fully understand the routing logic without this list.

### [CONCERN] Cross-project predecessor discovery mechanism not specified

The document says: "The decision step therefore reads "is this node's predecessor done?" through one function, so a cross-project predecessor is an added input, not a rewrite." (Initiative 180, future). The design leaves the function unspecified: What is its name, signature, and calling convention? How does a node declare a cross-project predecessor? Is it through a field on the node? An intent? A metadata file? Leaving this completely open risks a design that cannot cleanly accept cross-project dependencies without rework. The extension point should name the function and its contract, even if the v1 implementation is a stub.

### [NOTE] Concurrency per checkout creates single-project bottleneck acknowledged but not mitigated

The document explicitly acknowledges: "In v1, then, a project with one worktree moves one slice at a time, and a paused run stops that project until the PM handles it." This is a known limitation. However, paused runs are noted as blocking the checkout, and the document relies on the PM to resume them manually. There is no automatic timeout, escalation, or reminder mechanism specified for paused runs that block progress. For v1, this may be acceptable if paused runs are rare, but the architecture does not bound or monitor how long a project can be blocked, and the routing table has no auto-resume capability for paused loops within an attempt limit (that waits for tier inference). This is a real constraint that should be called out more explicitly in the "Current State" section as a deployment concern.

### Run Digest

- Response length: 7057 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 137957 / 57930 / 80001 / 18070 / not computed
- Duration: 199.2 s
- Cost: $0.26 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
