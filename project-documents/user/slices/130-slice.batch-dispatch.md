---
docType: slice-design
slice: batch-dispatch
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 125
- 126
- 127
- 128
- 129
interfaces: []
dateCreated: 20261020
dateUpdated: 20261021
status: not_started
turns: 41
promptTokens: 4711197
cachedTokens: 4537200
cacheWriteTokens: 173917
completionTokens: 51180
durationSeconds: 583.0
costUsd: 3.957987
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Batch Dispatch

## Overview

This slice lets the Runner design a whole initiative's undesigned slices in one Squadron run, `slices-plan`, instead of one `P4` run per slice.

- **One dispatch, many nodes.** The batch is one `sq_run` entry on the initiative node. It names the `slice_design` step nodes it covers. It is launched, confirmed, polled and recovered by 122's and 120's rules, unchanged.
- **Per-item outcomes.** When the run ends, ingestion reads Squadron's batch report (`{run_id}.slices.report.json`, `items[]`). It writes one resolved `sq_batch_item` entry on each item's step node, records that item's review, and leaves the entry for routing. From there, 126 routes it and 127 resolves it like any run outcome.
- **The Runner acts only at flagged items.** A passed item is routed like a passed `P4`. A flagged or unrun item blocks on a human with Squadron's `flagKind`.
- **Per-item resume.** A `retry` or `accept` decision on a flagged item runs `sq run --resume <run_id> --item <index> --decision retry|accept`, journaled as an `sq_item_resume` entry on the step. Its outcome is the item's rewritten record.
- **Batching is opt-in and exact.** A project opts in with one per-project config key. A batch is issued only when the slices Squadron will select are exactly the slices the PM is driving. Otherwise 125's per-phase `P4` path runs, unchanged.

## Value

Developer value:

- A PM who drives an initiative to `slice_design` gets every design written in one unattended run, which the arch expects to be common. Squadron's per-slice session reset, revise loop and flagging all apply, and the PM sees only the slices Squadron could not finish.
- Each slice keeps its own history. Its verdict, attempts, blocks, resolutions and routing decisions are on its own step node, as if it had been designed by `P4`. Batch and per-phase runs of one slice mix freely: a flagged item can be retried in place, or rerun later as a fresh `P4`.
- Squadron's flag handoff contract (Squadron `docs/PIPELINES.md`, "Batch reports and the flag handoff", which names Amoeba as its caller) gets its consumer.

## Technical Scope

**Included**

- `amoeba.runner.batch`, a new subpackage:
  - `selection.py`: the predicted selection and batch eligibility (D3), pure.
  - `planner.py`: `BatchPlanner`, which emits `LaunchBatch`.
  - `report.py`: the batch report model and its loader (D5).
  - `fanout.py`: report items to per-step outcomes, reviews and blocks (D6, D7), pure apart from file reads.
  - `item_resume.py`: `ResumeItem` and `ObserveItem` in Act, and the item-resume observer (D9).
- A per-project config key, `design_dispatch: per_phase | batch`, defaulting to `per_phase`, in 128's per-project config (D2).
- Store contract changes, landed first (D10):
  - two journal kinds, `sq_batch_item` and `sq_item_resume`, and the `batch_items` parameter on `sq_run`;
  - `record_batch_report`, one transaction for a whole batch;
  - `RUN_RESULT_KINDS`, the one definition of "a step's latest run entry".
- Extensions to earlier Runner code:
  - 125: `dispatch_state` and the checkout hold read `RUN_RESULT_KINDS` and batch coverage. The pointer-move check skips batch entries.
  - 126: routing input `outcome` (three new values), and a per-item time bound.
  - 127: the `flagged_item` situation and its decisions.
  - 120: pruning keeps a batch run while any of its items is not done.
- Stub `sq` support for `slices-plan`, its report file and `--item` resume, using fixtures captured from squadron-ai 0.23.5.
- Contract text in `docs/store-contract.md`, `docs/process-contract.md`, `docs/evidence-contract.md` and `docs/runner-guide.md` (129).

**Excluded**

- **`tasks-plan` and `implement-plan`** (D1). The `tasks-plan` case is added to the slice plan's Future Work.
- **Resuming an ended batch whole** (plain `--resume` or `--flagged`). After fan-out, each item is decided on its own (D8). A paused batch is resumed whole, by 127's `retry`.
- **Writing CF pointers for a batch.** Squadron's `each` step sets arch, slice and phase for every item (D4).
- **Changing Squadron's pipeline params or models.** Squadron's `slices-plan` defaults apply, as 125 D5 does for `P4`.

## Dependencies

### Prerequisites

- **125, 126, 127 and 128, merged.** This slice extends their dispatch states, routing inputs, resolution situations and per-project config.
- **129, complete.** The plan places this slice after the first proof. If 129's write-up proposes changes to this slice's entry, the entry and this design are updated before Phase 5.
- **squadron-ai 0.23.5 or later**, by shape (observed in Squadron source at `bb5f169e` on 20261020):
  - `slices-plan` with the `plan` param, and a single `each` step named `slices`;
  - batch report `schemaVersion` 1;
  - `sq run --resume <id> --item <index> --decision retry|accept [--instructions TEXT]`.

### Interfaces Required

**Squadron.** The report, its handoff contract and item resume are documented in Squadron's `docs/PIPELINES.md` ("Plan Batch Pipelines", "Item resume", "Batch reports and the flag handoff"). This design relies only on the following points, observed in squadron-ai 0.23.5 (`bb5f169e`) on 20261020:

- **Selection:** `cf.undesigned_slices(plan)` in `pipeline/sources.py`, with no param to narrow it (D3).
- **Report:** `{runs_dir}/{run_id}.slices.report.json`, `schemaVersion` 1. Per item, the Runner reads `index`, `outcome`, `flagKind`, `finalVerdict`, `reviewFile` and `unsavedParts`, plus `resumedAt` for item resume. `reviewFile` names the worst part of a split review.
- **`sq runs wait --json`** carries no items. A batch with flagged items ends `completed`, and its `reviews` list has every item's reviews, with no item index.
- **Item resume** changes neither the run's state nor its status, and prints no `run_id=` line.
- **Run ids** must contain no dots. 122's minted ids contain none.

