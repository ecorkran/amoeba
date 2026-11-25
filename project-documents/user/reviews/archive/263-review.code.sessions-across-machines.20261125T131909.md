---
docType: review
layer: project
reviewType: code
slice: sessions-across-machines
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/263-slice.sessions-across-machines.md
aiModel: haiku-line-pass
aiRecipe: true
recipeComplete: true
status: complete
dateCreated: 20261125
dateUpdated: 20261125
reviewedSha: 23bd0e2ee17b4bcc50758ccec4d2c7aa65560e3e
reviewedBlob: 49416963b3c086fc927854f8897a3c5b896c67db
reviewedBlobCurrent: true
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "src/amoeba/mcp/tick.py"
  - "src/amoeba/mcp/presence_task.py"
  - "src/amoeba/wiring_steps.py"
  - "src/amoeba/operations/steps/model_base.py"
  - "src/amoeba/wire/times.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/hub/call_sessions.py"
  - "src/amoeba/mcp/in_process.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/operations/steps/models_session.py"
searches:
  - "list_files src/amoeba/iring_presence.py in ."
  - "grep class (HubCertificateError|HubUnreachableError|HubRefusedError|ClientFileError)\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba/client"
  - "grep WRITING_STEPS|WRITING_CALLS|def _writes in /Users/manta/source/repos/manta/amoeba/src"
  - "grep DOOR_VERSION\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def call_result|SERVED\\[|served_edges|class ServedEdges|local:|door_version in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep tool_timeout_sec|machine_runs|session_stale_seconds:|notify_poll_seconds:|session_heartbeat_seconds: in /Users/manta/source/repos/manta/amoeba"
  - "grep STORE_CONTRACT\\s*=|STORE_CONTRACT: in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep machine_runs|sessions.*door_version|door_version|client_version in /Users/manta/source/repos/manta/amoeba/docs"
  - "grep tool_timeout_sec|tool_timeout in /Users/manta/source/repos/manta/amoeba"
  - "grep client_version|program_version|the version of the program in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/263-slice.sessions-across-machines.md"
  - "grep program_version\\(\\)|client_version= in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def load_config|def check_deadline|def joined in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/calls.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring_steps.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring.py"
  - "grep ^from typing import|^from __future__|import Any in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep HANDLE_PAUSE in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring.py"
  - "grep iring_presence|Only event-loop tasks touch in /Users/manta/source/repos/manta/amoeba"
  - "grep def _ticked|therow_of|norow_of|thirdrun|nextrun|SESSION_DIRECTORY_MAX_LENGTH|isprintable in /Users/manta/source/repos/manta/amoeba"
turns: 32
promptTokens: 4113731
cachedTokens: 3514894
cacheWriteTokens: 598811
completionTokens: 78701
durationSeconds: 352.7
costUsd: 1.211764
runId: run-20261125-p6-fbf201a3
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Accepted session ticks record the hub's program version as the session's client version"
    location: "src/amoeba/operations/steps/session.py:77"
  - id: F002
    severity: concern
    category: correctness
    summary: "The tick reads presence state from its worker thread"
    location: "src/amoeba/mcp/tick.py:167-172"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "The exit path's error set omits `HubCertificateError`"
    location: "src/amoeba/mcp/presence_task.py:75-81"
  - id: F004
    severity: concern
    category: type-contract-debt
    summary: "The normal tick accepts any client and directory string, while the header path rejects bad ones"
    location: "src/amoeba/operations/steps/models_session.py#SessionTickRequest"
  - id: F005
    severity: concern
    category: consistency-rot
    summary: "The injected door version reaches the session steps but not the served operations or status"
    location: "src/amoeba/operations/send_write.py:107"
  - id: F006
    severity: concern
    category: correctness
    summary: "Presence state is read on the exit thread as well"
    location: "src/amoeba/mcp/presence_task.py:53"
  - id: F007
    severity: concern
    category: correctness
    summary: "`_session_line` now prints the machine name in a fixed-width sessions line, but the header skip logic in `_running` is unchecked"
    location: "src/amoeba/cli/render/sessions.py:41"
  - id: F008
    severity: concern
    category: correctness
    summary: "`check_status` in `update_live.py` uses `names != [LOCAL_MACHINE_NAME]`, so any second machine in the store makes the read-back fail"
    location: "scripts/update_live.py:252"
  - id: F009
    severity: concern
    category: error-handling-observability
    summary: "`write_behind_row` runs `find_caller` and `write_behind_session` inside `store.write()`, and the `SessionOfAnotherMachineError` path is caught around the whole `with` block"
    location: "src/amoeba/hub/call_sessions.py:94"
  - id: F010
    severity: concern
    category: error-handling-observability
    summary: "`_end_session` catches a fixed list of errors and documents swallowing them; the `HubRefusedError` list here omits `HubCertificateError`"
    location: "src/amoeba/mcp/presence_task.py:70"
  - id: F011
    severity: concern
    category: correctness
    summary: "`_handle_reply` logs `presence for` only when the member changes, while the `test_the_presence_line_names...` test expects it on the first reply"
    location: "src/amoeba/mcp/tick.py:186"
  - id: F012
    severity: note
    category: consistency-rot
    summary: "Several test names have words mangled by a find-and-replace"
    location: "tests/operations/test_session_steps.py:51"
  - id: F013
    severity: note
    category: documentation-drift
    summary: "`wiring_presence` imports from `amoeba.client`, which the slice forbids"
    location: "src/amoeba/wiring_presence.py"
  - id: F014
    severity: note
    category: architectural-decay
    summary: "The \"behind\" rule is written in three places"
    location: "src/amoeba/operations/status_sessions.py:49"
  - id: F015
    severity: note
    category: performance-resource
    summary: "`status` now writes on every call, and all calls share one process-wide lock"
    location: "src/amoeba/hub/calls.py#_CALL_ORDER"
  - id: F016
    severity: pass
    category: documentation-drift
    summary: "Store contract and the Codex timeout docs match the code"
    location: "docs/mcp-server.md:58"
