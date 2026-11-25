---
docType: review
layer: project
reviewType: tasks
slice: sessions-across-machines
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/263-tasks.sessions-across-machines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261124
dateUpdated: 20261124
reviewedSha: d93226489246b0c8843ea9a2c2bf2685b9554bea
reviewedBlob: 5a6602173e3fc276e446ff576fe980487663ba58
reviewedBlobCurrent: true
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 76
injected:
  - key: input
    path: "project-documents/user/tasks/263-tasks.sessions-across-machines.md"
    chars: 41699
    sha256: 3134ced3eb0e168f4db13d846e34bcf965c59f486a059a1e94b15bd96c55d191
    whole: true
  - key: against
    path: "project-documents/user/slices/263-slice.sessions-across-machines.md"
    chars: 85817
    sha256: 846b97f865f9a8dcb5c72b7d9b77c1922cecbaeee20ea6da8fc6f1e6e6b4fba0
    whole: true
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "src/amoeba/wire/times.py"
  - "src/amoeba/store/sessions.py"
  - "src/amoeba/store/sql_sessions.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/store/push_reads.py"
  - "src/amoeba/store/sql_machines.py"
  - "src/amoeba/wiring_presence.py"
  - "src/amoeba/mcp/presence.py"
  - "src/amoeba/mcp/inbox_watcher.py"
  - "tests/config/test_session_timing_config.py"
  - "tests/mcp_server/test_boundary.py"
  - "src/amoeba/wiring_steps.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/operations/steps/dispatch.py"
  - "src/amoeba/operations/steps/models.py"
  - "src/amoeba/operations/caller.py"
  - "src/amoeba/operations/errors.py"
  - "src/amoeba/operations/steps/model_base.py"
  - "src/amoeba/operations/store_steps.py"
  - "src/amoeba/hub/call_work.py"
  - "src/amoeba/client/call.py"
  - "src/amoeba/mcp/in_process.py"
  - "src/amoeba/mcp/presence_task.py"
  - "src/amoeba/wiring_door.py"
  - "src/amoeba/mcp/server.py"
  - "tests/load/test_door_steps_load.py"
  - "tests/wire/test_protocol.py"
  - "src/amoeba/cli/render/waiting.py"
  - "src/amoeba/operations/status_models.py"
