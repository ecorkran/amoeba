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
reviewedSha: 8131471449d42c8199fd7b8d3e63fd36c3a99196
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
diffTruncated: false
effort: xhigh
turns: 33
promptTokens: 1868724
cachedTokens: 1488464
cacheWriteTokens: 380244
completionTokens: 83173
durationSeconds: 352.6
costUsd: 0.713363
costBasis: provider
runId: run-20261116-p6-d040de42
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "`live_member_ids` is unused production code reserved for slice 244"
    location: "src/amoeba/store/sessions.py:85"
  - id: F002
    severity: concern
    category: correctness
    summary: "Live harness decodes each PTY read on its own"
    location: "tests/live/channels/harness.py:158"
  - id: F003
    severity: note
    category: architectural-decay
    summary: "`SessionTiming` copies the three config keys"
    location: "src/amoeba/mcp/presence.py:42"
  - id: F004
    severity: note
    category: error-handling-observability
    summary: "A failed member lookup is logged twice, each with a traceback"
    location: "src/amoeba/mcp/presence.py:111"
  - id: F005
    severity: note
    category: test-debt
    summary: "The exit-delete timeout branch has no test"
    location: "src/amoeba/mcp/presence_task.py:75"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "Test helpers repeat the same polling and listing code"
    location: "tests/live/channels/world.py:132"
  - id: F007
    severity: note
    category: security-hygiene
    summary: "Enum value is f-string-interpolated into push SQL"
    location: "src/amoeba/store/sql_messages.py:111"
  - id: F008
    severity: note
    category: dependency-config-debt
    summary: "The pinned loop depends on private SDK modules"
    location: "src/amoeba/mcp/pinned_loop.py#serve_pinned"
  - id: F009
    severity: note
    category: dependency-config-debt
    summary: "Three config keys are now required with no default"
    location: "src/amoeba/config/user_config.py#UserConfig"
  - id: F010
    severity: pass
    category: error-handling-observability
    summary: "Exception handlers follow the rules"
    location: "src/amoeba/mcp/presence_task.py:85"
  - id: F011
    severity: pass
    category: performance-resource
    summary: "Blocking store and `cf` work stays off the event loop"
    location: "src/amoeba/mcp/inbox_watcher.py#watch_inbox"
  - id: F012
    severity: pass
    category: correctness
    summary: "The migration early return is correct and its comment is accurate"
    location: "src/amoeba/store/migrations.py:133"
  - id: F013
    severity: pass
    category: correctness
    summary: "Status and list keying matches the members dict"
    location: "src/amoeba/operations/status.py:197"
---

# Review: code — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 32 successful tool call(s) of 32 made; 214586 of 214586 diff characters reached the model

## Findings

### [CONCERN] `live_member_ids` is unused production code reserved for slice 244

`live_member_ids` has no caller under `src/`. Its docstring says it is "the liveness rule 244 wakes by". Its only callers are `tests/store/test_sessions.py` and `tests/operations/test_status_sessions.py`, which check it against the status view. It also brings `SELECT_LIVE_MEMBER_IDS` into `src/amoeba/store/sql_sessions.py:37`, and that query is the only user of `PUSH_CONFIRMED` (`sql_sessions.py:16`). This builds a later slice's consumer now. The no-deferral rule (AGENTS.md, Amoeba Design Rules) and the "resist adding complexity" rule both point to deleting it with its SQL and tests, or adding the slice 241 caller that needs it.

### [CONCERN] Live harness decodes each PTY read on its own

`ClaudeSession._read` calls `data.decode("utf-8", "replace")` on each `os.read` chunk. A multi-byte character split across two reads becomes U+FFFD on both sides. The menu pointer `❯` and the `…` glyph are both three bytes, so either can be split. The screen text then never contains them. `choose` presses arrow keys until `MENU_MAX_MOVES` and fails, and `wait_for` times out with "not on the screen". Whether this happens depends on how the PTY chunks output, so the channels tier can fail intermittently with no clear cause. Fix: hold a `codecs.getincrementaldecoder("utf-8")(errors="replace")` on the reader and decode through it.

### [NOTE] `SessionTiming` copies the three config keys

`SessionTiming` repeats `notify_poll_seconds`, `session_heartbeat_seconds` and `session_stale_seconds` from `UserConfig`. `_presence_deps` in `src/amoeba/mcp/server.py:243` copies them across field by field. Changing one key means three edits. Passing a narrowed view of `UserConfig` into `PresenceDeps` would keep one source.

