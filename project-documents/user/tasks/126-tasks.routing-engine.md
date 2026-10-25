---
docType: tasks
slice: routing-engine
project: amoeba
lld: user/slices/126-slice.routing-engine.md
dependencies:
- 121
- 122
- 123
- 124
- 125
projectState: Slices 120–125 are merged. The tick (`runner/tick.py`) has a `# [route
  - slice 126]` slot after the pointer observe, and `_decide` builds `ProjectView`
  itself. Ingestion (`runner/ingest/record.py`) resolves finished runs with `awaits_routing`
  and the result keys `RESULT_OUTCOME`, `RESULT_OUTCOME_DOCUMENT`, `RESULT_VERDICT_IDS`,
  `RESULT_REVIEW_FAULT`; `finish.RESULT_LAUNCH_FAILURE` marks a launch failure. The
  store has `record_routing_decision`, `Route` (advance, rerun, escalate), `StatusEffect`,
  `BlockEffect`, `routing_table_version`, `routing_decisions(node_id)`, `attempt_count`
  and `unrouted_outcomes`. Tests route outcomes through the stand-in `tests/runner/ingest/routing_support.py`.
  `amoeba.runner.routing` does not exist.
dateCreated: 20261024
dateUpdated: 20261025
status: complete
turns: 49
promptTokens: 3655862
cachedTokens: 3516714
cacheWriteTokens: 139070
completionTokens: 39762
durationSeconds: 416.6
costUsd: 2.611733
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 2.611733600000001
    completionTokens: 39762
revision_number: 2
---

## Context Summary

- Working on the **routing-engine** slice (126), the seventh slice of initiative 120 (Runner and Routing Engine). Every finished run gets a route (`advance`, `rerun` or `escalate`) chosen by a static YAML table, recorded with its inputs, rule id and table version so it can be recomputed. In-flight runs past their pipeline's time bound raise a project-scoped `run_overrun` escalation.
- **Current state:** ingested outcomes sit in `unrouted_outcomes` until a test's stand-in routes them. Nothing advances a step on its own.
- **Dependencies:** 121 (decision store), 122 (tick, faults, `StartupFailedError`), 123 (`LifecycleStep`, `STEP_MAP`), 124 (routing reads no desired state), 125 (ingestion, kind parsers). All merged. No store change and no migration.
- **What this slice delivers:** `amoeba.runner.routing` (inputs, evidence, table, engine, recompute, stage, overrun), the shipped `default.yaml`, the `routing_table_path` setting and `--routing-table` flag, start-up loading, `FaultKind.RUN_OVERRUN`, `amoeba inspect routing-decisions`, contract text and CHANGELOG.
- **Next planned slices:** 127 (resolutions and resumption) and 128 (gates, git and human steps), which add the `gate_state` and `check_standing` inputs.

**Branch:** all implementation happens on `126-slice.routing-engine`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/126-slice.routing-engine.md` at the named decision (D1–D9), "Architecture", or "Implementation Details". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/` or `docs/`. Keep every new or changed source file near 300 lines and each function near 50.

**Order and dependencies:** work tasks in file order. Each task's **Dependencies** lists only its real prerequisites. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off; only its dependents wait.

**Commit cadence:** each task ends in one commit. An implementation task with no commit step is committed together with the test task right after it, so a commit never holds untested behavior. Run `uv run ruff format .` before each commit. Commit type is `feat:` for new behavior, `refactor:` for behavior-preserving change, `test:` for test-only work, `docs:` for contract text.

