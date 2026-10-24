---
docType: slice-design
slice: run-dispatch-and-outcome-ingestion
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 120
- 121
- 122
- 123
- 124
interfaces:
- 126
- 127
- 128
- 129
dateCreated: 20261020
dateUpdated: 20261021
status: not_started
turns: 49
promptTokens: 6628271
cachedTokens: 6393791
cacheWriteTokens: 234396
completionTokens: 67667
durationSeconds: 676.4
costUsd: 5.381559
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Run Dispatch and Outcome Ingestion

## Overview

This slice takes a pipeline step node through one phase run, from the PM's drive to evidence in the store. It is the first slice whose production planner launches anything.

- **Dispatch takes two ticks.** On the first, a journaled `cf_write` points the step's checkout at the slice (`cf set slice <index>`, run in that checkout) and reads the result back. On a later tick, once the read-back is recorded, an `sq_run` launches the step's pipeline (`P4`, `P5` or `P6`) with the slice index as its target (`sq run P4 <index>`). `P6` always gets `-p merge=false` in this slice.
- **One pipeline per checkout.** The checkout is found from CF's worktree index ranges. It is held from the pointer write until the run is neither running nor paused.
- **Ingestion.** When a run finishes, ingestion records the review behind its final verdict, the last entry of the outcome document's `reviews` list, including every part file of a split review. It uses 105's parser and the attribution rule, and marks each file `runner_issued` in the same transaction that resolves the journal entry. A paused run becomes `blocked_on_sq_checkpoint`. A failed, orphaned or vanished run becomes `blocked_on_human` with the reason.
- **Left for routing.** Every finished outcome is marked as awaiting routing, in the same transaction that resolves its entry. Nothing routes it until 126. A crash between ingestion and routing loses nothing (issue #10).
- **Reissue.** A launch that recovery marked `not_applied` is relaunched under its own run id after its launch log is checked (issue #9).

## Value

Developer value. A slice step runs end to end under Amoeba for the first time:

- The PM drives a slice, and the Runner writes CF's pointer, launches the right Squadron pipeline in the right checkout, watches it, and records what came back. Nobody runs `cf set` or `sq run` by hand.
- Every finished run becomes evidence 126 can route on: the verdict and its `standing`, the outcome document, and the blocked state. Detection does not record the review a second time, and nothing is lost to a crash.
- Two slices in one checkout never run at once, so the Runner cannot corrupt a working tree it shares with itself.

## Technical Scope

**Included**

- `amoeba.runner.dispatch`, a new subpackage:
  - `checkout.py`: resolving a slice's checkout and worktree from the latest observed CF snapshot.
  - `state.py`: a step's dispatch state, derived from its journal entries.
  - `planner.py`: `DispatchPlanner`.
  - `pointer.py`: the pointer write and its read-back.
  - `pointer_watch.py`: the check for a pointer moved during a run.
- `amoeba.runner.ingest`, a new subpackage:
  - `outcome.py`: blocked states by outcome.
  - `reviews.py`: reading, parsing and attributing the review files.
  - `record.py`: replaces the body of 122's `finish.record()`.
- Extending 120's `RunOutcomeDocument` with `checkpoint`, `failure` and `reviews` (D7). This is the one place their shape is defined.
- Contract changes to 100, landed first (D10):
  - `cf_write` gains the `checkout` key and the optional `expected_slice_index` key, and the read-back observer runs `cf get` in the checkout.
  - `record_runner_report` takes a sequence of reviews and an outcome.
  - Migration `011` adds `awaits_routing` to the journal, with `unrouted_outcomes(project_id)`. `record_routing_decision` clears the flag.
- The `not_applied` reissue with the launch-log check (D9, issue #9).
- `Action` gains `WriteSlicePointer`. `LaunchRun` gains an optional reused run id.
- New fault kinds: `checkout_unresolved`, `pointer_write_failed`, `review_unknown` and `pointer_moved`.
- `DispatchPlanner` joins the production planners, after `HumanStepPlanner`.
- Stub changes: the stub `sq` writes review files and a `reviews` list. The stub `cf` gains `set slice` and `get --json` with worktree routing.
- Contract text in `docs/store-contract.md`, `docs/process-contract.md`, `docs/evidence-contract.md`, `docs/context-forge-contract.md` and `docs/substrate-guide.md`.

**Excluded**

- **Routing (126).** That covers advance, rerun and escalate decisions, attempt counts, and the per-pipeline time bound. **The time bound moves to 126** (D12).
- **Resumes and resolutions (127).** A paused run stays blocked until 127 can resume it.
- **Gates, git and merge policy (128).** These cover the CF gate read, the clean-tree check and auto-merge. In this slice `P6` always runs with `merge=false`. **Dispatch therefore runs without the arch's clean-tree check until 128.** This follows the plan's ordering. See Risk Assessment.
- **Batch dispatch (130).**
- **Writing CF's phase pointer.** Squadron's phase step sets the phase itself (D2).
- **Killing a run,** under any condition.

## Dependencies

### Prerequisites

- **120, merged.** It provides `poll_run`, `RunOutcomeDocument`, `PARAM_RUN_ID` and the by-id observer. This slice extends the document model.
- **121, merged.** It provides migration `009`, done-terminal enforcement, the project-scoped escalation, and `record_routing_decision`, which this slice changes to clear the routing flag (D8).
- **122, merged.** It provides the tick skeleton, `TickBudget`, the `Planner` seam and Act, `launch()` with confirmation and launch logs, in-flight observation, `finish.record()`, the fault boundary, and the `checkout` key on `sq_run`.
- **123, merged.** It provides step nodes, `STEP_MAP` with the pipeline names, `CFReference.index`, the `{index}-slice.` stem rule, and migration `010`, so this slice's migration is `011`.
- **124, merged.** It provides `view.current_steps`, the current-step guard and `drives_anything()`.
- **Slice plan and arch edits for D4, D5, D11 and D12, committed before merge.** They were made together with this design, in `120-slices.runner-routing-engine.md` entries 6 and 7 and in `120-arch.runner-routing-engine.md`.
- **squadron-ai 0.23.5 or later.** This slice uses its shapes, not its version number: `sq run --run-id`, the slice as the positional target (`sq run P4 131`; Squadron rejects `-p slice=131`, found by the live walkthrough, 20261024), `-p merge=false`, and `sq runs wait --json` with `checkpoint`, `failure` and `reviews`.
- **Context Forge** as `cf`, with the worktree routing observed on CF 0.19.16 on 20261020 (Interfaces Required).

### Interfaces Required

**Squadron** (observed in source on 20261020):

- `P4`, `P5` and `P6` each require the `slice` param. Each phase step begins with `cf set slice {slice}` and `cf set phase {n}`, run from the run's working directory (`pipeline/steps/phase.py`, `actions/cf_op.py`). `P6` declares `merge: "true"` and merges unless it is passed `merge=false`.
- The outcome document (`pipeline/run_outcome.py`, `docs/COMMANDS.md`):
  - `checkpoint`: `{kind, step, step_type, is_loop, round, max_rounds, verdict, review_file, reason, paused_at}`. `kind` is one of `loop_exhausted`, `interactive_checkpoint`, `awaits_human` or `other`.
  - `failure`: `{kind, step, message}`. `kind` is one of `provider_error`, `stall`, `artifact_missing` or `cost_cap`.
  - `reviews`: a list of `{path, paths, template, verdict, step, round}` in the order written. `paths` lists the part files of a split review, and is otherwise null.
  - Any null field means unknown.
- Review files are overwritten in place. The earlier content is copied to `reviews/archive/` first, which detection does not scan, because it scans top level only.

**Context Forge** (CF 0.19.16 source, confirmed read-only on 20261020):

- `cf set` and `cf get` with `-p <id>` choose the worktree from the process working directory. The worktree whose `worktreePath` is the longest prefix of the working directory wins. A working directory that matches no worktree goes to the project level, whose pointers are empty on a worktree-scoped project. **The working directory of the call decides where a pointer write lands.**
- `cf set slice <index>` stores the stem `NNN-slice.{name}`. The name is taken from the design file when one exists, and otherwise built from the slice-plan entry. Setting the slice also sets `fileTasks`. A slice with no plan entry exits non-zero (`ARTIFACT_NOT_FOUND`). A value that is already set writes nothing.
- `cf get --json` run in a worktree reports that worktree's pointers at the top level (`fileSlice`, `projectPath` = `worktreePath`), plus a `worktree` object with its `id`. `updatedAt` is the project's, and any write to any worktree bumps it.
- CF chooses a worktree only by working directory, never by slice index. Each worktree has an `indexRange`.

**Store and process:**

- `latest_cf_snapshots(project, link)`, whose projection (108) holds `projectPath` and, for each worktree, `worktreePath`, `indexRange` and `activeSlice`.
- `journal_issue`, `journal_resolve`, `journal_escalate`, `journal_entries(project, node_id=…)`, `unresolved_journal_entries`, `block`, `blocked`, `update_cf_reference`, `watches`, and `attribute_review`.
- 105's `parse_review_artifact` and `to_verdict_input`.
- 120's `version_label` capture of `sq --version`.

## Architecture

### Component Structure

```
amoeba/runner/dispatch/          NEW
  checkout.py      resolve_checkout(snapshot, slice_index) → Checkout | CheckoutUnresolved
  state.py         DispatchState, dispatch_state(entries) (pure)
  planner.py       DispatchPlanner: WriteSlicePointer | LaunchRun per current pipeline step
  pointer.py       issue_pointer_write(), read_back() (shared with the recovery observer)
  pointer_watch.py pointer_moved(in_flight, snapshots) (pure)
amoeba/runner/ingest/            NEW
  outcome.py       FinishedRun → BlockPlan (kind, context, payload) | none
  reviews.py       last review entry → ReviewFiles | ReviewUnknown (read, parse, attribute)
  record.py        ingest(store, finished) — block, then record_runner_report
amoeba/runner/
  decide.py        CHANGED  Action += WriteSlicePointer; LaunchRun.run_id, .reissue_of
                            ProjectView += dispatch facts per current pipeline step, held checkouts
  tick.py / act    CHANGED  pointer read-backs in observe; pointer-move check; act for both actions
  finish.py        CHANGED  delegates to ingest.record
  launch.py        CHANGED  reissue: log check, poll, then 122's launch
  faults.py        CHANGED  FaultKind += checkout_unresolved, pointer_write_failed,
                                         review_unknown, pointer_moved
  factory.py       CHANGED  PRODUCTION_PLANNERS = (HumanStepPlanner(), DispatchPlanner());
                            captures the sq version label once at start
amoeba/process/
  sq_outcome.py    CHANGED  RunCheckpoint (all fields), RunFailure, RunReview; CheckpointKind,
                            FailureKind
  observers/cf_readback.py  CHANGED  cwd = checkout; expected_slice_index (D10);
                            read_back_cf_write(), the one comparison
  observers/cf_get.py       NEW      the `cf get --json` read and its parse (split out)
  review_scan.py            CHANGED  ledger_key(), detection_key() (D7, D10)
amoeba/upstream/context_forge/
  slice_stem.py    NEW      parse_slice_stem(), the one `{index}-slice.` rule (D2, D10)
amoeba/store/
  schema/011_journal_awaits_routing.sql   NEW
  journal.py / runner_report.py / routing_decisions.py   CHANGED  (D8, D10)
  journal_models.py   CHANGED  cf_write required keys + checkout
amoeba/inspection/  journal listing shows awaits_routing
```

### Data Flow

Within one project's tick, using 122's skeleton with 123's and 124's stages:

```
apply intents (124)
observe   in-flight sq_run entries (122)                          ── poll, confirm
          unresolved cf_write entries, and current POINTED steps → read_back()   ── cf get in the checkout
          pointer_moved() for each in-flight run                  ── store snapshot read only
plan read / reconcile (123)
record    each finished run → ingest.record()                     ── replaces 122's body
[route — 126 reads unrouted_outcomes]
decide    view: current steps (124), dispatch state per step, checkouts, held checkouts
          DispatchPlanner → WriteSlicePointer | LaunchRun          ── at most one per checkout
act       WriteSlicePointer: journal cf_write → cf set slice → read_back → resolve
          LaunchRun: (reissue: log check, poll) → journal sq_run → 122's launch
```

**One step, end to end:**

```
tick n    decide: step S current, NEEDS_POINTER, checkout C free  → WriteSlicePointer
          act:    journal cf_write {project, checkout C, expected {}, expected_slice_index i}
                  cf set -p <cf> slice <i>   (cwd C)
                  cf get --json -p <cf>      (cwd C) → index i, worktree W, projectPath C
                  resolve completed {cf_updated_at, file_slice, worktree_id, project_path}
                  slice node cf.slice_name ← stem name, if it differs
tick n+1  decide: S POINTED, C still free → LaunchRun(P4|P5|P6, {slice: i[, merge: false]}, C)
          act:    122: mint id, journal sq_run, detached launch in C
tick …    observe: confirm, poll; pointer_moved check against W
tick m    observe: outcome ≠ still running → finished
          record:  block (if the outcome needs one) → record_runner_report(entry,
                   reviews, outcome, result)   ── one transaction, sets awaits_routing
tick m+1  decide: S AWAITING_ROUTING → no action; 126 routes it
```

### State Management

- **Durable, in the store. Nothing new is held in memory.**
  - The dispatch state of a step is derived from its own journal entries (D3).
  - A run's outcome document, checkpoint and recorded verdict ids are in its `sq_run` entry's `result` (D6).
  - Routing work is the `awaits_routing` flag on resolved entries (D8).
  - Checkouts and worktrees come from the latest observed CF snapshot (D1).
- **Per tick, in memory:** the held-checkout set and each current step's dispatch facts, built when the view is built and never cached across ticks.
- **No node status is written at dispatch.** A step stays `runnable` while its run is in flight. In flight means "has an unresolved entry", as 122 defines it (D3).

## Technical Decisions

### D1 — The checkout comes from CF's worktree ranges, read from the snapshot store
Status: decided
- A slice runs in the checkout of the CF worktree that owns its index. CF chooses a worktree only by working directory (Interfaces Required), so the Runner must run every `cf` and `sq` call for a step in that worktree's path.
- `resolve_checkout(snapshot, slice_index)` reads the link's latest **observed** snapshot from `latest_cf_snapshots`. That is a store read, with no subprocess:
  - **The project has worktrees.** Exactly one worktree whose `indexRange` contains the index, with a non-empty `worktreePath`, gives `Checkout(path, worktree_id)`.
  - **The project has no worktrees.** The project's `projectPath` gives `Checkout(path, worktree_id=None)`.
  - **Anything else** gives `CheckoutUnresolved(reason)`. That covers no observed snapshot, no range containing the index, several ranges containing it, a missing path, or a path that is not an existing directory.
- `CheckoutUnresolved` for a current step blocks the step on `HUMAN` with `{fault_kind: checkout_unresolved, index, reason}`. No run is in flight, so a node block is right (122, D8). Unknown escalates, and no checkout is guessed.
- **The read-back confirms it.** After the pointer write, the read-back's `projectPath` must equal the resolved path, and `worktree.id` must equal the worktree id, or be absent when the project has no worktrees. A mismatch is a failed pointer write (D2). So a stale snapshot cannot silently send a run to the wrong tree.
- Rejected: a `cf worktree list --json` read per tick. The snapshot already holds the same fields, and 108 keeps it current within one scan interval.

### D2 — The pointer write sets the slice only, in the checkout, and is checked by index
Status: decided
- **Why the Runner writes a pointer when Squadron also sets it.** Squadron's phase step runs `cf set slice` itself. The Runner still writes first, for two reasons that hold before any run starts. The read-back gives the slice's CF stem, which sets `cf.slice_name` for attribution on a slice that has no design file yet (123, D2). And 128's gate read needs CF's active slice to be this slice before it reads `activeSlice.status`.
- **The command:** `cf set -p <cf_project_id> slice <index>`, with `cwd=checkout`, under `TickBudget` and `tick_call_timeout_seconds`. The Runner does not write the phase, because Squadron's phase step sets it when it starts. One journaled command is one CF write.
- **Journal parameters** (`cf_write`):
  - `project`: the CF project id.
  - `checkout`: the absolute path. It is the working directory of the write and of every read-back.
  - `expected`: `{}`.
  - `expected_slice_index`: the index.

  An exact `fileSlice` value cannot be expected, because CF builds the stem itself. Amoeba never builds a slug (123, D2). So the check is by index, which is the node's link key (123, D1).
- **Read-back:** `cf get --json -p <cf_project_id>`, run in the checkout. It applies 120's observer rule plus the new key (D10). The index is parsed from `fileSlice` with 123's `{index}-slice.` stem rule, which is defined once.
  - **Equal**, with D1's path and worktree check passing: the entry resolves `completed`, with result `{cf_updated_at, file_slice, worktree_id, project_path}`. If the slice node's `cf.slice_name` differs from the stem's name, it is set through `update_cf_reference`.
  - **A different index, or a path or worktree mismatch:** the step blocks on `HUMAN` with `pointer_write_failed`, and the entry resolves `failed`.
  - **An absent field, or a `fileSlice` that does not parse:** the observer answers `Unknown` (D10). The entry goes through `journal_escalate` at once, which blocks the node on `HUMAN`, exactly as recovery would.
  - **A read that fails** (timeout, non-zero exit, non-JSON): this is transient. The entry stays unresolved, and the next tick's Observe reads back again. Once `launch_grace_seconds` has passed since the entry's `issued_at` and the read still fails, the entry goes through `journal_escalate` with the last failure as its reason. The bound reuses the existing confirmation setting, so no new setting is needed. Until then the unresolved entry holds the checkout (D4), and the bound is what stops that hold from lasting forever.
- **`cf set` exits non-zero** (for example `ARTIFACT_NOT_FOUND`): the entry resolves `failed`, and the step blocks on `HUMAN` with `pointer_write_failed` and the head of CF's stderr, bounded like 122's tail. Nothing is retried within the tick.
- **A cut-off between `cf set` and the read-back** leaves the entry unresolved. The next tick reads back. The write is idempotent, so recovery after a crash works the same way, through the same function (D10).
- **`cf set` exceeds `tick_call_timeout_seconds`.** The write may or may not have landed, so this is handled as a cut-off: the entry stays unresolved, and the next tick reads back under the rules above. A write that landed resolves `completed`. A write that did not land reads back another index, so the step blocks with `pointer_write_failed` and the entry resolves `failed`. It is not retried, because v1 escalates every fault. Resolving the block makes the step `NEEDS_POINTER`, which writes the pointer again (D3).

### D3 — A step's dispatch state is derived from its own journal entries
Status: decided
- `dispatch_state(entries)` is pure. It looks at the step's entries, oldest first (`journal_entries(project, node_id=step)`). History per step is bounded by the attempt limit, so the read is small. It returns one of:

  | State | When | Planner does |
  | --- | --- | --- |
  | `IN_FLIGHT` | Any unresolved entry. | Nothing. |
  | `AWAITING_ROUTING` | The latest `sq_run` entry has `awaits_routing` (D8). | Nothing. 126 routes it. |
  | `REISSUE` | The latest entry is an `sq_run` that recovery resolved `not_applied`. | `LaunchRun` reusing its run id (D9). |
  | `POINTED` | The latest entry is a `cf_write` resolved `completed` or `adopted`, and CF still points at the step's slice. | `LaunchRun`, if the checkout is free. |
  | `NEEDS_POINTER` | Anything else: no entries, a failed pointer write, an `sq_run` already routed, or one recovery resolved `unknown` or `adopted`. | `WriteSlicePointer`, if the checkout is free. |

- **"CF still points at the step's slice"** is checked by reading CF, not a snapshot. The CF watch writes a snapshot only when the projection changes (`context-forge-contract.md`, "What the watch records"), so a pointer write that changed nothing would never be followed by one.
  - In Observe, each current step whose journal says `POINTED` gets one read-back, under `TickBudget`. This is D2's `cf get` in the checkout, the same function.
  - The index matches: the step is `POINTED`, and launches in the same tick, with no wait for a scan.
  - Any other answer (another index, an absent field, or a failed read): the step is `NEEDS_POINTER`, and writes its pointer again. That new write's read-back follows D2's bounded rules, so a CF that keeps failing escalates rather than looping.

  So a launch, and 128's gate read before it, always follow a pointer that CF held in this tick.
- A step can only be current (124) when it is `runnable`. A blocked step therefore never reaches the planner, and the states above apply after the PM resolves a block. For example, after a failed pointer write is resolved, the step writes the pointer again.
- **No `started` status.** A step stays `runnable` while its run is in flight, and "in flight" stays what 122 defines: an unresolved entry. Writing `started` would add a second marker of in-flight state, with a crash window between the launch and the status write. **This settles 122's "125 decides how a node looks while its run is in flight".**

### D4 — One pipeline per checkout, held from the pointer write
Status: decided
- A checkout is **held** when any of these is true:
  - An unresolved `sq_run` entry in the project has that `checkout`.
  - A node that is not `done` has a latest `sq_run` entry with that `checkout` whose recorded outcome is `paused`. A paused run still has its branch checked out. The rule reads the run's outcome, not the block kind, so a paused run whose review was unknown (D7), which is blocked on `HUMAN`, still holds its checkout. A later `sq_run` entry on the node releases it: 127's resume, or a re-observation that finds the run no longer paused.
  - A current step in that checkout is `POINTED` or `IN_FLIGHT` on a `cf_write`. Its claim starts with the pointer write.
- The planner emits at most one action per checkout per tick. Candidates in a free checkout are ordered with `POINTED` and `REISSUE` steps first, then by `(initiative index, slice index, step rank)`. So a step that has already written its pointer launches before another step writes over it.
- **A pointer claim lapses when its step stops being current,** through hold, exclude or a block. Another step may then write the checkout's pointer. A step is `POINTED` only while CF still points at its slice (D3), so if the first step becomes current again after another write, it writes its pointer again before it launches. A paused or in-flight run never lapses. Only the run ending releases its checkout.
- **This departs from the arch's "held from launch".** The hold starts at the pointer write, so that no second step writes over a pointer between the write and the launch.
- Hold is computed across the project, not only over current steps. A held or excluded slice's run in flight or paused still holds its checkout.
- Checkouts in different projects are never compared. One path linked by two Amoeba projects is the PM's configuration, and is out of scope in v1.

### D5 — Pipelines and params are defined once
Status: decided
- The pipeline comes from 123's `STEP_MAP`. The params are built by one function, `dispatch_params(step, slice_index)`:
  - every pipeline step: `{"slice": "<index>"}`, which `build_argv` passes as the positional target (Squadron rejects it as `-p slice=<index>`);
  - `implementation` (`P6`): also `{"merge": "false"}`.
- **`merge=false` always, in this slice.** `P6` declares `merge: "true"`. Without the param, the first production `P6` would merge, which breaks "merging is a human step by default". 128 replaces the fixed value with the per-project merge policy. The param key and value are defined once, beside `dispatch_params`.
- Other params (models, revision limits) are not passed. Squadron's pipeline defaults apply. Choosing them is configuration for a later slice, not dispatch.

### D6 — Ingestion: block, record the last review, resolve, in that order
Status: decided
- `ingest.record(store, finished)` replaces 122's minimal body. It keeps 122's order, which is idempotent on re-entry: block (skipped if the node is already blocked), then one `record_runner_report` call that records the reviews and resolves the entry.
- **The block, by outcome:**

  | Outcome | Block | Entry |
  | --- | --- | --- |
  | `completed` | none | `completed` |
  | `paused` | `SQ_CHECKPOINT`, context `paused: <kind> at <step>, run <run_id>` | `completed` |
  | `failed` | `HUMAN`, payload `{reason: failed, run_id, failure}` | `completed` |
  | `orphaned` | `HUMAN`, payload `{reason: orphaned, run_id}` | `failed` |
  | `not_found` after confirmation | `HUMAN`, payload `{reason: vanished, run_id}` | `failed` |

  `failure` covers cost-capped (`cost_cap`), stalled (`stall`), provider errors and an unknown (null) kind, all as reported. The plan's "timed out" is Squadron's `stall`. With `--timeout 0`, `timed_out` means still running, which 122 already treats as in flight. `unreadable`, `unknown_status` and a `PollFailure` stay 122's per-tick faults, and are not finished runs.
- **A checkpoint block's data lives in the entry.** The store keeps a payload only for blocks that escalate, so an `SQ_CHECKPOINT` block carries no payload. The run id and checkpoint are in the `sq_run` entry's result, and 127 finds them through the node's latest `sq_run` entry. The context names the run id for people only.
- **Result:** `{run_id, outcome, status, outcome_document, verdict_ids, review_fault}`.
  - `outcome_document` is the polled document, verbatim.
  - `verdict_ids` lists the recorded verdicts in part order. It is empty when there was nothing to record.
  - `review_fault` is null, or the `ReviewUnknown` reason (D7).
  - This result is 126's input for the run, and 127's source for resuming a paused run.
- **Every outcome with a run state is ingested the same way,** whether it completed, paused, failed or was orphaned. A paused run's last review is the review behind its checkpoint verdict. Detection must not take that file as external either.
- **A crash anywhere** leaves the entry unresolved, and recovery leaves it in flight (122, D3). The next tick polls the run again and repeats `ingest.record`. The block is skipped, and the verdict ids are the parsed-content digests, so recording again is `record_verdict`'s retry, a no-op.

### D7 — Which review files are recorded, and how they are attributed
Status: decided
- **Selection.** The last entry of `reviews`. If its `paths` is non-null, every listed part file is recorded, in order. Otherwise its `path` is recorded. An empty list records nothing. This is the plan's rule.
- **Each file:**
  - A relative path is resolved against the run's `checkout`.
  - The file is read once, whole. The digest is sha256 of the bytes read. No size bound is applied, as in detection, because a truncated read would digest differently from detection's key.
  - The file is parsed with 105's `parse_review_artifact`. `to_verdict_input` adds `sq_run_id` (the run id), `journal_entry_id=None`, and provenance `{upstream: squadron, source: artifact_frontmatter, source_path}`. The version label is the file's `squadronVersion` stamp, or the `sq --version` label the factory captured once at start, or the explicit `unavailable` marker. This is detection's rule.
- **Attribution.** `attribute_review(slice nodes, review.slice)` must return exactly the slice node that is the run's step's parent. This applies the rule the evidence contract makes binding on 120, and checks it against the node the Runner knows.
- **`ReviewUnknown`.** Any of these makes the whole run's review unknown, and nothing is recorded:
  - a selected entry with a null `path` and null `paths`;
  - a file that is missing, unreadable or unparseable;
  - attribution to no node, to several, or to a different node.

  If no outcome block applies, the step blocks on `HUMAN` with `{fault_kind: review_unknown, path, reason}`. If one does (a failed run, for example), that block stands, with `review_fault` added to its payload. The one exception is a pause. An unknown review on a paused run blocks on `HUMAN` instead of `SQ_CHECKPOINT`, because a checkpoint block posts no message and the PM must be told. The entry still resolves, and is still left for routing.
- **Why the verdict's `journal_entry_id` is null.** `record_verdict` requires a given entry to be on the verdict's own node. The run is journaled on the step node, which is the work item: it carries attempt counts, blocks and the done guard. The verdict goes to the slice node, which is the attribution rule's target and where detected rounds of the same slice already live. The run is linked to the verdict both ways instead. `sq_run_id` is on the verdict, and `verdict_ids` is in the entry's result. The evidence contract's sentence "a Runner journals a review command on the node the review is of" is updated to say this.
  - Rejected: journaling on the slice node. Blocks, attempts and the done guard would then sit on a node that is not the work item, and one slice's design, tasks and code runs would share one node's in-flight state.
  - Rejected: relaxing `record_verdict`'s check to allow a child's entry. It would change a 104 invariant to carry a link the run id already carries.
- **Verdict ids are content digests, not minted.** 100's retry rule keys on the record id, and evidence contract D5 point 5 requires the Runner's id to be 105's parsed-content digest, the same id detection computes. So the Runner does not mint verdict ids at journal time. The arch sentence saying it does ("Run identity") is corrected with this design.
- **The detection key is computed by detection's own code, not reimplemented.** Today detection builds the key inside its directory source, as the watch directory joined with the file name, with `content_digest` in `review_scan.py`. D10 moves the key into one exported function, `detection_key(watches, file, content) -> (path, digest) | None` (`content` is the bytes already read, so the file is read once). `review_scan.examine` forms detection's key through the same `ledger_key` helper, and ingest calls `detection_key`. (`DirectoryReviewSource` is in `store/`, which Rule 1 bars from importing `amoeba.process`, so the source itself cannot call it.) `None` means no watch covers the file. Detection never sees such a file, and ingest then keys it by the resolved absolute path. A test asserts that detection and ingest produce the same key for one file.

### D8 — Unrouted outcomes are a flag set at resolution (issue #10)
Status: decided
- Migration `011` adds `command_journal.awaits_routing INTEGER NULL` and a partial index on `(project_id, issued_at) WHERE awaits_routing = 1`.
- **Set by the store, not by callers.** Every issuer resolution of an `sq_run` entry sets the flag in the same transaction, through `journal_resolve` and `record_runner_report`. That includes 122's launch failures. Recovery resolutions (`adopted`, `not_applied`, `unknown`) do not set it, because the Runner did not observe an outcome. Rows before `011` stay null.
- **Cleared by the decision.** `record_routing_decision` clears the flag on its `journal_entry_id` in its own transaction. So "unrouted" and "has no decision record" cannot disagree, and a crash between ingestion and routing leaves the flag set.
- **Read:** `unrouted_outcomes(project_id) -> list[JournalEntry]`, oldest first, served by the partial index. Its cost is bounded by unrouted work, not by history, which is the bound issue #10 asks for. 126 consumes it. In this slice, the only reader is `dispatch_state` (`AWAITING_ROUTING`) and the tests.
- Rejected: a query joining resolved entries to `routing_decisions`. It scans history every tick, which is the reason 121 deferred it.
- Rejected: marking the step `started` until it is routed (D3).

### D9 — Reissuing a `not_applied` launch (issue #9)
Status: decided
- A step is `REISSUE` when its latest entry is an `sq_run` that recovery resolved `not_applied`, meaning there was no run state after the launch grace period (120, D4). The planner emits `LaunchRun(…, run_id=<old id>, reissue_of=<old entry>)`. It goes through the current-step guard and the checkout filter like any launch.
- **Act, in order:**
  1. **Launch-log check,** on the old entry's `<entry_id>.stderr.log` (122, D4). This is a local read, with no subprocess. It is 122's exact-line check, bounded by its 64 KiB head limit, because Squadron prints the line before its first step.
     - An exact `run_id=<id>` line: the run started and its state was later removed, for example by pruning. The step blocks on `HUMAN` with `{reason: started_before_crash, run_id}`. Nothing is launched.
     - A log that exists and cannot be read: the step blocks on `HUMAN`, naming the error. Nothing is launched.
     - No log, or a readable log without the line: Squadron prints the line before its first step, so no work ran. Continue.
  2. **Journal** a new `sq_run` entry with the same `pipeline`, `params`, `checkout` and `run_id`, plus `reissue_of`. The old entry has no result, so 120's claimed-id guard does not refuse the id.
  3. **Poll once.** If a run state exists, the late run is adopted. The new entry is confirmed and in flight, and nothing is launched.
  4. **Not found:** launch through 122's `launch()`. If Squadron refuses the id because a run appeared in between, the child exits without the line. 122's D6 then polls once and finds the state, so the run is observed rather than failed.
- The pointer is not re-written. The reissue relaunches the same command, and Squadron's phase step re-sets the slice pointer itself.
- The new entry's own launch log is named by its own entry id (122, D4), so the evidence of the first attempt is kept.

### D10 — Contract changes to 100, landed before Runner code
Status: decided
- **`cf_write`:**
  - `checkout` joins `REQUIRED_PARAMETER_KEYS[CF_WRITE]`, which becomes `{project, expected, checkout}`. A new entry without it is refused, for the reason 120 (D1) made `run_id` required: an issuer that drops it writes to the wrong CF level without any error.
  - `expected_slice_index` is optional. It is set only for pointer writes.
  - The observer runs `cf get --json -p <project>` with `cwd=checkout` when the key is present, and with no working directory for entries written before this slice.
  - When `expected_slice_index` is present, `fileSlice` must parse by the stem rule to that index. A different index is `NotApplied`. A field that is absent or does not parse is `Unknown`.
  - **An entry with an empty `expected` and no `expected_slice_index` is `Unknown`.** Comparing nothing would otherwise adopt vacuously.
  - Adoption also records `file_slice`, `worktree_id` and `project_path`.
  - The in-tick read-back (D2) calls this same function. There is one read-back.
- **`record_runner_report(entry_id, reviews, *, outcome, result)`.**
  - `reviews` is a `Sequence[RunnerReview]`, where `RunnerReview(verdict, detection)`. It may be empty.
  - `outcome` is `completed` or `failed`. Any other value raises `ValueError`.
  - It is still one transaction: the checks, every verdict and ledger row in order, then the resolution, which sets `awaits_routing` (D8).
  - Each review's checks are the existing ones. Any failure writes nothing.
  - Callers updated: the stand-in Runner and the store tests.
  - Rejected: a second method beside the single-review one. Two methods would do one job.
- **Migration `011`**, `unrouted_outcomes`, and the flag clearing in `record_routing_decision` (D8).
- **`detection_key(watches, file, content)`**, defined in `amoeba.process.review_scan` next to `content_digest` and exported from `amoeba.process`. It and `examine` (and the baseline) form detection's ledger key through one helper, `ledger_key(path, content)` (D7). Behaviour is unchanged. An agreement test runs detection and ingest over the same file.
- **Order.** These land as this slice's first code tasks, with their contract tests, the contract suite and their contract text updated, before any dispatch code. D7's change to the evidence contract's journal-node sentence lands with them. This follows 122 D3's precedent and the arch's "the contract changes first".

### D11 — Pointer moves during a run escalate at project scope, while they last
Status: decided
- The plan says that a pointer someone else moves away from a node with a run in flight escalates that node. But 122 (D8) blocks a node with a run in flight only when its run ends. A block written mid-run would also make the run's own outcome block (D6) a no-op, so a paused run would lose its `SQ_CHECKPOINT` state.
- **So:** for each in-flight run, Observe reads the latest observed snapshot recorded after the run's pointer write resolved. That is a store read, ordered by the snapshot's `recorded_at`. The run's worktree is the `worktree_id` in the pointer write's result, or the project level when there are no worktrees. If that worktree's `activeSlice` (or `fileSlice`) parses to a different index, the condition holds.
  - It raises a project-scoped `pointer_moved` escalation. The payload lists every in-flight run whose pointer has moved at the time it is raised, each as `{node_id, run_id, worktree_id, observed}`.
  - **Accepted limit in v1:** the escalation is deduplicated on project and fault kind (121), so a run whose pointer moves while the escalation is already open does not appear in it until the escalation closes and is raised again.
  - It counts as a recurrence while the condition holds, so the escalation stays open, and it closes on the first complete tick where the condition is gone. This is 122's closure rule with 123's recurrence pattern.
  - The run is observed and ingested as usual. 126 routes its outcome.
- **No match by `cf_updated_at`.** The plan says the Runner recognizes its own writes by D8's `cf_updated_at`. The move rule never needs that:
  - The Runner writes a pointer only into a free checkout (D4), so its own writes never move a pointer away from a run.
  - Snapshots recorded after the pointer write's resolution were taken after that write, because the CF watch and the Runner tick in one process, one after the other.
  - Squadron's own `cf set slice` during the run writes the same index.

  `cf_updated_at` is still recorded in the result as provenance. **This departs from plan entry 6.** The entry is reworded.

### D12 — The per-pipeline time bound moves to 126
Status: decided
- The arch puts per-pipeline time bounds in the routing table. That table, its file format and its loading are 126's. If this slice enforced a bound, it would need a value source with no home before 126, which would be a second place routing values live. A run in flight also cannot block its node mid-run (D11). How an overrun is surfaced is therefore a routing choice too.
- 126 computes a run's age from the `sq_run` entry's `issued_at`, so this slice records nothing extra for it (126, D7).
- **Consequence until 126 lands:** a hung run holds its checkout indefinitely. It is visible as an unresolved entry and is never killed. Nothing launches without a PM drive, so the gap costs at most the runs the PM drives before 126 merges, and the pause intent stops new launches at once (Risk Assessment).
- **The plan edit is a prerequisite, already met.** Plan entries 6 and 7 were edited together with this design: the time bound moved from 125's text to 126's, and 126 has a success criterion for it (Prerequisites). 129 depends on 126, so no proof runs without the bound.

### Technology Choices

- Standard library `subprocess` (through 122's injected runner), `hashlib` and `pathlib`, plus pydantic v2 for the outcome document. There are no new dependencies.
- The automated tests never run the real `sq` or `cf`. The stub `sq` run mode writes review files into the checkout and lists them in its outcome document's `reviews`, including a split review and an unsaved one. The stub `cf` keeps a fixture `projects.json`-shaped state. Its `set slice` and `get --json` route by working directory and `indexRange`, using fixture outputs captured from CF 0.19.16, as the parser rule requires.

### Patterns and Conventions

- Each of these is defined once:
  - `DispatchState`;
  - the `slice` and `merge` param keys and the `false` value;
  - the new `FaultKind` members;
  - `CheckpointKind` and `FailureKind`;
  - the `cf_write` key names `checkout` and `expected_slice_index`;
  - the result keys `outcome_document`, `verdict_ids`, `review_fault`, `worktree_id` and `project_path`;
  - the block reasons `failed`, `orphaned`, `vanished` and `started_before_crash`.
- `CheckpointKind` and `FailureKind` are `StrEnum`s. The document model keeps the raw text (`str | None`), and a parse function returns a member or an explicit unknown carrying the raw value. An unrecognized kind never fails a poll and is never mapped to a near match.
- `dispatch_state`, `resolve_checkout`, `pointer_moved`, the planner and the outcome-to-block mapping are pure, and table-tested without I/O.
- Expected external failures are answers (`CheckoutUnresolved`, `ReviewUnknown`, a failed pointer write), never exceptions. Unexpected ones reach 122's one catch.
- Modules stay under about 300 lines, and functions under about 50.

## Implementation Details

### Database / Storage Schema

Migration `011_journal_awaits_routing.sql`:

```sql
ALTER TABLE command_journal ADD COLUMN awaits_routing INTEGER;
CREATE INDEX idx_journal_awaits_routing
    ON command_journal (project_id, issued_at) WHERE awaits_routing = 1;
```

It applies to a populated v10 store. Existing rows read null, meaning not awaiting routing.

### API Contracts

**Store** (`docs/store-contract.md`):

| Method | Change |
| --- | --- |
| `journal_issue` | `cf_write` requires `checkout`. `expected_slice_index` is optional. |
| `journal_resolve` | An issuer resolution of an `sq_run` sets `awaits_routing`. |
| `record_runner_report(entry_id, reviews, *, outcome, result)` | Takes a sequence of reviews and the outcome, and sets `awaits_routing`. |
| `unrouted_outcomes(project_id)` | New. Entries with `awaits_routing`, oldest first. |
| `record_routing_decision(...)` | Clears `awaits_routing` on its entry, in its own transaction. |

`JournalEntry` gains `awaits_routing: bool`. `amoeba inspect journal` shows it, and `--json` carries it.

**Outcome document** (`amoeba.process`, extending 120):

```python
class RunCheckpoint(BaseModel):   # every field optional; None means unknown
    kind: str | None; step: str | None; step_type: str | None; is_loop: bool | None
    round: int | None; max_rounds: int | None; verdict: str | None
    review_file: str | None; reason: str | None; paused_at: datetime | None
class RunFailure(BaseModel): kind: str | None; step: str | None; message: str | None
class RunReview(BaseModel):
    path: str | None; paths: list[str] | None; template: str | None
    verdict: str | None; step: str | None; round: int | None
# RunOutcomeDocument += checkpoint: RunCheckpoint | None, failure: RunFailure | None,
#                       reviews: list[RunReview] | None
```

**Runner, internal:**

```python
class DispatchState(StrEnum): IN_FLIGHT; AWAITING_ROUTING; REISSUE; POINTED; NEEDS_POINTER
@dataclass(frozen=True)
class WriteSlicePointer: node_id: str; cf_project_id: str; slice_index: int; checkout: Checkout
@dataclass(frozen=True)          # 122's LaunchRun, extended
class LaunchRun: node_id: str; pipeline: str; params: Mapping[str, str]; checkout: Path
                 run_id: str | None = None; reissue_of: str | None = None
type Action = LaunchRun | BlockHumanStep | WriteSlicePointer
```

## Integration Points

### Provides to Other Slices

- **126:**
  - `unrouted_outcomes`, and the flag that a decision clears.
  - Each outcome's entry result: the outcome document, the verdict ids and the review fault.
  - The blocked state ingestion already wrote.
  - `CheckpointKind` and `FailureKind` as routing inputs.
  - The unresolved `sq_run` entry and its `issued_at`, for the time bound (D12).
  - A completed run leaves its step `runnable`, with the outcome awaiting routing. Advance marks the step done, and rerun records its decision, which makes the step `NEEDS_POINTER` again.
  - **The interface 126 must handle:** a paused run's node is already `blocked_on_sq_checkpoint`, and a failed run's node is already blocked on `HUMAN`. An escalate decision on such a node needs no second block (121's `effect=None`).
- **127:**
  - A paused node's run id and checkpoint, read through its latest `sq_run` entry.
  - **A paused run is recognized by its entry's recorded outcome, not by the block kind.** A paused run whose review was unknown is blocked on `HUMAN` (D7), but its entry still holds the checkpoint. 127 offers the paused-run resolutions (retry, accept, handled, stop) for any node whose latest `sq_run` outcome is `paused`, whichever block it carries.
  - `LaunchRun` and 122's launch, for the resume command.
  - The checkout hold, which a resumed run keeps.
- **128:**
  - `dispatch_params`, where the merge policy replaces the fixed `merge=false`.
  - The `POINTED` state, as the point to check gates and the clean tree before `LaunchRun`. `POINTED` holds only when that tick's read-back shows CF pointing at the node's slice (D3), so a gate read at that point reads this slice's `activeSlice.status`. 128 still checks `activeSlice.index` in its own `cf status` read, because the pointer can move between the two reads.
- **129:** the first real dispatch path, and `inspect journal`'s `awaits_routing` for the write-up.
- **Contract documents:**
  - `store-contract.md`: `cf_write` keys, `record_runner_report`, migration `011`, `unrouted_outcomes`, and the decision clearing the flag.
  - `process-contract.md`: the read-back's working directory and index check, the dispatch and ingest stages, and the checkout hold.
  - `evidence-contract.md`: the Runner's journal and verdict nodes (D7), and multi-part recording.
  - `context-forge-contract.md`: where a write lands, and the pointer-move rule (D11).
  - `substrate-guide.md`: the 120 row, and issues #9 and #10 closed.

### Consumes from Other Slices

- **120:** `poll_run`, the document model it extends, and the by-id observer.
- **121:** `record_routing_decision`, changed to clear the flag, the project-scoped escalation, and done enforcement.
- **122:** the skeleton, `TickBudget`, `launch()`, confirmation, launch logs, faults and closure.
- **123:** `STEP_MAP`, step and slice nodes, `CFReference.index`, the stem rule, and `update_cf_reference` for `slice_name`.
- **124:** `current_steps` and the guard, and the Observe scope predicate, `drives_anything()` or a run in flight.
- **105 / 106:** the parser, the attribution rule, and the detection key.
- **108:** `latest_cf_snapshots`, with `projectPath`, worktrees, `indexRange` and `activeSlice`.

## Success Criteria

### Functional Requirements

- **Two-tick dispatch:**
  - A driven `slice_design` step gets a `cf_write` on one tick, with `checkout` and `expected_slice_index`, and an `sq_run` of `P4` with the slice index as its target (`sq run P4 <index>`) on a later tick, in that checkout.
  - With the step held or not driven, neither is issued.
  - A `P6` launch always carries `-p merge=false`.
- **The pointer lands in the right worktree.** With a stub CF holding two worktrees, the write runs in the worktree whose range holds the index. The read-back confirms its index, path and worktree id, and the slice node's `slice_name` is set from the stem.
- **Pointer failures:** `cf set` exiting non-zero, a read-back with another index, and a path or worktree mismatch each block the step with `pointer_write_failed` and resolve the entry `failed`. A read-back cut off by the deadline is completed on the next tick. A read-back with an absent field escalates at once. One that keeps failing escalates once `launch_grace_seconds` has passed since the entry was issued.
- **An already-pointed checkout:** when CF already points at the slice, so that `cf set` writes nothing and no snapshot follows, the step still launches on the next tick.
- **Checkout concurrency:**
  - A second slice in the same checkout writes no pointer while the first is `POINTED`, in flight or paused.
  - It is dispatched on the first tick after the first run completes or fails.
  - A slice in another worktree is dispatched meanwhile.
  - A paused run whose review was unknown, and whose step is therefore blocked on `HUMAN`, still holds its checkout.
  - A `POINTED` step whose pointer another step overwrote while it was not current writes its pointer again before it launches.
- **Unresolved checkout:** no range holding the index, two ranges holding it, or a missing path blocks the step with `checkout_unresolved`.
- **Ingestion of a completed run:** the last review is recorded on the slice node, with `sq_run_id` and a `runner_issued` ledger row whose key detection would compute. The entry resolves `completed` with `verdict_ids` and `awaits_routing`. A later detection scan of that directory records nothing new.
- **A split review:** every part file of the last entry is recorded, in order, in the same transaction.
- **An empty `reviews` list** records nothing, and the entry still resolves and awaits routing.
- **Unknown reviews:** a missing file, an unparseable file, a null path, or attribution to another node records nothing. Each blocks the step with `review_unknown`, including on a paused run, where the step is blocked on `HUMAN` rather than `SQ_CHECKPOINT`.
- **Each non-completed outcome produces its blocked state:** paused gives `SQ_CHECKPOINT`, with the checkpoint in the entry's result. Failed (each failure kind, including `cost_cap` and `stall`), orphaned and vanished each give `HUMAN`, with the payload of D6.
- **Left for routing:**
  - After ingestion, `unrouted_outcomes` lists the entry, and the step gets no further action.
  - A routing decision recorded for the entry removes it from the list.
  - A process killed between ingestion and that decision still lists it after restart.
- **Crash during ingestion:** killed after the block and before the report, the next tick finishes it. The node has one blocked state, and each verdict is recorded once.
- **Reissue (issue #9):**
  - A `not_applied` launch whose log has the line blocks `started_before_crash` and launches nothing.
  - An unreadable log blocks.
  - With no log, the run is relaunched under the same run id, in a new entry with `reissue_of`, once. The stub saw one `sq run` for that id after restart.
  - A state that appears before the relaunch is adopted without a launch.
- **Pointer moved:** a stub snapshot that moves the run's worktree to another slice index during a run raises one `pointer_moved` escalation. It stays open while the snapshot holds, and closes when the pointer returns or the run ends. The run is still ingested.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- Migration `011` is tested on a populated v10 store. `unrouted_outcomes` uses its partial index, which an `EXPLAIN QUERY PLAN` test asserts.
- `dispatch_state`, `resolve_checkout`, `pointer_moved`, `DispatchPlanner` and the outcome-to-block mapping have table-driven tests over every row of D1, D3, D4 and D6.
- Every `cf` and `sq` call in the dispatch path goes through `TickBudget`, which 122's injected-runner test pattern asserts.
- An import test asserts that `amoeba.runner` builds `-p merge=…` only in `dispatch_params`.
- The contract documents under Provides are updated, and the CHANGELOG has an entry. Issues #9 and #10 are closed by the commits that implement D9 and D8.

### Integration Requirements

- 100's contract suite passes with the new `cf_write` key and the `record_runner_report` signature, and its stand-in Runner is updated.
- 122's crash proof, 123's reconcile tests and 124's guard tests pass with `DispatchPlanner` in the production tuple.
- 126 can read `unrouted_outcomes` and record decisions without changing `dispatch/` or `ingest/`.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–2 are automated and use the stub `sq` and `cf`. Step 3 uses the real tools on a scratch copy and launches one real `P4` run, which costs one design dispatch and its reviews. Nothing routes the outcome until 126, so the walkthrough ends at "awaiting routing".

1. **Tests:**
   ```bash
   uv run pytest tests/runner/dispatch tests/runner/ingest tests/store/test_migration_011.py \
     tests/store/test_runner_report.py tests/test_observer_cf_readback.py -v
   uv run pytest tests/runner/test_crash_recovery.py -v
   ```
   Expected: all pass. Tests are named for their rules, for example `test_second_slice_waits_for_checkout`, `test_split_review_records_every_part`, `test_reissue_with_run_id_line_escalates`, and `test_kill_between_ingest_and_route_keeps_outcome_unrouted`.

2. **Full gate and contract suite:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/contract -v
   ```

3. **One real slice design, end to end, in a scratch copy:**
   ```bash
   scratch=$(mktemp -d)/amoeba-scratch; git clone -q . "$scratch"
   (cd "$scratch" && cf init)              # registers the copy as its own CF project
   export AMOEBA_STORE_DIR=$(mktemp -d)
   amoeba start &
   amoeba submit create-project --project scratch --by operator
   amoeba submit link-cf-project --project scratch --by operator --cf-project-id <copy's id>
   sleep 5; amoeba inspect nodes --project scratch      # find slice 126's node id
   amoeba submit intent --project scratch --by operator --node-id <slice-126> \
       --body '{"intent": "drive", "until": "slice_design"}'
   ```
   `cf init` is interactive if the copy has no CF config. If it asks, use the same template as this repository. If the copy's slice 126 is already designed, choose the first slice whose step `slice_design` is `runnable` instead.

   Expected:
   - Within two ticks, `amoeba inspect journal --project scratch` shows a `cf_write` resolved `completed`, with `expected_slice_index` 126 and `checkout` the scratch path. Then it shows an `sq_run` for `P4` with params `{slice: 126}` (launched as `sq run P4 126`), unresolved.
   - `(cd "$scratch" && cf status --json)` shows `activeSlice.index` 126.
   - `amoeba inspect nodes` shows the slice node's `slice_name` filled in.
   - `sq runs list` shows the run under its `amoeba-…` id, and `amoeba inspect journal` shows nothing new while it runs.
   - When the run finishes, the `sq_run` entry is resolved with `awaits_routing` true. `amoeba inspect verdicts --project scratch` shows the design review on slice 126's node, with the run id. `amoeba inspect detections --project scratch` shows its file as `runner_issued`, if the scratch reviews directory is watched.
   - If the run paused instead, `amoeba inspect blocked --project scratch` shows the step `blocked_on_sq_checkpoint`, and the entry's result holds the checkpoint.

   Then submit `{"intent": "pause"}` for the project, and confirm that no further `cf_write` appears. Stop with `amoeba stop`, and remove the scratch project with `cf project rm` if you want it gone.

## Risk Assessment

### Technical Risks

- **Writing to the wrong worktree.** CF routes by working directory and accepts writes that land on the project level without any error.
- **Recording the wrong review.** Squadron overwrites review files in place. A file read after a later run rewrote it would be the wrong round.
- **The first production launch.** Mistakes here spend money and touch a real working tree.

### Mitigation Strategies

- Each pointer write runs in the resolved checkout, and its read-back checks the index, the path and the worktree id. Any mismatch blocks the step (D1, D2).
- A checkout runs one pipeline at a time, and its hold lasts until the run is neither running nor paused (D4). No later run can rewrite a review file before its run is ingested, because ingestion happens on the first poll that sees the outcome, before the checkout is released.
- `P6` always runs with `merge=false`, and nothing dispatches unless the PM drives it (124). The walkthrough runs on a scratch copy.
- **There is no clean-tree check until 128.** Squadron commits its own output, so a run leaves a committed tree, but a PM edit left in the same checkout would be swept into the run's commits. What limits the exposure until 128:
  - Nothing launches unless the PM drives it (124). Linking a project dispatches nothing, and a PM drive is the only trigger.
  - The pause intent stops new launches at once.
  - 128 is a hard prerequisite of 129, so no real-repository use is planned before the check exists. Until then the Runner is driven only on scratch copies, as this slice's walkthrough is.
  - Rejected: a minimal clean-tree check here. It would be a second copy of 128's check (D5, D6 there), with its own git parser and fixtures, for one slice's interval.
- **There is no time bound until 126 (D12).** A hung run holds its checkout until it ends. It is visible in `amoeba inspect journal --unresolved`, and it is never killed. The same limits apply: only a PM drive launches a run, and the pause intent stops further launches. 129 depends on 126.

## Implementation Notes

### Development Approach

Relative effort: 4/5. Suggested order. Each step leaves the suite green.

1. Contract changes (D10, D8):
   - the `cf_write` keys and the observer change, with recovery tests;
   - migration `011`, the flag in `journal_resolve`, and `unrouted_outcomes`;
   - `record_runner_report`'s new signature, and the flag cleared in `record_routing_decision`;
   - the stand-in Runner and the contract suite;
   - the contract text for these changes: `store-contract.md`, the read-back's working directory and index check in `process-contract.md`, and the Runner's journal and verdict nodes and multi-part recording in `evidence-contract.md` (D7). The evidence rule binds the Runner, so it changes before ingestion code relies on it.
2. The outcome document fields, `CheckpointKind` and `FailureKind` (D6), with the stub `sq`'s review files and `reviews` list.
3. `ingest/`: the outcome-to-block mapping, review selection and attribution, and `record` replacing 122's body, with the crash-repeat test (D6, D7).
4. `dispatch/`: `resolve_checkout`, `dispatch_state`, `DispatchPlanner` and the held-checkout set (D1, D3, D4, D5).
5. `WriteSlicePointer` in Act, with the stub `cf`'s `set` and `get` routing (D2).
6. The reissue path (D9) and the pointer-move check (D11).
7. `DispatchPlanner` in the production tuple, the remaining contract text (the dispatch and ingest stages and the checkout hold in `process-contract.md`, `context-forge-contract.md`, `substrate-guide.md`) and the CHANGELOG.

**If the slice overruns.** Steps 1–5 are the plan's core: contract changes, ingestion, and two-tick dispatch with the checkout hold. The reissue path (D9) and the pointer-move check (D11) are independent of each other and of the core, which works without them. Without D9, a `REISSUE` step is blocked on `HUMAN`, so a new run id is never launched over a run that may have started. Without D11, a moved pointer goes unescalated. Either can be split into a follow-on slice through a plan edit, as D12 did, without changing steps 1–5.

- Rejected: deferring D9 and D11 now. 122 (D7) deferred the reissue to this slice as the first that launches in production, and 128 checks a 125 reissue like any launch. The arch's pointer rule and 126's D7 both cite D11. Both stay in scope, with the split above as the fallback.
- Rejected: cutting the Interfaces Required catalogs. They are the dated upstream observations the design rests on, and the contract documents hold them only once this slice lands.

**Testing approach.** The pure functions get most of the cases. Tick-level tests use `Store.open_temporary()`, the stub `sq` and `cf` on `PATH` under a temporary `HOME`, and hand-written snapshot rows for the worktree layouts. The crash tests extend 122's `SIGKILL` proof with two kill points: between the block and the report, and between ingestion and a test router's decision.

### Special Considerations

- **Arch and slice plan edits** for D4, D5, D7, D8, D11 and D12 are committed in plan entries 6 and 7 and in the arch (Prerequisites).
- **123's D7 note** that 125 reads `cf status --worktree` is superseded. 125 needs no `cf status` read, because the read-back and the snapshot cover it. 128 reads `cf status` for gates.
- **Spend.** Every launch is a paid Squadron run. Nothing launches without a PM drive, and the pause intent stops new launches at once. A run in flight is never killed (Squadron's `max_cost_usd` bounds each run).
- **Security.** Review files are read as data and parsed by 105's pure parser. CF and Squadron output stored in payloads is bounded like 122's tail. Journal parameters hold paths, ids and indexes only, and the inherited environment is never recorded.
