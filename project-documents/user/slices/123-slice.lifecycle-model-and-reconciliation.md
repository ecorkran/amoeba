---
docType: slice-design
slice: lifecycle-model-and-reconciliation
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 122
interfaces:
- 124
- 125
- 126
- 127
- 128
- 129
dateCreated: 20261020
dateUpdated: 20261023
status: complete
turns: 35
promptTokens: 3530572
cachedTokens: 3376390
cacheWriteTokens: 154114
completionTokens: 58923
durationSeconds: 607.5
costUsd: 3.087254
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Lifecycle Model and Reconciliation

## Overview

This slice projects each linked Context Forge (CF) project's plan into 100's node tree and keeps that tree in step as the plan changes.

- **Initiative nodes** come from `cf list initiatives --json`.
- **Slice nodes** come from `cf list slices <index> --json`, read once for each initiative.
- **Step nodes** sit below each initiative and slice, one for each lifecycle step in the v1 step map. Each step is a Squadron pipeline or a human step.

Nodes link to CF by index. A renamed slice keeps its node. A node whose index CF no longer reports is unlinked and escalated as an orphan, and is never deleted.

The slice also adds the lifecycle model that later slices decide on:

- the step vocabulary;
- the predecessor function, the single place that says what a step waits for;
- "ready", meaning a step whose predecessors are done;
- a planner that blocks a human step once it is current.

The Runner is the only code that creates nodes, and a guard test enforces that.

## Value

Developer value. Amoeba's tree mirrors the project's real plan and stays in step with it:

- **Intents get targets.** 124 can name an initiative or a slice node, because the node exists before anything is driven.
- **Dispatch gets work items.** 125 dispatches step nodes, and 126 counts attempts and advances per node and step, using step values defined once here.
- **Plan edits are safe.** Adding, renaming or renumbering a slice in a plan document changes the tree predictably. History is never deleted or silently moved to another node.

## Technical Scope

**Included**

- `amoeba.upstream.context_forge.plan`: pydantic models and parsers for the two plan reads. They replace 122's top-level-only parser seam.
- `amoeba.runner.lifecycle`, a new subpackage:
  - the `LifecycleStep` vocabulary and the step map;
  - `LifecycleTree`, built from the project's nodes, with `is_linked`, `predecessors`, `predecessors_done` and `ready_steps`;
  - the plan read, done under `TickBudget`;
  - reconciliation, which does orphan, create, update and completion;
  - `HumanStepPlanner`.
- Store contract changes, in migration `010`:
  - `CFReference.index` (`nodes.cf_index`), with a partial unique index;
  - `amoeba inspect nodes` shows the index.
- A new setting, `plan_read_interval_seconds`, with the flag `--plan-read-interval`.
- New fault kinds `plan_read_failed`, `lifecycle_orphan` and `plan_status_unknown`. The new Action `BlockHumanStep`.
- A change to 122's `cf` probe set (D11).
- A guard test that only `amoeba.runner.lifecycle.reconcile` calls `create_node` in `src/amoeba`.
- Contract text in `docs/store-contract.md`, `docs/context-forge-contract.md`, `docs/process-contract.md` and `docs/substrate-guide.md`.

**Excluded**

