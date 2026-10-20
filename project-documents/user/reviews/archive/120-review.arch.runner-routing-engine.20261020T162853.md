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
reviewedSha: 26f6e3911bbb48c449a2de616c33d365217754aa
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
turns: 2
promptTokens: 84534
cachedTokens: 12780
cacheWriteTokens: 71750
completionTokens: 4309
durationSeconds: 48.7
costUsd: 0.332046
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "\"Decide is a pure function with no I/O\" conflicts with in-tick CF/git observation and same-tick successor dispatch"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F002
    severity: concern
    category: feasibility
    summary: "Synchronous subprocess observation inside a \"never waits\" tick is unbudgeted"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F003
    severity: concern
    category: antipattern
    summary: "One `sq runs wait` child process per in-flight run, with unspecified lifecycle"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F004
    severity: concern
    category: completeness
    summary: "Concurrency rule (\"one mutating run per checkout\") has no owner, key, or recovery semantics"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Clean-tree precondition vs. Squadron's own writes between phases"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F006
    severity: concern
    category: completeness
    summary: "Intent and observation transaction boundaries do not cover the journal–launch gap for non-run commands"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F007
    severity: concern
    category: completeness
    summary: "Reconciliation rules leave the lifecycle node model underspecified for CF-driven pointer moves"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F008
    severity: concern
    category: abstraction
    summary: "Judge route \"escalate-and-label\" and rerun semantics blur the closed route set"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F009
    severity: concern
    category: dependencies
    summary: "Heavy dependence on unreleased and internal upstream surfaces"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F010
    severity: concern
    category: antipattern
    summary: "Scope is heavy for a first proof: batch dispatch, tier inference, merge policy, and multi-project are all designed in"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#anticipated-slices"
  - id: F011
    severity: concern
    category: completeness
    summary: "Intent semantics: \"desired state, idempotent\" combined with ordering and supersession is not fully defined"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F012
    severity: note
    category: completeness
    summary: "Crash-recovery of in-memory tick state and exactly-once ingestion"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F013
    severity: note
    category: completeness
    summary: "Per-project fault handler escalates to `blocked_on_human` even for transient faults"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
---

# Review: arch — initiative 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] "Decide is a pure function with no I/O" conflicts with in-tick CF/git observation and same-tick successor dispatch

The "Observe, decide, act" principle says Decide does no I/O. "The tick never waits" says that after ingestion and routing, the Runner decides for every node "runnable *at that point*" and a successor can be dispatched in the same tick. Several preconditions the document requires are observations, not store state:
- The clean-tree check and branch check ("Before any branch switch, the Runner observes the tree").
- The ungate-hatch checks.
- `cf status --json` gate state.

A successor dispatched in the same tick therefore needs fresh git and CF reads between Route and Decide. Those reads are either done before Decide (so they are stale for a successor that only became runnable mid-tick) or inside Decide (so it is not pure). The document must say which. Otherwise "any decision can be recomputed from the store" fails, because the clean-tree and hatch observations are not clearly recorded as inputs. These checks are also synchronous subprocess calls. Run for many projects, they conflict with "tick() returns promptly" and need a bound or a deferral model.

### [CONCERN] Synchronous subprocess observation inside a "never waits" tick is unbudgeted

Observation relies on `cf status --json`, `cf list slices --json`, `git status`, launching detached `sq run`, and spawning `sq runs wait <id>` children. Each is a process spawn made from a synchronous `tick()`. With N projects, per-tick latency grows linearly, and a hung `cf` or `git` (a lock file, a network filesystem) stalls every project. This contradicts "a slow run never stalls other nodes or projects." No per-call timeout, no budget, and no policy for a timed-out read is given. The per-project fault handler only catches exceptions, not hangs.

### [CONCERN] One `sq runs wait` child process per in-flight run, with unspecified lifecycle

Observing by running a blocking `sq runs wait <id>` child per run and polling for its exit is a heavy way to read status. It has gaps:
- It is unclear whether `sq runs wait` blocks until the run finishes (so a child per in-flight run lives for hours) or returns immediately with a status code.
- The document does not say what the Runner does with those children after a resident-process restart (re-spawn all, per adopted run).
- It does not say how a `sq runs wait` that is itself stuck is told apart from a stuck run.
- "A run that never ends hits a per-pipeline time bound" is the only bound, and it applies to the run, not to the wait child.
Meanwhile "paused" and "completed" are distinguished only by that wait child's exit code. The document should state the `sq runs wait` blocking semantics it depends on, or use a non-blocking status call.

### [CONCERN] Concurrency rule ("one mutating run per checkout") has no owner, key, or recovery semantics

The rule is stated as a default but nothing says where it is enforced or what counts as "mutating". It is not stated whether it applies in the Decide step (as a runnability filter) or at Act time. It is also unclear what keys it: CF worktree path, or the checkout resolved after reconciliation. Open questions:
- Batch runs (`slices-plan`) mutate many slices in one checkout. Do they lock the checkout for the whole batch?
- A PM-held checkout, or a paused run that holds the tree, blocks everything. A paused `blocked_on_sq_checkpoint` node for days leaves a dirty tree. Because the Runner escalates when the tree is not clean, the checkout then deadlocks until the PM acts.
- The slice-branch rule ("expected slice branch for this node") conflicts with parallel slice work in one worktree.
This is load-bearing for "unattended" operation and is deferred without a stated owner.

### [CONCERN] Clean-tree precondition vs. Squadron's own writes between phases

The Runner switches or creates branches only on a clean tree. Per-phase dispatch means each Squadron run writes design, task, or code files and review artifacts, and the Runner or Squadron must commit them before the next phase. The document never says who commits Squadron's output, or whether `sq` does so. If nobody does, the tree is dirty after every successful run. The next branch operation escalates, or "advance" can never happen without a human. Commits are a git side effect that the closed command-kind list does not include (only branch creation, switching and merge). This is a probable first-proof blocker.

