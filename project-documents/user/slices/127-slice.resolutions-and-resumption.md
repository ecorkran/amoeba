---
docType: slice-design
slice: resolutions-and-resumption
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 125
- 126
interfaces:
- 128
- 129
- 160
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
turns: 48
promptTokens: 6280494
cachedTokens: 6063484
cacheWriteTokens: 216928
completionTokens: 68731
durationSeconds: 765.8
costUsd: 5.065592
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Resolutions and Resumption

## Overview

This slice turns a PM's answer to a blocked step into the Runner's next action, from a closed set.

- **A resolution carries a decision.** The inbox `resolution` kind gains two optional fields, `decision` and `instructions`. The inbox still fills the slot and returns the node to `runnable`, as it does now. It also flags the resolution as awaiting the Runner.
- **The Runner acknowledges every flagged resolution.** A new stage runs at the start of each project's tick, after intents. It classifies the blocked step from its journal, checks the decision against the set allowed there, and acknowledges it `applied` or `rejected` with a reason. The acknowledgment and its effect are one transaction. A rejection blocks the node again, so the PM is told.
- **The decisions:**
  - **Paused run:** `retry` and `accept` resume it with `sq run --resume <id> --decision …`, passing `--instructions` through as data. `accept` is allowed only when the pause is at a loop. `handled` journals an observation of the run, so whatever the run now shows is ingested and routed. `stop` parks the node.
  - **Escalated completed outcome:** `accept` marks the step done in the store only. `rerun` dispatches a fresh run. `stop` parks the node.
  - **Any other blocked pipeline step:** `rerun` or `stop`.
- **Resumes are confirmed by state, not by a line.** Squadron prints no `run_id=` line on a resume, and the run stays `paused` until the resumed process claims it. A resume is confirmed when a poll shows the run has left the pause it was resumed from. A resume whose run is missing launches nothing and blocks the node.

## Value

User value. A PM decision on a stuck node is carried out without the PM running Squadron by hand:

- A paused run is retried or accepted from `amoeba submit resolution`, with the PM's instructions passed to Squadron unchanged. The Runner then observes the resumed run, ingests it and routes it, like any run.
- An escalated outcome the PM is satisfied with advances, and its successor is dispatched on the next tick.
- A resolution the Runner cannot carry out is refused with a code and the decisions that are allowed. It is never ignored and never guessed at.
- This is the vocabulary that 160 and the notification bridge submit.

## Technical Scope

**Included**

- `amoeba.runner.resolutions`, a new subpackage:
  - the vocabularies: decisions, situations, rejection codes and continuations;
  - `classify`, the pure classification of a blocked step;
  - `judge_resolution`, the pure check of a decision against its situation, which returns an acknowledgment and its effect;
  - the resolution stage.
- The two continuation actions: `ResumeRun` (retry and accept) and `ObserveRun` (handled). The planner that emits them, and Act for both.
- Resume confirmation and resume failures in 122's observe (D6).
- 125's `dispatch_state` reads the step's latest applied resolution (D5).
- Contract changes to 100, landed first (D9):
  - migration `012`: the decision, instructions and Runner-acknowledgment columns on `blocked_states`;
  - the `resolution` payload fields;
  - `pending_resolutions`, `acknowledge_resolution` and `blocked_state`;
  - the recovery observer's rules for continuation entries;
  - the optional `resolution` key on `cf_write` (D5).
- Routing input changes in 126's vocabulary: the outcome value `resume_failed` and the input `review_accepted`. One rule is added to the shipped table (D8).
- CLI: `amoeba submit resolution` gains `--decision` and `--instructions` through the flag rule. `amoeba inspect blocked` gains a `blocked_state_id` column.
- Contract text in `docs/inbox-contract.md`, `docs/store-contract.md`, `docs/process-contract.md` and `docs/substrate-guide.md`.

**Excluded**

- **The store and CF gate disagreement after an accept.** It needs a CF gate read, which is 128's. This slice makes an accepted outcome identifiable, and 128 compares it with CF's gate (D7).
- **Batch item resumes (`--item`)** belong to 130.
- **Pruning's held set.** Pruning holds runs by node `sq.run_id`, which the Runner never sets, so a run paused under the Runner can be pruned while its resolution is pending. That is a defect in the existing 100/125 integration, tracked as issue #14. Until it is fixed, a pruned run surfaces here as `run_missing` (D6), which blocks the node and launches nothing. Issue #14 must be fixed before the Runner is pointed at a real project (129).
- **`amoeba inspect resolutions`,** a listing of resolved blocks. Submitters read the outcome through `blocked_state(id)`, and `inspect blocked` gains `blocked_state_id`. Deferred to issue #16, for 128's or 129's use.
- **Resuming a failed run.** Squadron can resume a failed run, but a failed run releases its checkout (125, D4), so another slice may have changed the branch since. Listed under Future Work.
- **Judge results (140).** They will land through the same resolution slot later.
- **Killing a run**, under any condition.

## Dependencies

### Prerequisites

- **125, merged:** the `sq_run` result (`outcome`, `outcome_document`, `verdict_ids`, `review_fault`), `dispatch_state`, the checkout hold, the blocks ingestion writes, `LaunchRun` and 122's launch, `RunCheckpoint` and `CheckpointKind`. The rule that a paused run is recognized by its entry's recorded outcome, not by its block kind.
- **126, merged:** the route stage, `routing_decision_for_entry`, the input vocabulary and reducer to extend, the shipped table, and time bounds that read `pipeline` from every `sq_run` entry.
- **121, 122, 123 and 124, merged:** `StatusEffect` and `BlockEffect`, the tick skeleton and its fault boundary, the launch logs and `LaunchTracker`, `STEP_MAP` and `Executor`, the current-step guard.
- **squadron-ai 0.23.5 or later**, by shape: `sq run --resume <id> --decision accept|retry [--instructions TEXT]` (S12) and `checkpoint.is_loop` in `sq runs wait --json` (S10).

### Interfaces Required

**Squadron** (observed in source on 20261020, `cli/commands/run.py`, `pipeline/state.py`, `pipeline/run_outcome.py`):