**Task-level additions to the LLD** (code facts the LLD does not state, checked against the code on 20261024; each resolves a placement, not a product decision):
- **`store.verdict(id)` returns `None`, it does not raise.** `observations` and `finding_changes` raise `VerdictNotFoundError`. `gather` treats a `None` verdict the same as the raise: the review inputs are `unknown` (LLD D5, "Failure handling").
- **Entry result keys are reused, never retyped.** `RESULT_OUTCOME`, `RESULT_OUTCOME_DOCUMENT`, `RESULT_VERDICT_IDS`, `RESULT_REVIEW_FAULT` and `OUTCOME_VANISHED` are in `runner/ingest/record.py`; `RESULT_LAUNCH_FAILURE` is in `runner/finish.py`; `PARAM_PIPELINE` is in `runner/launch.py`. The `outcome` values other than `vanished` are `RunOutcome` values (`process/sq_outcome.py`); any `RunOutcome` outside D1's set (`timed_out`, `not_found`, …) reduces to `unknown`.
- **`checkpoint.is_loop` is a `JsonValue`.** Only a JSON boolean reduces to `true`/`false`; any other type is `unknown`.
- **Two version labels.** `RunnerTenant` already carries `version_label`, the `sq --version` label. The Amoeba package version is a separate value named `amoeba_version` everywhere, so the two are never confused.
- **The per-project decision listing.** The store reads decisions per node (`routing_decisions(node_id)`). The listing iterates the project's nodes (`nodes_for_project`) and sorts by `decided_at`. No store change.
- **`issued_at`.** `JournalEntry.issued_at` is `datetime | None`. `overrun_runs` raises `ValueError` for an in-flight entry without a timezone-aware `issued_at`, as `runner/observe.py` treats it, so it faults the project through 122's catch.
- **The stand-in is retired.** Once the route stage is in the tick, `tests/runner/ingest/routing_support.py`'s `route_outcome` would record a second decision for an entry the tick already routed. Task 6.3 moves its callers to the real stage, or to a direct store call where a test needs an outcome left unrouted.
- **Two modules beyond the LLD's component sketch,** to keep each file near 300 lines: `reduce.py` holds `OutcomeEvidence`, `ReviewPart` and `reduce`, leaving `inputs.py` the vocabulary only; `validate.py` holds the load-time validation that `table.py`'s `parse_table` calls.
- **Where `Route` members may be compared.** The LLD says only in `engine.py`. Validation must also branch on `Route` (each route's required parameters and its `outcome: completed` rule), and it cannot live in `engine.py`, which imports `table.py`, which calls `validate.py`. So Task 4.4's source test allows exactly `engine.py` and `validate.py`. `validate.py` checks which grammar a route accepts; it never chooses a route, which is what the LLD's rule protects.
- **Overrun check placement and closure.** The LLD draws the overrun check after the route stage. Task 7.2 places it beside `watch_pointers`, before `raise_expected_faults`, so the existing raise path records it. The order changes no result: routing touches only finished entries and the check reads only in-flight ones. Closure needs no registration: `ProjectTick._close_recovered` closes every open project escalation whose fault kind is absent from the tick's `TickFaults`, and no set of project-scoped kinds exists in `runner/faults.py`.
- **Inspection registry.** A listing is a `Listing` in `inspection/__init__.py`'s `LISTINGS`; `cli/main.py` adds one `inspect` subcommand per entry. `cli/inspect.py` needs no change unless a column type needs new rendering.
- **Shared names, defined once.** `RoutingInput` and each value set, `UNKNOWN`, `NONE`, `ROUTED_SEVERITIES`, the split-review combine order, the eligibility predicates, the escalate payload keys and `REASON_ROUTED`, `VERSION_PREFIX = "sha256:"`, `FaultKind.RUN_OVERRUN`, `DEFAULT_ROUTING_TABLE_PATH` and the `run_overrun` payload keys. Tests import them. They never retype a value.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`. Table problems are a `TableError` listing every problem, never the first one only.
- **Test doubles.** Pure functions get table-driven tests. Store-backed tests use `Store.open_temporary()`. Tick-level tests use `tests/runner/tick_support.py` and `plan_tick_support.py` with the stub `cf` and stub `sq` on `PATH` under a temporary `HOME`, and a small test table. Nothing sleeps or runs a real `cf` or `sq`.
- **Test location and naming.** New package `tests/runner/routing/` (with `__init__.py`). Tests are named for the rule they prove (LLD, Verification Walkthrough step 1).

**Section map.** 1 baseline; 2 inputs and evidence; 3 the table; 4 engine, effects and recompute; 5 setting and start-up loading; 6 the route stage in the tick; 7 time bounds; 8 inspection; 9 contract text, CHANGELOG and final validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and confirm the design's edits
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Run `git status --short`. Uncommitted edits to planning documents (the arch, the initiative plan, the slice or these tasks) are committed to the target first as `docs:`, each file by name. If any other file is dirty, write `BLOCKED:` naming it and stop
- [x] Confirm the plan and arch edits the LLD lists under "Special Considerations" are present: plan entry 9 registers `gate_state` and `check_standing` (in `user/architecture/120-slices.runner-routing-engine.md`); plan Future Work lists per-project routing tables; the arch (`120-arch.runner-routing-engine.md`) names the overrun as the one fixed response and lists the inputs per D1. Make any missing edit per the LLD and commit it to the target as `docs:`
- [x] Create `126-slice.routing-engine` from the target and switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright`. Record the pass count under this task. If any fails, write `BLOCKED:` with the failure and stop
- [x] Create `src/amoeba/runner/routing/__init__.py` (docstring only) and `tests/runner/routing/__init__.py`
- [x] **Success:** on the slice branch, the suite is green, and the two packages exist. Commit `chore: add the routing package skeleton`

Baseline: 3349 tests passed; ruff, format and pyright clean.

Plan/arch edits were already present, so nothing was committed to main for them.

---

## Section 2: Inputs and Evidence

### Task 2.1: Define the input vocabulary
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] Create `runner/routing/inputs.py` with, per the LLD D1 table and "API Contracts":
  - [x] `RoutingInput(StrEnum)` with the ten members
  - [x] `UNKNOWN = "unknown"` and `NONE = "none"`
  - [x] `VALUE_SETS`, a mapping from each input to its closed set of values, each including `UNKNOWN`. Sets that mirror an enum are built from it (`VerdictStanding`, `LifecycleStep`, `CheckpointKind`, `FailureKind`), never retyped
  - [x] `ROUTED_SEVERITIES` (`concern`, `fail`, from `FindingSeverity`) and the split-review combine order (`fail` over `concerns` over `pass`)
  - [x] the frozen dataclass `RoutingInputs(values, attempt)`, where `attempt` is `int | None` (null when `step` is unknown, D1 "Attempts"). Construction raises `ValueError` if `values` lacks an input or holds a value outside its set
