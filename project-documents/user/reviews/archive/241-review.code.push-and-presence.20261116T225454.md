---
docType: review
layer: project
reviewType: code
slice: push-and-presence
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/241-slice.push-and-presence.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 7454e26277210ad9bcf33730600b80e39ae37ac5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
diffTruncated: false
effort: xhigh
turns: 20
promptTokens: 2173524
cachedTokens: 1809280
cacheWriteTokens: 364224
completionTokens: 63181
durationSeconds: 280.9
costUsd: 0.622542
costBasis: provider
runId: run-20261116-p6-d040de42
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Push poll can announce the same delivery twice"
    location: "src/amoeba/mcp/inbox_watcher.py:59-69"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Every store open takes the writer lock, including the new read-only polls"
    location: "src/amoeba/store/migrations.py:132"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "A store failure on the inbox resource leaves no server-side log"
    location: "src/amoeba/mcp/inbox_resource.py:75-79"
  - id: F004
    severity: concern
    category: correctness
    summary: "Push confirmation does not show that the event reached the agent"
    location: "src/amoeba/mcp/presence.py#note_inbox_called"
  - id: F005
    severity: concern
    category: error-handling-observability
    summary: "A transient lookup failure disables push for the session, and nothing shows it"
    location: "src/amoeba/mcp/presence.py#resolve_presence"
  - id: F006
    severity: note
    category: error-handling-observability
    summary: "Cancellation during the lookup also writes the off-reason"
    location: "src/amoeba/mcp/presence.py:109-112"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Test helpers are copied across files"
    location: "tests/mcp_server/test_presence.py"
  - id: F008
    severity: note
    category: type-contract-debt
    summary: "SDK stream types are `Any`, and the pinned loop imports SDK internals"
    location: "src/amoeba/mcp/pinned_loop.py#serve_pinned"
  - id: F009
    severity: note
    category: test-debt
    summary: "The note branch is tested only with hand-built rows"
    location: "tests/mcp_server/test_inbox_watcher.py#test_a_note_pushes_naming_its_kind_and_sender"
  - id: F010
    severity: note
    category: consistency-rot
    summary: "`presence.py` holds five classes"
    location: "src/amoeba/mcp/presence.py"
---

# Review: code — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 18 successful tool call(s) of 19 made; 208253 of 208253 diff characters reached the model

## Findings

### [CONCERN] Push poll can announce the same delivery twice

`_new_rows` reads the high seq in one transaction (line 63) and the rows above `last_seen` in a second (lines 66-68). `push_rows_after` has no upper bound, so a delivery committed between the two reads is returned. `watch_inbox` then sets `last_seen = max(last_seen, high)` (line 117), which keeps the older value. The next tick reads that delivery again and sends a second channel event for it. No mail is lost, but the same seq is announced twice. Set the floor from the rows: `last_seen = rows[-1].seq if rows else high`. The module docstring also says "One indexed read", but a rise does two reads.

### [CONCERN] Every store open takes the writer lock, including the new read-only polls

`Store.open` calls `migrate` (store.py:105), and `migrate` runs `BEGIN IMMEDIATE` (migrations.py:132) on every call, even when no migration is pending. The watcher, the heartbeat and `read_as_of_seq` each open a fresh store per tick, so each tick takes the writer lock before it reads. That contends with `send`, `answer` and the other servers' heartbeats. A poller that waits past the 5 s busy timeout gets `StoreBusyError`, which becomes `BusyWarning` noise and skipped ticks. This migration code predates the slice, but the slice makes it a hot path. Read the version first and take `BEGIN IMMEDIATE` only when it is below `EXPECTED_SCHEMA_VERSION`. The load test (`tests/load/test_presence_load.py`) runs 12 presences at 20 ms polls, but it asserts only latency and heartbeat gaps, so it does not measure this lock cost.

### [CONCERN] A store failure on the inbox resource leaves no server-side log

`read_resource` catches `StoreError`, re-raises it as `MCPError`, and logs nothing. The project rule for a re-raising `try/except` is to log at ERROR with `logger.exception` first. The comment justifies the client-facing error, not the missing log. A failure here reaches the client and nowhere else. Add `logger.exception(...)` before the raise.

