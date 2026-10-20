---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/120-arch.runner-routing-engine.md
archIndex: 120
component: runner-routing-engine
audience: [human, ai]
description: Slice plan for Amoeba initiative 120 — decomposes the Runner and routing engine into substrate changes, the Runner's loop, lifecycle and intent, dispatch and ingestion, routing, resolutions, gates, and a first proof, with batch dispatch and tier inference after the proof.
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
---

# Slice Plan: Runner and Routing Engine

## Parent Document

`120-arch.runner-routing-engine.md`

## Planning Context

Architecture-level, built on a complete initiative 100. The Runner is new code, but it is a caller of 100's contract, and the arch says the contract changes first. So the plan opens with two foundation slices that change 100's side only, and every later slice codes against the changed contract.

Three things shape the decomposition:

- **The first proof is the turning point.** The arch puts tier inference and batch dispatch after the first proof, because the proof's wrong stops decide what they need. Slices 120–129 reach the proof. Slices 130 and 131 follow it and are still in this initiative's scope. Multi-project scheduling waits for real multi-project use and is listed under Future Work.
- **Squadron 0.23.5 carries everything the proof needs.** S9 through S13 were released on 20261020. The Runner checks the shapes at start (slice 122). It does not check version numbers.
- **One edit point for routing.** Only slice 126 decides routes. Slices before it ingest and record, and route nothing. A slice that needs a route before 126 exists escalates, which is the table's catch-all anyway.

Slice numbers are execution order. Following the slice-planning guide, the first slice takes the plan's index (120).

## Foundation Work

1. [ ] **(120) Run Identity and Supported Run Surfaces** — Moves 100's Squadron handling onto the surfaces Squadron supports. The minted run id joins `sq_run`'s parameter keys, and the journal's observer finds a run by that id. 100's recovery observer and paused-run pruning stop reading Squadron's internal run-state files and use `sq runs wait <id> --timeout 0 --json` (S10) instead. Matching by attributes stays only for entries journaled without an id.
   **Value:** Architectural enablement. Recovery becomes exact, and Amoeba no longer reads a file Squadron calls internal.
   **Success Criteria:**
   - An `sq_run` entry journaled with a run id is recovered by that id. Recovery adopts the run when its state exists and marks the entry `not_applied` when no state exists after the launch grace period.
   - Entries without an id still recover through the existing matching rule.
   - Recovery of entries journaled with a run id, and all pruning, make no reads of Squadron's run-state files. A test proves this. Only entries journaled without an id, which predate this slice, are still matched against those files.
   - Pruning decides from the outcome document's `status`, `paused_at` and `updated_at`.
   - 100's contract suite passes, extended for each change.
   **Dependencies:** None (100 complete).
   **Interfaces:** Changes 100's journal keys and observer contract (`docs/process-contract.md`, `docs/store-contract.md`). Consumed by 122 and 125.
   **Risk Level:** Medium. It changes recovery, the most sensitive code in 100.
   **Relative Effort:** 3

2. [ ] **(121) Store Contract Changes for the Runner** — The rest of the 100 changes the arch lists. `update_node_status` enforces `done` as terminal. An intent's acknowledgment carries an outcome (applied, no-op, or rejected with a reason), and a second acknowledgment still raises. A project-scoped escalation covers faults that have no node: it is deduplicated on project and fault kind, and the Runner closes it on the first clean tick. Migrations add the routing-decision, table-version, attempt-count and desired-state tables.
   **Value:** Architectural enablement. The Runner codes against a contract that already holds what it needs.
   **Success Criteria:**
   - Moving a `done` node to any other status raises.
   - An acknowledged intent's outcome can be read by its submitter. The change is additive, so existing acknowledgment callers are unaffected.
   - At most one project-scoped escalation is open per project and fault kind. Closing it is recorded.
   - The four tables exist through the migration mechanism, and the store contract documents their write and read API.
   - 100's contract suite passes, extended for each change.
   **Dependencies:** None (100 complete). Sequenced after 120 so migration numbers follow build order.
   **Interfaces:** Changes `docs/store-contract.md` and `docs/inbox-contract.md`. Consumed by 122, 124, 126 and 127.
   **Risk Level:** Low
   **Relative Effort:** 3