- [x] `tests/runner/routing/test_inputs.py`: every set contains `UNKNOWN`; `RoutingInputs` refuses a missing input and an out-of-set value
- [x] **Success:** tests pass; `inputs.py` imports nothing from `amoeba.store` writes or `runner/tick.py`; pyright strict is clean. Commit `feat: add the routing input vocabulary`

### Task 2.2: Implement `reduce` for the outcome inputs
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 3

- [x] Create `runner/routing/reduce.py` (Task-level additions). In it, define the frozen `OutcomeEvidence` (with one `ReviewPart` per recorded verdict) holding what D1's reductions read, as plain data so tests build it by hand
- [x] Implement `reduce(evidence) -> RoutingInputs` for `outcome`, `checkpoint_kind`, `at_loop`, `failure_kind`, `step` and `node_state`, per D1's table and "Reduction rules":
  - [x] `outcome` from `RESULT_OUTCOME`, or `launch_failed` when `RESULT_LAUNCH_FAILURE` is present
  - [x] the checkpoint and failure kinds through 125's `parse_checkpoint_kind` / `parse_failure_kind`: absent document section is `none`, a null field or `UnknownKind` is `unknown`
  - [x] `at_loop` per the JSON-boolean rule (Task-level additions)
  - [x] `step` from `cf.phase` through `LifecycleStep`; anything else is `unknown`
  - [x] `node_state`: the three `blocked_on_*` statuses are `blocked`; `in_progress` is `unknown`
  - [x] `attempt` is `attempt_count + 1`, or `None` when `step` is `unknown`
- [x] **Success:** `reduce` is pure (no store, no clock); each rule lives in one small helper

### Task 2.3: Test the outcome reductions
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 2

- [x] `tests/runner/routing/test_reduce_outcome.py`, table-driven over hand-built `OutcomeEvidence`: every `outcome` value including `vanished` and `launch_failed`, and a `RunOutcome` outside the set; each checkpoint and failure kind, a null kind, an unrecognized kind, and no section; `is_loop` true, false, a string, absent; every `NodeStatus`; a known and an unknown `cf.phase`, with the `attempt` result for each
- [x] **Success:** every row of D1 for these six inputs has a case, and every `unknown` source among them. Commit `feat: reduce outcome evidence to routing inputs`

### Task 2.4: Implement `reduce` for the review inputs
**Owner**: Junior AI | **Dependencies**: 2.2 | **Effort**: 3

- [x] Extend `reduce` in `reduce.py` for `verdict`, `standing`, `severity` and `recurrence` per D1 "Reduction rules":
  - [x] all four `none` when there are no parts; all four `unknown` when `RESULT_REVIEW_FAULT` is set, the review could not be read, or any part's verdict is `UNKNOWN`
  - [x] split review: worst verdict, common standing or `unknown`, highest severity
  - [x] `recurrence` over `ROUTED_SEVERITIES` findings only: `recurring`, `new`, `clear`; `unknown` when any part is not `comparable`
  - [x] verdict and severity values lower-cased into D1's value sets (store `PASS` → `pass`)
- [x] **Success:** `reduce` stays pure; no helper exceeds ~50 lines

### Task 2.5: Test the review reductions
**Owner**: Junior AI | **Dependencies**: 2.4 | **Effort**: 2

- [x] `tests/runner/routing/test_reduce_review.py`, table-driven: no review; review fault; unreadable review; a single PASS, CONCERNS and FAIL; each standing; split reviews with mixed verdicts, matching and differing standings, and mixed severities; recurrence with a recurring concern, only new concerns, only notes (→ `clear`), only gone findings (→ `clear`), a recurring note (→ not `recurring`), and a non-comparable part
- [x] **Success:** includes `test_split_review_takes_worst_verdict` and `test_recurring_note_does_not_recur`. Commit `feat: reduce review evidence to routing inputs`

### Task 2.6: Implement `gather`
**Owner**: Junior AI | **Dependencies**: 2.4 | **Effort**: 2

- [x] Create `runner/routing/evidence.py` with `gather(store, entry) -> OutcomeEvidence`. Store reads only: `get_node`, `attempt_count(node, step)` when the step is known, and for each id in `RESULT_VERDICT_IDS`: `verdict`, `observations`, `finding_changes`
- [x] A `None` verdict or a `VerdictNotFoundError` from either read marks the review unreadable (Task-level additions). Catch only `VerdictNotFoundError`, with a comment citing D5. Any other exception propagates
- [x] **Success:** `gather` writes nothing; pyright strict is clean

### Task 2.7: Test `gather`
**Owner**: Junior AI | **Dependencies**: 2.6 | **Effort**: 2