- A plain resume reloads the run's recorded pipeline and params. A pipeline name and `-p` are accepted and ignored, and `--run-id` with `--resume` exits 1. So the Runner passes neither.
- `--decision` takes `retry` or `accept`. `retry` is the plain resume. `accept` is refused with exit 2 unless the paused step's type is `loop`, and `checkpoint.is_loop` uses the same test.
- `--instructions` is prepended to every dispatch of that invocation. It is not persisted, so a later resume does not inherit it.
- **A resume prints no `run_id=` line.** The run's status stays `paused` until the resumed process claims it, after validation, the project lock and the CF preflight. A failure before the claim leaves the state untouched. The only signal is the process's exit code and output.
- After the claim the outcome is `timed_out` (still running) while it runs. A new pause writes a new `checkpoint.paused_at`. `reviews` accumulates across resumes, in write order. An accepted loop runs no round and writes no review.
- Exit codes: a run that does not exist exits 1. `accept` at a non-loop step, a held project lock, and a bad flag value exit 2. Two simultaneous resumes of one run are not prevented by Squadron, except by the per-checkout lock of pipelines that write.
- A non-TTY resume cannot get past an interactive checkpoint. It takes exit and pauses again (pinned, Squadron ce0ddf55).

**Store:** `blocked_state_for(node, include_resolved=True)`, `journal_entries(project, node_id=…)`, `journal_issue`, `journal_resolve`, `block`, `routing_decision_for_entry`, and 121's `StatusEffect` and `BlockEffect`.

## Architecture

### Component Structure

```
amoeba/runner/resolutions/          NEW
  vocabulary.py   ResolutionDecision, Situation, ResolutionRejection, Continuation,
                  ALLOWED (situation → decisions), payload keys and reasons
  classify.py     classify(step, executor, entries, decisions) → Situation (pure)
  judge.py        judge_resolution(blocked, situation, checkpoint) → Acknowledgment (pure)
  stage.py        apply_pending_resolutions(store, project) — one transaction each
  planner.py      ContinuationPlanner: ResumeRun | ObserveRun per current RESUME/REOBSERVE step
  act.py          resume and observe acts: journal, pre-poll, launch or not
amoeba/runner/
  decide.py       CHANGED  Action += ResumeRun, ObserveRun; view carries the latest
                           applied resolution per current pipeline step
  tick.py         CHANGED  resolution stage after intents
  observe.py      CHANGED  resume confirmation and failures (D6)
  launch.py       CHANGED  resume argv; logs and LaunchTracker reused
  faults.py       CHANGED  ResumeFailure
  tenant.py       CHANGED  production planners += ContinuationPlanner()
amoeba/runner/dispatch/state.py     CHANGED  RESUME, REOBSERVE; applied resolutions (D5)
amoeba/runner/routing/inputs.py, evidence.py, tables/default.yaml   CHANGED  (D8)
amoeba/process/observers/sq_run_id.py   CHANGED  continuation entries (D9)
amoeba/store/
  schema/012_resolution_decisions.sql   NEW
  _block_writer.py / blocking.py / inbox.py / models.py   CHANGED
amoeba/inbox/   CHANGED  resolution payload gains decision and instructions
amoeba/inspection/   CHANGED  resolutions listing; blocked gains blocked_state_id
```

### Data Flow

One project's tick, with this slice's changes marked:

```
apply intents (124)
resolutions  for blocked in pending_resolutions(project):     ── NEW, store-only
                 situation ← classify(...)                       pure
                 ack       ← judge_resolution(...)               pure
                 acknowledge_resolution(ack.outcome, reason, effect)   one transaction
observe      in-flight runs, including continuation entries (D6)    ── CHANGED
record → view → route → decide (planners + ContinuationPlanner) → act → close
```

The resolution stage runs before Observe and before the view is built, so no planner sees a resolved node before its resolution is checked. It starts no subprocess, so it needs no `TickBudget` check, as with 124's intent stage.

**A paused run retried, end to end:**

```
tick n    run R paused → step S blocked_on_sq_checkpoint; entry E1 resolved, routed (escalate)
(PM)      amoeba submit resolution --blocked-state-id B --decision retry --instructions "…"
          inbox: slot filled, S runnable, B awaits the Runner
tick n+1  resolutions: classify(S) = paused_run; retry allowed (loop_exhausted)
                       acknowledge_resolution(B, applied)
          view:    S current; dispatch_state = RESUME; checkout held by S only
          decide:  ContinuationPlanner → ResumeRun(S, R, retry, B)
          act:     journal E2 sq_run {run_id R, continuation retry, continues E1, resolution B, …}
                   poll R → paused at E1's pause → Popen sq run --resume R --decision retry
                       --instructions "…"   (detached, logs by E2's id)
tick …    observe: poll R → timed_out (claimed, running) → confirmed
tick m    observe: completed → record (125) → route (126) → advance or escalate
```

### State Management

- **Durable, in the store:**
  - The decision, instructions and Runner acknowledgment on each blocked state (D2). The `awaits_runner` flag marks the resolutions still to be acknowledged.
  - Continuation entries in the journal. A continuation is an `sq_run` entry on the same run id as the entry it continues (D4).
  - A step's next action is derived from its journal entries and its latest applied resolution. Nothing else is held (D5).
- **In memory:** 122's `LaunchTracker` holds each resume child for reaping and for confirmation, as it does for launches. After a restart, confirmation falls back to the grace period (D6).

## Technical Decisions