---

# Review: code — slice 263

**Verdict:** CONCERNS
**Model:** haiku-line-pass

## Recipe

Recipe `haiku-line-pass`; complete: yes.

| Stage | Kind | Alias | Answering model | Outcome | Findings | Cost |
|---|---|---|---|---|---|---|
| review haiku-xhigh | review | haiku-xhigh | claude-haiku-5-5 | ok | 16 findings | $0.8358 |
| review haiku | review | haiku | claude-haiku-5-5 | ok | 8 findings | $0.3759 |

### Not gating

| Reviewer | Category | Severity | Location | Title |
|---|---|---|---|---|
| haiku-xhigh | documentation-drift | CONCERN | src/amoeba/wire/times.py:45-47 | The retry-time comment on `TICK_TIMES` is false, and `keeps_result` duplicates `WRITING_STEPS` |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/hub/calls.py:259-341 | `_serve` is about 80 lines, and `hub/calls.py` is 384 lines |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/iring_presence.py | An empty module `iring_presence.py` was committed |
| haiku-xhigh | test-debt | CONCERN | tests/hub/test_sessions_modes.py:129 | A wait in the "no member" session test is true before any tick |
| haiku-xhigh | test-debt | CONCERN | tests/mcp_server/test_tick_failures.py:86 | Two more tests have no assertion that matches their names |
| haiku | performance-resource | CONCERN | src/amoeba/hub/calls.py:371 | `_CALL_ORDER` lock is module-level and is acquired before `open_store()`, so every hub call serializes on it, including reads |
| haiku | architectural-decay | CONCERN | src/amoeba/iring_presence.py | `amoeba/iring_presence.py` is added as an empty file |
| haiku | test-debt | CONCERN | tests/mcp_server/test_tick_member.py:1 | `tests/mcp_server/test_tick_member.py` imports `timed_out_cf` and `Opener` through `presence_rig`, and `test_a_cf_that_fails_twice_then_answers_gives_a_row_at_the_thirdrun_tick` uses a non-standard test name |

## Findings

### [CONCERN] Accepted session ticks record the hub's program version as the session's client version

`_refresh` sets `client_version=program_version()`. Through the door, that step runs in the hub process, so every session ticked through the hub is stored with the hub's installed version. The caller's version arrives as `Amoeba-Client-Version`, but it is stored only for refused ticks (`write_behind_session` in `hub/call_sessions.py`). `list` and `status` therefore show the hub's version as the session's client. Two machines on the same door version but different package versions look identical. The tests miss this. `tests/operations/test_session_steps.py` compares against in-process `program_version()`, which is the same process. `tests/hub/test_sessions_across_machines.py` only checks that `client_version` is truthy. The fix is to pass the caller's client version into the step and give the hub a different version in the test.