- [x] `tests/runner/routing/test_evidence.py` on `Store.open_temporary()`: an entry with recorded verdicts (reuse `tests/evidence_harness.py` or `tests/review_fixtures.py` helpers) gathers the parts; an entry naming a missing verdict id is unreadable, not an exception; a launch-failure entry gathers no parts; `attempt_count` is read for a known step only
- [x] `gather` then `reduce` on a recorded stated PASS gives `verdict: pass, standing: stated`
- [x] **Success:** tests pass. Commit `feat: gather routing evidence from the store`

---

## Section 3: The Table

### Task 3.1: Implement the table model, parser and version
**Owner**: Junior AI | **Dependencies**: 2.1 | **Effort**: 3

- [x] Create `runner/routing/table.py` per the LLD "API Contracts" and D2:
  - [x] `TableFile` and its rule model in pydantic v2 with `extra="forbid"`, reading `format`, `time_bounds_minutes` and `rules` (`id`, `when`, `route`, `max_attempts`, `judge_eligible`)
  - [x] the frozen `Rule` and `RoutingTable(version, content, rules, time_bounds_minutes)`
  - [x] `SUPPORTED_FORMATS = frozenset({1})` and `VERSION_PREFIX = "sha256:"`
  - [x] condition values accept one value or a list, are trimmed and lower-cased, and become `frozenset[str]`
  - [x] `parse_table(text)`: `yaml.safe_load`, model validation, conversion; the version is `sha256:` plus the hex digest of the text's UTF-8 bytes; `content` is the text verbatim
  - [x] `load_table(path)`: reads bytes; a missing file, an unreadable file, or bytes that are not UTF-8 raise `TableError` naming the path and the error
  - [x] `TableError(problems: tuple[str, ...])`, whose message lists every problem
- [x] **Success:** malformed YAML raises `TableError` naming the YAML error, never `yaml.YAMLError`

### Task 3.2: Implement load-time validation
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 3

- [x] Create `runner/routing/validate.py` (Task-level additions), called by `parse_table`. It collects every problem from D4 "Load-time validation" before raising, each naming the rule id where there is one:
  - [x] unsupported `format`; empty or duplicate rule id
  - [x] an input or value not in `VALUE_SETS` (so `gate_state` is refused, D3)
  - [x] a route that is not a `Route` member
  - [x] parameters: `rerun` needs `max_attempts ≥ 1`; `escalate` needs a boolean `judge_eligible`; `advance` takes neither; a parameter on the wrong route is a problem
  - [x] `advance` and `rerun` must name `outcome` with exactly `{completed}`
  - [x] the last rule has an empty `when` and route `escalate`; no earlier rule has an empty `when`
  - [x] `time_bounds_minutes` has one positive integer per `STEP_MAP` pipeline and no other key
- [x] Pydantic `ValidationError` problems are converted into the same list, so a type error and a rule problem are reported together where possible
- [x] **Success:** a table with three problems raises one `TableError` listing all three

### Task 3.3: Test the parser and validation
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 2

- [x] First create `tests/runner/routing/table_support.py` with `small_table(...)`, which builds a `RoutingTable` from YAML rule text through `parse_table`, adding the catch-all escalate rule and one positive bound per `STEP_MAP` pipeline unless the caller overrides them. Every later test table (4.2, 4.3, 5.x, 6.x, 7.x) uses it; none hand-rolls one. Tests of the refusals themselves call `parse_table` directly
- [x] `tests/runner/routing/test_table.py`, one case per D4 problem and per LLD "Load refusal" item: no catch-all, a non-escalate catch-all, an early empty `when`, an unknown input, `gate_state`, an unknown value, an unknown route, a missing and an extra parameter, a non-`completed` advance and rerun, a duplicate id, a missing and an extra time bound, an unsupported `format`, malformed YAML, a missing file, and an unreadable file: a directory path (the `OSError` branch) and a file of non-UTF-8 bytes (the `UnicodeDecodeError` branch)
- [x] Also: flow and block YAML styles parse to equal rules; `PASS` and ` pass ` equal `pass`; the version equals `sha256:` plus `hashlib.sha256(bytes).hexdigest()`; one byte changed gives a new version; several problems are all reported
- [x] **Success:** tests pass. Commit `feat: parse and validate the routing table`

### Task 3.4: Ship the first table
**Owner**: Junior AI | **Dependencies**: 3.2 | **Effort**: 2

- [x] Create `runner/routing/tables/default.yaml` with the four rules of D9 and the bounds of D7 (P4 240, P5 240, P6 720), `format: 1`. A comment at the top says no secrets go in the table, since its content is stored verbatim
- [x] In `pyproject.toml`, add `src/amoeba/runner/routing/tables/*.yaml` to the `artifacts` list beside the schema SQL
- [x] `tests/runner/routing/test_default_table.py`: the shipped table, read through `importlib.resources`, passes `parse_table`; its rule ids are in D9's order
- [x] `tests/runner/routing/test_wheel_contents.py`: `uv build --wheel --offline` into a temporary directory, and the wheel's file list contains `amoeba/runner/routing/tables/default.yaml`. The build backend (`hatchling`) is not a dev dependency, so when uv reports it is not cached, the test calls `pytest.skip` with uv's stderr as the reason; any other build failure fails the test
- [x] **Success:** both tests pass. Commit `feat: ship the default routing table`

