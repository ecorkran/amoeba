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
reviewedSha: 05464a92cc33e9548c575e4e7b3b51861bf5e9f8
reviewedBlob: edc728e84ba0948069dc733214f7ff3e79be29bb
reviewedBlobCurrent: true
revision_number: 1
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - ".git/HEAD"
  - "src/amoeba/mcp/after_runner.py"
  - "src/amoeba/mcp/presence_task.py"
  - "src/amoeba/mcp/inbox_resource.py"
  - "src/amoeba/iring_presence.py"
  - "src/amoeba/wire/times.py"
  - "src/amoeba/wiring_steps.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/wire/protocol.py"
  - "docs/store-contract.md"
  - "src/amoeba/cli/hub_commands.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/operations/steps/session.py"
  - "docs/mcp-server.md"
  - "docs/cli-contract.md"
searches:
  - "list_files src/amoeba/iring_presence.py in /Users/manta/source/repos/manta/amoeba"
  - "grep SESSION_STEP_NAMES|SESSION_CALLS|SERVED_OPERATIONS|delete_machine_runs|DELETE_MACHINE_RUNS_BY_ID|uv tool install --force amoeba-ai|tool_timeout_sec in /Users/manta/source/repos/manta/amoeba"
  - "grep SESSION_CALLS|HEADER_VALUE_MAX_LENGTH|def _header|create_app\\(|handle_call\\(|StepContext\\(|WRITING_STEPS =|uv tool install --force amoeba-ai in /Users/manta/source/repos/manta/amoeba/src"
  - "grep machine_runs|sessions\\.door_version|client_version in /Users/manta/source/repos/manta/amoeba/project-documents"
  - "grep STORE_CONTRACT\\s*=|STORE_CONTRACT: in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep machine_runs|door_version|sessions in /Users/manta/source/repos/manta/amoeba/docs"
  - "grep thirdrun|nextrun|replys|afterrun|firstrun in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep DOOR_VERSION\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep assert_never|WaitingRunState\\.NOT_LISTED in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep later slice|for now|not yet|TODO|FIXME|build only if|if needed in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep _ticked|def _ticked|a tick that found no member in /Users/manta/source/repos/manta/amoeba/tests/hub/test_sessions_modes.py"
  - "grep after-step|after step|amoeba://inbox|lists nothing|resources/list|no member in /Users/manta/source/repos/manta/amoeba/docs"
  - "grep after-step|after_call|after_operation in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring.py"
  - "grep environ=|environ:|forge\\.environ in /Users/manta/source/repos/manta/amoeba/tests/live"
  - "grep def write_behind_session|_not_in_process\\(name|if name is OperationName.HANDLE_PAUSE|MARKER_WAIT_SECONDS: Final|_CALL_ORDER: Final|def _is_ahead|hub_door_version=DOOR_VERSION in /Users/manta/source/repos/manta/amoeba"
