---
docType: slice-design
slice: gates-git-and-human-steps
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 125
- 126
- 127
interfaces:
- 129
- 130
- 131
dateCreated: 20261021
dateUpdated: 20261021
status: not_started
turns: 48
promptTokens: 7117998
cachedTokens: 6874801
cacheWriteTokens: 243105
completionTokens: 78803
durationSeconds: 778.3
costUsd: 4.896556
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Gates, Git and Human Steps

## Overview

This slice adds the checks around dispatch, so the Runner can be pointed at a checkout the PM also works in.

- **Outcome observation.** When a pipeline run completes, the Runner reads CF's gate for the slice (`cf status --json`), runs the two ungate-hatch checks on the slice design, and, for `implementation`, reads the checkout's branch and head. Ingestion records all of it with the outcome. Two new routing inputs, `gate_state` and `check_standing`, are reduced from it, and the shipped table requires both before it advances.
- **Pre-dispatch checks.** Before any launch, reissue or resume, the checkout must be on an allowed branch, and clean, except for a resume, whose tree is its paused run's own. Before `tasks` and `implementation` launch, CF's gate at the boundary they cross is read again. A failed check blocks the step.
- **The gate disagreement (issue #15).** When the PM accepted an outcome that CF's gate still fails, the disagreement is recorded on the slice node as a check record, and dispatch goes on.
- **Merge policy.** A static per-project config file holds `merge_policy`, which defaults to `human`. Under `human`, `P6` runs with `-p merge=false`. Under `auto`, `P6` runs without it. The policy is recorded on the `P6` dispatch.
- **Merge observation.** The `merge` step completes when the head `P6` left is reachable from the target in git. Under `human`, the step is a human step until then. Under `auto`, the same observation completes it after `P6` merged.
- **Git is read only.** Every git call goes through one function that allows `status` and `merge-base` only.

## Value

User value. The Runner can be pointed at a real repository without surprising the PM:

- A PM edit left in a checkout is never swept into a run's commits. The step blocks with the dirty paths named.
- A run never starts on the wrong branch. Planning runs start on the target, and code runs start on the target or on their own slice branch.
- A CF gate that is pending a PM decision, missing a review, or failing stops the slice and tells the PM, instead of being stepped over.
- `review: none` or a grandfathering date in a design cannot clear a slice silently. Each is a check record that shows what was examined, and it escalates.
- Merging stays the PM's by default. The Runner sees the merge in git and moves on. A project the PM trusts can opt into auto merge.
- 129 needs this slice. Until it lands, the Runner is driven only on scratch copies (125, Risk Assessment).

## Technical Scope

**Included**

- `amoeba.runner.gates`, a new subpackage:
  - the CF status model and the gate position mapping;
  - the outcome observation and its reduction to `gate_state` and `check_standing`;
  - the ungate-hatch checks;
  - the pre-dispatch checks and the branch rule;
  - the merge observation.
- `amoeba.runner.git_read`: the one function that runs git, with its allowlist and the porcelain parser.
- `amoeba.runner.project_config`: the per-project config file, its model and loader, and `MergePolicy`.
- Changes to earlier Runner code:
  - 125's ingestion records the outcome observation and the check ids. 125's `dispatch_params` takes the merge policy.
  - The planners launch only on a passed pre-dispatch check. `HumanStepPlanner` blocks a `merge` step only when git shows it unmerged.
  - 126's input vocabulary gains `gate_state` and `check_standing`, and the shipped table uses them.
- A new store-only Action, `BlockDispatch`.
- New `FaultKind` members: `checkout_dirty`, `checkout_branch`, `cf_gate_blocks`, `pending_decision` and the project-scoped `checkout_read_failed`.
- A setting, `project_config_path`, with the start flag `--project-config`.
- Stub changes: the stub `cf` gains `status --json` and `config get --json` (it already answers `list slices`), using fixtures captured from CF 0.19.16. Tests use real `git` in temporary repositories.
- Contract text in `docs/process-contract.md`, `docs/evidence-contract.md`, `docs/context-forge-contract.md` and `docs/substrate-guide.md`.

**Excluded**

- **Store changes.** `record_check` (107), `record_runner_report`'s free-form `result` (125) and optional journal keys already carry everything. No migration.
- **Other Tier-1 checks**, such as "the validator examined more than zero files", and baseline-diffed test checks. They are 131's, scoped by the first proof's stops.
- **A gate step in the step map.** CF's gate stays a routing input and a dispatch check, as 123 (D3) decided. `pending-decision` blocks the step that is current, and adds no step.
- **Merges made only on a hosting service.** The Runner reads local refs, and fetching would be a git write. Listed under Future Work.
- **Batch items (130).** Their outcome observation is 130's to define (Provides).
- **Writing anything to git or to review frontmatter,** under any policy.

## Dependencies

### Prerequisites

- **125, merged:** `dispatch_state`, `POINTED`, the checkout hold, `resolve_checkout` and `Checkout`, `dispatch_params`, `ingest.record`, the entry result, and the read-back's place in Observe.
- **126, merged:** `inputs.py` and the reducer to extend, the shipped table, `StartupFailedError` loading at start, and Amoeba's version label.
- **127, merged:** `ResumeRun`, `ContinuationPlanner`, the identifiable accept (127, D7), `review_accepted`, and the situations that a dispatch block falls into.
- **122, 123 and 124, merged:** `TickBudget`, the fault boundary and closure, `STEP_MAP`, `LifecycleTree`, `predecessors`, the `{index}-slice.` stem rule, 123's completion write for human steps, `HumanStepPlanner`, 123's plan-read parser, and `current_steps` with its guard.
- **107:** `record_check`, `CheckInput`, `CheckStanding` and `check_standing()`.
- **Context Forge**, by shape. The fields below were observed on CF 0.19.16 on 20261021 (Interfaces Required).
- **git**, any version with `status --porcelain=v2`, `--no-optional-locks` and `merge-base --is-ancestor`.

### Interfaces Required

**Context Forge** (read in CF source, `introspection/types.ts`, `WorkflowNavigator.ts`, `reviewGate.ts`, and run on this repository on 20261021):

- `cf status --json -p <id> [--worktree <worktree id>]` returns `activeSlice: {name, index, status, gateInfo?, pendingDecisions?, gateExempt?}`.
  - `status` is one of `needs-design`, `needs-tasks`, `in-implementation`, `complete`, `no-active-slice`, `pending-review`, `review-failed` or `pending-decision`.
  - `gateInfo: {reviewType, rationale}` is present only with `pending-review` or `review-failed`. `reviewType` is `slice`, `tasks` or `code`.
  - CF evaluates one boundary only: the one at the slice's current position. A design with no task file evaluates the slice gate. A task file with no task done evaluates the tasks gate. All tasks done evaluates the code gate. `pending-decision` comes before every review gate, unless all tasks are done.
  - With review gating off, CF never reports `pending-review` or `review-failed`.
  - `gateExempt` reports `review-none` only, and only while gating is on. Grandfathering is never reported.
- `cf config get <key> --json -p <id>`, run in a checkout, returns `{key, value, source, description}` for that checkout. The Runner reads `git.integration_branch` (empty means `main`, by the key's own description) and `workflow.review_gate_effective_date` (empty, or `YYYYMMDD`). This shape is not in the arch's start-up probe list. Like `cf list slices`, it is checked on each read: an answer without a string `value` is a failed read (D2, D11), never a default.
- `cf list slices <initiative index> --json -p <id>` returns `entries[]` with `designFile` relative to the project root (123).
- CF's two hatches (`reviewGate.ts`, `evaluateExemption`): a design whose frontmatter `dateCreated` sorts before a non-empty effective date is exempt from every gate. A design whose frontmatter `review` is `none` is exempt from the slice, tasks and code gates.

**Squadron** (source on 20261021):

- `P6` declares `merge: "true"`. Its last branch step is `branch: {op: merge, when: "{merge}"}`. With `merge=false`, the run ends on the slice branch with the branch unmerged.
- `branch enter` refuses a dirty tree, and a branch that is neither the target nor a slice branch.
- A planning commit (design, tasks, review) made off the target raises (`actions/commit.py`, `_check_placement`). A code commit made off the slice's own branch is refused.
- The target is `git.integration_branch` from CF, read again at merge time. Unset means `main`.

**Store:** `record_check`, `check`, `blocked_state_for(node, include_resolved=True)`, `journal_entries`, `block`, `resolve`, `update_node_status`, and 121's project-scoped escalation.

## Architecture

### Component Structure

```
amoeba/runner/gates/                 NEW
  checks.py        RunnerCheck, check_id(entry_id, name), runner_provenance() (pure)
  cf_status.py     CFActiveSlice model; parse_status(); GatePosition, position_of();
                   EXIT_GATE, ENTRY_GATE: the exit and entry gate of each step (pure)
  cf_reads.py      DEFAULT_TARGET_BRANCH; read_config(), read_target() (I/O under TickBudget)
  outcome.py       OutcomeObservation; observe_outcome() (I/O under TickBudget);
                   gate_state_at_exit(step, slice) (pure)
  hatches.py       hatch_checks(design, effective_date) → (CheckInput, CheckInput) (pure)
  predispatch.py   DispatchCheck = Ok | Block; launch_candidates(current, facts, holders);
                   entry_gate(step, slice, accepted); branch_rule(...) (pure)
  dispatch_reads.py read_dispatch_facts(candidate, ...) (I/O under TickBudget)
  stage.py         GateStage: the tick's outcome, merge and pre-dispatch stages
  accepted.py      accepted_by_pm(entries, resolution) (pure)
  merge.py         MergeObservation; merge_state(...) (pure); observe_merges() (I/O)
amoeba/runner/
  git_read.py      NEW  git_read(args, cwd, budget); GIT_SUBCOMMANDS; parse_porcelain_v2()
  project_config.py NEW ProjectConfig, MergePolicy, PROJECT_DEFAULTS, load_project_config()
  decide.py        CHANGED  Action += BlockDispatch; ProjectView += dispatch_checks,
                            merge_observations; guard: launch and resume need Ok
  tick.py / observe.py  CHANGED  outcome observation, merge observation, pre-dispatch reads
  faults.py        CHANGED  FaultKind += five members (D11)
  factory.py       CHANGED  loads the project config once at start
amoeba/runner/dispatch/params.py, planner.py   CHANGED  merge policy; launch only on Ok;
                                               LaunchRun.journal_extra
amoeba/runner/lifecycle/completion.py          CHANGED  _complete becomes public complete_step
amoeba/runner/resolutions/planner.py           CHANGED  resume only on Ok; ResumeRun.journal_extra
amoeba/runner/lifecycle/human_steps.py         CHANGED  merge blocked only on not_merged;
                                               BlockHumanStep.payload_extra
amoeba/runner/ingest/record.py                 CHANGED  checks, observation into the result
amoeba/runner/routing/inputs.py, evidence.py, tables/default.yaml   CHANGED  (D3)
amoeba/process/settings.py, amoeba/cli/settings_flags.py   CHANGED  project_config_path
```

`checks`, `cf_status`, `hatches`, `accepted`, the position and branch rules, and `merge_state` are pure. Only `observe_outcome`, `read_config`, `read_dispatch_facts`, `observe_merges` and `git_read` start subprocesses, and each call checks `TickBudget` first.

### Data Flow

One project's tick, with this slice's changes marked:

```
apply intents (124) → resolutions (127)
observe   in-flight runs (122, 127)
          outcome observation, each finished `completed` run           ── NEW (D2)
          pointer read-backs and pointer-move check (125)
          plan read / reconcile (123)
          merge observation, slices whose implementation is done       ── NEW (D9)
          pre-dispatch reads, each launch or resume candidate          ── NEW (D5)
          disagreement check records                                   ── NEW (D7)
record    finished runs: record_check × 2 → block → record_runner_report ── CHANGED (D2)
view      + dispatch_checks, merge_observations                        ── CHANGED
route     (126), with gate_state and check_standing                    ── CHANGED (D3)
decide    DispatchPlanner, ContinuationPlanner: launch/resume on Ok, BlockDispatch on Block
          HumanStepPlanner: merge step blocked only when observed not_merged
act       BlockDispatch (store only); LaunchRun with merge_policy and check evidence
close     + checkout_read_failed
```

- **Outcome observation comes right after polling,** because an ingestion waits on it. Merge observation and pre-dispatch reads come last, because they only enable new work. A cut-off defers them to the next tick, which is safe because they only read.
- **Candidates** come from one pure function, `launch_candidates(current, facts, holders)`, which takes each current step's dispatch state and resolved checkout and the checkout holders from the view's dispatch facts and recomputes nothing, called once in Observe after this tick's read-backs. A candidate is a step that would launch or resume this tick: `POINTED`, `REISSUE` or `RESUME`, in a free checkout, or one held only by itself for `RESUME`. Observe reads only for those steps, and the planners launch or resume only steps that have an `Ok` in `dispatch_checks` (D5). So the planners never recompute the set, and a step Observe did not check cannot launch.
- **Reads are per candidate and per merge observation,** and never kept across ticks. `TickBudget` and the per-call timeout bound their cost. Sharing reads per checkout is added only if a measured tick overruns.
- Rejected: dropping `launch_candidates` and reading for every step. The function is not an optimisation. It is the one definition of which steps Observe checks, and the `decide()` guard (D5) relies on that set.

**A slice from tasks to merge, human policy:**

```
tick a    P5 completed → observe: cf status (tasks gate), hatches, no git
          record: 2 checks, result.outcome_observation → route: advance-on-stated-pass
tick b    implementation current → pointer write (125)
tick c    POINTED → git: clean, on target; cf status: in-implementation (past tasks gate) → Ok
          LaunchRun P6 {slice, merge: false}, params += merge_policy: human, dispatch_check
tick …    P6 completed → observe: cf status (code gate), hatches, git {branch 128-slice.x, head H}
          route: advance → implementation done
tick d    merge current → merge observation: H not reachable from target → HumanStepPlanner blocks
          other slices' P4/P5 in this checkout: blocked checkout_branch until the PM merges (#18)
(PM)      git checkout main && git merge --no-ff 128-slice.x
tick e    merge observation: H reachable → resolve the human block, merge done
```

### State Management

- **Durable, in the store:**
  - The outcome observation, in the `sq_run` entry's `result`, under `outcome_observation`, next to 125's keys. Its check ids are in `check_ids`.
  - Hatch and disagreement checks, as check records on the slice node.
  - The merge policy and the pre-dispatch evidence, in the `P6` entry's parameters.
  - Blocks written by pre-dispatch checks, and the merge step's completion.
- **In memory, for the process lifetime:** the loaded `ProjectConfig`, frozen at start like the routing table.
- **Per tick:** checkout reads, `dispatch_checks` and `merge_observations`. Nothing is cached across ticks.

## Technical Decisions

### D1 — CF's gate is read at two points, both from `cf status --json`
Status: decided
- CF evaluates only the boundary at the slice's current position (Interfaces Required). So the gate a step creates can be read only right after it, and the gate a step must cross only right before it. The Runner reads at both points:
  - **When a run completes** (D2). CF's pointer is still on the slice, because Squadron's phase step set it and the checkout is held until ingestion (125, D4). This read is the routing input `gate_state`, which routes the step whose review the gate judges.
  - **Before `tasks` or `implementation` launches** (D5). That launch follows 125's pointer write, so CF points at the slice in that tick (125, D3). This read catches what changed since the outcome: a PM accept that CF still fails (D7), a decision added to the design, or a review removed.
- **The read:** `cf status --json -p <cf_project_id>`, plus `--worktree <worktree id>` when the checkout has one, run with `cwd=checkout`, under `TickBudget` and `tick_call_timeout_seconds`. `activeSlice.index` must equal the slice's index. Otherwise the read is about another slice.
- **Position.** `position_of(active_slice)` maps CF's status onto one ordered scale, defined once:

  | `activeSlice.status` | `gateInfo.reviewType` | `GatePosition` |
  | --- | --- | --- |
  | `needs-design` | none | `NEEDS_DESIGN` (0) |
  | `pending-review`, `review-failed` | `slice` | `AT_SLICE_GATE` (1) |
  | `needs-tasks` | none | `PAST_SLICE_GATE` (2) |
  | `pending-review`, `review-failed` | `tasks` | `AT_TASKS_GATE` (3) |
  | `in-implementation` | none | `PAST_TASKS_GATE` (4) |
  | `pending-review`, `review-failed` | `code` | `AT_CODE_GATE` (5) |
  | `complete` | none | `PAST_CODE_GATE` (6) |
  | `pending-decision` | none | `PENDING_DECISION`, outside the scale |
  | anything else: `no-active-slice`, an unknown status or review type, a missing field | | `UNKNOWN` |

- The model is lenient about added keys and strict about the fields it maps. Status text is compared after trimming and lower-casing. `rationale` and `pendingDecisions` are carried as evidence for people and never matched.
- Rejected:
  - `cf next --json`. Its `recommendation` is prose, which the arch forbids routing on.
  - `cf check --slice <n> --json`. It needs no pointer, but its findings are severities over every boundary. The plan names `activeSlice.status` and `gateInfo`, and the pointer is already in place at both read points.

### D2 — The outcome observation is recorded at ingestion
Status: decided
- **For every finished `sq_run` entry whose outcome is `completed`**, Observe runs, in order, in the entry's `checkout`:
  1. the gate read (D1);
  2. `cf list slices <initiative index> --json`, parsed with 123's parser, for the slice's `designFile`. The node's `artifact_path` is not used, because it lags behind a design `P4` has just written until the next plan read;
  3. `cf config get workflow.review_gate_effective_date --json`;
  4. a read of the design file, resolved against the checkout, as 125 (D7) resolves review paths;
  5. for the `implementation` step only, `git status` (D10), for the checkout's branch and head.
- **Result.** `OutcomeObservation` is stored in the entry result under `outcome_observation`:
  - `gate`: `{index, status, review_type, position, rationale, pending_decisions}`, or `{failure: <reason>}`;
  - `design_path`, or null with a reason;
  - `git`: `{branch, head}` for `implementation`, otherwise absent.

  The two hatch checks (D4) are written first with `record_check`, and their ids go in `check_ids`.
- **Order in `ingest.record`:** the two `record_check` calls, then 125's block, then one `record_runner_report`, whose `result` now carries `outcome_observation` and `check_ids`. Check ids are fixed by the entry and the check name (D4). So a crash between the writes repeats the observation, and `record_check`'s retry rule keeps the first record.
- **Failures are answers, never deferrals.** A read that fails, times out or does not parse is recorded as such. It reduces to `unknown` or `errored`, and the table escalates it. Only a `TickBudget` cut-off defers: the run is not recorded in this tick, its entry stays unresolved, and the next tick polls and observes again. This narrows 125's record step from "each finished run" to "each finished run whose observation is complete", and changes nothing else in 125.
- **Other outcomes** (paused, failed, orphaned, vanished, launch failures, resume failures) get no observation. Their routing inputs `gate_state` and `check_standing` are `none`.
- Rejected: running these reads in the route stage. 126 keeps that stage free of subprocesses, so routing stays a pure function of the store.

### D3 — Two routing inputs, and the shipped table requires them before it advances
Status: decided
- `inputs.py` gains two inputs (126, D3). Their reducers read only the entry result and the check records:

  | Input | Values (besides `unknown`) | Reduced from |
  | --- | --- | --- |
  | `gate_state` | `clear`, `pending_review`, `review_failed`, `pending_decision`, `misplaced`, `none` | `outcome_observation.gate` and the step's exit gate |
  | `check_standing` | the five `CheckStanding` values, `none` | the standings of `check_ids` |

- **`gate_state`.** Each pipeline step has an exit gate: `slice_design` → `AT_SLICE_GATE`, `tasks` → `AT_TASKS_GATE`, `implementation` → `AT_CODE_GATE`. The mapping is defined once, beside `STEP_MAP`.
  - `PENDING_DECISION` gives `pending_decision`.
  - At the exit gate: `pending_review` or `review_failed`, from CF's status.
  - One past the exit gate gives `clear`, which means CF does not block. With gating off, that is every completed step that wrote its artifact.
  - Any other position gives `misplaced`. CF is not where this step leaves the slice, for example `P6` completed with tasks still unchecked.
  - A failed read, `UNKNOWN`, or a `completed` entry with no observation gives `unknown`. The last covers entries ingested before this slice.
  - `none` for every outcome that is not `completed`.
- **`check_standing`** is the worst standing of the outcome's checks, in the order `failed`, `errored`, `vacuous`, `unattested`, `passed`, defined once. A check id that the store does not hold gives `unknown`. `none` for outcomes that are not `completed`.
- **The shipped table** after this slice. Changed rules are marked:

  ```yaml
  rules:
    - id: advance-on-stated-pass                 # CHANGED: gate and checks
      when: {outcome: completed, verdict: pass, standing: stated,
             gate_state: clear, check_standing: passed}
      route: advance
    - id: advance-on-accepted-review             # CHANGED: checks (127, D8)
      when: {outcome: completed, review_accepted: true, check_standing: passed}
      route: advance
    - id: rerun-new-concerns                     # CHANGED: checks
      when: {outcome: completed, verdict: concerns, standing: stated,
             recurrence: new, check_standing: passed}
      route: rerun
      max_attempts: 2
    - id: escalate-completed-concerns            # unchanged
    - id: escalate-everything-else               # unchanged catch-all
  ```

- **What this gives:**
  - A CF gate that clears on a `derived` or `imposed` verdict, or an untrusted standing, does not advance. `standing: stated` is still required, and CF's `clear` is not enough on its own.
  - A store pass that CF's gate fails does not advance either. It escalates on the step whose review CF judges, where the PM's `accept` (127) is the answer.
  - A hatch, an unreadable design or a vacuous check is never `passed`, so it escalates.
  - `pending_decision` escalates through the catch-all. The entry result carries CF's pending decisions for the PM.
- **`advance-on-accepted-review` does not name `gate_state`.** The PM accepted the loop's review, and CF failing that review is the disagreement D7 records, not a reason to undo the accept.
- **A PM `accept` advances an outcome these rules escalate.** Accepting an escalated completed outcome is store-only (127, D3, `StatusEffect(done)`) and is not routed again, so a hatch, a vacuous check or a CF gate escalation is cleared by the PM's accept. A loop accept (`--decision accept`) does route again: its completed outcome still needs `check_standing: passed`, so a hatch escalates it once more, and the PM's completed-outcome accept then advances it.
- **`rerun-new-concerns` does not name `gate_state`.** A CONCERNS review fails CF's gate under a `pass` threshold, and a rerun is the step's answer to its own review.

### D4 — The ungate hatches are two check records on the slice node
Status: decided
- `hatch_checks(design, effective_date)` is pure. It returns two `CheckInput`s. The names are a `StrEnum`, `RunnerCheck`, defined once. Names are data and never logic (evidence contract):

  | Check | `failed` (hatch present) | `passed` | `errored` |
  | --- | --- | --- | --- |
  | `ungate_review_none` | frontmatter `review`, trimmed and lower-cased, is `none` | `review` absent or any other value | frontmatter missing or unparseable |
  | `ungate_effective_date` | effective date set, and `dateCreated` sorts before it | effective date empty, or `dateCreated` on or after it | the config read failed, the effective date is not eight digits, or `dateCreated` is missing while a date is set |

- **What is examined.** `examined_count` is the number of design files read: 1, or 0 when the design path is unknown or the file is missing. A check that read no design is `vacuous` by 107's rule, whatever its outcome. So a missing design is never a pass. `examined` holds `{design_path, review}` or `{design_path, date_created, effective_date}`, as read.
- **Frontmatter** is the YAML between a leading `---` line and the next `---` line, read with `safe_load`. Leading whitespace and a byte-order mark are allowed. `dateCreated` is compared as text, as CF compares it. YAML may load `20261021` as an integer, so the value is converted back to text first.
- **Matching CF.** `review` is compared more leniently than CF's exact `none`. A value CF would not honour, such as `None`, still escalates. A false escalation is the safe direction.
- **Identity and provenance.** The id is `chk-<entry id>-<check name>`, so one outcome gets one record per check, and a repeat is `record_check`'s retry. Provenance is upstream `amoeba`, Amoeba's version label (126, D5), source `document`, and `source_path` the design path.
- **Both hatches escalate through the table** (D3), not through code. The arch's "if either is present, the node escalates" holds because no advance or rerun rule matches a `check_standing` that is not `passed`.
- **The Runner never writes `review: none`** or any frontmatter. No code path in this slice opens a design file except to read it, so no source test is added for it.

### D5 — Pre-dispatch checks: git first, then the entry gate
Status: decided
- **Which actions.** `LaunchRun`, whether fresh or a 125 reissue, and 127's `ResumeRun`. These are the actions that start Squadron work in a checkout. A pointer write (`cf_write`) and 127's `ObserveRun` change no files and are not checked.
- **Reads, per candidate,** under `TickBudget`:
  1. `git status` (D10): branch, head and dirty paths;
  2. `cf config get git.integration_branch --json`: the target. Empty means `main`, which is `DEFAULT_TARGET_BRANCH`, defined once and citing the key's description;
  3. for a fresh or reissued `tasks` or `implementation` launch only, the gate read (D1).
- **Result:** `DispatchCheck`, one of:
  - `Ok(evidence)`. `evidence` is `{branch, head, target, gate_status, gate_review_type}`. It is written into the launch's journal parameters as `dispatch_check`, so the dispatch decision records what it was based on.
  - `Block(fault_kind, context, payload)`. The planner emits `BlockDispatch`, which Act applies as one `store.block(node, kind=HUMAN, …)`. This is store-only, like 123's `BlockHumanStep`.
  - No result: the reads were cut off or failed, or the gate read is about another slice. Nothing is issued and nothing is written. A failed read raises `checkout_read_failed` (D11).
- **Git, in order.** The first rule that applies decides:
  1. Detached HEAD: `Block(checkout_branch)`.
  2. Not on an allowed branch (D6): `Block(checkout_branch)`, naming the branch, the target and the allowed set.
  3. For a launch or reissue, any changed, staged, unmerged or untracked path: `Block(checkout_dirty)`, with the first 20 paths and the count.
- **A resume is not checked for a clean tree.** A paused run can leave uncommitted work, and Squadron's resume continues from it. Requiring a clean tree would leave the PM only `handled` or `stop`, or discarding the run's work. The dirty paths, if any, go into the `dispatch_check` evidence. **This departs from the plan's "before any dispatch, including 127's resumes, the tree must be clean".** The plan entry is edited to say so.
- **The entry gate,** for `tasks` (`AT_SLICE_GATE`) and `implementation` (`AT_TASKS_GATE`). `slice_design` has none, because no slice gate precedes it.

  | Gate read | Check |
  | --- | --- |
  | `activeSlice.index` is not the slice's | no result, and no fault. The next tick's read-back makes the step `NEEDS_POINTER` (125, D3). |
  | `PENDING_DECISION` | `Block(pending_decision)`, payload `{decisions: [{heading, line}]}` |
  | at the entry gate, and the predecessor was accepted by the PM (D7) | disagreement check recorded, then `Ok` |
  | at the entry gate, otherwise; before it; or `UNKNOWN` | `Block(cf_gate_blocks)`, payload `{position, status, review_type, rationale}` |
  | past the entry gate | `Ok`. CF has moved past this boundary, for example on a rerun. |

- **A guard in `decide()`**, beside 124's current-step guard: a `LaunchRun` or `ResumeRun` for a node without `Ok` in this tick's `dispatch_checks` is a programming error. It raises `ValueError` and faults the project, so no planner can launch unchecked.
- **The PM's answer to a block** is 127's, unchanged. A blocked pointed launch is `before_run`, and a blocked reissue is `ended_run`. Both allow `rerun` or `stop`. A blocked resume is still `paused_run`, because its latest entry is the paused run. It allows `retry`, `accept` (at a loop), `handled` or `stop`, never `rerun`. The PM fixes the checkout, then resolves a blocked launch or reissue with `rerun`, or a blocked resume with `retry` or `accept`, and the check runs again.

### D6 — The allowed branch depends on the pipeline
Status: decided
- **Allowed branches:**

  | Pipeline | Allowed |
  | --- | --- |
  | `P4`, `P5` (planning) | the target |
  | `P6` (code), fresh, reissued or resumed | the target, or this slice's own branch |

  **This refines the plan's "on the target or the node's slice branch".** Squadron refuses a planning commit made off the target, so a planning run on a slice branch would fail after it had spent money. A resume inherits its pipeline from the entry it continues.
- **"This slice's own branch"** is a branch whose name parses to the slice's index under 123's `{index}-slice.` stem rule. Amoeba never builds a branch name. That would mean building a slug, which 123 (D2) rules out.
- **A pending human merge is not waited out in v1.** Under `human`, `P6` leaves its slice branch checked out until the PM merges, so a later slice's `P4` or `P5` in that checkout blocks with `checkout_branch`, as the plan says, and the PM reruns it after merging. Waiting instead of blocking is deferred to issue #18. Until then, planning other slices during a pending merge needs a separate CF worktree, which is already the arch's rule for parallel work.
- The Runner never changes the branch. Squadron's `branch enter` restores the target from an unmerged slice branch, but that is a git write.

### D7 — A store accept that CF's gate still fails is a check record, and dispatch goes on (issue #15)
Status: decided
- **Where it is detected:** at the successor's entry gate (D5). That is where CF reports the boundary the accepted step produced (127, D7).
- **`accepted_by_pm(entries, resolution)`** is pure, and is defined once. It is true for the predecessor step when it holds 127's identifiable accept: the step's latest blocked state has an applied `accept` on a `completed_outcome`. The accepted verdicts are the `verdict_ids` of the step's latest `sq_run` entry. A loop accept in Squadron (127, D8) is not counted, and its successor blocks with `cf_gate_blocks`. Counting it is deferred to issue #17.
- **The record.** A check on the slice node:
  - name `cf_gate_accept_disagreement`, outcome `failed`, `examined_count` 1 (one gate evaluated);
  - `examined`: `{step, cf_status, review_type, rationale, accepted_by, verdict_ids}`, where `accepted_by` is the blocked state id;
  - id `chk-<accepted entry id>-cf_gate_accept_disagreement`, so each accepted outcome is recorded once, however many ticks or reruns read the gate again;
  - provenance upstream `amoeba`, source `command_output`.

  It is written in Observe, as an observation that changes the store.
- **Then dispatch goes on.** The PM decided, and the arch says the disagreement is "recorded on the node and shown to the PM rather than reconciled away". Squadron's pipelines do not check CF's gate (no reference to CF's gate statuses in Squadron's source, 20261021), so the successor runs. Nothing edits CF or frontmatter.
- **Visible to the PM:** in `amoeba inspect checks --project P --node <slice>`, and on the feed as a check record (107), where the notification bridge can show it. The launch's `dispatch_check` evidence names the check id.
- **Without an accept**, the same gate is `cf_gate_blocks` (D5). Either CF changed after the store advanced, or the table advanced on a rule that does not name `gate_state`, such as a loop accept (issue #17). Both need a person.

### D8 — Per-project config: a static file holding the merge policy
Status: decided
- **Format** (documented in `docs/process-contract.md`):

  ```yaml
  projects:
    amoeba:
      merge_policy: human
    scratch:
      merge_policy: auto
  ```

  Keys under `projects` are Amoeba project ids. Values are trimmed and lower-cased. `extra="forbid"` refuses unknown keys. 130 adds `design_dispatch` to the per-project model.
- **`MergePolicy`** is a `StrEnum` with `human` and `auto`. `PROJECT_DEFAULTS` in `project_config.py` is the one place the default lives: `merge_policy: human`, as the arch requires. A project the file does not name, or a key a project entry omits, takes the default.
- **Location.** The setting is `project_config_path: Path | None`, with the start flag `--project-config PATH`. Its default is `None`, defined in `settings.py`.
  - With no file, every project uses `PROJECT_DEFAULTS`. Start logs that at INFO, naming the defaults.
  - A given path that is missing or unreadable, YAML that does not parse, an unknown key or an unknown value each raise `StartupFailedError`, listing every problem. `amoeba start` exits `STARTUP_FAILED`, as 126 (D4) does for the table.
  - A project id the store does not hold is not checked. Its entry applies if that project is created later.
  - No format version key. `extra="forbid"` already refuses keys the model does not know, and a version is added when a second format exists.
- **Static, like the table.** It is loaded once in `runner_tenant()` and never mutated. A change needs a restart.
- **Recorded on each dispatch.** A `P6` launch's journal parameters gain `merge_policy` and `target`. A reissue copies its old entry's parameters (125, D9), and a resume reuses the run's own params in Squadron (127). So a run keeps the policy it was launched under, and its entry says which policy that was.
- **`dispatch_params(step, slice_index, merge_policy)`** stays the one place the `merge` param is built (125, D5). Under `human`, `P6` gets `{"merge": "false"}`. Under `auto`, it gets no `merge` key, so `P6`'s declared `true` applies. 125's import test still holds.
- **Never to `main` when an integration branch is set.** Squadron merges into the target it reads from CF in the run's checkout, and the dispatch records the same target. With an integration branch set, that target is the integration branch. The Runner itself never merges (D10).
- Rejected:
  - A store table set through an intent. The arch puts the policy in static config, and a policy that changes mid-run would need its own provenance.
  - A key in the routing table. 126 (D2) keeps the table project-independent.

### D9 — A merge is observed by reachability of the head `P6` left
Status: decided
- **The head.** D2 records `git: {branch, head}` for every completed `implementation` outcome, including resumed ones.
- **The observation.** For each slice in Observe scope whose `implementation` is done and whose `merge` is not done, read the target (D5, read 2) and run `git merge-base --is-ancestor <head> <target>` in the slice's checkout. The head and branch come from the step's latest completed `sq_run` entry:

  | Situation | `MergeObservation` |
  | --- | --- |
  | Exit 0, and the recorded branch was the slice's own branch, or the entry's `merge_policy` is `auto` | `merged` |
  | Exit 1 | `not_merged` |
  | No recorded head or branch, or a `human` entry whose recorded branch is not the slice's own | `unobservable` |
  | Exit other than 0 or 1, timeout, or no target | read failure: no observation, `checkout_read_failed` (D11) |
  | Cut off | no observation this tick |

  The branch condition matters under `human`. If `P6` ended on the target, nothing was left for the PM to merge, and marking the step done would claim a merge nobody saw.
- **Reachability, not the branch name,** decides it. A PM who deletes the slice branch after merging, or adds fix-up commits before merging, is still observed. A squash merge is not observed. 123's completion rule ("CF reports the slice complete") still completes the step once the plan entry is checked.
- **Effects:**
  - `merged`: the step is completed with 123's completion write. A blocked human step is resolved with `resolved_by="runner"` and detail `observed: <head> reachable from <target>`, then marked done. A runnable step is marked done. It is written in Observe, so the view sees it done.
  - `not_merged` or `unobservable`: `HumanStepPlanner` blocks the step if it is current, as 123 does today. `unobservable` adds `{merge_observation: unobservable, reason}` to the block payload.
  - No observation: `HumanStepPlanner` skips the step this tick. A read failure would otherwise block a step that `auto` already merged.
- **Both policies use the same path.** Under `auto`, `P6` merged before it completed, so the first observation is `merged`, and the step completes before it is ever blocked. If Squadron's merge did not happen, the step becomes a human step, which is the safe direction.
- **Local refs only.** A merge made only on a hosting service is seen after the PM pulls it into the local target. Fetching would be a git write (Future Work).

### D10 — Git is read through one allowlisted function
Status: decided
- `git_read(args, cwd, budget) -> GitReadResult | GitReadFailure` is the only place `amoeba.runner` starts git. It checks `TickBudget`, runs under `tick_call_timeout_seconds`, with stdin from `/dev/null`, and with `GIT_TERMINAL_PROMPT=0`.
- **Allowlist:** `GIT_SUBCOMMANDS = {status, merge-base}`. Any other subcommand raises `ValueError`, a programming error. The two calls are:
  - `git --no-optional-locks status --porcelain=v2 --branch --untracked-files=normal`. `--no-optional-locks` stops `status` from refreshing and rewriting the index, so even the read writes nothing.
  - `git merge-base --is-ancestor <head> <target>`.
- **The parser** reads `# branch.head` (`(detached)` is detached) and `# branch.oid`, and treats every other non-empty line as a dirty entry. It reads the path by entry kind: a rename line is `<new path>`, a TAB, `<old path>`, and the new path is taken. Header lines it does not know are ignored. The test fixture is real output captured from git on clean, modified, untracked, staged, renamed, unmerged and detached checkouts, as the parsing rule requires.
- **Never, under any policy:** merge, commit, checkout, branch deletion, reset, stash or push. A source test asserts that `git` appears as an executable only in `git_read.py`.
- Rejected: dropping that source test because the allowlist enforces the rule at runtime. The allowlist sees only calls made through `git_read`. The source test is what makes `git_read` the only path, as 125's and 126's source tests do for their one-place rules.

### D11 — Faults
Status: decided
- **Node blocks** (`BlockDispatch`, on `HUMAN`), each with `fault_kind` in the payload: `checkout_dirty`, `checkout_branch`, `cf_gate_blocks` and `pending_decision`. The context names the step and the reason. The payload holds the branch, target, paths and CF fields, all bounded like 122's tail.
- **Project-scoped:** `checkout_read_failed`, for a failed `git` or `cf` read in the pre-dispatch or merge observation. Its payload is `{checkout, command, reason}`. It counts as a recurrence on every tick a read fails, and closes on the first complete tick where none does (122's closure, 123's recurrence pattern). The step is not blocked, because the step is not at fault, and a retry costs only a read.
- **Outcome observation** never faults. Its failures are recorded and routed (D2).
- **Store failures** re-raise, and the process exits (122, D8). Any other exception reaches 122's one catch.

### Technology Choices

- Standard library `subprocess` (through 122's injected runner), `pathlib` and `hashlib`, PyYAML `safe_load` for frontmatter and the config file, and pydantic v2 for the CF status model and the config model. No new dependencies.
- The tests use real `git` in temporary repositories, which is local and fast. The stub `cf` returns fixtures captured from CF 0.19.16 on 20261021 for every gate status and position, so each mapping row is tested against the real format.

### Patterns and Conventions

- Defined once: `GatePosition` and its mapping, the exit and entry gate of each step, `RunnerCheck`, the check id format, the standing order, `MergePolicy`, `PROJECT_DEFAULTS`, `DEFAULT_TARGET_BRANCH`, `GIT_SUBCOMMANDS`, the CF config key names, the journal keys `merge_policy`, `target` and `dispatch_check`, the result keys `outcome_observation` and `check_ids`, and the new `FaultKind` members.
- Expected external states are answers (`DispatchCheck`, `MergeObservation`, a recorded read failure), never exceptions.
- Modules stay under about 300 lines, and functions under about 50.

## Implementation Details

### API Contracts

**Runner, internal:**

```python
class GatePosition(IntEnum): NEEDS_DESIGN; AT_SLICE_GATE; PAST_SLICE_GATE; AT_TASKS_GATE
                             PAST_TASKS_GATE; AT_CODE_GATE; PAST_CODE_GATE
class MergePolicy(StrEnum): HUMAN; AUTO
class RunnerCheck(StrEnum): UNGATE_REVIEW_NONE; UNGATE_EFFECTIVE_DATE; CF_GATE_ACCEPT_DISAGREEMENT
@dataclass(frozen=True)
class Ok: evidence: Mapping[str, str | None]
@dataclass(frozen=True)
class Block: fault_kind: FaultKind; context: str; payload: Mapping[str, object]
type DispatchCheck = Ok | Block              # absent from dispatch_checks: no result
@dataclass(frozen=True)
class BlockDispatch: node_id: str; block: Block
type Action = (LaunchRun | BlockHumanStep | WriteSlicePointer | ResumeRun | ObserveRun
               | BlockDispatch)
# ProjectView += dispatch_checks: Mapping[str, DispatchCheck]
#                merge_observations: Mapping[str, MergeObservation]
#                merge_policy: MergePolicy          # defaults to PROJECT_DEFAULTS' value
# LaunchRun, ResumeRun += journal_extra: Mapping[str, object] = {}
#     written into the entry's parameters: P6 launch: merge_policy, target, dispatch_check;
#     any other launch or resume: dispatch_check
# BlockHumanStep += payload_extra: Mapping[str, object] = {}   # merged into the block payload
launch_candidates(current, facts, holders) -> tuple[Candidate, ...]   # pure, gates/predispatch.py
complete_step(store, node, step, has_open_entry, *, detail)           # lifecycle/completion.py, public
```

**Entry result** (`sq_run`, `completed` outcomes, extending 125 D6):

```json
{"outcome_observation": {
   "gate": {"index": 128, "status": "review-failed", "review_type": "tasks",
            "position": "AT_TASKS_GATE", "rationale": "…", "pending_decisions": null},
   "design_path": "project-documents/user/slices/128-slice.….md",
   "git": {"branch": "128-slice.…", "head": "<sha>"}},
 "check_ids": ["chk-<entry>-ungate_review_none", "chk-<entry>-ungate_effective_date"]}
```

**CLI:** `amoeba start --project-config PATH` (D8). Checks are read with 107's `amoeba inspect checks`.

## Integration Points

### Provides to Other Slices

- **129:** the clean-tree and branch check, both gate reads, the merge observation that advances a human merge, the disagreement check record, and `--project-config`. Its write-up reads `inspect checks` and the `dispatch_check` evidence in `inspect journal --json`.
- **130:**
  - `ProjectConfig`, to which it adds `design_dispatch`.
  - **`slice_design`'s pre-dispatch check needs no pointer:** git and the target only (D5). The checkout must be on the target (D6). So 130's D3 point 6 leaves batches eligible.
  - **An item outcome has no outcome observation.** D2 reads the gate with CF pointed at the slice, which a batch does not set. Under this slice's table, an item whose `gate_state` is `unknown` escalates. 130 decides how its items get both inputs. The hatch checks need no pointer and can run per item. The gate needs either a pointer or another CF surface.
- **131:** `check_standing` and the check-record pattern (`RunnerCheck`, ids, provenance) for its Tier-1 checks, and the gate position for its tier inputs.
- **Contract documents:**
  Only what other slices consume:
  - `process-contract.md`: the per-project config format and setting (130), and the pre-dispatch checks (130).
  - `evidence-contract.md`: the Runner's checks, their ids and provenance (131).
  - `context-forge-contract.md`: the `cf status` fields and positions, and the two config keys (130, 131).
  - `substrate-guide.md`: the 120 row, and issue #15 closed (plan entry 9).

  The outcome observation, the merge observation and the git allowlist are described in this design and the code, not in the contracts.

### Consumes from Other Slices

- **125:** `POINTED`, `dispatch_state`, the checkout hold, `resolve_checkout`, `dispatch_params`, and `ingest.record` with its result. A failed check never changes 125's states: the step stays `POINTED`, and launches once the check passes.
- **126:** the input vocabulary, the reducer, the table and its validation. A table that names `gate_state` or `check_standing` now loads.
- **127:** `ResumeRun`, `ContinuationPlanner`, the accept that `blocked_state_for` shows, continuation entries, and the situations a block lands in.
- **123:** `STEP_MAP`, `predecessors`, the stem rule, the slice-list parser, the completion write and `HumanStepPlanner`.
- **124:** `current_steps` and the guard pattern.
- **107:** check records and standing.
- **122:** `TickBudget`, faults, closure, `StartupFailedError` and settings flags.

## Success Criteria

### Functional Requirements

- **Clean tree and branch:**
  - A dirty tree (modified, staged or untracked) blocks a pointed step with `checkout_dirty` naming the paths, and launches nothing.
  - A checkout on an unrelated branch, or detached, blocks with `checkout_branch`.
  - `P4` and `P5` launch only on the target. `P6` launches on the target or its own slice branch.
  - A reissue is checked like a launch. A resume is checked for its branch only, and a dirty tree left by its paused run does not block it. `ObserveRun` and pointer writes are not checked.
  - With an integration branch set in the checkout's CF config, that branch is the target, and `main` blocks a planning launch.
- **Gate at the outcome:**
  - A `P5` with a stated PASS and CF `in-implementation` advances.
  - The same PASS with CF `review-failed` at the tasks gate escalates.
  - A gate CF clears on a `derived` verdict escalates.
  - `pending-decision` after `P4` escalates, with the decisions in the entry result.
  - `P6` completing with CF `in-implementation` (tasks unchecked) escalates as `misplaced`.
  - A failed gate read escalates as `unknown`.
- **Gate at dispatch:** `pending-decision` blocks `pending_decision`. A failing entry gate without an accept, a position before it, or an unreadable gate blocks `cf_gate_blocks`. A position past it launches.
- **Hatches:**
  - `review: none` in the design makes `ungate_review_none` `failed`, and the outcome escalates.
  - A `dateCreated` before a set effective date makes `ungate_effective_date` `failed`, and the outcome escalates.
  - A missing design makes both checks `vacuous`, and the outcome escalates.
  - `amoeba inspect checks --node <slice>` shows each check with the design path and the values it examined.
- **Issue #15:** after a PM `accept` of a completed `slice_design` outcome whose CF slice gate still fails, the `tasks` launch records one `cf_gate_accept_disagreement` check on the slice node, then launches. A rerun of `tasks` adds no second record.
- **Merge policy:**
  - With no config file, `P6` runs with `-p merge=false`, and its entry records `merge_policy: human`.
  - With `merge_policy: auto`, `P6` runs with no `merge` param, and its entry records `auto` and the target.
  - An invalid config makes `amoeba start` exit `STARTUP_FAILED`, naming each problem.
- **Merge observation:**
  - Under `human`, after `P6` the `merge` step is a human step. A `git merge` the PM makes in the checkout completes it on the next tick, and resolves its block.
  - A merge made after deleting the branch, or after adding commits to it, is observed.
  - Under `auto`, the `merge` step completes without ever being blocked.
  - A failed `merge-base` read blocks nothing, and raises `checkout_read_failed`, which closes once a read succeeds.
- **No git writes:** across the suite, the Runner's git calls are `status` and `merge-base` only.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- `position_of`, `gate_state_at_exit`, the entry-gate rule, `branch_rule`, `hatch_checks`, `accepted_by_pm` and `merge_state` have table-driven tests over every row of D1, D3, D4, D5, D6 and D9.
- The porcelain parser is tested on real captured output. The CF status model is tested on captured CF 0.19.16 output for every status.
- Every `git` and `cf` call in this slice goes through `TickBudget`, which 122's injected-runner test asserts. The worst-case tick stays 122's bound: the tick deadline plus one `tick_call_timeout_seconds`.
- Two tests guard the invariants: a source test that git runs only in `git_read.py` (D10), and a test that the `decide()` guard refuses `LaunchRun` and `ResumeRun` without `Ok` (D5).
- The shipped table passes `parse_table`, and the contract documents and the CHANGELOG are updated. Issue #15 is closed by the commit that implements D7.

### Integration Requirements

- 125's dispatch and crash tests, 126's routing tests and 127's resolution tests pass with the checks in place. Their fixtures gain a clean, target-branch checkout and a stub `cf status`.
- 100's contract suite passes unchanged, because no store contract changes.
- 129 can drive a real slice to a human merge with no Squadron or CF command run by hand.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–3 use the stub `sq` and `cf` with real `git`. Step 4 uses the real `cf` and `git` on a scratch copy and launches nothing, so it spends nothing. Step 5 is optional and launches real runs.

1. **Tests:**
   ```bash
   uv run pytest tests/runner/gates tests/runner/test_git_read.py \
     tests/runner/test_project_config.py -v
   ```
   Expected: all pass. Tests are named for their rules, for example `test_dirty_tree_blocks_launch`, `test_planning_run_refused_off_target`, `test_resume_not_blocked_by_its_own_dirty_tree`, `test_derived_pass_cleared_by_cf_escalates`, `test_review_none_check_failed_and_escalates`, `test_accept_disagreement_recorded_once`, `test_merge_observed_after_branch_deleted` and `test_auto_merge_step_never_blocked`.

2. **Full gate and the earlier slices' suites:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/runner tests/contract -q
   ```

3. **An invalid per-project config refuses to start:**
   ```bash
   printf 'projects:\n  scratch:\n    merge_policy: sometimes\n' > /tmp/projects.yaml
   AMOEBA_STORE_DIR=$(mktemp -d) uv run amoeba start --project-config /tmp/projects.yaml; echo "exit $?"
   ```
   Expected: exit 7 (`STARTUP_FAILED`), naming `merge_policy` and the value `sometimes`. With `merge_policy: auto`, start succeeds. Stop it with `amoeba stop`.

4. **A dirty tree and a wrong branch block before any launch, on a scratch copy.** Follow 125's walkthrough step 3 to create the scratch project, but before submitting the drive intent:
   ```bash
   touch "$scratch/stray.txt"
   ```
   Then submit the drive for one undesigned slice, `until: slice_design`. Expected:
   - `amoeba inspect journal --project scratch` shows the `cf_write` resolved `completed`, and no `sq_run`.
   - `amoeba inspect blocked --project scratch` shows `slice_design` blocked, with `fault_kind: checkout_dirty` and `stray.txt` in the payload.

   Move to another branch while keeping the stray file out of the tree:
   ```bash
   rm "$scratch/stray.txt"; git -C "$scratch" checkout -q -b scratch-other
   amoeba submit resolution --project scratch --by operator \
       --blocked-state-id <id from inspect blocked> --detail "cleaned" --decision rerun
   ```
   Expected: a new `cf_write`, then a new block with `fault_kind: checkout_branch`, naming `scratch-other`, the target and the allowed set. Still no `sq_run`. Submit `{"intent": "pause"}` for the project before switching the scratch copy back to its target, then stop with `amoeba stop`.

5. **Optional, a human merge observed (spends one design, tasks and implementation run).** This is 129's path. On a scratch copy, drive one slice `until: merge`. When `P6` completes:
   - `amoeba inspect journal --project scratch --json` shows the `P6` entry with `merge_policy: human`, `-p merge=false`, and `outcome_observation.git` naming the slice branch.
   - `amoeba inspect blocked` shows `merge` as a human step.
   - `git -C "$scratch" checkout main && git -C "$scratch" merge --no-ff <slice branch>`. On the next tick, `amoeba inspect nodes` shows `merge` done, and its block resolved by `runner`.

## Risk Assessment

### Technical Risks

- **CF reports a gate only at the slice's current position.** A read at the wrong moment reports another boundary, and a mapping mistake would advance past a failing gate.
- **Wrongly observing a merge** would end a slice the PM has not merged.

### Mitigation Strategies

- Each read point names the gate it expects: the step's exit gate, or the successor's entry gate. Every other position maps to an explicit value (`misplaced`, `unknown`, or "past the entry gate"). Only `clear` takes part in an advance, and only with a stated pass. Each row is tested on captured CF output.
- A merge is `merged` only when the recorded head is reachable from the target, and under `human` only when `P6` ended on the slice's own branch. Anything else leaves the step a human step.

## Implementation Notes

### Development Approach

Relative effort: 3/5, as the plan says. Cut to fit it:

- deferred: counting a loop accept as a PM accept (issue #17), and waiting rather than blocking while a checkout awaits a human merge (issue #18);
- folded: `gate_state`'s `behind` and `ahead` into `misplaced`, and the dispatch blocks for a CF position behind the store or an unreadable gate into `cf_gate_blocks`;
- dropped: a table rule of its own for `pending_decision`, which the catch-all already escalates.

What remains is what plan entry 9 names: the two gate reads, the hatch checks, the clean-tree and branch check, the disagreement record, the merge policy and the merge observation. Suggested order. Each step leaves the suite green.

1. `git_read.py` with the allowlist, the porcelain parser and its captured fixtures (D10).
2. `project_config.py`, the setting and flag, loading at start, and `dispatch_params` with the policy (D8).
3. `cf_status.py` and the position mapping, with the stub `cf`'s `status` and `config get` fixtures (D1).
4. Outcome observation: the hatch checks, the observation, ingestion's changes, and the two routing inputs with the table edit (D2, D3, D4).
5. Pre-dispatch checks: the branch rule, the entry gate, `BlockDispatch`, the guard, and the planners' filter (D5, D6).
6. `accepted_by_pm` and the disagreement record (D7).
7. Merge observation and `HumanStepPlanner`'s change (D9), then the contract documents and the CHANGELOG.

**Testing approach.** The pure functions get most of the cases. Tick-level tests use `Store.open_temporary()`, the stub `sq` and `cf` on `PATH` under a temporary `HOME`, a temporary git repository as the checkout, and a small routing table through `--routing-table`. The merge tests make real merges, branch deletions and fix-up commits in that repository.

### Special Considerations

- **Plan and arch edits,** made with this design:
  - **Plan entry 9 (128):** the gate is read at the outcome and before dispatch (D1). The hatches escalate through `check_standing` (D3, D4). Planning runs need the target (D6). A resume is not checked for a clean tree (D5). The policy lives in a per-project config file (D8). A merge is observed by reachability (D9).
  - **Plan Future Work:** observing merges made only on a hosting service.
  - **Arch, "Squadron does the git work":** the allowed branch depends on the pipeline, and a resume is not checked for a clean tree (D5, D6).
  - **Arch, "Gates come from CF's structured status":** the two read points, and hatches routed through the table (D1, D3, D4).
  - **Arch, "Merge policy is a pipeline parameter":** the per-project config file, and the merge observed by reachability (D8, D9).
- **Spend.** Every check runs before a launch, so a failed check spends nothing. `auto` merge is opt-in for each project.
- **Security.** Block payloads hold paths, branch names, statuses and CF's rationale text, bounded like 122's tail. The config file holds no secrets, and the process contract says so. Git runs with prompts disabled and stdin closed, so it never waits on credentials.