searches:
  - "list_files **/store/schema/*.sql in /Users/manta/source/repos/manta/amoeba"
  - "grep EXPECTED_SCHEMA_VERSION\\s*=|DOOR_VERSION\\s*=|MCP_CALL_DEADLINE_SECONDS|CHANNEL_EVENT_MAX_ENTRIES\\s*=|CLIENT_NAME_PATTERN\\s*=|NotServedError|class DeadlineError|class HubHomeError|class ClientFileError in /Users/manta/source/repos/manta/amoeba/src"
  - "grep DOOR_VERSION in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep EXPECTED_SCHEMA_VERSION|DOOR_VERSION: |class DoorTimes|CALL_BOUND_SECONDS|retry_seconds|attempts|STEP_CALLS|WRITING_STEPS|SERVED_OPERATIONS|CHANNEL_EVENT_MAX_ENTRIES|CLIENT_NAME_PATTERN in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep live_member_ids|live_sessions|heartbeat\\(|delete_session|read_high_seq|member_high_seq|push_rows_after|read_push_rows|read_as_of_seq|touch_machine|remove_machine|prune_stale_sessions|upsert_session|from amoeba\\.store\\.push_reads|store\\.push_reads|store import push_reads|store\\.sessions|from amoeba\\.\u2026 in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def |^class |^[A-Z_]+ *[:=] in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring_presence.py"
  - "grep inbox_watcher|heartbeat_loop|watch_inbox|Session\\(|from amoeba\\.client|import amoeba\\.client|ClientFileError in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/**/*.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/mcp_server/*.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/live/channels/*.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/{test_after_step,test_wiring_release,test_import_boundaries,test_contract_docs,hub_fixture,hub_mcp}.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/{store/schema_12,store/schema_13,store/test_migration_013,store/test_schema_holds_no_mirrored_state,store/seed,store_open,hub/in_process_hub,cf_stub,sq_stub,fault_injection}.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/{scripts,config,load,client}/*.py in /Users/manta/source/repos/manta/amoeba"
  - "grep ^def test_|^async def test_ in /Users/manta/source/repos/manta/amoeba/tests/live/channels/test_channels_live.py"
  - "grep after_operation|after_call|start_after|claim_work|wiring_steps|\\.invoke\\(|NotServedError|DeadlineError|check_deadline in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep STALE_HEARTBEATS_MIN|session_stale_seconds|session_heartbeat_seconds|notify_poll_seconds|resume_wait_seconds|def |^class  in /Users/manta/source/repos/manta/amoeba/src/amoeba/config/user_config.py"
  - "grep def resume_bound_seconds|def resume_claim_seconds|def resume_work_seconds|RESUME_POLL_INTERVAL_SECONDS|RUN_POLL_TIMEOUT_SECONDS|TERMINATE_GRACE_SECONDS|def claim_bound|^RESUME_|def answer_|resume_wait_seconds in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def |^class |PAUSED|WaitingRunState|other_machine|run_state|machines|hub_door|door_version in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/status_models.py"
  - "grep CREATE TABLE|CREATE TRIGGER|client_version|door_version|machine_id|owner_id|REFERENCES|RAISE|BEFORE INSERT in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "grep ^def |^class |^[A-Z_]+ *[:=] in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/here.py"
  - "grep def |^class |rm.machine|hub machines|machines|door in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/admin.py"
  - "grep def two_machine_hub|class ClientHome|class TwoMachine|def |^class  in /Users/manta/source/repos/manta/amoeba/tests/hub_fixture.py"
  - "grep CLIENTS|clients|range\\(|def test_|ticks|16 in /Users/manta/source/repos/manta/amoeba/tests/load/test_door_load.py"
  - "grep class |def |DoorHooks|clock|door_version|serve in /Users/manta/source/repos/manta/amoeba/tests/hub/in_process_hub.py"
  - "grep def |open_store|PresenceDeps|SessionTiming|joined|state_move|load_config|check_deadline|served|NotServed|HubHome|AmoebaScriptMissing|ClientFileError|client_file|inbox_resource|presence_task|run_presence in /Users/manta/source/repos/manta/amoeba/src/amoeba/mcp/server.py"
  - "grep ^def |argparse|add_parser|add_argument|environ|AMOEBA_|restore|sessions|amoeba-mcp|read.?back|list in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep def |restore|update|monkeypatch|environ|tmp_path|schema_13|schema_12|import  in /Users/manta/source/repos/manta/amoeba/tests/scripts/test_update_live.py"
  - "grep push_confirmed|live_sessions|LIVE_SESSION|live_member_ids|DOOR_VERSION in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep COLUMN_REASONS|def test_|client_version|door_version|sessions in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep def test_|sessions|mcp-server|cli-contract|store-contract|config-contract|DOCS|\\.md in /Users/manta/source/repos/manta/amoeba/tests/test_contract_docs.py"
  - "grep 180|185|tool_timeout_sec|150\\.5|CLAUDE_CODE_MCP|2\\.1\\.325|MCP_TOOL_TIMEOUT in /Users/manta/source/repos/manta/amoeba"
  - "grep ^def test_|MCP_CALL_DEADLINE|check_deadline|DeadlineError|180|89\\.5|209|answer_bound in /Users/manta/source/repos/manta/amoeba/tests/mcp_server/test_deadline.py"
  - "grep MCP_CALL_DEADLINE_SECONDS|SessionTiming\\(|session_stale_seconds=|session_heartbeat_seconds=|notify_poll_seconds=|stale_seconds=|heartbeat_seconds= in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files tests/test_message_timing.py in /Users/manta/source/repos/manta/amoeba"
  - "grep ^(notify_poll_seconds|session_heartbeat_seconds|session_stale_seconds|resume_wait_seconds):|session_stale_seconds|session_heartbeat_seconds in /Users/manta/source/repos/manta/amoeba"
  - "grep def _example_number|example_config_text|def |example in /Users/manta/source/repos/manta/amoeba/tests/user_configs.py"
  - "grep WRITING_STEPS|STEP_CALLS|STEP_MODELS\\b.*writes|writes=|\\.writes|NotServedError in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep test_the_mcp_door_starts_the_ended_held_question_too|def test_the_cli_door|def test_ in /Users/manta/source/repos/manta/amoeba/tests/test_after_step.py"
  - "grep EXPECTED_SCHEMA_VERSION|== 13\\b|== 12\\b|SCHEMA_VERSION in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def read|def write|def call_scope|query_only|BEGIN|SAVEPOINT|readonly|mode=ro in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/store.py"
  - "grep pytest|tests/load|tests/live|-m |marker|--ignore|addopts|testpaths in /Users/manta/source/repos/manta/amoeba"
  - "grep waiting on|on request|run_state|WaitingRunState|def .*waiting|\"on \"|on \\{ in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/render"
  - "grep dotenv|\\.env\\b|environ in /Users/manta/source/repos/manta/amoeba/tests/live/channels"
  - "grep serve_pinned|^def |^async def |CF_GET_TIMEOUT_SECONDS in /Users/manta/source/repos/manta/amoeba"
  - "grep RUN_STATE_TEXT|def _machine_text|other_machine|on \\{|\" on \"|f\" on|machine in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/render/waiting.py"