### [CONCERN] Push confirmation does not show that the event reached the agent

`call_tool` calls `presence.inbox_called()` after every successful `inbox` call (server.py:165-166), without looking at the arguments or results. `note_inbox_called` then sets `push_confirmed_at` if any attempt was recorded in the last 300 s. Its docstring says the call "answers a recent attempt", but nothing ties the call to the event. An agent that calls `inbox` for its own reasons inside that window confirms push even if the notification never reached it. Confirmation is sticky. `live_member_ids` (store/sessions.py) makes a confirmed session the liveness rule that slice 244 wakes by, so the false positive reaches the wake decision. Confirm only on a signal the event itself produces, if the client exposes one. Otherwise document that the flag means "an inbox call followed an attempt", and do not present it as proof of delivery.

### [CONCERN] A transient lookup failure disables push for the session, and nothing shows it

`resolve_presence` runs once. If `cf` fails or times out, `off_reason` is set and the task ends. The one ERROR line is logged by the handler at presence_task.py:87-90. The member gets no session row and no push until the agent session restarts. `list` shows no session for the member, the same as a member whose agent is not running, so the PM cannot tell that push is off. If one-shot resolution is intended, the design should say so and `status` should show the unresolved state. Otherwise a retry with a stated limit fits the "every limit says what happens" rule.

### [NOTE] Cancellation during the lookup also writes the off-reason

`resolve_presence` catches `BaseException` to set `off_reason` and `resolved`, then re-raises. The re-raise is correct, but a client disconnect during the lookup also records "the member lookup failed". Move `resolved.set()` into a `finally`, and set the reason only in an `except Exception` branch.

### [NOTE] Test helpers are copied across files

`_timed_out` is defined here and again in `test_presence_task.py`. `_deliver` is written three times (`test_inbox_resource.py`, `test_inbox_watcher.py`, `test_presence_serving.py`). `store_path` is re-declared in five files around the same `seed_member` call. In `tests/user_configs.py`, `_example_number` duplicates `_example_integer` beside it. The presence rig already holds shared helpers, and these belong there. The project rule against duplicated logic applies to tests.

### [NOTE] SDK stream types are `Any`, and the pinned loop imports SDK internals

`serve_pinned` takes `streams: tuple[Any, Any]` and `lifespan_state: Any`. It also imports `mcp.server.runner.serve_connection`, `mcp.shared.jsonrpc_dispatcher` and `mcp.shared.transport_context`. The docstring explains why the streams are untyped, and the protocol pin test catches behavior drift. `pyproject.toml` bounds `mcp` to `>=2.3,<3`, not an exact pin, so a 2.x minor bump can move these internals without a type error. Keep the pin test in CI, and note the range in the design.

### [NOTE] The note branch is tested only with hand-built rows

The test inserts the note with raw SQL because the note writer is slice 243. The note branch of `SELECT_PUSH_ROWS_AFTER` and the "note, sent from" wording are checked only against that hand-written row shape. When 243 adds the writer, its own path should replace this helper so the test checks the real shape.

### [NOTE] `presence.py` holds five classes

The Python rules say one class per file for models and services. `presence.py` holds `SessionTiming`, `PresenceDeps`, `PresenceState`, `BusyWarning` and `ToolPresence`. The store and status modules already group classes, so this may be the repo's accepted practice. The PM should decide which convention governs.

### Run Digest

- Response length: 9782 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2173524 / 1809280 / 364224 / 63181 / not computed
- Duration: 280.9 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

### Raw Response

