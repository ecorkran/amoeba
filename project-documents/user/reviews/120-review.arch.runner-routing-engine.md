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
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: eee1a176bb918979573abaa5b4eb2d8dd3199c7a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
turns: 2
promptTokens: 82026
cachedTokens: 9622
cacheWriteTokens: 72400
completionTokens: 5801
durationSeconds: 52.6
costUsd: 0.34925
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Journaled-effect rule contradicts the journal's command kinds and the contract-change list"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F002
    severity: concern
    category: consistency
    summary: "\"Pure decision step with no I/O\" is not reconcilable with observation, and tick sequencing contradicts the one-decision rule"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F003
    severity: concern
    category: completeness
    summary: "Run identity and crash recovery rest on a deferred choice, yet the first slice's proof depends on them"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F004
    severity: concern
    category: feasibility
    summary: "Non-blocking subprocess model is unspecified at the points where it can break"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#observing-a-run-without-blocking-the-tick"
  - id: F005
    severity: concern
    category: completeness
    summary: "Dispatch granularity, the premise of the whole lifecycle model, is still \"proposed; PM to ratify\""
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F006
    severity: concern
    category: completeness
    summary: "Two sources of truth for lifecycle state, with no reconciliation or conflict rule"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#the-lifecycle-model"
  - id: F007
    severity: concern
    category: feasibility
    summary: "Git branch handling in a shared working tree is hand-waved"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F008
    severity: concern
    category: completeness
    summary: "Static routing table: \"recompute any decision\" and \"edit one place\" are not backed by mechanisms"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#design-goals"
  - id: F009
    severity: concern
    category: completeness
    summary: "Intent handling lacks idempotence and ordering semantics"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F010
    severity: concern
    category: completeness
    summary: "Tick-level failure handling and per-project fault isolation are not addressed"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#the-loop-per-tick-per-project"
  - id: F011
    severity: concern
    category: antipattern
    summary: "Overweight v1 scope: tier inference, baseline-diffed checks, scheduling, and multi-project generality ahead of a first vertical proof"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#anticipated-slices"
  - id: F012
    severity: note
    category: abstraction
    summary: "\"rerun\" overlaps Squadron's revise loops and checkpoint resume"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#the-routing-engine"
  - id: F013
    severity: note
    category: dependencies
    summary: "Upstream dependencies on Squadron are tracked but not gated"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#related-work"
---

# Review: arch — initiative 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Journaled-effect rule contradicts the journal's command kinds and the contract-change list

"Decide purely, act through the journal" says every side effect on CF, SQ, or git is a journaled command kind, with no unjournaled path. Current State lists the journal's kinds as `cf_write` and `sq_run` only. The "Contract changes the Runner needs from 100" list adds one review-producing kind and nothing for git. Yet the Runner creates and switches slice branches, and observation commands such as `cf status --json` and `sq runs wait` are also CLI invocations.

Branch creation and switching is the most crash-sensitive effect, because it mutates the working tree. It has no journal kind, no observer, and no recovery story. Either add git command kinds, with their keys and observers, to the 100 contract changes, or say which effects are exempt.

### [CONCERN] "Pure decision step with no I/O" is not reconcilable with observation, and tick sequencing contradicts the one-decision rule

The decision step is "a pure function from store state." The inputs it needs are run-state files, `cf status --json`, `projects.json`, and process exit. Those are I/O, and the document names no stage that reads them into the store before decide runs. There are really three stages: observe/ingest, decide, and effect. Only two are named.

"The loop, per tick, per project" says to ingest finished outcomes, compute and issue the next action for runnable nodes, and route each ingested outcome. The Architectural Principles say a tick advances each node by at most one decision. It is unclear whether a node whose run finished in a tick can have its outcome routed and its next command issued in that same tick. The order of "route" and "compute next action" in the prose also looks inverted: the routed outcome is what makes the next node runnable.

### [CONCERN] Run identity and crash recovery rest on a deferred choice, yet the first slice's proof depends on them

"Run identity and the hidden `--run-id`" defers the decision to slice design. The options are a hidden, non-contract flag with heuristic matching as the fallback, or waiting on Squadron's S9. Heuristic matching by pipeline, params, and time is not exact when two launches of the same pipeline with the same params are close together. That happens for a rerun after a failure, or a resume.

Ambiguity becomes a human block, so the failure mode is escalation noise rather than corruption. But the first anticipated slice promises a "no-op lifecycle step journaled, run, observed, and recovered across a `kill -9`." That proof can't be designed without the decision. Make the call now, or state which way the first slice goes and what S9 changes later.

### [CONCERN] Non-blocking subprocess model is unspecified at the points where it can break

The document says the Runner launches `sq run` as a child, polls it, and that the run "must survive or be cleanly observable" if the resident process stops. It does not say which of the two it commits to. If the child is attached, parent death can cause SIGPIPE or SIGHUP on its stdout/stderr pipes, or kill it outright. Surviving requires a detached session with output redirected to files, which the Runner then has to reap and tail.

It also doesn't say whether `tick()` is sync or async, or how child exit is detected after a restart. After a restart there is no `Popen` handle, so observation falls back to the pid or the run-state file. A `running` state that nothing is actually executing (a stale file) needs liveness detection. This is the hardest mechanical part of the design, and it is called "needs a design" without a position.

### [CONCERN] Dispatch granularity, the premise of the whole lifecycle model, is still "proposed; PM to ratify"