### [NOTE] A failed member lookup is logged twice, each with a traceback

`resolve_presence` logs `no presence: the member lookup failed` with `logger.exception` and re-raises. `run_presence` (`src/amoeba/mcp/presence_task.py:90`) logs the same exception again as `presence stopped`. Each failed `cf` call writes two ERROR tracebacks. Both handlers meet the exception-handling rule individually. Keep the log at one layer.

### [NOTE] The exit-delete timeout branch has no test

`_delete_row` bounds the exit delete with `move_on_after` and warns when the bound fires (lines 75 to 78). The test `test_a_failed_delete_leaves_a_row_that_stops_counting_after_the_limit` only reaches the `StoreError` branch, because its opener fails at once instead of blocking. Nothing checks that the bound fires or that the warning is logged. `Opener(block=...)` in `tests/mcp_server/presence_rig.py` can make the open block, which would cover it.

### [NOTE] Test helpers repeat the same polling and listing code

`sessions_of` (line 132) and `all_sessions` (line 145) each run `amoeba list -j` and walk programs, members and sessions. Five deadline loops do the same job: `wait_until` (world.py:157), `wait_for_log` (world.py:115), `ClaudeSession.wait_for` (`tests/live/channels/harness.py#ClaudeSession`), `_wait_until` (`tests/mcp_server/test_presence_stdio.py:70`) and `eventually` (`tests/mcp_server/presence_rig.py:170`). CLAUDE.md says not to duplicate logic. One sync waiter, one async waiter and one listing walk would cover them.

### [NOTE] Enum value is f-string-interpolated into push SQL

`SELECT_PUSH_ROWS_AFTER` puts `MessageKind.NOTE.value` into the SQL with an f-string. The value is a constant, so this is not an injection path. The query already binds `?` parameters and the SQL rule says never to f-string SQL, so the kind can be a bound value too.

### [NOTE] The pinned loop depends on private SDK modules

`serve_pinned` imports `serve_connection` from `mcp.server.runner` and `JSONRPCDispatcher` from `mcp.shared.jsonrpc_dispatcher`. Neither is public SDK API. `pyproject.toml` declares `mcp>=2.3,<3`. The protocol-pin tests would catch a behavior change. A 2.x release that moves these modules would still break `amoeba-mcp` at import. Confirm the lock pins the SDK and record the dependency on internals.

### [NOTE] Three config keys are now required with no default

`notify_poll_seconds`, `session_heartbeat_seconds` and `session_stale_seconds` have no defaults. Any existing `config.yaml` without them fails every command that loads the config until the keys are added. The error names the missing key, which the tests check, so the failure is explicit as the rules require. The diff contains no upgrade note. Confirm the CHANGELOG or config contract tells existing users to add them.

### [PASS] Exception handlers follow the rules

Each new handler takes one of the allowed forms. `run_presence` is the top-level process boundary and logs with `logger.exception`. `resolve_presence` (`presence.py:110`) logs and re-raises. `read_resource` (`inbox_resource.py:78`) logs and re-raises as `MCPError`. The busy-store handlers in `inbox_watcher.py:52` and `:116` and in `presence.py` catch only `StoreBusyError`, with a comment. `harness.py:153` catches `OSError` with a comment.

### [PASS] Blocking store and `cf` work stays off the event loop

Every store and `cf` call in the watcher, the heartbeat, the presence lookup and `read_resource` runs through `anyio.to_thread.run_sync`, which I checked by reading those files. The loop-side code (`channel_event`, the `note_*` functions, `client_name`) is pure and far under 1 ms. `PresenceState` is touched only on the loop, and workers receive immutable `Session` values and an opener, as the module docstring says.

### [PASS] The migration early return is correct and its comment is accurate

The unlocked stamp read returns early only when the stamp equals `EXPECTED_SCHEMA_VERSION`. The lock path re-reads the version inside `_apply_pending` (line 101) after `BEGIN IMMEDIATE`, as the comment at lines 131 to 132 says.

### [PASS] Status and list keying matches the members dict

`members` is a `dict[str, Member]` (line 158). `read_member_sessions` takes its `Iterable[str]` and calls `set(...)`, which yields the project-id keys, so the filter matches and `sessions[member.project_id]` cannot miss. The `Iterable[str]` annotation hides that a dict is passed, but the behavior is correct.

### Run Digest

- Response length: 9043 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1868724 / 1488464 / 380244 / 83173 / not computed
- Duration: 352.6 s
- Cost: $0.71 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