The wheel test ran and passed offline (it was not skipped).

---

## Section 4: Engine, Effects and Recompute

### Task 4.1: Implement `evaluate`, the eligibility predicates and `effect_for`
**Owner**: Junior AI | **Dependencies**: 2.1, 3.1 | **Effort**: 3

- [x] Create `runner/routing/engine.py` with the frozen `Match(rule, route, parameters)` and `evaluate(table, inputs)` per D4 "Matching" and "Eligibility predicates": rules in file order; a rule matches when every named input's value is in its set; a matching but ineligible rule is passed over
- [x] One predicate per route, in one mapping keyed by `Route`. `rerun` is ineligible when `attempt` is `None` or `attempt >= max_attempts`
- [x] A table with no eligible match raises `ValueError` (load validation makes it impossible, since the catch-all escalate is always eligible)
- [x] `parameters` is the rule's parameter mapping (`max_attempts` or `judge_eligible`), the value recorded as `route_parameters`
- [x] In `engine.py`, `effect_for(match, inputs, *, table_version, run_id) -> StatusEffect | BlockEffect | None` per the D5 table: advance → `StatusEffect(NodeStatus.DONE)`; rerun → `None`; escalate on `runnable` → `BlockEffect` with context `routed by <rule id>` and the payload of D5 (keys defined once as constants, `REASON_ROUTED = "routed"`); escalate on any other `node_state` → `None`. It is the only place a route becomes an effect
- [x] **Success:** both functions pure; pyright strict clean

### Task 4.2: Test `evaluate` and `effect_for`
**Owner**: Junior AI | **Dependencies**: 3.3, 4.1 | **Effort**: 2

- [x] `tests/runner/routing/test_engine.py`, table-driven over small tables built with `small_table` (Task 3.3): first match wins; an unnamed input is unconstrained; `test_unknown_matches_only_named_unknown`; advance passed over on a blocked node; `test_rerun_limit_falls_through_to_next_rule` (attempt 1 reruns, attempt 2 falls through with `max_attempts: 2`); a rerun rule not naming `step` passed over when `step` is `unknown`; the catch-all always applies
- [x] `tests/runner/routing/test_effects.py`: one case per D5 row, including escalate on `blocked`, `done` and `unknown`; the block payload carries `judge_eligible` from the rule
- [x] **Success:** tests pass. Commit `feat: evaluate routing rules and map routes to effects`

### Task 4.3: Implement and test `recompute`
**Owner**: Junior AI | **Dependencies**: 3.3, 4.1 | **Effort**: 2

- [x] Create `runner/routing/recompute.py`: `recompute(decision, stored) -> Recomputation` per D6. Rebuild `RoutingInputs` from `decision.inputs` (including `attempt`), parse `stored.content` with `parse_table`, evaluate, and report the rule id, route and whether both equal the record. A `TableError` or inputs outside today's vocabulary yield a `Recomputation` carrying the error reason, never a mismatch
- [x] `tests/runner/routing/test_recompute.py`: `test_decision_recomputes_from_stored_version` (a matching decision recomputes); a decision with an altered rule id does not; unparseable stored content and an unsupported `format` give an error reason
- [x] **Success:** tests pass; `recompute` reads nothing but its two arguments. Commit `feat: recompute routing decisions from the stored table`

### Task 4.4: Prove no route is chosen outside the engine
**Owner**: Junior AI | **Dependencies**: 3.2, 4.1 | **Effort**: 1

- [x] `tests/runner/routing/test_route_comparisons.py`: walk every module under `src/amoeba/runner/` with `ast` (see `tests/ast_strings.py` and `tests/runner/test_cf_commands_defined_once.py` for the pattern) and assert that `Route.<member>` appears in a comparison, `match` case or mapping key only in `runner/routing/engine.py` and `runner/routing/validate.py` (Task-level additions)
- [x] **Success:** passes now, and fails when a `Route.ADVANCE` comparison is added to another module (check once by hand, then revert). Commit `test: assert routes are compared only in the engine`

---

## Section 5: Setting and Start-up Loading

### Task 5.1: Add the setting and flag
**Owner**: Junior AI | **Dependencies**: 3.4 | **Effort**: 1

- [x] In `process/settings.py`, add `DEFAULT_ROUTING_TABLE_PATH`, resolved once from the package with `importlib.resources`, and the `routing_table_path: Path` field defaulting to it, with a docstring entry
- [x] In `cli/settings_flags.py`, add `--routing-table PATH` to `add_start_flags` and carry it into `start_settings`, following the existing flags
- [x] Extend the existing settings and flag tests (find them with `grep -rln start_settings tests`): the default is the shipped table; the flag overrides it
- [x] **Success:** tests pass. Commit `feat: add the routing_table_path setting and flag`

