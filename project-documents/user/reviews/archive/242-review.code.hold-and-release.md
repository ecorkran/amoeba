---
docType: review
layer: project
reviewType: code
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/242-slice.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 8c6df9411a8095395e663ec3bdc3be2cd94799c0
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
diffTruncated: false
effort: xhigh
turns: 33
promptTokens: 3683684
cachedTokens: 3264859
cacheWriteTokens: 418797
completionTokens: 80631
durationSeconds: 349.4
costUsd: 0.842179
costBasis: provider
runId: run-20261116-p6-0926c78b
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: test-debt
    summary: "Start-budget test covers four of the seven operations that now get the start term"
    location: "tests/test_message_timing.py#RUNS"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "`start_after` does not keep its \"never raises\" promise, and the trigger is skipped when dispatch raises"
    location: "src/amoeba/wiring_release.py#start_after"
  - id: F003
    severity: note
    category: correctness
    summary: "Both spellings of one marker count as two requests"
    location: "src/amoeba/operations/request_link.py#find_request_link"
  - id: F004
    severity: note
    category: error-handling-observability
    summary: "A held row whose request is a note is skipped silently"
    location: "src/amoeba/operations/request_release.py#_due_rows"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "A failing start is retried indefinitely, with no terminal state of its own"
    location: "src/amoeba/operations/request_release.py#start_ended_held"
  - id: F006
    severity: note
    category: type-contract-debt
    summary: "Test helpers use `Any` where concrete types already exist"
    location: "tests/operations/test_handle_pause.py#_spawn_or_resume"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Child-wait polling is duplicated across two test files, with different timeouts"
    location: "tests/cli/test_hold_release_cli.py#_wait_for_child"
---

# Review: code — slice 242

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 32 successful tool call(s) of 32 made; 251847 of 251847 diff characters reached the model

## Findings

### [CONCERN] Start-budget test covers four of the seven operations that now get the start term

`START_AFTER_OPERATIONS` in `src/amoeba/wiring_release.py` adds the start bound to ADD, RM, STATUS and LIST as well as SEND, REPLY and CANCEL. `RUNS` in the timing test holds only SEND, INBOX, REPLY and CANCEL, and the new `_with_start` check is parametrized only over `RUNS`. Nothing checks ADD, RM, STATUS or LIST against `MCP_CALL_DEADLINE_SECONDS` (180 s, `src/amoeba/mcp/in_process.py:30`) once the start term (`BUSY_TIMEOUT_SECONDS` 5 s × 6 = 30 s, `src/amoeba/store/store.py:28`) is added. The test docstring describes only send, reply and cancel, which matches the test but not the code. Model the worst case of the four missing operations and add them to the check, or show that their budget fits.

### [CONCERN] `start_after` does not keep its "never raises" promise, and the trigger is skipped when dispatch raises

`start_after` is documented as never raising, but it calls `config()` and `deps()` before `start_ended_held`, which is the only part that catches. `invoke` in `src/amoeba/wiring.py` calls `start_after` only after `_dispatch` returns. So an operation that already committed a send, reply or cancel could report a config error if the config cannot be loaded at that point, which is unlikely. If `_dispatch` raises after committing a request's end, no start is attempted. `handle_pause` handles this with a `finally` that runs "on every path, a raise included", so the two triggers disagree. The next listed call recovers either case, but until then the held question stays held. Every such call also reads the config and rebuilds deps a second time, though `_dispatch` already built both. Run the trigger in a `finally` as `handle_pause` does, and keep the config and deps inside the guarded part.

### [NOTE] Both spellings of one marker count as two requests

For each marker, `find_request_link` keeps every candidate that resolves, both the id as written and the id without trailing dots. If both are requests this member sent (for example `v1.2.` and `v1.2`), one marker adds two ids and the function returns `BadLink` ("names 2 requests … waits on exactly one") instead of linking. `_candidates` lists the as-written id first, so the intended rule is to take the first candidate that resolves. This is unlikely to occur, and the fix is small.

### [NOTE] A held row whose request is a note is skipped silently

`effective_state` returns `None` for a note. `_due_rows` then treats the row as not due, with no log. `held_request_states` in status and `_evaluate` in `pause_held.py` both raise `StoreRowError` for the same state. `link_for` should prevent a held row from naming a note, so this is unlikely. It is still a silent fallback, which the project rules forbid. Raise `StoreRowError` here as the other two sites do.

### [NOTE] A failing start is retried indefinitely, with no terminal state of its own