**Runner and store:** the earlier slices' functions this design names are listed under Consumes from Other Slices.

## Architecture

### Component Structure

```
amoeba/runner/batch/                 NEW
  selection.py    predicted_selection(initiative, tree) → indexes (pure)
                  batch_eligibility(view, initiative) → Eligible(items, checkout) | Ineligible(reason)
  planner.py      BatchPlanner: LaunchBatch per eligible initiative
  report.py       BatchReport, BatchItemRecord (pydantic); load_report(path) → BatchReport | ReportUnknown
  fanout.py       fan_out(entry, outcome_document, report) → [ItemOutcome] (D6, D7)
  item_resume.py  ResumeItem / ObserveItem act; item_resume_observer (D9)
amoeba/runner/
  decide.py        CHANGED  Action += LaunchBatch, ResumeItem, ObserveItem; guard covers every item
  dispatch/state.py CHANGED  RUN_RESULT_KINDS; batch coverage → IN_FLIGHT (D4)
  dispatch/planner.py CHANGED skips steps BatchPlanner claimed this tick
  dispatch/pointer_watch.py CHANGED  skips entries with batch_items
  finish.py        CHANGED  an entry with batch_items goes to batch ingestion
  routing/inputs.py CHANGED outcome += flagged, not_run, no_record (D7)
  resolutions/classify.py CHANGED  flagged_item situation (D8)
  tenant.py        CHANGED  production planners = (HumanStepPlanner, BatchPlanner, DispatchPlanner,
                                                   ContinuationPlanner)
amoeba/store/
  journal_models.py  CHANGED  CommandKind += SQ_BATCH_ITEM, SQ_ITEM_RESUME; keys; RUN_RESULT_KINDS
  batch_report.py    NEW      record_batch_report (D10)
amoeba/process/observers/sq_item_resume.py  NEW  recovery observer (D9)
amoeba/process/run_pruning.py  CHANGED  batch runs with open items are held (D10)
```

### Data Flow

**A batch, end to end:**

```
tick n    decide: initiative I, design_dispatch=batch, predicted selection {131,132,133}
                  = current, fresh slice_design steps, one free checkout C on the target
                  → LaunchBatch(I, items, C)
          act:    cf get --json in C → path and worktree match (no write)
                  122: mint id, journal sq_run on I {pipeline: slices-plan, params: {plan: I},
                       checkout: C, run_id, batch_items: [{index, node_id}…]}, detached launch
tick …    observe: confirm, poll by run id (122). Steps 131–133 are IN_FLIGHT; C is held.
tick m    observe: outcome ≠ running → finished
          plan read of I (123), so each slice node has its slice_name
          load report → fan_out → record_batch_report: one transaction
              per item: sq_batch_item entry on its step, resolved, verdicts, ledger rows,
                        block if not completed, awaits_routing
              then the batch entry resolved, with no awaits_routing of its own
tick m+1  route (126): each item entry → advance | rerun | escalate
          resolutions (127): a flagged item answered retry → ResumeItem
          act:    read report, record unchanged → journal sq_item_resume on the step
                  → sq run --resume <run_id> --item 132 --decision retry [--instructions …]
tick …    observe: the child's exit, or a change in item 132's record
          finish:  the new record → the sq_item_resume entry resolves, awaits_routing
```

### State Management

- **All durable, in the store.** Nothing new is held across ticks.
  - The batch's items and checkout are in its `sq_run` entry's parameters.
  - Each item's outcome is a resolved entry on its own step node.
  - The report path is in the batch entry's result, and each item's record is in its item entry's result.
- **Per tick, in memory:** the set of step nodes covered by an unresolved batch entry, built with the view.
- Steps stay `runnable` while their batch is in flight, as 125 D3 does for one run.

## Technical Decisions

### D1 — Only `slice_design` is batched, with `slices-plan`
Status: decided
- `BATCH_PIPELINES: Mapping[LifecycleStep, str]` holds one entry, `slice_design → slices-plan`. It is defined once, beside 123's `STEP_MAP`.
- **`implementation` (`implement-plan`) is not batched.** 123 D4 makes implementation sequential behind each slice's `merge`, and the default merge policy is human (128). Under `merge=false`, every item after the first would be flagged `dependency`, because its predecessor is unmerged. A batch would only be useful under auto merge, and it would merge several slices with no Runner decision between them. The arch puts every gate the Runner cares about between runs.
- **`tasks` (`tasks-plan`) is not batched in this slice.** Its selection is not 1:1 with undone steps. It also selects slices whose tasks exist but whose tasks review is missing or below threshold, including slices whose `tasks` step the store already holds as done by a PM accept (127). It pre-flags slices whose design review is below threshold, which the store may hold as accepted. Mapping that needs its own rules, so a Future Work entry records it.
- Rejected: batching all three now. The plan says `slices-plan` first, and only its selection is a clean predicate over CF's plan read.

### D2 — Batching is a per-project opt-in
Status: decided
- `design_dispatch: per_phase | batch`, default `per_phase`, is one key in 128's per-project config, beside the merge policy. `DesignDispatch` is a `StrEnum` defined once.
- **Why opt-in.** `slices-plan` is not `P4` run many times:
  - its default models differ (`slices-plan` uses `opus` and `glm-flash`, `P4` uses `opus` and `deepseek4-flash`);
  - it flags an exhausted loop instead of pausing;
  - its spend is unattended across the whole plan.

  Switching to it without the PM's word would change cost and review quality silently.
- The chosen value is recorded in the batch entry's parameters, as 128 records the merge policy on a dispatch.
- Rejected: inferring batch from the drive target (an initiative-level drive). Drive already means "advance up to a step". Giving the target level a second meaning would make two intents with the same settings behave differently.