The step map, gate placement, per-node attempt limits, and the "blocked-state per slice" behavior all assume one phase of one slice per run. This is the load-bearing decision of the architecture and it remains unratified. If the PM picks combined pipelines, the node model (a node per lifecycle step) and the routing inputs change. Ratify it before the architecture is accepted, or mark which sections depend on it.

### [CONCERN] Two sources of truth for lifecycle state, with no reconciliation or conflict rule

The Runner "keeps 100's node tree in step with CF." The node tree is projected from plan documents and per-worktree CF pointers. Both CF (`activeSlice.status`, `gateInfo`) and the store (verdicts, `standing`) hold gate-relevant state. The document covers the case where CF clears and the store disagrees, and escalates. It doesn't cover:
- CF pointers moving because the PM ran `cf set` by hand mid-run.
- Plan documents edited or slices renumbered while nodes exist.
- Nodes whose source slice disappeared.

Parsing plan documents to create nodes is also a parser under the project's own rules. It needs real-document fixtures and lenient parsing, and is not mentioned as a risk. Node creation from outside the process is explicitly left open ("inbox kind or only a Runner-applied intent"), which this component depends on.

### [CONCERN] Git branch handling in a shared working tree is hand-waved

The Runner creates and switches slice branches. The concurrency rule only protects against Runner-vs-Runner collisions: "at most one mutating run per checkout." A PM working in the same checkout (the document says live pointers are per worktree, and humans use these trees) can have uncommitted work or a different branch checked out. Nothing says the Runner checks for a clean tree, detects a human-held checkout, or refuses to switch. Without that, switching branches under the PM is a data-loss risk. Because project rules say never to start from another unit's branch, the Runner also needs a pre-switch check that it is on the target or the expected slice branch.

### [CONCERN] Static routing table: "recompute any decision" and "edit one place" are not backed by mechanisms

"Given the store's contents and the routing table version, any decision can be recomputed." That requires retaining every table version that has ever fired, and the tier-inference rules and code version that were used. Only a version stamp is mentioned, and its format is deferred. The table is "loaded at start and never mutated," so every PM edit means a tenant restart, with in-flight runs adopted across it. That isn't addressed.

The "one edit point" goal is also weakened because tier inference, the Tier-1 predicates, and the ungate-hatch checks are code, not table data. They are routing behavior defined outside the table.

### [CONCERN] Intent handling lacks idempotence and ordering semantics

The loop reads intents, applies them, and acknowledges "what was applied." A crash between apply and acknowledge replays the intent. It isn't stated whether intents are idempotent, or whether apply plus acknowledge happen in one transaction. "Drive up to a lifecycle step" has no defined semantics when the step is already past. Conflicting intents (a pause arriving with a resume) have no ordering rule. The closed vocabulary is meant to be 160's contract, so these need to be pinned before 160 builds on it.

### [CONCERN] Tick-level failure handling and per-project fault isolation are not addressed

Failure handling is covered per run (paused, failed, cost cap, missing). It is not covered for the Runner's own operations. For example:
- A `cf` or `sq` binary that is missing or has changed its JSON.
- An unparseable run-state file.
- A project directory that vanishes.
- A store write that fails mid-ingestion.

"Unknown escalates" covers data, not exceptions. "Many projects, one loop" needs a stated rule that one project's exception can't abort the tick for others. Because the project rules ban swallowed exceptions, the catch point (a top-level handler at the process boundary vs. per-project) should be named.

### [CONCERN] Overweight v1 scope: tier inference, baseline-diffed checks, scheduling, and multi-project generality ahead of a first vertical proof

Six slices cover the tenant, lifecycle projection, intents, dispatch and ingestion, a routing engine with inferred tiers, gate and check machinery, and multi-project scheduling with per-checkout exclusivity and cost limits. Several are speculative relative to the first proof the document itself names (one PM-chosen unstarted unit):
- **Tier inference.** It stands in for a Squadron field (S1) that is expected to replace it, and "shrink" the rules. Until then, a table over verdict, `standing`, and recurrence that escalates everything else would deliver the audit trail without inventing a classifier.
- **Baseline-diffed Tier-1 checks.** These are real work (test diff against baseline), and the only consumer is the tier rules above.
- **Global run and cost limits.** Squadron's `max_cost_usd` already bounds spend per run.
- **"Do not foreclose programs."** This adds a predecessor abstraction before a second project depends on it. It is cheap, but it is a hypothetical-requirements item.

Defer tier inference and baseline-diffed checks until the first proof shows which wrong stops matter. Drive a single project first and make multi-project fairness a follow-up.

### [NOTE] "rerun" overlaps Squadron's revise loops and checkpoint resume

The route set includes **rerun**, "issue a Squadron loop again, bounded by a per-node attempt limit." A paused run is resumed via `--resume`. A failed run is escalated. A completed run with CONCERNS is rerun. It isn't defined what a rerun carries into the new run (the previous findings? the resolution's instructions?), or how it differs from the "rerun with instructions" resolution of an escalation. The attempt counter's scope (per node, or per node and kind) is also not stated.

### [NOTE] Upstream dependencies on Squadron are tracked but not gated

The design relies on run-state file semantics, `sq runs wait` exit codes, and review frontmatter. These are observed, not contracted. S1, S8, and S9 are open. The document handles this by observing rather than depending, which is reasonable, but nothing says what version-compatibility check the Runner performs at start. An unrecognized run status is treated as an unknown that escalates, which covers one drift case but not field renames.

### Run Digest

- Response length: 11947 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 82026 / 9622 / 72400 / 5801 / not computed
- Duration: 52.6 s
- Cost: $0.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
