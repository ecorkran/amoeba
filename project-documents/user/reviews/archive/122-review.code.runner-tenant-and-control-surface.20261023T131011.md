---
docType: review
layer: project
reviewType: code
slice: runner-tenant-and-control-surface
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: e07f13739a5c7cd88c04fe2dffcc57b2a1eb5793
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 44
diffTruncated: false
turns: 20
promptTokens: 2606069
cachedTokens: 2286572
completionTokens: 144871
reasoningTokens: 137321
durationSeconds: 649.9
costUsd: 0.130743
costBasis: alias_pricing
runId: run-20261023-p56-63bf9ff6
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "The shared `RunObserver` drops other projects' state on every tick"
    location: "src/amoeba/runner/tenant.py:74"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`_in_flight_run_ids` subscripts a key a legacy entry does not have"
    location: "src/amoeba/runner/faults.py:196"
  - id: F003
    severity: concern
    category: testing
    summary: "The \"one broad except\" guard counts a string, not a syntax node"
    location: "tests/runner/test_tenant.py#test_the_runner_package_has_exactly_one_broad_except"
  - id: F004
    severity: concern
    category: documentation
    summary: "`cli_environment`'s docstring now contradicts the function"
    location: "tests/cli_harness.py:45"
  - id: F005
    severity: concern
    category: documentation
    summary: "The contract's Observer protocol block still shows a three-member union"
    location: "docs/process-contract.md:453"
  - id: F006
    severity: concern
    category: testing
    summary: "No load-tier coverage for the Runner's tick path"
    location: "tests/load"
  - id: F007
    severity: note
    category: documentation
    summary: "`--sq-timeout` help text was not updated with the setting's docstring"
    location: "src/amoeba/cli/settings_flags.py:113"
  - id: F008
    severity: note
    category: style
    summary: "Unused module logger in `tick.py`"
    location: "src/amoeba/runner/tick.py:51"
  - id: F009
    severity: note
    category: design
    summary: "`_record_ended` resolves `COMPLETED` for a failed run but `FAILED` for an orphaned one"
    location: "src/amoeba/runner/finish.py#_record_ended"
  - id: F010
    severity: note
    category: typing
    summary: "`validate_settings` reaches its fields by string name"
    location: "src/amoeba/runner/factory.py#validate_settings"
  - id: F011
    severity: pass
    category: design
    summary: "The `InFlight` observation is added without weakening the exhaustive union"
    location: "src/amoeba/process/recovery.py:91"
  - id: F012
    severity: pass
    category: correctness
    summary: "Journal-before-launch, exclusive log creation and detachment are all correct"
    location: "src/amoeba/runner/tick.py#_launch"
  - id: F013
    severity: pass
    category: error-handling
    summary: "Exit code 15 is added once and mapped at the one boundary"
    location: "src/amoeba/cli/main.py:118"
---

# Review: code — slice 122

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] The shared `RunObserver` drops other projects' state on every tick

`RunnerTenant.__init__` builds **one** `RunObserver` (`tenant.py:74`) and hands the same instance to every `ProjectTick` (`tenant.py:133`). The observer's per-entry state — `_last_poll`, `_overdue`, `_faulted` — is keyed by entry id, but `observe()` prunes it to the entries of the project currently being observed:

```python
live = {entry.id for entry in entries}          # observe.py:108
self._last_poll = {k: v for k, v in self._last_poll.items() if k in live}
self._overdue &= live
self._faulted = {k: v for k, v in self._faulted.items() if k in live}
```

`entries` is only ever `self._run_entries()` for one project (`tick.py:_run_entries`). So ticking project A deletes project B's last-poll timestamps. On B's next tick every entry has no `_last_poll` record, `_poll_due` returns `True` for all of them, and B polls every in-flight run on every tick — defeating `run_poll_interval_seconds` and the documented bound ("at most once per tick per run and no more often than `--run-poll-interval`", `docs/process-contract.md:330`–`366`). The same pruning clears `_overdue` and `_faulted`, so a standing `launch_overdue`/`run_observation_failed` fault stops recurring, `ProjectTick._close_recovered` closes the escalation, and the next tick reopens it — escalation churn across every tick in a multi-project supervisor. The `busy_rig` test in `tests/runner/test_budget_coverage.py` and `tests/runner/test_tenant.py` exercise multi-project ticks but only assert on launch counts and planner order, so neither catches it. Per-project observer instances (or keying the state by `(project_id, entry_id)`) would fix it.