turns: 34
promptTokens: 4074236
cachedTokens: 3492349
cacheWriteTokens: 581861
completionTokens: 82119
durationSeconds: 359.9
costUsd: 1.204468
runId: run-20261125-p6-fbf201a3
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: concern
    category: consistency-rot
    summary: "The served door version has two sources"
    location: "src/amoeba/operations/send_write.py:107"
  - id: F002
    severity: concern
    category: security-hygiene
    summary: "The two-machine live test passes the whole process environment to the agent"
    location: "tests/live/channels/test_two_machines_channels_live.py:110"
  - id: F003
    severity: concern
    category: type-contract-debt
    summary: "`_read_back` calls `steps.status()` but `check_status` assumes the result is a dict with `machines` as a list of `{name}` objects"
    location: "scripts/update_live.py#check_status"
  - id: F004
    severity: concern
    category: correctness
    summary: "`_door_text` / `machines` renderer: `lines[0]` indexing in `_run_machines` is fragile"
    location: "src/amoeba/cli/hub_commands.py#_run_machines"
  - id: F005
    severity: concern
    category: correctness
    summary: "`session_end` is written as a write step that keeps no result, yet `write_behind_row` and `handle_call` may leave the machine row with a stale door version"
    location: "src/amoeba/hub/calls.py#_serve"
  - id: F006
    severity: concern
    category: error-handling-observability
    summary: "Exception handling in `_end_session` swallows a tuple of errors but logs at WARNING with no traceback"
    location: "src/amoeba/mcp/presence_task.py#_end_session"
  - id: F007
    severity: note
    category: documentation-drift
    summary: "The store contract and CLI contract omit the new `machine_runs` delete from `rm-machine`"
    location: "docs/store-contract.md:683"
  - id: F008
    severity: note
    category: documentation-drift
    summary: "The inbox resource docstring says every handler waits for the first tick"
    location: "src/amoeba/mcp/inbox_resource.py:4"
  - id: F009
    severity: note
    category: documentation-drift
    summary: "The `TICK_TIMES` comment gives the wrong reason for excluding ticks from writing steps"
    location: "src/amoeba/wire/times.py:45"
  - id: F010
    severity: note
    category: consistency-rot
    summary: "Upgrade command, \"ahead of the hub\" wording, and the behind rule are repeated"
    location: "src/amoeba/cli/render/machines.py:22"
  - id: F011
    severity: note
    category: architectural-decay
    summary: "`HANDLE_PAUSE` is guarded twice, and the second guard is now unreachable"
    location: "src/amoeba/wiring.py:287"
  - id: F012
    severity: note
    category: consistency-rot
    summary: "Test names read like a search-and-replace artifact, and one test checks a private helper"
    location: "tests/mcp_server/test_tick_member.py:64"
  - id: F013
    severity: note
    category: consistency-rot
    summary: "A magic 300 repeats the MCP deadline"
    location: "tests/live/channels/test_long_call_live.py:36"
  - id: F014
    severity: note
    category: correctness
    summary: "`DOOR_VERSION` bumped from 2 to 3 with a pinned-tuple test"
    location: "src/amoeba/wire/times.py"
  - id: F015
    severity: note
    category: other
    summary: "Commit cadence and verdict"
    location: "unverified"
---

# Review: code — slice 263

**Verdict:** CONCERNS
**Model:** haiku-line-pass

## Recipe

Recipe `haiku-line-pass`; complete: yes.

| Stage | Kind | Alias | Answering model | Outcome | Findings | Cost |
|---|---|---|---|---|---|---|
| review haiku-xhigh | review | haiku-xhigh | claude-haiku-5-5 | ok | 16 findings | $0.8337 |
| review haiku | review | haiku | claude-haiku-5-5 | ok | 13 findings | $0.3708 |

### Not gating

| Reviewer | Category | Severity | Location | Title |
|---|---|---|---|---|
| haiku-xhigh | performance-resource | CONCERN | src/amoeba/mcp/after_runner.py:80 | Presence exit can wait for an in-flight after-step |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/hub/call_sessions.py:36 | Session step names are defined in two modules |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/operations/steps/session.py:53 | The session row's start and confirmation rules are written twice |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/iring_presence.py | An empty file was added to the source tree |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/hub/calls.py | Several modules are well past the ~300-line guideline |
| haiku-xhigh | documentation-drift | CONCERN | docs/cli-contract.md:1129 | The after-step docs describe the old MCP behavior |
| haiku-xhigh | test-debt | CONCERN | tests/hub/test_sessions_modes.py:129 | The sessions-modes test can race its own precondition |
| haiku | performance-resource | CONCERN | src/amoeba/hub/calls.py\#handle_call | `_CALL_ORDER` global lock serializes every hub call, including non-session calls |
| haiku | architectural-decay | CONCERN | src/amoeba/wiring_presence.py | `wiring_presence` re-exports many names; `__all__` includes `program_version` and `machine_name` which are not store or client types |
| haiku | architectural-decay | CONCERN | src/amoeba/operations/steps/dispatch.py\#StepEdges | `call_result` `door_version` threads through many layers as a positional argument, duplicating `DOOR_VERSION` defaults |
| haiku | architectural-decay | CONCERN | src/amoeba/wiring_steps.py\#SESSION_STEP_NAMES | `SESSION_STEP_NAMES` and `SESSION_CALLS` duplicate the same session-step set |
| haiku | documentation-drift | CONCERN | src/amoeba/config/user_config.py\#_session_timing_holds | `_session_timing` new check comment says "a heartbeat plus a poll interval" but the check uses `2 * notify_poll_seconds` |
| haiku | documentation-drift | CONCERN | src/amoeba/hub/calls.py | `_CALL_ORDER` comment cites SQLite handler timing (100 ms sleep) as fact |
| haiku | other | CONCERN | src/amoeba/iring_presence.py | `iring_presence.py` is added as an empty file |

