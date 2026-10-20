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
reviewedSha: 46b4c60a9b4ae7026163c3955a19dfc8530fc857
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
turns: 2
promptTokens: 85759
cachedTokens: 12780
cacheWriteTokens: 72975
completionTokens: 6772
durationSeconds: 59.3
costUsd: 0.361576
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: feasibility
    summary: "\"Tick never waits\" is not bounded across projects and runs"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F002
    severity: concern
    category: consistency
    summary: "Decide is \"pure\", but the reads it needs depend on Decide's candidates"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F003
    severity: concern
    category: consistency
    summary: "The \"Act issues only journaled commands\" rule conflicts with Runner-executed checks and with \"parses no plan markdown\""
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F004
    severity: concern
    category: consistency
    summary: "Resolution options contradict the stated limit on instructions"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Autonomy goal undercut by pause-reason gap and single-checkout exclusivity"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F006
    severity: concern
    category: completeness
    summary: "Launch race: `not found` is ambiguous right after detached launch"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F007
    severity: concern
    category: completeness
    summary: "Intent semantics need persisted desired-state that no table provides"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F008
    severity: concern
    category: completeness
    summary: "Fault policy: every fault escalates to a human, and fault-with-no-node is deferred"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F009
    severity: concern
    category: feasibility
    summary: "Amount of upstream-contract change and bundled scope in the first slice"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#anticipated-slices"
  - id: F010
    severity: concern
    category: antipattern
    summary: "Scope that can be cut or deferred from v1: merge-policy variant, batch, judge-eligible marks, programs seam"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F011
    severity: concern
    category: abstraction
    summary: "Index-based CF identity makes renumbering destructive to evidence continuity"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
---

# Review: arch — initiative 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] "Tick never waits" is not bounded across projects and runs

The tick is synchronous. Per project, it runs `cf status --json`, `cf list slices --json`, `git status` per candidate checkout, and one `sq runs wait <id> --timeout 0` per in-flight run. Each call has a per-call timeout, but the document sets no per-tick budget. Worst-case tick latency is projects × (runs + reads) × timeout. A few hung `cf` calls make the tick take minutes. That breaks the tenant obligation for the shipped tenants that tick before the Runner. Every fault, including a timeout, also escalates to a human (see the fault-handling finding). The design needs one of these:
- a per-tick deadline with round-robin resumption;
- bounded parallel subprocess fan-out for reads;
- an observation cadence slower than the tick.

### [CONCERN] Decide is "pure", but the reads it needs depend on Decide's candidates

Observe must record the git-clean and branch state, the CF pointer, and the checkout holder before Decide runs. Which checkouts matter depends on which nodes are runnable, and that depends on Decide and routing. The document does not say whether Observe reads everything speculatively or Decide requests reads. The dispatch sequence is also unspecified. It has a journaled `cf_write` of the pointer, a read-back confirmation (`cf set` has no JSON output), and then `sq_run`. That is two journaled actions with a confirmation between them, which cannot happen within one pure Decide→Act pass. The Runner's own pointer write also fires `cf_project_changed`, which triggers reconciliation. The document does not say how self-caused changes are told apart from foreign ones. It matters because "a pointer someone else moves" escalates a node that has a run in flight.

### [CONCERN] The "Act issues only journaled commands" rule conflicts with Runner-executed checks and with "parses no plan markdown"

Outcome ingestion and the Tier-1 predicates say the Runner runs checks itself, such as "the validator examined more than zero files". These are side-effecting, potentially long subprocesses (validators, later baseline-diffed tests). They are neither read-only Observe calls nor one of the two journaled kinds (`sq_run`, `cf_write`). They are also not covered by the short per-call timeout. The ungate-hatch checks (`review: none`, `dateCreated` before the effective date) need slice-document frontmatter. That contradicts "the Runner parses no plan markdown of its own". Define a check execution model (journaled or not, timeout, which tick runs it) and say where the hatch data comes from (CF output or direct file reads).

### [CONCERN] Resolution options contradict the stated limit on instructions

"Resolution and resumption" lists "rerun with instructions" as a resolution outcome. The routing-engine section says per-phase runs have no path for instructions, since only `--resume <id> --item N --instructions` on a batch item accepts them. The result is a resolution type the Runner cannot execute for v1 per-phase dispatch. The resolution vocabulary needs to be closed against what is executable, and the Runner must reject unsupported resolutions explicitly. The document also never says how a checkpoint "decision" is passed to `sq run --resume`. Detached runs have stdin from `/dev/null`, and 100 requires a non-TTY invariant with no implicit resume. This resume mechanism is load-bearing and under-specified.

### [CONCERN] Autonomy goal undercut by pause-reason gap and single-checkout exclusivity

Goal 2 says the Runner "moves on to other runnable work" while a human decides. Three things limit that:
- A checkout is held while a run is paused, possibly for days, and the PM's normal case is one worktree per project. One paused run therefore blocks every other node in that checkout.
- Until S10, pause reasons are not machine-readable, and "an unexplained pause escalates". Every pause is effectively a human stop with no routing.
- Squadron's `--run-id` is on main but unreleased, and S10 does not exist.