sectionsInDocument: 12
sectionsCovered: 12
effort: xhigh
turns: 77
promptTokens: 6441918
cachedTokens: 6137537
cacheWriteTokens: 304319
completionTokens: 197657
durationSeconds: 835.9
costUsd: 0.982082
costBasis: provider
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: fail
    category: existing-code
    summary: "Session steps cannot be written as the flag is specified"
    location: "src/amoeba/operations/steps/dispatch.py:93"
  - id: F002
    severity: fail
    category: test-coverage
    summary: "Deleting the two loops leaves 241 test modules importing deleted code"
    location: "tests/mcp_server/test_inbox_watcher.py:21"
  - id: F003
    severity: fail
    category: sequencing
    summary: "8.3 depends on a field that 9.1 adds after it"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:226"
  - id: F004
    severity: concern
    category: data-model
    summary: "The upsert has no machine guard and names no SQL change"
    location: "src/amoeba/store/sql_sessions.py:26"
  - id: F005
    severity: concern
    category: existing-code
    summary: "Session readers and constructors are not in the task list"
    location: "src/amoeba/mcp/presence.py:137"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "The third config check breaks a test the task does not name"
    location: "tests/config/test_session_timing_config.py:96"
  - id: F007
    severity: concern
    category: error-handling
    summary: "The exit call's errors are not named"
    location: "src/amoeba/mcp/presence_task.py:70"
  - id: F008
    severity: concern
    category: existing-code
    summary: "`SessionTiming` and the config read stay on the joined path"
    location: "src/amoeba/mcp/server.py:247"
  - id: F009
    severity: concern
    category: concurrency
    summary: "Each worker thread's steps are not named"
    location: "src/amoeba/wiring_steps.py:133"
  - id: F010
    severity: concern
    category: testability
    summary: "The wake rule's door version has no source a test can change"
    location: "src/amoeba/store/wakes.py:141"
  - id: F011
    severity: concern
    category: data-model
    summary: "The touch writes an unchecked door version"
    location: "src/amoeba/hub/calls.py:142"
  - id: F012
    severity: concern
    category: test-coverage
    summary: "Two step pins break, and the load test is not named"
    location: "tests/wire/test_protocol.py:121"
  - id: F013
    severity: concern
    category: existing-code
    summary: "`test_message_timing.py` imports the constant the task deletes"
    location: "tests/test_message_timing.py:34"
  - id: F014
    severity: concern
    category: existing-code
    summary: "A new run state would break `list`, and the `on <machine>` suffix is missing"
    location: "src/amoeba/cli/render/waiting.py:187"
  - id: F015
    severity: concern
    category: test-coverage
    summary: "10.2 says every walkthrough bullet is already tested"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:274"
  - id: F016
    severity: concern
    category: ci
    summary: "The load test has no CI gate step"
    location: ".github/workflows/ci.yml:40"
  - id: F017
    severity: concern
    category: proportionality
    summary: "4.4 bundles the consumer move with the deletions"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:138"
  - id: F018
    severity: concern
    category: docs
    summary: "The 260 and 262 amendments belong to no task"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:188"
  - id: F019
    severity: note
    category: docs
    summary: "0.1 names the wrong design sections"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:44"
  - id: F020
    severity: note
    category: docs
    summary: "4.3's outcome wording differs from D7's table"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:135"
  - id: F021
    severity: note
    category: existing-code
    summary: "6.4 misplaces the served check"
    location: "src/amoeba/wiring_door.py:118"
  - id: F022
    severity: note
    category: existing-code
    summary: "9.1 assigns work the code already does"
    location: "src/amoeba/store/machines.py:294"
  - id: F023
    severity: note
    category: existing-code
    summary: "9.3's status check needs a call the script does not make"
    location: "scripts/update_live.py:447"
  - id: F024
    severity: note
    category: test-coverage
    summary: "8.7's command drops the .env step"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:243"
  - id: F025
    severity: note
    category: test-coverage
    summary: "The import rules disagree with the existing boundary test"
    location: "tests/mcp_server/test_boundary.py:19"
  - id: F026
    severity: note
    category: docs
    summary: "The final commit holds only notes"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:277"
  - id: F027
    severity: note
    category: test-coverage
    summary: "Some success criteria are only partly tested"
    location: "project-documents/user/tasks/263-tasks.sessions-across-machines.md:112"