## Findings

### [CONCERN] The served door version has two sources

The served version reaches the hub through `handle_call(door_version=…)`, `create_app(door_version=…)`, `StepEdges.door_version`, and `StepContext.door_version`. But `send_write.py:107` and `:186`, `operations/wake.py:86`, `operations/wake_status.py:47`, and `operations/status.py:218` and `:239-240` read the `DOOR_VERSION` constant directly. In production the two agree. In a test that serves another version (the seam `HubRig.door_version` exists for this), a send's wake gate and the status view silently use the program's constant. The `handle_call` docstring (`src/amoeba/hub/calls.py:363-374`) acknowledges this. The defaults `door_version: int = DOOR_VERSION` (`hub/app.py:64`, `hub/calls.py:363`, `operations/steps/dispatch.py:75`) also mean an omitted argument silently becomes the constant; `src/amoeba/cli/hub_commands.py:123-130` relies on them. Pass the served version through the same edges to every hub-side reader, remove the defaults, and have `hub_commands` pass `DOOR_VERSION` explicitly.

Reviewer: haiku-xhigh

### [CONCERN] The two-machine live test passes the whole process environment to the agent

`environ=os.environ` gives a real Claude Code session every variable in the developer's shell. That can include `AMOEBA_HOME` or a production database URL, which the test rules forbid tests from reading (`sql.md`, "Production Database Protection"). The other live tests build an isolated environment: `test_long_call_live.py:61` and `world.py:109` use `world.forge.environ`. Use the same isolated environment, or an explicit list of named variables.

Reviewer: haiku-xhigh

### [CONCERN] `_read_back` calls `steps.status()` but `check_status` assumes the result is a dict with `machines` as a list of `{name}` objects

`check_status` does `document.get("machines", [])` and then `entry.get("name")` on each entry. The `status` step returns a parsed JSON dict from `amoeba status -j`, so a status document whose `machines` field is absent or not a list of objects will either silently yield `[]` (producing a false "lack local" failure rather than a clear parse error) or raise an `AttributeError` on a non-dict entry. The read-back is a trust boundary for a just-installed binary. Validation or an explicit shape check is missing here.

Reviewer: haiku

### [CONCERN] `_door_text` / `machines` renderer: `lines[0]` indexing in `_run_machines` is fragile

`text = "\n".join(lines if rows else [lines[0], "no machines"])` relies on `lines[0]` being the header line. This is correct as written, but the construction builds the header into `lines` and then indexes it back out. Reading the hunk, the logic holds; it is worth a direct simplification, but I am not claiming a defect.

Reviewer: haiku

### [CONCERN] `session_end` is written as a write step that keeps no result, yet `write_behind_row` and `handle_call` may leave the machine row with a stale door version

`touch_machine` is called with `keep_versions=is_session_call(request.name)`, so a session's tick does not update `door_version` on the machine. A refused tick from an old session writes a session row with the caller's versions but does not touch the machine row. This is the intended D6 behavior per the docstrings. The concern is only that `parse_door_version(_header(request, HEADER_DOOR_VERSION))` is evaluated in two places, and the second call (inside `write_behind_row` argument list) is evaluated after `clock()` inside `with store.call_scope()`. Behavior is consistent but duplicated; I could not verify the ordering contract without reading `store.call_scope`.

Reviewer: haiku

### [CONCERN] Exception handling in `_end_session` swallows a tuple of errors but logs at WARNING with no traceback

The `except (...)` block is justified by a comment (swallowing correct at teardown), so it satisfies rule (b). However it uses `logger.warning` without the traceback. That is acceptable for a documented expected failure, but `ConfigError` and `ClientFileError` are persistent conditions, not transient ones, and a silent WARNING per exit hides them. Consider whether these deserve ERROR with exception info.

