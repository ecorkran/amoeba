---
docType: review
layer: project
reviewType: code
slice: push-and-presence
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/241-slice.push-and-presence.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 93787d5915f57038691a89b8fa8f84b3f21328cd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
diffTruncated: false
effort: xhigh
turns: 20
promptTokens: 1842705
cachedTokens: 1512030
cacheWriteTokens: 330657
completionTokens: 53038
durationSeconds: 232.8
costUsd: 0.58931
costBasis: provider
runId: run-20261116-p6-d040de42
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "Presence lookup re-raises without logging at its own handler"
    location: "src/amoeba/mcp/presence.py:110"
  - id: F002
    severity: concern
    category: test-debt
    summary: "Load test checks final session state, not the heartbeat-gap claim"
    location: "tests/load/test_presence_load.py:194"
  - id: F003
    severity: concern
    category: test-debt
    summary: "Live test asserts the exit delete with no wait"
    location: "tests/live/channels/test_channels_live.py:102"
  - id: F004
    severity: note
    category: performance-resource
    summary: "Every watcher tick opens a new store connection"
    location: "src/amoeba/mcp/inbox_watcher.py:60"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "An assert guards a production invariant"
    location: "src/amoeba/mcp/presence.py:135"
  - id: F006
    severity: note
    category: security-hygiene
    summary: "SQL composed with f-strings from constants"
    location: "src/amoeba/store/sql_messages.py:111"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Pinned loop reimplements the SDK serve loop on SDK internals"
    location: "src/amoeba/mcp/pinned_loop.py#serve_pinned"
  - id: F008
    severity: pass
    category: correctness
    summary: "Migration fast path re-checks the stamp under the writer lock"
    location: "src/amoeba/store/migrations.py:133"
  - id: F009
    severity: pass
    category: correctness
    summary: "Timestamp text sorts correctly for the stale comparisons"
    location: "src/amoeba/store/row_values.py:118"
  - id: F010
    severity: pass
    category: correctness
    summary: "Watcher's closed-stream handling matches the SDK"
    location: "src/amoeba/mcp/inbox_watcher.py#_announce"
---

# Review: code — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 18 successful tool call(s) of 19 made; 213075 of 213075 diff characters reached the model

## Findings

### [CONCERN] Presence lookup re-raises without logging at its own handler

`resolve_presence` catches `Exception` around the member lookup, sets `off_reason`, and re-raises. The project rule for a re-raising `try/except` is to log at ERROR with `logger.exception` at that site. This one defers logging to `run_presence`'s handler (`presence_task.py:87`), per its comment. That handler does log with a traceback, so the server loses nothing. But `resolve_presence` is a public coroutine with its own `Raises:` docstring, and any caller outside `run_presence` gets no log. Add `logger.exception` here, or state the deferral in the docstring.

### [CONCERN] Load test checks final session state, not the heartbeat-gap claim

The docstring and the comment at line 194 say the test proves no heartbeat gap reached `session_stale_seconds`. The only session check is a snapshot taken after the client loop. `heartbeat` re-creates a pruned row with its original `started_at`, so a row that went stale mid-run and was re-created by the next beat is fresh at the snapshot. The assertion passes even with gaps. To test the claim, record each server's beat times during the run and assert the largest gap is below `TIMING.session_stale_seconds`. The load-test rule requires asserting a resource bound, and this test does not check the bound it names.

### [CONCERN] Live test asserts the exit delete with no wait

After `session.terminate()` returns, the test immediately asserts `sessions_of(...) == []`. The server deletes its row after its stdin closes, and nothing waits for that. Until the delete lands, the row is fresh (heartbeat 1s, stale 3s), so the assertion can fail on a race that looks like a delete bug. The other waits in this file use `wait_until`. Wrap this check in `wait_until` with `STALE_WAIT` as the bound, so it accepts either a delete or staleness. I did not run the live tier (it needs `claude`, a login, and `AMOEBA_LIVE_CHANNEL_MODEL`), so this comes from reading the code.

### [NOTE] Every watcher tick opens a new store connection

`_new_rows` calls `read_high_seq` on every tick, and each call runs `open_store()`: a new sqlite connection, the WAL and foreign-key pragmas, and the migration stamp check, then one indexed read (`wiring_presence.py`). A rise adds a second open for the rows. The docstring's "one indexed read every `notify_poll_seconds`" understates the cost. The work runs in worker threads, so the loop is not blocked. The number to watch is the per-tick open at the load test's 0.02s poll. Measure at the production interval before deciding whether to hold one connection per watcher.

### [NOTE] An assert guards a production invariant

`_session` checks `member_id` and `directory` with `assert`, which `python -O` strips. A `None` would then reach the NOT NULL columns, and the insert would raise a `StoreError` that presence's top-level handler logs. The failure stays loud, but the message no longer names the real cause. Replace the assert with an explicit `ValueError`.

### [NOTE] SQL composed with f-strings from constants

`SELECT_PUSH_ROWS_AFTER` interpolates `MessageKind.NOTE.value`, and `sql_sessions.py:32-38` interpolate module constants. None of these values come from input, so there is no injection path. The project rule says never to use f-string SQL, but `sql.py` composes SQL the same way throughout, so this matches the codebase. Raise it with the rule's owner. No change is needed in this slice.

### [NOTE] Pinned loop reimplements the SDK serve loop on SDK internals

`serve_pinned` builds its own `JSONRPCDispatcher` and `Connection.for_loop`, and calls `mcp.server.runner.serve_connection`. These are SDK internals. The duplication is deliberate, and `tests/mcp_server/test_protocol_pin.py` guards the wire behavior of both loops. An SDK bump that changes these signatures would break at runtime rather than at review. I did not diff `serve_pinned` against the installed `serve_loop`, so the pin test is the only evidence that they still match.

### [PASS] Migration fast path re-checks the stamp under the writer lock

`migrate` reads the stamp without a lock and returns early only when it equals `EXPECTED_SCHEMA_VERSION`. Otherwise it takes `BEGIN IMMEDIATE`, and `_apply_pending` reads the version again under that lock before applying anything. Two processes racing on an old store cannot both apply migration 007. I read the slow path through its rollback and found no gap.

### [PASS] Timestamp text sorts correctly for the stale comparisons

`encode_timestamp` always emits UTC `isoformat()`. Whole-second values have no fraction, and fractional values have six digits. In text comparison `+` sorts before `.` and digits, so a whole second sorts before its fractional values, and ordering across seconds holds. The `heartbeat_at > ?` checks in `sql_sessions.py` are therefore sound.

### [PASS] Watcher's closed-stream handling matches the SDK

`Connection.notify` in the installed SDK (`.venv/.../mcp/server/connection.py:401-410`) catches only `BrokenResourceError` and `ClosedResourceError`, and lets other errors propagate. The watcher's docstring says the same: it raises whatever `notify` raises beyond a closed stream. The test `test_a_notify_on_a_closed_stream_is_dropped_not_raised` exercises that contract.

### Run Digest

- Response length: 7739 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1842705 / 1512030 / 330657 / 53038 / not computed
- Duration: 232.8 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