## Feature Slices

3. [ ] **(122) Runner Tenant and Control Surface** — The Runner's loop, with no lifecycle in it yet. The tenant is composed after `standard_tenants` and has observe, decide and act stages: Decide is pure, and Act issues journaled commands only. Runs launch detached in their own session, with stdin from `/dev/null` and logs written to per-run files under the supervisor directory. A launch is confirmed by the exact `run_id=<id>` line, and a late launch is adopted by polling again. Each in-flight run is polled once per tick. The slice also adds the start-up shape probes, an exit-2 check on first use of a launch, per-project fault isolation with the one process-boundary catch, and the tick deadline checked before every subprocess call. Settings hold the tick deadline, the per-call timeout and the launch grace period.
   **Value:** Developer value. A command goes out, is watched without blocking, and survives a crash. Every later slice adds behaviour to this loop rather than building its own.
   **Success Criteria:**
   - A no-op step is journaled, launched, observed to completion and recorded. It is recovered correctly across a `kill -9` of the resident process. Recovery leaves an entry whose run exists in flight for the Runner to finish, rather than adopting it.
   - A failed `sq` probe stops `amoeba start`, with an error naming the missing shape. A CF link that fails its probe escalates for its project, and other projects continue.
   - An in-flight run is polled at most once per tick, and no more often than the run poll interval.
   - A launch whose child exits before the `run_id=` line, or that passes the grace period without one, resolves failed.
   - A fault in one project is logged at ERROR and escalated, and the tick continues for the other projects. A store write failure exits the process.
   - A tick stops issuing subprocess calls at its deadline. Work it did not reach goes first on the next tick.
   **Dependencies:** [120, 121]
   **Interfaces:** Provides the tick skeleton, the launch and observe primitives, and settings to 123–129. Consumes the journal, recovery, and the project-scoped escalation.
   **Risk Level:** High. Detached launch, launch confirmation and crash adoption are where the Runner can lose or duplicate a run.
   **Relative Effort:** 4

4. [ ] **(123) Lifecycle Model and Reconciliation** — Projects CF's plan into 100's node tree. Initiative nodes come from `cf list initiatives --json`, and slice nodes from `cf list slices <index> --json`. Pointers and gates are read from `cf status --json` by 125 and 128, which use them (slice 123, D7). Below each slice is a node per lifecycle step, and the v1 step map assigns each step a Squadron pipeline or a human step. No v1 step is a CF write: a pointer write is part of dispatching a pipeline step (slice 123, D3). Reconciliation runs on list diffs and on successful changed `cf_project_changed` snapshots. Nodes link to CF by slice index: a renamed slice keeps its node, and an index CF no longer reports becomes an orphan that escalates, unless it is already done or already blocked (slice 123, D5). The Runner is the only creator of nodes. Predecessor lookup goes through one function so 180 can add cross-project edges later.
   **Value:** Developer value. Amoeba's tree mirrors the project's real plan and stays in step as the plan changes.
   **Success Criteria:**
   - A project's initiatives and slices appear as nodes with step children that match the step map.
   - A slice added to a plan document appears on the next tick, even though `projects.json` did not change.
   - A rename keeps the node. A renumber produces one orphan escalation and one new node.
   - A failed snapshot, or a recovery that found nothing changed, triggers no early plan read. The plan is still read on its interval (slice 123, D7).
   - Human steps (P2, P3, P7, host cutover) are `blocked_on_human` from the moment they become current. This is proven under a test planner. The planner joins production in 124, because "current" needs drive (slice 123, D9).
   **Dependencies:** [122]
   **Interfaces:** Provides the node tree, the step map and the predecessor function to 124–129. Consumes CF's `--json` surfaces and 108's snapshots.
   **Risk Level:** Medium. Identity across plan edits is the subtle part.
   **Relative Effort:** 3

