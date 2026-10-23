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
reviewedSha: 8736ea5419144762394302dea321fb1469358033
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 46
diffTruncated: false
turns: 20
promptTokens: 2867753
cachedTokens: 2497770
completionTokens: 125854
reasoningTokens: 117718
durationSeconds: 602.9
costUsd: 0.129786
costBasis: alias_pricing
runId: run-20261023-p56-63bf9ff6
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Crash-safe ordering, budget discipline and the single process boundary are implemented as designed"
    location: "src/amoeba/runner/tick.py#ProjectTick.run"
  - id: F002
    severity: concern
    category: uncategorized
    summary: "The same malformed run id is an answer in recovery and an exception in the Runner"
    location: "src/amoeba/runner/observe.py#RunObserver._observe_one"
  - id: F003
    severity: concern
    category: uncategorized
    summary: "A settings invariant is stated as a property but is never enforced"
    location: "src/amoeba/runner/factory.py#validate_settings"
  - id: F004
    severity: concern
    category: uncategorized
    summary: "Tests import value types from a module that only re-exports them"
    location: "tests/runner/test_finish.py:12"
  - id: F005
    severity: note
    category: uncategorized
    summary: "Stale module docstring in `faults.py`"
    location: "src/amoeba/runner/faults.py:4"
  - id: F006
    severity: note
    category: uncategorized
    summary: "A test asserts a private attribute rather than observable behaviour"
    location: "tests/runner/test_factory.py#test_passed_planners_are_used_as_given"
  - id: F007
    severity: note
    category: uncategorized
    summary: "`cli_environment` gained a filesystem side effect on every call"
    location: "tests/cli_harness.py:40"
---

# Review: code — slice 122

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Crash-safe ordering, budget discipline and the single process boundary are implemented as designed

The tick sequence matches D1/D2/D10: `journal_issue` commits before `launch()` is called (`_launch`), `_record_finished` runs block-then-resolve through `finish.record`, and `_close_recovered` is reached only on a `COMPLETE` tick, so a cut-off or faulted tick closes nothing. `_act` and `_after_launch_poll`/`_confirmed` each consult `TickBudget.allows_call()` immediately before the call they guard, and `observe.observe` sorts least-recently-polled first so a deadline cannot starve the same runs. `tenant._tick_project` re-raises `(*STORE_FAILURES, UpstreamShapeError)` and escalates everything else, and `tests/runner/test_tenant.py::test_the_runner_package_has_exactly_one_broad_except` pins the single `except Exception` by AST, so a second one cannot appear unnoticed.

### [CONCERN] The same malformed run id is an answer in recovery and an exception in the Runner

`RunObserver._observe_one` raises `ValueError` when `entry.parameters[PARAM_RUN_ID]` is not a non-empty string, and `finish._run_id` raises on the same condition (with a weaker check: it accepts the empty string that `observe` rejects). Recovery answers the identical data condition with a handled `Unknown(reason=...)` in `src/amoeba/process/observers/sq_run_id.py`, so the two paths that read the same journal row disagree about whether it is an expected answer or a bug. The consequence in the Runner is larger than a different label: the raise propagates out of `observe()` before the remaining entries are visited, so one malformed entry stops the other in-flight runs in that project from being observed or recorded on that tick, and the operator sees `unexpected_fault` rather than a run-observation fault. Both paths do end in an escalation, so this is not a correctness failure, but the divergence is worth reconciling — either answer the condition as a `Fault` and continue the pass, or make recovery raise too.

### [CONCERN] A settings invariant is stated as a property but is never enforced

`ProcessSettings`'s docstring for `tick_call_timeout_seconds` asserts it is "Larger than `tick_deadline_seconds` so one call that starts just inside the deadline still has room to finish", but `validate_settings` checks only that each bound is positive and that `tick_call_timeout_seconds < shutdown_grace_seconds`. Both values are reachable through documented flags (`--tick-deadline`, `--tick-call-timeout` in `src/amoeba/cli/settings_flags.py`), so `--tick-deadline 60 --tick-call-timeout 8` is accepted and silently violates the stated relationship. Either enforce it alongside the existing grace check, or reword the docstring so it describes the defaults rather than a required property — as written, a reader designing against `settings.py` would rely on something the code does not guarantee.

### [CONCERN] Tests import value types from a module that only re-exports them

`LaunchFailed`, `RunEnded` and `RunVanished` are defined in `src/amoeba/runner/observed.py`; `tests/runner/test_finish.py:12`, `tests/runner/test_observe_launch.py:12` and `tests/runner/test_observe_poll.py:13` all import them from `src/amoeba/runner/observe.py`, which merely re-imports them. This mirrors the convention the project already enforces for production code — `tests/test_import_boundaries.py` Rule 8 explicitly requires `SubmissionKind` to be taken "from its defining module" — and here it means a future refactor that stops `observe.py` importing a name it does not use would break three test modules for a reason unrelated to behaviour. Import them from `amoeba.runner.observed` instead.

### [NOTE] Stale module docstring in `faults.py`

The docstring says "Escalation writes join this module in a later task", but `raise_expected_faults` and `escalate` — the escalation writes — are both defined in this module already. The line reads as a leftover from the task ordering in the slice design and now misdescribes the file.

### [NOTE] A test asserts a private attribute rather than observable behaviour

The test asserts `tenant._planners == (planner,)`, reaching into a private field with a `pyright: ignore[reportPrivateUsage]`, and the planner it passes does not satisfy the `Planner` protocol (hence `# type: ignore[arg-type]`). It proves the constructor stored the tuple but not that the planner is consulted, which is the behaviour `runner_tenant`'s `planners` argument exists for. Driving one tick and asserting the planner's `plan` was called would test the same decision through the public surface.

### [NOTE] `cli_environment` gained a filesystem side effect on every call

`cli_environment` previously built and returned an environment mapping; it now also calls `write_sq_stub(supervisor_dir.parent / "stub-sq-bin")` and rewrites `PATH` on every invocation. `write_sq_stub` is idempotent, so repeated calls are harmless, but the helper is used by unrelated suites (`tests/load/load_harness.py`, `tests/ingest_e2e_harness.py`, `tests/detection_e2e_harness.py`) and now silently makes a stub `sq` visible to all of them, and it assumes a `supervisor_dir.parent` layout. `tests/test_cli_lifecycle.py::test_a_failing_sq_probe_fails_the_start_naming_the_shape` already has to discard the whole `PATH` to get the opposite behaviour, which is the shape of the coupling to watch.

### Run Digest

- Response length: 6400 chars
- Response is newline-free: no
- Tool calls made: 46
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 454719
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2867753 / 2497770 / not computed / 125854 / 117718
- Duration: 602.9 s
- Cost: $0.13 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