### [CONCERN] `_in_flight_run_ids` subscripts a key a legacy entry does not have

```python
def _in_flight_run_ids(store: Store, project_id: str, node_id: str) -> list[str]:
    return [
        str(entry.parameters[PARAM_RUN_ID])
        for entry in store.unresolved_journal_entries(project_id)
        if entry.node_id == node_id and entry.kind is CommandKind.SQ_RUN
    ]
```

The comprehension filters on `kind` but not on the presence of `PARAM_RUN_ID`. Pre-120 rows carry no run id — that shape is explicitly supported (`docs/process-contract.md`, "Legacy"; `tests/sq_run_fixtures.py:insert_legacy_sq_run_entry`), and `observe._observe_one` and `finish._run_id` both guard for it with `isinstance(run_id, str)`. This function does not, so a `KeyError` is raised here instead of a typed answer.

It is reachable: a legacy unresolved `sq_run` entry makes `RunObserver._observe_one` raise `ValueError`, which `tenant._tick_project` catches and routes to `escalate(...)`, which calls `_in_flight_run_ids` and iterates the same unresolved set — including the legacy entry. The `KeyError` then escapes the tick, escapes `ResidentProcess._loop` (no handler there), and reaches `cli.main`'s boundary as `ExitCode.FAILURE`. The one handler that exists to isolate a project's faults (`tenant.py`, D8) is the one that throws. Using `entry.parameters.get(PARAM_RUN_ID)` and skipping or placeholder-marking the non-string case would keep it an answer.

### [CONCERN] The "one broad except" guard counts a string, not a syntax node

```python
count = sum(
    path.read_text(encoding="utf-8").count("except Exception")
    for path in package.glob("*.py")
)
assert count == 1
```

This is a textual scan, not an AST check. A docstring, comment, or test-name string containing `except Exception` inflates the count and fails the test for the wrong reason; conversely `except  Exception:` (two spaces) or `except BaseException` would slip through as zero/unchanged. The project's other mechanical guards are AST-based and deliberately so — `tests/test_import_boundaries.py` walks `ast.parse`, and `tests/test_writer_guard.py` is described in the contract as "walks the AST of every module". Matching the established pattern (`ast.ExceptHandler` with `node.type` a `Name`/`Attribute` for `Exception`) would make this guard mean what its name says.

### [CONCERN] `cli_environment`'s docstring now contradicts the function

The docstring still reads "``AMOEBA_STORE_DIR`` is the only variable set", but line 59 now also sets `PATH`:

```python
environment["AMOEBA_STORE_DIR"] = str(supervisor_dir)
stub_dir = write_sq_stub(supervisor_dir.parent / "stub-sq-bin")
environment["PATH"] = f"{stub_dir}{os.pathsep}{environment['PATH']}"
```

The added paragraph below it explains the `PATH` change, so the two statements sit three lines apart and disagree. Since this harness is the shared entry point for every CLI test, the stale invariant is the kind of thing a later reader trusts when reasoning about what a CLI subprocess can reach. Also worth noting: `cli_environment` now writes to disk (`write_sq_stub` → `mkdir` + `write_text` + `chmod`) as a side effect of being called, including from `tests/load/load_harness.py:168`.

### [CONCERN] The contract's Observer protocol block still shows a three-member union

The slice updated `Observation` in the hosting-surface table (`:211`, `:215`), the recovery pseudocode (`:411`) and the by-id observer prose (`:483`), but the protocol definition itself still reads:

```python
Observation = Adopt | NotApplied | Unknown  # frozen dataclasses
```

`InFlight` is missing, and the surrounding prose ("`Adopt` carries the `result` mapping to record…") says nothing about it. Since the contract is written so a tenant author need not read the implementation, a stale union here is the exact drift the document is meant to prevent.

### [CONCERN] No load-tier coverage for the Runner's tick path