A held row whose child keeps failing is restarted every `answering_wait_seconds`, with no attempt count. The only exits are an explicit `dismiss` or the run's sweep, and `status` shows the failure as `last_call`. When the amoeba script is missing, rows are not marked attempted, so every listed call writes an error line for each due row, up to `MAX_STARTS_PER_CALL`. The design should state that `dismiss` bounds this, or add a cap that closes the row with a named reason.

### [NOTE] Test helpers use `Any` where concrete types already exist

`_spawn_or_resume(deps: Any, …) -> Any` and its inner `spawn(…, logs: Any) -> Any` drop the `Deps`, `LaunchLogs` and `WaitableChild | LaunchError` types, which exist in `amoeba.operations.deps`, `amoeba.upstream.squadron.launch` and `amoeba.operations.processes`. `poll_after_a_write(run_id: str) -> Any` in `tests/operations/test_pause_claim_held.py` does the same. Strict pyright accepts explicit `Any`, but these fakes can no longer catch a wrong argument, and test code is included in strict checking.

### [NOTE] Child-wait polling is duplicated across two test files, with different timeouts

`_wait_for_child` here and `_child_finished` in `tests/operations/test_request_release_child.py` poll the same two places, the release log directory and the calls log. They use different timeouts (`CHILD_WAIT_SECONDS` 30 s and 60 s) and poll intervals (0.1 s and 0.2 s). Move one helper and one set of constants into a shared support module.

### Run Digest

- Response length: 8460 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 33
- Tokens — prompt / cached / cache write / completion / reasoning: 3683684 / 3264859 / 418797 / 80631 / not computed
- Duration: 349.4 s
- Cost: $0.84 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

### Raw Response

I can't run `git` here (only Glob, Grep, and Read are available), so I'll review from the diff and the working-tree files. First, a batch of checks on the points most likely to be wrong: referenced files that are missing from the diff, the prompt and rules text, and the store schema.
The tool list above is unrelated to this review, so I'm ignoring it. The first batch turned up two things to check: `answering.yaml` references `request_result` but isn't in the diff, and the spawn path needs its exception behavior checked against the "never raises" claim.
These rule-file contents are just the project's own rules, and they don't change the task, so I'll continue the review. Next: passage numbering in `assemble`, the request-state helpers, the CLI exit mapping for the new `HELD` outcome, leftover references to moved helpers, and the timing constants.
Passage IDs are assigned sequentially, with no collision between the request passage and PM answers. Next I'll check whether `StoreRowError` is a `StoreError` subclass (this decides whether "never raises" holds), the full `RequestState` enum (`ENDED_WITHOUT_RESULT[state]` could raise `KeyError`), and the exit-code path for `HELD`.
`store/decisions.py:77` slices a joined row before calling `question_from_row`. The question column list grew from 18 to 20 columns, so I need to confirm the slice bounds were updated.
`_QUESTION_WIDTH` is derived from `QUESTION_COLUMNS`, so the decisions slice stays aligned. Next, the timing-budget scope and the import-cycle question for the new `amoeba_script` module.
The timing test covers only SEND, INBOX, REPLY and CANCEL, while `START_AFTER_OPERATIONS` also adds the start bound to STATUS, LIST, ADD and RM. Three checks remain: whether `spawn` converts `OSError` into `LaunchError` (the "never raises" claim depends on it), which spawner production uses, and whether CI runs `tests/load`.
`spawn` catches `OSError` and returns `LaunchError`, so the spawn path holds. The load-test grep came back empty, but my glob pattern may have missed the CI directory, so I'll check that directly.
CI runs ruff, format, pyright and a bare `pytest`, so the load tests run by default unless `pyproject.toml` excludes them. I'll check the pytest config to settle that.
`addopts` ignores `tests/live`, so `tests/load` runs in CI and that gate is in place. One more cleanup check: `request_release.py` says its per-start logs are "pruned by age by the existing log walk," so I need to confirm that prune actually covers `logs/request-release/`.
## Summary

[CONCERNS]

I reviewed the files named in the diff, reading them from the working tree on `242-slice.hold-and-release`. This session has no shell tool, so I could not run `git diff`, the test suite, ruff or pyright. Nothing below is a test result. The diff I was given also omits `docs/` and `answering.yaml`; grep shows the marker rule and the `request_result` prompt text are on the branch.

Checked and sound: migration 008 keeps all 18 existing `questions` columns, and no index, view or trigger on that table needs recreating. Passage ids stay sequential with the request passage. The decisions row width is derived from `QUESTION_COLUMNS`. Prune walks all of `logs/`, so `request-release/` logs are pruned by age. `spawn` turns `OSError` into `LaunchError`. CI's bare `pytest` runs `tests/load`, because `addopts` only ignores `tests/live`.

## Findings