Reviewer: haiku

### [NOTE] The store contract and CLI contract omit the new `machine_runs` delete from `rm-machine`

Both documents list what `rm-machine` deletes (sessions and call results, then the machine). `remove_machine` also deletes `machine_runs` (`sql_machines.DELETE_MACHINE_RUNS`), and the `machine_runs` section (`store-contract.md:406`) says so. Add it to `docs/store-contract.md:683` and `docs/cli-contract.md:1264`.

Reviewer: haiku-xhigh

### [NOTE] The inbox resource docstring says every handler waits for the first tick

Lines 4-5 say every handler first waits for presence to resolve. `list_resources` (lines 67-75) returns at once, and a test asserts that it does. Correct the docstring.

Reviewer: haiku-xhigh

### [NOTE] The `TICK_TIMES` comment gives the wrong reason for excluding ticks from writing steps

"A retry time of 0 is also what keeps `session_tick` out of the writing steps." Membership comes from `keeps_result` and `WRITING_STEPS`, not from the retry time. Delete that sentence.

Reviewer: haiku-xhigh

### [NOTE] Upgrade command, "ahead of the hub" wording, and the behind rule are repeated

`UPGRADE_COMMAND` is defined here and again at `src/amoeba/client/call.py:52`. "ahead of the hub" appears in `render/machines.py` and in `src/amoeba/cli/hub_commands.py:158`. The behind/ahead direction is written out in `_door_text` (`hub_commands.py:154-158`), `_is_ahead` (`render/machines.py:93`), and `status_machines.differs_from_hub`. Import the command from one place and route the direction through one function.

Reviewer: haiku-xhigh

### [NOTE] `HANDLE_PAUSE` is guarded twice, and the second guard is now unreachable

`invoke` raises for `HANDLE_PAUSE` at lines 190-191, before `_dispatch` runs. The `case OperationName.HANDLE_PAUSE` at line 287 cannot be reached. Keep one guard.

Reviewer: haiku-xhigh

### [NOTE] Test names read like a search-and-replace artifact, and one test checks a private helper

`…gives_a_row_at_the_thirdrun_tick` (line 64), `…reaches_the_row_at_the_nextrun_tick` (line 248), and `…the_replys_after` in `tests/mcp_server/test_tick_failures.py:161` are garbled. Rename them to "third tick", "next tick", and "replies". `test_tick_failures.py:161-170` also asserts the private `_interval`. Assert the observable wait instead.

Reviewer: haiku-xhigh

### [NOTE] A magic 300 repeats the MCP deadline

`MARKER_WAIT_SECONDS = 300 + …` repeats `MCP_CALL_DEADLINE_SECONDS` from `wire/times.py`. Reference the constant so that changing the deadline changes one place.

Reviewer: haiku-xhigh

### [NOTE] `DOOR_VERSION` bumped from 2 to 3 with a pinned-tuple test

`DOOR_VERSION` moves 2 → 3, and `MCP_CALL_DEADLINE_SECONDS` moves from 180 to 300. The door change is a wire-contract change; the test pins the new values. The project expects a door bump for call-format changes, so this is consistent. Noted for the release record.

Reviewer: haiku

### [NOTE] Commit cadence and verdict

I could not inspect commit history, task files, or the migration file's full context from this session. The migration `014_sessions_across_machines.sql` adds a `BEFORE INSERT` trigger on `sessions` that aborts on null versions; the `UPSERT_SESSION` path depends on this. I did not verify the trigger against every insert path.

Reviewer: haiku

### Run Digest

- Response length: 10090 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: not computed
- Stop reason: not computed
- Output budget: backend default
- System prompt: not computed
- Settings sources: not computed
- Reasoning characters: not computed
- Effort: backend default
- Turns: 34
- Tokens — prompt / cached / cache write / completion / reasoning: 4074236 / 3492349 / 581861 / 82119 / not computed
- Duration: 359.9 s
- Cost: $1.20
- `## Summary` located: not computed
- `## Findings` located: not computed
- Finding-shaped matches — whole response: not computed
- Finding-shaped matches — inside fences: not computed
- Finding-shaped matches — in findings section: not computed
- Finding-shaped matches — surviving validation: not computed