### D3 — A batch is issued only when its selection is exactly the driven set
Status: decided
- `predicted_selection(initiative, tree)` returns the indexes of the initiative's linked slice nodes whose last-read CF status is not `complete`, `deferred` or `deprecated`, and that have no `cf.artifact_path` (`designFile`). This is Squadron's `undesigned_slices` predicate over the same `cf list slices <plan> --json` read (123, D7). The excluded statuses are defined once and cite Squadron's source.
- `batch_eligibility` is pure. An initiative is **eligible** when all of these hold:
  1. The project's `design_dispatch` is `batch`.
  2. The predicted selection has at least two slices. One slice goes to `P4`, which pauses where a batch would flag.
  3. Every predicted slice has a `slice_design` step in `current_steps` (124), so each is ready, driven and not held.
  4. Each of those steps is `NEEDS_POINTER` by 125's `dispatch_state`: no unresolved entry, nothing awaiting routing, no reissue, and no applied resolution waiting to be carried out (127, D5).
  5. Every step resolves to the same checkout (125, D1), and that checkout is free (125, D4).
  6. 128's pre-dispatch checks pass for every item. 128's checkout check must report the checkout on the target, because Squadron refuses planning commits on any other branch. If 128 has a `slice_design` check that needs CF pointed at the slice, the batch is ineligible, because a batch sets no per-slice pointer before it launches.
- **Ineligible** is not an error. `BatchPlanner` emits nothing, and 125's `DispatchPlanner` handles the current steps one by one. So a held slice in an otherwise driven initiative turns the batch off for that initiative, and the driven slices are designed by `P4`. A held slice is never designed by a batch.
- `BatchPlanner` runs before `DispatchPlanner`. The steps it claims in a tick are passed on, and `DispatchPlanner` skips them, so the two planners never act on one step.
- **The prediction can still be wrong.** CF can change between the plan read and Squadron's own read. That difference is caught at ingestion (D6) and reported, never guessed.
- **The prediction copies an undocumented Squadron predicate.** `undesigned_slices` is Squadron source, not a published shape, so it can change without notice. `design_dispatch: batch` is therefore experimental until S15 (D11) removes the prediction. The operator guide says so, and names the squadron-ai version the excluded statuses were observed in. A drift is caught after the fact by `batch_selection_mismatch`, which is checked at every fan-out, not only the first. The Runner cannot inspect Squadron's predicate before launch, so a drift costs at most one batch's unwanted items before the PM sees it. **Closing condition:** when S15 ships, the batch passes the driven set as its item filter, the prediction becomes a check only, held slices stop turning batching off, and the experimental label is removed. That change is a Future Work entry tied to S15.
- Rejected: launching whenever any driven slice is undesigned. Squadron would design the plan's undriven and held slices too, which breaks the arch's rule that hold stops anything new.

### D4 — A batch is one `sq_run` entry on the initiative node, with no pointer write
Status: decided
- **The entry.** Kind `sq_run` on the initiative node. Its parameters are 122's (`pipeline: slices-plan`, `params: {plan: "<initiative index>"}`, `checkout`, `run_id`) plus:
  - `batch_items`: `[{index, node_id}]`, the predicted items with their step node ids, in index order;
  - `design_dispatch: batch`.

  `batch_items` is one key, defined once. Its presence is what makes an entry a batch everywhere it matters.
- **Launch, confirmation, polling and recovery are 122's and 120's**, by run id, unchanged. The launch argv is `[sq, run, slices-plan, -p, plan=<index>, --run-id, <id>]` in the checkout. `dispatch_params` gains its `plan` case.
- **No pointer write.** Squadron's `each` step sets CF's arch, slice and phase for every item. 125 D2 writes a pointer for two reasons, and neither applies here:
  - `slice_name` for attribution: batch ingestion begins with a plan read instead (D6);
  - 128's gate read: D3 point 6 excludes any check that needs the pointer.
