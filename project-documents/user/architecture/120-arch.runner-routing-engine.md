---
docType: architecture
layer: project
project: amoeba
archIndex: 120
component: runner-routing-engine
initiative: runner-routing-engine
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [100-arch.substrate-run-state-store]
relatedSlices: []
riskLevel: medium
audience: [human, ai]
description: Architecture for Amoeba's Runner and routing engine — the deterministic lifecycle loop that runs as a tenant of the resident process, dispatches Context Forge and Squadron work, records what comes back, and routes every outcome to advance, Judge, or a persisted blocked-state through a static routing table.
dateCreated: 20261020
dateUpdated: 20261020
status: in_progress
---

# Architecture: Runner & Routing Engine

## Overview

The Runner is the project's core artifact: a deterministic state machine that drives a project through its Context Forge (CF) / Squadron (SQ) lifecycle with zero discretion of its own. Its loop is the concept's: *while runnable work exists, issue a command, read what comes back, apply the routing table, and advance, send to the Judge, or write a blocked-state.* The routing engine is the table and the rule-application step inside that loop. Together they are the only part of Amoeba that **acts**: the substrate (100) stores and observes, the Judge (140) evaluates, the Translator (160) interprets, and the Runner is what turns state into the next command.

**The problem it addresses.** With 100 complete, Amoeba can remember everything and notice everything, and do nothing. A slice still advances only when a human runs `cf set`, launches `sq run`, reads the review, decides whether CONCERNS is acceptable, resumes a paused run, and does it again. Most of those decisions are mechanical. Squadron has since automated the *within-artifact* half (revise → review → gate loops inside one pipeline run) but stops at the run boundary: a run that cannot converge exits paused, and nothing picks it up, carries it across days, or decides what the next run should be.