### [CONCERN] Intent and observation transaction boundaries do not cover the journal–launch gap for non-run commands

Run identity (`--run-id`) gives exact recovery for `sq run`. The other journaled kinds are `cf_write`, branch create, branch switch, and merge. For them the document claims reconciliation "the same way a CF write is" by reading back state. Idempotency is not addressed. `cf set` has no JSON output and is confirmed by readback. If the observer finds the state unchanged after a crash, is the command safely re-issued? A merge that crashed mid-way, or a branch switch interrupted with a dirty tree, may not be re-runnable. The retry versus escalate rule per command kind should be a required attribute of each command kind. It is currently left implicit in "observer reads the current branch and HEAD back".

### [CONCERN] Reconciliation rules leave the lifecycle node model underspecified for CF-driven pointer moves

Reconciliation runs on `cf_project_changed`. Three rules are stated, but gaps remain:
- "Moves away from a node with a run in flight → escalate" does not define behavior for a pointer move onto a node whose predecessors are not done.
- It does not define a rename, or a reorder of slices.
- Intent targets, attempt counts, and decision records are keyed to nodes, but nothing says how a node is identified stably across CF changes (slice index vs. name). Elsewhere the project rule is "never use user-accessible labels as logical structure". If node identity is derived from slice names or file names, that rule is violated. The document should state the identity key.

### [CONCERN] Judge route "escalate-and-label" and rerun semantics blur the closed route set

The route set is stated as closed (advance, rerun, judge, escalate), but `judge` is currently an alias for escalate with a label. It is therefore indistinguishable in behavior from `escalate`, and the audit record must carry "would have asked the Judge" as free text or a flag. Making `judge` a distinct route now adds an enum member with no behavior and a dependency on an undefined 140 interface. Either define the judge-request message shape now, so 140 is a drop-in, or drop the route until 140 and record a `would_judge` attribute on escalate. Rerun is also underspecified. "Prior findings carried through Squadron's findings-addressed mechanism" depends on a Squadron interface not named in the dependency list. S1, S8, S9, and S10 are listed, but this one is not, and no note says whether it is public.

### [CONCERN] Heavy dependence on unreleased and internal upstream surfaces

`--run-id` is "on main, not yet released". Pause reason (S10) does not exist. Review-completed events (S8) and tier (S1) are absent. The first proof must work with paused runs whose reason is unknown ("an unexplained pause escalates"), so nearly every non-converging run becomes a human block. The first routing table therefore cannot demonstrate its value, and the doc does not say what the first-proof acceptance criterion is if S10 slips. Separately, "move 100's recovery observer and pruning off run-state files" is a change to an already-complete component (100) that is bundled into the first slice, so its scope and ordering risk are not sized. The doc does not state a minimum Squadron version, even though it declines to gate on upstream version numbers. `--run-id` absent from an older `sq` would surface only as an unrecognized-flag failure. That conflicts with "depends on shapes", since a flag is a shape the Runner cannot probe in advance.

### [CONCERN] Scope is heavy for a first proof: batch dispatch, tier inference, merge policy, and multi-project are all designed in

The document sets the first proof as one project and one unit, then specifies several mechanisms for later:
- batch dispatch, with per-item resume and mapping `items[]` to nodes;
- tier inference;
- baseline-diffed checks;
- per-project merge policy;
- a program-aware predecessor function;
- an intent vocabulary shaped for 160's whitelist;
- stored table versions with full content per decision.
The scope text and Technical Considerations describe batch dispatch and the merge policy as supported ("Batch dispatch is also supported"), while the slice list defers batch to after the first proof. The Overview scope list and the Technical Considerations should state which mechanisms exist in v1 and which are only reserved. Batch dispatch, merge-policy config, and the single-function predecessor hook can be cut or reduced to a noted extension point, because nothing in the first proof uses them. Reserving the tier/predecessor hooks is cheap, but these should not be built.

### [CONCERN] Intent semantics: "desired state, idempotent" combined with ordering and supersession is not fully defined

Intents are applied in message order, and a later one supersedes an earlier one "for the same target". "Target" is undefined for overlapping scopes (a plan, a slice within it, and a node within the slice). A "stop driving plan" followed by "drive slice X" has an ambiguous result. "Pause" and "resume a node" read as increments or events, not desired states. They sit awkwardly next to "start or stop driving", which is a desired state. Specify the target hierarchy and the precedence between a broad intent and a narrow one, or this contract will be bent when 160 starts generating intents.

### [NOTE] Crash-recovery of in-memory tick state and exactly-once ingestion

Ingestion marks reviews `runner_issued` in the transaction that resolves the journal entry. That ties evidence to command resolution, which is good. The decision records and "route each ingested outcome" steps are not stated to share that transaction. A crash between ingestion and routing leaves an ingested but unrouted outcome. The doc should say that routing is derived from store state (an "ingested, unrouted" marker), not from the in-tick flow, so it resumes cleanly on restart.

### [NOTE] Per-project fault handler escalates to `blocked_on_human` even for transient faults

Every exception is recorded as a human escalation. A transient failure (a `cf` call timing out, a brief filesystem error) will block nodes until the PM resolves them. There is no retry or backoff class, and a persistent fault without a node ("where a fault has no node... slice design decides") has no stated home. This is acceptable for a first proof, but it will generate noise. Once the first stops are known, distinguish transient from structural faults.

### Run Digest

- Response length: 12620 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 84534 / 12780 / 71750 / 4309 / not computed
- Duration: 48.7 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
