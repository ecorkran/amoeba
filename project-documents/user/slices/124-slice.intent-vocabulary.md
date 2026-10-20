---
docType: slice-design
slice: intent-vocabulary
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 121
- 123
interfaces:
- 125
- 127
- 128
- 129
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
turns: 23
promptTokens: 1406863
cachedTokens: 1301928
cacheWriteTokens: 104899
completionTokens: 25792
durationSeconds: 257.0
costUsd: 1.615888
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Intent Vocabulary

## Overview

This slice defines how the PM steers the Runner, and makes the Runner obey it.

- **The vocabulary.** An intent's body is one of five closed kinds, written as six body forms: `drive` (optionally `until` a lifecycle step), `exclude`, `pause`, `resume` and `clear`. Its target is the intent message's `node_id`: none for the project, or an initiative or slice node.
- **Applying intents.** At the start of each project's tick, the Runner reads `pending_intents`, interprets each in message order, and acknowledges it with `applied`, `no_op` or `rejected` in the same transaction that writes the target's desired state (121, D3).
- **Governance.** For every step node, drive resolves from the nearest target on its path that sets it, and hold is true if any target on the path holds. A step is **current** when it is ready (123), driven and not held. Planners see only current steps, and Decide refuses an action on any other node.
- **`HumanStepPlanner` joins production.** Because nothing is driven by default, linking a project escalates nothing until the PM drives something (123, D9).
- **`amoeba inspect desired-states`** shows each target's stored settings.

## Value

User value. The PM can tell Amoeba what to work on, how far to take it, and when to stop, by submitting intents through the existing inbox. They never touch the store. A broad pause always works and cannot be undone from below. Each intent gets a readable answer: applied, already true, or refused with a reason.

Architectural value. The body format is the contract 160 translates natural language into, and 160's command-authority whitelist (OQ5) is a subset of it. Dispatch (125), resumes (127) and gates (128) all get "may I act on this node?" from one place.

## Technical Scope

**Included**

- `amoeba.runner.intent`, a new subpackage:
  - `vocabulary.py`: `IntentKind`, the `IntentBody` model, `IntentRejection` and the `until` applicability rule.
  - `apply.py`: interpreting one pending intent against the current row and the tree, and acknowledging it with its desired-state write.
  - `governance.py`: `DesiredStateIndex`, `governing(tree, index, node)` and `current_steps(tree, index)`. These are pure.
