---
docType: slice-design
slice: pipeline-supervisor
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 128
interfaces:
- 140
- 160
dateCreated: 20261028
dateUpdated: 20261031
status: complete
turns: 66
promptTokens: 6534186
cachedTokens: 6371222
cacheWriteTokens: 162858
completionTokens: 44894
durationSeconds: 460.5
costUsd: 3.47574
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.4757393999999993
    completionTokens: 44894
revision_number: 2
---

# Slice Design: Pipeline Supervisor

## Overview

Slices 120–128 built a Runner that steps a slice through P4, P5 and P6 itself, routes each review against a table, reruns on FAIL, reads CF's gates, checks the ungate hatches, and watches for merges. Squadron's pipelines already do all of that. The arch's Direction Change (20261028) and `user/notes/004-direction.amoeba.md` make the Runner a supervisor over each project's Squadron pipeline instead.

This slice does that cut. For each driven slice the Runner launches one run of the pipeline the project is configured to run, in the slice's checkout, after the clean-tree check. Then it watches the run:

- **completed:** the slice is done.
- **crashed or stopped for a transient reason:** the run is resumed with `sq run --resume`, up to a bound.
- **paused on an agent's question:** the slice blocks with the question attached, ready for 140.
- **anything else:** the slice blocks with the reason.

Every blocked slice, across every project, appears in one list. The policy layer the pipeline owns is deleted.

What stands from 120–128: the tenant and its observe / decide / act stages, the tick budget, fault isolation, detached launch and launch confirmation, observation by run id, the journal and crash recovery, intents (drive and hold), checkout resolution and one pipeline per checkout, the shape probes, plan reads and reconciliation of initiatives and slices, and review ingestion.

## Value

- **User value.** A PM drives a slice and Squadron runs the whole pipeline the project chose, `p456`, a merging `p4567`, or anything else, without Amoeba stopping between phases. Transient failures and usage-limit pauses no longer reach the PM. What does reach the PM is in one list across all projects.
- **Developer value.** One copy of pipeline policy, in Squadron. Thresholds, revision counts, judges and merging are set in one place. About a third of `src/amoeba/runner/` goes, and with it the routing table, its decision records and its grammar.
- **Architectural enablement.** 140 (the question answerer) gets a stable input: a slice blocked on `agent_question` whose payload holds the run id and the question, and a resolution (`resume` with instructions) that carries its answer back.

## Technical Scope

**Included:**

1. Per-project config reduced to the pipeline a project runs and its parameters (D2).
2. The slice as the unit of work. Reconciliation stops creating step nodes, and the step map, human steps and step-level predecessors go (D1).
3. Dispatch: one launch per driven slice, with no CF pointer write (D3).
4. The outcome map (D4) and automatic resume (D5).
5. Resolutions cut to `resume` and `stop` (D6).
6. Intents without `until` (D7).
7. `amoeba inspect blocked` across every project (D8).
8. Reading `checkpoint.question`, `checkpoint.resets_at` and `failure.agent_text` from `sq runs wait --json` (D10).
9. Deleting the routing engine, the pointer stages, CF gate reads, the ungate hatches, merge policy and merge observation, and every test, doc section and setting that only they used (D9, Migration Plan).

**Excluded:**

- Answering questions. That is 140, which reads the block this slice writes.
- Notification. That is 160.
- Reading Squadron's run-state file. Everything this slice and 140 need is in `sq runs wait --json` (D10).
- Retiring the store's routing tables and their API. They stay in 100's contract, unwritten (D9).
- Multi-project scheduling (plan Future Work 1).
- Recording every review of a multi-phase run. Ingestion keeps 125's last-review rule (Future Work, below).

## Dependencies

### Prerequisites