**Scope.** This component owns: (1) the **Runner tenant**, hosted in the resident process beside the shipped tenants; (2) the **control surface**, the closed set of CF and SQ commands the Runner issues, each journaled before it runs and observed until it finishes; (3) the **lifecycle model**: how a project's CF plan and pointers become nodes in 100's tree, and what "runnable" means for each node kind; (4) **outcome ingestion**: turning a finished run's reviews, run state, and CF gate state into store records under 100's evidence rules; (5) the **routing engine**: tier inference, the routing table, and a recorded decision for every outcome; (6) the **intent vocabulary**: what an `intent` message may ask the Runner to do. It does **not** own consensus or judge invocation (140), natural-language interpretation or notification (160), within-artifact revise loops (Squadron's), or the store, inbox, feed, and observers it builds on (100).

**Motivation.** Everything before this initiative is plumbing for it, and everything after it (140, 160, 180) attaches to its decisions. It is also where the project's method lives: "build by inducing failure" edits the routing table, so the table has to be data, auditable, and the only place routing behavior is defined.

## Design Goals

- **Zero discretion, total auditability.** Every action the Runner takes is the output of a fixed rule over recorded inputs. Given the store's contents and the routing table version, any decision can be recomputed and explained after the fact: which rule fired, on which evidence.

- **Unattended between decisions that need a person.** A slice goes from "design pending" to "implemented and reviewed" without a human touching it, *unless* the routing table says a human is the next step. When it does, the Runner writes the blocked-state, moves on to other runnable work, and resumes the node when the resolution lands, hours or days later, across restarts.

- **Squadron does the work; the Runner decides what work is next.** The Runner never reimplements what a Squadron pipeline already does (generation, review, revise loops, gating inside a run). It chooses which pipeline runs on which node, and routes what the run returns.

- **One edit point for routing.** Changing how a kind of outcome is handled means editing the routing table and nothing else. No routing behavior is coded in branches outside it.

- **Many projects, one loop.** The Runner serves every project in the supervisor directory from one tenant, with no per-project process and no assumption that projects are unrelated, so programs (180) are a later addition, not a rewrite.

## Architectural Principles

- **Decide purely, act through the journal.** The Runner splits into a decision step and an effect step. The decision step is a pure function from store state (plus the routing table) to the next actions; it does no I/O. The effect step issues each action as a journaled command (`journal_issue` before, result recorded after) and nothing else. Every side effect on CF, SQ, or git is a journaled command kind; there is no unjournaled path.

- **The tick never waits.** The tenant obligation is binding: `tick()` returns promptly. Long work is a subprocess the Runner launches, then observes on later ticks (process exit, Squadron's run-state file) until it finishes. A tick advances each project by at most one decision per node; a slow run never stalls other projects.

- **Observe outcomes from the contract, not the conversation.** What a run did is read from Squadron's machine surfaces (run-state file, `--output json`, review artifact frontmatter) and CF's (`cf status --json`, `projects.json` snapshots), never from stdout prose, `cf next`'s `recommendation` text, or exit code alone (`sq run` exits 0 for both completed and paused).

- **Unknown escalates.** A missing field, an unparseable artifact, an unrecognized run status, a review with no attributable node: each becomes an explicit unknown routed to a human, never a guessed value. Routing rules may match "unknown"; they may not default it away.

- **The table is static config.** The routing table and every threshold in it are loaded at start and never mutated at runtime. Calibration evidence (100's report, later 140's) produces *recommendations* the PM applies by editing the table. This is also Squadron's permanent metrology constraint.

- **Closed vocabularies for everything routed on.** Command kinds, intent kinds, inferred tiers, route outcomes, and lifecycle steps are enumerations defined once. Squadron's free-form `category` and CF's prose are carried as evidence and never matched as structure.

- **Respect the store's rules as the store's caller.** The Runner writes through 100's public API only, follows the attribution rule and D5 to the letter, never caches `project_ids`, and adds tables only through 100's migration mechanism. Where the Runner needs something the contract lacks, the contract changes first.

## Current State

- **Amoeba (100 complete).** The resident process hosts tenants and reconciles every journaled command before any tenant ticks. The store has the node tree, the six statuses, `block`/`resolve`, the two Runner queries (`runnable`, `blocked`), the command journal (`cf_write`, `sq_run`), verdict and finding records with a computed trust label (`standing`) and round-over-round `finding_changes`, checks with `vacuous ≠ passed`, `record_runner_report`, the `intent` channel (`pending_intents` / `acknowledge_message`), CF snapshots, and the change feed. A stand-in Runner in `tests/contract/` proves the path end to end. Requirements already binding on 120 are written in the contracts: the attribution rule, D5 points 3 and 5, `run_id` in every `sq_run` result, "a resume whose run is missing is a failed command", the tenant obligation, and no secrets in journal entries. Two gaps the Runner will hit: `done` is documented as terminal but not enforced by `update_node_status`, and no inbox kind creates nodes ("node creation from outside the process arrives with 120"). The intent body format is undefined, by design: it is 120's and 160's.

- **Squadron (observed 20261020).** Per-phase pipelines exist for architecture (P2), slice design (P4), tasks (P5), and implementation (P6), plus combined (P45, P56, P456) and plan-wide batch pipelines (`slices-plan`, `tasks-plan`, `implement-plan`). Each phase pipeline revises until its review passes and checkpoints otherwise; a non-interactive checkpoint exits with the run saved as `paused`. There is no slice-plan (P3) pipeline. `sq run` has no JSON output and exits 0 for completed *and* paused; the outcome is in the run-state file (`running | completed | paused | failed`, with `checkpoint{reason, step, verdict}`) or via `sq runs wait <id>` (distinct exit codes per outcome). A hidden `--run-id` lets a caller choose the run id. Findings now carry `location_verified`; `verdictSource` (`stated | derived | imposed`) is in frontmatter and JSON; `stop_reason` and related fields are JSON-only. Still absent: a tier field (S1), a review-completed event (S8), escalation on checkpoint (SQ 185). Runs can fail with `cost_cap` under `pipeline.max_cost_usd`.

- **Context Forge (observed 20261020).** `cf status --json` exposes `activeSlice.status` including `pending-review`, `review-failed`, and the new `pending-decision` (with `pendingDecisions[]`), plus `gateInfo`. `cf set` has no JSON output; writes are confirmed by reading back. Live pointers are per worktree. There is no execute mode; CF stays advisory and Amoeba is the executor. The two silent-ungate hatches (`review: none`, `dateCreated` before the effective date) still exist.

**Constraints this imposes:** the Runner observes run outcomes from files and process exit rather than from events; it can make recovery exact only by relying on a flag Squadron has not made public; and phases with no Squadron pipeline (P3, P7, merges, host cutovers) have no automated executor, so they are human steps for now.

## Envisioned State

At completion, the Runner is one tenant, ticking last in the resident process, that drives every project in the supervisor directory.

**The lifecycle model.** For each project, the Runner keeps 100's node tree in step with CF: initiatives and slices from the plan documents, and below each slice a node per lifecycle step (design, tasks, implementation) with a gate node where CF or the routing table requires a review. Nodes are created and reconciled by the Runner from CF's plan and pointers; the PM (and later the Translator) steers through `intent` messages: what to drive, how far, and when to stop. Every lifecycle step maps to exactly one of: a Squadron pipeline the Runner may run, a CF write it may make, or a **human step** that is a `blocked_on_human` node from the moment it becomes current.

**The loop, per tick, per project.** Read pending intents and acknowledge what was applied. Observe any in-flight runs; for each that finished, ingest its outcome. For each node that is runnable, compute its next action (pure), then issue it (journaled). For each ingested outcome, route it.

**Outcome ingestion.** A finished run yields evidence, not a verdict to trust: the run's final status and checkpoint, every review artifact it wrote (recorded from the artifact through 100's parser, attached by the attribution rule, marked `runner_issued` in the same transaction that resolves the journal entry), CF's gate state for the slice, and any checks the Runner ran itself. A run that exited paused becomes a `blocked_on_sq_checkpoint` node holding its run id; a run that failed, timed out, hit its cost cap, or cannot be found becomes a `blocked_on_human` node with the reason.

**The routing engine.** Each outcome is reduced to routing inputs: verdict and its `standing`, each finding's inferred tier, `finding_changes` against the last round, gate state, check outcomes, and run status. The table maps these to exactly one route from a closed set: **advance** (mark done, make the next node runnable), **rerun** (issue a Squadron loop again, bounded by a per-node attempt limit in the table), **judge** (block on the Judge), or **escalate** (block on a human). Every application writes a decision record (inputs, rule id, table version, route), which is both the audit trail and the raw material for "build by inducing failure." Until 140 exists, the judge route is defined in the table as escalate-and-label: the human gets the finding, and the record says the Judge would have been asked. When 140 lands, the same rule points at it with the concept's always-escalate threshold.

**Tier inference (v1).** No upstream tier field exists, so the Runner infers one per finding from closed signals only: severity, `location_verified`, the verdict's `standing`, recurrence in `finding_changes`, and the result of the Runner's own Tier-1 predicates (checks such as "file exists", "validator examined more than zero files", "test diff against baseline"). A finding the rules cannot classify is Tier 2, never Tier 1. When Squadron emits a tier (S1), it becomes one more input and the inference rules shrink.

**Resolution and resumption.** A human resolution or (later) a Judge result lands through the inbox and flips the node to runnable. The Runner's next action for a resolved checkpoint node is an explicit `sq run --resume <run_id>` carrying the resolution's decision; for a resolved escalation, whatever the resolution says (accept and advance, rerun with instructions, or stop the node). A resume whose run is missing is a failed command: the node blocks on a human, and the run is never relaunched.

**What it emits.** Nothing new on the wire: every node, verdict, and message write already appears on 100's feed. A subscriber (the notification bridge, a status view) sees the Runner's work as node status changes and escalation messages.

## Technical Considerations

- **Dispatch granularity — per-phase pipelines (proposed; PM to ratify).** Squadron now offers per-phase pipelines (P4, P5, P6), combined ones (P456), and plan-wide batch runs (`implement-plan`). Combined and batch runs move inter-phase gates and slice ordering *inside* one Squadron run, where the Runner cannot route on them, cannot block one slice without the rest, and sees a whole plan as one paused run. Recommendation: the Runner dispatches **one phase of one slice per run**, so every gate CF or the routing table cares about falls between runs, which is exactly where the Runner acts. Batch pipelines stay available to the PM by hand; reviews they produce arrive through 100's detection like any other PM-launched review.

- **Run identity and the hidden `--run-id`.** Recovery today matches a journaled launch against Squadron's runs directory by pipeline, params, and time; ambiguity becomes a human block. Squadron's `--run-id` would let the Runner choose the id at journal time and make recovery exact, and would let it mint the verdict id up front (100's retry rule). The flag is hidden and was added for replay, so it is not a contract. Slice design decides between using it with the matching observer as the declared fallback for runs it cannot place, or asking Squadron to make it public first (dependency S9). Either way the choice is explicit and recorded per entry, never silent.

- **Observing a run without blocking the tick.** The Runner launches `sq run` as a child process with non-TTY stdin (100's invariant: no implicit resume) and polls it on later ticks. Two cases need a design: the resident process stopping while a run is in flight (the run must survive or be cleanly observable afterwards; the journal entry is reconciled by 100's recovery, and the Runner then keeps observing an adopted `running` run), and a run that never ends (a per-pipeline time bound in the table, after which the node escalates). `sq runs wait` is an option for the observation step only if it can be used without blocking.

- **Concurrency is bounded by the working tree.** Two runs that write files in one checkout collide. The default is at most one mutating run per checkout (CF worktree), with read-only work (reviews of a committed SHA) free to overlap. Across checkouts and projects, a global limit on in-flight runs and Squadron's `max_cost_usd` bound spend. A `cost_cap` failure escalates; it is never retried automatically.

- **Git and the integration target are the PM's.** Slice branches are created and switched by the Runner, from the target `cf config get git.integration_branch` resolves, per the project's branch rules. **Merging is a human step** by default ("no merge before code review", merge only on the PM's word); the table can later make it automatic for a node class once the PM decides to. Never: merging to `main` when an integration branch is set, deleting branches, pushing.

- **Gates come from CF's structured status, and are not trusted alone.** The Runner reads `activeSlice.status` and `gateInfo` through `cf status --json`, never `cf next`'s prose. `pending-decision` is a human step. A CF gate that clears on a `derived` or `imposed` verdict, or on a review whose `standing` is not trustworthy, is still routed on the store's view, not CF's. The two silent-ungate hatches are Tier-1 checks the Runner runs: if either is present, the node escalates; the Runner never writes `review: none`.

- **What the routing table matches on.** Inputs are closed: run status, verdict, standing, inferred tier, finding severity, recurrence (`new` / `recurring` / `gone`), check standing, attempt count, node kind, and lifecycle step. Rules are ordered, first match wins, and the table must end in a catch-all that escalates. The table format, where it lives (per supervisor, with per-project overrides or not), and how its version is stamped on each decision are slice design's.

- **Tier-1 predicates are cheap and must be honest.** Field data shows validators that exit 0 having checked nothing and `main` carrying known failures. Every check the Runner runs records what it examined and compares against a baseline, using 100's check records; a vacuous check is never a pass.

- **Intent is a closed command set.** Before the Translator exists, the PM steers the Runner by submitting intents directly. The vocabulary is small and structural (start or stop driving a project, slice, or plan; drive up to a lifecycle step; pause; resume a node), and an intent the Runner cannot apply is acknowledged with an explicit rejection rather than ignored. This vocabulary is the contract 160 will translate natural language into; 160's command-authority whitelist (OQ5) is a subset of it.

- **Contract changes the Runner needs from 100.** Enforce `done` as terminal in `update_node_status`; add the Runner's review-producing command kind to `REVIEW_PRODUCING_KINDS` with its required keys and observer (process contract: enum member, keys, observer, all three); add any routing-decision and finding-disposition tables through the migration mechanism; decide whether node creation from outside the process is an inbox kind or only a Runner-applied intent.

- **Do not foreclose programs.** Cross-project dependency edges (180) will make a node in one project wait on a node in another. The decision step therefore reads "is this node's predecessor done?" through one function, so a cross-project predecessor is an added input, not a rewrite.

## Anticipated Slices

Exploratory, not a commitment:

- **Runner tenant and control surface.** The tenant composed after `standard_tenants`; the pure decide / journaled act split; launching, polling, and observing CF and SQ subprocesses without blocking the tick; the non-TTY invariant; run identity; the 100 contract changes above. Proof: a no-op lifecycle step journaled, run, observed, and recovered across a `kill -9`.
- **Lifecycle model and intent.** Projecting a CF plan and worktree pointers into the node tree and keeping it reconciled; the step map (pipeline, CF write, or human step) for each node kind; the intent vocabulary and its acknowledgment.
- **Run dispatch and outcome ingestion.** Per-phase pipeline dispatch; ingesting reviews under the attribution rule and D5; paused, failed, timed-out, cost-capped, and missing runs as blocked-states; explicit resume with the resolution's decision.
- **Routing engine.** The table as static versioned config; tier inference; decision records; advance / rerun / judge / escalate with per-node attempt limits; the judge route as escalate-and-label until 140.
- **Gates, checks, and human steps.** CF review and decision gates, ungate-hatch detection, baseline-diffed Tier-1 checks, merge and other human-only steps, branch handling against the integration target.
- **Scheduling and first proof.** Multi-project ticking, per-checkout exclusivity, run and cost limits; then the first vertical proof on a PM-chosen unstarted unit, whose wrong stops become the next routing rules.

## Related Work

- Concept: `user/project-guides/000-concept.amoeba.md`: the Runner definition, the checkpoint-as-persisted-blocked-state decision, Tier 1/2/3 routing, findings B, C, F, G, H, and "Multi-project programs".
- Initiative plan: `user/project-guides/001-initiative-plan.amoeba.md`: initiative 120 scope; 140, 160, and 180 depend on this component.
- Foundation: `user/architecture/100-arch.substrate-run-state-store.md` and `100-slices.substrate-run-state-store.md`.
- Contracts the Runner codes against: `docs/substrate-guide.md` (start here; the 120 row and "Four things a Runner author does"), `docs/process-contract.md` (hosting tenants, the tenant obligation, observers, pruning and the missing-resume rule), `docs/store-contract.md` (node writes, blocked-state writes, the Runner queries, the command journal), `docs/evidence-contract.md` (the attribution rule, D5, standing, checks), `docs/inbox-contract.md` (intent and resolution), `docs/context-forge-contract.md` (snapshots, D8), `docs/feed-contract.md`. The stand-in Runner in `tests/contract/` is the working reference.
- Upstream ground truth: `user/notes/002-upstream-delta.amoeba.md` (September grounding; the Current State above supersedes it where they differ) and the dependency register `user/notes/001-squadron-dependencies.amoeba.md` (S1 tier, S8 review-completed event, S9 run id; S6 and S7 are now met in JSON by `verdictSource` and `location_verified`).
- Squadron: `data/pipelines/` (P4, P5, P6, judge-cycle, findings-addressed-cycle), `pipeline/state.py` (run-state file), `pipeline/run_wait.py` (`sq runs wait`), `pipeline/executor.py` (non-interactive checkpoint).
- Context Forge: `docs/REVIEW-GATING.md`; `core/src/introspection/types.ts` (`activeSlice.status`, `gateInfo`, `pendingDecisions`).