The project's testing rules require that any code on the simulation, network, concurrency, or environment-layer paths have at least one load test asserting latency, throughput, or resource bounds, and `tests/load/test_recovery_scale.py` sets the precedent for exactly this kind of component. The Runner is the first tenant that starts subprocesses in a tick and is governed by an explicit latency bound (`tick_deadline_seconds`, `tick_call_timeout_seconds`), yet nothing in `tests/load/` exercises it — I checked, and no file under that directory references `RunnerTenant`, `runner_tenant`, or `amoeba.runner`. `tests/runner/test_budget_coverage.py` asserts the budget with a fake clock and `tests/runner/test_crash_recovery.py` drives real SIGKILLs, but neither measures a real tick against a realistic project/run count. A load test asserting that a tick with N projects and M in-flight runs still returns inside `tick_deadline_seconds` plus one call timeout would be the direct analogue of the recovery-scale test.

### [NOTE] `--sq-timeout` help text was not updated with the setting's docstring

`ProcessSettings.sq_timeout_seconds`'s docstring was updated to say it now "includes the Runner's ``sq`` probe", and `docs/process-contract.md:560` states "`--sq-timeout` also bounds the `sq` probe at start", but the flag help still reads "How long to wait for 'sq --version' at start-up." An operator tuning the probe timeout will not find it from `--help`.

### [NOTE] Unused module logger in `tick.py`

`logger = logging.getLogger(__name__)` is defined and never used in this module; the escalation logging happens in `tenant.py` and the probe logging in `probes.py`. Ruff's selected rules (`E`, `F`, `W`, `I`, `UP`, `BLE`, `ASYNC`, `B`) do not flag an assigned-but-unused module global, so this survives lint.

### [NOTE] `_record_ended` resolves `COMPLETED` for a failed run but `FAILED` for an orphaned one

`RunOutcome.FAILED` and `RunOutcome.PAUSED` block the node and then `journal_resolve(..., outcome=JournalOutcome.COMPLETED)`, while `RunOutcome.ORPHANED` blocks and resolves `FAILED` — and `RunVanished`/`LaunchFailed` also resolve `FAILED`. The asymmetry is deliberate and pinned by `tests/runner/test_finish.py`, but the rationale (the entry records that the *command* completed and reported an outcome; the *run's* failure lives in the block and the `result`) is only stated in the module docstring. The contract's Runner section (`docs/process-contract.md:330`–`369`) states the `failed` resolution only for the launch-child case, so a reader comparing `result["outcome"] == "failed"` against `entry.outcome == COMPLETED` has no statement to check it against. One sentence in the contract would remove the ambiguity.

### [NOTE] `validate_settings` reaches its fields by string name

```python
for name in ("tick_deadline_seconds", "tick_call_timeout_seconds", "run_poll_interval_seconds"):
    value: float = getattr(settings, name)
```

The `value: float` annotation is an assertion the checker cannot verify through `getattr`, and the three field names are string literals in a module that is otherwise fully typed. Since the project rule is "if a value is used in conditionals, switch cases, or lookups, define it once", an explicit three-field check (or a module-level tuple consumed by a typed accessor) would keep this under strict `pyright` rather than beside it.

### [PASS] The `InFlight` observation is added without weakening the exhaustive union

`type Observation = Adopt | InFlight | NotApplied | Unknown` gains a member and every `match` over it in `reconcile` gains the corresponding case, so the "adding another kind of answer is a type error, not a silent fall-through" property in the docstring still holds. `SquadronRunIdObserver._classify` no longer fabricates a `result` mapping (`RESULT_RUN_ID`/`RESULT_OUTCOME`/`RESULT_STATUS` are gone from the observer) — recovery resolves nothing for an in-flight run and the result keys now live once, in `runner/finish.py`, where the issuer writes them. `RecoverySummary` counts the new outcome and `describe()` reports it.

### [PASS] Journal-before-launch, exclusive log creation and detachment are all correct

`_launch` calls `build_argv` (validating params before anything is written), then `journal_issue`, then `launch` — preserving the ordering guarantee the journal exists for. `launch` opens both logs with `"xb"` inside an `ExitStack`, so an earlier attempt's evidence is never overwritten (and the parent's handles are closed on return), and passes `start_new_session=True`, `stdin=subprocess.DEVNULL` and `close_fds=True`. The environment is inherited rather than passed and is never logged or journaled, which matches the contract's credential note. Confirmation reads a bounded 64 KiB head and compares a whole line after stripping only the terminator — `str.splitlines()` is correctly avoided, since it would also split on form feeds.