---

# Review: tasks — slice 263

**Verdict:** FAIL (all findings resolved 20261124 in the task file)
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Session steps cannot be written as the flag is specified

`Step.writes` is both the transaction selector and the kept-result flag (`model_base.py:29-30`). `run_step` takes `store.write()` only when `writes` is true (`dispatch.py:93`); otherwise it takes `store.read()`, which outside a call scope is `BEGIN DEFERRED` (`store/store.py:185-193`). Task 3.1 (line 102) says neither session row has the kept flag, so `session_tick`'s delete and upsert would run in a deferred read. On the local path the write lock is then taken late, not through the `BEGIN IMMEDIATE` every other writer uses (`store.py:181`). Setting `writes=True` instead would put both rows into `WRITING_STEPS` through the derivation pinned at `tests/wire/test_protocol.py:122`, which 3.3 says must pass and 3.1 (line 105) contradicts. Also, `session_tick` reads three config keys, but 3.1 never sets `needs_config`, and `run_step` loads config only when it is set (`dispatch.py:91`). Split the two properties into separate fields, set `needs_config` on `session_tick`, and state what 262's pin becomes.

### [FAIL] Deleting the two loops leaves 241 test modules importing deleted code

Task 4.4 (line 139) deletes `mcp/inbox_watcher.py` and `heartbeat_loop`. `test_inbox_watcher.py` imports `watch_inbox` at line 21 and uses it at lines 56, 189 and 253. `tests/mcp_server/test_presence.py` imports `heartbeat_loop` at line 25 and uses it at lines 161, 231 and 244. The Context Summary (line 27) says `test_inbox_watcher.py` is replaced by `test_tick.py`, but no step deletes or rewrites either file. 4.6 (line 147) limits 241 test edits to six kinds, and none covers replacing loop-level tests. Collection fails at 4.4, so the "checks pass" successes in 4.4 and 4.6 cannot be met as written. Name each deletion, and say what `test_tick.py` must cover from each.

### [FAIL] 8.3 depends on a field that 9.1 adds after it

8.3 asserts that after an `amoeba` command on the upgraded machine, `amoeba hub machines -j` shows it as not behind (line 226). The `behind` field of `-j` is added in 9.1 (line 251), which comes after section 8 and its commit (line 246). Section 8 cannot pass in the order written. Move the `hub machines` change ahead of 8.3, or take that assertion out of 8.3 and test it in 9.1.

### [CONCERN] The upsert has no machine guard and names no SQL change

`UPSERT_SESSION` has no `machine_id` condition, and its conflict clause updates only `heartbeat_at` and `push_confirmed_at` (lines 26-31). A session id owned by another machine is therefore refreshed silently. Task 3.2 (line 107) requires a `StoreError` in that case, and 2.2 (line 80) says the upsert writes the two versions, but neither names the SQL change: no `WHERE` on the machine, no check that a row was affected, and no version columns in the conflict clause. `SELECT_MACHINES` (`src/amoeba/store/sql_machines.py:45`) also needs `door_version` for `MachineRow` (2.2, line 82), and no step names that.

### [CONCERN] Session readers and constructors are not in the task list

`Session` gains two fields (2.2, line 80), but `mcp/presence.py:137` builds one in `_session`, and no step updates it. The reader `store/sessions.py:110` takes columns positionally from `_SESSION_COLUMNS` (`sql_sessions.py:18-22`), which does not select the versions that 7.2's `SessionEntry` needs. 2.3 (line 88) lists test callers only. Unless the new fields have defaults, which the task doesn't say, the section-2 commit (line 97) fails pyright.

### [CONCERN] The third config check breaks a test the task does not name

`test_values_equal_to_both_limits_load` uses heartbeat 7, poll 7, stale 14. The third check needs stale ≥ 7 + 2×7 = 21, so this test fails. 2.4 (lines 91-92) permits only rig changes "without changing what the test asserts", and the Context Summary (line 34) says to fix code rather than tests. This test's assertion has to change to cover the three limits, and no rule covers that. Name it.