### D1 — Decisions ride on the existing `resolution` kind, and the Runner answers each one
Status: decided
- **The payload** gains `decision` (optional text) and `instructions` (optional text). The inbox checks only shape: each one, when present, is non-blank after trimming, because Squadron strips instructions and blank text would have no effect. The decision vocabulary is the Runner's, so the inbox does not validate it. This follows 124, D3: Runner vocabulary is not imported into the inbox, and the answer comes from one place.
- **The inbox's effect is unchanged.** It fills the slot, returns the node to `runnable` and records the submission `applied`. It also stores both fields and sets `awaits_runner` in the same transaction. Only the inbox path sets the flag. The Runner's own `resolve()` calls, such as 123's completion of a human step, do not set it.
- **The Runner answers on the blocked state**, not the submission. The submission record is the inbox's answer and is written once. The Runner's answer comes later and from a different party, which is the reason 121 (D2) gave for putting intent outcomes on the message. A submitter reads `submission(id)`, then `blocked_state(blocked_state_id)` for `runner_outcome`, `runner_code` and `runner_reason`. A consumer branches on `runner_code`, never on the reason text.
- **Why the node may be runnable before the Runner checks.** The inbox ticks before the Runner, and the resolution stage runs first in the Runner's project tick, before Observe and before the view. So no planner, reconcile step or route sees the node until its resolution has been acknowledged. The flag is durable, so a crash before the stage repeats nothing and loses nothing.
- Rejected:
  - **A `resolve` intent kind.** It would bypass 103's resolution slot, which the plan names, and leave two ways to answer one block.
  - **Validating context in the inbox** (for example, "accept needs a loop"). That needs the journal and Runner vocabulary inside the inbox, which 124 rejected for the same reason.
  - **Holding the node blocked until the Runner accepts.** That changes 100's resolution semantics for every existing submitter.

### D2 — Situations and the allowed decisions
Status: decided
- `ResolutionDecision` is a `StrEnum` with `retry`, `accept`, `handled`, `rerun` and `stop`, defined once.
- `classify` is pure. It reads the step's executor and its journal entries, newest first, plus the routing decision on the latest `sq_run` entry:

  | Situation | When | Allowed |
  | --- | --- | --- |
  | `no_decision` | the node is not a step, or its executor is human | no decision |
  | `paused_run` | the latest entry is an `sq_run` whose recorded `outcome` is `paused` | `retry`, `accept`, `handled`, `stop` |
  | `completed_outcome` | the latest entry is an `sq_run` with outcome `completed` and no `resume_failure` | `accept`, `rerun`, `stop` |
  | `ended_run` | the latest entry is any other resolved `sq_run` whose recorded outcome is not `paused`: failed, orphaned, vanished, a launch failure, a `run_missing` resume, or a recovery resolution | `rerun`, `stop` |
  | `before_run` | no entry, or the latest entry is a `cf_write` | `rerun`, `stop` |
  | `unresolvable` | the latest entry is unresolved, or the latest `sq_run` entry still has `awaits_routing` | none: rejected |

  Rows are tested in this order: `unresolvable`, `no_decision`, `paused_run`, `completed_outcome`, `ended_run`, `before_run`. The first match wins, so an unrouted pause is never `paused_run`, and a failed resume, whose recorded outcome stays `paused` (D6), is always `paused_run` and is never offered `rerun`. "Paused" is read from the entry's recorded outcome, never the block kind (125, Provides). So a paused run whose step is blocked on `HUMAN`, after an unknown review, a failed resume or a rejected resolution, is still `paused_run`.
- **The checks,** in order. The first failure is the rejection:
  0. `unresolvable` is rejected with that code, whatever the decision. The detail names the cause: an unresolved latest entry, or an unrouted outcome, which arises only when a route stage faulted after ingestion.
  1. A decision outside `ResolutionDecision` is `unknown_decision`.
  2. `no_decision` with a decision present is `decision_not_applicable`. Any other situation with no decision is `decision_required`. A bare resolution of a pipeline step would otherwise mean whatever the journal happened to imply.
  3. A decision outside the situation's set is `decision_not_applicable`.
  4. `accept` on `paused_run` requires `checkpoint.is_loop` to be `true`. `false` or null is `not_at_loop`. This is the arch's rule: accept is offered only when the outcome document says the pause is at a loop.
  5. `retry` and `accept` require the checkpoint's `kind` and `paused_at` to be present. Without them the resume cannot be confirmed (D6), so either one null is `checkpoint_unknown`.
  6. `retry` at an `interactive_checkpoint` is `interactive_checkpoint`. A non-TTY resume takes exit there and pauses again, so the Runner cannot carry it out. The PM resumes it interactively, then submits `handled`.
  7. `instructions` with any decision other than `retry` or `accept` is `instructions_not_applicable`. A fresh run takes no instructions (arch, "The routing engine").
- The checkpoint is the one in the latest `sq_run` entry's `outcome_document`, read with 125's model and `CheckpointKind` parser. A document or checkpoint that does not parse counts as null, so `retry` and `accept` are rejected `checkpoint_unknown` and the PM is told. Unknown escalates, and never faults the project.
- A blocked step whose latest entry is unresolved should not exist, because a node with a run in flight is never blocked (122, D8). If one does, `classify` returns `unresolvable`, and every decision is rejected. The node blocks again, and the resolution is acknowledged rather than retried every tick.
- **So expected data never stops the tick.** Every problem in the resolution's inputs is a rejection, which blocks only its own node. Observe and ingestion still run for the project's other nodes in the same tick.

### D3 — Acknowledgment and effect are one transaction
Status: decided
- `judge_resolution` returns `Acknowledgment(outcome, reason, effect)`. `apply_pending_resolutions` writes each one with `acknowledge_resolution`, oldest resolution first:

  | Decision and situation | Outcome | Effect in the same transaction |
  | --- | --- | --- |
  | any rejection | `rejected`, `runner_code` the `ResolutionRejection` value, `runner_reason` the detail | `BlockEffect` on `HUMAN`, context `resolution rejected: <code>`, payload `{reason: resolution_rejected, code, detail, rejected_blocked_state_id, allowed}` |
  | no decision, `no_decision` | `applied` | none |
  | `accept`, `completed_outcome` | `applied` | `StatusEffect(done)` |
  | `stop` | `applied` | `BlockEffect` on `HUMAN`, context `stopped by <resolved_by>`, payload `{reason: stopped, stopped_blocked_state_id}` |
  | `retry`, `accept` (paused), `handled`, `rerun` | `applied` | none. The planner acts on it (D5). |