- Slices 120–128, complete and merged. This slice cuts code they built.
- Squadron 0.24.9 (released 20261028, installed and observed 20261028): the `agent_question` checkpoint on design, tasks and implement steps, `checkpoint.resets_at` (#248), and `failure.agent_text`. The fields are optional, so an older `sq` degrades to the `BLOCKED` row of D4, never to a resume (D10).

### Interfaces Required

- `sq run <pipeline> <slice> --run-id <id> [-p k=v ...]`, `sq run --resume <id> [--instructions <text>]`, `sq runs wait <id> --timeout 0 --json`. All of these are already used by 122, 125 and 127.
- `sq run --resume` works on paused, failed and orphaned runs. It refuses a run still live under its process (Squadron `_refuse_live_run`, #195).
- 100's store: nodes, `block` / `resolve`, the journal, desired states, the resolution slot.

## Architecture

### Component Structure

After the cut, `src/amoeba/runner/` holds:

| Area | Keeps | Changes |
|---|---|---|
| `tick.py`, `tenant.py`, `factory.py` | the stage order and tenant | loses the pointer, gate, merge, routing and overrun stages (Data Flow) |
| `decide.py` | `Planner`, `decide`, the view | Actions become `LaunchRun`, `ResumeRun`, `BlockDispatch`. View fields for pointers, gates and merges go. |
| `launch.py`, `observe*.py`, `record_runs.py`, `finish.py`, `faults.py`, `budget.py`, `probes.py` | as built | `faults.py` loses the deleted kinds and gains `pipeline_unconfigured` (D11) |
| `ingest/` | review recording, `runner_issued`, the outcome block | `outcome.py` gains the outcome map (D4). `record.py` resolves and completes in one transaction, and stops marking `awaits_routing`. |
| `lifecycle/` | plan reads, reconcile, orphaning, references, status block, cadence | the step map, `human_steps.py` and step completion go. Predecessors become slice order (D1). |
| `intent/` | apply, governance, merge | `until` goes (D7). Governance resolves on slice nodes. |
| `dispatch/` | `checkout.py`, `hold.py`, `planner.py`, `params.py`, `build_view.py`, `reissue.py`, `state.py`, `facts.py` | pointer files go. `params.py` reads the project config (D2), and `state.py` loses `NEEDS_POINTER`. |
| `resolutions/` | stage, act, confirm, prepoll, argv | vocabulary cut to `resume` and `stop`. Situations collapse (D6). |
| `git_read.py`, `gates/predispatch.py` | the git half of the pre-dispatch check | the CF gate half goes. `predispatch.py` moves to `dispatch/checkout_check.py` once `gates/` is otherwise empty. |
| `gates/candidates.py`, `gates/dispatch_reads.py`, `gates/cf_reads.py` (`read_target`, `read_config`, `DEFAULT_TARGET_BRANCH`), `gates/stage.py` (`GateStage.check_dispatch`) | the dispatch check needs them ("on the target") | CF gate parts removed. They move to `dispatch/` as `candidates.py`, `checkout_reads.py` and `check_stage.py` (Task 10.2). |
| `project_config.py` | load, validate, defaults | `merge_policy` becomes `pipeline` and `params` (D2) |

The deleted modules are listed in D9.

One new pure module, `runner/supervise.py`, holds the outcome map (D4) and the resume rule (D5). Nothing else names an outcome class.

### Data Flow

One project's tick, after the cut:

```
apply intents ─► answer resolutions ─► observe runs ─► probes ─► plan reads
   ─► record finished runs  (ingest: block or complete, in the resolving transaction)
   ─► raise faults ─► build view ─► pre-dispatch checks (git) ─► decide ─► act
   ─► raise faults ─► close recovered escalations
```

Removed from the tick: the pointer observation, `watch_pointers`, `watch_overruns`, the outcome observation (CF gate at completion), merge observation, and `route_outcomes`.

A driven slice goes through these states:

```
runnable, no run ──LaunchRun──► in flight ──run ends──► ingest
   completed ───────────────────────────────► done              (same transaction)
   transient, under the bound ──────────────► runnable; Decide issues ResumeRun
   transient, at the bound ─────────────────► blocked_on_human  reason auto_resume_exhausted
   paused agent_question ───────────────────► blocked_on_human  {question}
   anything else ───────────────────────────► blocked_on_*      with the reason
blocked ──resolution resume──► ResumeRun (run exists) or LaunchRun (no run to resume)
blocked ──resolution stop────► stays blocked, reason stopped
```

### State Management

- **No new tables or columns.** Everything this slice decides is read from nodes, block payloads and journal entries that already exist.
- **The resume count** (D5) is derived from the slice's journal entries, not stored.
- **Stores built before this slice** may hold step nodes. The Runner ignores them: they are never candidates, and their journal entries still recover. No store in use holds any (checked 20261028: no store under `~/.config/amoeba`), so no migration is written.
- **Unwritten history.** `routing_decisions`, `routing_table_versions`, `attempt_counts`, `command_journal.awaits_routing` and `desired_states.drive_until_step` stay in the schema. Migrations are append-only and dropping data is not this slice's to do. The Runner stops writing them.

## Technical Decisions

### D1 — The slice is the unit of work
Status: decided
- The Runner dispatches slice nodes. Reconciliation creates initiative and slice nodes and no step children. `LifecycleStep`, `STEP_MAP`, `STEP_SEQUENCE`, `HumanStepPlanner` and the step completion rule go.
- **Ready slice:** `runnable`, linked, no blocked ancestor, CF status not `complete`, not `deferred` or `deprecated`, and its predecessor `done`. The predecessor is the linked eligible slice with the next lower CF index in the same initiative. That is 123's `_previous_eligible_slice`, kept as the whole of `predecessors.py`. The predecessor function stays the one place for 180 to add cross-project edges.
- **Completion from CF stays at slice level.** A slice CF reports complete, with no unresolved journal entry and not blocked, is marked `done` by reconcile. This covers work the PM did by hand.
- **Initiative-level human steps go.** A slice exists only once CF lists it in a slice plan, so architecture and slice planning are already done. Integration was never automated. An initiative node is `done` when every eligible slice under it is `done`, written by reconcile.
- **Rejected:**
  - One `pipeline` step child per slice. It keeps the step machinery for a single step.
  - Keeping the human steps as blocks. That puts the PM in the loop for work no pipeline does, against the direction's rule.

### D2 — Per-project config names the pipeline and its parameters
Status: decided
- **File:** the same static YAML file as 128, loaded at start, and changing it means a restart. Its shape changes:

  ```yaml
  projects:
    amoeba:
      pipeline: p456
      params:            # optional; each becomes -p key=value
        model: opus
    trading-engine:
      pipeline: p4567    # a user pipeline that also merges
  ```

- **`pipeline` is required for each named project, and there is no default.** A driven slice in a project the file does not name is not launched. The project raises a `pipeline_unconfigured` escalation, which closes on the first tick the project no longer needs it (D11). A default pipeline would be a magic value that could merge code nobody chose to merge.
- **`params`** is a string-to-string mapping passed through verbatim. Load fails, listing every problem, on any of these:
  - a key `slice`, because that is the target the Runner passes;
  - a key containing `,` or `=`;
  - a value containing `,`;
  - a non-string value;
  - an unknown key beside `pipeline` and `params`.

  The first three are the rules `build_argv` already enforces, checked at load so a bad config fails at start rather than at first launch.
- **The pipeline name is not validated at load.** An unknown pipeline makes `sq run` print `Error: Pipeline '<name>' not found.` and exit 1, not 2, before the `run_id=` line. This was observed with `sq` 0.24.8 on 20261028 (`run.py`, `load_pipeline`'s `FileNotFoundError`). So it takes 122's launch-failure path, which blocks only that slice, with Squadron's stderr. It never takes the exit-2 path that stops the process (122, D6). No help text or pipeline list is parsed.
- `MergePolicy`, `merge_policy`, `PROJECT_DEFAULTS.merge_policy` and the `merge_policy` and `target` journal keys go. A pipeline that merges is a pipeline that merges.
- The settings flag `--project-config` stays. `--routing-table` and `routing_table_path` go.

### D3 — Dispatch is one launch per driven slice, with no pointer write
Status: decided
- Every Squadron phase step runs `cf set slice`, `cf set phase` and `cf build` itself (direction note, "What Squadron already gives us"). The Runner issues no `cf_write`.
- These go:
  - the two-tick dispatch;
  - `WriteSlicePointer` and `NEEDS_POINTER`;
  - the pointer read-back and pointer-confirmed set;
  - `pointer_watch` (`pointer_moved`) and the snapshot-after-own-write rule.

  `CommandKind.CF_WRITE` stays in the store for recovery of old entries.
- **The launch:** `LaunchRun(slice_node, config.pipeline, {slice: <index>, **config.params}, checkout)`. 125's checkout resolution (the CF worktree whose index range holds the slice) and its one-pipeline-per-checkout hold are kept. A checkout is held from launch until the run is neither running nor paused. 125's hold rule counts a not-`done` slice whose latest `sq_run` entry recorded `paused`. That rule widens to `paused`, `failed` or `orphaned`, because each leaves the slice's work in the checkout for a resume (D5, D6). Release is the same as for `paused`. A blocked slice, including one at `auto_resume_exhausted` or stopped, therefore holds its checkout until the PM acts. This widens the arch's "until its run is no longer running or paused". The arch text is fixed under #22. The planner's per-checkout order becomes `(initiative index, slice index)`. Reissue (125, D9) is kept.
- **Pre-dispatch check, git only.** It keeps 128's D5 git rules and D6 with one allowed-branch rule for every pipeline:
  - **Fresh launch or reissue:** on the target and clean.
  - **Resume:** on the target or this slice's own branch (`{index}-slice.` stem). The tree is not checked for cleanliness, because a crashed or paused run's uncommitted work is what the resume continues.

  The CF entry-gate rows of D5 and the `pending_decision` block go.
- **A slice left on its branch.** A pipeline that does not merge leaves its checkout on the slice branch. The next slice in that checkout blocks with `checkout_branch` until the PM merges, or until the project's pipeline merges itself. This is the 128 D6 behaviour, kept. The fix is a merging pipeline, not a Runner wait.

### D4 — The outcome map
Status: decided
- **One pure function,** `supervise.classify(document | vanished | launch_failed | resume_failed) -> OutcomeClass`. It replaces `plan_outcome`'s match and the routing table. `OutcomeClass` is a closed enum: `COMPLETED`, `TRANSIENT`, `QUESTION`, `BLOCKED`.

  | Observed | Class | Effect at ingest |
  |---|---|---|
  | `completed` | `COMPLETED` | Entry resolved and slice marked `done` in one transaction |
  | `orphaned` | `TRANSIENT` | D5 |
  | `failed`, `failure.kind` `provider_error` or `stall` | `TRANSIENT` | D5 |
  | `paused`, `checkpoint.kind` `usage_limit` with `resets_at` present | `TRANSIENT` | D5 |
  | `paused`, `checkpoint.kind` `agent_question` | `QUESTION` | `block(HUMAN)`, payload `{run_id, reason: agent_question, step, question}` |
  | any other `paused` (`loop_exhausted`, `awaits_human`, `interactive_checkpoint`, `usage_limit` without `resets_at`, `other`, an unknown kind) | `BLOCKED` | `block(HUMAN)`, payload `{run_id, reason: paused, checkpoint}`; the checkpoint is also in the resolved entry's outcome document |
  | any other `failed` (`artifact_missing`, `cost_cap`, an unknown kind) | `BLOCKED` | `block(HUMAN)`, payload `{run_id, reason: failed, failure}`. `failure` includes `agent_text` when Squadron sent it. |
  | vanished, launch failed, resume failed | `BLOCKED` | as 122, 125 and 127 write them today |

- **Why the pause blocks are `HUMAN`.** The store keeps a block's payload only on the escalation row of a `HUMAN` block (`ESCALATING_KINDS`). A `SQ_CHECKPOINT` block carries none, so a question blocked that way would lose the text 140 needs. Found by the end-to-end test (Task 12.1). The other pauses are `HUMAN` too (settled 20261030), so one blocked list shows each checkpoint.
- **Atomic completion.** Resolving the `sq_run` entry and marking the slice `done` happen in one store transaction. Otherwise a crash between them would leave a runnable slice whose run completed, and the next tick would launch the pipeline again. `Store` gains this as an additive option on the ingestion write. The resolution and `runner_issued` marking already share a transaction there (125). 121's `done`-terminal rule is unchanged. `store-contract.md` documents it. This is a contract change made inside a Runner slice, an exception to the arch's "contract changes land as their own slice". It is taken deliberately: the change is additive, one option on an existing write, and a separate slice for it would be ceremony. It still lands first, as its own task with its own contract test, before any Runner code uses it (Migration Plan step 3). The alternative, marking `done` before resolving the entry, was rejected because a crash between the two leaves an unresolved entry whose completed run is ingested again onto a `done` node.
- **No `awaits_routing`, no decision record.** The map is fixed code over closed inputs, and the resolved entry holds the outcome document it acted on. The direction's rule "completed → done; resumable → resume; question → 140; anything else → blocked" is the whole policy. A table to configure it would be the second copy of policy this slice exists to remove.
- **Text bounds.** `question`, `agent_text` and every checkpoint and failure text field pass through `cut_to_bound` (`STDERR_TAIL_LIMIT_BYTES`), as 125 does today.
- **Constants defined once** in `supervise.py`: the payload reasons `agent_question`, `paused`, `failed` and `auto_resume_exhausted`, and the two transient failure kinds.

### D5 — Automatic resume
Status: decided
- **Who resumes.** At ingest, a `TRANSIENT` outcome under the bound leaves the slice `runnable`. Its entry is resolved with the outcome document, as now. The view lists it as a resume candidate. Decide issues `ResumeRun(node, run_id, checkout, instructions=None, cause=transient)` for a current (driven, not held) candidate whose pre-dispatch check passed. A held slice is not resumed until released, which matches "a held target issues nothing new".
- **When.** Immediately, except for a `usage_limit` pause, which waits until `view.now >= resets_at`. Decide reads `now` from the view, so it stays pure. The slice is runnable but not yet a candidate.
- **The bound.** The setting `auto_resume_limit` (default 3, defined once in `Settings`, flag `--auto-resume-limit`) is the most consecutive automatic resumes of one run **at one step**. The count is the number of trailing `sq_run` entries for the slice whose `resume_cause` journal parameter is `transient` and whose resumed-from outcome stopped at the same step as the outcome being ingested. The step is the outcome document's `checkpoint.step` or `failure.step`; an `orphaned` outcome with neither counts as the same step as the entry before it. A fresh launch, a PM `resume`, or a transient outcome at a different step ends the run of entries, so the count restarts. A `p456` run that crashes once in design, once in tasks and once in implementation is resumed each time; a run that crashes three times at the same step is not resumed a fourth time. The count is read from the slice's journal entries, which the view already reads (125), so a restart cannot reset it. At ingest, a `TRANSIENT` outcome at the bound blocks `HUMAN` instead, with reason `auto_resume_exhausted`, the last failure or checkpoint, the step, and the count.
- **Usage limits are bounded the same way.** Each wait for `resets_at` is an automatic resume and counts at its step. A long run that meets a usage-limit window at each of its phases is resumed at each one. A `usage_limit` pause with no `resets_at` is `BLOCKED`, never resumed blind.
- **Confirmation.** 127's D6 `resume_progress` generalises from "left the pause" to "left the state it was resumed from". That state is the resumed-from entry's recorded `outcome` and `updated_at`. A poll showing the run going (`timed_out`), or with a later `updated_at`, confirms the resume. Every resume entry is judged this way, automatic or resolution. `Continuation` becomes `{RESUME}`, the one value that marks an entry as a resume.
- **No stale re-ingestion.** Until a resume entry is confirmed, a poll that still shows the resumed-from state is `StillResuming`. It is never ingested, so it neither counts toward the bound nor triggers a second resume.
- **A resume that never takes.** If the child has exited, or the launch grace period has passed, while the run still shows its old state, 127's `ResumeFailed` path applies. The slice blocks `HUMAN` with reason `resume_failed`, the entry is resolved `failed`, and no further automatic resume is issued.
- **The act-time pre-poll** (127, D4) stays. Act polls the run once before resuming. If the run is no longer in the state that was classified, the resume is withheld and the run is observed again.
- **A run that is still live.** `orphaned` comes from Squadron's own liveness check, so a resume normally finds the run dead. If its owner comes back between the pre-poll and the resume, Squadron refuses with exit 1 ("still running", `_refuse_live_run`). The Runner does not read that message. After any failed resume it polls the run once more, and decides on what it sees (122's rule: the observed run state, never the error text). If the run is `running`, the resume entry resolves `not_applied`, the run is observed again as in flight, and nothing counts toward the bound or blocks the slice. Any other state takes the `ResumeFailed` path described under "A resume that never takes".
- **This extends the plan entry,** which lists orphaned, provider error and stall. `usage_limit` with `resets_at` is added because Squadron says resume after `resets_at`, and blocking it would put the PM in the loop for a timer. The plan entry says so.
- **Rejected:** keeping 126's attempt counts. Those bound reruns of a phase after a review. These count resumes of one crashed run, which the journal already records.

### D6 — Resolutions: `resume` and `stop`
Status: decided
- `ResolutionDecision` becomes `{RESUME, STOP}`. `retry`, `accept`, `handled` and `rerun` are rejected as `unknown_decision`, so a stale client fails loudly. No client submits them today: 160 is not built.
- **`resume`**, with optional `instructions` passed verbatim as data, on any blocked slice:
  - The slice's latest `sq_run` entry names a run Squadron still has (paused, failed or orphaned). The Runner issues `sq run --resume <id> [--instructions <text>]`, journal parameter `resume_cause: resolution`. This resets the D5 count.
  - Otherwise (launch failed, vanished, a `checkout_*` block before any run, an orphaned or status block): the block is resolved, and the slice is launched afresh when next current. Instructions on a resolution with no run to resume are rejected with `instructions_not_applicable`, because a fresh launch cannot carry them.
  - The pre-dispatch check runs before either.
- **`stop`:** 127's D3, unchanged. The node stays blocked with reason `stopped`.
- `--decision accept` and `--decision retry` are never passed. A plain `--resume` is Squadron's retry.
- **Situations collapse** to `RUN_TO_RESUME`, `NO_RUN` and `UNRESOLVABLE`. Rejection codes reduce to:
  - `unknown_decision`
  - `decision_required`
  - `instructions_not_applicable`
  - `unresolvable`
- The 127 rule stands: a resume whose run is missing is a failed command, never relaunched. An exit 2 from a resume blocks the slice with Squadron's message.
- **Name clash.** Intent `resume` (release a hold) and resolution `resume` (resume a run) live on different channels with different bodies. The inbox contract says so in one line.

### D7 — Intents lose `until`
Status: decided
- `until` named a lifecycle step, and there are none now. `IntentBody` drops the field. A body that still carries it is rejected as `malformed_body` (unknown keys are errors), and `UNTIL_NOT_APPLICABLE` goes. `drive`, `exclude`, `pause`, `resume` and `clear` are unchanged and resolve on slice nodes by the same nearest-target rule.
- The `drive_until_step` column stays and is written `NULL`. `DesiredStateIndex` ignores it.

### D8 — One blocked list across projects
Status: decided
- `amoeba inspect blocked` without `--project` lists every project's blocked nodes. With `--project` it narrows to one, as today. Columns: `project_id`, `node_id`, `title`, `blocked_on`, `reason`, `context`, `blocked_state_id`. `reason` is the payload's `reason` or `fault_kind`, empty when the block has neither. `--json` emits the same rows plus the full payload, which holds the question.
- It opens every store read-only, like the `projects` listing. It is the PM's view until 160 notifies.
- The network API's per-project blocked surface is unchanged.

### D9 — What is deleted, and what stays in the store
Status: decided
- **Deleted from `src/amoeba/runner/`:**
  - `routing/`, including `tables/default.yaml`;
  - `gates/`, except the git half of `predispatch.py` (moved, see Component Structure). `checks.py` goes with its only users, `hatches.py` and `accepted.py`;
  - `dispatch/pointer.py`, `pointer_apply.py`, `pointer_watch.py` and `observe_pointer.py`;
  - `lifecycle/steps.py` and `human_steps.py`, and the step rule in `completion.py`;
  - `resolutions/judge.py` cases for the removed situations.
- **Elsewhere:**
  - `inspection/routing.py` and the `routing-decisions` listing go, because they import the deleted recompute.
  - The `--routing-table` flag and `routing_table_path` setting go.
- **Each delete is confirmed against Squadron,** per the direction note's "confirmed one by one against what pipelines do":

  | Deleted | Squadron owns it as |
  |---|---|
  | verdict and standing routing, `rerun`, attempt limits | the pipeline's pass and accept thresholds, `--max-revisions` |
  | the P4/P5/P6 step map and chaining | `p456`, `p56`, `p45`, user pipelines |
  | `cf_write` pointer moves and pointer watch | each phase step's `cf set` and `cf build` |
  | CF gate reads, `pending_decision` | the review loop inside each phase step, which pauses or fails rather than proceeding |
  | ungate-hatch checks | none needed. The hatches only fooled the Runner's own CF gate reads, which are gone. |
  | merge policy and merge observation | a merging pipeline, or the PM; a non-merging run's slice is done when its run completes. Squadron's merge (`pipeline/branch_ops.py` `merge_slice_branch`, read 20261028 at `cc300518`) re-reads `git.integration_branch` from CF at merge time through `read_integration_target` and merges only into that target, raising rather than falling back to `main` when CF cannot be read. It also refuses to merge while any of the slice's task files has an unchecked box (`_require_checked_tasks`). |
  | run overrun and the per-pipeline time bound | Squadron's `stall` failure and its orphan detection, both of which this slice resumes |

- **Stays in the store, unwritten:** the routing-decision, table-version and attempt-count tables and their API, `awaits_routing` and `unrouted_outcomes`, and `CommandKind.CF_WRITE` and its observer. They are 100's contract. Retiring them is Future Work, below.

### D10 — Squadron shapes read
Status: decided
- **`RunCheckpoint` gains:**
  - `question: str | None`, Squadron's `checkpoint.question`, the reply's last 400 characters;
  - `resets_at: datetime | None`.

  **`RunFailure` gains** `agent_text: str | None`.

  **`CheckpointKind` gains** `AGENT_QUESTION`.

  All are optional, extra keys are still ignored, and an absent field is `None`, never a fill.
- **`agent_question` with no `question`** is still `QUESTION`. The payload's `question` is `null`, and 140 handles the absence. Implement steps pause on `agent_question` the same way as design and tasks steps (0.24.9), so a question from any phase of a `p456` or `p4567` takes the `QUESTION` row.
- **A task the agent marked blocked for a person** (the arch's Technical Considerations) is the same event as a question: the agent stops instead of finishing, and the run pauses as `agent_question`. A merging pipeline is also guarded by Squadron's merge, which refuses while any task box is unchecked (`_require_checked_tasks`, D9). No separate input is read.
- **No run-state file read.** `failure.agent_text` (0.24.9) carries the agent's reply on `artifact_missing`, so nothing needs the file.
- **No new probe.** These are optional fields on a shape 122 already probes.

### D11 — Faults
Status: decided
- **`FaultKind` loses:**
  - `pointer_write_failed`
  - `pointer_moved`
  - `run_overrun`
  - `cf_gate_blocks`
  - `pending_decision`
- **It gains `pipeline_unconfigured`,** project-scoped and closed on the first complete tick without it. It is raised once per tick for a project with a current slice and no configured pipeline.
- `checkout_read_failed` stays. Its source is now only the git read.
- All other kinds and the one process-boundary catch are unchanged.

### Technology Choices

No new libraries. YAML and pydantic for the config, as in 128.

### Patterns and Conventions

- `supervise.py` is pure and is the only module that names an `OutcomeClass` or a transient kind.
- Journal parameter `resume_cause` with values `transient` and `resolution`, defined once beside `PARAM_*` in `resolutions/vocabulary.py`.
- Deleting a module deletes its tests in the same commit. A test of a surviving behaviour that imported a deleted module is rewritten against the slice model, not removed.

## Implementation Details

### Migration Plan

This slice restructures the Runner in place. The resident process must start and pass its suite after every task.

**Order in the task breakdown.** The steps below are covered, but the tasks run in a different order. Dispatch cannot move to slice nodes while routing, the CF outcome read and the step map are still on the tick, because each keys on a step. So the tasks add every new piece first (config and settings, Squadron shapes, atomic completion, `supervise.py`), take the post-completion policy off the tick, add automatic resume, cut the vocabularies, then switch dispatch to slice nodes in one sequence and delete what is left unused.

1. **Config and dispatch first.** Add `pipeline` and `params` to the config, launch the configured pipeline on the slice node, and remove the pointer write. This is the step that changes what runs.
2. **Slice nodes.** Stop creating step nodes, then retarget these to slice nodes:
   - governance
   - `ready_steps` (renamed `ready_slices`)
   - predecessors
   - completion
   - `ProjectView.current_steps` (renamed `current_slices`)
   - `decide`'s guard
3. **Outcome map and resume.** First task: the store's atomic-completion option (D4), with its own contract-suite test and the `store-contract.md` update in the same task. Then add `supervise.py` and wire it into ingest with atomic completion. Add `ResumeRun(cause=transient)`, then remove `route_outcomes` from the tick.
4. **Resolutions and intents.** Cut the vocabularies and update `inbox-contract.md` in the same task.
5. **Deletions,** in dependency order:
   1. `routing/` and its listing;
   2. `gates/` reads, hatches and merge;
   3. the pointer modules;
   4. `steps.py` and `human_steps.py`;
   5. the unused `FaultKind` members.

   `test_import_boundaries.py` and the create-node guard keep passing throughout.
6. **Blocked list.** Make `amoeba inspect blocked` supervisor-scoped.

**Consumers to update:**

- `cli/lifecycle.py` (factory arguments)
- `cli/settings_flags.py` (flags)
- `process/settings.py` (`routing_table_path` out, `auto_resume_limit` in)
- `inspection/__init__.py` (listing registry)
- the test harnesses that build a routing table or merge policy: `routing_helpers.py`, `cf_stub_gates.py`, `gate_rig.py`, `cf_stub_pointer` tests

**Docs:**

- `process-contract.md`: config format, settings, the outcome map, auto-resume
- `inbox-contract.md`: intent body, resolution vocabulary
- `store-contract.md`: the routing tables marked unwritten by the Runner. The atomic completion option is documented in step 3's first task.
- `context-forge-contract.md`: the Runner no longer writes pointers or reads gates
- `substrate-guide.md`: the 120 row

**Behaviour verification.** 122's crash tests (launch, adoption, recovery across `kill -9`) and 125's ingestion tests run unchanged against the slice node. The end-to-end test is rewritten to drive one slice through a stub `p456` (Verification Walkthrough).

### API Contracts

```text
# project config (D2)
projects: {<project_id>: {pipeline: str, params?: {str: str}}}

# settings (D5)
auto_resume_limit: int = 3          # --auto-resume-limit

# intent body (D7)
{"intent": "drive|exclude|pause|resume|clear"}

# resolution (D6)
{"decision": "resume|stop", "instructions"?: str}      # instructions only with resume, on a run

# block payload, agent question (D4) — 140's input; a HUMAN block
{"run_id": str, "reason": "agent_question", "step": str|null, "question": str|null}

# sq_run journal parameters, resume (D5, D6)
{"run_id": str, "continues": <entry id>, "resume_cause": "transient|resolution",
 "instructions"?: str, "dispatch_check": {...}}
```

```text
# store: atomic completion (D4)
Store.record_runner_report(entry_id, reviews, outcome=, result=, complete_node_id: str | None = None)
    # when set, that node is marked done in the same transaction

# supervise.py (pure; the only place the D5 rule is written)
resume_count(entries, step) -> int      # trailing transient resumes at one step, newest first

# dispatch state
DispatchState.AUTO_RESUME               # beside RESUME; set by dispatch/state.py when the slice's
                                        # latest resolved sq_run outcome classifies TRANSIENT and the
                                        # slice is not blocked. resets_at is read by Decide, not state.

# ResumeRun after the cut
ResumeRun(node_id, run_id, continues, checkout, cause: ResumeCause,
          instructions: str | None, resolution: str | None, journal_extra)
    # ResumeCause = transient | resolution, PARAM_RESUME_CAUSE in resolutions/vocabulary.py
    # resolution is set only for cause=resolution
```

```bash
amoeba inspect blocked [--project ID] [--json]     # D8: every project when --project is omitted
```

## Integration Points

### Provides to Other Slices

- **140 (question answerer):**
  - the `agent_question` block and its payload (D4);
  - the `resume` resolution with `instructions` as its way back (D6);
  - every resolved `sq_run` entry's outcome document, for earlier answers to the same question.
- **160 (Translator, notification bridge):**
  - the two-value resolution vocabulary;
  - the drive and hold intent body without `until`;
  - the cross-project blocked list (D8) as the thing it notifies about.
- **Plan Future Work 1 (multi-project scheduling):** a single launch point (`LaunchRun` from one planner) to put a global limit in front of.

### Consumes from Other Slices

- **122:** launch, observe, recovery, faults and budget.
- **123:** plan reads and reconciliation, minus steps.
- **124:** intents and governance.
- **125:** checkout resolution and hold, ingestion, reissue.
- **127:** the resolution stage, act-time pre-poll and missing-run rule.
- **128:** the git pre-dispatch rules, D5 git rows and D6.
- **Squadron:** an absent optional field degrades to the `BLOCKED` row of D4, never to a resume.

## Success Criteria

### Functional Requirements

- A driven slice in a project configured with `pipeline: p456` gets one `sq run p456 <index> --run-id <id>` launch, with no `cf set` from Amoeba, and is `done` when the run completes.
- `params` reach the launch as `-p key=value`. A config with a `slice` key, a `,` or `=` in a key, a `,` in a value, or a non-string value refuses to start, listing each problem.
- A driven slice whose configured pipeline does not exist blocks with Squadron's `not found` stderr. The resident process and other projects keep running.
- A driven slice in an unconfigured project launches nothing and raises one `pipeline_unconfigured` escalation, which closes once the project is configured or no longer driven.
- Slices of one initiative run in index order, each waiting until its predecessor is `done`.
- A fresh launch on a dirty tree or off the target blocks with `checkout_dirty` or `checkout_branch`. A resume on the slice's own branch with a dirty tree goes ahead.
- Each D4 row produces its effect. A crash between ingest's writes never leaves a completed run's slice `runnable`. Proven with the crash harness.
- `orphaned`, `provider_error` and `stall` outcomes are resumed with `sq run --resume <id>` and no instructions, up to `auto_resume_limit` consecutive times at one step. The next one at that step blocks with `auto_resume_exhausted`. A transient outcome at a different step restarts the count.
- A `usage_limit` pause with `resets_at` is not resumed before `resets_at` and is resumed on the first tick after it.
- A held slice is not resumed. Releasing the hold resumes it.
- An `agent_question` pause blocks with the question in the payload, bounded.
- `resume` with instructions resumes the slice's run with them verbatim, and resets the count. `resume` on a slice with no run relaunches it. `stop` keeps it blocked. `retry`, `accept`, `handled` and `rerun` are rejected `unknown_decision`.
- An intent with `until` is rejected `malformed_body`.
- `amoeba inspect blocked` without `--project` lists blocked slices from two projects, with reason, and `--json` carries the question.

### Technical Requirements

- No module in `src/amoeba/runner/` imports `routing`, `gates.cf_*`, `gates.hatches`, `gates.merge*` or `dispatch.pointer*`. The modules do not exist. A grep test in `test_import_boundaries.py` names them.
- No code path issues `cf set`. The CF commands-defined-once test drops the write commands.
- `supervise.py` is pure and fully covered, one test per D4 row and per D5 bound edge.
- Format, lint and typecheck clean. The full suite passes. 100's existing contract tests pass unchanged, and the one added contract test covers atomic completion (D4).
- The listed contract docs are updated.

### Integration Requirements

- 140 can find every question-blocked slice by `reason == "agent_question"` and answer it with one `resume` resolution.
- `src/amoeba/runner/` is smaller by the deleted modules. The line count before and after is recorded in the slice's commit message.

### Verification Walkthrough

Steps 5–7 use the stub `sq` and `cf` from `tests/`; steps 1–4 run against a real slice with `sq`.

1. **Configure.** Write `~/.config/amoeba/projects.yaml`:

   ```yaml
   projects:
     amoeba:
       pipeline: p456
   ```

   Start with `amoeba start --project-config ~/.config/amoeba/projects.yaml`. Expected: the log line `project config loaded from …`. No routing-table line.
2. **Bad config refuses.** Add `params: {slice: "1"}` and restart. Expected: start fails, naming `projects.amoeba.params.slice`. Revert.
3. **Drive a slice.** `amoeba submit intent --project amoeba --by pm --node-id <slice-node> --body '{"intent": "drive"}'`. Run it on a scratch project (a throwaway `CONTEXT_FORGE_DATA_DIR` and `--cf-data-dir`, a throwaway checkout whose `.env` carries the provider keys, and a throwaway `AMOEBA_STORE_DIR`) so no real repo is touched. On the next tick:
   - `amoeba inspect journal --project amoeba` shows one `sq_run` entry with `pipeline: p456` and no `cf_write` entry.
   - `ps` shows `sq run p456 <index> --run-id …`.
4. **Completion.** When the run completes, `amoeba inspect nodes --project amoeba` shows the slice `done`. The next slice by index gets its launch on a following tick once it is driven too: submit the same intent on the initiative node, so it covers every slice under it.
5. **Transient resume (stub).** Run `pytest tests/runner/test_tick_auto_resume.py`. The scripted run stops transiently twice, then completes. Expected: two `resume_cause: transient` entries, then `done`; with four failures at one step the fourth blocks with `auto_resume_exhausted`.
6. **Question (stub).** Run `pytest tests/runner/test_end_to_end.py -k agent_question` (it blocks the slice on a human with the question, resumes it with instructions verbatim, and the slice finishes). On a real store, `amoeba inspect blocked --json` shows `reason: agent_question` and the question text. Run `amoeba submit resolution --project amoeba --by pm --blocked-state-id <id> --detail "answered" --decision resume --instructions "Use the target branch."`. Expected: a resume entry with those instructions, and the slice proceeds.
7. **One list.** With two stub projects each holding a blocked slice, `amoeba inspect blocked` with no `--project` shows both, with `project_id` and `reason`.
8. **Gone.** `amoeba start --routing-table x` fails as an unknown flag. `amoeba inspect routing-decisions` is not a listing.

## Risk Assessment

### Technical Risks

- **Broad deletion through tested code.** 126–128 threaded fields through `ProjectView`, `LaunchRun` and the tick. A missed consumer shows up as a type error or a dead test, not a silent fault, but the work is wide.
- **Resume loops spending money.** A run that fails transiently forever would be resumed forever without D5's bound.

### Mitigation Strategies

- The Migration Plan orders the work so each task leaves a passing suite, and pyright strict catches removed fields.
- The resume bound is counted from the journal, so a restart cannot reset it. The crash harness covers a crash mid-resume.

## Implementation Notes

### Development Approach

Follow the Migration Plan order. Write the D4 and D5 tests for `supervise.py` first: they are the whole new policy. Each later task is either wiring or deletion. Rewrite `test_end_to_end.py` against a stub that serves `p456` outcomes, with a run-state script per scenario in `sq_stub_scripts.py`.

### Special Considerations

- **Effort:** 4/5. Most of it is deletion and retargeting tests.
- No secrets enter the config file or journal. `params` are pipeline parameters, and the config loader's docstring says so, as 128's did.
- Merging stays out of the Runner. A pipeline the PM configures may merge. The integration-branch rule ("never merge to `main` when one is set") is enforced by Squadron's merge step, which merges only into the CF-configured target (D9, merge row). The Runner adds one guard of its own: a fresh launch runs only on the target (D3), so a merging pipeline starts from the branch it will merge back into.

### Future Work

- **Trim the 120 arch body to the supervisor design** once this slice lands (review F005). Issue #22.
- **Retire the routing store API.** Drop the Runner-only routing-decision, table-version and attempt-count API and `awaits_routing` from 100's contract, with a migration that removes the tables once no store holds rows the PM wants. Dependencies: [132]. Effort: 1/5
- **Record every review of a multi-phase run.** A `p456` run lists three phases' reviews, and ingestion records only the last. Record each, attributed to the slice, if 140 or calibration needs the design and tasks reviews. Dependencies: [132]. Effort: 2/5