### [CONCERN] The exit call's errors are not named

`_delete_row` catches only `StoreError`. Once the exit call goes through the door, `session_end` can raise `HubUnreachableError`, `HubRefusedError` or `ClientFileError`. Those escape `_delete_row`, then the `finally` in `run_presence` (lines 91-93). The module docstring (lines 4-6) says an exception escaping the presence task cancels the loop and ends every tool. Task 4.4 (line 139) says "one shielded session_end attempt bounded by TICK_BOUND_SECONDS" but not which errors it absorbs. 8.2 (line 220) requires an exit with the hub stopped to return within the bound. Name the absorbed set. D4 and D8 say that no reply means the row goes stale.

### [CONCERN] `SessionTiming` and the config read stay on the joined path

`_presence_deps(config)` builds `SessionTiming` from the config's three timing keys (lines 247-261), and `main()` loads the config at line 289 before it builds the deps. Replies now carry the poll interval (4.1, line 124), so `SessionTiming` and `PresenceDeps.timing` should go, and the joined start (6.3, line 184) must not read config. Neither 4.4 nor 6.3 says so. Name the removal, and say what `PresenceDeps` holds on a joined machine.

### [CONCERN] Each worker thread's steps are not named

`steps_for` opens the local store in a context manager and closes it when the block exits (lines 132-144). `LocalSteps` keeps that store (`operations/store_steps.py:26-31`), and sqlite connections cannot cross threads (`wiring_presence.py:4-5`). Tasks 4.1 (line 124) and 4.3 (line 135) run the tick and the after-step in worker threads without saying that each thread enters `steps_for` itself. If the runner reuses the tick's `Steps`, it would use a store whose block has already closed, or one owned by another thread.

### [CONCERN] The wake rule's door version has no source a test can change

`live_member_ids` takes the hub's door version (2.2, line 81), and 2.2 says its caller passes the module constant. The served version is compared in one place, `hub/calls.py:143`. 5.2 (line 163) lets the in-process hub serve a different version, but nothing says the waking rule reads that value. 8.3 (line 226) asserts that a wake is no longer held off after a restart one version up. That cannot be observed if the rule reads the constant. Also, 2.2 names "the presence read" as a second caller. The only caller in `src` is `store/wakes.py:141`.

### [CONCERN] The touch writes an unchecked door version

`_check_without_store` sanitises the client version (line 141) but reads the door version raw (line 142). The touch writes `machines.door_version` on every call with a good token, refused calls included (2.2, line 82; 5.2, line 160), and only session calls get header validation (5.2, line 161). `machines.door_version` is INTEGER (2.1, line 74), and `tests/hub/test_handle_call.py:155` already sends `"9\x1b[2J" + "9" * 200` as this header. Arbitrary text would reach the column, then `hub machines` and `list`. Say the value is parsed as an integer, and is null or unchanged otherwise.

### [CONCERN] Two step pins break, and the load test is not named

`tests/wire/test_protocol.py:121` pins `len(STEP_CALLS) == 16`. `tests/load/test_door_steps_load.py:331` asserts `set(timings) == set(STEP_CALLS)` after timing each step in `_step_documents()`. Two new names break both. 3.3 (line 116) says 262's STEP_CALLS/STEP_MODELS test "passes", which it will not without changes. The load test also needs a document for each new step. Name both files in 3.3.

### [CONCERN] `test_message_timing.py` imports the constant the task deletes

It imports `MCP_CALL_DEADLINE_SECONDS` from `amoeba.mcp.in_process`, which 6.1 (line 175) deletes. 6.1 (line 177) lists only `test_deadline.py` and `test_in_process.py`. The mechanical rule (line 34) would cover it, but following 6.1 as written leaves an ImportError that 10.1 would surface. Add the file to 6.1.

### [CONCERN] A new run state would break `list`, and the `on <machine>` suffix is missing

`RUN_STATE_TEXT` (lines 77-81) has three keys and is indexed at line 187. 7.2 (line 201) adds `other_machine` to `WaitingRunState` with no key here, so any question on another machine raises `KeyError` in `list`. Task 7.3 (lines 205-208) also never mentions the waiting line. The design asks for it to end `on <machine>` (slice design line 450, criterion at line 624) and says that is "as in 262". But `_machine_text` (lines 202-208) renders `machine: <name>`, so 262 does not do that. Name `waiting.py` in 7.3 and add both changes.