- **A rejection blocks again** so the PM is told. A paused run is blocked on `HUMAN` rather than `SQ_CHECKPOINT`, because a checkpoint block posts no message. This is 125's rule for an unknown review on a pause. `allowed` lists the situation's decisions, so the PM or the bridge can answer without reading the journal.
- **Stop parks the node as a block.** The arch says "the node stops being driven". A blocked node is never current, so nothing is issued for it. To start again, the PM resolves the stop block with any decision allowed in its situation, which is unchanged. Rejected alternatives:
  - **Writing an `exclude` desired state.** Desired states are set by intents, and their provenance is an intent message (121, D8). After a later drive, the step would also be runnable with no decision in its journal.
  - **A new node status.** That would be a store vocabulary change for one resolution.

  **This departs from the arch's wording**, and the arch is edited to say how stop is held.
- **Accept of a completed outcome** advances in the store only. Nothing in Amoeba edits CF or review frontmatter. `StatusEffect` follows 121's rules: the step has no unresolved entry, so done is allowed. The successor is decided on the next tick, as with 126's advance.
- **Store failures** re-raise, and the process exits (122, D8). The resolution is still flagged, so it is acknowledged after restart. Any other exception is a code defect, not a data problem, because D2 turns every input problem into a rejection. It reaches 122's catch as a project-scoped `unexpected_fault`, and the rest of that project's tick does not run. This is 124's D9 pattern. A tick that acknowledges anything counts as a store write.

### D4 — Continuation entries: resume and observe share one journal shape
Status: decided
- `retry`, `accept` and `handled` all continue a run that already exists. Each one is an `sq_run` entry on the step, with:
  - the continued entry's `pipeline`, `params`, `run_id` and `checkout`. The required keys are unchanged, and 126's time bound reads `pipeline` (126, D7).
  - `continuation`: `retry`, `accept` or `observe`, from `Continuation`, a `StrEnum` defined once.
  - `continues`: the id of the entry whose run it continues.
  - `resolution`: the blocked state id whose decision it carries.

  The instructions are not copied into the journal. They live in the resolution slot, and Act reads them from there.
- **Act, in order.** Nothing is journaled until the pre-poll has answered and the budget allows the launch, so a routine cut-off never leaves an entry with no launch behind it:
  1. **Check the budget, then poll once** (`poll_run`, under `tick_call_timeout_seconds`). This is a one-off act-time read, like 125's reissue poll, so it is not paced by `run_poll_interval_seconds`. That interval paces only the confirmation polls (D6).
     - **The budget is spent:** nothing is called or written. The step stays `RESUME` or `REOBSERVE`, and the action is decided again next tick, as 122 does for any unissued action.
     - **The poll fails or times out** (`PollFailure`): nothing is written. It is recorded as 122's project-scoped `run_observation_failed`, and the step stays `RESUME` or `REOBSERVE` for the next tick.
     - **`not_found`:** the run is missing. The entry is journaled and resolved `failed` at once, with `resume_failure: run_missing`, and the step blocks on `HUMAN`. Nothing is launched and nothing is relaunched, as the process contract requires.
     - **For `retry` and `accept`,** the run must still be paused with the `paused_at` the continued entry recorded. Anything else means the run has left the pause the PM decided on, for example because the PM resumed it by hand. The entry is journaled as an observation, with `resume_skipped: run_not_at_pause`, and nothing is launched. A decision is carried out only on the pause it was made for.
     - **For `observe`,** the entry is journaled and confirmed. Its next poll is its outcome, whatever it shows, including the same pause.
  2. **Check the budget again, then journal the entry.** The run id is the continued one, never minted. If the budget is spent, nothing is written and the action waits for the next tick. This check is the launch's check: only the journal write, a store call, runs between it and `Popen`.
  3. **Launch** with 122's detached launch: argv `[SQ_EXECUTABLE, "run", "--resume", <run_id>, "--decision", <retry|accept>]`, plus `"--instructions", <text>` when the resolution has instructions. It runs in the checkout, with stdin from `/dev/null` and logs named by the entry's id. The text is one argv element, never passed through a shell.
- **Why `handled` journals an entry.** The arch says reads are not journaled. This entry is not there to recover a side effect. It owns the run while it is observed: detection defers only while a review-producing entry is unresolved (evidence contract D5), and ingestion records a review only through an unresolved entry (`record_runner_report`). The arch is edited to name this exception.
- **One continuation at a time per step.** Squadron does not stop two simultaneous resumes of one run. The Runner never issues two, because a step with an unresolved entry is `IN_FLIGHT`.
- **Ingestion is 125's, unchanged.** The last entry of `reviews` is recorded. After an accept that wrote no new review, that is the review already recorded for the pause. `record_runner_report` already treats a known verdict id and ledger key as recorded, so nothing is written twice, and the entry's `verdict_ids` name it again for routing (D8).
- **Every continuation's outcome is routed by 126,** and counts one attempt, as every routed decision does (126, D5).

### D5 — The next action comes from the journal and the latest applied resolution
Status: decided
- 125's `dispatch_state(entries)` becomes `dispatch_state(entries, resolution)`. `resolution` is the step's latest acknowledged-`applied` resolution with a decision, read with `blocked_state_for(step, include_resolved=True)`, which is one read per current pipeline step.
- **If no journal entry on the step names that resolution** in its `resolution` key, the resolution has not been carried out yet, and it decides. Continuation entries carry the key (D4), and so does the pointer write a `rerun` issues (D9). This is a reference, not a time comparison, so clock resolution or a wall-clock step cannot change the answer:

  | Decision | State | Planner does |
  | --- | --- | --- |
  | `retry`, `accept` | `RESUME` | `ResumeRun` |
  | `handled` | `REOBSERVE` | `ObserveRun` |
  | `rerun` | `NEEDS_POINTER` | 125's pointer write, carrying `resolution`, then a fresh launch |

  Otherwise 125's rules apply as before. `accept` of a completed outcome and `stop` never reach the planner, because their effect leaves the step done or blocked.