Reviewer: haiku-xhigh

### [CONCERN] The tick reads presence state from its worker thread

`work()` runs under `anyio.to_thread` and calls `_request(state, ...)`, which reads `state.session_id`, `state.last_seen`, `state.way` and `state.push_confirmed_at`. The `inbox` tool writes `push_confirmed_at` on the event loop (`note_inbox_called`), so the read can race the write. `presence_task._end_in_thread` (`src/amoeba/mcp/presence_task.py:53-58`) reads `state.identity` and `state.session_id` the same way. The slice design says "Only event-loop tasks touch `PresenceState`" (`263-slice…md` line 729), and `mcp/presence.py`'s docstring repeats it. The impact is small, since a stale confirmation is sent one tick late, but the stated invariant is false. Fix: snapshot the four values on the loop before `to_thread`, and have the thread use the snapshot.

Reviewer: haiku-xhigh

### [CONCERN] The exit path's error set omits `HubCertificateError`

`_end_session` catches `HubUnreachableError, HubRefusedError, ClientFileError, StoreError, ConfigError` and logs a warning, on the basis that a failed end costs only a wait. `HubCertificateError` is a separate class (`client/errors.py:19`, not a subclass of `HubUnreachableError`). `TICK_ERRORS` (`tick.py:71-79`) and `AFTER_STEP_ERRORS` (`wiring_steps.py:229-236`) both include it. A certificate mismatch at exit therefore escapes to `run_presence`'s top-level handler and is logged as "presence stopped" at ERROR with a traceback. The operational-error set is now written out in four places (`TICK_ERRORS`, this inline tuple, `AFTER_STEP_ERRORS`, `OPERATIONAL_ERRORS` in `wiring.py`). Build the exit tuple from one shared constant so they cannot drift again.

Reviewer: haiku-xhigh

### [CONCERN] The normal tick accepts any client and directory string, while the header path rejects bad ones

`SessionTickRequest.client` and `.directory` are bare `str`, with no length or character constraint. `_refresh` writes them to `sessions` unchanged. `hub/call_sessions.py` applies `CLIENT_NAME_PATTERN`, the 4096-character bound and a printable-character check to the same values from headers, and writes nothing when they fail. An accepted tick can therefore store a control-character or very long directory, which `list` and `status` print for every viewer. The caller is an authenticated machine, so the exposure is internal, but the project rule is to validate at the model. Constrain the fields on the request model and have the header path reuse the same type.

Reviewer: haiku-xhigh

### [CONCERN] The injected door version reaches the session steps but not the served operations or status

`handle_call` and `create_app` take `door_version` so a test can serve another version, and `StepEdges` carries it to the steps. The served operations do not see it. `ServedEdges` (`operations/served_types.py:71`) has no door version, so `send` (`send_write.py:107, 186`), wake (`wake.py:86`), `status` (`status.py:218, 239-240`), `wake_status.py:47` and `hub/admin.py:91` read the `DOOR_VERSION` constant. Production is unaffected because both values are equal. A hub test that serves another version, though, gets one answer for "held off" from `open_runs` and a different one from `status`. Either thread `door_version` through `ServedEdges` and use it everywhere, or remove the seam.

Reviewer: haiku-xhigh

### [CONCERN] Presence state is read on the exit thread as well

This is the same thread-boundary issue as the tick, on the exit path. It is lower risk because the tick has been cancelled by then. Fix it with the same snapshot.

Reviewer: haiku-xhigh

### [CONCERN] `_session_line` now prints the machine name in a fixed-width sessions line, but the header skip logic in `_running` is unchecked

The session line now joins `entry.client`, `entry.machine`, `entry.directory` and so on. The test `test_a_session_renders_as_one_line_under_its_member` was updated to expect `alpha` in the second position, which matches this order. I could not confirm that every consumer of this line expects the new field order, so this is a note to check the other renderers and the `list` text path.

Reviewer: haiku

### [CONCERN] `check_status` in `update_live.py` uses `names != [LOCAL_MACHINE_NAME]`, so any second machine in the store makes the read-back fail

The read-back check requires `status` to list exactly the one `local` machine. A PM store with any other machine with a token (for example one joined to a hub) fails the update and triggers a restore. If `update_live` is only meant for the single-machine local store, this is intended. The docstring should say so, because the rule is otherwise surprising.