### Task 5.2: Load and validate the table at start
**Owner**: Junior AI | **Dependencies**: 3.3, 5.1 | **Effort**: 2

- [x] In `runner/factory.py`'s `runner_tenant()`, after `validate_settings`: `load_table(settings.routing_table_path)`, and read `amoeba_version` with `importlib.metadata.version("amoeba")`. A `TableError` or `PackageNotFoundError` raises `StartupFailedError` with every problem (D4, D5). Log the loaded table's version at INFO
- [x] Tests in `tests/runner/test_factory.py`: a valid table starts; a broken table raises `StartupFailedError` listing its problems; a missing file names the path
- [x] CLI test (follow `tests/test_cli_lifecycle.py`): `amoeba start --routing-table <broken>` exits `STARTUP_FAILED` (7) and names the missing catch-all
- [x] **Success:** the full suite passes. Commit `feat: load the routing table at start`

Landed in one commit with Task 5.3: `feat: load the routing table at start and carry it through the tick`.

### Task 5.3: Thread the table and Amoeba version through the tenant and tick
**Owner**: Junior AI | **Dependencies**: 5.2 | **Effort**: 2

- [x] Pass the loaded table and `amoeba_version` into `RunnerTenant` (`runner/tenant.py`) as `routing_table` and `amoeba_version`, held for the process's life, and on into each `ProjectTick` it builds. Update the docstrings
- [x] Update `tests/runner/tick_support.py` (its `RunnerTenant(...)` call) and any other direct constructor callers to pass `small_table(...)` (Task 3.3)
- [x] **Success:** the full suite passes. Commit `refactor: carry the routing table through the tenant and tick`

Landed in one commit with Task 5.2: `feat: load the routing table at start and carry it through the tick`.

---

## Section 6: The Route Stage in the Tick

### Task 6.1: Implement and test the route stage
**Owner**: Junior AI | **Dependencies**: 2.6, 4.1, 5.3 | **Effort**: 3

- [x] Create `runner/routing/stage.py` with `route_outcomes(store, project_id, routing, amoeba_version, context) -> bool` (whether it wrote), where `routing` is the loaded `RoutingTable`. For each entry in `unrouted_outcomes(project_id)`, oldest first:
  - [x] call `context.set(entry.node_id)` on the `NodeContext` (`runner/faults.py`), the same pattern as `runner/observe.py`, so 122's catch blocks the right node
  - [x] `gather` → `reduce` → `evaluate` → `effect_for`
  - [x] build `RoutingDecisionInput` per D5 "The decision row": `inputs` is every input's value plus `attempt`; `route_parameters` from the match; `journal_entry_id` is the entry; `table_version` and `amoeba_version`
  - [x] call `record_routing_decision(..., table=RoutingTableVersion(version, content), effect=..., attempt_step=step or None)`