- **`rerun` needs the event** only where 125's state would be something else: a `not_applied` entry would be `REISSUE`, and 125's log check would block it again. Everywhere else `rerun` agrees with 125's rules, because a routed `sq_run` is already `NEEDS_POINTER`.
- **This is crash-safe without new state.** The acknowledgment is durable. Once the continuation entry or the rerun's pointer write is journaled, it names the resolution, and 125's rules take over: `IN_FLIGHT` for an unresolved entry. A crash between acknowledgment and journaling leaves `RESUME`, and the next tick issues it.
- **The checkout hold** (125, D4) still counts a paused run's checkout as held. `ContinuationPlanner` may act in a checkout held only by the step itself, because the paused run it continues is that step's own. Any other holder makes it wait, like any launch.
- **Governance.** `ResumeRun` and `ObserveRun` are actions on current steps, so the current-step guard applies (124, D7). A held or undriven step's resolution is acknowledged, and its continuation waits until the step is current.
- `ContinuationPlanner` is pure and joins the production tuple after `DispatchPlanner`. Each step is in one dispatch state, so the two planners never act on the same step.

### D6 — Resume confirmation and resume failures
Status: decided
- **Confirmed** when a poll shows the run has left the pause it was resumed from: any outcome other than `paused`, or `paused` with a `checkpoint.paused_at` different from the one the continued entry recorded. A new pause has a new `paused_at`. `timed_out` (claimed and running) confirms it.
- **While unconfirmed,** the run is polled on `run_poll_interval_seconds`, because there is no line to wait for. A poll that still shows the old pause means still resuming.
- **Failed while unconfirmed**, decided on observed state and exit code, never on message text:

  | `ResumeFailure` | When |
  | --- | --- |
  | `refused` | The tracked child exited 2, and a poll still shows the old pause. That covers accept at a non-loop step, a held project lock and a missing flag. The arch says an exit 2 from a resume escalates its node. It does not stop the process, unlike 122's exit 2 on a launch. |
  | `exited_before_claim` | The tracked child exited with any other code, and a poll still shows the old pause. |
  | `no_claim_within_grace` | `launch_grace_seconds` passed since `issued_at`, and a poll still shows the old pause. After a restart, no child is tracked, so this is the only rule. |
  | `spawn_error` | `Popen` or a log file raised `OSError` (122, D4). |
  | `run_missing` | A poll returns `not_found`, before or after the launch. |

  On failure, the step blocks on `HUMAN` with `{reason: resume_failed, resume_failure, run_id, exit_code, stderr_tail}`. The tail is the last 4 KiB of the stderr log, as in 122. The entry resolves `failed`, with result `{run_id, outcome, outcome_document, resume_failure}`.
- **The result keeps the run's real outcome.** For every failure except `run_missing`, `outcome` is `paused` and `outcome_document` is the last poll. The run is still paused, with its branch checked out. So 125's checkout hold still holds, and `classify` still reads `paused_run`. The PM can retry again, or use `handled` if a late resume did start. A `run_missing` result has outcome `not_found`, so the hold is released and the situation is `ended_run`.
- **A confirmed continuation** is observed and finished by 122's rules and ingested by 125's.

### D7 — Accepting an outcome CF's gate still fails is detected by 128
Status: decided
- The plan asks that an accepted outcome CF's gate still fails be recorded on the node. CF computes its gate from review frontmatter against per-project thresholds (`workflow.review_threshold` and related keys). Amoeba cannot compute it, and must read it. `cf status --json` reports the gate only for the worktree's active slice, and by the time of an accept, the checkout is free and its pointer may be on another slice.
- **So the comparison belongs to the one gate reader, 128.** It reads `activeSlice.status` and `gateInfo` at `POINTED`, before the successor's launch, when CF points at this slice (125, D3). When the gate for the accepted phase has failed and the store holds an accept for that step, 128 records the disagreement as a check record on the slice node and routes as its design decides.
- **What this slice provides** is the identifiable accept: an applied resolution with decision `accept` on a `completed_outcome` step, read with `blocked_state(id)`, and the `verdict_ids` of the step's latest `sq_run` entry, which is the entry it accepted.
- **This departs from plan entry 8**, whose last criterion moves to entry 9 (128) with this design. Entry 9 now carries it as a success criterion required before 128 merges, and lists reading 127's identifiable accept as the store side of the comparison. The move is a dated plan change (20261020) in the plan's Notes, tracked as issue #15.
- **Until 128 lands,** an accept advances the step and the successor is dispatched with no disagreement recorded. The first sign is a Squadron refusal at the successor's run, which escalates as any failed run does. 128 follows this slice directly and lands before 129, so no proof runs in that state. Until then, the Runner is driven only on scratch copies (125, Risk Assessment).

### D8 — Routing inputs for continuations
Status: decided
- 126's vocabulary grows by code (126, D3):
  - **`outcome` gains `resume_failed`.** It is reduced from `resume_failure` in the entry result, which takes precedence over `outcome`, as `launch_failure` does. Advance and rerun rules must name `outcome: completed` (126, D4), so a failed resume can only escalate.
  - **`review_accepted`**, a new input with `true`, `false` and `none`. It is `none` unless the entry's `continuation` is `accept`. It is `true` when the entry's `verdict_ids` equal those of the entry it continues, which means the run's final review is the one the PM accepted. Otherwise it is `false`, meaning a later loop wrote a newer review, and that one is routed on its own.
- **Why an input and not a code path.** Without it, an accepted CONCERNS loop would complete, and the table would route its CONCERNS again, undoing the PM's decision. Advancing on it in code would choose a route outside the table. The table decides instead.
- **The shipped table** gains one rule, after `advance-on-stated-pass`:

  ```yaml
  - id: advance-on-accepted-review
    when: {outcome: completed, review_accepted: true}
    route: advance
  ```

- `gather` reads the continued entry's result, which is one store read, so `reduce` stays pure.

