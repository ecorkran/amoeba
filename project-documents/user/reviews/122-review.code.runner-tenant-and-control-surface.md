---
docType: review
layer: project
reviewType: code
slice: runner-tenant-and-control-surface
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: 9672d165dca7a42c79fa2f84a51ac3e13f6e13af
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
diffTruncated: false
turns: 20
promptTokens: 2562226
cachedTokens: 2237488
completionTokens: 94187
reasoningTokens: 86754
durationSeconds: 454.9
costUsd: 0.106553
costBasis: alias_pricing
runId: run-20261023-p56-63bf9ff6
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Recovery's `InFlight` couples the upstream-agnostic protocol to Squadron"
    location: "src/amoeba/process/recovery.py:27"
  - id: F002
    severity: concern
    category: error-handling
    summary: "An unexpected fault on a node blocked on a non-human kind is recorded nowhere"
    location: "src/amoeba/runner/faults.py#escalate"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A malformed `issued_at` aborts the whole project tick instead of faulting one entry"
    location: "src/amoeba/runner/observe.py#_within_grace"
  - id: F004
    severity: concern
    category: test-infrastructure
    summary: "`cli_environment` now writes to `supervisor_dir.parent`, an unenforced precondition"
    location: "tests/cli_harness.py:40-62"
  - id: F005
    severity: note
    category: error-handling
    summary: "Store failures re-raise without a log line"
    location: "src/amoeba/runner/tenant.py#_tick_project"
  - id: F006
    severity: note
    category: consistency
    summary: "`cf` and `sq` executable constants live in different places"
    location: "src/amoeba/runner/probes.py:38"
  - id: F007
    severity: note
    category: style
    summary: "Exit-code and head-size literals lack `Final`, and one duplicates knowledge held elsewhere"
    location: "src/amoeba/runner/observe.py:45"
  - id: F008
    severity: note
    category: test-structure
    summary: "New tests import a private helper across modules"
    location: "tests/runner/test_budget_coverage.py:16"
  - id: F009
    severity: note
    category: consistency
    summary: "Shared result/parameter key names are re-typed as literals in the new tests"
    location: "tests/contract/runner_tenant.py"
  - id: F010
    severity: pass
    category: correctness
    summary: "The tick budget is enforced before every call site and mechanically pinned"
    location: "src/amoeba/runner/budget.py"
  - id: F011
    severity: pass
    category: correctness
    summary: "Crash safety and idempotent recording are proven, not asserted"
    location: "src/amoeba/runner/finish.py"
---

# Review: code — slice 122

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Recovery's `InFlight` couples the upstream-agnostic protocol to Squadron

`recovery.py` imports `RunOutcome` from `amoeba.process.sq_outcome` and `InFlight.outcome: RunOutcome` makes the shared observation vocabulary carry a Squadron-specific enum. The module docstring still says "This module knows nothing about Squadron or Context Forge… That separation is the point: adding a command kind means adding an enum member, its required parameter keys, and an observer, with no change here." That claim is now false, and the Observer protocol documented in `docs/process-contract.md` ("The Observer protocol" section, `Observation = Adopt | InFlight | NotApplied | Unknown`) no longer holds for a non-Squadron observer: any observer for a future command kind that wants to report "reached the system, not finished" must supply a Squadron `RunOutcome`. Either the field should be an upstream-neutral value (e.g. an opaque status string plus the run id, with the Runner classifying), or the docstring and the contract section should be amended to say recovery now knows one upstream's outcome vocabulary.

### [CONCERN] An unexpected fault on a node blocked on a non-human kind is recorded nowhere

In `escalate()`, `blocked_state_for(node.id) is not None` causes an early `return` with no write at all. The docstring justifies this as "a node already blocked gets nothing more, so a fault repeating cannot storm", and `tests/runner/test_faults.py::test_an_already_blocked_node_gets_nothing_more` pins it — but that test only exercises a `HUMAN` block. For a node blocked on `SQ_CHECKPOINT` or `JUDGE`, the fault is dropped entirely: no second block (correct) *and* no project-scoped escalation, so the only trace is the `logger.exception` line in `RunnerTenant._tick_project`. Compare `Store.journal_escalate`, which has an explicit already-blocked branch (`_escalate_existing_block`) that writes an escalation against the existing block precisely because "whatever it is blocked on … a human must now also hear that a command's outcome is unknown". The Runner should take the same path: when the existing block is not `HUMAN`, fall through to `raise_project_escalation` rather than returning.

### [CONCERN] A malformed `issued_at` aborts the whole project tick instead of faulting one entry

`_within_grace` raises `ValueError` for an entry with no `issued_at` or a naive one. That exception propagates out of `observe()` → `ProjectTick.run()` → `RunnerTenant._tick_project`'s broad handler, which escalates it as `unexpected_fault` and returns — so for that tick the project's finished runs are never recorded, its expected faults are never raised, nothing is decided or acted on, and `_close_recovered` never runs. The same module states the opposite principle one method above: "As in recovery, a malformed run id is an answer, not a bug: it faults this entry and the others are still observed" (`_observe_one`). The two malformed-row cases should be handled alike — a `Fault(kind=RUN_OBSERVATION_FAILED, …)` on that entry and carry on. The path is nearly unreachable today (the store always writes an aware timestamp), which is exactly why the inconsistency is easy to keep.

