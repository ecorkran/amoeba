---
docType: review
layer: project
reviewType: code
slice: waking
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/244-slice.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261117
dateUpdated: 20261117
reviewedSha: ed19572ae852121a338ae4033d1d3d356a4610df
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
diffTruncated: false
effort: xhigh
turns: 30
promptTokens: 2807089
cachedTokens: 2412119
cacheWriteTokens: 394946
completionTokens: 67652
durationSeconds: 310.5
costUsd: 0.740348
costBasis: provider
runId: run-20261117-p6-fdffa7db
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "A non-busy store error after the command starts leaves the command running past its deadline"
    location: "src/amoeba/operations/wake_run.py:72-84"
  - id: F002
    severity: concern
    category: correctness
    summary: "The Waking line asserts the wrapper is gone, which the row cannot show"
    location: "src/amoeba/cli/render/waking.py:53-68"
  - id: F003
    severity: note
    category: documentation-drift
    summary: "The wrapper-failure detail is not made in one place, as the docs claim"
    location: "src/amoeba/operations/wake.py#_start_wrapper"
  - id: F004
    severity: note
    category: error-handling-observability
    summary: "A failed \"already ended\" check is discarded"
    location: "src/amoeba/operations/wake_run.py#_finish"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "The daily window is written twice"
    location: "src/amoeba/cli/render/waking.py#_stopped_text"
  - id: F006
    severity: note
    category: test-debt
    summary: "The docs check exempts one env name by position"
    location: "tests/test_wake_docs.py:76"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "The same fake is written twice in the tests"
    location: "tests/cli/test_wake_run_cli.py#_RaisingChild"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "Long parameter lists, and noqa markers for a rule that is not selected"
    location: "src/amoeba/store/wakes.py#claim_wake"
  - id: F009
    severity: note
    category: performance-resource
    summary: "The spawned wrapper's handle is dropped in a long-lived process"
    location: "src/amoeba/operations/wake.py#_start_wrapper"
  - id: F010
    severity: pass
    category: performance-resource
    summary: "The wake step runs off the event loop"
    location: "src/amoeba/mcp/in_process.py:79"
  - id: F011
    severity: pass
    category: security-hygiene
    summary: "The woken command's environment is an allow-list"
    location: "src/amoeba/operations/wake_environment.py#build_wake_environment"
  - id: F012
    severity: pass
    category: security-hygiene
    summary: "Wake SQL builds from constants and binds values"
    location: "src/amoeba/store/sql_wakes.py"
  - id: F013
    severity: pass
    category: test-debt
    summary: "The load test runs in the default CI pytest run"
    location: ".github/workflows/ci.yml:40"
  - id: F014
    severity: pass
    category: correctness
    summary: "Removed members are refused as recipients"
    location: "src/amoeba/operations/message_member.py#resolve_recipient"
---

# Review: code — slice 244

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 29 successful tool call(s) of 29 made; 230961 of 230961 diff characters reached the model

## Findings

### [CONCERN] A non-busy store error after the command starts leaves the command running past its deadline

`run_wake` starts the command (line 73), then calls `_record_pid` (line 74). `_record_pid` catches only `StoreBusyError` (line 132). Every other `StoreError` subclass (`StorePermissionError`, `StoreCorruptError`, `StoreIntegrityError` and the rest in `store/errors.py`) propagates to `except (WakeRunError, StoreError): raise` (lines 83-84). That branch never calls `terminate_group`, unlike the generic branch at line 88. The wrapper then exits 3 with the row unended, and the command's process group keeps running until the command's own cap ends it. `docs/cli-contract.md` says a wake "ends one of four ways", and `timed_out` means "the command and its whole process group were stopped". This path breaks both statements. Fix: terminate the group in that branch, or stop treating a pid-write failure as fatal.

### [CONCERN] The Waking line asserts the wrapper is gone, which the row cannot show

`_running_text` prints "overdue since …: its wrapper is gone; the command's own cap ends it" whenever the row is past its deadline. `overdue` comes from the deadline alone (`sql_wakes.LIVE_WAKE`, and `wake_status.py` says "Nothing here looks at a process"). The claim is wrong in two cases:

- **Deadline passed, wrapper still alive.** At the deadline, `run_wake` calls `terminate_group`. That waits up to `TERMINATE_GRACE_SECONDS` (5 s, `processes.py:27-28`) before SIGKILL, and the row stays unended during that wait. `list` and `status` say the wrapper is gone, and `can_wake` already allows a second wake beside it.
- **Wrapper failed before any command started.** `_unended_row` (`wake_run.py:70`) runs outside the `try`. A `StoreBusyError` there exits 3 with the row unended and `command_pid` null. No command ran, but the line still says "the command's own cap ends it". Because the row is unended, `last_problem` does not show the failure either.

Fix: say "past its deadline and not yet recorded as ended", and drop the wrapper-gone and command-cap claims. Also record a start failure for the pre-start error path.

### [NOTE] The wrapper-failure detail is not made in one place, as the docs claim

`wake_environment.wake_detail`'s docstring, and `wake_run.py`'s module docstring, call it "the one place a detail text is made", and say an `OSError` never contributes its filename. `_start_wrapper` instead records `started.detail` verbatim. `processes.spawn_failure` (`processes.py:91-93`) builds that text as `f"{type(error).__name__}: {error}"`, filename included. `AmoebaScriptMissing`'s text is recorded as-is too. Nothing recorded is the woken command's text: the wrapper's argv is the script, `wake-run`, and the wake id. So this is a mismatch with the docs, not a leak today.

### [NOTE] A failed "already ended" check is discarded

`finish_wake` returns `False` when its compare-and-set finds the row already ended (`store/wakes.py`). `_finish` in `wake_run.py` and `_record_start_failure` in `wake.py` both ignore that result, so `run_wake` can return an outcome the row does not hold. No path can reach this today. Log it or raise it, so a future second writer shows up.

### [NOTE] The daily window is written twice

`DAY_HOURS = 24` restates `WAKE_WINDOW = timedelta(hours=24)` in `store/wakes.py`. Changing the window would change the limit but not the "in the last 24 h" text. Derive the text from `WAKE_WINDOW`.

### [NOTE] The docs check exempts one env name by position

`for name in WAKE_ENV_NAMES[:-1]` skips the last tuple entry, `AMOEBA_HOME`, by position. Any name appended later would be skipped silently. The docs say "the Amoeba home variable" and never name `AMOEBA_HOME`, which is why the slice exists. Name it in the docs and check every entry.

### [NOTE] The same fake is written twice in the tests

`_RaisingChild` duplicates `_RaisingWait` in `tests/operations/test_wake_run.py`. Move one shared fake into `tests/operations/wake_run_support.py`.

### [NOTE] Long parameter lists, and noqa markers for a rule that is not selected

`claim_wake` takes nine positional arguments, and `finish_wake` takes six. `_finish` in `wake_run.py` carries `# noqa: PLR0913`, but `pyproject.toml:49` selects only `E, F, W, I, UP, BLE, ASYNC, B`, so those markers do nothing. Group the claim's fields, and the end-of-wake fields, into dataclasses.

### [NOTE] The spawned wrapper's handle is dropped in a long-lived process

`_start_wrapper` discards the child that `deps.spawn` returns. Under the MCP server, which lives across calls, nothing in this code waits on the exited wrapper. CPython reaps such children only on a later `Popen`. The count is bounded by wakes per member per day, so this is a NOTE.

### [PASS] The wake step runs off the event loop

The in-process tool runs its operation through `anyio.to_thread.run_sync`, so the synchronous store transactions and the spawn in `send`'s wake step do not block the loop.

### [PASS] The woken command's environment is an allow-list

`build_wake_environment` copies only the names in `WAKE_ENV_NAMES`. `tests/operations/test_wake_run.py` sets a sender-only variable and an AWS-style key and asserts that neither reaches the command.

### [PASS] Wake SQL builds from constants and binds values

Every f-string interpolates a module constant (`_WAKE_COLUMNS`, `LIVE_WAKE`), and every value is bound with `?`. This meets the repo's SQL rule for Amoeba.

### [PASS] The load test runs in the default CI pytest run

`uv run pytest` runs `tests/load/test_wake_claim_load.py`, because `pyproject.toml:64` ignores only `tests/live`. The concurrent-claim load test therefore gates merges.

### [PASS] Removed members are refused as recipients

`resolve_recipient` reads through `get_member`, whose SQL includes `ACTIVE_MEMBER` (`store/sql.py:98-101`). A removed member is refused as `UNKNOWN_RECIPIENT`, so no wake starts for it.

### Run Digest

- Response length: 10551 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 30
- Tokens — prompt / cached / cache write / completion / reasoning: 2807089 / 2412119 / 394946 / 67652 / not computed
- Duration: 310.5 s
- Cost: $0.74 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