### [PASS] Exit code 15 is added once and mapped at the one boundary

`UPSTREAM_SHAPE = 15` is declared in the `ExitCode` enum with the reason 8 was unavailable, `UpstreamShapeError` is exported from `amoeba.process` (pinned in `tests/test_process_public_api.py`), and `main` maps it to the enum member rather than a literal. `runner/tenant.py` re-raises it out of the per-project handler alongside the store failures, so it reaches that boundary instead of being swallowed into an `unexpected_fault` escalation. `tests/test_cli_lifecycle.py` pins the whole enum's name→value mapping so a renumbering cannot pass silently.

### Run Digest

- Response length: 12537 chars
- Response is newline-free: no
- Tool calls made: 44
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 536961
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2606069 / 2286572 / not computed / 144871 / 137321
- Duration: 649.9 s
- Cost: $0.13 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

### Raw Response

## Summary
[CONCERNS]

The slice is well-structured: the `InFlight` observation is added as a proper union member (no fallback case needed), the `ExitCode` addition is defined once, journaling-before-launch ordering is preserved, and the detached-launch flags are correct. The concerns below are about cross-project state in a shared observer, an unguarded subscript on a documented legacy entry shape, and three documentation/guard inconsistencies that the slice left half-updated.

## Findings

### [CONCERN] The shared `RunObserver` drops other projects' state on every tick
category: correctness
location: src/amoeba/runner/tenant.py:74

`RunnerTenant.__init__` builds **one** `RunObserver` (`tenant.py:74`) and hands the same instance to every `ProjectTick` (`tenant.py:133`). The observer's per-entry state — `_last_poll`, `_overdue`, `_faulted` — is keyed by entry id, but `observe()` prunes it to the entries of the project currently being observed:

```python
live = {entry.id for entry in entries}          # observe.py:108
self._last_poll = {k: v for k, v in self._last_poll.items() if k in live}
self._overdue &= live
self._faulted = {k: v for k, v in self._faulted.items() if k in live}
```

`entries` is only ever `self._run_entries()` for one project (`tick.py:_run_entries`). So ticking project A deletes project B's last-poll timestamps. On B's next tick every entry has no `_last_poll` record, `_poll_due` returns `True` for all of them, and B polls every in-flight run on every tick — defeating `run_poll_interval_seconds` and the documented bound ("at most once per tick per run and no more often than `--run-poll-interval`", `docs/process-contract.md:330`–`366`). The same pruning clears `_overdue` and `_faulted`, so a standing `launch_overdue`/`run_observation_failed` fault stops recurring, `ProjectTick._close_recovered` closes the escalation, and the next tick reopens it — escalation churn across every tick in a multi-project supervisor. The `busy_rig` test in `tests/runner/test_budget_coverage.py` and `tests/runner/test_tenant.py` exercise multi-project ticks but only assert on launch counts and planner order, so neither catches it. Per-project observer instances (or keying the state by `(project_id, entry_id)`) would fix it.

### [CONCERN] `_in_flight_run_ids` subscripts a key a legacy entry does not have
category: error-handling
location: src/amoeba/runner/faults.py:196

```python
def _in_flight_run_ids(store: Store, project_id: str, node_id: str) -> list[str]:
    return [
        str(entry.parameters[PARAM_RUN_ID])
        for entry in store.unresolved_journal_entries(project_id)
        if entry.node_id == node_id and entry.kind is CommandKind.SQ_RUN
    ]
```

The comprehension filters on `kind` but not on the presence of `PARAM_RUN_ID`. Pre-120 rows carry no run id — that shape is explicitly supported (`docs/process-contract.md`, "Legacy"; `tests/sq_run_fixtures.py:insert_legacy_sq_run_entry`), and `observe._observe_one` and `finish._run_id` both guard for it with `isinstance(run_id, str)`. This function does not, so a `KeyError` is raised here instead of a typed answer.

