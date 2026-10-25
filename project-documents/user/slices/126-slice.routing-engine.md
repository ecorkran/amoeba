---
docType: slice-design
slice: routing-engine
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies:
- 121
- 125
interfaces:
- 127
- 128
- 129
- 140
dateCreated: 20261020
dateUpdated: 20261021
status: not_started
turns: 25
promptTokens: 2398881
cachedTokens: 2235633
cacheWriteTokens: 163206
completionTokens: 38276
durationSeconds: 387.2
costUsd: 2.518787
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Routing Engine

## Overview

This slice gives every finished run a route, chosen by a static table and recorded with enough evidence to recompute it.

- **The table** is a YAML file, loaded and validated once at start, and never mutated. It holds ordered rules and the per-pipeline time bounds. Its version is the sha256 digest of its bytes. A table that fails validation stops `amoeba start`.
- **Inputs are closed and defined in code.** Ten named inputs, each with a closed value set that includes `unknown`, are reduced from store state: the run's outcome, checkpoint and failure kind, the recorded verdict, its standing, finding severity and recurrence, the lifecycle step and the node's state. Code defines the inputs and the route eligibility predicates. The table alone chooses routes.
- **Routes** are `advance` (mark the step done), `rerun` (a fresh run of the same step, eligible while under the rule's `max_attempts`) and `escalate` (block on a human, with a `judge_eligible` mark for 140). The first match wins, and the table must end in a catch-all escalate.
- **A route stage** in each project's tick routes every entry from 125's `unrouted_outcomes`. Each decision goes through 121's `record_routing_decision`, which stores the table version on first use and lands the decision, the attempt increment and the node effect in one transaction.
- **Time bounds.** An in-flight run older than its pipeline's bound raises a project-scoped `run_overrun` escalation. The run is never killed.

## Value

Developer value, and the method's foundation:

- Every outcome gets an explained route. `amoeba inspect routing-decisions` shows the rule, the inputs and the table version for each one, and checks that the decision recomputes.
- A slice step that passes advances on its own, and its successor runs on the next tick. With 125, this is the first time a slice moves through more than one step unattended.
- "Build by inducing failure" becomes a table edit and a restart. No code changes.
- A hung run is visible to the PM within its time bound, which closes the gap 125 left open (125, D12).

## Technical Scope

**Included**

- `amoeba.runner.routing`, a new subpackage: the input vocabulary and reduction, the table model and loader, the pure evaluator, recomputation, the route stage, and the overrun check.
- The first table, shipped in the package as `amoeba/runner/routing/tables/default.yaml`.
- A `routing_table_path` setting with the `--routing-table` start flag, whose default is the shipped table.
- Start-up loading: the table and the Amoeba version label are read once in `runner_tenant()`. Failures raise `StartupFailedError`.
- `FaultKind` gains `run_overrun`.
- CLI: `amoeba inspect routing-decisions`.
- Contract text in `docs/process-contract.md` (the route stage, the tick order and the table file format) and `docs/substrate-guide.md` (the 120 row).

**Excluded**

- **Gate state and check standing as inputs (128).** Their observations do not exist until 128, which adds both to the input vocabulary (D3).
- **Tier inference (131)** and the **judge route (140).** The table carries `judge_eligible` only.
- **Resolutions (127).** What happens after a PM answers an escalation is 127's.
- **Per-project tables** (D2). One table serves every project in v1.
- **Store changes.** 121 and 125 already provide every write and read this slice needs. No migration.
- **Killing a run**, under any condition.
- **A standalone `amoeba routing-table check` command.** `amoeba start` already refuses an invalid table with every problem listed. Deferred to issue #13.

## Dependencies

### Prerequisites

- **121, merged:** `record_routing_decision` with `StatusEffect` and `BlockEffect`, `Route`, `routing_table_version`, `routing_decision_for_entry`, `routing_decisions` and `attempt_count`.
- **125, merged:** `unrouted_outcomes`, the flag that a decision clears, the `sq_run` entry result (`outcome`, `outcome_document`, `verdict_ids`, `review_fault`), the blocks ingestion writes, and `CheckpointKind` and `FailureKind`.
- **122, 123 and 124, merged:** the tick skeleton and faults, `LifecycleStep` and `STEP_MAP`, and the rule that routing reads no desired state (124, D7).
- **Plan edit, committed with this design:** entry 9 (128) registers the gate-state and check-standing inputs (D3).

### Interfaces Required

- **Store reads:** `unrouted_outcomes(project)`, `get_node`, `verdict(id)`, `finding_changes(id)`, `observations(id)`, `attempt_count(node, step)` and `journal_entries` for the in-flight runs.
- **Store write:** `record_routing_decision(decision, *, table, effect, attempt_step)` (121, D5). Its transaction is the whole write of a decision.
- **Entry results:**
  - 125's ingestion: `{run_id, outcome, status, outcome_document, verdict_ids, review_fault}`.
  - 122's launch failure: `{run_id, launch_failure}`, resolved `failed`.
- **Evidence vocabularies:** `ReviewVerdict`, `VerdictStanding`, `FindingSeverity` and `FindingChange` from `amoeba.store`.
- **PyYAML**, already a dependency.

## Architecture

### Component Structure

```
amoeba/runner/routing/                   NEW
  inputs.py      RoutingInput, the value set of each, UNKNOWN and NONE;
                 reduce(evidence) → RoutingInputs (pure)
  evidence.py    gather(store, entry) → OutcomeEvidence (store reads only)
  table.py       TableFile (pydantic, extra="forbid"), RoutingTable, Rule;
                 parse_table(text) / load_table(path); TableError lists every problem
  engine.py      evaluate(table, inputs) → Match(rule, route, parameters) (pure);
                 the route eligibility predicates; effect_for(match, inputs) (pure)
  recompute.py   recompute(decision, stored_version) → Recomputation (pure)
  stage.py       route_outcomes(store, project, routing) — one decision per entry
  overrun.py     overrun_runs(in_flight, table, now) (pure)
  tables/default.yaml   the first table
amoeba/runner/
  tick.py        CHANGED  view built after record; route stage; overrun check
  faults.py      CHANGED  FaultKind += run_overrun
  factory.py     CHANGED  load the table and the Amoeba version label at start
amoeba/process/settings.py, amoeba/cli/settings_flags.py   CHANGED  routing_table_path
amoeba/cli/
  inspect.py     CHANGED  routing-decisions (listing + recompute column)
amoeba/inspection/routing.py   NEW  the decision listing rows
pyproject.toml   CHANGED  the tables directory ships in the wheel, like the SQL
```

The evaluator and the reducer are pure, so the CLI's recompute column reuses them over a read-only store.

### Data Flow

One project's tick, with this slice's changes marked:

```
apply intents (124)
observe   in-flight runs, read-backs, plan read (122, 123, 125)
record    finished runs → ingest (125)                 ── sets awaits_routing
overrun   check over in-flight runs                    ── NEW, D7: beside watch_pointers, before raise_expected_faults
view      ProjectView built here, before routing        ── CHANGED (D8)
route     for entry in unrouted_outcomes(project):      ── NEW
              evidence ← gather(store, entry)            store reads
              inputs   ← reduce(evidence)                pure
              match    ← evaluate(table, inputs)         pure
              effect   ← effect_for(match, inputs)       pure
              record_routing_decision(…, table, effect, attempt_step=step)
decide    planners over the view (unchanged)
act       (unchanged)
close     project escalations, including run_overrun
```

The route stage and the overrun check make store reads and pure computations only. They start no subprocess, so they add no `TickBudget` check, and the tick's worst case stays 122's deadline plus one call timeout. Their cost is bounded by unrouted outcomes and in-flight runs, not by history.

**One outcome, end to end:**

```
tick m    record:  P4 run completed, review PASS (stated) → entry resolved, awaits_routing
          view:    slice_design AWAITING_ROUTING; tasks not ready
          route:   inputs {outcome: completed, verdict: pass, standing: stated, …}
                   rule advance-on-stated-pass → StatusEffect(done), attempt 1
          decide:  nothing for slice_design (the view predates the route)
tick m+1  view:    slice_design done; tasks ready and current → DispatchPlanner (125)
```

### State Management

- **Durable, in the store (121's tables):** each decision with its inputs, rule id, table version, Amoeba version, route and parameters; each table version's content, on first use; attempt counts per step node.
- **In memory, for the process's lifetime:** the loaded `RoutingTable` and the Amoeba version label. Both are frozen at start. A restart is the only way to change them, which 100's recovery already makes safe.
- **Nothing per tick** beyond the inputs being reduced. Overrun escalations follow 121's project-scoped dedup and 122's closure rule.

## Technical Decisions

### D1 — The routing inputs, and what `unknown` and `none` mean
Status: decided
- `RoutingInput` is a `StrEnum`, defined once in `inputs.py`. Each input has a closed value set, also defined there. Two values are shared: `none` means the input does not apply to this outcome (a completed run has no checkpoint), and `unknown` means it should apply and could not be read. Neither is a default.

  | Input | Values (besides `unknown`) | Reduced from |
  | --- | --- | --- |
  | `outcome` | `completed`, `paused`, `failed`, `orphaned`, `vanished`, `launch_failed` | the entry result's `outcome`, or `launch_failure` |
  | `checkpoint_kind` | `loop_exhausted`, `interactive_checkpoint`, `awaits_human`, `other`, `none` | `outcome_document.checkpoint.kind` |
  | `at_loop` | `true`, `false`, `none` | `checkpoint.is_loop` |
  | `failure_kind` | `provider_error`, `stall`, `artifact_missing`, `cost_cap`, `none` | `outcome_document.failure.kind` |
  | `verdict` | `pass`, `concerns`, `fail`, `none` | the recorded verdicts (`verdict_ids`) |
  | `standing` | the seven `VerdictStanding` values, `none` | the recorded verdicts |
  | `severity` | `pass`, `note`, `concern`, `fail`, `none` | the highest finding severity in the recorded review |
  | `recurrence` | `recurring`, `new`, `clear`, `none` | `finding_changes` of each recorded verdict |
  | `step` | the seven `LifecycleStep` values | the node's `cf.phase` |
  | `node_state` | `runnable`, `blocked`, `done` | the node's status |

- **Reduction rules,** each defined once:
  - `verdict`, `standing`, `severity` and `recurrence` are `none` when `verdict_ids` is empty, and `unknown` when `review_fault` is set or the verdict is `UNKNOWN`.
  - **A split review** combines its parts. `verdict` is the worst part (`fail` over `concerns` over `pass`). `standing` is the parts' common standing, or `unknown` when they differ. `severity` is the highest across parts.
  - `recurrence` looks only at findings of severity `concern` or `fail` (`ROUTED_SEVERITIES`): `recurring` when any is tagged recurring, `new` when there are some and none recur, `clear` when there are none. It is `unknown` when a part's `finding_changes` is not comparable.
  - A null field in the outcome document, or a kind outside its vocabulary, is `unknown`. 125's `parse_*_kind` functions are reused, so no near match is ever taken.
  - `node_state` maps the three `blocked_on_*` statuses to `blocked`, and any status the Runner does not write (`in_progress`) to `unknown`.
- **Attempts** are recorded with every decision but are not a matchable input. A rule bounds them with `max_attempts` (D4), so the grammar needs no numeric comparisons. `attempt` is the run's number for its step: `attempt_count(node, step) + 1`. When `step` is `unknown` it cannot be counted, and is recorded as null.
- **Departures from plan entry 7 and the arch's input list:**
  - `node_kind` is not an input. Every routed outcome is on a step node (125, D7), so it would be constant, and `step` already tells the levels apart.
  - Finding severity is one input (the highest), and recurrence counts only `concern` and `fail` findings. A note recurring is not a reason to route differently.
  - `recurrence` uses `recurring`, `new`, `clear` and `none`, not the arch's `new` / `recurring` / `gone`. Those are per-finding tags in 104's `finding_changes`. A routing input needs one value per outcome, so the tags are folded over `concern` and `fail` findings as above. `gone` findings (previous ones now absent) do not change the route, and an outcome where every finding is gone reduces to `clear`.
  - Attempt count is not a matchable input (see "Attempts" above).
  - Gate state and check standing are added by 128 (D3).

### D2 — The table file: one YAML file for every project, versioned by digest
Status: decided
- **Format** (documented in `docs/process-contract.md`):

  ```yaml
  format: 1
  time_bounds_minutes: {P4: 240, P5: 240, P6: 720}
  rules:
    - id: advance-on-stated-pass
      when: {outcome: completed, verdict: pass, standing: stated}
      route: advance
    - id: rerun-new-concerns
      when: {outcome: completed, verdict: concerns, standing: stated, recurrence: new}
      route: rerun
      max_attempts: 2
    - id: escalate-everything-else
      when: {}
      route: escalate
      judge_eligible: false
  ```

  A condition's value is one value or a list. Values are compared after trimming and lower-casing, so `PASS` and `pass` are the same value, and YAML's flow and block styles both parse.
- **`format`** is required, and the only member of its closed set in this slice is `1`. It lets a later loader read an old stored version for recomputation after the grammar changes, which is the plan's named risk.
- **Version label:** `sha256:<hex>` of the file's bytes. Editing the table always makes a new version, so 121's "same version, different content" error cannot happen through a forgotten label bump. The stored content is the file's text, verbatim.
- **Location.** `routing_table_path` defaults to the shipped `default.yaml`, a constant in `settings.py`. `--routing-table PATH` points at another file. Editing the shipped table in this repository keeps table history in git, which is where the first proof's table edits belong.
- **No per-project override in v1.** One table keeps "which table decided this" a single answer per process, and no project has needed different rules yet. The plan left this open. A Future Work entry records the override for when the proof or a second project shows the need. The merge policy, the one per-project value the arch names, is 128's per-project config, not the table's.
- Rejected: TOML. PyYAML is already a dependency, and YAML lists of mappings read better for rules.

### D3 — The input vocabulary grows by code, never by table
Status: decided
- A table may name only inputs and values in `inputs.py`. 128 adds `gate_state` and `check_standing` there, with their reducers, when it has the observations behind them. Until then, a table naming either one refuses to load, which is more honest than an input that is always `unknown`.
- Adding an input changes no existing rule's meaning: a rule constrains only the inputs it names.
- The plan's entry 9 (128) is edited with this design to say it registers both inputs.

### D4 — Matching, route eligibility, and the catch-all
Status: decided
- **Matching.** Rules are evaluated in file order. A rule matches when every input it names has a value in that condition's set. An input a rule does not name is unconstrained. `unknown` is in a condition's set only when the condition names it, so an unknown value never satisfies a condition by default. This is the arch's grammar as written.
- **Eligibility predicates,** defined once in `engine.py`. A matching rule whose route is not eligible is passed over, and evaluation continues with the next rule:
  - `advance`: `node_state` is `runnable`.
  - `rerun`: `node_state` is `runnable`, `step` is not `unknown`, and `attempt < max_attempts`. So a step runs at most `max_attempts` times through rerun rules, and an outcome whose attempts cannot be counted is never rerun: the next rule or the catch-all applies.
  - `escalate`: always eligible.

  The predicates restrict a route. They never choose one: what happens after a rerun limit is the next rule that matches, which the table decides. This is how "the attempt limit then escalates" holds without a route chosen in code.
- **Load-time validation.** Every problem is collected and reported together, naming the rule id:
  - `format` is a supported value. Rule ids are non-empty and unique.
  - Every input and value is in D1's sets (D3).
  - `route` is a `Route` member. 121's `Route` has `advance`, `rerun` and `escalate`, and 140 adds `judge`.
  - Parameters: `rerun` requires `max_attempts`, an integer of at least 1. `escalate` requires `judge_eligible`, a boolean. `advance` takes none. Unknown keys are refused (`extra="forbid"`).
  - `advance` and `rerun` rules must name `outcome: completed` and nothing else for `outcome`. A paused run is resumed, never rerun or advanced, and a failed one is the PM's (arch, "The routing engine").
  - The last rule has an empty `when` and route `escalate`. No earlier rule has an empty `when`, since it would hide every rule after it.
  - `time_bounds_minutes` has one positive integer for each pipeline in `STEP_MAP`, and no other key.
- A table file that is missing or unreadable, or whose YAML does not parse, fails the same way as a validation problem, naming the path and the error.
- A table that fails raises `StartupFailedError` from `runner_tenant()`, listing the problems, and `amoeba start` exits `STARTUP_FAILED`.

### D5 — Each route's effect on the node, and attempt counting
Status: decided
- `effect_for(match, inputs)` is pure, and is the one place a route becomes a store effect:

  | Route | `node_state` | Effect |
  | --- | --- | --- |
  | `advance` | `runnable` (eligibility) | `StatusEffect(done)` |
  | `rerun` | `runnable` (eligibility) | none. The step stays `runnable`, and 125's `dispatch_state` reads a routed `sq_run` as `NEEDS_POINTER`, so the next tick writes the pointer and relaunches the same pipeline with no instructions. |
  | `escalate` | `runnable` | `BlockEffect` on `HUMAN`, context `routed by <rule id>`, payload `{reason: routed, rule_id, table_version, run_id, judge_eligible}` |
  | `escalate` | `blocked`, `done` or `unknown` | none. Ingestion's block already stands (125, Provides), and a done node takes no writes (121, D1). |

- **Every decision on a step counts one attempt.** `attempt_step` is the `step` input whenever it is known, so the counter equals the number of runs of that step that have been routed. It is null when `step` is `unknown`.
- **The decision row:**
  - `inputs`: every input's value, plus `attempt`.
  - `route_parameters`: the rule's parameters (`max_attempts` or `judge_eligible`).
  - `journal_entry_id`: the routed entry, so 121's unique index makes a second decision for one outcome impossible.
  - `amoeba_version`: the installed package version, read once at start with `importlib.metadata.version("amoeba")`. If it cannot be read, start fails.
- **Failure handling in the route stage:**
  - A `verdict_id` in the entry result whose verdict, observations or `finding_changes` read raises `VerdictNotFoundError` makes the review inputs `unknown`, so the outcome is routed (normally by the catch-all) rather than faulting the project on every tick.
  - A store write failure in `record_routing_decision` is one of 122's `STORE_FAILURES`. It is re-raised and the process exits, as the arch requires. Recovery and `unrouted_outcomes` then route the outcome after restart.
  - Any other exception reaches 122's one catch and faults the project. The entry stays unrouted.
- **A crash** before the decision's transaction leaves the entry in `unrouted_outcomes`. After it, the decision, its effect and its attempt are all there. Routing again is impossible because the flag is cleared in the same transaction (125, D8).

### D6 — Recomputation from the record alone
Status: decided
- `recompute(decision, stored_version)` parses the stored content with `parse_table`, evaluates it on the decision's recorded `inputs` (including `attempt`), and returns the rule id and route it gets, and whether both equal the record.
- It reads nothing else, so it meets the plan's "from its record and its stored table version alone". It checks the table's application. The reduction from raw evidence is checked by the reducer's own tests, and the evidence stays in the store, linked through `journal_entry_id`.
- `amoeba inspect routing-decisions --project P [--node ID] [--json]` lists decisions oldest first with `decided_at`, node, step, rule id, route, attempt, the short version, and `recomputes`. It opens the store with `Store.open_read_only`, as every `inspect` command does, so it is safe beside a running process, and a store at another schema version fails with the existing `StoreSchemaError` exit.
- `recomputes` is `yes` or `no` when the stored table parses, and `error: <reason>` when its version row is missing or its content does not parse (for example an unsupported `format`). An unreadable table is never shown as a mismatched decision.

### D7 — Per-pipeline time bounds raise a project-scoped escalation
Status: decided
- Beside `watch_pointers`, before `raise_expected_faults` (so before the route stage), `overrun_runs(in_flight, table, now)` lists each unresolved `sq_run` entry whose age exceeds its pipeline's bound. Age is `now - issued_at`. The entry is journaled just before the launch, so this needs no field from the outcome document, which a running run has not finished writing. 125's recorded `started_at` is not needed.
- If the list is non-empty, the Runner raises `run_overrun`, a project-scoped escalation with the payload `{runs: [{node_id, run_id, pipeline, issued_at, bound_minutes}], table_version}`. A node with a run in flight is never blocked mid-run (122, D8), which is why this is project-scoped.
- The condition counts as a recurrence on every tick it holds, so the escalation closes on the first complete tick with no overrun, normally the tick that ingests the run. 125's D11 dedup limit applies: a second run that overruns while the escalation is open joins it only when it is raised again.
- **The table decides the bound, and the response is fixed.** This is the one stated exception to the arch's "no route is chosen in a code branch outside the table", and departs from its "the node escalates". The arch is edited to say both. An in-flight run can only be escalated: it has no outcome to advance, and a rerun would start a second pipeline in a held checkout. So no rule chooses it, and no decision record is written. A decision record would also take the entry's one decision slot, which its outcome needs.
- An in-flight entry whose pipeline has no bound is a programming error (`ValueError`) and faults the project through 122's catch. Every pipeline the Runner launches is in `STEP_MAP`, and load validation requires a bound for each. **For 127:** a resume entry must carry its `pipeline` key, so a resumed run is bounded from its resume.
- The shipped bounds (P4 and P5 240 minutes, P6 720) are starting values to be calibrated by 129's runs. They are table data, so changing them is a table edit.

### D8 — Routing takes effect on the next tick
Status: decided
- The arch says a successor made runnable by routing is decided on the next tick, after a fresh observation. So `ProjectView` is built after record and before route, and Decide uses that view. Every effect of routing (a done step, a rerun's `NEEDS_POINTER`, a block) is seen first by the next tick's view.
- This is safe for the routed step itself. In the view it is `AWAITING_ROUTING`, for which the dispatch planner does nothing (125, D3).
- Routing reads no desired state (124, D7). A held step's outcome is still routed. Advance on a held step marks it done and issues nothing, and its successor stays not current while the hold lasts.
- **This changes 125's data flow** in one place: the view was drawn after `[route]`, and is now built before it.

### D9 — The first table
Status: decided
- The shipped table routes only on recorded evidence, as the arch requires before the first proof:
  1. `advance-on-stated-pass`: completed, verdict `pass`, standing `stated`, advance.
  2. `rerun-new-concerns`: completed, verdict `concerns`, standing `stated`, recurrence `new`, rerun with `max_attempts: 2`.
  3. `escalate-completed-concerns`: completed, verdict `concerns` or `fail`, escalate with `judge_eligible: true`. These are the outcomes the Judge would weigh (arch, "Escalations from inside a run").
  4. `escalate-everything-else`: catch-all escalate, `judge_eligible: false`. Every pause, failure, unknown and untrusted standing lands here.
- Every pause escalates, as the plan requires. Rerunning a CONCERNS run reruns a phase pipeline with `existing: keep`, so it revises the work on disk with the fresh review as feedback (arch).
- A recurring concern is not rerun. The same finding twice means another round is unlikely to fix it.

### Technology Choices

- PyYAML's `safe_load` for the file, pydantic v2 for its model with `extra="forbid"`, `hashlib` for the version, and `importlib.metadata` for the Amoeba version. No new dependencies.
- The shipped table is read through `importlib.resources`, and the wheel includes it, as it does the migration SQL.

### Patterns and Conventions

- Defined once: `RoutingInput` and each value set, `UNKNOWN` and `NONE`, `ROUTED_SEVERITIES`, the combine order for split-review verdicts, the eligibility predicates, the escalate payload keys and `reason: routed`, the version prefix `sha256:`, `FaultKind.run_overrun`, and the default table path.
- `reduce`, `evaluate`, `effect_for`, `recompute` and `overrun_runs` are pure and table-tested.
- A source test asserts that `Route` members are compared only in `engine.py` (`evaluate`, the eligibility predicates and `effect_for`) and `validate.py`. `validate.py` only checks the grammar (which parameters each route requires); it chooses no route. So no route is chosen in a code branch elsewhere.
- Expected failures are answers. A table problem is a `TableError` that lists every problem. Unexpected exceptions in the route stage reach 122's one catch.
- Modules stay under about 300 lines and functions under about 50.

## Implementation Details

### API Contracts

**Internal** (used by 127–129 and 140):

```python
class RoutingInput(StrEnum): OUTCOME; CHECKPOINT_KIND; AT_LOOP; FAILURE_KIND; VERDICT
                             STANDING; SEVERITY; RECURRENCE; STEP; NODE_STATE
@dataclass(frozen=True)
class RoutingInputs: values: Mapping[RoutingInput, str]; attempt: int
@dataclass(frozen=True)
class Rule: id: str; when: Mapping[RoutingInput, frozenset[str]]; route: Route
            max_attempts: int | None; judge_eligible: bool | None
@dataclass(frozen=True)
class RoutingTable: version: str; content: str; rules: tuple[Rule, ...]
                    time_bounds_minutes: Mapping[str, int]
def parse_table(text: str) -> RoutingTable: ...          # raises TableError
def load_table(path: Path) -> RoutingTable: ...
def evaluate(table: RoutingTable, inputs: RoutingInputs) -> Match: ...
def recompute(decision: RoutingDecision, stored: RoutingTableVersion) -> Recomputation: ...
```

**CLI:**

- `amoeba start --routing-table PATH`. It also lets tests and the first proof run a small table.
- `amoeba inspect routing-decisions --project P [--node ID] [--json]` (D6).

## Integration Points

### Provides to Other Slices

- **127:**
  - Each escalation's decision and rule, read with `routing_decision_for_entry`.
  - An outcome's entry already has its one decision, so a resolution of an escalated outcome is recorded without that entry id. Whether 127 uses `record_routing_decision` for store-only accept, with `journal_entry_id` null, is 127's choice (121, Provides).
  - Resume entries carry `pipeline`, so they are bounded (D7).
- **128:** the input vocabulary to add `gate_state` and `check_standing` to (D3). The table's rules then use them, through a table edit.
- **129:** decisions and their recompute check for the proof's write-up, and the table as the place each wrong stop's fix goes.
- **140:** `judge_eligible` in every escalate decision's `route_parameters`, and `Route` to add `judge` to.
- **Contract documents:** `process-contract.md` (the route stage, the view built before it, the overrun escalation, and the setting and flag), and the table file format, inputs, values, eligibility and validation rules), and `substrate-guide.md` (the 120 row).

### Consumes from Other Slices

- **121:** `record_routing_decision`, `Route`, table versions, attempt counts, and the project-scoped escalation.
- **125:** `unrouted_outcomes`, the entry result, the blocks ingestion wrote, and the kind parsers.
- **123 / 124:** `LifecycleStep`, `STEP_MAP`, and routing's independence from desired state.
- **122:** the tick skeleton, the fault boundary and closure, and `StartupFailedError`.
- **104:** verdicts, standing, findings and `finding_changes`.

## Success Criteria

### Functional Requirements

- **Recomputation:** for every decision the tests record, `recompute` returns the same rule and route from the decision row and its stored table version alone. Editing the table file and restarting stores a second version, and old decisions still recompute against the first.
- **Advance:** a completed P4 run with a stated PASS marks `slice_design` done. `tasks` is dispatched on the next tick, not the same one.
- **Rerun:** a completed run with stated CONCERNS and new findings records `rerun`. The next tick writes the pointer and launches the same pipeline with no instructions. With `max_attempts: 2`, the second such outcome falls through to `escalate-completed-concerns`, which blocks the step on `HUMAN`. A rerun rule that does not name `step` is passed over for an outcome whose `step` is `unknown`.
- **Escalate:** a paused run's decision is `escalate` with no second block, and the node stays `blocked_on_sq_checkpoint`. A failed, orphaned, vanished or launch-failed run is escalated with no second block. An unknown review escalates.
- **Load refusal:** each of these makes `amoeba start` exit `STARTUP_FAILED`, with the problem named: no catch-all, a catch-all that is not `escalate`, an empty `when` before the last rule, an unknown input or value (including `gate_state` before 128), an unknown route, a missing or extra parameter, an advance or rerun rule not limited to `outcome: completed`, a duplicate rule id, a missing or extra time bound, an unsupported `format`, a missing or unreadable table file, and malformed YAML.
- **Unknown:** an input that reduces to `unknown` satisfies only a condition that names `unknown`.
- **No route in code:** a test asserts that `Route` members are compared only in the evaluator, the effect mapping and the load-time grammar check (`validate.py`).
- **Time bound:** a stub run in flight past a one-minute bound raises one `run_overrun` escalation naming it. The run is not killed, is still polled, and its outcome is ingested and routed. The escalation closes on the first complete tick after.
- **Crash:** a process killed between ingestion and routing routes the outcome after restart, exactly once.
- **Hold:** a held step's outcome is still routed, and nothing new is issued under the hold.

### Technical Requirements

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` (strict) are clean.
- `reduce`, `evaluate`, `effect_for` and `overrun_runs` have table-driven tests covering every row of D1, D4 and D5, including split reviews and every `unknown` source.
- The shipped `default.yaml` passes `parse_table` in a test, and a wheel-build test finds it in the package.
- The CHANGELOG has an entry.

### Integration Requirements

- 125's crash and ingestion tests and 124's guard tests pass with the route stage in the tick.
- 127 and 128 can read decisions and extend the inputs without changing `engine.py` or the table grammar.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–3 need no network. Step 4 launches real Squadron runs on a scratch copy, which costs a design run and, if it advances, a tasks run.

1. **Tests and gates:**
   ```bash
   uv run pytest tests/runner/routing -v
   uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright
   ```
   Expected: all pass. Tests are named for their rules, for example `test_rerun_limit_falls_through_to_next_rule`, `test_unknown_matches_only_named_unknown` and `test_decision_recomputes_from_stored_version`.

2. **Break a copy of the shipped table:**
   ```bash
   cp src/amoeba/runner/routing/tables/default.yaml /tmp/t.yaml
   # delete the last rule from /tmp/t.yaml, then:
   AMOEBA_STORE_DIR=$(mktemp -d) uv run amoeba start --routing-table /tmp/t.yaml; echo "exit $?"
   ```
   Expected: `amoeba start` exits 7, naming the missing catch-all.

3. **Time bound, with the stub `sq`:** `uv run pytest tests/runner/routing/test_overrun.py -v`. This shows the escalation opening while a stub run outlives a one-minute bound, the run still being ingested, and the escalation closing.

4. **A real step routed, in a scratch copy.** Follow 125's walkthrough step 3 to create the scratch project and drive one slice `until: tasks`. When the P4 run finishes:
   ```bash
   amoeba inspect routing-decisions --project scratch
   amoeba inspect journal --project scratch
   amoeba inspect blocked --project scratch
   ```
   Expected:
   - One decision for the P4 entry. Its `recomputes` column is `yes`, and its version is `sha256:` followed by the output of `shasum -a 256 src/amoeba/runner/routing/tables/default.yaml`.
   - **If the review was a stated PASS:** the rule is `advance-on-stated-pass`, `slice_design` is done, and a `cf_write` for the `tasks` step appears on a later tick, followed by a P5 `sq_run`.
   - **If it paused, or anything else:** the rule is an escalate rule, and `inspect blocked` shows the step blocked, with no second block for a pause.

   `amoeba inspect journal` shows no `awaits_routing` entries once routing has run. Stop with `amoeba stop`.

## Risk Assessment

### Technical Risks

- **The grammar is hard to change once decisions exist.** Old decisions must still recompute against their stored tables.

### Mitigation Strategies

- The `format` field (D2) lets a later loader parse each stored version by its own format. A test stores a decision, then recomputes it from the stored content alone, so a grammar change that breaks old tables fails the suite.
- The grammar is deliberately small: equality on closed values, one numeric limit through eligibility, and two route parameters.

## Implementation Notes

### Development Approach

Relative effort: 3/5. Suggested order. Each step leaves the suite green.

1. `inputs.py` and `evidence.py`: the vocabularies, `gather` and `reduce`, with table tests over hand-built entries and verdicts.
2. `table.py`: the model, `parse_table`, validation and the version, and `default.yaml`.
3. `engine.py` and `effect_for`: matching, eligibility and effects. Then `recompute`.
4. `stage.py`: the route stage in `tick.py`, the view moved before it (D8), table and version loading in `runner_tenant()`, and the setting and flag.
5. `overrun.py` and `FaultKind.run_overrun` (D7).
6. `inspect routing-decisions`, the contract documents and the CHANGELOG.

**Testing approach.** The pure functions get most of the cases. Tick-level tests use `Store.open_temporary()` and the stub `sq` from 125, with a test table passed through `--routing-table` so that rules and bounds can be small. The crash test extends 125's kill between ingestion and routing, now with the real route stage.

### Special Considerations

- **Plan and arch edits,** made with this design:
  - Plan entry 9 (128): it registers the `gate_state` and `check_standing` inputs (D3).
  - Plan Future Work: per-project routing tables (D2).
  - Arch, "What the routing table matches on": node kind and attempt count are not inputs (the attempt limit is a route parameter), gate state and check standing arrive with 128, and recurrence is `new` / `recurring` / `clear` (D1, D3). The table format is YAML, one table for every project (D2).
  - Arch, "One edit point for routing" and the time-bound sentence: an overrun raises a project-scoped escalation, the one fixed response outside the table, and writes no decision record, because the entry's one decision belongs to its outcome. The payload carries the bound and the table version as evidence (D7).
- **Spend.** Rerun is the only route that launches a paid run without a PM, and it is bounded by `max_attempts`. The shipped table reruns at most once per step.
- **Security.** Decision inputs and escalation payloads hold vocabulary values, ids and paths only. Table content is stored verbatim, so the process contract repeats the rule that no secrets go in it.