5. [ ] **(124) Intent Vocabulary** — How the PM steers the Runner. Targets are a project, an initiative or a slice. Each target carries a drive setting (advance work, up to a lifecycle step) and a hold setting, and clear removes a target's own settings. Drive resolves from the nearest target that sets it, and hold applies if any ancestor holds. An intent is applied and acknowledged in one transaction, writing the desired-state table. An intent that would not change the target's settings is acknowledged as a no-op (slice 124, D5), and one the Runner cannot apply is rejected with a reason.
   **Value:** User value. The PM can tell Amoeba what to work on and stop it, without touching the store.
   **Success Criteria:**
   - Applying the same intent twice leaves the same state as applying it once. The later intent for a target replaces the earlier one.
   - A project hold blocks a slice that is set to resume, and clearing the project hold releases it.
   - Finding the governing settings for a node is a lookup up its path, not a replay of messages.
   - Each intent is acknowledged exactly once, with outcome applied, no-op or rejected.
   - A held target issues nothing new, and its in-flight runs are still observed and ingested.
   - 123's `HumanStepPlanner` is registered in production together with the drive filter, so a human step blocks only once it is current and driven, and linking a project alone escalates nothing.
   **Dependencies:** [121, 123]
   **Interfaces:** Provides the intent body format that 160 translates into. Its whitelist (OQ5) is a subset of this vocabulary. Consumes 121's acknowledgment outcomes and desired-state table.
   **Risk Level:** Low
   **Relative Effort:** 2