It is reachable: a legacy unresolved `sq_run` entry makes `RunObserver._observe_one` raise `ValueError`, which `tenant._tick_project` catches and routes to `escalate(...)`, which calls `_in_flight_run_ids` and iterates the same unresolved set — including the legacy entry. The `KeyError` then escapes the tick, escapes `ResidentProcess._loop` (no handler there), and reaches `cli.main`'s boundary as `ExitCode.FAILURE`. The one handler that exists to isolate a project's faults (`tenant.py`, D8) is the one that throws. Using `entry.parameters.get(PARAM_RUN_ID)` and skipping or placeholder-marking the non-string case would keep it an answer.

### [CONCERN] The "one broad except" guard counts a string, not a syntax node
category: testing
location: tests/runner/test_tenant.py#test_the_runner_package_has_exactly_one_broad_except

```python
count = sum(
    path.read_text(encoding="utf-8").count("except Exception")
    for path in package.glob("*.py")
)
assert count == 1
```

This is a textual scan, not an AST check. A docstring, comment, or test-name string containing `except Exception` inflates the count and fails the test for the wrong reason; conversely `except  Exception:` (two spaces) or `except BaseException` would slip through as zero/unchanged. The project's other mechanical guards are AST-based and deliberately so — `tests/test_import_boundaries.py` walks `ast.parse`, and `tests/test_writer_guard.py` is described in the contract as "walks the AST of every module". Matching the established pattern (`ast.ExceptHandler` with `node.type` a `Name`/`Attribute` for `Exception`) would make this guard mean what its name says.

### [CONCERN] `cli_environment`'s docstring now contradicts the function
category: documentation
location: tests/cli_harness.py:45

The docstring still reads "``AMOEBA_STORE_DIR`` is the only variable set", but line 59 now also sets `PATH`:

```python
environment["AMOEBA_STORE_DIR"] = str(supervisor_dir)
stub_dir = write_sq_stub(supervisor_dir.parent / "stub-sq-bin")
environment["PATH"] = f"{stub_dir}{os.pathsep}{environment['PATH']}"
```

The added paragraph below it explains the `PATH` change, so the two statements sit three lines apart and disagree. Since this harness is the shared entry point for every CLI test, the stale invariant is the kind of thing a later reader trusts when reasoning about what a CLI subprocess can reach. Also worth noting: `cli_environment` now writes to disk (`write_sq_stub` → `mkdir` + `write_text` + `chmod`) as a side effect of being called, including from `tests/load/load_harness.py:168`.

### [CONCERN] The contract's Observer protocol block still shows a three-member union
category: documentation
location: docs/process-contract.md:453

The slice updated `Observation` in the hosting-surface table (`:211`, `:215`), the recovery pseudocode (`:411`) and the by-id observer prose (`:483`), but the protocol definition itself still reads:

```python
Observation = Adopt | NotApplied | Unknown  # frozen dataclasses
```

`InFlight` is missing, and the surrounding prose ("`Adopt` carries the `result` mapping to record…") says nothing about it. Since the contract is written so a tenant author need not read the implementation, a stale union here is the exact drift the document is meant to prevent.

### [CONCERN] No load-tier coverage for the Runner's tick path
category: testing
location: tests/load

The project's testing rules require that any code on the simulation, network, concurrency, or environment-layer paths have at least one load test asserting latency, throughput, or resource bounds, and `tests/load/test_recovery_scale.py` sets the precedent for exactly this kind of component. The Runner is the first tenant that starts subprocesses in a tick and is governed by an explicit latency bound (`tick_deadline_seconds`, `tick_call_timeout_seconds`), yet nothing in `tests/load/` exercises it — I checked, and no file under that directory references `RunnerTenant`, `runner_tenant`, or `amoeba.runner`. `tests/runner/test_budget_coverage.py` asserts the budget with a fake clock and `tests/runner/test_crash_recovery.py` drives real SIGKILLs, but neither measures a real tick against a realistic project/run count. A load test asserting that a tick with N projects and M in-flight runs still returns inside `tick_deadline_seconds` plus one call timeout would be the direct analogue of the recovery-scale test.

### [NOTE] `--sq-timeout` help text was not updated with the setting's docstring
category: documentation
location: src/amoeba/cli/settings_flags.py:113

`ProcessSettings.sq_timeout_seconds`'s docstring was updated to say it now "includes the Runner's ``sq`` probe", and `docs/process-contract.md:560` states "`--sq-timeout` also bounds the `sq` probe at start", but the flag help still reads "How long to wait for 'sq --version' at start-up." An operator tuning the probe timeout will not find it from `--help`.