Reviewer: haiku

### [CONCERN] `write_behind_row` runs `find_caller` and `write_behind_session` inside `store.write()`, and the `SessionOfAnotherMachineError` path is caught around the whole `with` block

The `except SessionOfAnotherMachineError: return` handler swallows the error, and its comment says that no column changed. The write transaction is therefore committed or rolled back depending on where the raise happens. The comment says "the refusal stands", which is true, but the rule for a swallowed exception requires an explanation that the store state is consistent. The comment does this. The handler only catches a specific class, which the rules allow. Flagging it so the reviewer confirms the commit behaviour inside the `with` block.

Reviewer: haiku

### [CONCERN] `_end_session` catches a fixed list of errors and documents swallowing them; the `HubRefusedError` list here omits `HubCertificateError`

`_end_session` catches `HubUnreachableError`, `HubRefusedError`, `ClientFileError`, `StoreError` and `ConfigError`. `tick.py` also treats `HubCertificateError` as an operational failure (`TICK_ERRORS`). An exit that hits a certificate error would therefore escape as an unhandled error, and `run_presence` would log it as "presence stopped". The two lists should be one shared constant.

Reviewer: haiku

### [CONCERN] `_handle_reply` logs `presence for` only when the member changes, while the `test_the_presence_line_names...` test expects it on the first reply

The condition `reply.member_id != state.member_id` fires once per member change, which matches the test. A session that restarts with the same state object would not log again. This is probably fine, but it is a second consumer of the line (`wait_for_presence` in `hub_mcp.py` reads it), so confirm that the live tests still see the line after a reconnect.

Reviewer: haiku

### [NOTE] Several test names have words mangled by a find-and-replace

The names `…changes_norow_of`, `…dates_therow_of` (`tests/operations/test_session_end_steps.py:193`), `…at_the_thirdrun_tick` (`tests/mcp_server/test_tick_member.py:64`) and `…reaches_the_row_at_the_nextrun_tick` (`test_tick_member.py:248`) are broken. Rename them.

Reviewer: haiku-xhigh

### [NOTE] `wiring_presence` imports from `amoeba.client`, which the slice forbids

Slice 263 says `amoeba.mcp` and `wiring_presence` import "nothing from `amoeba.client`" (`263-slice…md` line 122). The module imports `client_file` and `client.errors`, which is reasonable for a wiring module, but the design and the code disagree. The boundary test (`tests/test_import_boundaries.py`) pins only `amoeba.store`. Update the design, or add the client import to the test.

Reviewer: haiku-xhigh

### [NOTE] The "behind" rule is written in three places

`status_machines.is_behind` returns `None` for an unknown version, `status_sessions._entry` writes the comparison inline, and `hub/admin.is_behind` is a wrapper that exists only to pass the constant. Use one function.

Reviewer: haiku-xhigh

### [NOTE] `status` now writes on every call, and all calls share one process-wide lock

`status` and `list` now call `store_calling_runs` and write the report on every call, so a view is no longer read-only. `_CALL_ORDER` serializes every call, reads included. The comment explains the choice, and the load test covers it, so this is for awareness.

Reviewer: haiku-xhigh

### [PASS] Store contract and the Codex timeout docs match the code

`docs/store-contract.md` documents migration 014's columns and `machine_runs`, and `docs/mcp-server.md` gives `tool_timeout_sec = 305`, matching `MCP_CALL_DEADLINE_SECONDS = 300` in `wire/times.py`. The starter config (`notify_poll_seconds: 5`, `session_heartbeat_seconds: 30`, `session_stale_seconds: 90`) satisfies the new stale-time rule, 90 ≥ 30 + 2×5.

Reviewer: haiku-xhigh

### Run Digest

- Response length: 11247 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: not computed
- Stop reason: not computed
- Output budget: backend default
- System prompt: not computed
- Settings sources: not computed
- Reasoning characters: not computed
- Effort: backend default
- Turns: 32
- Tokens — prompt / cached / cache write / completion / reasoning: 4113731 / 3514894 / 598811 / 78701 / not computed
- Duration: 352.7 s
- Cost: $1.21
- `## Summary` located: not computed
- `## Findings` located: not computed
- Finding-shaped matches — whole response: not computed
- Finding-shaped matches — inside fences: not computed
- Finding-shaped matches — in findings section: not computed
- Finding-shaped matches — surviving validation: not computed