The first proof therefore depends on unreleased upstream behavior. Document the expected throughput honestly. Consider whether a blocked node's checkout can be released, or state that one-node-at-a-time per checkout is the v1 experience.

### [CONCERN] Launch race: `not found` is ambiguous right after detached launch

Runs are launched detached with the id minted up front. `run_id=` is printed on stderr only before the first step. The next tick's `sq runs wait <id> --timeout 0` can therefore return `not found` for a run that has not yet written state. A run refused at argument validation, or one that crashed before state existed, returns the same code. "A run that cannot be found" is specified to become `blocked_on_human`, so the Runner will either escalate spuriously or leave a launch failure undetected. The design needs a launch grace period or an explicit launch-failure signal. Reading the per-run log file or the child's exit status would give one. The stderr line the Runner depends on goes to a log file the Runner is never described as reading.

### [CONCERN] Intent semantics need persisted desired-state that no table provides

Intents set a desired state on a target node, the "nearest intent on the path" governs, and held-true on an ancestor wins. Intents are acknowledged and consumed in one transaction. The contract-change list adds routing-decision, table-version, and attempt-count tables, but no table for per-node desired state (driven, drive-to step, held). Either the Runner recomputes governing intent by replaying acknowledged messages every tick, which is expensive and depends on "store's message order", or a table is missing. The two-sentence ordering rule also mixes arrival order with tree precedence, and the document does not say what happens when a node is reparented or orphaned. The Runner is also unable to feed back "rejected" until 100's acknowledgment-outcome change lands.

### [CONCERN] Fault policy: every fault escalates to a human, and fault-with-no-node is deferred

A CF timeout, a transient JSON glitch, or a momentarily missing directory becomes a `blocked_on_human` escalation with the retry class deferred to "after the first proof". With the per-call-timeout design above, transient faults will be common, and each costs a human action. Open points:
- Faults with no node ("a failed plan read") are left to slice design, which is a load-bearing deferral.
- A fault escalating a node that has a run in flight is not defined. It is unclear whether ingestion still happens when the run finishes, or whether the checkout is held.
- A project with a persistent fault produces a new escalation every tick unless deduplicated.

At minimum, specify dedup and a consecutive-failure threshold. The cost is small and it avoids notification storms.

### [CONCERN] Amount of upstream-contract change and bundled scope in the first slice

The first slice bundles:
- the tenant;
- observe/decide/act;
- detached launch and run identity;
- per-project fault isolation;
- all of the "Contract changes the Runner needs from 100" (`done` terminal enforcement, `REVIEW_PRODUCING_KINDS`, `sq_run` required keys and observer, ack outcomes, recovery and pruning migration off the run-state file, new migrations);
- a `kill -9` recovery proof.

That is several slices of work, and 100 is described as complete. Splitting out the 100 contract changes as their own slice (or a 100 follow-up) would put the dependency direction right: contract first, then Runner. Otherwise the first proof absorbs a modification of its own foundation.

### [CONCERN] Scope that can be cut or deferred from v1: merge-policy variant, batch, judge-eligible marks, programs seam

Several mechanisms serve hypothetical or later needs:
- The per-project auto-merge policy, and Amoeba's own "P6 without merge" pipeline. This is a forked copy of a Squadron pipeline that the document admits "will drift". It exists to serve human-merge as the default, but human merge could be a plain human step that waits on a git observation, with no pipeline fork until S11.
- The batch-dispatch design (`items[]` mapping), a "planned" feature detailed before the first proof.
- The judge-eligible field on escalations for a component (140) that does not exist.
- The single-function predecessor seam for 180 programs.

Cut or defer these. Auto-merge and the pipeline fork in particular add a second dispatch path and a recorded policy input to every dispatch decision.

Separately, the concept locks tier inference inside Amoeba for v1, yet it is deferred past the first proof, with a first table that "escalates everything else". That drops scope the plan assigns to this architecture. Record the deferral explicitly as a change to the plan, with a trigger (which first-proof stops justify it). Otherwise v1 ships as a routing table over run status and verdict only, with little automatic advance.

### [CONCERN] Index-based CF identity makes renumbering destructive to evidence continuity

Node identity links to CF by slice index only. A renumbered slice becomes an orphan plus a new node, and the PM "sorts out which is which". The orphan keeps its verdicts, findings, attempt counts, and blocked-states, and the new node starts with none. Round-over-round `finding_changes` and attempt limits then reset silently, which undermines recurrence-based routing. The Runner has no merge or relink operation, and none is defined as an intent. Either add a relink intent to the closed vocabulary, or state that attempt and recurrence history is lost on renumbering.

### Run Digest

- Response length: 10976 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 85759 / 12780 / 72975 / 6772 / not computed
- Duration: 59.3 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