### [NOTE] Unused module logger in `tick.py`
category: style
location: src/amoeba/runner/tick.py:51

`logger = logging.getLogger(__name__)` is defined and never used in this module; the escalation logging happens in `tenant.py` and the probe logging in `probes.py`. Ruff's selected rules (`E`, `F`, `W`, `I`, `UP`, `BLE`, `ASYNC`, `B`) do not flag an assigned-but-unused module global, so this survives lint.

### [NOTE] `_record_ended` resolves `COMPLETED` for a failed run but `FAILED` for an orphaned one
category: design
location: src/amoeba/runner/finish.py#_record_ended

`RunOutcome.FAILED` and `RunOutcome.PAUSED` block the node and then `journal_resolve(..., outcome=JournalOutcome.COMPLETED)`, while `RunOutcome.ORPHANED` blocks and resolves `FAILED` — and `RunVanished`/`LaunchFailed` also resolve `FAILED`. The asymmetry is deliberate and pinned by `tests/runner/test_finish.py`, but the rationale (the entry records that the *command* completed and reported an outcome; the *run's* failure lives in the block and the `result`) is only stated in the module docstring. The contract's Runner section (`docs/process-contract.md:330`–`369`) states the `failed` resolution only for the launch-child case, so a reader comparing `result["outcome"] == "failed"` against `entry.outcome == COMPLETED` has no statement to check it against. One sentence in the contract would remove the ambiguity.

### [NOTE] `validate_settings` reaches its fields by string name
category: typing
location: src/amoeba/runner/factory.py#validate_settings

```python
for name in ("tick_deadline_seconds", "tick_call_timeout_seconds", "run_poll_interval_seconds"):
    value: float = getattr(settings, name)
```

The `value: float` annotation is an assertion the checker cannot verify through `getattr`, and the three field names are string literals in a module that is otherwise fully typed. Since the project rule is "if a value is used in conditionals, switch cases, or lookups, define it once", an explicit three-field check (or a module-level tuple consumed by a typed accessor) would keep this under strict `pyright` rather than beside it.

### [PASS] The `InFlight` observation is added without weakening the exhaustive union
category: design
location: src/amoeba/process/recovery.py:91

`type Observation = Adopt | InFlight | NotApplied | Unknown` gains a member and every `match` over it in `reconcile` gains the corresponding case, so the "adding another kind of answer is a type error, not a silent fall-through" property in the docstring still holds. `SquadronRunIdObserver._classify` no longer fabricates a `result` mapping (`RESULT_RUN_ID`/`RESULT_OUTCOME`/`RESULT_STATUS` are gone from the observer) — recovery resolves nothing for an in-flight run and the result keys now live once, in `runner/finish.py`, where the issuer writes them. `RecoverySummary` counts the new outcome and `describe()` reports it.

### [PASS] Journal-before-launch, exclusive log creation and detachment are all correct
category: correctness
location: src/amoeba/runner/tick.py#_launch

`_launch` calls `build_argv` (validating params before anything is written), then `journal_issue`, then `launch` — preserving the ordering guarantee the journal exists for. `launch` opens both logs with `"xb"` inside an `ExitStack`, so an earlier attempt's evidence is never overwritten (and the parent's handles are closed on return), and passes `start_new_session=True`, `stdin=subprocess.DEVNULL` and `close_fds=True`. The environment is inherited rather than passed and is never logged or journaled, which matches the contract's credential note. Confirmation reads a bounded 64 KiB head and compares a whole line after stripping only the terminator — `str.splitlines()` is correctly avoided, since it would also split on form feeds.

### [PASS] Exit code 15 is added once and mapped at the one boundary
category: error-handling
location: src/amoeba/cli/main.py:118

`UPSTREAM_SHAPE = 15` is declared in the `ExitCode` enum with the reason 8 was unavailable, `UpstreamShapeError` is exported from `amoeba.process` (pinned in `tests/test_process_public_api.py`), and `main` maps it to the enum member rather than a literal. `runner/tenant.py` re-raises it out of the per-project handler alongside the store failures, so it reaches that boundary instead of being swallowed into an `unexpected_fault` escalation. `tests/test_cli_lifecycle.py` pins the whole enum's name→value mapping so a renumbering cannot pass silently.