- [x] No `except`: store failures and other exceptions propagate to the tick and tenant (D5)
- [x] `tests/runner/routing/test_stage.py` on `Store.open_temporary()` with ingested-shape entries (reuse 125's ingest test helpers): a stated PASS marks the step done and counts attempt 1; a stated CONCERNS with new findings records `rerun`, leaves the node `runnable`, and a second such outcome escalates with a `HUMAN` block; a paused entry escalates with no second block and the node stays `blocked_on_sq_checkpoint`; a failed, an orphaned, a vanished and a launch-failed entry escalate with no second block; an entry with a missing verdict id escalates
- [x] After each, `unrouted_outcomes` is empty, and the table version is stored once across several decisions
- [x] **Success:** tests pass; the function is under ~50 lines, with any row-building in a helper. Commit `feat: route unrouted outcomes`

### Task 6.2: Build the view before the route slot
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

- [x] In `runner/tick.py`, split `_decide` so `ProjectView` is built by a separate method called before the `# [route - slice 126]` slot (D8), and `_decide` takes the built view. The slot stays empty, so behavior is unchanged
- [x] Keep `tick.py` near 300 lines. If it grows past ~330, move the view building into a helper module beside it (`runner/dispatch/build_view.py` already builds the dispatch part)
- [x] **Success:** the full suite passes unchanged. Commit `refactor: build the project view before the route slot`

The view building moved into `runner/project_view.py`, since `tick.py` was past the size trigger.

### Task 6.3: Wire the stage into the tick and retire the routing stand-in
**Owner**: Junior AI | **Dependencies**: 6.1, 6.2 | **Effort**: 3

- [x] Replace the `# [route - slice 126]` slot with the call to `route_outcomes`, setting `self.wrote`. Confirm it adds no `TickBudget` check (it starts no subprocess, LLD "Data Flow")
- [x] Find every caller of `route_outcome` and `review_harness.route` (`grep -rn "route_outcome\|\.route(" tests`). For each:
  - [x] where the tick now routes the entry, delete the stand-in call and assert the real decision instead
  - [x] where a test needs an outcome left unrouted (the crash harness's kill before routing), keep the kill point and let the restart's tick route it
- [x] Delete `tests/runner/ingest/routing_support.py` once it has no callers. Keep `tests/routing_helpers.py` if store tests still use it
- [x] Run 125's crash and ingestion tests and 124's guard tests
- [x] **Success:** the full suite passes. Commit `feat: route outcomes in the tick before decide`

### Task 6.4: Tick-level routing tests
**Owner**: Junior AI | **Dependencies**: 6.3 | **Effort**: 3

- [x] `tests/runner/routing/test_tick_routing.py`, with the stub `sq` and a small table:
  - [x] `test_advance_dispatches_successor_next_tick`: a completed P4 run with a stated PASS marks `slice_design` done on tick m, and `tasks` gets its pointer write on tick m+1, not tick m
  - [x] `test_rerun_relaunches_same_pipeline`: after a `rerun`, the next tick writes the pointer and launches the same pipeline with no instructions
  - [x] `test_held_step_outcome_is_routed`: a held step's outcome is routed, and nothing new is issued under the hold
- [x] Extend `tests/runner/test_crash_recovery.py`'s `test_kill_between_ingest_and_route...`: after restart, the real stage routes the outcome exactly once (one decision row for the entry)
- [x] Decision recompute across versions: route one outcome under table A, restart with table B (an edited copy), route a second; both table versions are stored and both decisions recompute against their own version
- [x] **Success:** tests pass. Commit `test: prove routing across ticks, holds, restarts and table edits`

The crash-recovery extension (kill between ingest and route, one decision after restart) was done under Task 6.3, as part of retiring the stand-in.

---

## Section 7: Time Bounds

### Task 7.1: Add `run_overrun` and `overrun_runs`
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 2

- [x] In `runner/faults.py`, add `FaultKind.RUN_OVERRUN = "run_overrun"` and a docstring line saying it is project-scoped
- [x] Create `runner/routing/overrun.py` with `overrun_runs(in_flight, table, now) -> tuple[Overrun, ...]` per D7: age is `now - issued_at`; the bound is `table.time_bounds_minutes[pipeline]` read from `PARAM_PIPELINE`; a pipeline with no bound or a missing/naive `issued_at` raises `ValueError`. `Overrun` carries `node_id`, `run_id`, `pipeline`, `issued_at`, `bound_minutes`, the payload keys defined once
- [x] `tests/runner/routing/test_overrun_runs.py`, table-driven: under, at and over the bound; several runs with one over; an unbounded pipeline; a missing `issued_at`
- [x] **Success:** tests pass. Commit `feat: find in-flight runs past their time bound`

### Task 7.2: Raise the overrun escalation in the tick
**Owner**: Junior AI | **Dependencies**: 6.3, 7.1 | **Effort**: 2

- [x] In `runner/tick.py`, compute `overrun_runs` over the in-flight entries the tick already has (`o.run.entry for o in observed.runs if o.finished is None`). If non-empty, add a `Fault(FaultKind.RUN_OVERRUN, …, extra={runs: [...], table_version})` to the tick's `TickFaults`, exactly as `runner/dispatch/pointer_watch.py` adds `POINTER_MOVED`
- [x] Call it beside `watch_pointers`, before `raise_expected_faults` (placement per Task-level additions), with a one-line comment giving the reason
- [x] Closure needs no change: `_close_recovered` already closes the escalation on the first complete tick whose `TickFaults` lacks `RUN_OVERRUN` (Task-level additions)
- [x] Re-check `tick.py`'s length after 6.3 and this task; past ~330 lines, apply the 6.2 split
- [x] **Success:** pyright clean; existing tests pass; `tick.py` within the 6.2 size limit

Wired and tested together with Task 7.3 in one commit, `feat: escalate runs past their time bound`. Test planners and fixtures that launched the fake pipeline `noop` (or `p`) now launch `P4`, since an in-flight run on an unbounded pipeline is a ValueError by design (D7).

### Task 7.3: Tick-level overrun test
**Owner**: Junior AI | **Dependencies**: 7.2 | **Effort**: 2

- [x] `tests/runner/routing/test_overrun.py` with the stub `sq` holding a run open, a table with one-minute bounds, and an injected clock: one `run_overrun` escalation names the run; the run is not killed and is still polled; when the stub run completes, it is ingested and routed, and the escalation closes on that complete tick; a second tick while overrun adds no second escalation
- [x] **Success:** tests pass (this is Walkthrough step 3). Commit `feat: escalate runs past their time bound`

Committed together with Task 7.2 in `feat: escalate runs past their time bound`.

---

## Section 8: Inspection

### Task 8.1: Add the `routing-decisions` listing
**Owner**: Junior AI | **Dependencies**: 4.3 | **Effort**: 2

- [x] Create `inspection/routing.py` with the columns and row function per D6: `decided_at`, node, step, rule id, route, attempt, short version, `recomputes`. Rows come from `routing_decisions` over the project's nodes (or the one `--node ID`), sorted oldest first. `recomputes` is `yes`, `no`, or `error: <reason>` (a missing version row, or a `Recomputation` error)
- [x] Register it in `LISTINGS` (`inspection/__init__.py`) as project-scoped with a `node_id` option, following the existing listings. Add the short-version length as a constant in `routing.py`
- [x] Check `inspection` may import `amoeba.runner.routing` under `tests/test_import_boundaries.py`. If a rule forbids it, write `BLOCKED:` naming the rule and stop
- [x] **Success:** `amoeba inspect routing-decisions --help` lists `--project`, `--node` and `--json`

Resolved by the PM: Rule 10 exempts `amoeba.runner.routing.inputs` and `.recompute` for inspection (commit e1bdcc3). The node option is `--node ID` (the existing inspect convention), not `--node-id`.

### Task 8.2: Test the listing
**Owner**: Junior AI | **Dependencies**: 8.1 | **Effort**: 2

- [x] `tests/inspection/test_routing_decisions.py` (follow `tests/inspection_harness.py`): rows oldest first across two nodes; `--node` narrows; a recomputing decision shows `yes`; a decision whose stored content was written with an unsupported `format` shows `error: …`, not `no`; `--json` emits full rows; the store opens read-only (the writer-guard test still passes)
- [x] **Success:** tests pass. Commit `feat: add inspect routing-decisions`

---

## Section 9: Contract Text, CHANGELOG and Final Validation

### Task 9.1: Update the contract documents and CHANGELOG
**Owner**: Junior AI | **Dependencies**: 7.3, 8.2 | **Effort**: 2

- [x] `docs/process-contract.md`: the route stage and the tick order with the view before it (D8); the table file format, inputs and values, matching, eligibility and validation rules (D1–D4); the `routing_table_path` setting and `--routing-table` flag; the `run_overrun` escalation, its payload (D7) and its actual place in the tick order (Task-level additions); the rule that no secrets go in the table
- [x] `user/slices/126-slice.routing-engine.md`: amend the two places the tasks depart from it, so the design matches what was built. (1) The `Route`-comparison rule (D-Patterns and Success Criteria): members are compared in `engine.py` and `validate.py`, and `validate.py` only checks grammar. (2) The overrun check (Data Flow diagram and D7): it runs beside `watch_pointers`, before `raise_expected_faults`, not after the route stage
- [x] `docs/substrate-guide.md`: update the 120 row for routing
- [x] `CHANGELOG.md`: add 1–2 line Slice 126 entries under `[Unreleased]` / `### Added`: routing by table with recorded, recomputable decisions; the overrun escalation; `--routing-table`; `inspect routing-decisions`
- [x] **Success:** every name in the text matches the code. Commit `docs: document the routing engine contract`

### Task 9.2: Final validation
**Owner**: Junior AI | **Dependencies**: 9.1 | **Effort**: 2

- [x] Run `uv run pytest tests/runner/routing -v`, then `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run pyright`. All pass
- [x] Walkthrough step 2: copy the shipped table, delete the last rule, and `AMOEBA_STORE_DIR=$(mktemp -d) uv run amoeba start --routing-table /tmp/t.yaml`. It exits 7 naming the missing catch-all. Record the output under this task
- [x] Walkthrough step 4 (real Squadron runs on a scratch copy, pre-authorized): follow 125's walkthrough step 3 to drive one slice `until: tasks`, then check `inspect routing-decisions`, `inspect journal` and `inspect blocked` against the LLD's expected results. Record the decision row and outcome under this task. If the scratch setup cannot be built, write `BLOCKED:` with the reason
- [x] Record under this task whether `test_wheel_contents.py` ran or skipped. If it skipped, run it once with network access (without `--offline`) and record that it passed
- [x] **Success:** all gates green; work is committed on `126-slice.routing-engine`. Commit any remaining fixes as `fix:` or `test:`

Gates: `uv run pytest -q` 3610 passed; ruff check, ruff format --check and pyright clean.

Walkthrough step 2: with the last rule deleted, `amoeba start --routing-table` exits 7: "the routing table is refused: ... the last rule 'escalate-completed-concerns' must be a catch-all: an empty when and route escalate".

Walkthrough step 4 (real Squadron, scratch clone, slice 131 driven until slice_design): P4 run amoeba-20261025T140947Z-53c51eb78c36 ran 18 min and FAILED with Squadron reporting no failure kind and no steps completed. Routed in the same tick it was ingested: decision rule `escalate-everything-else`, route `escalate`, attempt 1, table sha256:518453b2…, `recomputes: yes`. `inspect journal` showed the sq_run `completed`, awaits_routing false; `inspect blocked` showed slice_design blocked on human ("run … failed: unknown", ingestion's block stood, routing's own block skipped by design). A passing run (advance-on-stated-pass) was not exercised live; it is covered by tests/runner/routing. Scratch CF project removed, amoeba stopped.

Wheel test: tests/runner/routing/test_wheel_contents.py ran (not skipped) and passed.