### [CONCERN] 10.2 says every walkthrough bullet is already tested

Several bullets in the design walkthrough have no test in 8 or 9: turning push off (slice design line 753), a client that cuts a tool call off (line 736), runs that look old (rendered in 7.3, outside 8 and 9), the deadline refusal (6.2), and the cf-broken and not-a-project bullets (4.2). Name a test for each bullet, or say which are checked by hand and record that in the notes.

### [CONCERN] The load test has no CI gate step

8.6 (lines 238-241) adds latency assertions to `tests/load/test_door_load.py`, and no task wires a CI gate for them. CI runs `uv run pytest` (`ci.yml:40`), and `pyproject.toml:70` ignores only `tests/live`. The load test therefore runs in CI implicitly, but nothing in the task says so or says what fails the build. Add a step that confirms the job collects `tests/load` and states the gate.

### [CONCERN] 4.4 bundles the consumer move with the deletions

4.4 covers the presence task, the resource, server and in-process wiring, two module deletions and the `wiring_presence` deletions. It is also the cut-over that breaks the 241 tests (the first FAIL above). Split it into "consumers move" and "delete the old loops and their tests", so each can be checked on its own.

### [CONCERN] The 260 and 262 amendments belong to no task

6.4 asks to update "the design text" for 260's entry-point table without naming the file. 0.1 (line 44) updates only this design. The slice design's amendments section (lines 527-541) says each amended row is "brought into that design with the same revision", and no task assigns those edits. Name the files and rows, or record that the design revision already made them.

### [NOTE] 0.1 names the wrong design sections

The after-step name `wiring_steps.after_call` appears in the slice design's Interfaces Required (line 89), not in the sections 0.1 lists (Component Structure, D2, D7, Amendments). The test-name and channel-constant conflicts are where 0.1 says.

### [NOTE] 4.3's outcome wording differs from D7's table

Line 135 says "a failed start ... start nothing". The slice design's D7 table (lines 301-307) says a claimed item that fails to start is recorded by `start_claimed`, so it is not a silent no-op. Say which is meant.

### [NOTE] 6.4 misplaces the served check

The `SERVED_OPERATIONS` check is in `wiring_door.route` (line 118), not in `wiring.invoke`. `refuse_if_joined` (lines 80-85) also goes with `NotServedError`, and 6.4 does not name it.

### [NOTE] 9.1 assigns work the code already does

`remove_machine` already deletes the machine's session rows (`DELETE_MACHINE_SESSIONS`, line 294). Only the `machine_runs` delete is new, and 2.2 covers it.

### [NOTE] 9.3's status check needs a call the script does not make

The read-back runs `amoeba list` (`_amoeba_list`, line 447) and reads the store directly (`check_store`, line 192). The "status document holds a machines list" check needs a new `amoeba status` call, which 9.3 (line 260) does not name.

### [NOTE] 8.7's command drops the .env step

1.1 (line 56) sources `.env` before the live channel run, and so does the design's verification walkthrough (slice design line 672). 8.7 omits it. Whether the harness needs it is unverified, but the command should match 1.1.

### [NOTE] The import rules disagree with the existing boundary test

`test_boundary.py` forbids any `amoeba.store` import in `amoeba.mcp`. 4.6 (line 148) allows store error types. The tick has to reach `StoreError` and `ConfigError` through `wiring`, as `inbox_resource.py:27` does through `wiring_presence`. Say so in 4.1, or the rule and the test disagree.

### [NOTE] The final commit holds only notes

The final commit at line 277 holds only the walkthrough notes unless 10.2 fixes a dead end, and AGENTS.md forbids a commit that only adds notes. Say that this commit must carry a fix, or merge it into section 9.

### [NOTE] Some success criteria are only partly tested

- Slice design criterion at line 617: no task runs a tool with no local `config.yaml` present; 6.3 tests only the start.
- Criterion at line 600: "listed and goes stale like any other" for an hour-ahead client is not tested end to end; 3.3 (line 112) checks only the stored times.
- 8.1 (line 216) names no test file for its smoke test.

### Run Digest

- Response length: 30359 chars
- Response is newline-free: no
- Tool calls made: 76
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 77
- Tokens — prompt / cached / cache write / completion / reasoning: 6441918 / 6137537 / 304319 / 197657 / not computed
- Duration: 835.9 s
- Cost: $0.98 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 27
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 27
- Finding-shaped matches — surviving validation: 27