6. [ ] **(125) Run Dispatch and Outcome Ingestion** — Drives a node through one phase run. Dispatch takes two ticks: a journaled `cf_write` sets CF's pointers, and once its read-back is recorded, an `sq_run` launches P4, P5 or P6 for that node, in the checkout of the CF worktree whose index range holds the slice. P6 always runs with `merge=false` until 128 adds the merge policy (slice 125, D5). A pointer someone else moves away from a node with a run in flight raises a project-scoped escalation naming the node while the move lasts. Only snapshots recorded after the Runner's own pointer write are read, so its own writes never count (slice 125, D11). Each checkout runs one pipeline, held from the pointer write until the run is neither running nor paused. On completion, ingestion records the last entry of the outcome's `reviews` list, plus all part files of a split review. It uses 105's parser under the attribution rule and D5, marking the review `runner_issued` in the same transaction that resolves the journal entry. A paused run becomes `blocked_on_sq_checkpoint` holding its run id and checkpoint. A failed, timed-out, cost-capped, orphaned or missing run becomes `blocked_on_human` with the reason. Every finished outcome is flagged as awaiting routing in the transaction that resolves its entry (issue #10). The per-pipeline time bound is 126's (slice 125, D12). The Runner never kills a run.
   **Value:** Developer value. A slice step runs end to end under Amoeba, and its result lands in the store as evidence.
   **Success Criteria:**
   - A driven node gets a pointer write on one tick and a run on a later tick. Neither is issued while the node is held.
   - A second slice in the same checkout waits until the first run releases it.
   - A completed run's final review is recorded and attributed. An empty `reviews` list records nothing, and a listed file that is missing or unparseable escalates as unknown.
   - Each non-completed outcome kind produces its blocked state, with the outcome document's fields attached.
   - An ingested outcome with no decision record is left for routing, and a crash between ingestion and routing loses nothing.
   **Dependencies:** [120, 122, 123, 124]
   **Interfaces:** Provides ingested outcomes to 126. Consumes `sq run --run-id`, `sq runs wait --json`, `cf set`, 105's parser and 104's verdict records.
   **Risk Level:** Medium
   **Relative Effort:** 4

7. [ ] **(126) Routing Engine** — The routing table as static config, loaded at start and never mutated. Rules are ordered and conditioned on named closed inputs: run outcome, checkpoint kind and `is_loop`, failure kind, verdict, standing, finding severity, recurrence, attempt count, step and node state. Gate state and check standing join when 128 registers them (slice 126, D1, D3). Unknown values match only rules that name unknown, and the table must end in a catch-all escalate. The routes are advance, rerun (bounded by an attempt limit per node and step, and only for a completed run) and escalate (with a judge-eligible mark for 140). Every application writes a decision record holding the inputs, rule id, table version, Amoeba version and route. Each table version is stored in full the first time a decision uses it. The first table escalates every pause. Outcomes to route come from 125's `unrouted_outcomes`. The table also holds the per-pipeline time bound, moved here from 125 (slice 125, D12).
   **Value:** Developer value. Every outcome gets an explained route, and "build by inducing failure" becomes a table edit.
   **Success Criteria:**
   - Any recorded decision can be recomputed from its record and its stored table version alone.
   - Advance marks the node done and makes its successor runnable on the next tick.
   - A rerun relaunches the same phase pipeline with no instructions, and the attempt limit then escalates.
   - A table without a catch-all escalate, or one naming an input or route outside the closed sets, refuses to load.
   - No route is chosen in code outside the table. Code defines only inputs and predicates.
   - A run in flight past its pipeline's time bound escalates, without being killed.
   **Dependencies:** [121, 125]
   **Interfaces:** Provides decision records to 127–129 and the judge-eligible mark to 140. Defines the table file format: YAML, one table for every project (slice 126, D2).
   **Risk Level:** Medium. The grammar is hard to change once tables exist.
   **Relative Effort:** 3

8. [ ] **(127) Resolutions and Resumption** — Turns a PM resolution from the inbox into the Runner's next command, from a closed set. A paused run can be retried (`sq run --resume <id> --decision retry`), accepted (`--decision accept`, offered only when `is_loop` is true), marked handled (the Runner journals an observation of the run and routes what it finds) or stopped. Retry and accept pass the resolution's `--instructions` through as data. An escalated completed outcome can be accepted (store only, which advances the node), rerun or stopped. Any other blocked pipeline step can be rerun or stopped. Stop parks the node as a block (slice 127, D3). The store and CF gate disagreement after an accept is detected by 128's gate read (slice 127, D7). Resolutions outside the set are rejected explicitly. A resume whose run is missing is a failed command and is never relaunched. An exit 2 from a resume escalates the node with Squadron's message.
   **Value:** User value. A PM decision on a stuck node is carried out without the PM running Squadron by hand.
   **Success Criteria:**
   - Each resolution in the set issues the right command, or makes the right store change for store-only accept and stop.
   - Accept is refused at the Amoeba side for a pause that is not at a loop.
   - Instructions reach the resumed run unchanged, and the Runner never writes any of its own.
   - A missing run on resume blocks the node and launches nothing.
   - An accepted outcome is identifiable in the store, for 128's gate comparison (slice 127, D7).
   **Dependencies:** [125, 126]
   **Interfaces:** Provides the resolution vocabulary that 160 and the notification bridge submit. Consumes 103's resolution slot and S12.
   **Risk Level:** Low
   **Relative Effort:** 2

9. [ ] **(128) Gates, Git and Human Steps** — The checks around dispatch. Gate state comes from `cf status --json` (`activeSlice.status` and `gateInfo`), and `pending-decision` is a human step. A CF gate cleared on a `derived` or `imposed` verdict, or on a review whose standing is not trustworthy, is routed on the store's view. The two ungate hatches are Tier-1 checks recorded as 100 check records: either one present escalates, and a vacuous check is never a pass. Before any dispatch, including 127's resumes, the tree must be clean and on the target or the node's slice branch, otherwise the node escalates. When CF's gate for a phase the PM accepted in the store still fails, the disagreement is recorded on the slice node as a check record (slice 127, D7). The per-project merge policy defaults to human, so P6 runs with `-p merge=false` and the node waits on a human merge, which the Runner observes in git. Under auto policy, P6 merges. Under any policy, the Runner never merges, deletes branches or pushes, and nothing merges to `main` when an integration branch is set.
   **Value:** User value. The Runner can be pointed at a real repository without surprising the PM.
   **Success Criteria:**
   - A dirty tree, or a checkout on an unrelated branch, escalates instead of dispatching.
   - Either ungate hatch on a node escalates it, and the check record shows what was examined.
   - Under human policy, a P6 run ends with the slice branch unmerged, and a merge the PM makes is observed and advances the node.
   - Under auto policy, P6 is dispatched without `merge=false`. The policy used is recorded on the dispatch decision.
   - `pending-decision` produces a human step, and a gate CF clears on an untrusted verdict is not treated as passed.
   - Required before merge: a store accept that CF's gate still fails is recorded on the slice node and visible to the PM (issue #15). The store side is 127's identifiable accept: an applied `accept` on a completed-outcome step, with the verdict ids it accepted (slice 127, D7).
   **Dependencies:** [125, 126]
   **Interfaces:** Provides Tier-1 predicates to the routing inputs, registering `gate_state` and `check_standing` in 126's input vocabulary (slice 126, D3). Consumes 107's check records, S11 and CF's gate fields.
   **Risk Level:** Medium
   **Relative Effort:** 3

## Integration Work

10. [ ] **(129) First Proof** — One project, one PM-chosen unstarted unit, driven end to end by the Runner under intents, through design, tasks and implementation to the human merge. Every stop is recorded. Wrong stops (escalations a human found routable, or routes a human disagreed with) become the next routing rules, or become the trigger for 130 and 131. The slice also closes out the substrate guide's 120 row and the operator documentation for running the Runner, and adds `amoeba inspect resolutions` (issue #16) for the write-up.
   **Value:** The Runner is shown to drive real work, and its stops become evidence for the routing table.
   **Success Criteria:**
   - The chosen unit reaches merged with no Squadron or CF command run by hand, except at steps the routing table sent to the PM.
   - Every decision in the run can be recomputed from its record.
   - A restart of the resident process during the proof leaves the run completable.
   - The proof's stops are written up with a proposed table edit or follow-on slice for each wrong stop.
   - Operator documentation covers settings, intents, resolutions and the routing table.
   **Dependencies:** [120–128]
   **Interfaces:** Consumes the whole Runner. Produces the evidence that shapes 130, 131 and 140.
   **Risk Level:** Medium
   **Relative Effort:** 3

## After the First Proof

These are in scope for initiative 120. They are built after 129 because the arch makes the proof's stops their input.

11. [ ] **(130) Batch Dispatch** — Treats a plan-wide run, `slices-plan` first, as one dispatch whose per-item outcomes (Squadron's batch report, `items[]`) map onto per-slice nodes. The Runner acts only at items Squadron flags or pauses on. Resuming a flagged item is an explicit per-item resume carrying the resolution's decision. Which lifecycle steps may be batched, and how report items map to nodes, are decided at slice design. Dependencies: [129]. Risk: Medium. Effort: 3/5

12. [ ] **(131) Tier Inference and Baseline-Diffed Checks** — Adds the inferred tier as a routing input, built from closed signals only: severity, `location_verified`, standing, recurrence and the Runner's Tier-1 predicates. A finding the rules cannot classify is Tier 2, never Tier 1. Adds test checks diffed against a baseline, dispatched like a run because they are long and write. Scope is set by the first proof's stops. When Squadron ships a tier field (S1), it becomes one more input. Dependencies: [129]. Risk: Medium. Effort: 3/5

## Implementation Order

`120 → 121 → 122 → 123 → 124 → 125 → 126 → 127 → 128 → 129`, then 130 and 131 in either order.

- **Dependencies.** The contract changes (120, 121) come first, as the arch requires. 122 is the loop every later slice adds to. 123 has to exist before intents have targets (124), and dispatch needs both a node and a drive setting (125).
- **Testability.** 122 proves a journaled run across a crash before any lifecycle logic exists. 125 is the first point where a real slice step runs, and its outcomes are recorded and escalated through the catch-all rather than routed.
- **Risk.** 122 is the highest-risk slice and comes before anything depends on its launch and adoption behaviour.
- **Value.** 127 and 128 both follow routing and are independent of each other. They are both needed before 129 points the Runner at a real repository.

## Notes

- **Migration order.** 120 and 121 both change 100's contract, and 121 adds four tables. Slice design assigns migration numbers in build order, as 100's plan did.
- **Tables before their consumers.** 121 adds the routing, attempt and desired-state tables before 124 and 126 use them, because the arch makes the contract change a slice of its own. If slice design finds a table's shape depends on details settled in 124 or 126, that table moves to its consumer slice. The contract-first rule still holds, because the table lands in 100's contract either way.
- **Concurrency in v1.** A project with one worktree moves one slice at a time, and a paused run stops that project until the PM acts. Parallel work means separate CF worktrees.
- **Plan change, 20261020: the gate-disagreement criterion moves from 127 to 128.** Entry 8 required that an accepted outcome CF's gate still fails be recorded on the node. CF's gate depends on per-project thresholds, and `cf status --json` reports it only for the active slice, so only 128's gate read at the successor's dispatch can compare reliably (slice 127, D7). Entry 9 carries the criterion, required before 128 merges. Tracked as issue #15.
- **No P3 executor.** Slice planning has no Squadron pipeline, so for every initiative the Runner drives, P3 is a human step.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.

1. [ ] **Multi-project scheduling** — Fairness across projects and a global limit on in-flight runs. Waits until real multi-project use shows it is needed. Dependencies: [129]. Effort: 3/5
2. [ ] **Retry class for transient faults** — v1 escalates every fault. Once the first proof shows which faults recur (timeouts, provider errors), give them a bounded automatic retry in the routing table. Dependencies: [129]. Effort: 2/5
3. [ ] **Relink intent for renumbered slices** — A renumber currently orphans the node and resets its history. Add an intent that links an orphan to its new index, if renumbering turns out to be common. Dependencies: [123, 124]. Effort: 2/5
4. [ ] **Judge route** — Initiative 140 adds the judge route, and rules marked judge-eligible switch to it. Listed here so the mark's consumer is recorded. Dependencies: [126], initiative 140.
5. [ ] **Squadron review-completed event (S8)** — If Squadron adds the event, it can replace per-tick polling for completion. Dependencies: [122].
6. [ ] **Skip held runs when pruning** — From 120's design: `amoeba prune sq-runs` polls `sq runs wait` once per owned run id. If the owned set grows enough to make pruning slow, skip ids held by unfinished nodes, which can never be candidates. Dependencies: [120]. Effort: 1/5
7. [ ] **Feed change for project-escalation closure** — From 121's design: a project-scoped escalation's opening reaches the feed as `message_posted`, but its closure is a column update and emits nothing. Add a closure change kind (new `ChangeKind`, trigger, invariant-test step) once a subscriber such as the notification bridge needs to clear a shown fault. Dependencies: [121]. Effort: 1/5
8. [ ] **Mark a step done** — From 123's design: a slice already partly done by hand gets all its steps runnable, because the Runner infers no partial progress. Add an intent or resolution that marks a step done, if driving such slices turns out to be common. Dependencies: [123, 124]. Effort: 1/5
9. [ ] **CF asks: `indexSource` and a no-plan error code** — From 123's design: `cf list slices --json` does not expose `indexSource`, so CF's fallback counters cannot be told from explicit indexes. CF also reports "no slice plan" as `code: UNKNOWN`. Ask CF for both. Dependencies: none. Effort: 1/5
10. [ ] **Per-project routing tables** — From 126's design: one table serves every project in v1. Let a project override it once the first proof or a second project shows different rules are needed. Each decision already records its table version. Dependencies: [129]. Effort: 2/5
11. [ ] **Resume a failed run** — From 127's design: Squadron resumes a failed run by re-running its failed step, but v1 offers only rerun or stop for one. A failed run releases its checkout, so another slice may have changed the branch since. Add a `retry` for failed runs once the checkout hold covers them. Dependencies: [127, 128]. Effort: 2/5