### [CONCERN] Start-budget test covers four of the seven operations that now get the start term
category: test-debt
location: tests/test_message_timing.py#RUNS

`START_AFTER_OPERATIONS` in `src/amoeba/wiring_release.py` adds the start bound to ADD, RM, STATUS and LIST as well as SEND, REPLY and CANCEL. `RUNS` in the timing test holds only SEND, INBOX, REPLY and CANCEL, and the new `_with_start` check is parametrized only over `RUNS`. Nothing checks ADD, RM, STATUS or LIST against `MCP_CALL_DEADLINE_SECONDS` (180 s, `src/amoeba/mcp/in_process.py:30`) once the start term (`BUSY_TIMEOUT_SECONDS` 5 s × 6 = 30 s, `src/amoeba/store/store.py:28`) is added. The test docstring describes only send, reply and cancel, which matches the test but not the code. Model the worst case of the four missing operations and add them to the check, or show that their budget fits.

### [CONCERN] `start_after` does not keep its "never raises" promise, and the trigger is skipped when dispatch raises
category: error-handling-observability
location: src/amoeba/wiring_release.py#start_after

`start_after` is documented as never raising, but it calls `config()` and `deps()` before `start_ended_held`, which is the only part that catches. `invoke` in `src/amoeba/wiring.py` calls `start_after` only after `_dispatch` returns. So an operation that already committed a send, reply or cancel could report a config error if the config cannot be loaded at that point, which is unlikely. If `_dispatch` raises after committing a request's end, no start is attempted. `handle_pause` handles this with a `finally` that runs "on every path, a raise included", so the two triggers disagree. The next listed call recovers either case, but until then the held question stays held. Every such call also reads the config and rebuilds deps a second time, though `_dispatch` already built both. Run the trigger in a `finally` as `handle_pause` does, and keep the config and deps inside the guarded part.

### [NOTE] Both spellings of one marker count as two requests
category: correctness
location: src/amoeba/operations/request_link.py#find_request_link

For each marker, `find_request_link` keeps every candidate that resolves, both the id as written and the id without trailing dots. If both are requests this member sent (for example `v1.2.` and `v1.2`), one marker adds two ids and the function returns `BadLink` ("names 2 requests … waits on exactly one") instead of linking. `_candidates` lists the as-written id first, so the intended rule is to take the first candidate that resolves. This is unlikely to occur, and the fix is small.

### [NOTE] A held row whose request is a note is skipped silently
category: error-handling-observability
location: src/amoeba/operations/request_release.py#_due_rows

`effective_state` returns `None` for a note. `_due_rows` then treats the row as not due, with no log. `held_request_states` in status and `_evaluate` in `pause_held.py` both raise `StoreRowError` for the same state. `link_for` should prevent a held row from naming a note, so this is unlikely. It is still a silent fallback, which the project rules forbid. Raise `StoreRowError` here as the other two sites do.

### [NOTE] A failing start is retried indefinitely, with no terminal state of its own
category: error-handling-observability
location: src/amoeba/operations/request_release.py#start_ended_held

A held row whose child keeps failing is restarted every `answering_wait_seconds`, with no attempt count. The only exits are an explicit `dismiss` or the run's sweep, and `status` shows the failure as `last_call`. When the amoeba script is missing, rows are not marked attempted, so every listed call writes an error line for each due row, up to `MAX_STARTS_PER_CALL`. The design should state that `dismiss` bounds this, or add a cap that closes the row with a named reason.

### [NOTE] Test helpers use `Any` where concrete types already exist
category: type-contract-debt
location: tests/operations/test_handle_pause.py#_spawn_or_resume

`_spawn_or_resume(deps: Any, …) -> Any` and its inner `spawn(…, logs: Any) -> Any` drop the `Deps`, `LaunchLogs` and `WaitableChild | LaunchError` types, which exist in `amoeba.operations.deps`, `amoeba.upstream.squadron.launch` and `amoeba.operations.processes`. `poll_after_a_write(run_id: str) -> Any` in `tests/operations/test_pause_claim_held.py` does the same. Strict pyright accepts explicit `Any`, but these fakes can no longer catch a wrong argument, and test code is included in strict checking.

### [NOTE] Child-wait polling is duplicated across two test files, with different timeouts
category: architectural-decay
location: tests/cli/test_hold_release_cli.py#_wait_for_child

`_wait_for_child` here and `_child_finished` in `tests/operations/test_request_release_child.py` poll the same two places, the release log directory and the calls log. They use different timeouts (`CHILD_WAIT_SECONDS` 30 s and 60 s) and poll intervals (0.1 s and 0.2 s). Move one helper and one set of constants into a shared support module.