- `STEP_SEQUENCE` in 123's `steps.py`: the lifecycle steps in order, defined once, used for `until` (D4).
- The "apply intents" stage in `tick.py`, before observe (122's slot).
- `ProjectView` gains `desired` and `current_steps`. `decide()` gains the current-step guard (D7).
- `HumanStepPlanner` in the production planner tuple (D8).
- A new listing, `desired-states`, through the existing registry (CLI and `/v1/listings`).
- Contract text: the intent body format in `docs/inbox-contract.md`, the stage and the guard in `docs/process-contract.md`, and the 120 row in `docs/substrate-guide.md`.

**Excluded**

- **Validating bodies at submission.** The inbox keeps accepting any JSON object as an intent body. The Runner rejects what it cannot apply (D3).
- **Addressing targets by CF index.** Targets are node ids (D2).
- **Marking a step done, and relinking an orphan.** These stay in the slice plan's Future Work (items 8 and 3).
- **Anything that launches or resumes a run.** No production planner launches until 125. Resolutions are 127's.
- **Effective-state listing.** `desired-states` shows stored rows only. The per-step resolved view is a pure function that tests prove. A listing for it waits until an operator needs it.

## Dependencies

### Prerequisites

- **121, merged.** It provides `AcknowledgmentOutcome`, `acknowledge_message(…, outcome, reason, desired_state)`, `SetDesiredState`, `ClearDesiredState`, the `desired_states` table with its reads, and `intent_for_submission`.
- **123, merged.** It provides initiative, slice and step nodes, `LifecycleStep`, `StepLevel`, `STEP_MAP`, `LifecycleTree` (`is_linked`, `ready_steps`, `step_of`), `HumanStepPlanner` and `BlockHumanStep`.
- **122, merged.** It provides the tick skeleton with its slot before observe, the `Planner` seam, `decide()`, the fault boundary and `STORE_FAILURES`.

### Interfaces Required

**Store** (as 121 changes it):

| Call | Used for |
| --- | --- |
| `pending_intents(project_id)` | The intents to apply, in ascending `seq`. |
| `desired_state(project_id, node_id=…)` / `desired_states(project_id)` | The current row for one target. All rows, for the per-tick index. |
| `acknowledge_message(id, acknowledged_by, outcome, reason, desired_state)` | The applied, no-op or rejected answer and the row write, in one transaction. |
| `nodes_for_project(project_id)` | The tree that target checks run against. |

121's store rules this slice relies on: a desired state is accepted only with `applied`. `drive` and `hold` cannot both be null. `drive_until_step` requires `drive is True`. Clearing a target with no row writes nothing.

**Inbox.** An `intent` submission's `node_id` is checked by the inbox to be a node of the project, and the body arrives as the message's `payload`. Neither changes.

## Architecture

### Component Structure

```
amoeba/runner/intent/            NEW subpackage
  vocabulary.py   IntentKind, IntentBody (pydantic, extra="forbid"), IntentRejection,
                  until_applies(level, step)
  apply.py        apply_pending_intents(store, project_id): read → interpret → acknowledge
                  interpret(message, tree, current_row) -> Interpretation   (pure)
  governance.py   DesiredStateIndex, Governance, governing(), current_steps()   (pure)
amoeba/runner/lifecycle/
  steps.py        CHANGED  STEP_SEQUENCE and step_rank()
amoeba/runner/
  tick.py         CHANGED  apply intents first, then DesiredStateIndex read once, before observe
  decide.py       CHANGED  ProjectView.desired, .current_steps; current-step guard
  tenant.py       CHANGED  production planners = (HumanStepPlanner(),)
  lifecycle/human_steps.py  CHANGED  plans over view.current_steps
amoeba/inspection/
  desired_states.py  NEW  the desired-states listing rows
docs/inbox-contract.md, docs/process-contract.md, docs/substrate-guide.md  CHANGED
```

`interpret` is pure and holds every rule. `apply.py`'s loop only reads, calls it and writes. `governance.py` has no store access. The tick reads the rows once and hands it the index.

### Data Flow

Within one project's tick:

```
apply intents   pending_intents(P) ── none ──▶ skip (no tree read)
                     │ one or more
                     ▼
                tree ← LifecycleTree(nodes_for_project(P))
                for each intent, ascending seq:
                  row  ← desired_state(P, node_id=intent.node_id)
                  answer ← interpret(intent, tree, row)          pure
                  acknowledge_message(intent.id, acknowledged_by=runner,
                                      outcome, reason, desired_state)  one transaction
index           index ← DesiredStateIndex(desired_states(P))     rows only, no tree
observe         in-flight runs (122) — not filtered by hold
                from 125/128: status and checkout reads only if index.drives_anything()
                or a run is in flight
plan read / reconcile (123)
record / [route — 126]
decide          view.desired = index
                view.current_steps = ready_steps ∩ driven ∩ not held
                planners see current_steps; guard refuses any other node
act             BlockHumanStep (123), and from 125 the dispatch actions
```

Each intent reads its target's row after the previous intent's write, so "the later intent replaces the earlier" follows from processing in `seq` order.

### State Management

- **Durable:** `desired_states` rows (one per target), and each intent's acknowledgment outcome and reason on its message row. Both are 121's tables. This slice adds no schema.
- **Stored values are normalized** (D5). `hold` is stored as `true` or not set, never `false`. `drive` is `true`, `false` or not set.
- **Per tick, in memory:** the `DesiredStateIndex` built from one `desired_states(P)` read, right after the apply stage and before Observe. It is rebuilt every tick and never cached across ticks, so an intent applied at the top of a tick governs that same tick's Observe scope and Decide.

## Technical Decisions

### D1 — The body format: one closed `intent` field, plus `until` for drive
Status: decided

The body is a JSON object, validated by `IntentBody` (pydantic v2, `extra="forbid"`):

| Body | Meaning | Row write (D5) |
| --- | --- | --- |
| `{"intent": "drive"}` | Advance all work under the target. | `drive=true`, `until` not set, `hold` kept |
| `{"intent": "drive", "until": "<step>"}` | Advance work under the target up to and including `<step>`. | `drive=true`, `drive_until_step=<step>`, `hold` kept |
| `{"intent": "exclude"}` | Do not advance work under the target, unless a narrower target drives it. | `drive=false`, `until` not set, `hold` kept |
| `{"intent": "pause"}` | Issue nothing new under the target. This cannot be overridden from below. | `hold=true`, drive and `until` kept |
| `{"intent": "resume"}` | Remove the target's own pause. | `hold` not set, drive and `until` kept |
| `{"intent": "clear"}` | Remove the target's own settings, so the next one up applies. | Row deleted |

- `IntentKind` is a `StrEnum` with five values (`drive`, `exclude`, `pause`, `resume`, `clear`), defined once. The table has six rows because `drive` has two body forms. `until` takes a `LifecycleStep` value, and is accepted only with `drive`.
- **`extra="forbid"`.** An unknown key is rejected, not ignored. A misspelled `"untill"` must not silently drive everything.
- **Why `exclude` exists.** Drive and hold are independent in the arch. Drive `false` lets the PM drive initiative 120 except slice 125, which a later drive on slice 125 can still override. A pause cannot express that, because a pause cannot be overridden from below.
- **Why `pause` and `resume` and not `hold: true/false`.** The arch names them, and they read as commands for 160 to emit. They are settings, not events: applying either twice is the same as once.
- Rejected: a single body that sets fields directly, such as `{"drive": true, "hold": null}`. It would expose the store's null-means-unset encoding as the public contract, and 160's whitelist would have to reason about field combinations instead of a list of intents.

### D2 — The target is the message's `node_id`
Status: decided

- A missing `node_id` targets the project. Otherwise the node must be an initiative or a slice, and linked (`is_linked`, 123). The inbox already refuses a node outside the project.
- **A step node** is rejected (`target_not_initiative_or_slice`). Steps are work items, not targets. The arch's targets are a project, an initiative or a slice.
- **An orphaned or unlinked node** is rejected (`target_unlinked`). Its state would have no effect (D6), so applying it would answer "applied" to an intent that does nothing.
- Rejected: addressing targets by CF index in the body (`{"slice": 124}`). An initiative and its first slice share an index, a project may link several CF projects, and an index moves on a renumber while the arch keeps desired state on the node id. Node ids are listed by `amoeba inspect nodes` with their index, so the PM can look them up. An index-based CLI convenience can be added later on top of node ids, without changing the contract.

### D3 — Rejections are answers, never exceptions, and the inbox stays unchanged
Status: decided

- `IntentRejection` is a `StrEnum`: `malformed_body`, `target_not_initiative_or_slice`, `target_unlinked`, `until_not_applicable`. Each rejection is acknowledged `rejected` with reason `"<code>: <detail>"`. For example, `malformed_body: unknown key 'untill'`. The detail is at most the first pydantic error, bounded to 512 characters. The submitter branches on the outcome and reads the code. Nothing branches on the detail.
- Body validation happens in the Runner, not at submission. The inbox contract says intent bodies are the Runner's and 160's, and that the inbox does not interpret them. A rejected acknowledgment already gives the submitter an explicit answer through `intent_for_submission`.
- Rejected: validating `IntentBody` in the inbox's `intent` payload model. It would give earlier feedback, but it would make the inbox import Runner vocabulary, and the target rules (linked, kind) need the tree, which the inbox does not read. Feedback would then come from two places.

### D4 — `until` uses one step order, and must apply at the target's level
Status: decided

- `STEP_SEQUENCE` in `steps.py` lists the seven `LifecycleStep` values in process order: `architecture`, `slice_plan`, `slice_design`, `tasks`, `implementation`, `merge`, `integration`. `step_rank(step)` is the position. It is defined once, explicitly. Enum declaration order is not relied on.
- A step `s` under a driven target is **within drive** when `until` is unset or `step_rank(s) <= step_rank(until)`.
  - On an initiative or the project, this covers the initiative's own steps and its slices' steps. "Drive initiative 120 until `slice_design`" covers `architecture`, `slice_plan` and every slice's `slice_design`, and stops before `tasks` and `integration`.
  - On a slice, only slice-level steps exist below it.
- **`until_not_applicable`:** on a slice target, `until` must be a slice-level step (`STEP_MAP[until].level is StepLevel.SLICE`). `architecture`, `slice_plan` and `integration` are rejected, because they are never below a slice. Initiative and project targets accept any step.

### D5 — Merging, normalization and no-op
Status: decided

- **Merge.** Each kind writes only its own fields and keeps the others from the current row (D1's table). This is the merge 121 (D3) leaves to 124. `drive` and `until` travel together: `drive` without `until` clears a stored `until`, and `exclude` clears it too.
- **Hold is stored as `true` or not set.** Hold resolves as "true if any target on the path holds", so a stored `false` behaves exactly like no value. Writing it would make two rows mean the same thing. So `resume` unsets hold, and a row left with drive and hold both unset is deleted, as `clear` does. **This departs from the arch's "pause and resume set hold to true and false"** only in encoding: the resolved hold is the same. The arch is updated to say "resume removes the target's hold".
- **No-op means the stored row would not change.** If the merged row equals the current row, or `clear` finds no row, the intent is acknowledged `no_op` and nothing is written. The row keeps the `message_id` of the intent that last changed it. Applying the same intent twice therefore leaves the same state, and the second answer is `no_op`.
- **Driving to a step already passed.** The arch's example of an already-satisfied intent is "drive to a step the node has passed". That intent is a no-op only if it changes no row. If it changes one, it is applied, because it still restricts work. For example, a project drives everything and the PM drives slice 124 `until: tasks` after its tasks are done. That stops slice 124's implementation, which is a real change, so it is acknowledged `applied` with no reason. **This departs from the arch's example**, and the arch is updated to define no-op as "the target's settings would not change".

### D6 — Governance is a pure lookup up the path
Status: decided

- `DesiredStateIndex` maps a target to its row. The project's row has key `None`. It is built from one `desired_states(P)` read per tick, from the rows alone, so it exists before Observe. An orphan's row has no effect without any filtering: `ready_steps` returns only linked steps, and every ancestor of a linked step is linked (123, D5), so an unlinked target is never on a current step's path.
- `index.drives_anything()` is true when any row sets `drive` true. It is the Observe-scope predicate for 125 and 128 (Provides). An orphan's driving row can make it true, which costs only an extra read, never an action.
- `governing(tree, index, step) -> Governance(driven, held)`. The path is the step's container (slice or initiative), the slice's initiative if any, then the project.
  - **Drive:** the nearest row on the path whose `drive` is set. `driven` is that row's `drive`, and the step must also be within its `until` (D4). If no row on the path sets drive, the step is **not driven**. This is the defined default and the reason linking a project escalates nothing.
  - **Held:** true if any row on the path has `hold` set.
- `current_steps(tree, index)` is `tree.ready_steps()` filtered to steps that are driven and not held, in `ready_steps` order.
- No message is replayed. Governance reads only the rows and the tree.

### D7 — Planners see current steps, and Decide enforces it
Status: decided

- `ProjectView` gains `desired: DesiredStateIndex` and `current_steps: Sequence[Node]`, computed when the view is built. `HumanStepPlanner` plans over `view.current_steps` instead of `view.tree.ready_steps()`.
- **The guard.** `decide(view, planners)` raises `ValueError` if a planner returns an action whose `node_id` is not in `view.current_steps`. That is a programming error, and it faults the project through 122's one catch, the same as 122's duplicate-action rule. Nothing is silently dropped.
- **Why both.** The filter on the view makes the right thing easy for each planner. The guard makes "a held target issues nothing new" hold for every planner later slices add, 125's dispatch and 127's resumes included, without each of them re-checking hold. The rule is enforced in one place.
- **What hold does not stop.** Observe, ingestion (125), routing (126) and reconcile (123) do not read desired state. A held target's in-flight runs are still polled and recorded. A block written before the hold stays. A routing decision that escalates still escalates, because it issues nothing.
- A step that stops being current while it is `blocked_on_human` stays blocked. The PM resolves it, and while the step is not current it is not blocked again (123, D9).

### D8 — `HumanStepPlanner` registers in production with the drive filter
Status: decided

- The production tuple becomes `(HumanStepPlanner(),)`. 125 appends its dispatch planner.
- Together with D6's not-driven default, a newly linked project has no current steps, so it escalates nothing. Driving an initiative with no `archFile` blocks its `architecture` step on that tick, which is the intended "waiting on you".
- This meets plan entry 5's last criterion and 123's D9.

### D9 — Applying intents: one stage, store-only, before observe
Status: decided

- `apply_pending_intents(store, project_id)` runs first in each project's tick, as the arch orders it. With no pending intents it does nothing and reads no tree.
- **Every link's state is ignored here.** An intent is a store-only write, so a project whose CF link failed its probe still has its intents applied.
- **No budget check.** No subprocess runs, and each intent is one transaction. The same reasoning as 123's reconcile (D5) applies.
- **Failures:**
  - A store failure (`STORE_FAILURES`) re-raises, and the process exits (122, D8). The intent being applied is not acknowledged, because its acknowledgment and write are one transaction. It is applied again after restart.
  - Any other exception is a bug. It reaches 122's one catch as a project-scoped `unexpected_fault`, and the rest of that project's tick does not run. Intents already acknowledged stay acknowledged. The failing intent stays pending and is retried on the next tick. The escalation is deduplicated, so a bug that repeats every tick adds no rows.
- `acknowledged_by` is the Runner's actor name, the same constant 123 uses for `resolved_by`.
- **A tick return value.** Applying any intent counts as a store write, so `tick()` returns true (122).

### D10 — `amoeba inspect desired-states`
Status: decided

- A project-scoped listing in the existing registry, so it appears in the CLI and under `/v1/listings/desired-states` with no new code in either.
- Columns: `target` (`project`, or the node id), `drive`, `until`, `hold`, `message_id` and `updated_at`. Unset values are empty strings, as in the other listings. The columns come from the row alone, so inspection imports no Runner code. A target's kind, index and title are in `amoeba inspect nodes`.
- Rejected: a listing of every step's resolved state. It needs the tree and the step map inside inspection, and nothing yet needs it.

### Technology Choices

- Pydantic v2 for `IntentBody`, as the rest of the package uses. No new dependencies.
- Tests use `Store.open_temporary()` with hand-built trees and pending intents. No subprocess is involved.

### Patterns and Conventions

- Each is defined once: `IntentKind`, `IntentRejection`, `STEP_SEQUENCE`, the Runner's actor name, and the 512-character reason bound.
- `interpret` and `governing` are pure. All their rules are tested without I/O.
- The reason text is display data. Code and submitters branch on `AcknowledgmentOutcome` and on the `IntentRejection` code prefix, never on the detail.
- Modules stay under about 300 lines, and functions under about 50.

## Implementation Details

### API Contracts

**Intent body** (`docs/inbox-contract.md`, a new "Intent bodies" section, which replaces the `{"want": "a review"}` example):

```bash
# drive initiative 120 through slice design
amoeba submit intent --project amoeba --by operator --node-id <initiative-120-node> \
    --body '{"intent": "drive", "until": "slice_design"}'
# stop everything new in the project
amoeba submit intent --project amoeba --by operator --body '{"intent": "pause"}'
```

The answer is read with `amoeba inspect messages --project P --channel intent`, whose rows carry `acknowledgment_outcome` and `acknowledgment_reason` (121). A submitter holding a submission id uses `intent_for_submission`.

**Internal API** (used by 125–128):

```python
class IntentKind(StrEnum): DRIVE; EXCLUDE; PAUSE; RESUME; CLEAR
class IntentRejection(StrEnum): MALFORMED_BODY; TARGET_NOT_INITIATIVE_OR_SLICE; TARGET_UNLINKED; UNTIL_NOT_APPLICABLE

class IntentBody(BaseModel):            # extra="forbid"
    intent: IntentKind
    until: LifecycleStep | None = None  # only with DRIVE

@dataclass(frozen=True)
class Governance: driven: bool; held: bool

class DesiredStateIndex:                # built from desired_states(P) alone
    def drives_anything(self) -> bool: ...
def governing(tree: LifecycleTree, index: DesiredStateIndex, step: Node) -> Governance: ...
def current_steps(tree: LifecycleTree, index: DesiredStateIndex) -> Sequence[Node]: ...
def apply_pending_intents(store: Store, project_id: str) -> int: ...   # intents acknowledged
```

`steps.py` gains `STEP_SEQUENCE: tuple[LifecycleStep, ...]` and `step_rank(step) -> int`.

## Integration Points

### Provides to Other Slices

- **125:** `view.current_steps` as the set it dispatches from. A held or undriven step gets no pointer write and no launch, enforced by the guard. 125 owns the arch's Observe scope for its `cf status` read: it reads a project only when `index.drives_anything()` or the project has a run in flight. The index is built before Observe for this (D6).
- **126:** nothing to read. Routing runs on store state and does not consult desired state (D7).
- **127:** a resume is an action on a current step, so a held target is not resumed. A resolution that makes a step runnable puts it back under governance on the next tick.
- **128:** gates narrow `current_steps` further in Decide. Its checkout and gate reads in Observe use the same scope predicate as 125.
- **129:** the intents the first proof is driven with, and `inspect desired-states` for its write-up.
- **160:** the body format as the contract it translates into. Its OQ5 whitelist is a subset of `IntentKind`.
- **Contract documents:** the intent body format, the rejection codes and the no-op rule (`inbox-contract.md`); the apply stage and the current-step guard (`process-contract.md`); the 120 row (`substrate-guide.md`).

### Consumes from Other Slices

- **121:** acknowledgment outcomes and the desired-state write inside the acknowledgment. If a store shape rule raises `ValueError` for a row `interpret` produced, that is a bug in `interpret` and is handled as in D9.
- **123:** the tree, the step map and `HumanStepPlanner`. `tree.py` and `reconcile.py` are unchanged, as 123 promised. `steps.py` gains only the sequence.
- **122:** the slot before observe, `ProjectView`, `decide()` and the fault boundary.

## Success Criteria

### Functional Requirements

- **Idempotence and order:**
  - The same intent applied twice leaves the same row, and the second is acknowledged `no_op`.
  - For one target, `drive until tasks` then `drive until implementation` leaves `until: implementation`.
  - `pause` then `drive` on one target keeps the pause.
- **Hold wins:**
  - With the project paused and a slice set to `resume`, the slice's ready steps are not current.
  - Clearing (or resuming) the project makes them current, if driven.
- **Drive resolves from the nearest target:**
  - The project driven and an initiative excluded: that initiative's steps are not current, and a slice under it driven again is current.
  - `until` stops at its rank: driving an initiative `until slice_design` makes `slice_design` current and never `tasks`.
- **Governance is a lookup.** `governing` takes the tree and the rows only. A test builds both by hand and asserts `driven` and `held`.
- **Exactly one acknowledgment** per intent, with each outcome produced:
  - `applied` for a row change;
  - `no_op` for an unchanged row, and for `clear` or `resume` with nothing to remove;
  - `rejected` with each `IntentRejection` code: a malformed body, an unknown key, `until` on a non-drive kind, a step-node target, an orphaned target, and `architecture` as `until` on a slice.
- **Held targets issue nothing new.** With a test planner that emits an action for every ready step, a held step's action raises the guard's `ValueError`. With the production planners, a held human step is not blocked. A run in flight under a held slice is still polled and recorded (122's stub `sq`).
- **`HumanStepPlanner` in production:** linking a fixture project blocks nothing. Driving an initiative with no `archFile` blocks its `architecture` step on the next tick.
- **Crash safety:** a store failure injected inside `acknowledge_message` leaves the intent pending and no row written. The next tick applies it once.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- `interpret` and `governing` have table-driven tests for every row of D1, D4 and D5.
- The contract documents under Provides are updated, and the CHANGELOG has an entry.

### Integration Requirements

- 100's contract suite passes. Its stand-in Runner acknowledges intents in its own test projects and is unaffected.
- 122's and 123's tests pass with the changed `ProjectView` and production tuple.
- 125 can add its dispatch planner over `view.current_steps` without changing `intent/` or the guard.

### Verification Walkthrough

Run in bash from the repository root. Step 1 is automated. Steps 2–4 use the real `cf` on this repository, read-only. Nothing launches a run, because no production planner launches until 125. Human-step blocks are store writes only.

1. **Tests:**
   ```bash
   uv run pytest tests/runner/intent tests/runner/test_decide.py -v
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   uv run pytest tests/contract -v
   ```
   Expected: all pass. The intent tests are named for their rules, for example `test_project_pause_wins_over_slice_resume` and `test_same_intent_twice_is_no_op`.

2. **Link and see that nothing escalates.** As in 123's walkthrough step 3, start a throwaway process and link this repository:
   ```bash
   export AMOEBA_STORE_DIR=$(mktemp -d)
   amoeba start &
   amoeba submit create-project --project amoeba --by operator
   amoeba submit link-cf-project --project amoeba --by operator --cf-project-id <id>
   sleep 5; amoeba inspect messages --project amoeba --channel escalation
   ```
   Expected: no rows. `HumanStepPlanner` is in production, but nothing is driven.

3. **Drive, repeat, pause and clear.** Find initiative 140's node id in `amoeba inspect nodes --project amoeba` (the initiative row with `cf_index` 140), then:
   ```bash
   amoeba submit intent --project amoeba --by operator --node-id <i140> --body '{"intent": "drive"}'
   sleep 3; amoeba inspect messages --project amoeba
   ```
   Expected: the intent row has `acknowledgment_outcome` `applied`, and one escalation row names `architecture is a human step` for initiative 140. Then:
   - Submit the same intent again. Its row shows `no_op`.
   - Submit `{"intent": "pause"}` with no node id, then drive initiative 150 the same way. 150's intent is `applied`, but no escalation appears for 150, because the project is paused.
   - `amoeba inspect desired-states --project amoeba` shows three rows: the project (`hold` true), 140 and 150 (`drive` true).
   - Submit `{"intent": "resume"}` with no node id. On the next tick, an escalation for 150's `architecture` appears, and the project's row is gone from `inspect desired-states`.

4. **Rejections.** Submit `{"intent": "drive", "untill": "tasks"}` for the project, and `{"intent": "drive"}` with the node id of 140's `architecture` step. `amoeba inspect messages --project amoeba --channel intent` shows both `rejected`, with reasons starting `malformed_body:` and `target_not_initiative_or_slice:`. Stop the process with `amoeba stop`.

## Implementation Notes

### Development Approach

Relative effort: 2/5. Suggested order. Each step leaves the suite green.

1. `STEP_SEQUENCE` and `step_rank` in `steps.py`, and `vocabulary.py` with its model tests (D1, D3, D4).
2. `interpret` in `apply.py`, table-driven over D1–D5, then `apply_pending_intents` against a temporary store, with the crash test (D9).
3. `governance.py`, table-driven over D6.
4. `ProjectView.desired` and `current_steps`, the guard in `decide()`, `HumanStepPlanner` on `current_steps`, and the production tuple (D7, D8). Then the apply stage in `tick.py`.
5. The `desired-states` listing (D10).
6. Contract documents and the CHANGELOG.

**Testing approach.** The pure functions get most of the cases. One tick-level test per Functional Requirement uses `Store.open_temporary()`, the stub `cf` fixture plan from 123 and the stub `sq` from 122.

### Special Considerations

- **Arch and slice plan edits,** made with this design. They follow the departures above:
  - In the arch's intent paragraph: resume removes the target's hold rather than setting it false (D5). No-op is defined as "the target's settings would not change", and driving to a passed step is applied when it restricts (D5).
  - In plan entry 5: the no-op wording follows D5.
- **A pending intent that faults every tick** stops its project's tick until the bug is fixed. That includes Observe, so ingestion and checkout release for that project wait too. This can only be a code bug, because every body and target error is a rejection (D3). The deduplicated `unexpected_fault` shows it. Giving apply its own fault scope, so Observe still runs, is deferred until the first proof shows it matters (issue #12).
- **Security.** Intent bodies are PM-supplied data. They are validated against a closed model and never executed or passed to a subprocess. The rejection detail is bounded.