I'll confirm the repo state, then read the changed files before forming findings.
Bash is disabled in this session, so I can't run `git diff` or the test suite. I'll review from the diff in the prompt and the working-tree files, and I'll say so in the report. Starting with the files where the diff's behavior depends on code outside the hunks.
The Python rules reminder matches the project rules I already have, so nothing changes. Next I'll check the schema index that `member_high_seq` depends on, the `models.py` imports, and the render helpers.
The deliveries index `deliveries_member_seq (member_id, seq)` exists, so the docstring's "indexed read" claim holds. `StoreBusyError` subclasses `StoreError`. Next I'll check the store open path, the `wiring` names `server.py` uses, and the live-tier collection behavior.
Two things settled: `addopts = ["--ignore=tests/live"]` keeps the channels tier out of bare `pytest` runs, and the live tiers all read their variables at collection, so that pattern is consistent. Now I'll read the watcher and the store helpers that the race and N+1 findings depend on, so I can cite exact lines.
Confirmed: `_new_rows` reads `high` (line 63) and then the rows in a separate transaction (lines 66-68), and returns `high` as the new floor. I'll get exact line numbers for the remaining citations.
The race, the N+1 lookup, and the exception handlers are confirmed at the lines I'll cite. One more check before I write up: every worker call calls `Store.open`, so I need to know whether `migrate()` takes a write lock on each open. If it does, the polling load lands on the writer lock.
`migrate()` runs `BEGIN IMMEDIATE` unconditionally (migrations.py:132), and `Store.open` calls it on every open (store.py:105). So every watcher and heartbeat tick takes the writer lock before it reads. That's a finding. One last check: whether the `mcp` SDK is pinned, since `pinned_loop.py` imports its internals.
## Summary

**Verdict: CONCERNS.** Five concerns, all in the new push and presence path or the store open it depends on. None is a FAIL.

**Limits of this review:** Bash is disabled in this session, so I could not run `git diff`, ruff, pyright or pytest. I reviewed the diff text, read the working-tree files behind each finding, and read the store and wiring code the new code calls. I did not check the installed `mcp` SDK's behavior, such as whether `Connection.notify` swallows closed-stream errors. The tests assert that, and I took them at their word.

**Checked and clean:**
- The `deliveries_member_seq (member_id, seq)` index backs the high-seq read, so the docstring's "indexed read" holds.
- The stale rule is defined once (`sql_sessions.LIVE_SESSION`) and used by prune, live reads and live member ids.
- `status` keys sessions by project id correctly, because `members` is a dict and `set(...)` yields its keys.
- `server.py` is under 300 lines.
- The channels live tier is excluded from bare runs by `addopts = ["--ignore=tests/live"]`. It reads its variables at collection, like the other live tiers.
- Live subprocesses get a named-variable allowlist (`tests/live_environment.py`), not the full environment.

### [CONCERN] Push poll can announce the same delivery twice
category: correctness
location: src/amoeba/mcp/inbox_watcher.py:59-69

`_new_rows` reads the high seq in one transaction (line 63) and the rows above `last_seen` in a second (lines 66-68). `push_rows_after` has no upper bound, so a delivery committed between the two reads is returned. `watch_inbox` then sets `last_seen = max(last_seen, high)` (line 117), which keeps the older value. The next tick reads that delivery again and sends a second channel event for it. No mail is lost, but the same seq is announced twice. Set the floor from the rows: `last_seen = rows[-1].seq if rows else high`. The module docstring also says "One indexed read", but a rise does two reads.

### [CONCERN] Every store open takes the writer lock, including the new read-only polls
category: performance-resource
location: src/amoeba/store/migrations.py:132

`Store.open` calls `migrate` (store.py:105), and `migrate` runs `BEGIN IMMEDIATE` (migrations.py:132) on every call, even when no migration is pending. The watcher, the heartbeat and `read_as_of_seq` each open a fresh store per tick, so each tick takes the writer lock before it reads. That contends with `send`, `answer` and the other servers' heartbeats. A poller that waits past the 5 s busy timeout gets `StoreBusyError`, which becomes `BusyWarning` noise and skipped ticks. This migration code predates the slice, but the slice makes it a hot path. Read the version first and take `BEGIN IMMEDIATE` only when it is below `EXPECTED_SCHEMA_VERSION`. The load test (`tests/load/test_presence_load.py`) runs 12 presences at 20 ms polls, but it asserts only latency and heartbeat gaps, so it does not measure this lock cost.

### [CONCERN] A store failure on the inbox resource leaves no server-side log
category: error-handling-observability
location: src/amoeba/mcp/inbox_resource.py:75-79