### D9 — Contract changes to 100, landed before Runner code
Status: decided
- **Migration `012_resolution_decisions.sql`** (125's is `011`, and 126 adds none). It adds these columns to `blocked_states`:
  - `resolution_decision TEXT`, `resolution_instructions TEXT`;
  - `awaits_runner INTEGER`, with a partial index `WHERE awaits_runner = 1`;
  - `runner_outcome TEXT`, `runner_code TEXT`, `runner_reason TEXT`. `runner_code` holds the rejection code on its own, so no consumer parses it out of `runner_reason`, which is display text.

  Rows before `012` read null, which means they are not awaiting the Runner. The migration backfills nothing.
- **Models.** `Resolution` gains `decision` and `instructions`. `BlockedState` gains `awaits_runner`, `runner_outcome` (`ResolutionOutcome`: `applied` or `rejected`, a store `StrEnum`), `runner_code` and `runner_reason`. The store holds `runner_code` as text, as it holds `fault_kind`; its vocabulary is the Runner's.
- **Store methods:**
  - `pending_resolutions(project_id) -> list[BlockedState]`: flagged rows, oldest resolution first, served by the partial index.
  - `acknowledge_resolution(blocked_state_id, *, outcome, code=None, reason=None, effect=None)`: in one transaction, records the outcome, clears the flag and applies the effect, a `StatusEffect` or `BlockEffect` from 121 written through the same writers. `rejected` requires a code and a reason, and `applied` takes no code. A row that is not resolved or not flagged raises `InvalidTransitionError`. An effect failure writes nothing.
  - `blocked_state(blocked_state_id) -> BlockedState | None`, for submitters. It works through a read-only handle.
- **Inbox:** `RESOLUTION_DECISION` and `RESOLUTION_INSTRUCTIONS` join the payload keys. `_write_resolution` stores them, and the inbox apply sets the flag.
- **Recovery observer** (`observers/sq_run_id.py`), for entries with `continuation`:
  - **The claimed-id guard** ignores earlier entries on the same node. A continuation shares its run id with the entry it continues by design. An id claimed on another node is still `Unknown`.
  - **No run state** is `Unknown` with reason `resume_run_missing`, never `NotApplied`. `NotApplied` would make 125's `REISSUE` launch a fresh run under the old id, which the process contract forbids for a resume. `Unknown` escalates the node, and the entry is never reissued.
  - A state that exists is `InFlight`, as 122's D3 says, and the Runner's confirmation rules finish it.
- **`cf_write`** gains an optional `resolution` key, the blocked state id a rerun's pointer write carries out (D5). It is not required, and the observer ignores it.
- **Order.** These land as the slice's first code tasks, with their contract tests, before any Runner code. This follows 125's D10.

### Technology Choices

- No new dependencies. Standard library `subprocess` through 122's injected runner, pydantic v2 for the payload and the outcome document, and raw `sqlite3` for the migration.
- The automated tests never run the real `sq`. The stub `sq` gains `run --resume` with a configurable claim delay, exit code and outcome. With them it can pause again, complete, refuse with exit 2, exit before the claim, or never claim.

### Patterns and Conventions

- Defined once: `ResolutionDecision`, `Situation`, `ALLOWED`, `ResolutionRejection`, `Continuation`, `ResumeFailure`, `ResolutionOutcome`, the journal keys `continuation`, `continues` and `resolution`, the result keys `resume_failure` and `resume_skipped`, the payload reasons `resolution_rejected`, `stopped` and `resume_failed`, and the `--resume`, `--decision` and `--instructions` flag names.
- `classify`, `judge_resolution`, `dispatch_state`, `ContinuationPlanner` and the confirmation rule are pure, and table-tested.
- Rejections are answers (`Acknowledgment`), never exceptions. Expected resume failures are answers too. Unexpected exceptions reach 122's one catch.
- Modules stay under about 300 lines, and functions under about 50.

## Implementation Details

### Database / Storage Schema

```sql
ALTER TABLE blocked_states ADD COLUMN resolution_decision TEXT;
ALTER TABLE blocked_states ADD COLUMN resolution_instructions TEXT;
ALTER TABLE blocked_states ADD COLUMN awaits_runner INTEGER;
ALTER TABLE blocked_states ADD COLUMN runner_outcome TEXT;
ALTER TABLE blocked_states ADD COLUMN runner_code TEXT;
ALTER TABLE blocked_states ADD COLUMN runner_reason TEXT;
CREATE INDEX idx_blocked_states_awaits_runner
    ON blocked_states (resolved_at) WHERE awaits_runner = 1;
```

It applies to a populated v11 store, and existing rows read null.

### API Contracts

**Submitting** (`docs/inbox-contract.md`):

```bash
amoeba submit resolution --project amoeba --by operator --blocked-state-id <id> \
    --detail "loop is close; one more round" --decision retry \
    --instructions "Address the two schema concerns only."
```

| Field | Rule |
| --- | --- |
| `decision` | Optional. `retry`, `accept`, `handled`, `rerun` or `stop`, checked by the Runner. |
| `instructions` | Optional. Only with `retry` or `accept`, and passed to Squadron verbatim. No secrets, the same rule as payloads. |

**Learning the outcome:** `submission(id)` is `applied` once the slot is filled. Then `blocked_state(id)` carries `runner_outcome` (`applied` or `rejected`), `runner_code` (the rejection code, null when applied) and `runner_reason` (the detail, for people). A rejection also opens a new block, whose escalation lists `allowed`.

**Runner, internal:**

```python
class ResolutionDecision(StrEnum): RETRY; ACCEPT; HANDLED; RERUN; STOP
class Situation(StrEnum): NO_DECISION; PAUSED_RUN; COMPLETED_OUTCOME; ENDED_RUN; BEFORE_RUN
                          UNRESOLVABLE
class ResolutionRejection(StrEnum): UNKNOWN_DECISION; DECISION_REQUIRED; DECISION_NOT_APPLICABLE
                                    NOT_AT_LOOP; CHECKPOINT_UNKNOWN; INTERACTIVE_CHECKPOINT
                                    INSTRUCTIONS_NOT_APPLICABLE; UNRESOLVABLE
class Continuation(StrEnum): RETRY; ACCEPT; OBSERVE
class ResumeFailure(StrEnum): REFUSED; EXITED_BEFORE_CLAIM; NO_CLAIM_WITHIN_GRACE; SPAWN_ERROR
                              RUN_MISSING
@dataclass(frozen=True)
class ResumeRun: node_id: str; run_id: str; decision: Continuation; continues: str
                 resolution: str; checkout: Path
@dataclass(frozen=True)
class ObserveRun: node_id: str; run_id: str; continues: str; resolution: str; checkout: Path
type Action = LaunchRun | BlockHumanStep | WriteSlicePointer | ResumeRun | ObserveRun
```

**CLI:**

- `amoeba inspect blocked` gains `blocked_state_id`, which is the id a resolution names.

## Integration Points

### Provides to Other Slices

- **128:**
  - The identifiable accept of a completed outcome, which is the store side of the gate disagreement it records (D7).
  - `ResumeRun` as a dispatch. 128's clean-tree and branch check applies to it as to `LaunchRun`. A paused run's checkout is on the node's slice branch, which that check allows.
- **129:** the resolutions the proof's PM stops are answered with.
- **160 and the notification bridge:** the decision vocabulary, the `allowed` list in each rejection, and the rejection codes. 160's whitelist is a subset of `ResolutionDecision`.
- **140:** the resolution slot that judge results will fill, with the same acknowledgment.
- **Contract documents:** the resolution fields, the Runner's answer and the codes (`inbox-contract.md`); migration `012` and the three methods (`store-contract.md`); the resolution stage, continuation entries, resume confirmation, and the observer's continuation rules (`process-contract.md`); the 120 row (`substrate-guide.md`).

### Consumes from Other Slices

- **125:** the entry result, `dispatch_state`, the checkout hold, the outcome document model, ingestion and the pointer-move check. The check covers continuation entries, using the step's latest pointer write for the worktree and the continuation's `issued_at` as its start.
- **126:** the route stage, which routes every continuation's outcome, the vocabulary it extends, and the shipped table.
- **121:** `StatusEffect`, `BlockEffect` and the done rule.
- **122:** the launch, logs, `LaunchTracker`, poll cadence, faults and `TickBudget`.
- **124:** the current-step guard, and 124's D9 pattern for a store-only stage.
- **103:** the resolution slot and the inbox's apply.

## Success Criteria

### Functional Requirements

- **Each decision in its situation:**
  - `retry` on a paused run journals a continuation and launches `sq run --resume <id> --decision retry` in the checkout, with no `--run-id`, pipeline or `-p`. `accept` at a loop does the same with `--decision accept`.
  - `handled` journals an observation and launches nothing. The run's current outcome is ingested and routed.
  - `accept` on an escalated completed outcome marks the step done with no command. Its successor is dispatched on the next tick.
  - `rerun` dispatches a fresh run through 125's pointer write, including after a `not_applied` launch.
  - `stop` blocks the node again with `reason: stopped`, and nothing is issued for it.
- **Rejections,** each acknowledged `rejected` with its code, and the node blocked again with `allowed`: an unknown decision, no decision on a pipeline step, a decision outside the situation, accept with `is_loop` false or null, retry at an interactive checkpoint, a null checkpoint kind or `paused_at`, instructions with handled, rerun or stop, an unrouted outcome, an unresolved latest entry, and an outcome document that does not parse. A decision on a human step is rejected, and a bare resolution of one is applied.
- **Instructions** reach the stub `sq` as one argv element, byte for byte. No Runner code path adds instructions of its own, which a source test asserts.
- **An identifiable accept:** after `accept` on an escalated completed outcome, `blocked_state` shows the applied decision, and the step's latest `sq_run` entry holds the verdict ids it accepted, which is what 128 reads (D7).
- **A missing run:** a retry whose pre-poll returns `not_found` resolves `failed` with `run_missing`, blocks the step, and launches nothing. After a restart, a continuation with no run state is escalated by recovery and never reissued.
- **Resume confirmation:** a run that stays at its old pause and then claims is confirmed by the first poll after the claim. A new pause after a retry is recognized by its new `paused_at`, ingested, and routed to escalate.
- **Resume failures:** an exit 2, an exit before the claim, and no claim within the grace period each block the step with their `ResumeFailure`. The checkout stays held, and the node offers the paused-run decisions again.
- **A run moved by hand:** a retry whose pre-poll finds the run running launches nothing and observes it to its outcome.
- **Accept over CONCERNS:** a resumed accept whose final review is the accepted one routes through `advance-on-accepted-review`.
- **Crash:** killed after an acknowledgment and before the continuation is journaled, the next tick issues it once. Killed after a resume is journaled and before the launch, the entry fails as `no_claim_within_grace` and nothing is launched twice.
- **Cut-off and poll failure before a resume:** a spent budget, or a pre-poll that fails, journals nothing. The step stays `RESUME`, and the resume is issued on a later tick with no `resume_failed` escalation.
- **A poisoned resolution stays contained:** with one step's resolution carrying an unparseable outcome document, another step's finished run in the same project is still ingested in that tick.
- **Hold:** a held step's resolution is acknowledged, and its resume waits until the hold is removed.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- Migration `012` is tested on a populated v11 store, and `pending_resolutions` uses its partial index, which an `EXPLAIN QUERY PLAN` test asserts.
- `classify`, `judge_resolution`, `dispatch_state` and the confirmation rule have table-driven tests over every row of D2, D3, D5 and D6.
- Every `sq` call in the continuation path goes through `TickBudget`.
- The contract documents under Provides are updated, and the CHANGELOG has an entry.

### Integration Requirements

- 100's contract suite passes with the new payload fields, and the observer rules. The stand-in Runner acknowledges resolutions.
- 125's dispatch and crash tests and 126's routing tests pass with the resolution stage, `ContinuationPlanner` and the extended vocabulary.
- 128 can read an accepted outcome and filter `ResumeRun` without changing `resolutions/`.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–2 use the stub `sq`. Step 3 launches one real `P4` run on a scratch copy, plus a `P5` run if the accept advances it.

1. **Tests:**
   ```bash
   uv run pytest tests/runner/resolutions tests/store/test_migration_012.py \
     tests/store/test_resolutions.py tests/test_observer_sq_run_id.py -v
   ```
   Expected: all pass. Tests are named for their rules, for example `test_accept_refused_when_not_at_loop`, `test_retry_confirmed_by_new_paused_at`, `test_missing_run_launches_nothing` and `test_continuation_never_reissued`.

2. **Full gate and contract suite:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/contract -v
   ```

3. **An escalated outcome, rejected and then accepted, on a scratch copy.** Write a table that escalates everything:
   ```bash
   cp src/amoeba/runner/routing/tables/default.yaml /tmp/escalate.yaml
   # keep only the last rule (escalate-everything-else) in /tmp/escalate.yaml
   ```
   Follow 125's walkthrough step 3 to create the scratch project, starting with `amoeba start --routing-table /tmp/escalate.yaml &`, and drive one slice `until: tasks`. When the P4 run finishes:
   ```bash
   amoeba inspect blocked --project scratch          # note blocked_state_id of slice_design
   amoeba submit resolution --project scratch --by operator \
       --blocked-state-id <id> --detail "try a resume" --decision retry
   sleep 3; amoeba inspect messages --project scratch --channel escalation
   ```
   Expected, if the run completed: the resolution is rejected. `inspect blocked` shows a new block, and its escalation payload carries `code: decision_not_applicable` and `allowed` as `accept, rerun, stop`. If the run paused instead, retry is allowed: skip to the paused-run check below.
   ```bash
   amoeba inspect blocked --project scratch          # the new blocked_state_id
   amoeba submit resolution --project scratch --by operator \
       --blocked-state-id <new id> --detail "good enough" --decision accept
   ```
   Expected: `inspect nodes` shows `slice_design` done, with no new block, and `inspect journal` shows a `cf_write` for `tasks` on a later tick, then a `P5` `sq_run`. Then pause the project with `{"intent": "pause"}` to stop spending.

   **If the run paused:** submit `--decision accept` if its checkpoint is at a loop (`inspect journal --json` shows `outcome_document.checkpoint.is_loop`), otherwise `--decision retry`. Expected: a new `sq_run` entry with `continuation` and `continues`, `sq runs list` showing the same run id running again, and on its end an ingested outcome and a routing decision.

   Stop with `amoeba stop`.

## Risk Assessment

### Technical Risks

- **Losing or duplicating a resumed run.** A resume has no launch line, and the run looks unchanged until it is claimed. A failure before the claim leaves only an exit code.
- **Resuming the wrong pause.** A PM's decision made days ago could be applied to a run someone has since resumed by hand.

### Mitigation Strategies

- Confirmation reads only observed state: the `paused_at` of a new pause, or any non-paused outcome. Failure rules cover a child that exits, a child that never claims and a restart. One continuation per step at a time, journaled before any side effect, rules out a second resume from Amoeba (D4, D6).
- The pre-poll requires the recorded `paused_at`. A run that has moved is observed, not resumed (D4). A failed resume keeps the run's real outcome, so the checkout stays held while its branch is checked out (D6).

## Implementation Notes

### Development Approach

Relative effort: 3/5. The plan said 2. The resume confirmation and the recovery changes, which follow from Squadron's observed behaviour, add the difference. Suggested order. Each step leaves the suite green.

1. Contract changes (D9): migration `012`, the models, the three store methods, the inbox payload, the observer's continuation rules, the stand-in Runner and the contract suite.
2. `vocabulary.py`, `classify` and `judge_resolution`, table-tested (D2, D3).
3. The resolution stage in the tick (D3).
4. `dispatch_state` with resolutions, `ContinuationPlanner`, and the observe act (D4, D5).
5. The resume act, confirmation and failures, with the stub `sq`'s resume mode (D4, D6).
6. The routing input and table rule (D8), the `blocked` column, the contract documents and the CHANGELOG.

**Testing approach.** The pure functions get most of the cases. Tick-level tests use `Store.open_temporary()`, the stub `sq` on `PATH` under a temporary `HOME`, and a small routing table through `--routing-table`. The crash tests extend 125's `SIGKILL` proof with two kill points: after an acknowledgment, and after a continuation is journaled.

### Special Considerations

- **Plan and arch edits,** made with this design:
  - **Plan entry 8 (127):**
    - Stop parks the node as a block (D3).
    - `handled` journals an observation (D4).
    - Dispatch faults resolve with `rerun` or `stop` (D2).
    - The gate-disagreement criterion moves to entry 9 (D7).
  - **Plan entry 9 (128):**
    - It records the store and CF gate disagreement after an accept, as a criterion required before 128 merges (issue #15). This is a dated plan change (20261020), recorded in the plan's Notes.
    - Its pre-dispatch checks apply to resumes (D7, Provides).
  - **Plan Future Work:** resuming a failed run (Technical Scope).
  - **Arch, "Resolution and resumption":**
    - Stop is held as a block.
    - The gate disagreement is detected by 128's gate read.
    - A resume is confirmed by state, because Squadron prints no line for it (D3, D6, D7).
    - `retry` is refused at an interactive checkpoint, because a non-TTY resume cannot pass it (D2, rule 6).
    - Any other blocked pipeline step can be rerun or stopped (D2).
  - **Arch, "Observe, decide, act":** a continuation that only observes is journaled, because it owns the run while observed (D4).
  - **Arch, tick order** in "The tick never waits" and "The loop, per tick, per project": resolutions are acknowledged after intents and before Observe (D3).
- **Abandoning a paused run.** The run's checkout stays held while the run is paused, including after `stop`. To free it, the PM removes or finishes the run in Squadron and submits `handled`. A missing run resolves `run_missing`, which releases the checkout, and `rerun` or `stop` is then allowed. A pause whose work the PM finished by hand loops back to the PM through `handled`, until "mark a step done" (Future Work 8) exists.
- **Spend.** `retry` on an exhausted loop is one paid review round, and only a PM decision issues it. No route in the table resumes a run in v1.
- **Security.** Instructions are passed as one argv element, with no shell. They are visible in the process list and stored verbatim in the store, so the inbox contract repeats the no-secrets rule for them. Journal parameters hold ids and paths only.