- **The checkout is still confirmed.** Act runs `cf get --json -p <cf project id>` in the checkout before journaling, and applies 125 D1's path and worktree comparison, the same function, without the index check. A mismatch blocks every item step with `checkout_unresolved`. It is a read, so it is not journaled. This is the arch's precondition check in Act (127 D4's pre-poll is the first): a read made immediately before a command, so the command never acts on state that moved since Observe. It can withhold the command and record what it read, as D9's `resume_skipped` and 127's observed run do. It never issues a different command.
- **Batch coverage.** For each step named in the `batch_items` of a batch run's latest entry, while that entry is unresolved or resolved `paused` (D6), `dispatch_state` returns `IN_FLIGHT`. 125 D4's first hold rule (an unresolved `sq_run` with that checkout) already holds the checkout.
- **What batch entries do not do:**
  - **The pointer-move check (125, D11) is narrowed, not skipped.** The batch moves CF's slice pointer itself, item by item, so a move to a slice in the entry's `batch_items` is expected. A move to any other slice, or off the initiative, is someone else's and raises `pointer_moved` as it does for one run.
  - **The checkout hold is the arch's, unchanged.** A paused batch is a paused run (D8), so it holds its checkout until a poll shows it is no longer `paused`, as any paused run does.
- **The guard.** `LaunchBatch` names every item's step. 124's current-step guard checks each one, and refuses the action if any is not current.
- Rejected: one `sq_run` entry per item step, all with the batch's run id. That means n entries in flight for one process, n polls of one run per tick, and n recoveries of one launch.

### D5 — The batch report is read from the runs directory, by its documented name
Status: decided
- **Path:** `{sq_runs_dir}/{run_id}.slices.report.json`. `sq_runs_dir` is the existing setting, which 120 kept only for legacy matching. Its documentation now says it also locates batch reports. The step name `slices` comes from the pipeline definition. It is defined once, beside `BATCH_PIPELINES`, and checked against the report's `stepName`.
- **This is a supported surface.** Squadron documents the report as the flag-handoff contract. The run-state file beside it stays unread (arch, "Observe outcomes from the contract").
- `load_report(path)` returns `BatchReport` or `ReportUnknown(reason)`. It returns `ReportUnknown` when:
  - the file is missing or unreadable, or is not JSON;
  - `schemaVersion` is not 1;
  - `docType`, `runId`, `pipeline` or `plan` differ from the entry's;
  - an item's `outcome` or `flagKind` is outside its closed set.

  The model is lenient about added keys and strict about the fields the Runner routes on (123, D12).
- `reason` is kept as text for people and never matched.
- The report shape cannot be probed at start, because that needs a real batch. It is checked on every read, and a shape the Runner cannot read escalates.

### D6 — Ingestion fans a batch out to its item steps
Status: decided
- **Only an ended batch fans out.** A batch whose outcome is `paused` is not fanned out. It is ingested as 125 ingests a paused run: its entry resolves with outcome `paused`, and the initiative node blocks on `SQ_CHECKPOINT` with the run id and checkout. Batch coverage (D4) counts the latest entry on a batch's run id when it is unresolved or resolved `paused`, so its items stay `IN_FLIGHT`. A continuation of a batch (127, D4) copies its `batch_items`, so the coverage carries over, and when the continued run ends with any other outcome, it is that entry that fans out (D8).
  - **If the initiative node is already blocked** (the store allows one open block per node), no second block is written, as for any node already blocked (125, D6; 121's `effect=None`). The pause is still recorded on the entry, and 127 classifies by the latest run entry's outcome, not by block kind. So the standing block's resolution is offered the paused-run decisions, and the pause shows in `inspect journal` and `sq runs list`. Item coverage reads the entry, not the initiative's status, so the items stay `IN_FLIGHT` either way, and the run keeps being polled, as any run in flight under a blocked node is (arch, "Faults stay in their project").
- **Before recording,** batch ingestion runs one plan read of the initiative, 123's read and reconcile, under `TickBudget`. Each designed slice then has a `designFile`, so its node has the `slice_name` that attribution needs. If the read fails, the batch entry stays unresolved and the next tick tries again, as 125 D2 does for a failed read-back. After `launch_grace_seconds` has passed since the run's finish was first observed, the entry goes through `journal_escalate`.
- **Matching items to steps.** By CF slice index, through `batch_items`:

  | Case | Effect |
  | --- | --- |
  | Predicted, with a record | An item entry from the record |
  | Predicted, no record | An item entry with outcome `no_record`. Its `no_record_reason` is `not_selected` when the batch completed (Squadron did not select it), or `not_reached` otherwise (the batch stopped first). The reason is payload, not a routing input. |
  | Record not predicted | The mismatch escalation only. No item entry, review, block or routing is written, because no one drove that step. A review the batch saved for that slice is left to detection (106), which records it as external. |

  - **The mismatch escalation** is one project-scoped `batch_selection_mismatch`, raised once per batch. Its payload holds the run id, the unpredicted indexes and the predicted indexes Squadron did not select. The escalation tells the PM that a slice may have been designed without a drive. It follows 121's rules for project-scoped escalations. It is raised at fan-out, and it closes on the first complete tick where the fault does not recur, which is the next one. Its message stays in the store as the record.
  - **A `ReportUnknown`** makes every predicted item an entry with outcome `unknown` and `review_fault: batch_report_unknown`, holding the reason. Nothing is recorded from the report.
- **The item entry.** Kind `sq_batch_item`, on the step node, issued and resolved in one write (D10). Its result:
  - `run_id`: the batch's;
  - `outcome`, from the mapping in D7;
  - `item_record`: the item's record, verbatim, or null;
  - `batch_entry`: the batch entry's id;
  - `verdict_ids` and `review_fault`, as in 125 D6.

  It carries no `outcome_document`. The batch entry's result holds it once, with `report_path`.
- **Ingestion blocks,** as 125 D6 does:
  - `completed`: no block.
  - Every other outcome: `HUMAN`, payload `{reason: item_<outcome>, run_id, item, flag_kind, failed_step, no_record_reason}`. `reason` text is carried in the context for people.

  A flagged item is a person's decision by Squadron's contract, so it posts an escalation. That differs from a paused `P4`, whose `SQ_CHECKPOINT` block posts no message.
- **One transaction for the whole batch.** `record_batch_report` writes every item entry with its verdicts, ledger rows and block, then resolves the batch entry `completed`, or `failed` for orphaned and vanished runs, as 125 D6 does. A crash leaves the batch entry unresolved and nothing written. The next tick polls, finds the same outcome, and repeats. Verdict ids are content digests, so a repeat is a retry.

### D7 — Each item's review, and its routing inputs
Status: decided
- **Review selection.** The item's `reviewFile` names the worst part of its last review. The Runner takes the last entry of the outcome document's `reviews` list whose `path` equals `reviewFile` or whose `paths` contains it. That entry is then recorded as 125 D7 records one: every part file of a split review, in order, with the same parse, attribution and ledger key. The two surfaces are matched by path, never by position.
  - `reviewFile` is null and the item has a `finalVerdict`: `review_unknown`. Squadron reviewed it but saved nothing.
  - `reviewFile` is null and there is no `finalVerdict` (a pre-flag, or a step that failed before review): no review, and `verdict_ids` is empty.
  - `reviewFile` is set and no `reviews` entry matches, the file is missing or unparseable, or attribution gives a node other than the item's slice: `review_unknown`, as in 125 D7.
  - A non-empty `unsavedParts` is `review_unknown` for that item, because the split review is incomplete.
- **Routing inputs** (126, D3: the vocabulary grows by code):
  - `outcome` gains three values. `completed` keeps its meaning, so 126's advance rules apply unchanged to a passed item.

    | Item | `outcome` |
    | --- | --- |
    | `passed`, `accepted` | `completed` |
    | `flagged` | `flagged` |
    | `not_run` | `not_run` |
    | no record (D6) | `no_record` |
    | report unknown | `unknown` |

  - Squadron's `flagKind` is not a routing input in this slice. No shipped rule would use it, and it is already in the block payload and the item record. It becomes an input when the first table edit needs one (126, D3: the vocabulary grows by code).
  - `checkpoint_kind`, `at_loop` and `failure_kind` are `none` for item entries. Squadron reports no per-item checkpoint or failure document.
  - `verdict`, `standing`, `severity` and `recurrence` come from `verdict_ids`, as 126 reduces them.
- **An `accepted` item is a completed outcome with its loop's last verdict,** usually CONCERNS. That is what `P4` gives when `accept_if` is met, so the table treats both the same way. The shipped table already escalates CONCERNS, so nothing advances that the per-phase path would hold.
- **The shipped table gains no rules.** 126 D4 requires advance and rerun rules to name `outcome: completed`. The catch-all escalates every new value, which is the arch's "before 140, every such point routes to a human". Routing on the flag kind waits for evidence, and then needs the input added (above) and a table edit.
- **Time bound** (126, D7). The table's bound for `slices-plan` is per item: its entry is marked `per_item: true`, and a batch's bound is that value times its number of predicted items. An item resume is bounded by the per-item value. The multiplication is in 126's bound function, the one place bounds are computed. The per-item value starts at `P4`'s bound in the shipped table (126, D7: 240 minutes), because an item is one design with its review loop. If 129's write-up changes `P4`'s bound, the per-item value follows it. If it has no usable `P4` timing, the value stays at 240. Rejected: one fixed bound for a whole batch. A batch's length scales with its item count, so any fixed value is either too short for a large plan, escalating a healthy run, or too long for a small one, hiding a stall. The per-item flag is one key in the table entry and one multiplication in 126's bound function.

### D8 — Resolutions on items: per-item resume, never a whole-run resume
Status: decided
- 127's `classify` gains one situation. It is tested after `unresolvable` and `no_decision`, and before `paused_run`:

  | Situation | When | Allowed |
  | --- | --- | --- |
  | `flagged_item` | the latest run entry is an `sq_batch_item` or `sq_item_resume` with outcome `flagged` or `not_run` | `retry`, `accept`, `handled`, `rerun`, `stop` |

  - `accept` requires `item_record.flagKind` to be `review_unresolved`, otherwise `not_review_unresolved`. This is Squadron's own rule, and it is checked first so Squadron's exit 2 is never the first signal.
  - `not_run` takes no `accept` (`decision_not_applicable`).
  - Item outcomes `completed` reach 127's `completed_outcome` unchanged (`accept`, `rerun`, `stop`). `no_record`, `unknown` and an `sq_item_resume` resolved `failed` or `unknown` reach `ended_run` (`rerun`, `stop`), and also allow `handled`, because a record may have changed since.
- **What each decision does:**
  - `retry` and `accept` lead to `ResumeItem`.
  - `handled` leads to `ObserveItem`: read the item's current record and route it.
  - `rerun` is 125's fresh `P4` of that one slice, through `NEEDS_POINTER`. `P4` runs with `existing: keep`, so it revises the design the batch wrote. `slices-plan` would not reselect that slice, because a design file now exists.
  - `stop` is 127's.
- **A paused batch is a paused run, answered whole.** It is not fanned out (D6), so no item has been decided yet. The initiative node takes 127's `paused_run` situation unchanged, except that `accept` is refused with `decision_not_applicable`, because accepting one item's loop is an item decision.
  - `retry` is 127's continuation: `sq run --resume <run_id> --decision retry`. Squadron continues the batch, keeping its passed and accepted items. This is the normal answer to a `usage_limit` pause (squadron#248: the batch pauses when the account's usage limit runs out, instead of flagging every later item). The PM answers after the checkpoint's `resets_at`. 127 D2's refusal at an interactive checkpoint still applies.
  - `handled` and `stop` are 127's.
- **An ended batch is never resumed whole.** After fan-out, each item has its own block and its own decision. A plain resume, or Squadron's `--resume --flagged`, would rerun every flagged item under one decision, across items the PM decided separately. Items with no record block on a human like any other item. Their allowed decisions are `rerun` and `stop` (`ended_run`), and the Runner never picks one itself.
- **An item record with `flagKind: paused`** appears only in a paused run, which is not fanned out. If one reaches fan-out anyway, `retry` and `accept` are refused with `item_paused`, because a record does not say which checkpoint paused it.
- **Instructions** pass through to `--instructions` as data, as in 127.

### D9 — The item resume: journaled, observed and recovered by its record
Status: decided
- **Kind `sq_item_resume`**, on the step node. Required keys: `run_id`, `item`, `decision` (`retry` or `accept`), `checkout`, `report_path`, `record_before` (the item's record as read just before launch), `continues` and `resolution`. The decision is in the required keys because Squadron needs it on every call.
- **Act** follows 127 D4's order:
  1. Check the budget, then read the report. A report that is now `ReportUnknown` blocks the step on `HUMAN` with `batch_report_unknown`, and nothing is launched. If the record differs from the routed entry's `item_record`, the item has moved on since the PM decided, for example through a hand resume. An `ObserveItem` result is recorded instead, with `resume_skipped: record_changed`. A decision is carried out only on the record it was made for.
  2. Check the budget again, then journal.
  3. Launch detached, with 122's `launch()`, in the checkout: `[sq, run, --resume, <run_id>, --item, <index>, --decision, <d>]`, plus `--instructions <text>` when given. Item resume prints no `run_id=` line, so 122's line confirmation is not used. The entry is in flight from launch.
- **Observation** each tick, at most once per `run_poll_interval_seconds`, is by the item's record, with the exit code used only to fail fast:
  - **The record differs from `record_before`:** finished. The new record is the outcome, whatever the exit code. A halted or re-flagged item routes on its new record like any other.
  - **The record is unchanged and the tracked child has exited:** failed, with the exit code and the stderr tail. Squadron's codes are kept as data, never matched.
  - **Otherwise:** in flight. After a restart there is no tracked child, so an unchanged record stays in flight until recovery decides it (below) or the time bound escalates it.

  A lighter design, observing only the record, was rejected: a refused resume (exit 2) never changes the record, so it would sit until the time bound, hours later, instead of failing on the next tick.
- **Finished.** The entry resolves `completed` with the item entry result shape (D6), from the new record, with the same review selection (D7). The review list is the run's `reviews`, read with one `poll_run`, because the resumed item's reviews are appended there. The entry awaits routing.
- **Failed.** The step blocks on `HUMAN` with `{reason: resume_failed, resume_failure, run_id, item, exit_code, stderr_tail}`, and the entry resolves `failed`. 127's rule holds: the result keeps the item's real record, so the situation is still `flagged_item`, and the PM can retry again.
- **Recovery observer** (100's protocol, at start):
  - The record differs from `record_before`: the resume ran. The entry is left in flight, and the Runner finishes it on the first tick (122, D3).
  - Otherwise: `Unknown`. The resume may still be running, or may have died with the host. Nothing Squadron publishes tells them apart, so the entry escalates, and the PM answers `handled` once the record shows the outcome, or answers `rerun` or `stop`.
- **`review-producing`.** `sq_item_resume` joins `REVIEW_PRODUCING_KINDS`, so detection defers while it is unresolved. `sq_batch_item` is never unresolved and does not join.
- **Squadron asks** (dependency register, D11): S14 asks for a supported sign that an item resume is in progress, for example a `resumeStartedAt` written when the resume claims the item. With it, the `Unknown` recovery case becomes exact.

**Failure modes of the new I/O paths** (D5, D6, D9):

| Path | Failure | Handling |
| --- | --- | --- |
| Report read | Missing, unreadable, wrong shape | `ReportUnknown`. Every item is `unknown` (D6), or the resume blocks before launch (D9). |
| Report read | Slow or large | It is one local file read, not a subprocess, so the per-call timeout does not apply. A plan's `items[]` is one entry per slice in one plan, tens at most, and `record_batch_report` writes them in one transaction. The tick deadline is checked before the read. |
| Plan read before fan-out | Fails or times out | The batch entry stays unresolved and the next tick retries. After `launch_grace_seconds`, `journal_escalate` (D6). |
| `record_batch_report` | Host dies mid-transaction | Nothing is written. The next tick polls the same outcome and fans out once. Proven by the crash test. |
| Item resume child | Hangs | It stays in flight until the per-item time bound escalates it (D7). The Runner never kills it. |
| Item resume child | Refused or halted with no record change | Failed on the next tick, with the exit code and stderr tail. |
| Item resume after restart | Record unchanged | Recovery answers `Unknown`, and the step escalates. |

### D10 — Store contract changes, landed before Runner code
Status: decided
- **Journal kinds:**
  - `sq_batch_item`. Required keys: `run_id`, `item`, `batch_entry`. It is written only by `record_batch_report`, already resolved. Its observer answers `Unknown` with "an unresolved batch item entry is a store defect", so recovery escalates rather than guesses.
  - `sq_item_resume` (D9), with its observer registered.
- **`batch_items`** is an optional `sq_run` key. It must be a non-empty list of `{index, node_id}`, and every `node_id` must be a step node in the entry's project. An `sq_run` with `batch_items` is never set `awaits_routing` by its own resolution. Its item entries are set instead.
- **`record_batch_report(batch_entry_id, items, *, outcome, result)`**, where each item is `(node_id, item_result, reviews, block | None)`. It runs as one transaction:
  1. 125's per-review checks, for every review;
  2. per item: insert the resolved `sq_batch_item` entry, record its verdicts and ledger rows, write its block, and set `awaits_routing`;
  3. resolve the batch entry.

  Any failed check writes nothing. A verdict or ledger key already present is the existing retry rule.
- **`RUN_RESULT_KINDS = {sq_run, sq_batch_item, sq_item_resume}`**, defined once in `journal_models.py`. It is "a step's latest run entry" everywhere: 125's `dispatch_state` and hold, 126's gather, and 127's `classify`. Each of those swaps a kind comparison for membership, with a test per consumer.
- **Pruning** (120, D6). A run id is held while any step in its batch entry's `batch_items` is not `done`. Item resume needs the run state to exist.
- **Order.** These land as this slice's first tasks, with contract tests and the stand-in Runner updated, before any batch code. This follows the precedent in 122 D3 and 125 D10.

### D11 — Upstream asks, recorded in the dependency register
Status: decided
- **S14, an item-resume claim marker** (D9). This one is non-blocking.
- **S15, an item filter on plan batches** (for example `-p items=131,132`). It is non-blocking. With it, D3's exact-match rule becomes "batch the driven subset", and held slices no longer turn batching off. Prediction would then be needed only as a check.
- Both are added to `user/notes/001-squadron-dependencies.amoeba.md` with this design.

### Technology Choices

- Standard library and pydantic v2, as in 125. There are no new dependencies.
- The stub `sq` gains a `slices-plan` mode, which writes a report and `reviews` from a fixture script, and an `--item` resume mode, which rewrites one record and exits with a scripted code. Report fixtures are captured from a real `slices-plan` run on squadron-ai 0.23.5, as the parser rule requires.

### Patterns and Conventions

- Each of these is defined once: `BATCH_PIPELINES`, the step name `slices`, `DesignDispatch`, `RUN_RESULT_KINDS`, the item outcome mapping, `FlagKind` and `ItemOutcome` (mirroring Squadron's sets, with an explicit unknown), the `batch_items` key, and the fault kinds `batch_selection_mismatch` and `batch_report_unknown`.
- `predicted_selection`, `batch_eligibility`, `fan_out`'s matching and the item outcome mapping are pure and table-tested.
- Expected external failures are answers (`ReportUnknown`, `Ineligible`, a failed resume), never exceptions.

## Implementation Details

### API Contracts

**Store** (`docs/store-contract.md`):

| Method or key | Change |
| --- | --- |
| `journal_issue` | `sq_run` accepts `batch_items`. New kinds `sq_batch_item` (store-written only) and `sq_item_resume`. |
| `record_batch_report(batch_entry_id, items, *, outcome, result)` | New. One transaction per batch (D10). |
| `RUN_RESULT_KINDS` | New export. |
| `unrouted_outcomes` | Unchanged. It now also lists item and item-resume entries. |

**Runner, internal:**

```python
@dataclass(frozen=True)
class LaunchBatch: initiative_id: str; pipeline: str; plan_index: int
                   items: tuple[BatchItem, ...]; checkout: Checkout
@dataclass(frozen=True)
class ResumeItem: node_id: str; run_id: str; item: str; decision: ItemDecision
                  continues: str; resolution: str
@dataclass(frozen=True)
class ObserveItem: node_id: str; run_id: str; item: str; continues: str; resolution: str
```

**Squadron commands issued:**

```
sq run slices-plan -p plan=<initiative index> --run-id <minted id>        (cwd: checkout)
sq run --resume <run id> --item <slice index> --decision retry|accept [--instructions TEXT]
```

## Integration Points

### Provides to Other Slices

- **140:** flagged items reach the routing table as `outcome: flagged`, with the flag kind in the block payload, ready to become an input (D7). Judge-eligible marks on those rules work as they do for any escalation.
- **131:** item entries carry verdicts like any run, so tier inference needs no batch-specific input.
- **Future Work (`tasks-plan`):** `BATCH_PIPELINES`, `fan_out` and `sq_item_resume` are generic over a single-`each` pipeline. A second entry needs its own selection predicate and item-to-step mapping.

### Consumes from Other Slices

- **122:** `launch()`, confirmation, polling, log files and tracked children.
- **123:** the plan read and reconcile, `cf.artifact_path`, CF status, and `STEP_MAP`.
- **124:** `current_steps` and the guard.
- **125:** `resolve_checkout`, the read-back comparison, review parsing and attribution, `dispatch_state`, the hold, and `dispatch_params`.
- **126:** reducers, the time bound function and the catch-all.
- **127:** `classify`, `ResolutionDecision`, the pre-poll pattern, and resolution acknowledgment.
- **128:** the per-project config and the pre-dispatch checks. If 128's merged design has a `slice_design` check that needs a pointer, D3 point 6 makes batches ineligible there, and the task breakdown says so.
- **129:** the write-up's proposals for this entry, and observed `P4` durations for the per-item bound.

## Success Criteria

### Functional Requirements

- **Eligibility:**
  - With `design_dispatch: batch`, and three undesigned slices of one initiative all driven to `slice_design`, one `sq_run` of `slices-plan` is journaled on the initiative node with all three in `batch_items`, and no `cf_write` is issued.
  - With one of the three held, or undriven, or with `per_phase`, no batch is issued, and the driven slices are dispatched as `P4`.
  - A single undesigned slice is dispatched as `P4`.
  - Slices resolving to two checkouts, or a checkout not on the target, get no batch.
- **In flight:** the covered steps are `IN_FLIGHT`, and no other slice dispatches in the checkout. A pointer moving between items raises no `pointer_moved`. A pointer moved to a slice outside `batch_items` raises it.
- **Fan-out:**
  - Passed, accepted, flagged and `not_run` records each produce an `sq_batch_item` entry on the right step, with the outcome mapping of D7.
  - A passed item with a PASS review advances under the shipped table. Every other outcome escalates, with the flag kind in the block payload.
  - Each item's review is recorded on its slice node, `runner_issued`, including every part of a split review. A later detection scan records nothing new.
  - A null `reviewFile` with a verdict, an unmatched path, or unsaved parts each give `review_unknown` on that item only.
  - A predicted item with no record is `no_record`, with its reason. A record for an unpredicted slice gets no item entry, review or decision, and raises one `batch_selection_mismatch`.
  - A missing report, `schemaVersion` 2, or a `runId` mismatch makes every item `unknown`, with `batch_report_unknown`.
- **Crash:** killed between the batch's finish and `record_batch_report`, the next tick fans out once. Each item has one entry and each verdict is recorded once.
- **Item resume:**
  - `retry` on a flagged item issues exactly the Squadron command of the API Contracts, in the checkout, with `--instructions` when given.
  - A changed record routes on its new outcome, whatever the exit code: a passed record routes `completed`, and a re-flagged one routes `flagged`. An exit with the record unchanged blocks with `resume_failed` on the next tick.
  - `accept` on a `step_failed` item is rejected `not_review_unresolved`, and nothing launches.
  - A record changed by hand before the act is observed, not resumed.
  - After a `SIGKILL` of the resident process mid-resume:
    - a changed record is finished;
    - an unchanged record escalates as `Unknown`, and `handled` then routes the record.
- **Paused batch:**
  - A batch that pauses (for example `usage_limit`) is not fanned out. The initiative node blocks on `SQ_CHECKPOINT`, and its items stay `IN_FLIGHT`.
  - `retry` on it issues `sq run --resume <run_id> --decision retry`. When the continued run ends, its entry fans out once, and the paused entry writes no items.
  - `accept` on it is rejected `decision_not_applicable`.
  - The checkout stays held until a poll shows the run is not `paused`.
- **Rerun** of a flagged item launches `P4` for that one slice.
- **Pruning** keeps a batch run while any item step is not done.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- Table-driven tests cover every row of D3, D6, D7, D8 and D9's observation table.
- Every consumer of `RUN_RESULT_KINDS` has a test using an item entry.
- A parser test loads a real captured `slices-plan` report.
- Contract documents and the CHANGELOG are updated. The operator guide gains "Batch design" (opt-in, eligibility, answering flagged items).

### Integration Requirements

- 100's contract suite passes with the new kinds and `record_batch_report`.
- 125's, 126's and 127's suites pass unchanged with per-phase dispatch, and 129's first-proof fixtures still route to their recorded routes.

### Verification Walkthrough

Steps 1–2 use the stub `sq` and `cf`. Step 3 runs one real `slices-plan` batch on a scratch copy, which costs one design and up to three reviews per slice.

1. **Tests:**
   ```bash
   uv run pytest tests/runner/batch tests/store/test_batch_report.py \
     tests/test_observer_sq_item_resume.py -v
   uv run pytest tests/runner/test_crash_recovery.py -k batch -v
   ```
   Expected: all pass. Tests are named for their rules, for example `test_held_slice_disables_batch`, `test_split_review_matched_by_path`, and `test_paused_item_refuses_retry`.

2. **Full gate and contract suite:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/contract -v
   ```

3. **A real batch, on a scratch copy of a project whose initiative has at least two undesigned slices.** The setup follows 129's operator guide (`docs/runner-guide.md`): scratch clone, `cf init`, `create-project`, `link-cf-project`, `watch-reviews`.
   ```bash
   # Opt in. The command and file come from 128's per-project config; the guide names them.
   amoeba inspect nodes --project scratch            # the initiative's node id
   amoeba submit intent --project scratch --by operator --node-id <initiative> \
       --body '{"intent": "drive", "until": "slice_design"}'
   ```
   Expected:
   - Within one tick, `amoeba inspect journal --project scratch` shows one `sq_run` on the initiative node, with pipeline `slices-plan` and every undesigned slice in `batch_items`, and no `cf_write`.
   - `sq runs list` shows the run under its `amoeba-…` id.
   - When it ends, the journal shows one `sq_batch_item` per slice, and `amoeba inspect routing-decisions --project scratch` shows one decision for each.
   - `amoeba inspect verdicts` shows each design review on its own slice node.
   - Compare `jq '.items[] | {index, outcome, flagKind}' ~/.config/squadron/runs/<run id>.slices.report.json` with `amoeba inspect blocked --project scratch`. Every flagged item is blocked, with its flag kind in the payload, and nothing else is.
   - If an item is flagged `review_unresolved`, answer it:
     ```bash
     amoeba submit resolution --project scratch --by operator --blocked-state-id <id> \
         --detail "one more round" --decision retry \
         --instructions "Address the open findings only."
     ```
     The journal shows an `sq_item_resume` on that step, and the report's record for that item gains `decision: retry` and a `resumedAt`. The entry then resolves, and the item is routed again.
   - Hold one slice and drive the initiative again on a second scratch copy. No batch is issued, and the driven slices get `P4` runs.

   If no item is flagged, the resume step is shown by the stub test in step 1 instead. The walkthrough is refined in Phase 6.

## Risk Assessment

### Technical Risks

- **Selection drift.** CF can change between the plan read and Squadron's own selection, so a batch can design a slice the PM did not drive.
- **Unobservable item resumes after a restart.** Squadron publishes no in-progress sign for an item resume.
- **External pruning.** `sq runs prune` run by hand (its defaults include completed runs) removes a batch that still has open items. A later item resume is then refused.

### Mitigation Strategies

- D3 issues a batch only when prediction and drive agree. D6 records any difference and raises `batch_selection_mismatch`, and D11's S15 removes the prediction.
- D9 escalates an unobservable resume as `Unknown` instead of guessing. `handled` recovers it, and S14 removes the case.
- A refused resume blocks with `resume_failed`, and `rerun` still designs the slice with `P4`. The operator guide says not to prune batch runs by hand while their items are open.

## Implementation Notes

### Development Approach

Relative effort: 4/5, as the plan entry now says. Each step leaves the suite green:

1. Store changes (D10): the kinds, `batch_items`, `record_batch_report`, `RUN_RESULT_KINDS` with every consumer switched, and pruning.
2. The report model and loader (D5), with captured fixtures and the stub `sq` `slices-plan` mode.
3. `fan_out` and batch ingestion (D6, D7), with the routing inputs and the crash test.
4. Selection, eligibility, `BatchPlanner`, `LaunchBatch` and the checkout read (D2, D3, D4).
5. Item resolutions and resume (D8, D9), with the stub `--item` mode and the recovery observer.
6. The per-item time bound, the operator guide section, the contract documents, the dependency register (D11), and the CHANGELOG.

**If the slice overruns:** steps 1–4 are a complete, safe slice. Without step 5, a flagged item's only decisions are `rerun` (a `P4`) and `stop`, which 127 already supports through `ended_run`. Step 5 can move to a follow-on entry through a plan edit.

### Special Considerations

- **Slice plan Future Work** gains "Batch `tasks` with `tasks-plan`" (D1), with this design.
- **Arch edits, made with this design** (20261021). They record where batches differ from the arch's dispatch rules (D2, D4):
  - "Where each value lives" lists `design_dispatch` under per-project config, beside the merge policy.
  - The pointer rule says a batch writes no pointer, because Squadron's `each` step sets it for every item.
  - The pointer-move rule says that during a batch, a move among the batch's items is expected, and any other move still escalates.
- **Operator guide.** The "Batch design" section says that `slices-plan`'s params cannot be probed at start. A launch exit 2 from an upstream param change therefore stops the resident process on the first batch, by 122 D6's rule, and the fix is to turn batching off for that project.
- **Spend.** A batch is a paid, unattended run across a plan. It needs the project's opt-in and a PM drive, and pause stops new batches at once. Squadron's `max_cost_usd` stops a batch that crosses it, and its items then fan out as `not_reached`.
- **Security.** Report files are parsed as data, and `reason` and `--instructions` text are never interpreted. The instructions are one argv element, never passed through a shell.