`read_resource` catches `StoreError`, re-raises it as `MCPError`, and logs nothing. The project rule for a re-raising `try/except` is to log at ERROR with `logger.exception` first. The comment justifies the client-facing error, not the missing log. A failure here reaches the client and nowhere else. Add `logger.exception(...)` before the raise.

### [CONCERN] Push confirmation does not show that the event reached the agent
category: correctness
location: src/amoeba/mcp/presence.py#note_inbox_called

`call_tool` calls `presence.inbox_called()` after every successful `inbox` call (server.py:165-166), without looking at the arguments or results. `note_inbox_called` then sets `push_confirmed_at` if any attempt was recorded in the last 300 s. Its docstring says the call "answers a recent attempt", but nothing ties the call to the event. An agent that calls `inbox` for its own reasons inside that window confirms push even if the notification never reached it. Confirmation is sticky. `live_member_ids` (store/sessions.py) makes a confirmed session the liveness rule that slice 244 wakes by, so the false positive reaches the wake decision. Confirm only on a signal the event itself produces, if the client exposes one. Otherwise document that the flag means "an inbox call followed an attempt", and do not present it as proof of delivery.

### [CONCERN] A transient lookup failure disables push for the session, and nothing shows it
category: error-handling-observability
location: src/amoeba/mcp/presence.py#resolve_presence

`resolve_presence` runs once. If `cf` fails or times out, `off_reason` is set and the task ends. The one ERROR line is logged by the handler at presence_task.py:87-90. The member gets no session row and no push until the agent session restarts. `list` shows no session for the member, the same as a member whose agent is not running, so the PM cannot tell that push is off. If one-shot resolution is intended, the design should say so and `status` should show the unresolved state. Otherwise a retry with a stated limit fits the "every limit says what happens" rule.

### [NOTE] Cancellation during the lookup also writes the off-reason
category: error-handling-observability
location: src/amoeba/mcp/presence.py:109-112

`resolve_presence` catches `BaseException` to set `off_reason` and `resolved`, then re-raises. The re-raise is correct, but a client disconnect during the lookup also records "the member lookup failed". Move `resolved.set()` into a `finally`, and set the reason only in an `except Exception` branch.

### [NOTE] Test helpers are copied across files
category: architectural-decay
location: tests/mcp_server/test_presence.py

`_timed_out` is defined here and again in `test_presence_task.py`. `_deliver` is written three times (`test_inbox_resource.py`, `test_inbox_watcher.py`, `test_presence_serving.py`). `store_path` is re-declared in five files around the same `seed_member` call. In `tests/user_configs.py`, `_example_number` duplicates `_example_integer` beside it. The presence rig already holds shared helpers, and these belong there. The project rule against duplicated logic applies to tests.

### [NOTE] SDK stream types are `Any`, and the pinned loop imports SDK internals
category: type-contract-debt
location: src/amoeba/mcp/pinned_loop.py#serve_pinned

`serve_pinned` takes `streams: tuple[Any, Any]` and `lifespan_state: Any`. It also imports `mcp.server.runner.serve_connection`, `mcp.shared.jsonrpc_dispatcher` and `mcp.shared.transport_context`. The docstring explains why the streams are untyped, and the protocol pin test catches behavior drift. `pyproject.toml` bounds `mcp` to `>=2.3,<3`, not an exact pin, so a 2.x minor bump can move these internals without a type error. Keep the pin test in CI, and note the range in the design.

### [NOTE] The note branch is tested only with hand-built rows
category: test-debt
location: tests/mcp_server/test_inbox_watcher.py#test_a_note_pushes_naming_its_kind_and_sender

The test inserts the note with raw SQL because the note writer is slice 243. The note branch of `SELECT_PUSH_ROWS_AFTER` and the "note, sent from" wording are checked only against that hand-written row shape. When 243 adds the writer, its own path should replace this helper so the test checks the real shape.

### [NOTE] `presence.py` holds five classes
category: consistency-rot
location: src/amoeba/mcp/presence.py

The Python rules say one class per file for models and services. `presence.py` holds `SessionTiming`, `PresenceDeps`, `PresenceState`, `BusyWarning` and `ToolPresence`. The store and status modules already group classes, so this may be the repo's accepted practice. The PM should decide which convention governs.