- **Drive and hold (124).** Drive and hold narrow "ready" to "ready and driven". `HumanStepPlanner` joins the production planners in 124, so that linking a project escalates nothing until the PM drives it (D9).
- **Reading `cf status` (125, 128).** Pointers and checkout paths are read by 125, the first slice that writes pointers and dispatches. Gate fields are read by 128 (plan entry 9). 123 has no use for either, and builds no status model or view for them (D7).
- **Routing and attempt counting (126).**
- **Gates, git, and the merge step's observation (128).** In 123, a current merge step is a human step that only the PM's action or a completed slice clears. 128 adds the git observation and the auto-merge policy.
- **Gate nodes.** v1 has no gate step (D3).
- **Relinking an orphan to a new index** (slice plan Future Work 3).
- **Inferring partial progress on a slice that is already under way** (D6, Future Work below).
- **Refreshing titles on a rename, and rolling up container status.** Nothing in 120 needs either yet. Titles are set at creation, and initiative and slice nodes stay `runnable` while their steps carry progress (issue #11).

## Dependencies

### Prerequisites

- **122, merged.** It provides:
  - the tick skeleton, `TickBudget`, `ProjectView`, the `Planner` seam and the `Action` union;
  - the per-link probe results and the failed-link flag;
  - `FaultKind`, the fault boundary, and the closure rule for project-scoped escalations;
  - `tick_call_timeout_seconds`.
- **121, merged.** It provides migration `009` (so this slice's migration is `010`), done-terminal enforcement, the project-scoped escalation, and `attempt_counts` and `desired_states` with an opaque `step` text that this slice's vocabulary fills.
- **108.** It provides `cf_links` and `latest_cf_snapshots`, used for early plan reads.
- **Context Forge** as `cf`, with the shapes observed on CF 0.19.16 on 20261020 (Interfaces Required).

### Interfaces Required

**Store.** `nodes_for_project`, `create_node`, `update_cf_reference`, `update_node_status`, `block`, `resolve`, `blocked_state_for` and `unresolved_journal_entries`, plus 121's project-scoped escalation. The changes this slice makes to the store are listed under Implementation Details.

**CF reads.** Every read passes `-p <cf_project_id>` and runs under `tick_call_timeout_seconds`. These shapes were observed on CF 0.19.16 on 20261020.

| Read | Fields used | Notes |
| --- | --- | --- |
| `cf list initiatives --json -a -p <id>` | array of `{index, name, archFile, isChecked}` (also has `status`, `isActive`) | `-a` covers every worktree. |
| `cf list slices <index> --json -p <id>` | object with `entries[]`, each `{index, name, designFile, status, isChecked}` | An initiative with no slice plan exits 1 with `{"error": true, "code": "UNKNOWN", "message": …}`. |

`status` is CF's normalized set: `complete`, `in_progress`, `not_started`, `deprecated`, `deferred`, or `degraded` when CF could not resolve the entry.

## Architecture

### Component Structure

```
amoeba/upstream/context_forge/
  plan.py          NEW  CFInitiative, CFSliceEntry, CFSliceList, CFErrorDocument,
                        PlanEntryStatus; parse_initiatives / parse_slice_list
amoeba/runner/lifecycle/       NEW subpackage
  steps.py         LifecycleStep, StepLevel, Executor, StepSpec, STEP_MAP, completion predicates
  tree.py          LifecycleTree: index by (kind, cf_project, index); is_linked, children,
                   predecessors, predecessors_done, ready_steps (pure, no I/O)
  plan_read.py     PlanRead per link: the CF reads under TickBudget, cadence, triggers
  reconcile.py     apply a complete PlanRead to the store: orphan, create, update,
                   complete. The only create_node caller in src/amoeba
  human_steps.py   HumanStepPlanner → BlockHumanStep actions
amoeba/runner/
  tick.py          CHANGED  plan read and reconcile after in-flight polling; tree in view
  decide.py        CHANGED  ProjectView.tree; Action += BlockHumanStep
  act.py / tick    CHANGED  BlockHumanStep applied as one store.block (D9)
  faults.py        CHANGED  FaultKind += plan_read_failed, lifecycle_orphan, plan_status_unknown
  probes.py        CHANGED  full models; slices probe dropped (D11)
amoeba/store/
  schema/010_node_cf_index.sql   NEW
  models.py / nodes.py / mapping / sql   CHANGED  CFReference.index
amoeba/process/settings.py, amoeba/cli/settings_flags.py   CHANGED  plan_read_interval_seconds
amoeba/inspection/listing.py   CHANGED  nodes listing shows cf index
```

### Data Flow

Within one project's tick (122's skeleton), the new stage runs at the end of observe, after in-flight runs are polled:

```
[apply intents — 124]
observe     in-flight runs (122)
plan read   for each CF link whose probe passed, if a read is due (D7):
              cf list initiatives -a                       ─┐ each call checks TickBudget;
              cf list slices <i>   for each initiative     ─┘ a cut-off read applies nothing
                                                              and restarts next tick
reconcile   apply the complete read: orphan → create → update → complete (D5)
tree        LifecycleTree ← nodes_for_project(project)       (after reconcile)
record / [route — 126]
decide      ProjectView(tree, …); planners see tree.ready_steps()
act         LaunchRun (journaled) | BlockHumanStep (one store write)
```

A plan read either completes for a link and is applied, or it is cut off and applies nothing for that link. Within a completed read, failures are scoped: a failed initiatives read applies nothing, and a failed slice read for one initiative leaves that initiative's slices untouched (D5).

### State Management

- **Durable, in the store:**
  - Initiative, slice and step nodes, and each node's CF link: `cf.project`, `cf.index`, `cf.slice_name` and `cf.artifact_path` for initiatives and slices, and `cf.phase` for steps.
  - Orphan blocks.
  - Human-step blocks.
  - Done statuses from completion.
- **In memory, rebuilt after a restart:**
  - For each link: the time of the last complete plan read, when the current read became due, the id of the last observed snapshot seen, and whether the last plan read failed.

  After a restart, every link is due for a read on the first tick, and the reconcile that follows is idempotent. So losing this state costs one read per link.
- Nothing about the plan is cached between reads except the tree itself, which is the store.

## Technical Decisions

### D1 — Nodes link to CF by index, held in a new `CFReference.index`
Status: decided
- The arch says a node's link to CF "is the slice's index within its project, held in the node's CF reference". `CFReference` has no index field today (`project`, `phase`, `slice_name`, `artifact_path`). Migration `010` adds `nodes.cf_index INTEGER NULL`, and `CFReference` gains `index: int | None = None`. The store still does not interpret the value.
- **Link key:** `(project_id, kind, cf.project, cf.index)`, where `cf.project` is the CF project id. `kind` is needed because an initiative and its first slice share an index (initiative 120, slice 120). `cf.project` is needed because one Amoeba project may link several CF projects. A partial unique index, `ON nodes (project_id, kind, cf_project, cf_index) WHERE cf_index IS NOT NULL`, makes a duplicate link a `StoreIntegrityError`, so a reconcile bug cannot create two linked nodes for one index.
- **Step nodes** have kind `phase_or_artifact`, `cf.project` set, `cf.index` null and `cf.phase` set to the `LifecycleStep` value. A step's identity is its parent node and its step. Reconciliation creates a step only when its parent has no child with that step.
- **Display data:**
  - The title comes from CF's `name` (initiatives and slices) or from the step value, at creation, and is not updated (issue #11).
  - `cf.artifact_path` comes from `archFile` (initiatives) or `designFile` (slices).
  - Display data is never matched. Rejected: matching by name or file name. The arch makes both display data.
- Rejected: storing the index in another field, such as `cf.phase` or `artifact_path`. A field would then mean two things depending on the node's kind.

### D2 — `cf.slice_name` follows CF, because attribution depends on it
Status: decided
- The attribution rule (evidence contract) attaches a review to the one slice node whose `cf.slice_name` equals the review's frontmatter `slice`. So 123 keeps `slice_name` equal to CF's slug for that slice, taken only from CF:
  - **`designFile` present.** Use the file-name stem between `{index}-slice.` and `.md`. The `nnn-slice.{name}.md` form is CF's file-naming convention. A `designFile` without that form leaves `slice_name` null, logs a WARNING naming the file, and raises nothing.
  - **No `designFile`:** `slice_name` is null, and no review can be attributed to the node yet. A slice gets a design file only through P4, which 125 dispatches after writing CF's pointer. 125 reads that pointer back with `cf get --json` in the checkout, and sets `slice_name` from the `fileSlice` stem before it launches (125, D2), through `update_cf_reference`.
  - Amoeba never builds a slug from a slice name itself. Doing so would duplicate CF's `slugify` and drift from it.
- **On a rename,** `slice_name` and `artifact_path` are updated, and the node is unchanged. Later reviews attribute to it under the new slug. Earlier reviews were already recorded against its node id.
- **On orphaning** (D5), `slice_name` and `index` are cleared together. That stops a renumbered slice's new node and its orphan from both matching one review, which would leave the review unattributed. The former values are kept in the orphan escalation's payload.

### D3 — The v1 step map
Status: decided
- `LifecycleStep` is a `StrEnum`, defined once. Its values are the `step` text in 121's `attempt_counts` and `desired_states.drive_until_step`.

  | Step | Process phase | Level | Executor | Observed complete when |
  | --- | --- | --- | --- | --- |
  | `architecture` | P2 | initiative | human | the initiative has an `archFile` |
  | `slice_plan` | P3 | initiative | human | the initiative's slice list reads successfully |
  | `slice_design` | P4 | slice | pipeline `P4` | CF reports the slice complete |
  | `tasks` | P5 | slice | pipeline `P5` | CF reports the slice complete |
  | `implementation` | P6 | slice | pipeline `P6` | CF reports the slice complete |
  | `merge` | merge | slice | human (128 adds git observation and auto policy) | CF reports the slice complete |
  | `integration` | P7 and host cutover | initiative | human | the initiative is checked (`isChecked`) |

  "CF reports the slice complete" means `status == complete` or `isChecked`, and it is defined once as a predicate.
- **`merge` and CF's checkbox.** The arch says git, not CF's checkboxes, shows a merge. In 123 the only completion for `merge` is CF's, so a PM who checks slice n in CF without merging makes slice n+1's `implementation` ready (D4). This window is accepted, for three reasons:
  - Checking the slice in CF is the PM's own statement that it is finished.
  - 128 adds the git observation, and keeps CF's completion as a second path, which also covers a squash merge git cannot observe (128, D9).
  - 128's pre-dispatch branch check is the backstop. An unmerged `P6` leaves slice n's branch checked out, which is neither the target nor slice n+1's branch, so slice n+1's `P6` blocks instead of launching (128, D6).

  Until 128 lands, nothing checks the tree. 129, the first proof, runs with 128 in place.
- **Executors.** `Executor` has two members, `pipeline` and `human`. The arch also names "a CF write", but in v1 a pointer write is part of dispatching a pipeline step (125) and is not a step of its own, so no step has that executor. An executor nothing used would be dead vocabulary. **This departs from the arch's step-map sentence and plan entry 4**, and both are updated to say so.
- **Host cutover** is folded into `integration`. The arch groups them in one row ("Phase 7, and host cutovers"), and not every initiative has a cutover. A separate step would put a human step in front of every initiative.
- **No gate nodes in v1.** P4, P5 and P6 each review inside their own run. CF's gate (`pending-review`, `review-failed`, `pending-decision`) is a dispatch check and a routing input in 128, not a step. **This departs from the arch's "a gate node where CF or the routing table requires a review"**, which the arch is updated to say. If 128 finds that it needs a gate step, it adds a row to this map, which is the one place steps are defined.
- `NodeKind.GATE` stays in the store vocabulary, unused by the Runner.

### D4 — The predecessor function
Status: decided
- `predecessors(tree, node) -> tuple[Node, ...]` is the one place that says what a step waits for. `predecessors_done(tree, node)` is true when every predecessor is `done`. 180 adds cross-project edges by giving this function a wider view, not by editing its callers.

  | Step | Waits for |
  | --- | --- |
  | `architecture` | nothing |
  | `slice_plan` | `architecture` of the same initiative |
  | `slice_design` | `slice_plan` of the slice's initiative |
  | `tasks` | `slice_design` of the same slice |
  | `implementation` | `tasks` of the same slice, and `merge` of the previous eligible slice in the initiative |
  | `merge` | `implementation` of the same slice |
  | `integration` | `slice_plan`, and `merge` of every eligible slice in the initiative |

- **Eligible slice.** A linked slice with step children (D6). Orphans are left out. So are slices CF reports `deferred` or `deprecated`, which CF itself takes out of the plan, so the skip is deliberate. A slice with an unknown status has steps and stays in the order (D6), so it holds later slices back until its status is known and its work is done.
- **"Previous" means by ascending `cf.index` within the initiative.** The slice-planning convention makes slice numbers the execution order, and the index is stored, so Decide does not depend on a list order from the last read.
- **Why implementation is sequential and design is not.**
  - Designs and task files can run ahead. Batch dispatch (130) will often design a whole plan.
  - Code cannot run ahead. Slice n+1's P6 would start from slice n's unmerged branch, which 128's clean-tree check would escalate.
- **`ready_steps(tree)`** returns the step nodes that are `runnable`, linked (`is_linked`, D5), have no blocked ancestor, and whose predecessors are done.
  - It is pure, over the tree only.
  - Later slices narrow it in Decide: drive and hold (124), no unresolved journal entry and a free checkout (125), and gates (128).
  - The arch's "runnable" is this narrowed set. The store's `runnable` status alone only means "not blocked, started or done".

### D5 — Reconciliation applies a complete read, in a fixed order
Status: decided

Reconcile runs on one link's completed plan read. Every write is the store's one-transaction call. Each rule checks the store before it writes, so a crash at any point is repaired by the next read.

1. **Orphan.** A linked node is orphaned when:
   - it is an initiative missing from a successful initiatives read;
   - it is a slice missing from every successful slice read, and its own initiative's read succeeded; or
   - it is a slice listed under a different initiative from its parent. That is a move, so it is orphaned and recreated, the same as a renumber.

   Orphaning:
   - clears `cf.index` and `cf.slice_name` through `update_cf_reference`;
   - then, if the node is neither blocked nor done, blocks it on `HUMAN`. The context is `orphaned: CF no longer reports index <n>`, and the payload is `{fault_kind: lifecycle_orphan, cf_project_id, former_index, former_slice_name}`;
   - if the node is `done`, does not block it (121 refuses a block on a done node) and logs INFO. A finished slice leaving a plan needs no person;
   - if the node is already blocked, keeps its open escalation and logs a WARNING naming the former index. The node stays unlinked, so resolving that escalation leaves it as history.

   **The last two cases depart from the arch's and plan's "an orphan escalates".** A done orphan needs no person. An already-blocked orphan cannot be blocked twice, and its open escalation already reaches the PM. The arch and plan entry 4 are updated to say so.

   Descendants of an orphan are not touched. `is_linked` is false for any node with an unlinked ancestor, so they leave `ready_steps`. A run in flight under an orphan is still observed and ingested (122, 125). **One orphan escalation per orphaned initiative or slice** meets the plan's "one orphan escalation and one new node" for a renumber. The new node is created in step 2 of the same reconcile. Because orphaning runs first and clears the link, the unique index never sees two linked nodes.
2. **Create.**
   - An initiative CF lists that has no linked node gets an initiative node, then its `architecture`, `slice_plan` and `integration` steps.
   - A slice listed by a successfully read initiative that has no linked node gets a slice node under that initiative, then its four steps (subject to D6).
   - A linked node missing a step child gets that step.
   - New nodes take the statuses D6 gives them.
3. **Update.** A linked node whose `slice_name` or `artifact_path` differs from CF's is updated through `update_cf_reference`.
4. **Complete.** For each linked step whose completion predicate (D3) holds:
   - **`runnable` with no unresolved journal entry:** mark it `done`.
   - **`blocked_on_human` and its executor is human:** `resolve(resolved_by="runner", detail="observed: <predicate>")`, then mark it `done`.
   - **Anything else:** leave it. In-flight and blocked pipeline steps finish their own course, and 121 refuses `done` while an entry is unresolved.

Safety rules:

- **A failed or partial read never orphans.**
  - A failed initiatives read applies nothing for the link.
  - A failed slice read for one initiative leaves that initiative's slices out of the create, update, orphan and complete steps.
  - A successful read that returns **an empty list while linked nodes exist** is treated as a failed read (`plan_read_failed`, naming the count), not as a mass orphaning. A deleted or misconfigured plan is far likelier than a deliberate removal of everything.
- **Duplicate indexes are a failed read.** A list that repeats an index, or two initiatives that list one slice index, makes that read `plan_read_failed`, naming the index. Nothing is guessed.
- The feed sees creates and status changes through the existing triggers. Reference updates add no `ChangeKind`, consistent with the arch's "nothing new on the wire".

Failures during reconcile and the view build:

- **No subprocess, so no call timeout.** Reconcile and the `LifecycleTree` build (one `nodes_for_project` read after reconcile) only touch the local store. Each store call is bounded by the store's busy timeout. They are not checked against `TickBudget`, because a call is milliseconds. The largest case is a project's first link, with one transaction per node, once.
- **A store failure mid-reconcile** (`STORE_FAILURES`, including `StoreBusyError` after the busy timeout) re-raises, and the process exits (122, D8). The writes already committed stay. On restart, the link is due on the first tick, and the rules' check-before-write repairs the rest.
- **Any other exception mid-reconcile** is a bug. For example, `StoreIntegrityError` from the unique index, or `InvalidTransitionError` from a status write. It stops this link's reconcile and reaches 122's one catch. No node is in context, so it raises a project-scoped `unexpected_fault`. The link's read is not counted as complete, so it is due again on the next tick. The committed writes stay, and the next reconcile resumes from them. The escalation is deduplicated, so a bug that repeats every tick adds no rows.
- **A failure while building the view** follows the same two paths, and Decide does not run for that project in that tick.

### D6 — Statuses at creation, and which slices get steps
Status: decided
- **A new step is created with the status its completion predicate gives:** `done` if the predicate holds, otherwise `runnable`. This is the same predicate D5's complete step applies later, so creation and later reads agree.
  - Linking a project whose initiative 100 is checked therefore creates every step in 100's subtree `done`.
  - Initiative 140, with no `archFile`, gets a runnable `architecture` step.
- **A container (initiative or slice node) is created `runnable` and stays so.** It is not a work item. Its steps carry progress (issue #11).
- **No partial progress is inferred.** A slice CF reports `in_progress` gets all four steps `runnable`, even if a design file exists.
  - A design file does not show that the design was reviewed, and the Runner does not parse plan documents.
  - Driving such a slice runs P4 again. P4 runs with `existing: keep`, so it re-reviews and revises the existing design rather than replacing it.
  - The PM can avoid that by driving only from where the slice actually stands. A way to mark a step done is listed under Future Work.
  - The first proof uses an unstarted unit (129), so this does not affect it.
- **Slices without steps.** A slice whose CF status is `deferred` or `deprecated` gets a slice node and no step children. Steps are added on the first read that reports any other status. A slice that already has steps keeps them when CF later reports it deferred. The PM stops it with a hold (124).
- **An unknown status:** `degraded`, or a value outside the vocabulary. The slice node gets its four steps, all `runnable` because "reported complete" is false, and is blocked on `HUMAN` with payload `{fault_kind: plan_status_unknown, index, status}`. Following "unknown escalates", the value is never read as a default. This is a node fault (D8), not `plan_read_failed`: the read succeeded, and the fault belongs to one slice. While the slice is blocked, its steps are not ready (D4). Its `merge` is not done, so later slices' `implementation` waits. Nothing is skipped. If the PM resolves the block while the status is still unknown, it is blocked again on the next read.
- Rejected: only logging an unknown status and leaving the slice without steps. A slice without steps is not eligible (D4), so later slices' `implementation` would silently skip past it.

### D7 — When the plan is read
Status: decided
- Plan documents can change without `projects.json` changing, so the feed alone cannot show a new slice. Each link is therefore read on an interval, and also early on a pointer change:
  - **Interval.** A link is due when `plan_read_interval_seconds` (default 30.0, defined in `settings.py`) has passed since its last complete read. Every link is due on the first tick of a lifetime. A plan edit does not change `projects.json`, so a new slice appears on the next plan read, not the next tick. **The plan's "appears on the next tick" is reworded to "appears on the next plan read".**
  - **Early read on a pointer change.** At the start of observe, the Runner reads `latest_cf_snapshots(project, link)`, which is a store read and not a subprocess. If the latest observed snapshot's id differs from the one last seen and its `changed` list is non-empty, the link is due now. A failed snapshot (`changed` null) does not move the latest observed row. A recovery with `changed: []` is seen but triggers nothing. **The plan's "triggers no reconciliation" is reworded to "triggers no early plan read"**, because the interval read still runs.
- **Polling comes first.** The plan read runs after in-flight runs are polled, so a run's poll is never cut off by a plan read. A plan read only uses budget that polling left. Its cost is bounded too: each call is about 0.1 s, against a 5 s deadline.
- **A cut-off read** applies nothing, logs a WARNING naming the link, and starts again on the next tick. It raises no fault.
  - Rejected: a separate "starved read" escalation with its own timer. Runs are polled at most once per run poll interval (122, D10), so most ticks leave the read the whole budget, and a read needs well under a second. The timer, its message and its closure are state for a case not yet observed. If the first proof shows reads starving, it is added then.
- **Which projects are read: every project with a CF link that passed its probe.** The arch's fixed set reads only projects that are driven or have a run in flight. But 124's intents target initiative and slice nodes, so those nodes must exist before anything is driven. Reads cost about 0.1 s each (measured 20261020), so a project with six initiatives costs under a second every 30 s. **This is a departure from the arch's Observe sentence**, which the arch is updated to say.
- **No `cf status` read.** Nothing in 123 uses pointers or gates. 125 reads no `cf status`: its pointer read-back is `cf get --json` run in the checkout, and checkouts come from the CF snapshot (125, D1, D2). 128 reads the gate fields. The plan's entry 4 is edited to match. `cf status -p` without `--worktree` reports only project-level pointers, which are empty on a worktree-scoped project, and `--worktree` accepts the worktree id (both observed 20261020). These are recorded in the context-forge contract for 125.

### D8 — Plan-read faults
Status: decided
- `FaultKind` gains three members:
  - `plan_read_failed`: a CF read timed out, exited non-zero without a CF error document, did not parse into the models, or broke a D5 safety rule.
  - `lifecycle_orphan`: the payload kind of an orphan block (D5). Defined in the same vocabulary, so payloads use one set of names.
  - `plan_status_unknown`: the payload kind of an unknown-status block (D6). It is node-scoped: it is closed only by resolving the block, and it is not deduplicated per project. `plan_read_failed` stays project-scoped only.
- **An error document from `cf list slices <i>`** (exit 1, `error: true`) means the initiative's slices are unavailable:
  - **If the initiative has no linked slices,** this is the normal no-plan state: `slice_plan` is not complete, and no fault is raised.
  - **If it has linked slices,** a plan that was readable no longer is, and this raises `plan_read_failed`.
  - The decision never reads the error's `message`, because CF reports every error as `code: UNKNOWN` (observed 20261020).
- **Closure.** `plan_read_failed` is project-scoped and deduplicated (121). Plan reads do not run every tick, so 122's rule ("closed on the first complete tick where the kind did not recur") would close it on the next tick that did not read. A link whose last plan read failed therefore counts as a recurrence on every tick until a read of that link succeeds. This is the pattern 122 uses for a failed probe link.
- A plan read is never retried within the tick. The next due read is the retry.

### D9 — Human steps are blocked by a planner, as a store-only action
Status: decided
- A human step is `blocked_on_human` from the moment it becomes current, where current means ready and, from 124, driven. `HumanStepPlanner` emits `BlockHumanStep(node_id)` for each ready step whose executor is human. Act applies it as one `store.block(node_id, kind=HUMAN, context="<step> is a human step", payload={step, cf_project_id, index})`. Here `index` is the initiative's or slice's CF index.
- **Not journaled.** The arch says Act issues each action as a journaled command. Journaling exists to recover an external side effect across a crash. A single store transaction has none, so it needs no recovery. **This is recorded in the arch** as "store-only actions are applied in one transaction and not journaled".
- **Why a planner, not reconcile.** Reconcile only projects what CF says. Choosing to put a person on a step is a decision about the next action, and drive (124) has to filter it like any dispatch.
- **Reconcile's own blocks are faults, not decisions.** An orphan (D5, `lifecycle_orphan`) and an unknown status (D6, `plan_status_unknown`) are cases where CF reported something the Runner cannot project. The arch's fault rule records such a fault against the affected node as a `blocked_on_human` escalation, including one found while observing, such as "a `cf` that returns unexpected JSON". Neither chooses a next action, and neither depends on drive. Like any fault block, each is one store write in Observe and is not journaled.
- **Not in the production planners until 124.** Without drive, every current human step on every linked project would escalate as soon as the project is linked, for example `architecture` on each unstarted initiative. 124 adds the planner to the production tuple together with the drive filter. In 123 it runs only under tests, as 122's test planner does. It stays one small planner with no abstraction around it. 124 registers it and 128 extends it for the merge step (128, D9). The plan records this: entry 4's human-step criterion is proven under a test planner, and entry 5 (124) gains the registration and a criterion for it.
- **When a person resolves a human step without doing the work,** the node becomes runnable. If the step is still current and driven, it is blocked again on the next tick. That is the intended "still waiting on you". When the work is done, D5's complete step resolves the block and marks the step done.

### D10 — Only the Runner creates nodes
Status: decided
- A guard test walks the AST of `src/amoeba/` and fails if any module other than `runner/lifecycle/reconcile.py` calls `create_node`. This follows the writer guard's pattern. Tests and the contract suite's stand-in Runner are outside `src/` and are unaffected.
- No inbox kind creates nodes. Outside parts steer through intents (124).

### D11 — 122's `cf` probe set changes
Status: decided
- 122 probes `cf list slices --json -p <id>` with no index. Run from the resident process's directory, that reads CF's project-level `slicePlan`. On a worktree-scoped project that pointer is empty, so CF exits 1 with "No slice plan configured" (observed on this repository, 20261020). The probe would mark a healthy link failed.
- From this slice on, the probe runs:
  - `cf status --json -p <id>`, with 122's top-level check unchanged. Project-level fields may be empty.
  - `cf list initiatives --json -a -p <id>`, parsed with the full model.

  The slice-list shape is checked on every plan read instead, where D8 separates "no plan" from a failure. The commands are defined once in `plan_read.py`, and `probes.py` uses the same constants.
- **This departs from the arch's probe list** ("Unknown escalates" names `cf list slices --json` as a start-up probe). The arch is updated to say the slice list is checked on each plan read. Plan entry 3 names no commands and is unchanged.
- 122 is implemented before 123. If 122's implementation finds this while running its walkthrough, it drops the slices probe there, and this decision then only swaps in the full models.

### D12 — Upstream models are lenient where CF varies, strict where the Runner relies
Status: decided
- Models use pydantic v2 with `extra="ignore"`, so new CF fields are not an error.
- **Required fields:** `index` (int), `name` (str), and `isChecked` (bool) on initiatives and slices; and `entries` on a slice list.
- **Optional fields** (absent or null): `archFile` and `designFile`.
- **`status`** parses to `PlanEntryStatus`, or to an explicit unknown carrying the raw value (D6). It never falls back to a default.
- A missing required field fails the whole read (`plan_read_failed`). The error names the read, the entry index if one was parsed, and the pydantic error.
- `cf list slices --json` does not expose CF's `indexSource`, so a plan whose entries have no explicit `(nnn)` gets CF's per-file counters as indexes. Those counters change when an entry is inserted. The Runner cannot detect this from the read. It is recorded as an upstream ask (Special Considerations).

### Technology Choices

- Standard library `subprocess` through 122's injected runner, and pydantic v2 for the CF models. There are no new dependencies.
- Automated tests never run the real `cf`. 122's stub `cf` gains `list initiatives -a` and `list slices <index>`, including the error document. Its output comes from fixture files captured from CF 0.19.16, as the parser rule in CLAUDE.md requires.

### Patterns and Conventions

- Each of these is defined once: `LifecycleStep`, `Executor`, `STEP_MAP`, `PlanEntryStatus`, the completion predicates, the "reported complete" predicate, the CF read commands, the `{index}-slice.` stem rule, `is_linked`, and the payload keys `fault_kind`, `former_index` and `former_slice_name`.
- Expected CF failures are answers, either an error document or a failed `PlanRead`, and never exceptions. Unexpected exceptions reach 122's one catch.
- Each module stays under about 300 lines, and each function under about 50.

## Implementation Details

### Database / Storage Schema

Migration `010_node_cf_index.sql`:

```sql
ALTER TABLE nodes ADD COLUMN cf_index INTEGER;
CREATE UNIQUE INDEX idx_nodes_cf_link
    ON nodes (project_id, kind, cf_project, cf_index) WHERE cf_index IS NOT NULL;
```

It applies to a populated v9 store. Existing rows get a null `cf_index`, so none are linked. The stand-in Runner's nodes and any test nodes are unaffected.

### API Contracts

**Store** (`docs/store-contract.md`):

- `CFReference` gains `index: int | None = None`. `update_cf_reference` replaces it along with the other fields, as it already does for them.
- `amoeba inspect nodes` shows `cf_index`, and `--json` gains `cf.index`.

**Lifecycle** (internal, used by 124–129):

```python
class LifecycleStep(StrEnum): ARCHITECTURE; SLICE_PLAN; SLICE_DESIGN; TASKS; IMPLEMENTATION; MERGE; INTEGRATION
@dataclass(frozen=True)
class StepSpec: level: StepLevel; executor: Executor; pipeline: str | None   # set iff pipeline
STEP_MAP: Mapping[LifecycleStep, StepSpec]

class LifecycleTree:                      # frozen view over nodes_for_project
    def step_of(self, node: Node) -> LifecycleStep | None: ...
    def is_linked(self, node: Node) -> bool: ...
    def ready_steps(self) -> Sequence[Node]: ...
def predecessors(tree: LifecycleTree, node: Node) -> tuple[Node, ...]: ...
def predecessors_done(tree: LifecycleTree, node: Node) -> bool: ...

@dataclass(frozen=True)
class BlockHumanStep: node_id: str               # Action union += BlockHumanStep
```

`ProjectView` gains `tree: LifecycleTree`, which replaces 122's flat runnable-node list.

**Settings and CLI:** `plan_read_interval_seconds` (30.0) and `amoeba start --plan-read-interval`. It must be positive, which `runner_tenant()` checks with 122's other bounds.

## Integration Points

### Provides to Other Slices

- **124:**
  - Initiative and slice nodes to target.
  - `LifecycleStep` for `drive_until_step`.
  - `ready_steps` to narrow by drive and hold.
  - `is_linked`, so desired states on orphans have no effect.
  - `HumanStepPlanner`, to register in production.
- **125:**
  - Step nodes with their pipeline from `STEP_MAP`.
  - The slice's index for the pointer write, and `slice_name` where a design file exists. 125 sets it for an undesigned slice from its pointer read-back (D2).
- **126:** `LifecycleStep` as the routing input "step" and the `attempt_counts` key. "Advance" marks a step done, and `ready_steps` then makes its successor ready on the next tick.
- **127:** a resolved human step returns to `runnable` and is blocked again until its work is observed (D9).
- **128:**
  - The `merge` step, which needs git observation and the auto-merge policy.
  - The step map, as the place to add a gate step if one is needed.
- **129:** the tree the proof's unit is driven through.
- **180:** `predecessors` as the single function to widen.
- **Contract documents:**
  - `store-contract.md`: `CFReference.index`, migration `010`, and the `create_node` guard.
  - `context-forge-contract.md`: the two plan reads, D8's error-document rule, and the `cf status --worktree` observations (D7), which 128's gate read relies on.
  - `process-contract.md`: the plan-read setting and flag.
  - `substrate-guide.md`: the 120 row.

### Consumes from Other Slices

- **122:** the tick skeleton, `TickBudget`, the planner seam, Act, faults, closure and probes. This slice changes the probe set (D11).
- **121:** migration order, `done` enforcement (D5's complete and orphan steps rely on it refusing writes), the project-scoped escalation, and the opaque `step` columns.
- **108:** `cf_links` and `latest_cf_snapshots`, used for early plan reads.
- **104 / evidence contract:** the attribution rule, which D2 keeps true.

## Success Criteria

### Functional Requirements

- **Linking a project:** linking a CF project whose fixture plan has initiatives 100 (checked) and 120, and 120's slices, produces:
  - initiative nodes, each with `architecture`, `slice_plan` and `integration` steps;
  - slice nodes, each with `slice_design`, `tasks`, `implementation` and `merge` steps;
  - every step in 100's subtree `done`;
  - every node carrying its CF index.
- **A new slice:** a slice added to the fixture plan (the stub's next answer) gets a node and steps on the first read after the interval, while `projects.json` is unchanged.
- **A renamed slice** keeps its node id and its link, and raises no orphan escalation. A changed `designFile` updates `slice_name` and `artifact_path`.
- **A renumbered or moved slice:** exactly one `lifecycle_orphan` escalation, one new linked node, and the orphan's `index` and `slice_name` cleared.
- **A completed slice that leaves the plan** is unlinked and not blocked.
- **No orphaning on a bad read:** none of the following orphans anything or creates nodes for the affected scope:
  - a failed initiatives read;
  - a failed slice read on an initiative that has linked slices;
  - an empty list where linked nodes exist;
  - a duplicate index.

  Each raises one `plan_read_failed`, which stays open until a read of that link succeeds.
- **An initiative with no slice plan** reads as the no-plan state (`slice_plan` not complete, no fault).
- **Cut-off reads:** a read cut off partway applies nothing, raises no fault, and is read again on the next tick. A run's poll is never cut off by a plan read in the same tick.
- **Early reads:**
  - a changed observed snapshot makes the link's read due on the next tick;
  - a failed snapshot, or one with `changed: []`, makes no early read.
- **Human steps:** with `HumanStepPlanner` in a test tuple, a ready human step (`architecture` on an initiative with no `archFile`, or `merge` after `implementation` is done) is `blocked_on_human` on that tick. When its completion predicate becomes true, the block is resolved by `runner` and the step is `done`.
- **Ready steps follow the predecessor table.** In particular:
  - slice n+1's `implementation` is not ready until slice n's `merge` is done;
  - its `slice_design` is ready once the initiative's `slice_plan` is done;
  - nothing under an orphan is ready.
- **Deferred, deprecated or unknown status:**
  - a `deferred` or `deprecated` slice has no steps, and gains them on a later read that reports an active status;
  - a `degraded` slice has steps, is blocked with `plan_status_unknown`, raises no `plan_read_failed`, and holds the next slice's `implementation` until its own `merge` is done.
- **Crash or fault during reconcile:** a reconcile killed partway, or stopped by an exception injected after its k-th write, is completed by the next read, with no duplicate nodes. The injected exception raises one `unexpected_fault`, and the link is read again on the next tick.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- Migration `010` is tested on a populated v9 store, and the partial unique index refuses a duplicate link.
- Parser tests use the captured CF 0.19.16 outputs, including the slice-list error document.
- The `create_node` guard test passes, and adding a call elsewhere in `src/amoeba` fails it.
- Every CF call in the plan read goes through `TickBudget`, which checks 122's `tick_deadline_seconds` before the call, and runs under `tick_call_timeout_seconds` (122's injected-runner test pattern). A read cut off partway writes nothing for its link.
- The contract documents under Provides are updated, and the CHANGELOG has an entry.

### Integration Requirements

- 100's contract suite passes. Its stand-in Runner creates nodes from `tests/`, outside the guard.
- 122's tests pass with the changed probe set and `ProjectView`.
- 124 can register `HumanStepPlanner` and narrow `ready_steps` without changing `tree.py` or `reconcile.py`.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–2 are automated and use the stub `cf`. Step 3 uses the real `cf` on this repository, and the Runner only reads from CF. Nothing launches a run, because no production planner launches until 125.

1. **Tests:**
   ```bash
   uv run pytest tests/runner/lifecycle tests/upstream/test_cf_plan.py tests/store/test_migration_010.py -v
   ```
   Expected: all pass (256 on 20261023). The reconcile tests are named for the rules they prove, for example `test_renumber_yields_one_orphan_and_one_new_node` (`tests/runner/lifecycle/test_reconcile_create.py`) and `test_empty_list_with_linked_nodes_orphans_nothing` (`test_orphaning.py`).

2. **Full gate and contract suite:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/contract -v
   ```
   Expected (20261023): 2758 passed (2384 before the slice); `ruff` and `pyright` clean; the contract suite 47 passed.

3. **Mirror this repository's plan, with the real `cf`:** verified 20261023 on `cf` 0.19.17 and squadron 0.23.7. `amoeba` is not on `PATH` in a development checkout, so each command is `uv run amoeba …`.
   ```bash
   export AMOEBA_STORE_DIR=$(mktemp -d)
   uv run amoeba start > /tmp/amoeba.log 2>&1 &
   sleep 4
   uv run amoeba submit create-project --project amoeba --by operator
   uv run amoeba submit link-cf-project --project amoeba --by operator \
     --cf-project-id "$(cf list projects --json | python3 -c 'import json,os,sys; print(next(p["id"] for p in json.load(sys.stdin) if p.get("projectPath") == os.getcwd()))')"
   sleep 8; uv run amoeba inspect nodes --project amoeba
   ```
   Expected, as observed:
   - one initiative row for each entry of `cf list initiatives --json -a` (indexes 100, 120, 140, 160, 180, 200), with that index in the `cf_index` column;
   - every step under initiative 100 and its slices 101–110 `done`, including its `integration` (it is checked);
   - initiative 120 with slices 120–131, each with four step rows. **Slices 120, 121 and 122 are now reported complete by CF, so their steps are `done`; the other nine are all `runnable`.** (This walkthrough was written when none was complete.) Initiative 120's `architecture` and `slice_plan` are `done`, and its `integration` is `runnable`: CF reports it `complete` but not checked, and `integration` follows `isChecked`;
   - initiatives 140–200 each with a `runnable` `architecture` step (plus `slice_plan` and `integration`) and no slices, because they have no slice plan.

   Then:
   ```bash
   uv run amoeba inspect messages --project amoeba --json
   ```
   Expected: `[]`. No `plan_read_failed`, no orphan escalation, and no human-step block, because `HumanStepPlanner` is not in production until 124. Stop with `uv run amoeba stop`.

4. **A rename and a renumber, in a scratch copy:** verified 20261023. This writes CF's project registry (`~/.config/context-forge/projects.json`) with a scratch entry, which the last command removes.
   ```bash
   SCR=$(mktemp -d); rsync -a --exclude .git --exclude .venv ./ "$SCR/amoeba-scratch/"
   (cd "$SCR/amoeba-scratch" && cf init --lite --no-ide --name amoeba-scratch-123)
   SCF=$(cf list projects --json | python3 -c 'import json,sys; print(next(p["id"] for p in json.load(sys.stdin) if p["name"]=="amoeba-scratch-123"))')
   export AMOEBA_STORE_DIR=$(mktemp -d)
   uv run amoeba start --plan-read-interval 3 > /tmp/amoeba.log 2>&1 &
   sleep 4
   uv run amoeba submit create-project --project scratch --by operator
   uv run amoeba submit link-cf-project --project scratch --by operator --cf-project-id "$SCF"
   sleep 8; uv run amoeba inspect nodes --project scratch --json     # note slice 131's id
   ```
   `cf init --lite --no-ide` registers the copy without prompting. `--plan-read-interval 3` shortens the 30-second default.

   *Rename.* Edit the name of slice 131 in the copy's `120-slices.runner-routing-engine.md`, wait one interval, and list the nodes again. Observed: `cf list slices 120` reports the new name; `inspect nodes` shows the **same node id, still linked to index 131**, with its title unchanged (a title is display data and is never updated, D1); `inspect messages` is empty.

   *Renumber.* Change `**(131)` to `**(132)` in the same file and wait one interval. Observed: `inspect nodes` shows the old node (same id) with an empty `cf_index`, `blocked_on_human`, and a new `runnable` slice node with `cf_index` 132; `inspect messages --json` shows exactly one escalation on the old node with payload `{"fault_kind": "lifecycle_orphan", "cf_project_id": "<scratch id>", "former_index": 131, "former_slice_name": null}` (`former_slice_name` is null because the plan lists no design file for 131).

   Clean up: `uv run amoeba stop`, `cf project rm "$SCF" --yes`, and delete `$SCR` and the store directories. Afterwards `cf list projects --json` shows this repository's project active again.

   **Caveat found while capturing the fixtures:** with CF 0.19.17, `cf list slices <index> --json` for an initiative without a slice plan prints its `error: true` document on **stderr**, with an empty stdout and exit 1. The plan read classifies a non-zero exit from both streams (see [Plan reads](../../../docs/context-forge-contract.md#plan-reads-slice-123)).

## Risk Assessment

### Technical Risks

- **Identity across plan edits.** A wrong orphaning resets a slice's history, and a wrong link attaches history to the wrong slice.
- **A bad read taken as a plan change.** A misconfigured CF or a broken plan document could look like everything was removed.
- **Unstable indexes.** A plan without explicit `(nnn)` indexes gets CF's counters as indexes, and the Runner cannot see this (D12).

### Mitigation Strategies

- Links are keyed on the stored index only, enforced by a unique index. Display data is never matched (D1, D2).
- Orphaning needs a successful, non-empty, duplicate-free read of that exact scope. Orphaning never deletes, and it escalates (D5).
- Unstable indexes are a documented requirement on projects driven by the Runner (explicit indexes). They are also an upstream ask for `indexSource` in `cf list slices --json`.

## Implementation Notes

### Development Approach

Relative effort: 3/5. Suggested order. Each step leaves the suite green.

1. Migration `010`, `CFReference.index`, the inspect column, and their store tests and contract text.
2. `upstream/context_forge/plan.py` with the captured fixtures. Then swap the models into 122's probes and drop the slices probe (D11, D12).
3. `steps.py` and `tree.py`: the step map, `is_linked`, predecessors and `ready_steps`, as pure tests over built trees.
4. `plan_read.py`: the cadence, the snapshot trigger and budget checks, with the stub `cf` extensions and the setting and flag.
5. `reconcile.py`, rule by rule (D5, D6), with the crash-repeat test and the `create_node` guard.
6. `human_steps.py`, `BlockHumanStep` in Act, and the new fault kinds and closure-recurrence rule (D8, D9).
7. Contract documents, the CHANGELOG, and the arch and slice plan edits listed below.

**Testing approach.** Reconcile is tested against `Store.open_temporary()` with hand-built `PlanRead` values, one test per rule and safety rule. The plan read is tested with an injected subprocess runner and clock. Fixture files hold the real CF outputs captured on 20261020.

### Special Considerations

- **Arch and slice plan edits.** These follow the departures above:
  - In the arch: no gate nodes in v1 (D3); no v1 step has a CF-write executor (D3); Observe reads every linked project's plan on an interval (D7); store-only actions are not journaled (D9); the slice list is not a start-up probe (D11); a done or already-blocked orphan does not get its own escalation (D5).
  - In plan entry 4: the new-slice criterion is reworded to "appears on the next plan read" (D7); the failed-snapshot criterion is reworded to "triggers no early plan read" (D7); the step map assigns a pipeline or a human step, with no CF-write step in v1 (D3); `cf status` is left to 125 and 128 (D7); the human-step criterion is proven under a test planner (D9); a done or already-blocked orphan does not get its own escalation (D5).
  - In plan entry 5 (124): registering `HumanStepPlanner` with the drive filter, and a criterion for it (D9).
  - The plan's Future Work gains the two items below.
- **Future Work (slice plan):**
  - **Mark step done.** An intent, or a resolution, that marks a step done for a slice already partly done by hand (D6).
  - **CF `indexSource`.** Upstream asks to CF: `indexSource` on `cf list slices --json`, and a distinct error code for "no slice plan" (D8, D12).
- **Security.** CF output is stored only as titles, paths and slugs. Error payloads hold at most the head of CF's output, bounded like 122's tail. CF prints no credentials.
- **Performance.** Reconcile does one `nodes_for_project` read and writes only what changed. A first link of a project with a hundred or more nodes writes them one transaction each, once.