### [CONCERN] `cli_environment` now writes to `supervisor_dir.parent`, an unenforced precondition

`cli_environment` was a pure environment builder; it now calls `write_sq_stub(supervisor_dir.parent / "stub-sq-bin")` on every invocation — including the default path inside `run_cli` and `start_background`, so a test that only reads a listing still writes a stub `sq` to disk. The docstring asserts the parent "must therefore be a throwaway directory", but nothing enforces it and no fixture guarantees the name: every current caller happens to pass `tmp_path / "supervisor"` (or a `tmp_path_factory.mktemp(...) / "supervisor"`), so the parent is `tmp_path` today. A future test that passes `tmp_path` itself as the supervisor directory would place the stub in pytest's session root, and one that passed a shared directory would make every test in the session silently depend on the same stub. Passing the stub directory in explicitly (or writing it under `supervisor_dir` and adding it to `PATH` from there) would make the precondition structural rather than documentary.

### [NOTE] Store failures re-raise without a log line

The `except (*STORE_FAILURES, UpstreamShapeError): raise` branch re-raises with no logging, while the branch below it follows the project's stated pattern (`logger.exception` then handle). The operator does see a message, because `amoeba.cli.main` prints `amoeba: {error}` for `StoreError` — so nothing is silent — but the convention used elsewhere in this package (`recovery._observe`) is to log at ERROR before re-raising. Worth a one-line `logger.exception` for consistency, or a comment naming the boundary that will report it.

### [NOTE] `cf` and `sq` executable constants live in different places

`SQ_EXECUTABLE` is defined once in `amoeba.process.sq_outcome` and re-exported; `CF_EXECUTABLE` is defined locally in `runner/probes.py`. Two placement rules for the same kind of value invite drift if a second caller ever needs the `cf` name. Not a correctness issue — no second definition exists today.

### [NOTE] Exit-code and head-size literals lack `Final`, and one duplicates knowledge held elsewhere

`USAGE_ERROR_EXIT_CODE = 2`, `probes.OUTPUT_HEAD_CHARS = 200` and `tick.CLOSED_BY: str = "runner"` are unannotated or `str`-annotated, where the rest of the package (including the adjacent `budget.py`, `launch.py`, `faults.py`) uses `Final`. The `2` in particular encodes Squadron's usage-error exit code, which `sq_outcome.OUTCOME_EXIT_CODES` documents in a comment but does not export; deriving it from that module would keep the one-place-per-value rule.

### [NOTE] New tests import a private helper across modules

`from runner.test_probes import _link  # pyright: ignore[reportPrivateUsage]` reaches into another test module's private helper, and `tests/runner/test_tenant.py` uses `rig.tenant._tracker.confirm(...)` with the same suppression. `_link` is a four-line fixture builder; moving it to `tests/runner/tick_support.py` (where `PROJECT` and `Rig` already live) would remove the suppression and the cross-module private import.

### [NOTE] Shared result/parameter key names are re-typed as literals in the new tests

`_finish_in_flight` writes `result={"run_id": run_id_of(entry)}` with a bare literal, and `tests/runner/test_observer_*`/`test_tick.py` build parameter dicts with bare `"pipeline"`, `"params"`, `"checkout"` alongside the imported `PARAM_RUN_ID`. `tests/runner/test_launch.py` already imports `PARAM_CHECKOUT`, and `finish.py` defines `RESULT_RUN_ID`, so the constants exist; the literals are a small step away from the "define the value once" rule and would silently diverge if a key were renamed. Also note `tests/runner/test_launch_ids.py` asserts `len(STORE_FAILURES) == 5`, which fails on any legitimate addition to the store-failure set rather than on a behavior change — the other vocabulary assertions in that test (enum value sets) are the ones worth keeping.

### [PASS] The tick budget is enforced before every call site and mechanically pinned

`TickBudget.allows_call()` is consulted before the poll (`observe._confirmed`, `_unconfirmed`), before each `cf` probe command (`probes.probe_link`, per command, so a cut-off between the two commands starts no second call), and before `Popen` (`tick._act`). `tests/runner/test_budget_coverage.py` wraps all three call kinds so a new call site that skips the check fails the suite, and `tests/load/test_runner_tick_load.py` bounds a tick to `deadline + one call` under a realistic 10×10 configuration with real per-poll cost. The tenant obligation in `docs/process-contract.md` is honored, including the "no new call after a stop request" clause via `StopSignal`.

### [PASS] Crash safety and idempotent recording are proven, not asserted

`record` always blocks before it resolves, and `_block_once` returns early when a block already exists, so a crash between the two writes leaves a state the next tick finishes — `tests/runner/test_finish.py::test_reentry_after_a_crash_between_block_and_resolve_finishes_the_sequence` and `tests/runner/test_crash_recovery.py` (real `SIGKILL` at four points, real restart, real stub `sq`) exercise this end to end. The recovery change that leaves an id-bearing run in flight (`InFlight`) is covered on both sides: `tests/test_recovery.py` pins that the entry stays unresolved and is counted, and `tests/contract/runner_tenant.py` + `steps.check_finished_review` pin that the issuer finishes it with the run id in `result`, which keeps the ownership guarantee for pruning intact.

### Run Digest

- Response length: 10090 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 336870
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2562226 / 2237488 / not computed / 94187 / 86754
- Duration: 454.9 s
- Cost: $0.11 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
